"""
SuperMemo 2 (SM-2) Aralıklı Tekrar Algoritması ve Veritabanı Entegrasyon Testleri
"""
import unittest
import tempfile
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, date

from app.database import Database, calculate_sm2


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
        word_id = self.db.add_word("Lernen", "öğrenmek")
        self.db.update_sm2_review(word_id, quality=4)  # rep: 1, interval: 1, EF: 2.50
        self.db.update_sm2_review(word_id, quality=4)  # rep: 2, interval: 6, EF: 2.50
        word_rep3 = self.db.update_sm2_review(word_id, quality=4)  # rep: 3, interval: 15, EF: 2.50

        self.assertEqual(word_rep3["repetitions"], 3)
        current_ef = word_rep3["ease_factor"]
        self.assertEqual(current_ef, 2.5)

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
        
        reviewed = self.db.update_sm2_review(word_id, quality=5)
        self.assertIsNotNone(reviewed)
        self.assertAlmostEqual(reviewed["ease_factor"], 2.6, places=2)
        self.assertEqual(reviewed["repetitions"], 1)
        self.assertEqual(reviewed["interval_days"], 1)
        self.assertEqual(reviewed["status"], "reviewed")
        expected_next_review = reviewed["next_review_date"]
        expected_last_reviewed = reviewed["last_reviewed_at"]

        readded_id = self.db.add_word("Apfel", "kırmızı elma", article="der", notes="Önemli meyve")
        self.assertEqual(readded_id, word_id)

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

        w1_id = self.db.add_word("Heute", "bugün", next_review_date=today_str)
        w2_id = self.db.add_word("Gestern", "dün", next_review_date=yesterday_str)
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

    def test_migration_from_old_schema_idempotent(self):
        """Eski şemadan göç (migration) ve ikinci çalıştırmada hatasız çalışma testi."""
        old_db_path = Path(self.temp_dir) / "old_schema.db"
        conn = sqlite3.connect(old_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE wordbook (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                german TEXT NOT NULL,
                article TEXT DEFAULT '',
                plural TEXT DEFAULT '',
                turkish TEXT NOT NULL,
                part_of_speech TEXT DEFAULT '',
                example_de TEXT DEFAULT '',
                example_tr TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                status TEXT DEFAULT 'learning',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("INSERT INTO wordbook (german, turkish) VALUES ('AlteKatze', 'eski kedi')")
        conn.commit()
        conn.close()

        # 1. İlk çalıştırma: Sütun göçü (ALTER TABLE) çalışmalı
        db1 = Database(old_db_path)
        word1 = db1.get_word_by_id(1)
        self.assertIsNotNone(word1)
        self.assertEqual(word1["ease_factor"], 2.5)
        self.assertEqual(word1["interval_days"], 0)
        self.assertEqual(word1["repetitions"], 0)

        # 2. İkinci çalıştırma: Tekrar eden göç hataya (duplicate column name) yol açmamalı
        db2 = Database(old_db_path)
        updated = db2.update_sm2_review(1, quality=4)
        self.assertIsNotNone(updated)
        self.assertEqual(updated["repetitions"], 1)

    def test_get_review_statistics_four_counters(self):
        """get_review_statistics yeni anahtar setini (total_words, due_today, learned_words, new_words) doğrulamalıdır."""
        today_str = datetime.now().strftime("%Y-%m-%d")

        # 1. Yeni kelime (last_reviewed_at IS NULL, reps=0, due_today)
        w1 = self.db.add_word("Neu1", "yeni 1")

        # 2. Yeni kelime ancak ileri bir tarihe ötelenmiş (last_reviewed_at IS NULL, reps=0, due_today DEĞİL)
        w2 = self.db.add_word("Neu2", "yeni 2", next_review_date="2099-01-01")

        # 3. 3 kez tekrar edilmiş öğrenilmiş kelime (learned_words: reps >= 3, last_reviewed_at NOT NULL)
        w3 = self.db.add_word("Gelernt", "öğrenilmiş")
        self.db.update_sm2_review(w3, quality=4)
        self.db.update_sm2_review(w3, quality=4)
        self.db.update_sm2_review(w3, quality=4)

        # 4. 1 kez tekrar edilmiş öğrenilmekte olan kelime (reps=1 < 3, last_reviewed_at NOT NULL)
        w4 = self.db.add_word("Lernen", "öğrenilen")
        self.db.update_sm2_review(w4, quality=4)

        stats = self.db.get_review_statistics(today_str)

        # İstenen anahtarların varlığı
        self.assertIn("total_words", stats)
        self.assertIn("due_today", stats)
        self.assertIn("learned_words", stats)
        self.assertIn("new_words", stats)

        # Anahtarların doğruluğu
        self.assertEqual(stats["total_words"], 4, "total_words tüm kayıtları saymalıdır (4 kelime)")
        self.assertEqual(stats["new_words"], 2, "new_words last_reviewed_at IS NULL olanları saymalıdır (w1 ve w2)")
        self.assertEqual(stats["learned_words"], 1, "learned_words repetitions >= 3 olanları saymalıdır (yalnızca w3)")

        due_words = self.db.get_due_words(today_str)
        self.assertEqual(stats["due_today"], len(due_words), "due_today get_due_words ile aynı koşulda limitsiz sayım yapmalıdır")

        # Geriye dönük uyumluluk anahtarlarının varlığı
        self.assertIn("total", stats)
        self.assertIn("due", stats)
        self.assertIn("learning", stats)
        self.assertIn("reviewed", stats)

    def test_sm2_ease_factor_clamping_minimum_1_3(self):
        """Ease factor kalitesi ne kadar düşük olursa olsun 1.3'e clamp edilmelidir."""
        # Başlangıçta EF 1.35 olan bir kelime ekleyelim
        word_id = self.db.add_word("ExtremSchwer", "çok zor", ease_factor=1.35)
        # quality=3 verildiğinde EF delta -0.14 olur (1.35 - 0.14 = 1.21). Clamping ile 1.3 olmalıdır.
        updated = self.db.update_sm2_review(word_id, quality=3)
        self.assertEqual(updated["ease_factor"], 1.3, "EF 1.3 altına düşmemeli ve 1.3'e clamp edilmelidir")

    def test_sm2_with_fixed_today_date(self):
        """Sabit 'today' tarihi verildiğinde sonraki tekrar tarihleri deterministik hesaplanmalıdır."""
        fixed_day1 = date(2026, 10, 1)
        word_id = self.db.add_word("FixDatum", "sabit tarih")

        # 1. Tekrar (quality=4): interval=1 gün -> next_review_date = 2026-10-02
        rev1 = self.db.update_sm2_review(word_id, quality=4, review_date=fixed_day1)
        self.assertEqual(rev1["repetitions"], 1)
        self.assertEqual(rev1["interval_days"], 1)
        self.assertEqual(rev1["next_review_date"], "2026-10-02")

        # 2. Tekrar (quality=4) 2026-10-02 tarihinde: interval=6 gün -> next_review_date = 2026-10-08
        rev2 = self.db.update_sm2_review(word_id, quality=4, review_date=date(2026, 10, 2))
        self.assertEqual(rev2["repetitions"], 2)
        self.assertEqual(rev2["interval_days"], 6)
        self.assertEqual(rev2["next_review_date"], "2026-10-08")

        # 3. Tekrar (quality=4) 2026-10-08 tarihinde: interval=round(6 * 2.5) = 15 gün -> next_review_date = 2026-10-23
        rev3 = self.db.update_sm2_review(word_id, quality=4, review_date=date(2026, 10, 8))
        self.assertEqual(rev3["repetitions"], 3)
        self.assertEqual(rev3["interval_days"], 15)
        self.assertEqual(rev3["next_review_date"], "2026-10-23")

    def test_due_today_and_get_due_words_with_null_next_review_date(self):
        """next_review_date'i NULL olan bir satir ekleyip due_today == len(get_due_words(limit=cok buyuk)) oldugunu dogrular."""
        # 1. Normal vadesi bugun olan bir kelime
        w1 = self.db.add_word("Heute", "bugun")

        # 2. Gelecek tarihe otelenmis kelime (vadesi gelmemis)
        w2 = self.db.add_word("Zukunft", "gelecek", next_review_date="2099-12-31")

        # 3. next_review_date'i acikca NULL olan bir kelime ekleyelim
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO wordbook (german, turkish, status, next_review_date)
                VALUES ('OhneDatum', 'tarihsiz', 'learning', NULL)
            """)
            conn.commit()
            null_word_id = cursor.lastrowid

        today_str = datetime.now().strftime("%Y-%m-%d")
        stats = self.db.get_review_statistics(today_str)
        # Cok buyuk limit ile get_due_words cagrisi
        due_words = self.db.get_due_words(target_date=today_str, limit=100000)

        # due_today == len(get_due_words(limit=cok buyuk)) dogrulamasi
        self.assertEqual(stats["due_today"], len(due_words))

        due_ids = [w["id"] for w in due_words]
        self.assertIn(w1, due_ids, "Bugunku kelime vadesi gelenlerde yer almalidir")
        self.assertIn(null_word_id, due_ids, "next_review_date NULL olan kelime vadesi gelenlerde yer almalidir")
        self.assertNotIn(w2, due_ids, "Gelecek tarihli kelime vadesi gelenlerde yer almamalidir")

    def test_calculate_sm2_quality_clamping(self):
        """calculate_sm2 fonksiyonunun quality=0 ve quality=9 gibi aralik disi degerleri 1-5 araligina kirptigini dogrular."""
        today = date(2026, 10, 2)
        # quality=0 verilince 1'e kirpilmali (quality < 3 basarisiz tekrar: reps=0, interval=1, ef degismez)
        reps_0, interval_0, ef_0, next_0 = calculate_sm2(quality=0, repetitions=3, interval_days=15, ease_factor=2.5, today=today)
        reps_1, interval_1, ef_1, next_1 = calculate_sm2(quality=1, repetitions=3, interval_days=15, ease_factor=2.5, today=today)
        self.assertEqual(reps_0, 0)
        self.assertEqual(interval_0, 1)
        self.assertEqual(ef_0, 2.5)
        self.assertEqual((reps_0, interval_0, ef_0, next_0), (reps_1, interval_1, ef_1, next_1))

        # quality=9 verilince 5'e kirpilmali (quality=5 mukemmel tekrar: reps=1, interval=1, ef=2.60)
        reps_9, interval_9, ef_9, next_9 = calculate_sm2(quality=9, repetitions=0, interval_days=0, ease_factor=2.5, today=today)
        reps_5, interval_5, ef_5, next_5 = calculate_sm2(quality=5, repetitions=0, interval_days=0, ease_factor=2.5, today=today)
        self.assertEqual(reps_9, 1)
        self.assertEqual(interval_9, 1)
        self.assertEqual(ef_9, 2.60)
        self.assertEqual((reps_9, interval_9, ef_9, next_9), (reps_5, interval_5, ef_5, next_5))


if __name__ == "__main__":
    unittest.main()

