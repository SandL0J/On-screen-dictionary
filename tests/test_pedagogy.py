"""
Almanca Pedagojik Dilbilgisi ve Öğrenme Asistanı Birim Testleri
1. Fiil İstemleri (Rektion der Verben)
2. İki Yönlü Edatlar (Wechselpräpositionen)
3. Kalıp ve Deyim Tespiti (Collocations & Redewendungen)
4. UI Kart ve Defter Entegrasyonu
"""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import tkinter as tk

from app.data.verb_valency import find_verb_valency, VERB_VALENCY_DATA
from app.data.two_way_prepositions import detect_two_way_preposition
from app.data.collocations import find_collocation
from app.pedagogy import analyze_pedagogy
from app.database import Database
from app.gui.result_hud import ResultHUD
from app.gui.hover_tooltip import HoverTooltip
from app.gui.settings_window import SettingsWindow
from app.config import DEFAULT_CONFIG


class TestVerbValency(unittest.TestCase):
    """Fiil istemleri (Rektion der Verben) doğrulama testleri."""

    def test_basic_valency_lookup(self):
        """Basit fiil sorgusu doğru edat ve hali döner."""
        res = find_verb_valency("warten")
        self.assertIsNotNone(res)
        self.assertEqual(res["preposition"], "auf")
        self.assertEqual(res["case"], "Akkusativ")
        self.assertIn("🎯", res["badge"])

    def test_reflexive_verb_valency(self):
        """Dönüşlü fiiller (sich) ve edatları doğru çözümlenir."""
        res = find_verb_valency("interessieren")
        self.assertIsNotNone(res)
        self.assertEqual(res["preposition"], "für")
        self.assertEqual(res["case"], "Akkusativ")
        self.assertTrue(res["reflexive"])

        res2 = find_verb_valency("sich interessieren")
        self.assertIsNotNone(res2)
        self.assertEqual(res2["preposition"], "für")

    def test_contextual_multi_preposition_selection(self):
        """Birden fazla edat alabilen fiiller bağlam cümlesine göre doğru olanı seçer."""
        # freuen: auf (gelecek) vs über (mevcut/geçmiş)
        res_auf = find_verb_valency("freuen", "Ich freue mich auf den Urlaub.")
        self.assertEqual(res_auf["preposition"], "auf")

        res_ueber = find_verb_valency("freuen", "Ich freue mich über das Geschenk.")
        self.assertEqual(res_ueber["preposition"], "über")

        # bestehen: aus (oluşmak) vs auf (ısrar etmek)
        res_aus = find_verb_valency("bestehen", "Das Team besteht aus fünf Spielern.")
        self.assertEqual(res_aus["preposition"], "aus")

        res_auf_b = find_verb_valency("bestehen", "Er besteht auf seinem Recht.")
        self.assertEqual(res_auf_b["preposition"], "auf")

    def test_contracted_preposition_in_sentence(self):
        """Cümlede kaynaşmış edat ('am', 'im', 'zum') geçtiğinde kök edatla eşleşir."""
        res = find_verb_valency("teilnehmen", "Er nimmt am Deutschkurs teil.")
        self.assertIsNotNone(res)
        self.assertEqual(res["preposition"], "an")
        self.assertEqual(res["case"], "Dativ")

    def test_unknown_verb_returns_none(self):
        """İstem tablosunda olmayan fiil için None döner."""
        self.assertIsNone(find_verb_valency("blablabla"))


