"""
Unit and integration tests for:
1. GeminiService.analyze_sentence_grammar
2. TranslationEngine.analyze_grammar
3. HoverTracker lemma integration and cache invariance
4. ResultHUD and GrammarPanel UI components
5. SettingsWindow lemma and grammar checkbox toggling
"""

import json
import unittest
from unittest.mock import MagicMock, patch
import tkinter as tk

from app.gemini_service import GeminiService, clean_json_markdown
from app.translator import TranslationEngine
from app.database import Database
from app.hover_tracker import HoverTracker
from app.gui.result_hud import ResultHUD
from app.gui.grammar_panel import GrammarPanel
from app.gui.settings_window import SettingsWindow
from app.config import DEFAULT_CONFIG


class TestGeminiGrammarService(unittest.TestCase):
    """GeminiService.analyze_sentence_grammar testleri."""

    def test_clean_json_markdown(self):
        """Markdown kod bloklarını temizler."""
        self.assertEqual(clean_json_markdown("```json\n{\"a\": 1}\n```"), '{"a": 1}')
        self.assertEqual(clean_json_markdown("```\n{\"a\": 2}\n```"), '{"a": 2}')
        self.assertEqual(clean_json_markdown('{"a": 3}'), '{"a": 3}')
        self.assertEqual(clean_json_markdown(""), "")

    def test_unconfigured_returns_none(self):
        """API anahtarı yapılandırılmamışsa API'yi çağırmadan None döner."""
        service = GeminiService(api_key="")
        with patch.object(service, "_call_gemini_api") as mock_api:
            res = service.analyze_sentence_grammar("Er geht nach Hause.")
            self.assertIsNone(res)
            mock_api.assert_not_called()

    def test_sensitive_sentence_rejected(self):
        """Hassas veri içeren cümle reddedilir ve API çağrılmaz."""
        service = GeminiService(api_key="valid_dummy_key_123456789")
        with patch.object(service, "_call_gemini_api") as mock_api:
            res = service.analyze_sentence_grammar("Mein Passwort ist Secret123!")
            self.assertIsNone(res)
            mock_api.assert_not_called()

    def test_valid_json_response_parsing(self):
        """Geçerli JSON yanıtı doğru alanlarla parse edilir ve sınırlandırılır."""
        service = GeminiService(api_key="valid_dummy_key_123456789", model="gemini-3.5-flash-lite")
        dummy_json = {
            "translation_tr": "Yarın işe başlıyor.",
            "clauses": [
                {"text": "Er fängt morgen an", "type": "ana", "conjunction": None, "verb_position": "V2", "explanation_tr": "Ana cümle"}
            ],
            "verbs": [
                {"surface": "fängt ... an", "lemma": "anfangen", "tense": "Präsens", "separable_prefix": "an", "is_modal": False, "position_note_tr": "Ayrılabilir fiil"}
            ],
            "cases": [
                {"phrase": "den Hund", "case": "Akkusativ", "reason_tr": "Nesne"},
                {"phrase": "ungültig", "case": "Locative", "reason_tr": "Geçersiz"}
            ],
            "focus_word": {"surface": "fängt", "lemma": "anfangen", "role_tr": "Çekimli fiil"},
            "tips_tr": ["İpucu 1", "İpucu 2", "İpucu 3", "İpucu 4 fazla"]
        }

        with patch.object(service, "_call_gemini_api", return_value="```json\n" + json.dumps(dummy_json) + "\n```"):
            res = service.analyze_sentence_grammar("Er fängt morgen an.", focus_word="fängt")
            self.assertIsNotNone(res)
            self.assertEqual(res["translation_tr"], "Yarın işe başlıyor.")
            self.assertEqual(res["source"], "gemini_grammar")
            self.assertEqual(res["model_used"], "gemini-3.5-flash-lite")
            self.assertEqual(len(res["clauses"]), 1)
            self.assertEqual(res["clauses"][0]["verb_position"], "V2")
            self.assertEqual(len(res["verbs"]), 1)
            self.assertEqual(res["verbs"][0]["lemma"], "anfangen")
            # Geçersiz "Locative" elenmiş olmalı; sadece Akkusativ kalmalı
            self.assertEqual(len(res["cases"]), 1)
            self.assertEqual(res["cases"][0]["case"], "Akkusativ")
            # İpuçları en fazla 3 olmalı
            self.assertEqual(len(res["tips_tr"]), 3)
            self.assertIsNotNone(res["focus_word"])
            self.assertEqual(res["focus_word"]["lemma"], "anfangen")

    def test_broken_json_returns_none(self):
        """Bozuk JSON çıktısı geldiğinde çökmez, None döner."""
        service = GeminiService(api_key="valid_dummy_key_123456789")
        with patch.object(service, "_call_gemini_api", return_value="Bu bir JSON değil {bozuk"):
            res = service.analyze_sentence_grammar("Er fängt morgen an.")
            self.assertIsNone(res)


