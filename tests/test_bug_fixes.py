"""
Ekran Sözlüğü Kapsamlı Hata Düzeltmeleri ve Regresyon Testleri
Bu test modülü, sprint boyunca tespit edilen ve düzeltilen tüm kritik bileşenleri
(lemmatizer, veritabanı, çeviri motoru, hover takipçi, GUI pencereleri, OCR ve Gemini servisi)
bağımsız ve derinlemesine test eder.
"""
import unittest
import tempfile
import sqlite3
import json
import time
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch
import tkinter as tk

from app.lemmatizer import resolve_lemma, _resolve_regular_verb, KNOWN_REGULAR_VERBS
from app.database import Database
from app.translator import TranslationEngine
from app.hover_tracker import _find_word_at_point, _extract_context_sentence, HoverTracker
from app.hotkey_manager import parse_hotkey, validate_hotkey_string
from app.gemini_service import GeminiService
from app.ocr_engine import OCREngine


class TestLemmatizerBugFixes(unittest.TestCase):
    """Lemmatizer Partizip II, ayrılabilir fiil ve kök çözme düzeltmeleri."""

    def test_partizip_ii_gemacht_not_gemachen(self):
        """'gemacht' kelimesi 'gemachen' değil, 'machen' olarak çözülmelidir."""
        res = resolve_lemma("gemacht")
        self.assertIsNotNone(res)
        self.assertEqual(res.lemma, "machen")
        self.assertEqual(res.confidence, "high")
        self.assertIn("Partizip II", res.form_label)

    def test_partizip_ii_separable_prefix_mitgearbeitet(self):
        """'mitgearbeitet' ayrılabilir fiili 'mitarbeiten' olarak çözülmelidir."""
        res = resolve_lemma("mitgearbeitet")
        self.assertIsNotNone(res)
        self.assertEqual(res.lemma, "mitarbeiten")
        self.assertEqual(res.confidence, "high")
        self.assertEqual(res.separable_prefix, "mit")
        self.assertIn("Partizip II", res.form_label)

    def test_partizip_ii_separable_prefix_angemeldet(self):
        """'angemeldet' ayrılabilir fiili 'anmelden' olarak çözülmelidir."""
        res = resolve_lemma("angemeldet")
        self.assertIsNotNone(res)
        self.assertEqual(res.lemma, "anmelden")
        self.assertEqual(res.confidence, "high")
        self.assertEqual(res.separable_prefix, "an")

    def test_partizip_ii_geoffnet(self):
        """'geöffnet' kelimesi 'öffnen' olarak çözülmelidir."""
        res = resolve_lemma("geöffnet")
        self.assertIsNotNone(res)
        self.assertEqual(res.lemma, "öffnen")
        self.assertEqual(res.confidence, "high")

    def test_partizip_ii_gelernt(self):
        """'gelernt' düzenli Partizip II 'lernen' olarak çözülmelidir."""
        res = resolve_lemma("gelernt")
        self.assertIsNotNone(res)
        self.assertEqual(res.lemma, "lernen")
        self.assertEqual(res.confidence, "high")

    def test_ge_stem_verbs_not_corrupted(self):
        """Doğrudan ge- ile başlayan temel fiiller (gestalten, gefährden vb.) sahte köklere bozulmamalıdır."""
        test_cases = [
            ("gestaltet", "gestalten"),
            ("gefährdet", "gefährden"),
            ("genehmigt", "genehmigen"),
            ("gestattet", "gestatten"),
            ("gewöhnt", "gewöhnen"),
        ]
        for surface, expected_lemma in test_cases:
            res = resolve_lemma(surface)
            self.assertIsNotNone(res)
            self.assertEqual(res.lemma, expected_lemma, f"{surface} -> {expected_lemma} olmalıydı, {res.lemma} oldu")
            self.assertIn(res.confidence, ("high", "medium"))

    def test_gehoert_sentence_context_differentiation(self):
        """'gehört' kelimesi cümle bağlamına göre doğru fiile (gehören vs hören) çözülmelidir."""
        # 'Das gehört mir.' -> gehören
        res_gehoeren = resolve_lemma("gehört", "Das gehört mir.")
        self.assertIsNotNone(res_gehoeren)
        self.assertEqual(res_gehoeren.lemma, "gehören")

        # 'Ich habe das gehört.' -> hören
        res_hoeren = resolve_lemma("gehört", "Ich habe das gehört.")
        self.assertIsNotNone(res_hoeren)
        self.assertEqual(res_hoeren.lemma, "hören")
        self.assertEqual(res_hoeren.form_label, "Partizip II")


