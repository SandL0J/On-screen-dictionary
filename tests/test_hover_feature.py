"""
Canlı Fare Üzerine Gelme (Hover OCR & Tooltip) Özelliği Testleri
"""
import unittest
import tkinter as tk
from unittest.mock import MagicMock, patch
from PIL import Image, ImageDraw

from app.ocr_engine import OCREngine
from app.hover_tracker import HoverTracker
from app.gui.hover_tooltip import HoverTooltip
from app.config import load_config, DEFAULT_CONFIG


class TestHoverFeature(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.ocr = OCREngine()
        self.mock_translator = MagicMock()
        self.mock_translator.translate_and_analyze.return_value = {
            "original": "Haus",
            "translation": "Ev",
            "analysis": {"article": "das", "plural": "Häuser"},
        }
        self.mock_db = MagicMock()
        self.mock_db.is_word_saved.return_value = False

    def tearDown(self):
        if getattr(self, "root", None):
            for child in list(self.root.winfo_children()):
                try:
                    child.destroy()
                except Exception:
                    pass
            try:
                self.root.update()
            except Exception:
                pass

    def test_config_hover_defaults(self):
        """DEFAULT_CONFIG içinde ve load_config sonucunda hover ayarları bulunmalıdır."""
        self.assertIn("hover_enabled", DEFAULT_CONFIG)
        self.assertIn("hover_delay_ms", DEFAULT_CONFIG)
        self.assertIn("hover_trigger_mode", DEFAULT_CONFIG)
        self.assertIn("hover_auto_hide_seconds", DEFAULT_CONFIG)
        self.assertIn("hotkey_hover", DEFAULT_CONFIG)

        cfg = load_config()
        self.assertIn("hover_enabled", cfg)
        self.assertIn("hover_auto_hide_seconds", cfg)
        self.assertIn("hotkey_hover", cfg)

    def test_ocr_recognize_words_with_boxes(self):
        """recognize_words_with_boxes metodu kelimeleri ve geçerli kutuları dönmelidir."""
        img = Image.new("RGB", (250, 60), color="white")
        d = ImageDraw.Draw(img)
        d.text((15, 15), "das Buch", fill="black")

        boxes = self.ocr.recognize_words_with_boxes(img)
        self.assertIsInstance(boxes, list)
        self.assertGreaterEqual(len(boxes), 1)

        words = [b["text"].lower() for b in boxes]
        self.assertTrue(any("buch" in w or "das" in w for w in words))
        for b in boxes:
            self.assertIn("x", b)
            self.assertIn("y", b)
            self.assertIn("w", b)
            self.assertIn("h", b)
            self.assertGreater(b["w"], 0)
            self.assertGreater(b["h"], 0)

    def test_hover_tracker_init_and_toggle(self):
        """HoverTracker açılıp kapatılabilmeli ve ayarları güncellenebilmelidir."""
        on_hover = MagicMock()
        on_leave = MagicMock()

        tracker = HoverTracker(
            ocr_engine=self.ocr,
            translator=self.mock_translator,
            on_word_hover=on_hover,
            on_hover_leave=on_leave,
            hover_delay_ms=300,
            trigger_mode="always",
            enabled=False
        )

        self.assertFalse(tracker.is_enabled())
        tracker.set_enabled(True)
        self.assertTrue(tracker.is_enabled())

        tracker.update_settings(hover_delay_ms=450, trigger_mode="ctrl")
        self.assertEqual(tracker.hover_delay_sec, 0.45)
        self.assertEqual(tracker.trigger_mode, "ctrl")

        tracker.stop()
        self.assertFalse(tracker.is_enabled())

    def test_hover_tracker_trigger_conditions(self):
        """Tetikleme kuralları ('always', 'ctrl', 'alt', 'shift') doğru değerlendirilmelidir."""
        tracker = HoverTracker(
            ocr_engine=self.ocr,
            translator=self.mock_translator,
            on_word_hover=MagicMock(),
            on_hover_leave=MagicMock(),
            trigger_mode="always"
        )
        self.assertTrue(tracker._is_trigger_condition_met())

        tracker.trigger_mode = "mouse_side"
        self.assertFalse(tracker._is_trigger_condition_met())

        tracker.trigger_mode = "ctrl"
        with patch("app.hover_tracker.is_key_down", return_value=True):
            self.assertTrue(tracker._is_trigger_condition_met())
        with patch("app.hover_tracker.is_key_down", return_value=False):
            self.assertFalse(tracker._is_trigger_condition_met())

    def test_hover_tracker_xbutton_hook_callback(self):
        """WM_XBUTTONDOWN geldiğinde inspect_hover_area çağrılmalı ve 1 dönerek tuş tüketilmelidir."""
        from app.hover_tracker import WM_XBUTTONDOWN, MSLLHOOKSTRUCT, POINT
        tracker = HoverTracker(
            ocr_engine=self.ocr,
            translator=self.mock_translator,
            on_word_hover=MagicMock(),
            on_hover_leave=MagicMock(),
            trigger_mode="mouse_side",
            enabled=True,
            consume_xbutton=True
        )
        tracker._running = True

        ms = MSLLHOOKSTRUCT()
        ms.pt = POINT(150, 200)

        with patch.object(tracker, "_inspect_hover_area") as mock_inspect:
            import ctypes
            res = tracker._mouse_hook_callback(0, WM_XBUTTONDOWN, ctypes.addressof(ms))
            self.assertEqual(res, 1)  # Tüketildi (consumed)

        tracker.stop()

    def test_hover_tracker_disabled_releases_xbutton(self):
        """Hover kapalıyken (enabled=False) fare yan tuşları taranmamalı, tüketilmemeli ve sisteme serbest bırakılmalıdır."""
        from app.hover_tracker import WM_XBUTTONDOWN, MSLLHOOKSTRUCT, POINT
        on_loading = MagicMock()
        tracker = HoverTracker(
            ocr_engine=self.ocr,
            translator=self.mock_translator,
            on_word_hover=MagicMock(),
            on_hover_leave=MagicMock(),
            on_loading=on_loading,
            trigger_mode="mouse_side",
            enabled=False,  # Hover KAPALI
            consume_xbutton=True
        )
        tracker._running = True

        ms = MSLLHOOKSTRUCT()
        ms.pt = POINT(250, 350)

        with patch.object(tracker, "_inspect_hover_area") as mock_inspect:
            import ctypes
            res = tracker._mouse_hook_callback(0, WM_XBUTTONDOWN, ctypes.addressof(ms))
            # 1 dönmemeli (tüketilmemeli / serbest bırakılmalı), CallNextHookEx sonucu dönmeli (0 veya hook zinciri)
            self.assertNotEqual(res, 1)
            on_loading.assert_not_called()
            mock_inspect.assert_not_called()

        # Hover açıldığında ise tuş yakalanmalı ve 1 dönmelidir
        tracker.set_enabled(True)
        with patch.object(tracker, "_inspect_hover_area") as mock_inspect:
            import ctypes
            res = tracker._mouse_hook_callback(0, WM_XBUTTONDOWN, ctypes.addressof(ms))
            self.assertEqual(res, 1)
            on_loading.assert_called_once_with(250, 350)

        tracker.stop()

    def test_hover_tooltip_loading_and_message(self):
        """show_loading ve show_message anında görünür mesaj vermelidir."""
        tooltip = HoverTooltip(self.root, db=self.mock_db)

        tooltip.show_loading(cursor_x=200, cursor_y=200, message="🔍 Okunuyor...")
        self.root.update()
        self.assertEqual(tooltip.lbl_german.cget("text"), "🔍 Okunuyor...")

        tooltip.show_message(cursor_x=200, cursor_y=200, message="⚠️ Kelime bulunamadı", auto_hide_ms=0)
        self.root.update()
        self.assertEqual(tooltip.lbl_german.cget("text"), "⚠️ Kelime bulunamadı")

        tooltip.hide()
        self.root.update()

    def test_hover_tooltip_lifecycle(self):
        """HoverTooltip penceresi veriyi göstermeli, yıldızlamayı desteklemeli ve gizlenebilmelidir."""
        tooltip = HoverTooltip(self.root, db=self.mock_db)

        sample_data = {
            "original": "Haus",
            "translation": "Ev",
            "analysis": {"article": "das", "plural": "Häuser"},
        }

        # Göster
        tooltip.show(sample_data, cursor_x=400, cursor_y=300)
        self.root.update()

        self.assertEqual(tooltip.lbl_german.cget("text"), "Haus")
        self.assertEqual(tooltip.lbl_article.cget("text"), "das")
        self.assertEqual(tooltip.lbl_turkish.cget("text"), "Ev")

        # Yıldızlama / Kaydetme testi
        tooltip._toggle_save()
        self.mock_db.add_word.assert_called_once()

        # Gizle
        tooltip.hide()
        self.root.update()
        self.assertIsNone(tooltip._current_data)

    def test_hover_tooltip_close_button(self):
        """HoverTooltip sağ üst köşesinde kırmızı kapatma çarpısı bulunmalı ve tıklandığında kutu kapanmalıdır."""
        tooltip = HoverTooltip(self.root, db=self.mock_db)
        try:
            self.assertTrue(hasattr(tooltip, "btn_close"))
            self.assertEqual(tooltip.btn_close.cget("text"), "✕")
            self.assertEqual(tooltip.btn_close.cget("fg"), "#ef4444")

            sample_data = {
                "original": "Buch",
                "translation": "Kitap",
                "analysis": {"article": "das", "plural": "Bücher"},
            }
            tooltip.show(sample_data, cursor_x=300, cursor_y=250)
            self.root.update()
            self.assertIsNotNone(tooltip._current_data)

            # Kapatma butonuna tıklandığında gizlenmeli
            tooltip.hide()
            self.root.update()
            self.assertIsNone(tooltip._current_data)
        finally:
            tooltip.window.destroy()

    def test_hover_tooltip_auto_hide_configurable(self):
        """HoverTooltip otomatik kapanma süresi yapılandırılabilmeli ve show çağrıldığında timer kurulmalıdır."""
        tooltip = HoverTooltip(self.root, db=self.mock_db, auto_hide_seconds=2)
        try:
            self.assertEqual(tooltip.auto_hide_seconds, 2)
            sample_data = {
                "original": "Sonne",
                "translation": "Güneş",
                "analysis": {"article": "die", "plural": "Sonnen"},
            }
            tooltip.show(sample_data, cursor_x=200, cursor_y=150)
            self.root.update_idletasks()
            self.assertIsNotNone(tooltip._auto_hide_id, "auto_hide_seconds > 0 ise timer başlatılmalıdır")

            # 0 sn olarak ayarlanırsa (manuel kapatma modu) timer kurulmamalıdır
            tooltip.set_auto_hide_seconds(0)
            self.assertEqual(tooltip.auto_hide_seconds, 0)
            tooltip.show(sample_data, cursor_x=200, cursor_y=150)
            self.root.update_idletasks()
            self.assertIsNone(tooltip._auto_hide_id, "auto_hide_seconds == 0 ise timer kurulmamalıdır")
        finally:
            tooltip.window.destroy()

    @patch("app.gui.settings_window.save_config")
    @patch("tkinter.messagebox.showinfo")
    def test_settings_window_hover_duration_editing(self, mock_showinfo, mock_save_config):
        """Ayarlar penceresinde hover kutucuk kapanma süresi düzenlenebilmeli ve kaydedilebilmelidir."""
        from app.gui.settings_window import SettingsWindow
        cfg = {
            "hover_auto_hide_seconds": 5,
            "hover_enabled": True,
            "hover_trigger_mode": "mouse_side",
            "hover_delay_ms": 300,
            "hotkey_ocr": "tab+space",
            "hotkey_hover": "alt+v",
            "hotkey_overlay": "alt+h",
            "hotkey_clipboard": "alt+c",
        }
        saved_cfg = {}
        def on_saved(c):
            nonlocal saved_cfg
            saved_cfg = c

        sw = SettingsWindow(self.root, cfg, on_saved)
        try:
            self.assertTrue(hasattr(sw, "var_hover_duration"))
            self.assertEqual(sw.var_hover_duration.get(), 5)

            # Değiştirip kaydet: 8 saniye yapalım
            sw.var_hover_duration.set(8)
            sw._save()

            self.assertEqual(saved_cfg.get("hover_auto_hide_seconds"), 8)
        finally:
            if sw.window.winfo_exists():
                sw.window.destroy()

    @patch("app.config.save_config")
    def test_main_overlay_hover_integration(self, mock_save_config):
        """MainOverlay üzerinde hover_tracker, hover_tooltip ve btn_hover entegre olmalıdır."""
        from app.gui.main_overlay import MainOverlay

        mock_clip = MagicMock()
        mock_clip.is_enabled.return_value = True

        overlay = MainOverlay(
            root=self.root,
            translator=self.mock_translator,
            ocr_engine=self.ocr,
            db=self.mock_db,
            clipboard_watcher=mock_clip,
            config={"hover_enabled": False, "hotkey_hover": "alt+v", "first_run_completed": True}
        )

        self.assertTrue(hasattr(overlay, "hover_tracker"))
        self.assertTrue(hasattr(overlay, "hover_tooltip"))
        self.assertTrue(hasattr(overlay, "btn_hover"))

        self.assertIn("KAPALI", overlay.btn_hover.cget("text"))

        # Butona tıklama / Toggle Aç
        overlay._toggle_hover()
        self.assertTrue(overlay.hover_tracker.is_enabled())
        self.assertIn("AÇIK", overlay.btn_hover.cget("text"))

        # Tooltip gösterildiğinde
        overlay.hover_tooltip.show({"original": "Auto", "translation": "Araba"}, 100, 100)
        self.root.update_idletasks()
        self.assertTrue(overlay.hover_tooltip.is_visible())

        # Tekrar tıklayıp kapattığımızda tooltip derhal gizlenmeli ve takipçi devre dışı kalmalıdır
        overlay._toggle_hover()
        self.assertFalse(overlay.hover_tracker.is_enabled())
        self.assertIn("KAPALI", overlay.btn_hover.cget("text"))
        self.root.update_idletasks()
        self.assertFalse(overlay.hover_tooltip.is_visible())

        overlay.stop()

    def test_mouse_move_does_not_hide_tooltip_in_mouse_side_mode(self):
        """mouse_side modunda WM_MOUSEMOVE geldiğinde on_hover_leave çağrılmamalıdır."""
        from app.hover_tracker import WM_MOUSEMOVE, MSLLHOOKSTRUCT, POINT
        import ctypes

        on_leave = MagicMock()
        tracker = HoverTracker(
            ocr_engine=self.ocr,
            translator=self.mock_translator,
            on_word_hover=MagicMock(),
            on_hover_leave=on_leave,
            trigger_mode="mouse_side",
            enabled=True
        )
        tracker._running = True
        # Simüle edilen bir kelime bölgesi olsun
        tracker._active_word_screen_rect = (100, 100, 150, 120)

        ms = MSLLHOOKSTRUCT()
        ms.pt = POINT(500, 500)  # Kelimenin çok uzağında fare hareketi

        tracker._mouse_hook_callback(0, WM_MOUSEMOVE, ctypes.addressof(ms))
        on_leave.assert_not_called()
        tracker.stop()

    def test_button_trigger_does_not_set_active_word_screen_rect(self):
        """Yan tuş / buton tetiklemesinde (is_passive_hover=False) _active_word_screen_rect None kalmalıdır."""
        tracker = HoverTracker(
            ocr_engine=self.ocr,
            translator=self.mock_translator,
            on_word_hover=MagicMock(),
            on_hover_leave=MagicMock(),
            trigger_mode="mouse_side",
            enabled=True
        )
        # Sahte kutu eşleştirmesi ile _inspect_hover_area testi (kırpma merkezine denk gelen koordinat)
        with patch.object(tracker.ocr_engine, "recognize_words_with_boxes", return_value=[{"x": 210, "y": 55, "w": 40, "h": 20, "text": "Hund"}]), \
             patch("app.hover_tracker.capture_screen_rect_gdi", return_value=Image.new("RGB", (440, 120))):
            tracker._inspect_hover_area(cursor_x=200, cursor_y=200, is_passive_hover=False)
            self.assertEqual(tracker._active_word, "Hund")
            self.assertIsNone(tracker._active_word_screen_rect, "Buton tetiklemesinde fare takip sınırlayıcısı None olmalıdır")

    def test_hover_tooltip_has_active_auto_hide(self):
        """has_active_auto_hide ve is_visible metodları doğru durumu dönmelidir."""
        tooltip = HoverTooltip(self.root, db=self.mock_db, auto_hide_seconds=3)
        try:
            self.assertFalse(tooltip.has_active_auto_hide())
            sample_data = {"original": "Baum", "translation": "Ağaç"}
            tooltip.show(sample_data, cursor_x=100, cursor_y=100)
            self.root.update_idletasks()
            self.assertTrue(tooltip.has_active_auto_hide())

            tooltip._cancel_auto_hide()
            self.assertFalse(tooltip.has_active_auto_hide())
        finally:
            tooltip.window.destroy()


    @patch("app.gui.settings_window.save_config")
    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.askyesno")
    def test_settings_window_reset_to_defaults(self, mock_askyesno, mock_showinfo, mock_save_config):
        """Ayarları varsayılanlara sıfırlama butonu onay alarak tüm alanları fabrika değerlerine döndürmeli ve uygulamalıdır."""
        from app.gui.settings_window import SettingsWindow
        from app.config import DEFAULT_CONFIG

        mock_askyesno.return_value = True

        custom_cfg = {
            "clipboard_auto_lookup": False,
            "always_on_top": False,
            "auto_hide_seconds": 30,
            "hover_auto_hide_seconds": 15,
            "hover_enabled": False,
            "hover_trigger_mode": "always",
            "hover_delay_ms": 800,
            "hotkey_ocr": "alt+z",
            "hotkey_hover": "ctrl+1",
            "hotkey_overlay": "ctrl+2",
            "hotkey_clipboard": "ctrl+3",
            "gemini_api_key": "my_secret_key_123",
        }
        saved_cfg = {}
        def on_saved(c):
            nonlocal saved_cfg
            saved_cfg = c

        sw = SettingsWindow(self.root, custom_cfg, on_saved)
        try:
            self.assertEqual(sw.entry_hotkey_ocr.get(), "alt+z")
            self.assertEqual(sw.var_duration.get(), 30)

            sw._reset_to_defaults()

            mock_askyesno.assert_called_once()
            self.assertEqual(sw.entry_hotkey_ocr.get(), DEFAULT_CONFIG["hotkey_ocr"])
            self.assertEqual(sw.entry_hotkey_hover.get(), DEFAULT_CONFIG["hotkey_hover"])
            self.assertEqual(sw.var_duration.get(), DEFAULT_CONFIG["auto_hide_seconds"])
            self.assertEqual(sw.var_hover_duration.get(), DEFAULT_CONFIG["hover_auto_hide_seconds"])
            self.assertEqual(sw.entry_api.get(), "")
            self.assertEqual(saved_cfg.get("hotkey_ocr"), DEFAULT_CONFIG["hotkey_ocr"])
            self.assertIn("sıfırlandı", sw.lbl_save_status.cget("text").lower())
        finally:
            if sw.window.winfo_exists():
                sw.window.destroy()

    @patch("app.gui.settings_window.save_config")
    @patch("tkinter.messagebox.askyesno")
    def test_settings_window_reset_cancel(self, mock_askyesno, mock_save_config):
        """Kullanıcı sıfırlama onay kutusunda 'Hayır'ı seçerse ayarlar değişmemelidir."""
        from app.gui.settings_window import SettingsWindow

        mock_askyesno.return_value = False
        custom_cfg = {
            "hotkey_ocr": "alt+z",
            "hotkey_hover": "alt+v",
            "hotkey_overlay": "alt+h",
            "hotkey_clipboard": "alt+c",
            "hover_auto_hide_seconds": 15,
        }
        saved_calls = []
        sw = SettingsWindow(self.root, custom_cfg, lambda c: saved_calls.append(c))
        try:
            sw._reset_to_defaults()
            self.assertEqual(sw.entry_hotkey_ocr.get(), "alt+z")
            self.assertEqual(len(saved_calls), 0)
        finally:
            if sw.window.winfo_exists():
                sw.window.destroy()

    @patch("app.gui.settings_window.save_config")
    @patch("tkinter.messagebox.showinfo")
    def test_settings_window_save_feedback(self, mock_showinfo, mock_save_config):
        """Ayarları kaydet butonuna basıldığında durum etiketi ve buton metni kullanıcıya net geri bildirim vermelidir."""
        from app.gui.settings_window import SettingsWindow

        cfg = {
            "hotkey_ocr": "tab+space",
            "hotkey_hover": "alt+v",
            "hotkey_overlay": "alt+h",
            "hotkey_clipboard": "alt+c",
            "hover_auto_hide_seconds": 5,
            "auto_hide_seconds": 12,
        }
        saved_cfg = {}
        sw = SettingsWindow(self.root, cfg, lambda c: saved_cfg.update(c))
        try:
            sw.var_duration.set(22)
            sw._save()

            self.assertEqual(saved_cfg.get("auto_hide_seconds"), 22)
            status_text = sw.lbl_save_status.cget("text")
            self.assertIn("kaydedildi", status_text.lower())
            self.assertIn("uygulandı", status_text.lower())
            self.assertEqual(sw.btn_save.cget("text"), "✅ Kaydedildi ve Uygulandı!")
        finally:
            if sw.window.winfo_exists():
                sw.window.destroy()


if __name__ == "__main__":
    unittest.main()
