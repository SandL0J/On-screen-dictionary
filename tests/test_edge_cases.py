"""
Uç Nokta (Edge Case) ve Dayanıklılık Testleri
"""
import unittest
from unittest.mock import patch
import tempfile
import gc
from pathlib import Path
from app.database import Database
from app.german_analyzer import clean_text, predict_gender_by_rules, analyze_sentence_grammar
from app.clipboard_watcher import ClipboardWatcher
from app.translator import TranslationEngine


class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp_dir.name) / "test_edge.db")
        self.translator = TranslationEngine(db=self.db)

    def tearDown(self):
        self.translator = None
        self.db = None
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    @patch.object(TranslationEngine, "_translate_via_gt")
    @patch.object(TranslationEngine, "_fetch_wiktionary_info")
    def test_german_umlauts_and_sz(self, mock_wiki, mock_gt):
        mock_gt.return_value = {
            "translated_text": "anlam",
            "detected_lang": "de",
            "dict_entries": []
        }
        mock_wiki.return_value = {"article": "die", "plural": "", "pos": "İsim (Nomen)"}
        words = ["Überraschung", "Änderung", "Öl", "Straße", "größer"]
        for w in words:
            res = self.translator.translate_and_analyze(w)
            self.assertNotIn("error", res)
            self.assertTrue(len(res.get("turkish", "")) > 0)

    def test_sql_injection_defense(self):
        malicious = "'; DROP TABLE wordbook; --"
        # Veritabanı çökmemeli ve parametrik sorgu kullanıldığından tablo silinmemeli
        self.db.add_word(german=malicious, turkish="saldırı denemesi")
        words = self.db.get_words(search=malicious)
        self.assertEqual(len(words), 1)

        # Tablo hala sağlam olmalı
        self.assertTrue(self.db.is_word_saved(malicious))

    def test_clipboard_filter_edge_cases(self):
        watcher = ClipboardWatcher(on_text_detected=lambda t: None)

        # Geçersiz metinler (filtrelenmeli)
        self.assertFalse(watcher._is_valid_candidate("123456789"))
        self.assertFalse(watcher._is_valid_candidate("https://youtube.com/watch?v=12345"))
        self.assertFalse(watcher._is_valid_candidate("C:\\Program Files\\Python312\\python.exe"))
        self.assertFalse(watcher._is_valid_candidate("const x = () => { return a + b; };"))
        self.assertFalse(watcher._is_valid_candidate("a" * 600))  # Çok uzun metin

        # Geçerli Almanca metinler (kabul edilmeli)
        self.assertTrue(watcher._is_valid_candidate("Entscheidung"))
        self.assertTrue(watcher._is_valid_candidate("Ich verstehe nur Bahnhof."))
        self.assertTrue(watcher._is_valid_candidate("Das ist ein sehr interessanter Satz!"))

    def test_extreme_sentence_grammar_edge_cases(self):
        # Boş ve tek kelimeli durumlar
        self.assertEqual(analyze_sentence_grammar(""), [])
        self.assertEqual(analyze_sentence_grammar("   "), [])
        self.assertEqual(analyze_sentence_grammar("..."), [])

        # Birden fazla kural barındıran karmaşık cümle
        complex_sentence = "Obwohl er krank war, musste er um 6 Uhr aufstehen."
        notes = analyze_sentence_grammar(complex_sentence)
        self.assertGreaterEqual(len(notes), 2)  # obwohl, müssen, aufstehen

    @patch.object(TranslationEngine, "_translate_via_gt")
    @patch.object(TranslationEngine, "_fetch_wiktionary_info")
    def test_weird_punctuation(self, mock_wiki, mock_gt):
        mock_gt.return_value = {
            "translated_text": "merhaba",
            "detected_lang": "de",
            "dict_entries": []
        }
        mock_wiki.return_value = {"article": "", "plural": "", "pos": "Ünlem"}
        res = self.translator.translate_and_analyze("???!!!   --- Hallo??? ***")
        self.assertNotIn("error", res)


if __name__ == "__main__":
    unittest.main()