class TestDatabaseUnicodeAndPreservationFixes(unittest.TestCase):
    """Veritabanı Unicode duyarsızlığı, alan koruma ve önbellek homograf testleri."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_bugs.db"
        self.db = Database(db_path=self.db_path)

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_turkish_and_german_unicode_case_insensitivity(self):
        """Türkçe ve Almanca özel harfleri (İ, I, Ä, Ö, Ü) içeren aramalarda tam eşleşme sağlanmalıdır."""
        word_id = self.db.add_word(
            german="Öffnen",
            turkish="açmak",
            article="",
            part_of_speech="Fiil"
        )
        self.assertIsNotNone(word_id)

        # Küçük harfle arandığında bulmalı
        found = self.db.get_word_by_german("öffnen")
        self.assertIsNotNone(found)
        self.assertEqual(found["turkish"], "açmak")
        self.assertTrue(self.db.is_word_saved("ÖFFNEN"))
        self.assertTrue(self.db.is_word_saved("öffnen"))

    def test_empty_update_preserves_existing_fields(self):
        """Var olan kelime boş alanlarla tekrar eklendiğinde mevcut veriler silinmemelidir."""
        self.db.add_word(
            german="Haus",
            turkish="ev",
            article="das",
            plural="die Häuser",
            part_of_speech="İsim",
            example_de="Das Haus ist groß.",
            example_tr="Ev büyüktür.",
            notes="Önemli temel kelime"
        )

        # Boş alanlarla güncelleme yapalım
        self.db.add_word(
            german="Haus",
            turkish="konut",
            article="",
            plural="",
            part_of_speech="",
            example_de="",
            example_tr="",
            notes=""
        )

        saved = self.db.get_word_by_german("Haus")
        self.assertIsNotNone(saved)
        self.assertEqual(saved["turkish"], "konut")
        self.assertEqual(saved["article"], "das", "Mevcut artikel silinmemeli")
        self.assertEqual(saved["plural"], "die Häuser", "Mevcut çoğul silinmemeli")
        self.assertEqual(saved["example_de"], "Das Haus ist groß.", "Mevcut örnek silinmemeli")
        self.assertEqual(saved["notes"], "Önemli temel kelime", "Mevcut notlar silinmemeli")

    def test_get_words_article_filter_artikelsiz(self):
        """'Artikelsiz' filtresi artikeli olmayan kelimeleri (fiil, sıfat vb.) listelemelidir."""
        self.db.add_word(german="gehen", turkish="gitmek", article="")
        self.db.add_word(german="Baum", turkish="ağaç", article="der")

        artikelsiz = self.db.get_words(article_filter="Artikelsiz")
        self.assertEqual(len(artikelsiz), 1)
        self.assertEqual(artikelsiz[0]["german"], "gehen")

    def test_cache_homograph_case_preservation(self):
        """'Leben' (isim) ve 'leben' (fiil) gibi homograflar birbirinin önbelleğini ezmemelidir."""
        noun_data = {"german": "das Leben", "article": "das", "pos": "İsim (Nomen)", "turkish": "hayat"}
        verb_data = {"german": "leben", "article": "", "pos": "Fiil (Verb)", "turkish": "yaşamak"}

        self.db.set_cache("Leben", noun_data)
        self.db.set_cache("leben", verb_data)

        cached_noun = self.db.get_cache("Leben")
        cached_verb = self.db.get_cache("leben")

        self.assertIsNotNone(cached_noun)
        self.assertIsNotNone(cached_verb)
        self.assertEqual(cached_noun["turkish"], "hayat")
        self.assertEqual(cached_noun["article"], "das")
        self.assertEqual(cached_verb["turkish"], "yaşamak")
        self.assertEqual(cached_verb["article"], "")

    def test_cache_fallback_for_regular_words(self):
        """Homograf olmayan standart kelimelerde büyük/küçük harf duyarsız önbellek eşleşmesi çalışmalıdır."""
        data = {"german": "Entscheidung", "article": "die", "turkish": "karar"}
        self.db.set_cache("Entscheidung", data)

        cached = self.db.get_cache("entscheidung")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["turkish"], "karar")

    def test_export_anki_csv_alias_and_notes(self):
        """Database.export_anki_csv metodu doğru çalışmalı ve kartlarda notları dışa aktarmalıdır."""
        self.db.add_word(
            german="Buch",
            turkish="kitap",
            article="das",
            plural="die Bücher",
            notes="Grammatik A1"
        )
        csv_path = Path(self.temp_dir.name) / "anki_test.csv"
        count = self.db.export_anki_csv(str(csv_path))
        self.assertEqual(count, 1)
        self.assertTrue(csv_path.exists())
        content = csv_path.read_text(encoding="utf-8")
        self.assertIn("Grammatik A1", content)
        self.assertIn("das Buch", content)

    def test_homograph_stale_cache_invalidation(self):
        """Veritabanında önceden yanlışlıkla isim olarak kaydedilmiş 'leben' fiil sorgusunu bozmamalıdır."""
        bad_noun_data = {"german": "das Leben", "article": "das", "pos": "İsim (Nomen)", "turkish": "hayat"}
        # Doğrudan veritabanına küçük harfle isim kaydı simüle edelim
        self.db.set_cache("leben", bad_noun_data)
        # get_cache("leben") çağrıldığında bu hatalı kayıt reddedilmelidir
        cached = self.db.get_cache("leben")
        self.assertIsNone(cached, "Küçük harfli 'leben' sorgusunda isim önbelleği dönmemelidir")


class TestTranslatorPedagogyCaching(unittest.TestCase):
    """Çeviri motoru ve pedagoji önbellek entegrasyonu."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(db_path=Path(self.temp_dir.name) / "test_trans.db")
        self.engine = TranslationEngine(db=self.db)

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def test_analyze_grammar_pedagogy_hints_retained_in_cache(self):
        """analyze_grammar sonucu önbellekten alındığında pedagogy_hints korunmalıdır."""
        sentence = "Ich warte auf den Bus."
        mock_gemini_res = {
            "source": "gemini_grammar",
            "translation_tr": "Otobüsü bekliyorum.",
            "rule_notes": []
        }
        with patch.object(self.engine.gemini_service, "is_configured", return_value=True), \
             patch.object(self.engine.gemini_service, "analyze_sentence_grammar", return_value=mock_gemini_res):
            # İlk çağrı: Gemini API'den
            first_res = self.engine.analyze_grammar(sentence, focus_word="warte")
            self.assertIn("pedagogy_hints", first_res)

            # İkinci çağrı: Önbellekten dönmeli ve pedagogy_hints içermeli
            second_res = self.engine.analyze_grammar(sentence, focus_word="warte")
            self.assertTrue(second_res.get("from_cache"))
            self.assertIn("pedagogy_hints", second_res)


