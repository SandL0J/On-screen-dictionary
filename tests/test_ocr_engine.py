"""
OCR Motoru Birim Testleri
"""
import unittest
from PIL import Image, ImageDraw
from app.ocr_engine import OCREngine


class TestOCREngine(unittest.TestCase):
    def setUp(self):
        self.engine = OCREngine()

    def test_text_cleaning(self):
        dirty = "  --- Hallo Welt! \r\n  Wie gehts?  \" "
        cleaned = self.engine.clean_recognized_text(dirty)
        self.assertEqual(cleaned, "Hallo Welt! Wie gehts?")

    def test_image_preprocessing(self):
        img = Image.new("RGB", (100, 30), color=(255, 255, 255))
        prep = self.engine.preprocess_image(img)
        # Büyütülmüş ve L moduna (gri) dönüştürülmüş olmalı
        self.assertEqual(prep.mode, "L")
        self.assertGreater(prep.width, img.width)
        self.assertGreater(prep.height, img.height)

    def test_synthetic_image_recognition(self):
        img = Image.new("RGB", (400, 80), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        d.text((20, 25), "Guten Morgen", fill=(0, 0, 0))

        text = self.engine.recognize_from_image(img)
        # Windows OCR ortamda aktif ise tanımalı, hata fırlatmamalı
        self.assertIsInstance(text, str)


if __name__ == "__main__":
    unittest.main()