class TestTwoWayPrepositions(unittest.TestCase):
    """İki yönlü edat (Wechselpräpositionen) Akkusativ / Dativ belirleme testleri."""

    def test_contracted_forms(self):
        """Kaynaşmış biçimler doğrudan ve kesin sonuç verir."""
        ins = detect_two_way_preposition("ins")
        self.assertIsNotNone(ins)
        self.assertEqual(ins["case"], "Akkusativ")
        self.assertIn("Wohin?", ins["question"])

        im = detect_two_way_preposition("im")
        self.assertIsNotNone(im)
        self.assertEqual(im["case"], "Dativ")
        self.assertIn("Wo?", im["question"])

        aufs = detect_two_way_preposition("aufs")
        self.assertEqual(aufs["case"], "Akkusativ")

        am = detect_two_way_preposition("am")
        self.assertEqual(am["case"], "Dativ")

    def test_article_cues_in_sentence(self):
        """Edattan sonra gelen artikel (den vs dem) hali belirler."""
        # auf den -> Akkusativ
        res_akk = detect_two_way_preposition("auf", "Er legt das Buch auf den Tisch.")
        self.assertIsNotNone(res_akk)
        self.assertEqual(res_akk["case"], "Akkusativ")
        self.assertIn("den", res_akk["hint"])

        # auf dem -> Dativ
        res_dat = detect_two_way_preposition("auf", "Das Buch liegt auf dem Tisch.")
        self.assertIsNotNone(res_dat)
        self.assertEqual(res_dat["case"], "Dativ")
        self.assertIn("dem", res_dat["hint"])

    def test_verb_type_cues_when_article_ambiguous(self):
        """Artikel belirsiz olduğunda fiilin hareket mi durum mu bildirdiği incelenir."""
        # gehen -> Akkusativ
        res_go = detect_two_way_preposition("in", "Sie geht in die Stadt.")
        self.assertIsNotNone(res_go)
        self.assertEqual(res_go["case"], "Akkusativ")

        # stehen -> Dativ
        res_stand = detect_two_way_preposition("in", "Sie steht in der Ecke.")
        self.assertIsNotNone(res_stand)
        self.assertEqual(res_stand["case"], "Dativ")

    def test_standalone_two_way_prep(self):
        """Yalnızca edat sorgulandığında genel kural açıklanır."""
        res = detect_two_way_preposition("unter")
        self.assertIsNotNone(res)
        self.assertIn("Akkusativ / Dativ", res["case"])


class TestCollocations(unittest.TestCase):
    """Kalıp, deyim ve birleşik fiil (Funktionsverbgefüge) tespit testleri."""

    def test_direct_phrase_match(self):
        """Doğrudan kalıp arandığında eşleşir."""
        res = find_collocation("auf jeden Fall")
        self.assertIsNotNone(res)
        self.assertEqual(res["phrase"], "auf jeden Fall")
        self.assertIn("kesinlikle", res["meaning_tr"])

    def test_sentence_inflected_verb_collocations(self):
        """Cümledeki çekimli fiil üzerinden kalıp tespit edilir."""
        # es geht um
        res1 = find_collocation("geht", "Es geht um Leben und Tod.")
        self.assertIsNotNone(res1)
        self.assertEqual(res1["phrase"], "es geht um")

        # Angst haben vor
        res2 = find_collocation("Angst", "Er hat große Angst vor Prüfungen.")
        self.assertIsNotNone(res2)
        self.assertEqual(res2["phrase"], "Angst haben vor")

        # in Frage kommen
        res3 = find_collocation("Frage", "Das kommt für mich nicht in Frage.")
        self.assertIsNotNone(res3)
        self.assertEqual(res3["phrase"], "in Frage kommen")

        # zur Verfügung stehen
        res4 = find_collocation("Verfügung", "Die Unterlagen stehen zur Verfügung.")
        self.assertIsNotNone(res4)
        self.assertEqual(res4["phrase"], "zur Verfügung stehen")

        # eine Entscheidung treffen
        res5 = find_collocation("Entscheidung", "Wir müssen jetzt eine Entscheidung treffen.")
        self.assertIsNotNone(res5)
        self.assertEqual(res5["phrase"], "eine Entscheidung treffen")

    def test_irrelevant_sentence_returns_none(self):
        """Kalıp içermeyen normal cümlede None döner."""
        res = find_collocation("Tisch", "Der Tisch ist aus Holz.")
        self.assertIsNone(res)


class TestUnifiedPedagogyEngine(unittest.TestCase):
    """Pedagoji motorunun birleşik çıktısı."""

    def test_analyze_pedagogy_all_components(self):
        """Fiil, edat ve kalıbın bir arada olduğu senaryo."""
        res = analyze_pedagogy("geht", "Es geht um das Kind im Zimmer.", lemma="gehen")
        self.assertIsNotNone(res["collocation"])
        self.assertEqual(res["collocation"]["phrase"], "es geht um")
        self.assertIsNotNone(res["two_way_prep"])
        self.assertEqual(res["two_way_prep"]["prep"], "in")
        self.assertTrue(len(res["pedagogy_hints"]) >= 2)