class TestHoverTrackerLogic(unittest.TestCase):
    """HoverTracker nokta eşleme ve bağlam cümlesi çıkarımı testleri."""

    def test_find_word_at_point_exact_and_padded(self):
        """_find_word_at_point önce kesin, sonra dolgulu kutu eşleştirmesini seçmelidir."""
        boxes = [
            {"x": 10, "y": 10, "w": 40, "h": 20, "text": "Hallo"},
            {"x": 60, "y": 10, "w": 40, "h": 20, "text": "Welt"},
        ]

        # 1. Kesin kutu içi
        b1 = _find_word_at_point(boxes, rel_x=20, rel_y=15)
        self.assertIsNotNone(b1)
        self.assertEqual(b1["text"], "Hallo")

        # 2. Dolgulu kutu içi (x=58, Welt'e daha yakın ve dolgu içinde)
        b2 = _find_word_at_point(boxes, rel_x=58, rel_y=15, pad_x=10, pad_y=10)
        self.assertIsNotNone(b2)
        self.assertEqual(b2["text"], "Welt")

        # 3. Yakınlık toleransı (70px mesafe)
        b3 = _find_word_at_point(boxes, rel_x=120, rel_y=20)
        self.assertIsNotNone(b3)
        self.assertEqual(b3["text"], "Welt")

        # 4. Çok uzak (200px mesafe) -> None
        b4 = _find_word_at_point(boxes, rel_x=300, rel_y=300)
        self.assertIsNone(b4)

    def test_extract_context_sentence_with_short_tokens(self):
        """_extract_context_sentence satırdaki kelimeleri birleştirmeli ve kısa belirteçleri korumalıdır."""
        boxes = [
            {"x": 10, "y": 10, "w": 20, "h": 15, "text": "3"},
            {"x": 35, "y": 12, "w": 10, "h": 15, "text": "à"},
            {"x": 50, "y": 10, "w": 30, "h": 15, "text": "Euro"},
        ]
        target = boxes[1]  # "à"
        sent = _extract_context_sentence(boxes, target)
        self.assertEqual(sent, "3 à Euro")


