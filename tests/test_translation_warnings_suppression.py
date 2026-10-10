"""
Güvenlik Uyarılarını Kapatma ve Teknik Hataları Koruma Birim Testleri
(Security Warnings Suppression & Technical Errors Retention Unit Tests)
"""
import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk
import tempfile
from pathlib import Path

from app.config import DEFAULT_CONFIG
from app.database import Database
from app.gui.result_hud import ResultHUD, _is_security_warning, _should_suppress_security
from app.gui.settings_window import SettingsWindow
from app.gui.snipper import ScreenSnipper
from app.clipboard_watcher import ClipboardWatcher
from app.hover_tracker import HoverTracker


class TestSecurityWarningsSuppression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except Exception:
            cls.root = None

    @classmethod
    def tearDownClass(cls):
        if cls.root:
            try:
                cls.root.destroy()
            except Exception:
                pass

    def setUp(self):
        if self.root is None:
            self.skipTest("Tkinter ortamı mevcut değil (GUI headless).")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp_dir.name) / "test_sec_warn.db")
        ResultHUD._instance = None

    def tearDown(self):
        if ResultHUD._instance and ResultHUD._instance.is_alive():
            try:
                ResultHUD._instance.close()
            except Exception:
                pass
        ResultHUD._instance = None
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_default_config_has_security_filter_keys(self):
        """Varsayılan yapılandırma disable_security_filter=False içermelidir."""
        self.assertIn("disable_security_filter", DEFAULT_CONFIG)
        self.assertIn("hide_security_warnings", DEFAULT_CONFIG)
        self.assertFalse(DEFAULT_CONFIG["disable_security_filter"])

    def test_security_detection_helpers(self):
        """_is_security_warning ve _should_suppress_security doğru çalışmalıdır."""
        self.assertTrue(_is_security_warning({"error": "🛡️ Güvenlik Koruması:\nKopyalanan metin hassas veri"}))
        self.assertTrue(_is_security_warning({"error": "Metin hassas veri kalıbı içeriyor"}))
        self.assertFalse(_is_security_warning({"error": "Kelime sözlükte bulunamadı"}))
        self.assertFalse(_is_security_warning({"error": "İnternet bağlantısı koptu"}))

        self.assertFalse(_should_suppress_security(None))
        self.assertFalse(_should_suppress_security({}))
        self.assertFalse(_should_suppress_security({"disable_security_filter": False}))
        self.assertTrue(_should_suppress_security({"disable_security_filter": True}))
        self.assertTrue(_should_suppress_security({"hide_security_warnings": True}))

    @patch("app.gui.settings_window.save_config", return_value=True)
    @patch("app.gui.settings_window.enable_startup")
    @patch("app.gui.settings_window.disable_startup")
    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.askyesno", return_value=True)
    def test_settings_window_security_toggle_and_reset(self, mock_ask, mock_info, mock_dis, mock_en, mock_save):
        """SettingsWindow güvenlik korumasını kapat kutucuğunu açıp kapatabilmeli ve sıfırlayabilmelidir."""
        cfg = {"disable_security_filter": False, "hide_security_warnings": False}
        sw = SettingsWindow(self.root, cfg, on_settings_changed=MagicMock())
        try:
            self.root.update_idletasks()
            self.assertTrue(hasattr(sw, "var_disable_security"))
            self.assertFalse(sw.var_disable_security.get())

            # 1. İşaretle ve kaydet
            sw.var_disable_security.set(True)
            sw._save(close_window=False)
            self.assertTrue(cfg["disable_security_filter"])
            self.assertTrue(cfg["hide_security_warnings"])

            # 2. Varsayılana sıfırla
            sw._reset_to_defaults()
            self.assertFalse(sw.var_disable_security.get())
        finally:
            sw.close()

    def test_technical_errors_always_shown_in_result_hud(self):
        """Teknik hatalar (bağlantı, sözlükte bulunamadı vb.) güvenlik ayarından bağımsız her zaman gösterilmelidir."""
        tech_err = {"error": "Çeviri motoru yanıt vermedi (Zaman aşımı)"}

        # Güvenlik filtresi kapalıyken bile teknik hata gösterilmelidir
        cfg_sec_disabled = {"disable_security_filter": True}
        ResultHUD.show_result(self.root, tech_err, db=self.db, config=cfg_sec_disabled)
        self.root.update_idletasks()

        self.assertIsNotNone(ResultHUD._instance)
        self.assertTrue(ResultHUD._instance.is_alive())

    def test_security_warning_suppressed_only_when_disabled(self):
        """Güvenlik uyarısı sadece güvenlik filtresi kapatıldığında gizlenmelidir."""
        sec_err = {"error": "🛡️ Güvenlik Koruması:\nKopyalanan metin hassas veri kalıbı içeriyor."}

        # 1. Güvenlik açık (normal mod): gösterilmeli
        cfg_normal = {"disable_security_filter": False}
        ResultHUD.show_result(self.root, sec_err, db=self.db, config=cfg_normal)
        self.root.update_idletasks()
        self.assertIsNotNone(ResultHUD._instance)
        self.assertTrue(ResultHUD._instance.is_alive())
        ResultHUD._instance.close()

        # 2. Güvenlik kapatılmış: gizlenmeli / açılmamalı
        cfg_disabled = {"disable_security_filter": True}
        ResultHUD.show_result(self.root, sec_err, db=self.db, config=cfg_disabled)
        self.root.update_idletasks()
        self.assertIsNone(ResultHUD._instance)

    def test_screen_snipper_technical_toast_always_shown(self):
        """ScreenSnipper okunabilir metin bulunamadı uyarısını her zaman göstermelidir (teknik hata)."""
        snipper = ScreenSnipper(
            self.root,
            ocr_engine=MagicMock(),
            on_text_extracted=MagicMock(),
            config={"disable_security_filter": True}
        )
        with patch("tkinter.Toplevel") as mock_top:
            mock_toast = MagicMock()
            mock_top.return_value = mock_toast
            snipper._notify_no_text()
            mock_top.assert_called_once()

    def test_clipboard_watcher_respects_security_toggle(self):
        """ClipboardWatcher güvenlik kapatıldığında hassas metinleri reddetmemelidir."""
        sensitive_text = "Passwort: P@ssw0rd123!"

        # Normalde hassas metin reddedilir
        watcher_normal = ClipboardWatcher(config={"disable_security_filter": False})
        self.assertFalse(watcher_normal._is_valid_candidate(sensitive_text))

        # Güvenlik kapatıldığında kabul edilir
        watcher_sec_off = ClipboardWatcher(config={"disable_security_filter": True})
        self.assertTrue(watcher_sec_off._is_valid_candidate(sensitive_text))

    @patch("app.hover_tracker.capture_screen_rect_gdi")
    def test_hover_tracker_respects_security_toggle(self, mock_capture):
        """HoverTracker güvenlik kapatıldığında hassas kelimeyi engellememeli, çevirmelidir."""
        mock_capture.return_value = MagicMock()
        translator_mock = MagicMock()
        translator_mock.translate_and_analyze.return_value = {"german": "P@ssw0rd123!", "turkish": "şifre"}
        on_hover_mock = MagicMock()
        on_not_found_mock = MagicMock()

        target_box = {"x": 200, "y": 50, "w": 40, "h": 20, "text": "P@ssw0rd123!", "sentence": ""}
        ocr_mock = MagicMock()
        ocr_mock.recognize_words_with_boxes.return_value = [target_box]

        # 1. Güvenlik açıkken: hassas kelime on_not_found tetikler
        tracker_normal = HoverTracker(
            ocr_engine=ocr_mock,
            translator=translator_mock,
            on_word_hover=on_hover_mock,
            on_hover_leave=MagicMock(),
            on_not_found=on_not_found_mock,
            config={"disable_security_filter": False}
        )
        tracker_normal._inspect_hover_area(cursor_x=300, cursor_y=300, is_passive_hover=True)
        on_not_found_mock.assert_called()

        # 2. Güvenlik kapalıyken: çeviriciye gider, on_word_hover çağrılır
        translator_mock.reset_mock()
        on_hover_mock.reset_mock()
        on_not_found_mock.reset_mock()

        tracker_sec_off = HoverTracker(
            ocr_engine=ocr_mock,
            translator=translator_mock,
            on_word_hover=on_hover_mock,
            on_hover_leave=MagicMock(),
            on_not_found=on_not_found_mock,
            config={"disable_security_filter": True}
        )
        tracker_sec_off._inspect_hover_area(cursor_x=300, cursor_y=300, is_passive_hover=True)
        translator_mock.translate_and_analyze.assert_called_once()
        on_hover_mock.assert_called_once()
