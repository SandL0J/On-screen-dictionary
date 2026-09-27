"""
Hata Düzeltme ve Yeni Özellik Doğrulama Testleri (Bug Fixes & Feature Regression Suite)
Bu test paketi, önceki sürümde tespit edilen kritik mantık hataları ve uç durumları doğrular:
1. 'ein Tisch' / 'ein Auto' artikel ayıklama hatası (extract_base_word)
2. Noktalama işaretli kelimelerin kuralları bozması (Haus., Wohnung.)
3. Çoğul kelimelerin (Häuser, Bücher, Kinder) tekil eşleşmesi
4. 'Guten Abend!' ve 'Vorname' gibi isimlerin sahte ayrılabilir fiil üretmesi
5. 'Ich bin da.' ve 'größer als ich' ifadelerindeki sahte yan cümle bağlacı tespiti
6. 'ihr' şahsı modal fiillerinin (könnt, müsst) tanınması
7. Wiktionary 'Nominativ Plural 1=' regex desen desteği
8. Veritabanı delete_word_by_german ve kelime defteri toggle silme
9. Bileşik isim (Komposita) artikel miras alma kuralı (Krankenhaus -> das)
10. Boş metin durumunda IndexError çökmesinin engellenmesi
"""
import unittest
import tempfile
import gc
from pathlib import Path

from app.database import Database
from app.german_analyzer import (
    clean_text, is_single_word, extract_base_word, predict_gender_by_rules,
    analyze_sentence_grammar, get_offline_analysis
)
from app.translator import TranslationEngine


class TestBugFixesAndNewFeatures(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp_dir.name) / "test_bugs.db")
        self.translator = TranslationEngine(db=self.db)

    def tearDown(self):
        self.translator = None
        self.db = None
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_extract_base_word_indefinite_articles(self):
        # Önceki sürümde 'ein' kelimesi base_word olarak dönüyordu ve 'Tisch' kayboluyordu
        art, base = extract_base_word("ein Tisch")
        self.assertEqual(base, "Tisch")

        art, base = extract_base_word("eine Frau")
        self.assertEqual(base, "Frau")
        self.assertEqual(art, "die")

        art, base = extract_base_word("ein Auto")
        self.assertEqual(base, "Auto")

        art, base = extract_base_word("kein Problem")
        self.assertEqual(base, "Problem")

    def test_punctuation_stripping(self):
        # Noktalama işareti içeren kelimeler kural motorunu ve sözlüğü bozmamalı
        res = get_offline_analysis("Haus.")
        self.assertIsNotNone(res)
        self.assertEqual(res["article"], "das")

        art, _ = predict_gender_by_rules("Wohnung.")
        self.assertEqual(art, "die")

        art, _ = predict_gender_by_rules("Freiheit!")
        self.assertEqual(art, "die")

    def test_plural_offline_lookup(self):
        # Çoğul kelime arandığında temel sözlük tekilini ve çoğul bilgisini bulmalı
        res = get_offline_analysis("Häuser")
        self.assertIsNotNone(res)
        self.assertEqual(res["article"], "das")
        self.assertIn("Häuser", res["german"])

        res_b = get_offline_analysis("Bücher")
        self.assertIsNotNone(res_b)
        self.assertEqual(res_b["article"], "das")

        res_k = get_offline_analysis("Kinder")
        self.assertIsNotNone(res_k)
        self.assertEqual(res_k["article"], "das")

        # ae transliterasyonu ile çoğul arama
        res_t = get_offline_analysis("Haeuser")
        self.assertIsNotNone(res_t)
        self.assertEqual(res_t["article"], "das")

    def test_empty_string_safety(self):
        # Boş string verildiğinde IndexError vermemeli
        res = self.translator._lookup_word("")
        self.assertIn("error", res)

        res2 = self.translator._lookup_word("   ")
        self.assertIn("error", res2)

    def test_separable_verb_false_positives_eliminated(self):
        # 'Abend' ve 'Vorname' isimdir, ayrılabilir fiil olarak işaretlenmemeli
        notes_abend = analyze_sentence_grammar("Guten Abend!")
        sep_notes = [n for n in notes_abend if n["type"] == "trennbare"]
        self.assertEqual(len(sep_notes), 0)

        notes_vorname = analyze_sentence_grammar("Wie ist Ihr Vorname?")
        sep_notes_v = [n for n in notes_vorname if n["type"] == "trennbare"]
        self.assertEqual(len(sep_notes_v), 0)

    def test_separable_verb_true_positive(self):
        # Gerçek ayrılabilir fiiller doğru tespit edilmeli
        notes = analyze_sentence_grammar("Er steht jeden Morgen früh auf.")
        sep_notes = [n for n in notes if n["type"] == "trennbare"]
        self.assertEqual(len(sep_notes), 1)
        self.assertIn("auf", sep_notes[0]["title"])

    def test_conjunction_vs_adverb_disambiguation(self):
        # 'Ich bin da.' -> 'da' zarftır, yan cümle bağlacı değildir
        notes_da = analyze_sentence_grammar("Ich bin da.")
        self.assertEqual(len(notes_da), 0)

        # 'Er ist größer als ich.' -> 'als' karşılaştırmadır, yan cümle bağlacı değildir
        notes_als = analyze_sentence_grammar("Er ist größer als ich.")
        self.assertEqual(len(notes_als), 0)

        # Gerçek bağlaç:
        notes_weil = analyze_sentence_grammar("Weil er krank ist, kommt er nicht.")
        self.assertTrue(any("'weil'" in n["title"] for n in notes_weil))

    def test_modal_verbs_ihr_conjugation(self):
        # 'ihr könnt' ve 'ihr müsst' gibi ihmal edilen şahıslar tanınmalı
        notes = analyze_sentence_grammar("Ihr könnt jetzt Deutsch sprechen.")
        self.assertTrue(any("können" in n["title"] for n in notes))

        notes_m = analyze_sentence_grammar("Ihr müsst diese Aufgabe machen.")
        self.assertTrue(any("müssen" in n["title"] for n in notes_m))

    def test_compound_noun_article_inheritance(self):
        # 1. Genel arama das dönmeli
        res = self.translator.translate_and_analyze("Krankenhaus")
        self.assertEqual(res["article"], "das")

        # 2. Wiktionary'de olmayan veya çevrimdışı durumda bileşik isim son kelime kuralı devreye girmeli
        self.translator._fetch_wiktionary_info = lambda w: {'article': '', 'plural': '', 'pos': ''}
        res_fallback = self.translator._lookup_word("Krankenhaus")
        self.assertEqual(res_fallback["article"], "das")
        self.assertIn("Bileşik isim kuralı", res_fallback.get("rule_note", ""))
        self.assertEqual(res_fallback["plural"], "die Krankenhäuser")

    def test_database_delete_by_german(self):
        # Kelimeyi ekle
        self.db.add_word(german="Stuhl", turkish="sandalye", article="der")
        self.assertTrue(self.db.is_word_saved("Stuhl"))

        # delete_word_by_german ile sil
        deleted = self.db.delete_word_by_german("Stuhl")
        self.assertTrue(deleted)
        self.assertFalse(self.db.is_word_saved("Stuhl"))


if __name__ == "__main__":
    unittest.main()