class TestPedagogyUIIntegration(unittest.TestCase):
    """ResultHUD ve HoverTooltip üzerinde pedagojik kartların çizimi ve kayıt testleri."""

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp_dir.name) / "test.db")

    def tearDown(self):
        try:
            if ResultHUD._instance and ResultHUD._instance.is_alive():
                ResultHUD._instance.close()
            self.db.close()
            self.temp_dir.cleanup()
            self.root.destroy()
        except Exception:
            pass

    def test_result_hud_pedagogy_rendering_and_save(self):
        """ResultHUD üzerinde kalıp, istem ve edat kartları render edilir; kalıp deftere kaydedilir."""
        data = {
            "german": "geht",
            "turkish": "gidiyor",
            "surface_form": "geht",
            "context_sentence": "Es geht um Leben und Tod.",
            "is_sentence": False,
            "collocation": {
                "phrase": "es geht um",
                "meaning_tr": "söz konusu olmak",
                "badge": "🧩 Kalıp: es geht um"
            },
            "valency": {
                "verb": "gehen",
                "preposition": "um",
                "case": "Akkusativ",
                "meaning_tr": "konusu olmak",
                "badge": "🎯 um + Akkusativ"
            },
            "two_way_prep": {
                "prep": "in",
                "case": "Akkusativ",
                "badge": "🏃 Akkusativ (Wohin?)",
                "hint": "🏃 İki Yönlü Edat (in): Akkusativ"
            }
        }

        ResultHUD.show_result(self.root, data, db=self.db, config={"grammar_analysis_enabled": True})
        hud = ResultHUD._instance
        self.assertIsNotNone(hud)
        self.assertTrue(hud.is_alive())

        # Kaydet butonuna basıldığında kalıp ismiyle ('es geht um') kaydedilmeli
        hud._toggle_favorite()
        self.assertTrue(self.db.is_word_saved("es geht um"))

        # Yeniden basıldığında silinmeli (Toggle)
        hud._toggle_favorite()
        self.assertFalse(self.db.is_word_saved("es geht um"))

    def test_hover_tooltip_pedagogy_and_save(self):
        """HoverTooltip üzerinde pedagoji etiketi gösterilir ve kalıp olarak kaydedilir."""
        tooltip = HoverTooltip(self.root, db=self.db)
        word_data = {
            "german": "Fall",
            "turkish": "vaka / düşüş",
            "collocation": {
                "phrase": "auf jeden Fall",
                "meaning_tr": "kesinlikle",
                "badge": "🧩 Kalıp: auf jeden Fall"
            },
            "pedagogy_hints": ["🧩 Kalıp: auf jeden Fall → kesinlikle"]
        }

        tooltip.show(word_data, 100, 100)
        self.assertEqual(tooltip.lbl_pedagogy.cget("text"), "🧩 Kalıp: auf jeden Fall → kesinlikle")
        self.assertEqual(tooltip.lbl_pedagogy.winfo_manager(), "pack")

        # Yıldızla kaydet
        tooltip._toggle_save()
        self.assertTrue(self.db.is_word_saved("auf jeden Fall"))

        tooltip.hide()
        tooltip.window.destroy()

    @patch("tkinter.messagebox.askyesno", return_value=True)
    @patch("tkinter.messagebox.showinfo")
    def test_settings_pedagogy_toggle(self, mock_info, mock_ask):
        """Ayarlar penceresinde hap dilbilgisi ipuçları checkbox'ı kaydedilir ve sıfırlanır."""
        cfg = DEFAULT_CONFIG.copy()
        win = SettingsWindow(self.root, cfg, on_settings_changed=MagicMock())

        self.assertTrue(hasattr(win, "var_pedagogy_hints"))
        win.var_pedagogy_hints.set(False)

        with patch("app.gui.settings_window.save_config") as mock_save:
            win._save()
            self.assertFalse(win.config["pedagogy_hints_enabled"])

        # Sıfırla
        win._reset_to_defaults()
        self.assertTrue(win.var_pedagogy_hints.get())
        win.window.destroy()


if __name__ == "__main__":
    unittest.main()
