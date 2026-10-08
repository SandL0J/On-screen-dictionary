"""
Bağlam İçi Cümle Madenciliği (Sentence Mining) ve Tek Tıkla Cümle Kaydı Testleri
"""
import unittest
import tkinter as tk
import json
from unittest.mock import MagicMock, patch
from PIL import Image

from app.ocr_engine import OCREngine
from app.hover_tracker import HoverTracker
from app.gui.result_hud import ResultHUD
from app.gui.hover_tooltip import HoverTooltip


class TestSentenceMining(unittest.TestCase):
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
        self.mock_db = MagicMock()
        self.mock_db.is_word_saved.return_value = False
        self.mock_translator = MagicMock()

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
        if ResultHUD._instance:
            try:
                ResultHUD._instance.close()
            except Exception:
                pass
            ResultHUD._instance = None

    def test_ps_script_contains_line_text(self):
        """PowerShell OCR betiği $words içine line_text = $line.Text alanını eklemelidir."""
        script_path = self.ocr._ps_script
        self.assertTrue(script_path.exists())
        content = script_path.read_text(encoding="utf-8")
        self.assertIn("line_text = $line.Text", content)

    def test_windows_ocr_boxes_include_sentence(self):
        """_boxes_with_windows_ocr çıktısı her kutucukta sentence alanını içermelidir."""
        mock_output = json.dumps([
            {
                "text": "Das",
                "x": 10, "y": 20, "w": 30, "h": 15,
                "line_text": "Das ist ein schönes Haus."
            },
            {
                "text": "Haus",
                "x": 80, "y": 20, "w": 40, "h": 15,
                "line_text": "Das ist ein schönes Haus."
            }
        ])

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = mock_output
            mock_run.return_value.returncode = 0

            img = Image.new("RGB", (200, 50), color="white")
            boxes = self.ocr._boxes_with_windows_ocr(img)

            self.assertEqual(len(boxes), 2)
            self.assertEqual(boxes[0]["text"], "Das")
            self.assertEqual(boxes[0]["sentence"], "Das ist ein schönes Haus.")
            self.assertEqual(boxes[1]["text"], "Haus")
            self.assertEqual(boxes[1]["sentence"], "Das ist ein schönes Haus.")
            self.assertIn("x", boxes[0])
            self.assertIn("y", boxes[0])
            self.assertIn("w", boxes[0])
            self.assertIn("h", boxes[0])

    def test_tesseract_boxes_grouped_by_line_num_include_sentence(self):
        """_boxes_with_tesseract çıktısı kelimeleri aynı line_num'a göre gruplayıp sentence eklemelidir."""
        tsv_content = (
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
            "5\t1\t1\t1\t1\t1\t10\t10\t30\t15\t95\tHeute\n"
            "5\t1\t1\t1\t1\t2\t50\t10\t35\t15\t95\tist\n"
            "5\t1\t1\t1\t1\t3\t90\t10\t45\t15\t95\tMontag\n"
            "5\t1\t1\t1\t2\t1\t10\t35\t40\t15\t95\tMorgen\n"
            "5\t1\t1\t1\t2\t2\t60\t35\t50\t15\t95\tDienstag\n"
        )

        with patch.object(self.ocr, "tesseract_cmd", "/mock/tesseract"), \
             patch("os.path.isfile", return_value=True), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = tsv_content
            mock_run.return_value.returncode = 0

            img = Image.new("RGB", (200, 80), color="white")
            boxes = self.ocr._boxes_with_tesseract(img)

            self.assertEqual(len(boxes), 5)
            # 1. Satır: Heute ist Montag
            self.assertEqual(boxes[0]["text"], "Heute")
            self.assertEqual(boxes[0]["sentence"], "Heute ist Montag")
            self.assertEqual(boxes[1]["text"], "ist")
            self.assertEqual(boxes[1]["sentence"], "Heute ist Montag")
            self.assertEqual(boxes[2]["text"], "Montag")
            self.assertEqual(boxes[2]["sentence"], "Heute ist Montag")

            # 2. Satır: Morgen Dienstag
            self.assertEqual(boxes[3]["text"], "Morgen")
            self.assertEqual(boxes[3]["sentence"], "Morgen Dienstag")
            self.assertEqual(boxes[4]["text"], "Dienstag")
            self.assertEqual(boxes[4]["sentence"], "Morgen Dienstag")

    def test_hover_tracker_captures_context_sentence_and_sets_example_de(self):
        """HoverTracker hedef kutucuktaki cümleyi context_sentence ve example_de olarak eklemelidir."""
        on_hover = MagicMock()
        on_leave = MagicMock()

        tracker = HoverTracker(
            ocr_engine=self.ocr,
            translator=self.mock_translator,
            on_word_hover=on_hover,
            on_hover_leave=on_leave,
        )

        mock_box = {
            "text": "Katze",
            "x": 210, "y": 55, "w": 40, "h": 20,
            "sentence": "Die Katze schläft auf dem Sofa."
        }

        self.mock_translator.translate_and_analyze.return_value = {
            "german": "Katze",
            "turkish": "kedi",
            "article": "die",
            "example_de": ""  # Henüz örnek cümle yok
        }

        with patch("app.hover_tracker.capture_screen_rect_gdi", return_value=Image.new("RGB", (440, 120))), \
             patch.object(tracker.ocr_engine, "recognize_words_with_boxes", return_value=[mock_box]):

            tracker._inspect_hover_area(cursor_x=200, cursor_y=200, is_passive_hover=False)

            self.assertTrue(on_hover.called)
            called_data = on_hover.call_args[0][0]
            self.assertEqual(called_data.get("context_sentence"), "Die Katze schläft auf dem Sofa.")
            self.assertEqual(called_data.get("example_de"), "Die Katze schläft auf dem Sofa.")

    def test_hover_tracker_does_not_overwrite_existing_example_de(self):
        """Eğer çevirmen zaten bir example_de döndürdüyse üzerine yazılmamalı, context_sentence ayrı saklanmalıdır."""
        on_hover = MagicMock()
        tracker = HoverTracker(
            ocr_engine=self.ocr,
            translator=self.mock_translator,
            on_word_hover=on_hover,
            on_hover_leave=MagicMock(),
        )

        mock_box = {
            "text": "Hund",
            "x": 210, "y": 55, "w": 40, "h": 20,
            "sentence": "Mein Hund rennt schnell."
        }

        self.mock_translator.translate_and_analyze.return_value = {
            "german": "Hund",
            "turkish": "köpek",
            "example_de": "Hunde sind treue Freunde."
        }

        with patch("app.hover_tracker.capture_screen_rect_gdi", return_value=Image.new("RGB", (440, 120))), \
             patch.object(tracker.ocr_engine, "recognize_words_with_boxes", return_value=[mock_box]):

            tracker._inspect_hover_area(cursor_x=200, cursor_y=200, is_passive_hover=False)

            self.assertTrue(on_hover.called)
            called_data = on_hover.call_args[0][0]
            self.assertEqual(called_data.get("context_sentence"), "Mein Hund rennt schnell.")
            self.assertEqual(called_data.get("example_de"), "Hunde sind treue Freunde.")

    def test_hover_tracker_process_hover_detection_alias(self):
        """_process_hover_detection metodu _inspect_hover_area ile aynı işlevi görmelidir."""
        tracker = HoverTracker(
            ocr_engine=self.ocr,
            translator=self.mock_translator,
            on_word_hover=MagicMock(),
            on_hover_leave=MagicMock(),
        )
        self.assertEqual(tracker._process_hover_detection, tracker._inspect_hover_area)

    def test_result_hud_displays_context_label_and_saves_sentence(self):
        """ResultHUD bağlam etiketini göstermeli ve ⭐ tıklandığında example_de olarak kaydetmelidir."""
        data = {
            "german": "Baum",
            "turkish": "ağaç",
            "article": "der",
            "plural": "die Bäume",
            "context_sentence": "Der alte Baum steht vor dem Haus."
        }

        ResultHUD.show_result(self.root, data, db=self.mock_db, config={})
        hud = ResultHUD._instance
        self.assertIsNotNone(hud)
        self.root.update_idletasks()

        # 1. Bağlam etiketi gösterildi mi?
        self.assertIsNotNone(hud.context_label)
        self.assertEqual(hud.context_label.cget("text"), '💬 Bağlam: "Der alte Baum steht vor dem Haus."')

        # 2. ⭐ Butonuna tıklandığında (_toggle_favorite) DB'ye cümleyle birlikte kaydedildi mi?
        hud._toggle_favorite()
        self.assertTrue(self.mock_db.add_word.called)
        call_kwargs = self.mock_db.add_word.call_args[1]
        self.assertEqual(call_kwargs.get("german"), "Baum")
        self.assertEqual(call_kwargs.get("turkish"), "ağaç")
        self.assertEqual(call_kwargs.get("example_de"), "Der alte Baum steht vor dem Haus.")

    def test_result_hud_fallback_to_example_de_for_context_label(self):
        """context_sentence yoksa fakat example_de varsa bağlam etiketi example_de metnini göstermelidir."""
        data = {
            "german": "Buch",
            "turkish": "kitap",
            "article": "das",
            "example_de": "Ich lese ein Buch."
        }

        ResultHUD.show_result(self.root, data, db=self.mock_db, config={})
        hud = ResultHUD._instance
        self.root.update_idletasks()

        self.assertIsNotNone(hud.context_label)
        self.assertEqual(hud.context_label.cget("text"), '💬 Bağlam: "Ich lese ein Buch."')

        hud._toggle_favorite()
        call_kwargs = self.mock_db.add_word.call_args[1]
        self.assertEqual(call_kwargs.get("example_de"), "Ich lese ein Buch.")

    def test_result_hud_without_context_does_not_show_context_label(self):
        """context_sentence ve example_de yoksa bağlam etiketi gösterilmemelidir."""
        data = {
            "german": "Sonne",
            "turkish": "güneş",
            "article": "die"
        }

        ResultHUD.show_result(self.root, data, db=self.mock_db, config={})
        hud = ResultHUD._instance
        self.root.update_idletasks()

        self.assertIsNone(hud.context_label)

    def test_hover_tooltip_saves_context_sentence(self):
        """HoverTooltip üzerindeki yıldız tıklandığında context_sentence example_de olarak kaydedilmelidir."""
        tooltip = HoverTooltip(self.root, db=self.mock_db)
        try:
            data = {
                "german": "Vogel",
                "turkish": "kuş",
                "article": "der",
                "context_sentence": "Ein kleiner Vogel singt im Garten."
            }
            tooltip.show(data, 100, 100)
            self.root.update_idletasks()

            tooltip._toggle_save()
            self.assertTrue(self.mock_db.add_word.called)
            call_kwargs = self.mock_db.add_word.call_args[1]
            self.assertEqual(call_kwargs.get("german"), "Vogel")
            self.assertEqual(call_kwargs.get("example_de"), "Ein kleiner Vogel singt im Garten.")
        finally:
            tooltip.window.destroy()


if __name__ == "__main__":
    unittest.main()
