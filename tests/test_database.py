"""
Veritabanı Modülü Birim Testleri
"""
import unittest
import tempfile
import os
from pathlib import Path
from app.database import Database


import gc

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = Database(self.db_path)

    def tearDown(self):
        self.db = None
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_cache_set_and_get(self):
        query = "Entscheidung"
        data = {"german": "Entscheidung", "article": "die", "turkish": "karar"}
        self.db.set_cache(query, data)

        cached = self.db.get_cache(query)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["article"], "die")
        self.assertEqual(cached["turkish"], "karar")

        # Büyük/küçük harf duyarsız olmalı
        cached_lower = self.db.get_cache("entscheidung")
        self.assertIsNotNone(cached_lower)

    def test_wordbook_crud(self):
        # Ekleme
        word_id = self.db.add_word(
            german="Haus",
            turkish="ev",
            article="das",
            plural="die Häuser",
            part_of_speech="İsim",
            example_de="Das Haus ist groß.",
            example_tr="Ev büyüktür."
        )
        self.assertGreater(word_id, 0)
        self.assertTrue(self.db.is_word_saved("Haus"))
        self.assertTrue(self.db.is_word_saved("haus"))

        # Listeleme
        words = self.db.get_words()
        self.assertEqual(len(words), 1)
        self.assertEqual(words[0]["german"], "Haus")
        self.assertEqual(words[0]["article"], "das")

        # Filtreleme
        das_words = self.db.get_words(article_filter="das")
        self.assertEqual(len(das_words), 1)
        der_words = self.db.get_words(article_filter="der")
        self.assertEqual(len(der_words), 0)

        # Durum güncelleme
        self.db.update_word_status(word_id, "mastered")
        updated = self.db.get_words()
        self.assertEqual(updated[0]["status"], "mastered")

        # Silme
        deleted = self.db.delete_word(word_id)
        self.assertTrue(deleted)
        self.assertFalse(self.db.is_word_saved("Haus"))

    def test_anki_export(self):
        self.db.add_word(german="Auto", turkish="araba", article="das", plural="die Autos")
        self.db.add_word(german="Frau", turkish="kadın", article="die", plural="die Frauen")

        export_path = Path(self.temp_dir.name) / "anki.txt"
        count = self.db.export_to_anki_csv(str(export_path))
        self.assertEqual(count, 2)
        self.assertTrue(export_path.exists())

        with open(export_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("das Auto", content)
            self.assertIn("die Frau", content)


if __name__ == "__main__":
    unittest.main()
