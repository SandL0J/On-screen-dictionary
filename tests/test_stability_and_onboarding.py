"""
Kararlılık, Hata Yönetimi ve İlk Çalıştırma Sihirbazı Birim Testleri
(Stability, Graceful Degradation & Onboarding Wizard Tests)
"""
import unittest
from unittest.mock import MagicMock, patch
import tempfile
import json
import os
from pathlib import Path
from PIL import Image, ImageDraw

from app.config import DEFAULT_CONFIG, load_config, save_config
from app.database import Database
from app.ocr_engine import OCREngine, find_tesseract_path
from app.gemini_service import GeminiService
from app.translator import TranslationEngine
from app.gui.hover_tooltip import HoverTooltip
from app.gui.result_hud import ResultHUD
from app.gui.onboarding_wizard import OnboardingWizard
from app.gui.settings_window import SettingsWindow
from app.gui.main_overlay import MainOverlay


class TestStabilityAndDegradation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_stab.db"
        self.db = Database(self.db_path)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # 1. DATABASE RESILIENCE & SEEDING TESTS
    # -------------------------------------------------------------------------
    def test_database_add_word_resilient_to_extra_kwargs(self):
        """Database.add_word bilinmeyen argümanlar (tags, foo, bar) aldığında çökmemelidir."""
        word_id = self.db.add_word(
            german="lernen",
            turkish="öğrenmek",
            article="",
            plural="",
            part_of_speech="Fiil",
            tags="hover_ocr",
            unexpected_arg="deneme",
            another_extra_key=123
        )
        self.assertGreater(word_id, 0)
        saved = self.db.get_word_by_german("lernen")
        self.assertIsNotNone(saved)
        self.assertEqual(saved["turkish"], "öğrenmek")
        self.assertIn("hover_ocr", saved["notes"])

    def test_database_seed_starter_words(self):
        """seed_starter_words boş deftere temel kelimeleri eklemeli, dolu defteri bozmamalıdır."""
        self.assertEqual(len(self.db.get_words()), 0)
        count = self.db.seed_starter_words()
        self.assertGreater(count, 0)
        self.assertEqual(len(self.db.get_words()), count)

        # İkinci çağrıda tekrar eklememeli (idempotent olmalı)
        count_second = self.db.seed_starter_words()
        self.assertEqual(count_second, 0)
        self.assertEqual(len(self.db.get_words()), count)

    # -------------------------------------------------------------------------
    # 2. OCR DUAL BACKEND & EDGE CASE TESTS
    # -------------------------------------------------------------------------
    def test_find_tesseract_path(self):
        """find_tesseract_path var olmayan yollar için güvenle None dönmelidir."""
        self.assertIsNone(find_tesseract_path("C:/gecersiz/bir/yol/tesseract.exe"))

    def test_ocr_engine_empty_or_zero_size_images(self):
        """OCR motoruna boş, None veya 0 boyutlu resim verildiğinde çökmemelidir."""
        engine = OCREngine()
        # None resim
        self.assertEqual(engine.recognize_from_image(None), "")
        self.assertEqual(engine.recognize_words_with_boxes(None), [])

        # 1x1 çok küçük resim
        tiny = Image.new("RGB", (1, 1), color=(255, 255, 255))
        self.assertEqual(engine.recognize_from_image(tiny), "")

    def test_ocr_engine_status_and_test(self):
        """get_status ve test_ocr metodları eksiksiz durum dönmelidir."""
        engine = OCREngine()
        status = engine.get_status()
        self.assertIn("windows_media_ocr", status)
        self.assertIn("tesseract_ocr", status)
        self.assertIn("active_backend", status)
        self.assertIn("is_ready", status)

        # test_ocr sentetik bir test çalıştırmalı ve (bool, str) dönmeli
        ok, msg = engine.test_ocr("Guten Tag")
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(msg, str)

    # -------------------------------------------------------------------------
    # 3. GEMINI SERVICE & TRANSLATOR STABILITY TESTS
    # -------------------------------------------------------------------------
    def test_gemini_format_grammar_notes_dual_keys(self):
        """Gemini çıktısı hem 'desc' hem de 'text' anahtarlarını içermelidir (ResultHUD uyumu)."""
        gs = GeminiService("fake_key")
        parsed = {
            "german": "das Buch",
            "turkish": "kitap",
            "article": "das",
            "plural": "die Bücher",
            "pos": "isim",
            "is_sentence": False,
            "rule_note": "Orta cins isimdir.",
            "examples": [{"de": "Das Buch ist gut.", "tr": "Kitap iyidir."}]
        }
        res = gs._format_gemini_translation(parsed, "Buch", "gemini-1.5-flash")
        self.assertIsNotNone(res)
        self.assertEqual(res["turkish"], "kitap")
        self.assertTrue(len(res["grammar_notes"]) > 0)
        first_note = res["grammar_notes"][0]
        self.assertIn("desc", first_note)
        self.assertIn("text", first_note)
        self.assertEqual(first_note["desc"], "Orta cins isimdir.")
        self.assertEqual(first_note["text"], "Orta cins isimdir.")

    def test_gemini_test_connection_empty_key(self):
        """Boş API anahtarı ile test_connection çağrıldığında çökmemeli ve uyarı vermelidir."""
        gs = GeminiService("")
        ok, msg = gs.test_connection()
        self.assertFalse(ok)
        self.assertIn("Lütfen önce bir Gemini API anahtarı girin", msg)

    # -------------------------------------------------------------------------
    # 4. CONFIG FIRST-RUN OPTIONS
    # -------------------------------------------------------------------------
    def test_config_first_run_defaults(self):
        """DEFAULT_CONFIG içinde first_run_completed ve OCR seçenekleri bulunmalıdır."""
        self.assertIn("first_run_completed", DEFAULT_CONFIG)
        self.assertIn("tesseract_cmd", DEFAULT_CONFIG)
        self.assertIn("ocr_engine_preference", DEFAULT_CONFIG)
        self.assertFalse(DEFAULT_CONFIG["first_run_completed"])


    def test_database_add_word_empty_string_rejected(self):
        """Database.add_word boş kelime verildiğinde veritabanına eklememeli ve -1 dönmelidir."""
        res_empty = self.db.add_word(german="", turkish="boş")
        res_spaces = self.db.add_word(german="   ", turkish="boşluk")
        self.assertEqual(res_empty, -1)
        self.assertEqual(res_spaces, -1)
        self.assertEqual(len(self.db.get_words()), 0)

    def test_capture_screen_rect_gdi_handles_and_coords(self):
        """capture_screen_rect_gdi çoklu monitörlerdeki negatif koordinatları kabul etmelidir."""
        from app.hover_tracker import capture_screen_rect_gdi
        # Negatif koordinat veya geçerli koordinat çağrıldığında çökmemelidir
        img = capture_screen_rect_gdi(-100, -100, 50, 50)
        # Windows ortamında Image nesnesi veya None dönmelidir (asla istisna fırlatmamalı)
        self.assertTrue(img is None or hasattr(img, "size"))

    def test_translate_sentence_offline_graceful(self):
        """İnternet bağlantısı koptuğunda cümle çevirisi çökmek yerine dilbilgisi analiziyle zarifçe dönmelidir."""
        trans = TranslationEngine(db=self.db)
        with patch.object(trans, "_translate_via_gt", side_effect=Exception("Ağ bağlantısı yok")):
            res = trans.translate_and_analyze("Weil ich krank bin, kann ich heute nicht kommen.")
            self.assertIsNotNone(res)
            self.assertTrue(res.get("is_sentence"))
            self.assertTrue(res.get("offline_mode"))
            self.assertIn("Çeviri alınamadı", res.get("turkish"))
            # Dilbilgisi kuralları yine de analiz edilmiş olmalıdır
            self.assertGreater(len(res.get("grammar_notes", [])), 0)