class TestTranslationEngineGrammar(unittest.TestCase):
    """TranslationEngine.analyze_grammar testleri."""

    def setUp(self):
        self.db = Database()
        self.engine = TranslationEngine(db=self.db, gemini_api_key="")

    def tearDown(self):
        self.db.close()

    def test_rule_based_fallback_when_gemini_not_configured(self):
        """Gemini yapılandırılmamışsa kural tabanlı analiz döner ve needs_gemini=True olur."""
        res = self.engine.analyze_grammar("Er steht früh auf, weil er arbeiten muss.")
        self.assertEqual(res["source"], "rule_based")
        self.assertTrue(res["needs_gemini"])
        self.assertTrue(len(res["rule_notes"]) > 0)

    def test_gemini_success_caching(self):
        """Gemini başarılı olduğunda sonuç SQLite önbelleğine yazılır ve ikinci çağrıda API çağrılmaz."""
        self.engine.set_gemini_key("valid_dummy_key_123456789")
        mock_result = {
            "sentence": "Er geht nach Hause.",
            "translation_tr": "O eve gidiyor.",
            "clauses": [],
            "verbs": [],
            "cases": [],
            "focus_word": None,
            "tips_tr": [],
            "model_used": "gemini-3.5-flash-lite",
            "source": "gemini_grammar"
        }

        with patch.object(self.engine.gemini_service, "analyze_sentence_grammar", return_value=mock_result) as mock_analyze:
            # 1. Çağrı
            res1 = self.engine.analyze_grammar("Er geht nach Hause.")
            self.assertEqual(res1["source"], "gemini_grammar")
            self.assertEqual(mock_analyze.call_count, 1)

            # 2. Çağrı: Önbellekten gelmeli
            res2 = self.engine.analyze_grammar("Er geht nach Hause.")
            self.assertEqual(res2["source"], "gemini_grammar")
            self.assertTrue(res2.get("from_cache"))
            self.assertEqual(mock_analyze.call_count, 1)


