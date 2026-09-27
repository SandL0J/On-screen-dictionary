"""
Almanca Dil Analiz Birim Testleri
"""
import unittest
from app.german_analyzer import (
    clean_text, is_single_word, extract_base_word, predict_gender_by_rules,
    analyze_sentence_grammar, get_offline_analysis, get_offline_reverse_analysis
)


class TestGermanAnalyzer(unittest.TestCase):
    def test_clean_text(self):
        self.assertEqual(clean_text("  hallo   welt  "), "hallo welt")
        self.assertEqual(clean_text(""), "")
        self.assertEqual(clean_text(None), "")

    def test_is_single_word(self):
        self.assertTrue(is_single_word("Haus"))
        self.assertTrue(is_single_word("das Haus"))
        self.assertTrue(is_single_word("der Mann"))
        self.assertTrue(is_single_word("die Frau"))
        self.assertTrue(is_single_word("ein Hund"))
        self.assertFalse(is_single_word("Ich gehe nach Hause"))

    def test_extract_base_word(self):
        art, base = extract_base_word("der Tisch")
        self.assertEqual(art, "der")
        self.assertEqual(base, "Tisch")

        art, base = extract_base_word("die Katze")
        self.assertEqual(art, "die")
        self.assertEqual(base, "Katze")

        art, base = extract_base_word("Buch")
        self.assertEqual(art, "")
        self.assertEqual(base, "Buch")

    def test_predict_gender_by_rules(self):
        # -ung -> die
        art, _ = predict_gender_by_rules("Wohnung")
        self.assertEqual(art, "die")

        # -heit -> die
        art, _ = predict_gender_by_rules("Freiheit")
        self.assertEqual(art, "die")

        # -keit -> die
        art, _ = predict_gender_by_rules("Möglichkeit")
        self.assertEqual(art, "die")

        # -or -> der
        art, _ = predict_gender_by_rules("Motor")
        self.assertEqual(art, "der")

        # -chen -> das
        art, _ = predict_gender_by_rules("Mädchen")
        self.assertEqual(art, "das")

        # -ment -> das
        art, _ = predict_gender_by_rules("Dokument")
        self.assertEqual(art, "das")

    def test_analyze_sentence_grammar(self):
        sentence = "Ich lerne Deutsch, weil ich in Deutschland leben will."
        notes = analyze_sentence_grammar(sentence)
        titles = [n["title"] for n in notes]

        # 'weil' bağlacı yakalanmalı
        self.assertTrue(any("'weil'" in t for t in titles))
        # 'will' modal fiili yakalanmalı
        self.assertTrue(any("wollen" in t for t in titles))

    def test_offline_analysis(self):
        res = get_offline_analysis("Haus")
        self.assertIsNotNone(res)
        self.assertEqual(res["article"], "das")
        self.assertIn("Häuser", res["plural"])

        res2 = get_offline_analysis("das Auto")
        self.assertIsNotNone(res2)
        self.assertEqual(res2["article"], "das")

        # Cümleler için offline analizer None dönmeli
        self.assertIsNone(get_offline_analysis("Das ist ein sehr schönes Haus."))

    def test_offline_reverse_analysis(self):
        # Türkçe kelimeden Almanca karşılık ve artikel bulma
        res = get_offline_reverse_analysis("kitap")
        self.assertIsNotNone(res)
        self.assertEqual(res["article"], "das")
        self.assertIn("Buch", res["german"])
        self.assertIn("Bücher", res["plural"])

        res2 = get_offline_reverse_analysis("araba")
        self.assertIsNotNone(res2)
        self.assertEqual(res2["article"], "das")
        self.assertIn("Auto", res2["german"])

        # Bilinmeyen veya cümle için None dönmeli
        self.assertIsNone(get_offline_reverse_analysis("bu bir araba"))
        self.assertIsNone(get_offline_reverse_analysis(""))


if __name__ == "__main__":
    unittest.main()
