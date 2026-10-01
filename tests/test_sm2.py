"""
SuperMemo 2 (SM-2) Aralıklı Tekrar Algoritması ve Veritabanı Entegrasyon Testleri
"""
import unittest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta

from app.database import Database


class TestSM2SpacedRepetition(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_sm2.db"
        self.db = Database(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_quality_3_ease_factor_reduction(self):
        """quality=3: ease_factor 2.5 -> 2.36'ya düşmelidir."""
        word_id = self.db.add_word("Katze", "kedi", article="die")
        self.assertGreater(word_id, 0)

        initial_word = self.db.get_word_by_id(word_id)
        self.assertEqual(initial_word["ease_factor"], 2.5)

        updated = self.db.update_sm2_review(word_id, quality=3)
        self.assertIsNotNone(updated)
        self.assertAlmostEqual(updated["ease_factor"], 2.36, places=2)
        self.assertEqual(updated["repetitions"], 1)
        self.assertEqual(updated["interval_days"], 1)

    def test_quality_1_resets_repetitions_interval_ease_unchanged(self):
        """repetitions=3 iken quality=1 verilince repetitions=0, interval=1, ease değişmez."""
        # 3 başarılı tekrar yapıp repetitions=3 durumuna getirelim
        word_id = self.db.add_word("Lernen", "öğrenmek")
        self.db.update_sm2_review(word_id, quality=4)  # rep: 1, interval: 1, EF: 2.50
        self.db.update_sm2_review(word_id, quality=4)  # rep: 2, interval: 6, EF: 2.50
        word_rep3 = self.db.update_sm2_review(word_id, quality=4)  # rep: 3, interval: 15, EF: 2.50

        self.assertEqual(word_rep3["repetitions"], 3)
        current_ef = word_rep3["ease_factor"]
        self.assertEqual(current_ef, 2.5)

        # Şimdi başarısız tekrar (quality=1) verelim
        updated = self.db.update_sm2_review(word_id, quality=1)
        self.assertIsNotNone(updated)
        self.assertEqual(updated["repetitions"], 0, "quality < 3 durumunda repetitions sıfırlanmalıdır")
        self.assertEqual(updated["interval_days"], 1, "quality < 3 durumunda interval 1 güne düşmelidir")
        self.assertEqual(updated["ease_factor"], current_ef, "quality < 3 durumunda ease factor değişmemelidir")

    def test_add_word_assigns_today_as_next_review_date(self):
        """add_word yeni kelimeye next_review_date = bugün atar."""
        today_str = datetime.now().strftime("%Y-%m-%d")
        word_id = self.db.add_word("Hund", "köpek", article="der")
        self.assertGreater(word_id, 0)

        word = self.db.get_word_by_id(word_id)
        self.assertIsNotNone(word)
        self.assertEqual(word["next_review_date"], today_str)
        self.assertEqual(word["ease_factor"], 2.5)
        self.assertEqual(word["interval_days"], 0)
        self.assertEqual(word["repetitions"], 0)
        self.assertIsNone(word["last_reviewed_at"])

    def test_same_word_readded_preserves_sm2_fields(self):
        """Aynı kelime tekrar eklenince SM-2 alanları sıfırlanmaz."""
        word_id = self.db.add_word("Apfel", "elma", article="der")
        
        # Kelimeyi tekrar edelim ve SM-2 değerlerini ilerletelim
        reviewed = self.db.update_sm2_review(word_id, quality=5)
        self.assertIsNotNone(reviewed)
        self.assertAlmostEqual(reviewed["ease_factor"], 2.6, places=2)
        self.assertEqual(reviewed["repetitions"], 1)
        self.assertEqual(reviewed["interval_days"], 1)
        self.assertEqual(reviewed["status"], "reviewed")
        expected_next_review = reviewed["next_review_date"]
        expected_last_reviewed = reviewed["last_reviewed_at"]

        # Aynı kelimeyi yeniden ekleyelim (örneğin güncellenmiş Türkçe veya not ile)
        readded_id = self.db.add_word("Apfel", "kırmızı elma", article="der", notes="Önemli meyve")
        self.assertEqual(readded_id, word_id)

        # Veritabanından kelimeyi tekrar çekip SM-2 alanlarının korunduğunu doğrulayalım
        current_word = self.db.get_word_by_id(word_id)
        self.assertEqual(current_word["turkish"], "kırmızı elma", "Türkçe anlam güncellenmiş olmalı")
        self.assertEqual(current_word["notes"], "Önemli meyve", "Notlar güncellenmiş olmalı")
        self.assertAlmostEqual(current_word["ease_factor"], 2.6, places=2, msg="ease_factor sıfırlanmamalı")
        self.assertEqual(current_word["repetitions"], 1, "repetitions sıfırlanmamalı")
        self.assertEqual(current_word["interval_days"], 1, "interval_days sıfırlanmamalı")
        self.assertEqual(current_word["next_review_date"], expected_next_review, "next_review_date sıfırlanmamalı")
        self.assertEqual(current_word["last_reviewed_at"], expected_last_reviewed, "last_reviewed_at sıfırlanmamalı")
        self.assertEqual(current_word["status"], "reviewed", "status korunmalı")

    def test_sm2_minimum_ease_factor_boundary(self):
        """Ease factor asla 1.3'ün altına düşmemelidir."""
        word_id = self.db.add_word("Schwierig", "zor")
        # Sürekli quality=3 vererek EF'yi düşürelim
        for _ in range(15):
            updated = self.db.update_sm2_review(word_id, quality=3)
        self.assertGreaterEqual(updated["ease_factor"], 1.3)
        self.assertAlmostEqual(updated["ease_factor"], 1.3, places=2)

    def test_get_due_words(self):
        """get_due_words vadesi gelen kelimeleri doğru filtrelemelidir."""
        today = datetime.now().date()
        today_str = today.strftime("%Y-%m-%d")
        yesterday_str = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        tomorrow_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")

        # Bugün vadesi gelen kelime
        w1_id = self.db.add_word("Heute", "bugün", next_review_date=today_str)
        # Dünden kalmış vadesi geçmiş kelime
        w2_id = self.db.add_word("Gestern", "dün", next_review_date=yesterday_str)
        # Yarın vadesi gelecek kelime (bugün listelenmemeli)
        w3_id = self.db.add_word("Morgen", "yarın", next_review_date=tomorrow_str)

        due_words = self.db.get_due_words(today_str)
        due_ids = [w["id"] for w in due_words]

        self.assertIn(w1_id, due_ids)
        self.assertIn(w2_id, due_ids)
        self.assertNotIn(w3_id, due_ids)

    def test_update_sm2_review_sets_status_reviewed(self):
        """update_sm2_review çağrıldığında kelime durumu 'reviewed' olmalıdır."""
        word_id = self.db.add_word("Wasser", "su")
        self.assertEqual(self.db.get_word_by_id(word_id)["status"], "learning")

        updated = self.db.update_sm2_review(word_id, quality=4)
        self.assertEqual(updated["status"], "reviewed")


if __name__ == "__main__":
    unittest.main()