class TestHoverLemmaIntegration(unittest.TestCase):
    """HoverTracker üzerinde Lemma çözümleme ve önbellek mutasyon koruması testleri."""

    def test_hover_resolves_lemma_and_preserves_cache(self):
        """Hover sırasında 'fängt' sözcüğü 'anfangen' olarak sorgulanır, önbellek mutasyonu engellenir."""
        shared_cached_dict = {
            "german": "anfangen",
            "turkish": "başlamak",
            "article": "",
            "plural": "",
            "is_sentence": False
        }

        mock_translator = MagicMock()
        mock_translator.translate_and_analyze.return_value = shared_cached_dict

        tracker = HoverTracker(
            ocr_engine=MagicMock(),
            translator=mock_translator,
            on_word_hover=MagicMock(),
            on_hover_leave=MagicMock(),
            config={"lemma_lookup_enabled": True}
        )

        # Hedef kelime ve OCR kutusu (rel_cursor_x=160, rel_cursor_y=80 konumuna denk gelen kutu)
        target_box = {"x": 150, "y": 70, "w": 40, "h": 20, "text": "fängt", "sentence": "Er fängt morgen an."}
        with patch("app.hover_tracker.capture_screen_rect_gdi", return_value=MagicMock()):
            with patch.object(tracker.ocr_engine, "recognize_words_with_boxes", return_value=[target_box]):
                tracker._inspect_hover_area(100, 100)

        # Translator anfangen ile çağrılmış olmalı
        mock_translator.translate_and_analyze.assert_called_with("anfangen")

        # Callback çağrılmış olmalı
        self.assertTrue(tracker.on_word_hover.called)
        call_args = tracker.on_word_hover.call_args[0]
        result_data = call_args[0]

        self.assertEqual(result_data["surface_form"], "fängt")
        self.assertEqual(result_data["lemma"], "anfangen")
        self.assertIn("🧩", result_data.get("lemma_hint", ""))

        # Önbellekteki orijinal sözlük nesnesi mutasyona uğramamış olmalı!
        self.assertNotIn("surface_form", shared_cached_dict)

    def test_hover_lemma_fallback_on_error(self):
        """Lemma çevirisi hata verirse orijinal yüzey kelimesiyle geri dönüş yapılır."""
        mock_translator = MagicMock()
        # İlk çağrı (anfangen) None, ikinci çağrı (fängt) sözlük döner
        mock_translator.translate_and_analyze.side_effect = [
            None,
            {"german": "fangen", "turkish": "yakalamak", "is_sentence": False}
        ]

        tracker = HoverTracker(
            ocr_engine=MagicMock(),
            translator=mock_translator,
            on_word_hover=MagicMock(),
            on_hover_leave=MagicMock(),
            config={"lemma_lookup_enabled": True}
        )

        target_box = {"x": 150, "y": 70, "w": 40, "h": 20, "text": "fängt", "sentence": "Er fängt morgen an."}
        with patch("app.hover_tracker.capture_screen_rect_gdi", return_value=MagicMock()):
            with patch.object(tracker.ocr_engine, "recognize_words_with_boxes", return_value=[target_box]):
                tracker._inspect_hover_area(100, 100)

        self.assertEqual(mock_translator.translate_and_analyze.call_count, 2)
        mock_translator.translate_and_analyze.assert_any_call("anfangen")
        mock_translator.translate_and_analyze.assert_any_call("fängt")