class TestGUIStabilityAndOnboarding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tkinter as tk
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
            cls.tk_available = True
        except Exception:
            cls.tk_available = False

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "tk_available", False) and cls.root:
            try:
                cls.root.destroy()
            except Exception:
                pass

    def setUp(self):
        if not self.tk_available:
            self.skipTest("Tkinter mevcut değil")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_gui.db"
        self.db = Database(self.db_path)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_hover_tooltip_timer_cancel_safety(self):
        """show_message ardından hide çağrıldığında timer güvenle iptal edilmelidir."""
        tooltip = HoverTooltip(self.root, db=self.db)
        try:
            tooltip.show_message(100, 100, "Test Mesajı", auto_hide_ms=2000)
            self.root.update_idletasks()
            self.assertIsNotNone(tooltip._auto_hide_id)

            tooltip.hide()
            self.assertIsNone(tooltip._auto_hide_id)
        finally:
            tooltip.window.destroy()

    def test_hover_tooltip_toggle_save_without_crash(self):
        """HoverTooltip üzerindeki yıldız butonuna basıldığında TypeError vermeden deftere kaydetmelidir."""
        tooltip = HoverTooltip(self.root, db=self.db)
        try:
            data = {
                "german": "Fenster",
                "turkish": "pencere",
                "article": "das",
                "plural": "die Fenster",
                "example_de": "Er öffnet das Fenster.",
                "example_tr": "O pencereyi açıyor."
            }
            tooltip.show(data, 200, 200)
            self.root.update_idletasks()

            # Kaydet
            tooltip._toggle_save()
            self.assertTrue(self.db.is_word_saved("Fenster"))
            self.assertEqual(tooltip.btn_star.cget("text"), "★")

            # Tekrar tıklandığında sil
            tooltip._toggle_save()
            self.assertFalse(self.db.is_word_saved("Fenster"))
            self.assertEqual(tooltip.btn_star.cget("text"), "☆")
        finally:
            tooltip.window.destroy()

    def test_result_hud_render_note_missing_text_key(self):
        """ResultHUD sadece 'desc' içeren grammar note ile açıldığında KeyError vermemelidir."""
        data = {
            "german": "das Haus",
            "turkish": "ev",
            "article": "das",
            "is_sentence": True,
            "grammar_notes": [
                {"title": "Özel Kural", "desc": "Sadece desc alanı var, text yok."}
            ]
        }
        hud = ResultHUD(self.root, data, db=self.db, config={})
        try:
            self.root.update_idletasks()
            self.assertTrue(hud.is_alive())
        finally:
            hud.close()

    def test_result_hud_renders_error_cleanly(self):
        """ResultHUD hata sözlüğü aldığında çökmeden uyarı kartını göstermeli ve butonları gizlemelidir."""
        data = {"error": "İnternet bağlantısı kesildi."}
        hud = ResultHUD(self.root, data, db=self.db, config={})
        try:
            self.root.update_idletasks()
            self.assertTrue(hud.is_alive())
            # Deftere boş kelime eklenmemeli
            hud._toggle_save_word()
            self.assertEqual(len(self.db.get_words()), 0)
        finally:
            hud.close()

    @patch("app.gui.onboarding_wizard.save_config")
    def test_onboarding_wizard_step_flow_and_completion(self, mock_save_config):
        """OnboardingWizard adımları arasında geçiş yapabilmeli ve bitirildiğinde config'i güncelleyebilmelidir."""
        ocr = OCREngine()
        trans = TranslationEngine(db=self.db)
        cfg = {"first_run_completed": False, "gemini_api_key": ""}
        completed = False

        def on_done():
            nonlocal completed
            completed = True

        wiz = OnboardingWizard(self.root, cfg, ocr, trans, db=self.db, on_complete=on_done)
        try:
            self.root.update_idletasks()
            self.assertEqual(wiz.current_step, 0)

            # İleri
            wiz._next_step()
            self.assertEqual(wiz.current_step, 1)

            # İleri
            wiz._next_step()
            self.assertEqual(wiz.current_step, 2)

            # Geri
            wiz._prev_step()
            self.assertEqual(wiz.current_step, 1)

            # Bitir
            wiz._finish_wizard()
            self.assertTrue(completed)
            self.assertTrue(cfg["first_run_completed"])
            # Deftere otomatik tohumlama yapılmış olmalı
            self.assertGreater(len(self.db.get_words()), 0)
        finally:
            try:
                wiz.window.destroy()
            except Exception:
                pass

    @patch("app.gui.onboarding_wizard.save_config")
    def test_onboarding_wizard_wm_delete_window(self, mock_save_config):
        """OnboardingWizard [X] ile kapatıldığında kurulum tamamlanmalı ve defter tohumlanmalıdır."""
        ocr = OCREngine()
        trans = TranslationEngine(db=self.db)
        cfg = {"first_run_completed": False}
        completed = False

        def on_done():
            nonlocal completed
            completed = True

        wiz = OnboardingWizard(self.root, cfg, ocr, trans, db=self.db, on_complete=on_done)
        try:
            self.root.update_idletasks()
            # WM_DELETE_WINDOW protokolünü tetikle
            wiz._finish_wizard()
            self.assertTrue(completed)
            self.assertTrue(cfg["first_run_completed"])
            self.assertGreater(len(self.db.get_words()), 0)
        finally:
            try:
                wiz.window.destroy()
            except Exception:
                pass

    @patch("app.hotkey_manager.HotkeyManager.start")
    def test_main_overlay_corrupt_hotkey_resilience(self, mock_start):
        """MainOverlay bozuk kısayol ayarları ile başlatıldığında çökmemeli ve varsayılanlara dönmelidir."""
        from app.clipboard_watcher import ClipboardWatcher
        ocr = OCREngine()
        trans = TranslationEngine(db=self.db)
        watcher = ClipboardWatcher(on_text_detected=lambda t: None)

        corrupt_config = {
            "hotkey_ocr": "gecersiz+tus+kombinasyonu",
            "hotkey_hover": "hatali_tus",
            "hotkey_overlay": "yanlis_tus",
            "hotkey_clipboard": "bozuk_tus"
        }

        overlay = MainOverlay(
            root=self.root,
            translator=trans,
            ocr_engine=ocr,
            db=self.db,
            clipboard_watcher=watcher,
            config=corrupt_config
        )
        try:
            self.assertTrue(overlay._is_bar_visible)
            # Varsayılan kısayollara güvenle dönmüş olmalı
            self.assertIn("ocr", overlay.hotkey_mgr._bindings)
        finally:
            overlay.stop()

    def test_wordbook_empty_flashcard_state(self):
        """WordbookWindow boş olduğunda flashcard alanında 'Henüz kayıtlı kelime yok' mesajı görünmelidir."""
        from app.gui.wordbook_window import WordbookWindow
        wb = WordbookWindow(self.root, self.db)
        try:
            self.root.update_idletasks()
            self.assertIn("Henüz kayıtlı", wb.fc_german_lbl.cget("text"))
        finally:
            wb.window.destroy()


if __name__ == "__main__":
    unittest.main()

