"""
Unit tests for the German Lemmatizer module (app/lemmatizer.py).
Fully isolated, no network, no Tkinter dependencies, fast execution (< 1s).
"""

import unittest
from app.lemmatizer import (
    LemmaResult,
    resolve_lemma,
    format_lemma_hint
)


class TestLemmatizer(unittest.TestCase):
    """Lemmatizer ve ayrılabilir fiil çözümleme testleri."""

    def test_table_driven_lemma_resolution(self):
        """Plan dokümanındaki test tablosunu doğrular."""
        test_cases = [
            # (word, sentence, expected_lemma, expected_conf, expected_source, note)
            ("ging", "", "gehen", "high", "irregular_table", "Präteritum güçlü fiil"),
            ("war", "", "sein", "high", "irregular_table", "Präteritum sein"),
            ("ist", "", "sein", "high", "irregular_table", "Präsens sein"),
            ("hat", "", "haben", "high", "irregular_table", "Präsens haben"),
            ("kann", "", "können", "high", "irregular_table", "Modal fiil"),
            ("fängt", "Er fängt morgen an.", "anfangen", "high", "separable_rule", "Ayrılabilir fiil (fiil hover)"),
            ("an", "Er fängt morgen an.", "anfangen", "high", "separable_rule", "Ayrılabilir fiil (önek hover)"),
            ("aufsteht", "Ich weiß, dass er früh aufsteht.", "aufstehen", "high", "participle_rule", "Yan cümlede birleşik"),
            ("an", "Er denkt an dich.", "an", "none", "none", "Edat tuzağı: an son kelime değil"),
            ("denkt", "Er denkt an dich.", "denken", "medium", "regular_rule", "Ayrılabilir değil, düzenli"),
            ("aufgestanden", "", "aufstehen", "high", "participle_rule", "Partizip II ayrılabilir"),
            ("angefangen", "", "anfangen", "high", "participle_rule", "Partizip II ayrılabilir"),
            ("anzufangen", "", "anfangen", "high", "participle_rule", "zu-Infinitiv"),
            ("verstehe", "", "verstehen", "high", "participle_rule", "Ayrılmayan önek (ver-)"),
            ("machte", "", "machen", "medium", "regular_rule", "Düzenli Präteritum"),
            ("Haus", "", "Haus", "none", "none", "Büyük harfli isimlere dokunulmaz"),
            ("xyzqw", "", "xyzqw", "none", "none", "Bilinmeyen kelime"),
            ("", "", "", "none", "none", "Boş metin"),
            (None, "", "", "none", "none", "None girdisi"),
            ("...", "", "...", "none", "none", "Sadece noktalama"),
        ]

        for word, sentence, exp_lemma, exp_conf, exp_source, note in test_cases:
            with self.subTest(word=word, sentence=sentence, note=note):
                res = resolve_lemma(word, sentence)
                self.assertIsInstance(res, LemmaResult)
                self.assertEqual(res.lemma, exp_lemma, f"Failed for {word}: got {res.lemma}, expected {exp_lemma} ({note})")
                self.assertEqual(res.confidence, exp_conf, f"Failed confidence for {word}: got {res.confidence}")
                self.assertEqual(res.source, exp_source, f"Failed source for {word}: got {res.source}")

    def test_clause_boundary_no_cross_split(self):
        """Yan cümle sınırları aşılarak ayrılabilir fiil uydurulmamalı."""
        # "steht" ana cümlede veya bağımsızken, sonraki yan cümlenin sonundaki "auf" ile birleşmemeli
        sentence = "Er steht hier, weil jemand die Tür aufmacht."
        res = resolve_lemma("steht", sentence)
        self.assertEqual(res.lemma, "stehen")
        self.assertNotEqual(res.lemma, "aufstehen")

    def test_format_lemma_hint(self):
        """format_lemma_hint metninin UI format kurallarına uygunluğunu doğrular."""
        # 1. Präteritum irregular
        res_ging = resolve_lemma("ging", "")
        hint_ging = format_lemma_hint(res_ging)
        self.assertIn("🔁", hint_ging)
        self.assertIn("ging → gehen", hint_ging)
        self.assertIn("Präteritum", hint_ging)

        # 2. Separable verb (Durum 1)
        res_faengt = resolve_lemma("fängt", "Er fängt morgen an.")
        hint_faengt = format_lemma_hint(res_faengt)
        self.assertIn("🧩", hint_faengt)
        self.assertIn("fängt … an → anfangen", hint_faengt)
        self.assertIn("ayrılabilir fiil", hint_faengt)

        # 3. Separable verb (Durum 2 - önek hover)
        res_an = resolve_lemma("an", "Er fängt morgen an.")
        hint_an = format_lemma_hint(res_an)
        self.assertIn("🧩", hint_an)
        self.assertIn("anfangen", hint_an)
        self.assertIn("ayrılabilir fiil", hint_an)

        # 4. Değişiklik yok veya none confidence -> boş metin
        res_haus = resolve_lemma("Haus", "")
        self.assertEqual(format_lemma_hint(res_haus), "")

        res_none = resolve_lemma("xyzqw", "")
        self.assertEqual(format_lemma_hint(res_none), "")


if __name__ == "__main__":
    unittest.main()