class TestUIComponents(unittest.TestCase):
    """ResultHUD ve GrammarPanel Tkinter UI testleri (Tk pencereleri gizlenerek test edilir)."""

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.db = Database()

    def tearDown(self):
        try:
            if ResultHUD._instance and ResultHUD._instance.is_alive():
                ResultHUD._instance.close()
            if GrammarPanel._instance and GrammarPanel._instance.is_alive():
                GrammarPanel._instance.close()
            self.db.close()
            self.root.destroy()
        except Exception:
            pass

    def test_result_hud_grammar_button_and_lemma_hint(self):
        """ResultHUD üzerinde dilbilgisi butonu ve lemma_hint satırı testleri."""
        mock_grammar_cb = MagicMock()
        word_data = {
            "german": "gehen",
            "turkish": "gitmek",
            "surface_form": "ging",
            "lemma": "gehen",
            "lemma_hint": "🔁 ging → gehen · Präteritum",
            "context_sentence": "Er ging nach Hause.",
            "is_sentence": False
        }

        ResultHUD.show_result(
            self.root,
            word_data,
            db=self.db,
            config={"grammar_analysis_enabled": True},
            on_grammar_request=mock_grammar_cb
        )
        hud = ResultHUD._instance
        self.assertIsNotNone(hud)
        self.assertTrue(hud.is_alive())

        # Dilbilgisi butonu görünür olmalı (pack edilmiş olmalı)
        self.assertEqual(hud.btn_grammar.winfo_manager(), "pack")

        # Butona tıklandığında callback (context_sentence, surface_form) ile çağrılmalı
        hud._on_grammar_click()
        mock_grammar_cb.assert_called_once_with("Er ging nach Hause.", "ging")

    def test_result_hud_sentence_grammar_button(self):
        """Cümle çevirisinde dilbilgisi butonu (cümle, None) ile çağrılır."""
        mock_grammar_cb = MagicMock()
        sentence_data = {
            "german": "Er fängt morgen an.",
            "turkish": "Yarın başlıyor.",
            "is_sentence": True
        }

        ResultHUD.show_result(
            self.root,
            sentence_data,
            db=self.db,
            config={"grammar_analysis_enabled": True},
            on_grammar_request=mock_grammar_cb
        )
        hud = ResultHUD._instance
        hud._on_grammar_click()
        mock_grammar_cb.assert_called_once_with("Er fängt morgen an.", None)

    def test_grammar_panel_lifecycle_and_rendering(self):
        """GrammarPanel loading, Gemini sonucu ve kural tabanlı sonucu hatasız çizer."""
        panel = GrammarPanel.get_or_create(self.root, "Er geht nach Hause.")
        self.assertTrue(panel.is_alive())

        # 1. Loading
        panel.show_loading()

        # 2. Rule based render
        rule_data = {
            "source": "rule_based",
            "needs_gemini": True,
            "rule_notes": [
                {"badge": "Kural", "title": "Modal Fiil", "text": "Mastar sonda."}
            ]
        }
        panel.show_result(rule_data)

        # 3. Gemini result render
        gemini_data = {
            "source": "gemini_grammar",
            "translation_tr": "O eve gidiyor.",
            "clauses": [{"text": "Er geht nach Hause", "type": "ana", "conjunction": None, "verb_position": "V2", "explanation_tr": "Ana cümle"}],
            "verbs": [{"surface": "geht", "lemma": "gehen", "tense": "Präsens", "separable_prefix": None, "is_modal": False, "position_note_tr": "V2"}],
            "cases": [{"phrase": "Er", "case": "Nominativ", "reason_tr": "Özne"}],
            "focus_word": {"surface": "geht", "lemma": "gehen", "role_tr": "Yüklem"},
            "tips_tr": ["nach Hause = eve"]
        }
        panel.show_result(gemini_data)
        panel.close()
        self.assertFalse(panel.is_alive())


class TestSettingsCheckboxes(unittest.TestCase):
    """SettingsWindow üzerindeki yeni checkbox'ların kayıt ve sıfırlama testleri."""

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    @patch("tkinter.messagebox.askyesno", return_value=True)
    @patch("tkinter.messagebox.showinfo")
    def test_settings_lemma_and_grammar_toggles(self, mock_info, mock_ask):
        """Ayar penceresinde iki yeni checkbox kaydedilir ve sıfırlanır."""
        cfg = DEFAULT_CONFIG.copy()
        win = SettingsWindow(self.root, cfg, on_settings_changed=MagicMock())

        self.assertTrue(hasattr(win, "var_lemma_lookup"))
        self.assertTrue(hasattr(win, "var_grammar_analysis"))

        # Değerleri değiştir
        win.var_lemma_lookup.set(False)
        win.var_grammar_analysis.set(False)

        # Kaydet
        with patch("app.gui.settings_window.save_config") as mock_save:
            win._save()
            self.assertFalse(win.config["lemma_lookup_enabled"])
            self.assertFalse(win.config["grammar_analysis_enabled"])

        # Sıfırla
        win._reset_to_defaults()
        self.assertTrue(win.var_lemma_lookup.get())
        self.assertTrue(win.var_grammar_analysis.get())

        win.close()


if __name__ == "__main__":
    unittest.main()
