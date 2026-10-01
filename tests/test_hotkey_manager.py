"""
Global Hotkey Manager ve Özelleştirilebilir Kısayol Test Paketi
Bu test paketi:
1. Tuş ayrıştırıcı (parse_hotkey), doğrulama (validate_hotkey_string) ve biçimlendirme (format_hotkey)
2. Tab+Space, Alt+H, Alt+C ve çoklu tuş durum takibi (multi-key state tracker)
3. Normal yazmayı engellememe (non-blocking pass-through) ve tuş yutma (swallowing)
4. Değiştirici tuş izolasyonu (Alt+Tab, Ctrl+Tab çakışma önleme)
5. Tuşa basılı tutulduğunda tek sefer tetiklenme (debounce / auto-repeat önleme)
6. Sıra bağımsızlığı (Tab sonra Space veya Space sonra Tab)
7. Eski Win32 RegisterHotKey imzasıyla geriye dönük tam uyumluluk
8. Ayarlar penceresi (SettingsWindow) kısayol düzenleme ve doğrulama akışı
9. MainOverlay arayüzünde Tab+Space ile un-minimize ve OCR tetikleme
özelliklerini eksiksiz ve derinlemesine doğrular.
"""
import unittest
from unittest.mock import patch, MagicMock
import tkinter as tk
import tempfile
import gc
from pathlib import Path

from app.config import DEFAULT_CONFIG, load_config, save_config
from app.hotkey_manager import (
    HotkeyManager,
    parse_hotkey,
    validate_hotkey_string,
    format_hotkey,
    VK_TAB,
    VK_SPACE,
    VK_MENU,
    VK_CONTROL,
    VK_SHIFT,
    VK_LWIN,
    VK_RETURN,
    VK_ESCAPE,
    VK_X,
    VK_H,
    VK_C,
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT
)
from app.gui.settings_window import SettingsWindow
from app.gui.main_overlay import MainOverlay
from app.translator import TranslationEngine
from app.ocr_engine import OCREngine
from app.clipboard_watcher import ClipboardWatcher
from app.database import Database


class TestHotkeyParserAndValidation(unittest.TestCase):
    """Tuş ayrıştırma, doğrulama ve biçimlendirme testleri."""

    def test_parse_tab_space(self):
        keys = parse_hotkey("tab+space")
        self.assertEqual(keys, frozenset({VK_TAB, VK_SPACE}))

    def test_parse_with_whitespace_and_case(self):
        keys = parse_hotkey("  Tab + Space  ")
        self.assertEqual(keys, frozenset({VK_TAB, VK_SPACE}))

    def test_parse_turkish_aliases(self):
        keys1 = parse_hotkey("tab+boşluk")
        keys2 = parse_hotkey("tab+bosluk")
        self.assertEqual(keys1, frozenset({VK_TAB, VK_SPACE}))
        self.assertEqual(keys2, frozenset({VK_TAB, VK_SPACE}))

    def test_parse_alt_x_and_alt_h(self):
        keys_alt_x = parse_hotkey("alt+x")
        keys_alt_h = parse_hotkey("Alt+H")
        self.assertEqual(keys_alt_x, frozenset({VK_MENU, VK_X}))
        self.assertEqual(keys_alt_h, frozenset({VK_MENU, VK_H}))

    def test_parse_ctrl_combinations(self):
        keys = parse_hotkey("ctrl+space")
        self.assertEqual(keys, frozenset({VK_CONTROL, VK_SPACE}))

    def test_parse_three_key_combination(self):
        keys = parse_hotkey("ctrl+shift+a")
        self.assertEqual(keys, frozenset({VK_CONTROL, VK_SHIFT, 0x41}))

    def test_parse_function_keys(self):
        keys = parse_hotkey("f2")
        self.assertEqual(keys, frozenset({0x71}))
        keys12 = parse_hotkey("f12")
        self.assertEqual(keys12, frozenset({0x7B}))

    def test_parse_empty_or_invalid_raises_error(self):
        with self.assertRaises(ValueError):
            parse_hotkey("")
        with self.assertRaises(ValueError):
            parse_hotkey("   ")
        with self.assertRaises(ValueError):
            parse_hotkey("invalid_key_xyz")
        with self.assertRaises(ValueError):
            parse_hotkey("tab+nonexistentkey")

    def test_validate_hotkey_string(self):
        valid, _ = validate_hotkey_string("tab+space")
        self.assertTrue(valid)

        valid, _ = validate_hotkey_string("alt+h")
        self.assertTrue(valid)

        valid, err = validate_hotkey_string("foobar+xyz")
        self.assertFalse(valid)
        self.assertIn("Tanınmayan tuş", err)

        valid, err = validate_hotkey_string("")
        self.assertFalse(valid)

    def test_format_hotkey(self):
        self.assertEqual(format_hotkey("tab+space"), "Tab+Space")
        self.assertEqual(format_hotkey("alt+h"), "Alt+H")
        self.assertEqual(format_hotkey("alt+c"), "Alt+C")
        self.assertEqual(format_hotkey("ctrl+shift+a"), "Ctrl+Shift+A")


