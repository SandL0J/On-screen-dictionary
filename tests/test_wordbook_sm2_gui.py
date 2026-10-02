"""
Wordbook Flashcard ve SM-2 Arayüzü Birim Testleri
(app/gui/wordbook_window.py & SM-2 Aralıklı Tekrar Entegrasyonu)
"""
import unittest
from unittest.mock import MagicMock
import tkinter as tk
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, date

from app.database import Database
try:
    from app.database import calculate_sm2
except ImportError:
    calculate_sm2 = None
from app.gui.wordbook_window import WordbookWindow


class TestWordbookSM2GUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
            cls.tk_available = True
        except Exception:
            cls.tk_available = False

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, 'tk_available', False) and cls.root:
            try:
                cls.root.destroy()
            except Exception:
                pass

    def setUp(self):
        if not self.tk_available:
            self.skipTest("Tkinter grafik arayüzü bu ortamda mevcut değil")
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_wb_sm2.db"
        self.db = Database(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_calculate_sm2_function(self):
        """calculate_sm2 fonksiyonunun doğru tuple (reps, interval, ef, next_date) döndürdüğünü test eder."""
        if calculate_sm2 is None:
            self.skipTest("calculate_sm2 bağımsız fonksiyon olarak app.database modülünde henüz export edilmemiş")
        today = date(2026, 10, 2)
        # 1. Başarılı tekrar (quality=4, rep=0) -> rep=1, interval=1, ef=2.50, next_date=2026-10-03
        reps, interval, ef, next_date = calculate_sm2(quality=4, repetitions=0, interval_days=0, ease_factor=2.5, today=today)
        self.assertEqual(reps, 1)
        self.assertEqual(interval, 1)
        self.assertEqual(ef, 2.50)
        self.assertEqual(next_date, "2026-10-03")

        # 2. Başarısız tekrar (quality=1, rep=3) -> rep=0, interval=1, ef değişmez
        reps, interval, ef, next_date = calculate_sm2(quality=1, repetitions=3, interval_days=15, ease_factor=2.36, today=today)
        self.assertEqual(reps, 0)
        self.assertEqual(interval, 1)
        self.assertEqual(ef, 2.36)

    def test_stats_display_keys(self):
        """get_review_statistics metodundan dönen total_words, due_today, learned_words değerlerinin stats_lbl metnine doğru yansıdığını test eder."""
        # 1. Mock DB ile tam anahtar testi
        mock_db = MagicMock()
        mock_db.get_words.return_value = []
        mock_db.get_due_words.return_value = []
        mock_db.get_review_statistics.return_value = {
            "total_words": 42,
            "due_today": 9,
            "learned_words": 17,
            "new_words": 16
        }

        wb_mock = WordbookWindow(self.root, mock_db)
        try:
            self.root.update_idletasks()
            expected_text = "Toplam: 42 | Bugün Tekrar: 9 | Öğrenilen: 17"
            self.assertEqual(wb_mock.stats_lbl.cget("text"), expected_text)
        finally:
            wb_mock.window.destroy()

        # 2. Gerçek DB ile test
        # Bir öğrenilmiş kelime (reps >= 3)
        w1 = self.db.add_word("Lernen", "öğrenmek", article="das")
        self.db.update_sm2_review(w1, quality=4)
        self.db.update_sm2_review(w1, quality=4)
        self.db.update_sm2_review(w1, quality=4)

        # Bir yeni kelime (bugün vadesi gelen)
        w2 = self.db.add_word("Buch", "kitap", article="das")

        wb_real = WordbookWindow(self.root, self.db)
        try:
            self.root.update_idletasks()
            stats = self.db.get_review_statistics()
            expected = f"Toplam: {stats['total_words']} | Bugün Tekrar: {stats['due_today']} | Öğrenilen: {stats['learned_words']}"
            self.assertEqual(wb_real.stats_lbl.cget("text"), expected)
            self.assertIn("Toplam: 2", wb_real.stats_lbl.cget("text"))
            self.assertIn("Öğrenilen: 1", wb_real.stats_lbl.cget("text"))
        finally:
            wb_real.window.destroy()

    def test_due_words_queue_flow(self):
        """due modunda vadesi gelen kelimelerin yüklendiğini, _rate_card(4) çağrıldığında db.update_sm2_review metodunun çağrıldığını ve kelimenin kuyruktan eksildiğini doğrular."""
        today_str = datetime.now().strftime("%Y-%m-%d")
        w1_id = self.db.add_word("Hund", "köpek", article="der", next_review_date=today_str)
        w2_id = self.db.add_word("Katze", "kedi", article="die", next_review_date=today_str)

        wb = WordbookWindow(self.root, self.db)
        try:
            self.root.update_idletasks()
            # Varsayılan mod due olmalı
            self.assertEqual(wb.flashcard_mode, "due")
            self.assertEqual(len(wb.flashcard_words), 2)

            # İlk kartı kontrol et
            first_word = wb.flashcard_words[0]
            first_word_id = first_word["id"]

            # Kartı çevir ve 4 (İyi) puanı ver
            wb._flip_card()
            self.assertTrue(wb.is_card_flipped)
            self.assertTrue(wb.is_rating_visible)

            wb._rate_card(4)

            # Veritabanında güncelleme yapılmış olmalı
            updated_w1 = self.db.get_word_by_id(first_word_id)
            self.assertEqual(updated_w1["repetitions"], 1)
            self.assertEqual(updated_w1["status"], "reviewed")

            # İlk kelime kuyruktan çıkarılmış olmalı (kalan: 1)
            self.assertEqual(len(wb.flashcard_words), 1)

            # Kalan son kartı da puanlayalım
            wb._flip_card()
            wb._rate_card(5)

            # Kuyruk boşalmalı ve tebrik mesajı gösterilmeli
            self.assertEqual(len(wb.flashcard_words), 0)
            self.assertIn("Tebrikler", wb.fc_german_lbl.cget("text"))
            self.assertIn("Bugün tekrar edilecek başka kelime kalmadı", wb.fc_turkish_lbl.cget("text"))
            self.assertFalse(wb.is_rating_visible)
        finally:
            wb.window.destroy()

    def test_empty_wordbook_preserves_text(self):
        """Kelime yokken fc_german_lbl içinde 'Henüz kayıtlı' metninin korunduğunu doğrular."""
        wb = WordbookWindow(self.root, self.db)
        try:
            self.root.update_idletasks()
            self.assertEqual(len(wb.flashcard_words), 0)
            self.assertIn("Henüz kayıtlı", wb.fc_german_lbl.cget("text"))
            self.assertIn("Sözlük kartından", wb.fc_turkish_lbl.cget("text"))
            self.assertFalse(wb.is_rating_visible)
        finally:
            wb.window.destroy()

    def test_rating_buttons_visibility(self):
        """Kart çevrilmeden önce ve çevrildikten sonra puanlama butonlarının durumunu doğrular."""
        self.db.add_word("Apfel", "elma", article="der")
        wb = WordbookWindow(self.root, self.db)
        try:
            self.root.update_idletasks()

            # Kart çevrilmeden önce: puan butonları gizli
            self.assertFalse(wb.is_card_flipped)
            self.assertFalse(wb.is_rating_visible)

            # 4 buton da tanımlı ve doğru metinlere sahip
            self.assertIn("Yeniden", wb.btn_rate_again.cget("text"))
            self.assertIn("Zor", wb.btn_rate_hard.cget("text"))
            self.assertIn("İyi", wb.btn_rate_good.cget("text"))
            self.assertIn("Kolay", wb.btn_rate_easy.cget("text"))

            # Kart çevrildiğinde: puan butonları görünür
            wb._flip_card()
            self.root.update_idletasks()
            self.assertTrue(wb.is_card_flipped)
            self.assertTrue(wb.is_rating_visible)

            # Kart tekrar çevrildiğinde (ön yüze dönüldüğünde): puan butonları gizli
            wb._flip_card()
            self.root.update_idletasks()
            self.assertFalse(wb.is_card_flipped)
            self.assertFalse(wb.is_rating_visible)
        finally:
            wb.window.destroy()

    def test_mode_switching_due_and_all(self):
        """Çalışma modları arasında (due vs all) geçiş yapıldığında kelime kuyruğunun ve buton renklerinin güncellendiğini doğrular."""
        # 1 vadesi bugün olan, 1 vadesi 2099'a ötelenmiş kelime ekleyelim
        self.db.add_word("HeuteWord", "bugünkü", article="das", next_review_date=datetime.now().strftime("%Y-%m-%d"))
        self.db.add_word("FutureWord", "gelecekteki", article="die", next_review_date="2099-12-31")

        wb = WordbookWindow(self.root, self.db)
        try:
            self.root.update_idletasks()

            # Varsayılan mod 'due': sadece bugün vadesi gelen olmalı
            self.assertEqual(wb.flashcard_mode, "due")
            self.assertEqual(len(wb.flashcard_words), 1)
            self.assertEqual(wb.flashcard_words[0]["german"], "HeuteWord")

            # 'all' moduna geç
            wb._set_flashcard_mode("all")
            self.root.update_idletasks()
            self.assertEqual(wb.flashcard_mode, "all")
            self.assertEqual(len(wb.flashcard_words), 2)

            # 'all' modunda puan verildiğinde kelime kuyruktan silinmez
            wb._flip_card()
            wb._rate_card(4)
            self.assertEqual(len(wb.flashcard_words), 2, "Tüm kelimeler modunda kelime kuyruktan eksilmemelidir")

            # Tekrar 'due' moduna dön
            wb._set_flashcard_mode("due")
            self.root.update_idletasks()
            self.assertEqual(wb.flashcard_mode, "due")
            # due modunda get_due_words sonuçları yüklenmelidir
            due_words = self.db.get_due_words(target_date=None, limit=None)
            self.assertEqual(len(wb.flashcard_words), len(due_words))
        finally:
            wb.window.destroy()


if __name__ == "__main__":
    unittest.main()
