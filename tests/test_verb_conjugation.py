import unittest
import tempfile
import os
import tkinter as tk
from unittest.mock import MagicMock

from app.database import Database
from app.german_analyzer import (
    STRONG_VERBS,
    VERB_CONJUGATIONS_INDEX,
    get_verb_conjugation_info
)
from app.translator import TranslationEngine
from app.gui.result_hud import ResultHUD


class TestVerbConjugationEngine(unittest.TestCase):
    """Morfolojik Fiil Çözücü, Triad Şeridi ve Çevirmen Kök Entegrasyonu Birim Testleri."""

    def setUp(self):
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_file.close()
        self.db = Database(db_path=self.temp_db_file.name)
        self.engine = TranslationEngine(db=self.db)

    def tearDown(self):
        try:
            self.db.close()
        except Exception:
            pass
        if os.path.exists(self.temp_db_file.name):
            try:
                os.remove(self.temp_db_file.name)
            except Exception:
                pass

    def test_strong_verbs_data_structure(self):
        """STRONG_VERBS 200+ güçlü/düzensiz fiil içermeli ve tüm alanlar eksiksiz olmalı."""
        self.assertGreaterEqual(len(STRONG_VERBS), 200, "STRONG_VERBS en az 200 fiil içermelidir.")
        
        required_fields = {
            "infinitive", "praeteritum", "partizip2", "auxiliary",
            "perfekt", "praesens_3sg", "triad", "triad_display"
        }
        for inf, item in list(STRONG_VERBS.items())[:20]:
            self.assertTrue(required_fields.issubset(item.keys()), f"{inf} fiilinde eksik alanlar var: {set(item.keys())}")
            self.assertIn(item["auxiliary"], ("ist", "hat"), f"{inf} fiilinin yardımcı fiili ist veya hat olmalıdır.")
            self.assertTrue(item["triad_display"].startswith("📌 Mastar:"), f"{inf} triad_display formatı hatalı.")
            self.assertIn(f"Prät: {item['praeteritum']}", item["triad"])
            self.assertIn(f"Perf: {item['perfekt']}", item["triad"])

    def test_verb_conjugations_index_o1_lookup(self):
        """VERB_CONJUGATIONS_INDEX O(1) erişimle tüm çekimli kelimeleri mastarına bağlamalıdır."""
        self.assertGreaterEqual(len(VERB_CONJUGATIONS_INDEX), 1000, "İndeks 1000'den fazla form barındırmalıdır.")
        
        # Präteritum formları
        self.assertEqual(VERB_CONJUGATIONS_INDEX.get("ging"), "gehen")
        self.assertEqual(VERB_CONJUGATIONS_INDEX.get("gingst"), "gehen")
        self.assertEqual(VERB_CONJUGATIONS_INDEX.get("gingen"), "gehen")
        self.assertEqual(VERB_CONJUGATIONS_INDEX.get("sprach"), "sprechen")
        self.assertEqual(VERB_CONJUGATIONS_INDEX.get("nahm"), "nehmen")
        self.assertEqual(VERB_CONJUGATIONS_INDEX.get("sah"), "sehen")
        self.assertEqual(VERB_CONJUGATIONS_INDEX.get("war"), "sein")
        self.assertEqual(VERB_CONJUGATIONS_INDEX.get("hatte"), "haben")
        self.assertEqual(VERB_CONJUGATIONS_INDEX.get("wurde"), "werden")

        # Partizip II formları
        self.assertEqual(VERB_CONJUGATIONS_INDEX.get("gegangen"), "gehen")
        self.assertEqual(VERB_CONJUGATIONS_INDEX.get("gesehen"), "sehen")
        self.assertEqual(VERB_CONJUGATIONS_INDEX.get("genommen"), "nehmen")
        self.assertEqual(VERB_CONJUGATIONS_INDEX.get("gesprochen"), "sprechen")
        self.assertEqual(VERB_CONJUGATIONS_INDEX.get("gewesen"), "sein")

        # Präsens kök değişimi formları
        self.assertEqual(VERB_CONJUGATIONS_INDEX.get("fährt"), "fahren")
        self.assertEqual(VERB_CONJUGATIONS_INDEX.get("fährst"), "fahren")
        self.assertEqual(VERB_CONJUGATIONS_INDEX.get("sieht"), "sehen")
        self.assertEqual(VERB_CONJUGATIONS_INDEX.get("liest"), "lesen")
        self.assertEqual(VERB_CONJUGATIONS_INDEX.get("gibt"), "geben")
        self.assertEqual(VERB_CONJUGATIONS_INDEX.get("nimmt"), "nehmen")
        self.assertEqual(VERB_CONJUGATIONS_INDEX.get("hilft"), "helfen")

    def test_get_verb_conjugation_info(self):
        """get_verb_conjugation_info fonksiyonu çekimli veya mastar kelimeler için triad ve form döner."""
        # Çekimli fiil: ging
        ging_info = get_verb_conjugation_info("ging")
        self.assertIsNotNone(ging_info)
        self.assertEqual(ging_info["infinitive"], "gehen")
        self.assertEqual(ging_info["praeteritum"], "ging")
        self.assertEqual(ging_info["partizip2"], "gegangen")
        self.assertEqual(ging_info["auxiliary"], "ist")
        self.assertEqual(ging_info["perfekt"], "ist gegangen")
        self.assertEqual(ging_info["triad_display"], "📌 Mastar: gehen • Prät: ging • Perf: ist gegangen")
        self.assertEqual(ging_info["form"], "Präteritum")
        self.assertTrue(ging_info["is_inflected"])

        # Mastar: gehen
        gehen_info = get_verb_conjugation_info("gehen")
        self.assertIsNotNone(gehen_info)
        self.assertEqual(gehen_info["infinitive"], "gehen")
        self.assertEqual(gehen_info["form"], "Infinitiv")
        self.assertFalse(gehen_info["is_inflected"])

        # Partizip II: gelesen
        gelesen_info = get_verb_conjugation_info("gelesen")
        self.assertIsNotNone(gelesen_info)
        self.assertEqual(gelesen_info["infinitive"], "lesen")
        self.assertEqual(gelesen_info["auxiliary"], "hat")
        self.assertEqual(gelesen_info["perfekt"], "hat gelesen")
        self.assertEqual(gelesen_info["triad_display"], "📌 Mastar: lesen • Prät: las • Perf: hat gelesen")
        self.assertTrue(gelesen_info["is_inflected"])

        # Birleşik form: ist gegangen
        compound_info = get_verb_conjugation_info("ist gegangen")
        self.assertIsNotNone(compound_info)
        self.assertEqual(compound_info["infinitive"], "gehen")

        # Fiil olmayan kelime
        self.assertIsNone(get_verb_conjugation_info("Auto"))
        self.assertIsNone(get_verb_conjugation_info(""))
        self.assertIsNone(get_verb_conjugation_info(None))

    def test_translator_verb_root_integration(self):
        """translate_and_analyze() çekimli fiilde kök mastarı tespit edip verb_info ve pos='Fiil (Verb)' atamalıdır."""
        # 'ging' çevrildiğinde:
        res = self.engine.translate_and_analyze("ging")
        self.assertIn("verb_info", res)
        self.assertEqual(res["pos"], "Fiil (Verb)")
        self.assertEqual(res["verb_info"]["infinitive"], "gehen")
        self.assertEqual(res["verb_info"]["auxiliary"], "ist")
        self.assertEqual(res["verb_info"]["perfekt"], "ist gegangen")
        self.assertEqual(res["verb_info"]["triad_display"], "📌 Mastar: gehen • Prät: ging • Perf: ist gegangen")
        self.assertEqual(res.get("lemma"), "gehen")
        self.assertEqual(res.get("surface_form"), "ging")
        self.assertEqual(res.get("article"), "")

        # 'gehen' (mastar) çevrildiğinde:
        res_inf = self.engine.translate_and_analyze("gehen")
        self.assertIn("verb_info", res_inf)
        self.assertEqual(res_inf["pos"], "Fiil (Verb)")
        self.assertEqual(res_inf["verb_info"]["infinitive"], "gehen")
        self.assertEqual(res_inf.get("article"), "")

        # 'Buch' (isim) çevrildiğinde fiil bilgisi olmamalı:
        res_noun = self.engine.translate_and_analyze("Buch")
        self.assertNotIn("verb_info", res_noun)
        self.assertEqual(res_noun.get("article"), "das")
        self.assertNotEqual(res_noun.get("pos"), "Fiil (Verb)")

    def test_result_hud_triad_and_notes_save(self):
        """ResultHUD üzerinde triad şeridi gösterilmeli ve ⭐ tıklandığında notes alanına aktarılmalıdır."""
        root = tk.Tk()
        root.withdraw()

        try:
            # Çekimli fiil sonucuyla HUD oluştur
            hud_data = {
                "german": "ging",
                "turkish": "gitmek",
                "pos": "Fiil (Verb)",
                "surface_form": "ging",
                "lemma": "gehen",
                "verb_info": {
                    "infinitive": "gehen",
                    "praeteritum": "ging",
                    "partizip2": "gegangen",
                    "auxiliary": "ist",
                    "perfekt": "ist gegangen",
                    "triad": "Mastar: gehen • Prät: ging • Perf: ist gegangen",
                    "triad_display": "📌 Mastar: gehen • Prät: ging • Perf: ist gegangen"
                }
            }

            hud = ResultHUD(root, hud_data, db=self.db)
            
            # İçerikte triad şeridi metninin yer aldığını doğrula
            found_triad_text = False
            for widget in hud.content_frame.winfo_children():
                if isinstance(widget, tk.Frame):
                    for child in widget.winfo_children():
                        if isinstance(child, tk.Label) and "📌 Mastar: gehen" in child.cget("text"):
                            found_triad_text = True
                            break
            self.assertTrue(found_triad_text, "HUD arayüzünde '📌 Mastar: gehen' triad şeridi bulunamadı.")

            # ⭐ Kaydet butonuna tıkla
            hud._toggle_save_word()

            # Veritabanında kelimenin ve notun kontrolü
            saved_word = self.db.get_word_by_german("gehen")
            self.assertIsNotNone(saved_word, "Kelime mastar adıyla ('gehen') veritabanına kaydedilmeli.")
            self.assertEqual(saved_word["part_of_speech"], "Fiil (Verb)")
            self.assertIn("Mastar: gehen • Prät: ging • Perf: ist gegangen", saved_word["notes"],
                          "Kayıt sırasındaki notes alanına fiil triad bilgisi aktarılmalı.")
            self.assertIn("Kelime (ging)", saved_word["notes"],
                          "Kayıt sırasındaki notes alanında yüzey form bilgisi yer almalı.")

            hud.close()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
