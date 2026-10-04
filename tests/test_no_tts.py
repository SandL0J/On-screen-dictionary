"""
Dinleme / TTS Özelliğinin Kaldırılması Doğrulama Testleri
Bu test paketi, dinleme (TTS / sesli telaffuz) özelliğinin arayüzden ve uygulama akışından
tamamen ve güvenle kaldırıldığını doğrular.
"""
import unittest
from unittest.mock import patch
import tkinter as tk
import tempfile
import gc
from pathlib import Path

from app.config import DEFAULT_CONFIG, load_config, save_config
from app.database import Database
from app.gui.result_hud import ResultHUD
from app.gui.wordbook_window import WordbookWindow
from app.gui.settings_window import SettingsWindow
from app.gui.main_overlay import MainOverlay
from app.translator import TranslationEngine
from app.ocr_engine import OCREngine
from app.clipboard_watcher import ClipboardWatcher
from app.tts_engine import GermanTTSEngine


class DummyTTS:
    def __init__(self):
        self.play_called = False
        self.played_text = None

    def play(self, text):
        self.play_called = True
        self.played_text = text


class TestTTSFeatureRemoval(unittest.TestCase):
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
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp_dir.name) / "test_no_tts.db")
        self.dummy_tts = DummyTTS()

    def tearDown(self):
        self.db = None
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass
        if getattr(self, "tk_available", False) and self.root:
            for child in list(self.root.winfo_children()):
                try:
                    child.destroy()
                except Exception:
                    pass
            try:
                self.root.update()
            except Exception:
                pass

    def test_config_sound_enabled_removed(self):
        """DEFAULT_CONFIG içinde 'sound_enabled' anahtarı bulunmamalıdır."""
        self.assertNotIn("sound_enabled", DEFAULT_CONFIG)

    def test_result_hud_no_sound_button(self):
        """ResultHUD penceresinde '🔊 Dinle' butonu bulunmamalıdır."""
        if not self.tk_available:
            self.skipTest("Tkinter arayüzü mevcut değil")

        data = {
            "german": "Apfel",
            "article": "der",
            "article_color": "#3b82f6",
            "turkish": "elma",
            "is_sentence": False,
        }
        hud = ResultHUD(self.root, data, db=self.db, config={}, tts_engine=self.dummy_tts)
        try:
            # hud.btn_sound niteliği olmamalı
            self.assertFalse(hasattr(hud, "btn_sound"))

            # footer_frame içindeki tüm butonları kontrol et
            footer_btn_texts = []
            for child in hud.footer_frame.winfo_children():
                if isinstance(child, tk.Button):
                    footer_btn_texts.append(child.cget("text"))

            for text in footer_btn_texts:
                self.assertNotIn("Dinle", text)
                self.assertNotIn("🔊", text)

            # Otomatik çalma çağrılmamış olmalı
            self.assertFalse(self.dummy_tts.play_called)
        finally:
            hud.window.destroy()

    def test_result_hud_update_data_no_audio(self):
        """ResultHUD update_data çağrıldığında ses tetiklenmemelidir."""
        if not self.tk_available:
            self.skipTest("Tkinter arayüzü mevcut değil")

        data1 = {"german": "Buch", "turkish": "kitap", "is_sentence": False}
        hud = ResultHUD(self.root, data1, db=self.db, config={"sound_enabled": True}, tts_engine=self.dummy_tts)
        try:
            self.assertFalse(self.dummy_tts.play_called)

            data2 = {"german": "Tisch", "turkish": "masa", "is_sentence": False}
            hud.update_data(data2)
            self.assertFalse(self.dummy_tts.play_called)

            # _play_audio çağrısı hata vermeden no-op olmalı
            hud._play_audio()
            self.assertFalse(self.dummy_tts.play_called)
        finally:
            hud.window.destroy()

    def test_result_hud_signature_backward_compatibility(self):
        """ResultHUD hem yeni hem de eski argüman sıralamasını kabul etmelidir."""
        if not self.tk_available:
            self.skipTest("Tkinter arayüzü mevcut değil")

        data = {"german": "Hund", "turkish": "köpek", "is_sentence": False}

        # Yeni imza: (root, data, db, config)
        ResultHUD.show_result(self.root, data, self.db, {})
        hud1 = ResultHUD._instance
        self.assertIsNotNone(hud1)
        self.assertEqual(hud1.db, self.db)
        hud1.close()

        # Eski imza: (root, data, tts_engine, db, config)
        ResultHUD.show_result(self.root, data, self.dummy_tts, self.db, {})
        hud2 = ResultHUD._instance
        self.assertIsNotNone(hud2)
        self.assertEqual(hud2.db, self.db)
        hud2.close()

    def test_wordbook_flashcard_no_sound_button(self):
        """Kelime defteri Flashcard sekmesinde '🔊 Dinle' butonu bulunmamalıdır."""
        if not self.tk_available:
            self.skipTest("Tkinter arayüzü mevcut değil")

        # Örnek kelime ekle
        self.db.add_word(german="Katze", turkish="kedi", article="die")

        wb = WordbookWindow(self.root, self.db)
        try:
            # Flashcard buton çerçevesindeki çocukları tara
            fc_buttons = []
            for child in wb.tab_flashcards.winfo_children():
                if isinstance(child, tk.Frame):
                    for subchild in child.winfo_children():
                        if isinstance(subchild, tk.Button):
                            fc_buttons.append(subchild.cget("text"))

            for btn_txt in fc_buttons:
                self.assertNotIn("Dinle", btn_txt)
                self.assertNotIn("🔊", btn_txt)

            # Ses çalma metotlarının no-op olduğunu doğrula
            wb.tts = self.dummy_tts
            wb._play_flashcard_audio()
            self.assertFalse(self.dummy_tts.play_called)

            wb._on_row_double_click(None)
            self.assertFalse(self.dummy_tts.play_called)
        finally:
            wb.window.destroy()

    @patch("app.gui.settings_window.disable_startup")
    @patch("app.gui.settings_window.enable_startup")
    @patch("app.gui.settings_window.save_config")
    @patch("tkinter.messagebox.showinfo")
    def test_settings_window_no_sound_option(self, mock_showinfo, mock_save_config, mock_enable_startup, mock_disable_startup):
        """Ayarlar penceresinde ses seçeneği bulunmamalı ve kaydederken sound_enabled temizlenmelidir."""
        if not self.tk_available:
            self.skipTest("Tkinter arayüzü mevcut değil")

        cfg = {"clipboard_auto_lookup": True, "sound_enabled": True, "always_on_top": True}
        saved_cfg = {}

        def on_saved(c):
            nonlocal saved_cfg
            saved_cfg = c

        sw = SettingsWindow(self.root, cfg, on_saved)
        try:
            # var_sound niteliği olmamalı
            self.assertFalse(hasattr(sw, "var_sound"))

            # Penceredeki Checkbutton metinlerini kontrol et
            check_texts = []
            for child in sw.window.winfo_children():
                if isinstance(child, tk.Frame):
                    for sub in child.winfo_children():
                        if isinstance(sub, tk.Checkbutton):
                            check_texts.append(sub.cget("text"))

            for txt in check_texts:
                self.assertNotIn("telaffuz", txt.lower())
                self.assertNotIn("ses", txt.lower())

            # Kaydetmeyi simüle et
            sw._save()
            self.assertNotIn("sound_enabled", saved_cfg)
        finally:
            try:
                sw.window.destroy()
            except Exception:
                pass

    @patch("app.hotkey_manager.HotkeyManager.start")
    @patch("app.hotkey_manager.HotkeyManager.register")
    def test_main_overlay_without_tts(self, mock_register, mock_start):
        """MainOverlay tts_engine olmadan başlatılabilmeli ve pencereleri açabilmelidir."""
        if not self.tk_available:
            self.skipTest("Tkinter arayüzü mevcut değil")

        translator = TranslationEngine(db=self.db)
        ocr = OCREngine()
        watcher = ClipboardWatcher(on_text_detected=lambda t: None)

        overlay = MainOverlay(
            root=self.root,
            translator=translator,
            ocr_engine=ocr,
            db=self.db,
            clipboard_watcher=watcher,
            config={"always_on_top": False, "first_run_completed": True}
        )
        try:
            self.assertEqual(overlay.db, self.db)
            self.assertEqual(overlay.ocr, ocr)

            # _show_hud çağrısı tts olmadan çalışmalı
            data = {"german": "Wasser", "turkish": "su", "is_sentence": False}
            overlay._show_hud(data)
            if ResultHUD._instance:
                ResultHUD._instance.close()

            # _open_wordbook tts olmadan açılabilmeli
            overlay._open_wordbook()
        finally:
            overlay.stop()

    def test_load_config_sanitizes_sound_enabled(self):
        """Eski bir config.json dosyasında sound_enabled olsa bile load_config bunu temizlemelidir."""
        dummy_config_path = Path(self.temp_dir.name) / "config.json"
        import json
        with open(dummy_config_path, "w", encoding="utf-8") as f:
            json.dump({"clipboard_auto_lookup": True, "sound_enabled": True, "always_on_top": True}, f)

        with patch("app.config.CONFIG_FILE", dummy_config_path):
            loaded = load_config()
            self.assertNotIn("sound_enabled", loaded)

    def test_german_tts_engine_is_noop(self):
        """GermanTTSEngine hiçbir ses indirmemeli, çalmamalı ve önbellek klasörü oluşturmamalıdır."""
        engine = GermanTTSEngine()
        res = engine.download_audio("Guten Morgen")
        self.assertIsNone(res)
        # play çağrısı hatasız dönmeli
        engine.play("Guten Morgen")
        # audio_cache oluşturulmamış olmalı
        cache_dir = Path(__file__).resolve().parent.parent / "audio_cache"
        self.assertFalse(cache_dir.exists())

    def test_result_hud_without_db_safe(self):
        """ResultHUD veritabanı (db) olmadan açıldığında ve kelime kaydet butonuna basıldığında çökmemelidir."""
        if not self.tk_available:
            self.skipTest("Tkinter arayüzü mevcut değil")

        data = {"german": "Katze", "turkish": "kedi", "is_sentence": False}
        hud = ResultHUD(self.root, data, db=None, config={})
        try:
            # _toggle_save_word db None iken hata fırlatmamalı
            hud._toggle_save_word()
        finally:
            hud.window.destroy()


if __name__ == "__main__":
    unittest.main()