class TestHotkeyManagerLogic(unittest.TestCase):
    """HotkeyManager durum takibi ve simülasyon testleri."""

    def setUp(self):
        # Programatik simülasyonda fiziksel hardware GetAsyncKeyState kontrolünü devre dışı bırak
        self.mgr = HotkeyManager(consume_hotkeys=True, verify_physical=False)

    def tearDown(self):
        self.mgr.stop()

    def test_tab_space_trigger_sequence(self):
        """Tab basılıyken Space basıldığında OCR callback'i tetiklenmeli."""
        triggered_count = 0

        def on_ocr():
            nonlocal triggered_count
            triggered_count += 1

        self.mgr.register("ocr", "tab+space", on_ocr)

        # 1. Tab basıldı -> tetiklenmemeli, yutulmamalı
        swallow = self.mgr._handle_key_event(VK_TAB, is_down=True)
        self.assertFalse(swallow)
        self.assertEqual(triggered_count, 0)
        self.assertIn(VK_TAB, self.mgr._pressed_keys)

        # 2. Space basıldı -> kombinasyon tamamlandı! Tetiklenmeli ve Space yutulmalı
        swallow = self.mgr._handle_key_event(VK_SPACE, is_down=True)
        self.assertTrue(swallow)
        import time
        time.sleep(0.05)  # Daemon thread'in çalışması için minik bekleme
        self.assertEqual(triggered_count, 1)

        # 3. Space basılı tutuluyor (auto-repeat) -> tekrar tetiklenmemeli
        swallow = self.mgr._handle_key_event(VK_SPACE, is_down=True)
        time.sleep(0.02)
        self.assertEqual(triggered_count, 1)

        # 4. Space bırakıldı -> yutulmalı, tetik durumu sıfırlanmalı
        swallow = self.mgr._handle_key_event(VK_SPACE, is_down=False)
        self.assertTrue(swallow)
        self.assertNotIn(VK_SPACE, self.mgr._pressed_keys)

        # 5. Space tekrar basıldı (Tab halen basılı) -> tekrar tetiklenmeli!
        swallow = self.mgr._handle_key_event(VK_SPACE, is_down=True)
        self.assertTrue(swallow)
        time.sleep(0.05)
        self.assertEqual(triggered_count, 2)

        # 6. Her iki tuş bırakıldı
        self.mgr._handle_key_event(VK_SPACE, is_down=False)
        self.mgr._handle_key_event(VK_TAB, is_down=False)
        self.assertEqual(len(self.mgr._pressed_keys), 0)

    def test_space_then_tab_order_independence(self):
        """Space önce basılıp ardından Tab basılsa dahi kombinasyon çalışmalı."""
        triggered = False

        def on_ocr():
            nonlocal triggered
            triggered = True

        self.mgr.register("ocr", "tab+space", on_ocr)

        # Space önce basıldı
        self.mgr._handle_key_event(VK_SPACE, is_down=True)
        self.assertFalse(triggered)

        # Tab basıldı
        swallow = self.mgr._handle_key_event(VK_TAB, is_down=True)
        self.assertTrue(swallow)
        import time
        time.sleep(0.05)
        self.assertTrue(triggered)

        # Temizle
        self.mgr._handle_key_event(VK_TAB, is_down=False)
        self.mgr._handle_key_event(VK_SPACE, is_down=False)

    def test_normal_typing_not_swallowed(self):
        """Kısayol olmayan tuşlar kesinlikle yutulmamalı (pass-through)."""
        self.mgr.register("ocr", "tab+space", lambda: None)

        # Sıradan harfler
        for key in [ord('A'), ord('B'), ord('C'), 0x30, VK_RETURN]:
            swallow_down = self.mgr._handle_key_event(key, is_down=True)
            self.assertFalse(swallow_down)
            swallow_up = self.mgr._handle_key_event(key, is_down=False)
            self.assertFalse(swallow_up)

        # Yalnızca Tab basıp bırakma
        self.assertFalse(self.mgr._handle_key_event(VK_TAB, is_down=True))
        self.assertFalse(self.mgr._handle_key_event(VK_TAB, is_down=False))

        # Yalnızca Space basıp bırakma
        self.assertFalse(self.mgr._handle_key_event(VK_SPACE, is_down=True))
        self.assertFalse(self.mgr._handle_key_event(VK_SPACE, is_down=False))

    def test_modifier_isolation_alt_tab_safety(self):
        """Alt basılıyken Tab+Space kısayolu kazara tetiklenmemelidir (Alt+Tab çakışma koruması)."""
        triggered = False

        def on_ocr():
            nonlocal triggered
            triggered = True

        self.mgr.register("ocr", "tab+space", on_ocr)

        # Kullanıcı Alt+Tab yapıyor
        self.mgr._handle_key_event(VK_MENU, is_down=True)
        self.mgr._handle_key_event(VK_TAB, is_down=True)
        self.mgr._handle_key_event(VK_SPACE, is_down=True)

        import time
        time.sleep(0.05)
        # Alt tuşu basılı olduğu için Tab+Space tetiklenmemeli!
        self.assertFalse(triggered)

        self.mgr._handle_key_event(VK_SPACE, is_down=False)
        self.mgr._handle_key_event(VK_TAB, is_down=False)
        self.mgr._handle_key_event(VK_MENU, is_down=False)

    def test_multiple_registered_hotkeys(self):
        """Farklı kısayolların (Tab+Space, Alt+H, Alt+C) bağımsız çalışması."""
        calls = {"ocr": 0, "overlay": 0, "clip": 0}

        self.mgr.register("ocr", "tab+space", lambda: calls.__setitem__("ocr", calls["ocr"] + 1))
        self.mgr.register("overlay", "alt+h", lambda: calls.__setitem__("overlay", calls["overlay"] + 1))
        self.mgr.register("clipboard", "alt+c", lambda: calls.__setitem__("clip", calls["clip"] + 1))

        import time

        # Alt+H tetikle
        self.mgr._handle_key_event(VK_MENU, is_down=True)
        self.mgr._handle_key_event(VK_H, is_down=True)
        time.sleep(0.05)
        self.assertEqual(calls["overlay"], 1)
        self.assertEqual(calls["ocr"], 0)
        self.assertEqual(calls["clip"], 0)
        self.mgr._handle_key_event(VK_H, is_down=False)
        self.mgr._handle_key_event(VK_MENU, is_down=False)

        # Tab+Space tetikle
        self.mgr._handle_key_event(VK_TAB, is_down=True)
        self.mgr._handle_key_event(VK_SPACE, is_down=True)
        time.sleep(0.05)
        self.assertEqual(calls["ocr"], 1)
        self.assertEqual(calls["overlay"], 1)
        self.assertEqual(calls["clip"], 0)
        self.mgr._handle_key_event(VK_SPACE, is_down=False)
        self.mgr._handle_key_event(VK_TAB, is_down=False)

    def test_legacy_register_backward_compatibility(self):
        """Eski register(id, mod, vk, cb) ve register(id, 0, 0, cb) çağrıları hatasız çalışmalı."""
        called_1 = False
        called_2 = False

        self.mgr.register(1, 0, 0, lambda: None)
        self.mgr.register(2, MOD_ALT, VK_H, lambda: None)

        self.assertIn(1, self.mgr._bindings)
        self.assertIn(2, self.mgr._bindings)
        self.assertEqual(self.mgr._bindings[2].required_keys, frozenset({VK_MENU, VK_H}))

    def test_unregister_and_clear(self):
        self.mgr.register("test", "tab+space", lambda: None)
        self.assertIn("test", self.mgr._bindings)

        self.mgr.unregister("test")
        self.assertNotIn("test", self.mgr._bindings)

        self.mgr.register("a", "alt+h", lambda: None)
        self.mgr.register("b", "alt+c", lambda: None)
        self.mgr.clear()
        self.assertEqual(len(self.mgr._bindings), 0)


