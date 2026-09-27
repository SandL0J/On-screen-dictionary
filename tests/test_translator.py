"""
Çeviri Motoru Birim Testleri
"""
import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path
from app.database import Database
from app.translator import TranslationEngine
from app.gemini_service import GeminiService


import gc

class TestTranslator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = Database(self.db_path)
        self.translator = TranslationEngine(db=self.db)

    def tearDown(self):
        self.translator = None
        self.db = None
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_translate_offline_word(self):
        res = self.translator.translate_and_analyze("Buch")
        self.assertEqual(res["article"], "das")
        self.assertIn("kitap", res["turkish"].lower())
        self.assertFalse(res["is_sentence"])

    def test_translate_online_word_with_caching(self):
        res = self.translator.translate_and_analyze("Entscheidung")
        self.assertEqual(res["article"], "die")
        self.assertIn("karar", res["turkish"].lower())

        # İkinci çağrıda önbellekten gelmeli
        res_cached = self.translator.translate_and_analyze("Entscheidung")
        self.assertTrue(res_cached.get("from_cache", False))

    def test_translate_sentence(self):
        sentence = "Wir müssen heute Deutsch sprechen."
        res = self.translator.translate_and_analyze(sentence)
        self.assertTrue(res["is_sentence"])
        self.assertTrue(len(res["turkish"]) > 0)
        self.assertTrue(len(res.get("grammar_notes", [])) > 0)

    def test_translate_german_sentence_to_turkish(self):
        # Almanca cümle Türkçe'ye çevrilmeli
        res = self.translator.translate_and_analyze("Ich gehe nach Hause")
        self.assertEqual(res["direction"], "de_to_tr")
        self.assertTrue(res["is_sentence"])
        self.assertIn("ev", res["turkish"].lower())

    def test_translate_german_verb(self):
        # Almanca fiil Türkçe'ye çevrilmeli
        res = self.translator.translate_and_analyze("Kreuzen")
        self.assertEqual(res["direction"], "de_to_tr")
        self.assertTrue(len(res["turkish"]) > 0)
        self.assertNotEqual(res["turkish"].lower(), "kreuzen")

    @patch.object(GeminiService, "translate_and_analyze")
    def test_translate_direct_gemini_mode(self, mock_gemini_trans):
        mock_gemini_trans.return_value = {
            "original": "Hund",
            "german": "der Hund",
            "turkish": "köpek",
            "article": "der",
            "plural": "die Hunde",
            "pos": "isim",
            "is_sentence": False,
            "grammar_notes": [],
            "dict_entries": [{"pos": "isim", "meanings": ["köpek"]}],
            "examples": [],
            "direction": "de_to_tr",
            "detected_lang": "de",
            "source": "gemini_ai",
            "model_used": "gemini-1.5-flash"
        }
        self.translator.set_gemini_key("AIzaSyValidKeyForTesting123")
        self.translator.set_gemini_options(use_direct=True, model="gemini-1.5-flash")

        res = self.translator.translate_and_analyze("Hund")
        self.assertEqual(res["source"], "gemini_ai")
        self.assertEqual(res["turkish"], "köpek")
        self.assertEqual(res["article"], "der")
        mock_gemini_trans.assert_called_once_with("Hund")

    @patch.object(GeminiService, "translate_and_analyze")
    def test_translate_direct_gemini_fallback(self, mock_gemini_trans):
        # Gemini hata verirse otomatik olarak yerel / standart motora geçmeli
        mock_gemini_trans.side_effect = Exception("API connection timeout")
        self.translator.set_gemini_key("AIzaSyValidKeyForTesting123")
        self.translator.set_gemini_options(use_direct=True, model="gemini-1.5-flash")

        res = self.translator.translate_and_analyze("Buch")
        self.assertIsNotNone(res)
        self.assertEqual(res["article"], "das")
        self.assertIn("kitap", res["turkish"].lower())

    def test_empty_input(self):
        res = self.translator.translate_and_analyze("")
        self.assertIn("error", res)


if __name__ == "__main__":
    unittest.main()