class TestGeminiServiceRetryAndQuota(unittest.TestCase):
    """GeminiService kota aşımı ve gecikme süresi ayrıştırma testleri."""

    def test_parse_retry_delay(self):
        svc = GeminiService("AIzaSyTestKey1234567890")

        # Header'dan okuma
        delay_hdr = svc._parse_retry_delay("", headers={"Retry-After": "45"})
        self.assertEqual(delay_hdr, 45.0)

        # Metin içerisinden saniye çıkarma
        delay_str = svc._parse_retry_delay("Please retry after 60s")
        self.assertEqual(delay_str, 60.0)

        # Sınırlandırma (clamping: 5.0 ile 120.0 arası)
        self.assertEqual(svc._parse_retry_delay("retry after 2s"), 5.0)
        self.assertEqual(svc._parse_retry_delay("retry after 300s"), 120.0)

    def test_parse_retry_delay_from_json_details(self):
        """Google API JSON hata gövdesindeki RetryInfo/retryDelay alanından süre doğru ayrıştırılmalıdır."""
        svc = GeminiService("AIzaSyTestKey1234567890")
        json_err = json.dumps({
            "error": {
                "code": 429,
                "message": "Resource has been exhausted",
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": "42s"
                    }
                ]
            }
        })
        delay = svc._parse_retry_delay(json_err)
        self.assertEqual(delay, 42.0)

    def test_quota_exhausted_pauses_calls(self):
        svc = GeminiService("AIzaSyTestKey1234567890")
        svc._mark_quota_exhausted(10.0)
        self.assertGreater(svc._quota_exhausted_until, time.monotonic())
        # Kota doluyken doğrudan çağrı yapılmamalı ve None dönmeli
        self.assertIsNone(svc._call_gemini_api("test"))


class TestHotkeyValidation(unittest.TestCase):
    """HotkeyManager tuş doğrulama testleri."""

    def test_standalone_function_keys_allowed(self):
        """F1..F12 tek başına kısayol olarak kabul edilmelidir."""
        for i in range(1, 13):
            valid, err = validate_hotkey_string(f"f{i}")
            self.assertTrue(valid, f"F{i} geçerli olmalıdır: {err}")

    def test_bare_modifiers_rejected(self):
        """Tek başına Alt, Ctrl, Shift geçerli olmamalıdır."""
        for mod in ("alt", "ctrl", "shift", "win"):
            valid, err = validate_hotkey_string(mod)
            self.assertFalse(valid)
            self.assertIn("Yalnızca değiştirici", err)

    def test_bare_letters_rejected(self):
        """Tek başına harf tuşları ('a', 'x' vb.) normal yazmayı bozacağı için reddedilmelidir."""
        valid, err = validate_hotkey_string("a")
        self.assertFalse(valid)
        self.assertIn("Harf, rakam veya boşluk", err)


class TestOCREngineBugFixes(unittest.TestCase):
    """OCREngine öznitelik başlatma ve öncelik fallback testleri."""

    def test_ocr_engine_initial_attributes(self):
        """OCREngine başlatıldığında _german_ocr_available ve _win_ocr_available None olmalıdır."""
        engine = OCREngine()
        self.assertIsNone(engine._german_ocr_available)
        self.assertIsNone(engine._win_ocr_available)

    def test_ocr_engine_tesseract_preferred_when_german_unsupported(self):
        """Almanca OCR desteklenmediğinde ve tesseract tanımlıysa auto modunda tesseract öncelikli çalışmalıdır."""
        from PIL import Image
        engine = OCREngine(preference="auto")
        engine.tesseract_cmd = "C:/mock/tesseract.exe"
        engine._german_ocr_available = False
        with patch.object(engine, "_recognize_with_tesseract", return_value="Hallo") as mock_tess, \
             patch.object(engine, "_recognize_with_windows_ocr") as mock_win:
            img = Image.new("RGB", (50, 50))
            res = engine.recognize_from_image(img)
            self.assertEqual(res, "Hallo")
            mock_tess.assert_called_once()
            mock_win.assert_not_called()


class TestPackagingAndDependencies(unittest.TestCase):
    """Paketleme ve bağımlılık temizliği testleri."""

    def test_requests_not_in_requirements(self):
        """requirements.txt dosyasında kullanılmayan requests bulunmamalıdır."""
        req_path = Path(__file__).resolve().parent.parent / "requirements.txt"
        content = req_path.read_text(encoding="utf-8")
        self.assertNotIn("requests", content.lower())

    def test_pil_imagegrab_in_spec_hiddenimports(self):
        """PyInstaller spec dosyasında PIL.ImageGrab bulunmalı ve requests bulunmamalıdır."""
        spec_path = Path(__file__).resolve().parent.parent / "packaging" / "ekran_sozlugu.spec"
        content = spec_path.read_text(encoding="utf-8")
        self.assertIn("'PIL.ImageGrab'", content)
        self.assertNotIn("'requests'", content)


if __name__ == "__main__":
    unittest.main()
