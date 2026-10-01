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

    def test_config_hover_defaults(self):
        """DEFAULT_CONFIG içinde ve load_config sonucunda hover ayarları bulunmalıdır."""
        self.assertIn("hover_enabled", DEFAULT_CONFIG)
        self.assertIn("hover_delay_ms", DEFAULT_CONFIG)
        self.assertIn("hover_trigger_mode", DEFAULT_CONFIG)
        self.assertIn("hotkey_hover", DEFAULT_CONFIG)

        cfg = load_config()
        self.assertIn("hover_enabled", cfg)
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

    def test_hover_tracker_unconditional_xbutton(self):
        """enabled=False olsa bile fare yan tuşuna basıldığında tetikleme çalışmalıdır."""
        from app.hover_tracker import WM_XBUTTONDOWN, MSLLHOOKSTRUCT, POINT
        on_loading = MagicMock()
        tracker = HoverTracker(
            ocr_engine=self.ocr,
            translator=self.mock_translator,
            on_word_hover=MagicMock(),
            on_hover_leave=MagicMock(),
            on_loading=on_loading,
            trigger_mode="mouse_side",
            enabled=False,  # Pasif bekleme KAPALI
            consume_xbutton=True
        )
        tracker._running = True

        ms = MSLLHOOKSTRUCT()
        ms.pt = POINT(250, 350)

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
            config={"hover_enabled": False, "hotkey_hover": "alt+v"}
        )

        self.assertTrue(hasattr(overlay, "hover_tracker"))
        self.assertTrue(hasattr(overlay, "hover_tooltip"))
        self.assertTrue(hasattr(overlay, "btn_hover"))

        self.assertIn("KAPALI", overlay.btn_hover.cget("text"))

        # Butona tıklama / Toggle
        overlay._toggle_hover()
        self.assertTrue(overlay.hover_tracker.is_enabled())
        self.assertIn("AÇIK", overlay.btn_hover.cget("text"))

        overlay.stop()


if __name__ == "__main__":
    unittest.main()