class TestConfigAndSettingsIntegration(unittest.TestCase):
    """Yapılandırma (config.py) ve Ayarlar Penceresi (settings_window.py) testleri."""

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

    def test_default_config_hotkeys(self):
        """DEFAULT_CONFIG içinde hotkey_ocr, hotkey_overlay ve hotkey_clipboard bulunmalıdır."""
        self.assertEqual(DEFAULT_CONFIG.get("hotkey_ocr"), "tab+space")
        self.assertEqual(DEFAULT_CONFIG.get("hotkey_overlay"), "alt+h")
        self.assertEqual(DEFAULT_CONFIG.get("hotkey_clipboard"), "alt+c")

    def test_load_config_supplies_default_hotkeys(self):
        """Eski bir config dosyasında kısayollar olmasa bile load_config varsayılanları eklemelidir."""
        temp_dir = tempfile.TemporaryDirectory()
        try:
            cfg_file = Path(temp_dir.name) / "config.json"
            import json
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump({"clipboard_auto_lookup": True}, f)

            with patch("app.config.CONFIG_FILE", cfg_file):
                loaded = load_config()
                self.assertEqual(loaded.get("hotkey_ocr"), "tab+space")
                self.assertEqual(loaded.get("hotkey_overlay"), "alt+h")
                self.assertEqual(loaded.get("hotkey_clipboard"), "alt+c")
        finally:
            temp_dir.cleanup()

    @patch("app.gui.settings_window.disable_startup")
    @patch("app.gui.settings_window.enable_startup")
    @patch("app.gui.settings_window.save_config")
    @patch("tkinter.messagebox.showinfo")
    def test_settings_window_hotkey_editing(self, mock_showinfo, mock_save_config, mock_enable_startup, mock_disable_startup):
        """Ayarlar penceresinde kısayollar düzenlenebilmeli ve kaydedilebilmelidir."""
        if not self.tk_available:
            self.skipTest("Tkinter mevcut değil")

        cfg = {
            "hotkey_ocr": "tab+space",
            "hotkey_overlay": "alt+h",
            "hotkey_clipboard": "alt+c",
            "clipboard_auto_lookup": True,
            "always_on_top": True,
        }
        saved_cfg = {}

        def on_saved(c):
            nonlocal saved_cfg
            saved_cfg = c

        sw = SettingsWindow(self.root, cfg, on_saved)
        try:
            # Giriş kutuları başlangıç değerlerini içermeli
            self.assertEqual(sw.entry_hotkey_ocr.get(), "tab+space")
            self.assertEqual(sw.entry_hotkey_overlay.get(), "alt+h")
            self.assertEqual(sw.entry_hotkey_clip.get(), "alt+c")

            # Preset butonunu test et
            sw._set_ocr_preset("ctrl+space")
            self.assertEqual(sw.entry_hotkey_ocr.get(), "ctrl+space")

            # Değiştirip kaydet
            sw.entry_hotkey_ocr.delete(0, tk.END)
            sw.entry_hotkey_ocr.insert(0, "alt+x")

            sw._save()

            self.assertEqual(saved_cfg.get("hotkey_ocr"), "alt+x")
            self.assertEqual(saved_cfg.get("hotkey_overlay"), "alt+h")
        finally:
            try:
                sw.window.destroy()
            except Exception:
                pass

    @patch("tkinter.messagebox.showerror")
    def test_settings_window_invalid_hotkey_validation(self, mock_showerror):
        """Ayarlar penceresinde geçersiz kısayol girildiğinde uyarı vermeli ve kaydetmemelidir."""
        if not self.tk_available:
            self.skipTest("Tkinter mevcut değil")

        cfg = {"hotkey_ocr": "tab+space", "hotkey_overlay": "alt+h", "hotkey_clipboard": "alt+c"}
        saved_called = False

        sw = SettingsWindow(self.root, cfg, lambda c: None)
        try:
            sw.entry_hotkey_ocr.delete(0, tk.END)
            sw.entry_hotkey_ocr.insert(0, "invalid+key123")

            sw._save()

            mock_showerror.assert_called_once()
            self.assertIn("geçersiz kısayol tuşu", mock_showerror.call_args[0][1].lower())
        finally:
            try:
                sw.window.destroy()
            except Exception:
                pass


