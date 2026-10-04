"""
Gemini Servisi Birim Testleri
"""
import unittest
from unittest.mock import patch, MagicMock
import urllib.error
import io
import json
import time
from app.gemini_service import GeminiService


class TestGeminiService(unittest.TestCase):
    def test_configuration(self):
        svc = GeminiService("")
        self.assertFalse(svc.is_configured())

        svc.set_api_key("short")
        self.assertFalse(svc.is_configured())

        svc.set_api_key("AIzaSyValidLengthKey1234567890")
        self.assertTrue(svc.is_configured())

    def test_empty_key_connection_test(self):
        svc = GeminiService("")
        ok, msg = svc.test_connection("")
        self.assertFalse(ok)
        self.assertIn("Lütfen önce", msg)

    @patch("urllib.request.urlopen")
    def test_successful_connection(self, mock_urlopen):
        # 200 OK yanıt simülasyonu
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"models": [{"name": "models/gemini-1.5-flash"}, {"name": "models/gemini-pro"}]}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        svc = GeminiService("AIzaSyTestKey12345")
        ok, msg = svc.test_connection()
        self.assertTrue(ok)
        self.assertIn("Başarılı", msg)
        self.assertIn("2 model", msg)

    @patch("urllib.request.urlopen")
    def test_invalid_key_connection(self, mock_urlopen):
        # 400 Bad Request (geçersiz anahtar)
        err = urllib.error.HTTPError(
            url="https://generativelanguage.googleapis.com",
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=io.BytesIO(b'{"error": {"message": "API key not valid"}}')
        )
        mock_urlopen.side_effect = err

        svc = GeminiService("AIzaSyInvalidKey")
        ok, msg = svc.test_connection()
        self.assertFalse(ok)
        self.assertIn("Geçersiz", msg)

    @patch("urllib.request.urlopen")
    def test_network_error(self, mock_urlopen):
        # URLError (internet yok)
        mock_urlopen.side_effect = urllib.error.URLError("DNS resolution failed")

        svc = GeminiService("AIzaSyValidKeyFormat")
        ok, msg = svc.test_connection()
        self.assertFalse(ok)
        self.assertIn("Bağlantı Kurulamadı", msg)

    def test_model_selection(self):
        default_svc = GeminiService("AIzaSyTestKey12345")
        self.assertEqual(default_svc.model, "gemini-3.5-flash-lite")
        svc = GeminiService("AIzaSyTestKey12345", model="gemini-3.5-flash-lite")
        self.assertEqual(svc.model, "gemini-3.5-flash-lite")
        svc.set_model("gemini-3.8-flash")
        self.assertEqual(svc.model, "gemini-3.8-flash")

    @patch("urllib.request.urlopen")
    def test_translate_and_analyze_success(self, mock_urlopen):
        mock_payload = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": json.dumps({
                            "direction": "de_to_tr",
                            "detected_lang": "de",
                            "german": "das Buch",
                            "turkish": "kitap",
                            "article": "das",
                            "plural": "die Bücher",
                            "pos": "isim",
                            "is_sentence": False,
                            "rule_note": "Buch tekil nötr bir isimdir ve 'das' artikelini alır.",
                            "examples": [{"de": "Ich lese ein Buch.", "tr": "Bir kitap okuyorum."}]
                        })
                    }]
                }
            }]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        svc = GeminiService("AIzaSyTestKey12345")
        res = svc.translate_and_analyze("Buch")
        self.assertIsNotNone(res)
        self.assertEqual(res["article"], "das")
        self.assertEqual(res["turkish"], "kitap")
        self.assertEqual(res["plural"], "die Bücher")
        self.assertEqual(res["direction"], "de_to_tr")
        self.assertEqual(res["source"], "gemini_ai")
        self.assertEqual(len(res["grammar_notes"]), 1)
        self.assertEqual(len(res["examples"]), 1)

    def test_translate_and_analyze_unconfigured(self):
        svc = GeminiService("")
        res = svc.translate_and_analyze("Buch")
        self.assertIsNone(res)

    @patch("urllib.request.urlopen")
    def test_call_gemini_api_respects_deadline(self, mock_urlopen):
        """Zaman bütçesi dolduğunda model deneme döngüsünün kesildiğini doğrular."""
        # İlk çağrıda 503 HTTP hatası dönsün
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "url", 503, "Service Unavailable", {}, io.BytesIO(b'{"error":{"message":"overloaded"}}')
        )
        svc = GeminiService("AIzaSyTestKey12345")
        # Süresi dolmuş veya dolmak üzere olan deadline
        expired_deadline = time.monotonic() + 0.05
        res = svc._call_gemini_api("test", deadline=expired_deadline)
        self.assertIsNone(res)
        # Sadece 1 model denendikten sonra süre bittiği için döngüden çıkmalı, tüm modellere istek yapmamalı
        self.assertLessEqual(mock_urlopen.call_count, 1)

    @patch("urllib.request.urlopen")
    def test_generate_explanation_respects_deadline(self, mock_urlopen):
        """Açıklama üretiminde deadline parametresinin aktarıldığını doğrular."""
        mock_payload = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Grammar explanation note."}]
                }
            }]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        svc = GeminiService("AIzaSyTestKey12345")
        deadline = time.monotonic() + 3.0
        res = svc.generate_explanation("laufen", deadline=deadline)
        self.assertEqual(res, "Grammar explanation note.")
        self.assertTrue(mock_urlopen.called)


if __name__ == "__main__":
    unittest.main()