class TestMainOverlayHotkeyIntegration(unittest.TestCase):
    """MainOverlay içinde kısayol bağlama ve OCR tetikleme testleri."""

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
        self.db = Database(Path(self.temp_dir.name) / "test_overlay.db")

    def tearDown(self):
        self.db = None
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    @patch("app.hotkey_manager.HotkeyManager.start")
    def test_main_overlay_initializes_hotkeys_and_snip_label(self, mock_start):
        """MainOverlay yapılandırmadaki kısayolları kaydetmeli ve butonda göstermelidir."""
        if not self.tk_available:
            self.skipTest("Tkinter mevcut değil")

        cfg = {
            "hotkey_ocr": "tab+space",
            "hotkey_overlay": "alt+h",
            "hotkey_clipboard": "alt+c",
        }
        overlay = MainOverlay(
            root=self.root,
            translator=TranslationEngine(db=self.db),
            ocr_engine=OCREngine(),
            db=self.db,
            clipboard_watcher=ClipboardWatcher(on_text_detected=lambda t: None),
            config=cfg
        )
        try:
            # Buton üzerinde '✂ Kırp (Tab+Space)' yazmalı
            btn_text = overlay.btn_snip.cget("text")
            self.assertIn("Tab+Space", btn_text)

            # HotkeyManager'a 'ocr', 'overlay', 'clipboard' kayıtları yapılmış olmalı
            self.assertIn("ocr", overlay.hotkey_mgr._bindings)
            self.assertIn("overlay", overlay.hotkey_mgr._bindings)
            self.assertIn("clipboard", overlay.hotkey_mgr._bindings)
        finally:
            overlay.stop()

    @patch("app.gui.snipper.ScreenSnipper.start_selection")
    @patch("app.hotkey_manager.HotkeyManager.start")
    def test_trigger_ocr_hotkey_unminimizes_and_opens_snipper(self, mock_start, mock_start_selection):
        """_trigger_ocr_hotkey çağrıldığında pencere gizliyse açılmalı ve snipper başlatılmalıdır."""
        if not self.tk_available:
            self.skipTest("Tkinter mevcut değil")

        overlay = MainOverlay(
            root=self.root,
            translator=TranslationEngine(db=self.db),
            ocr_engine=OCREngine(),
            db=self.db,
            clipboard_watcher=ClipboardWatcher(on_text_detected=lambda t: None),
            config={"hotkey_ocr": "tab+space"}
        )
        try:
            # Önce çubuğu gizle
            overlay._is_bar_visible = False
            overlay.root.withdraw()

            # Kısayol tetiklendiğinde:
            overlay._trigger_ocr_hotkey()

            # Çubuk tekrar görünür olmalı
            self.assertTrue(overlay._is_bar_visible)
            # Snipper başlatılmış olmalı
            mock_start_selection.assert_called_once()
        finally:
            overlay.stop()


if __name__ == "__main__":
    unittest.main()
