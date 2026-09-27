"""
Gemini Servisi Birim Testleri
"""
import unittest
from unittest.mock import patch, MagicMock
import urllib.error
import io
import json
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
        svc = GeminiService("AIzaSyTestKey12345", model="gemini-1.5-flash")
        self.assertEqual(svc.model, "gemini-1.5-flash")
        svc.set_model("gemini-2.0-flash")
        self.assertEqual(svc.model, "gemini-2.0-flash")

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


if __name__ == "__main__":
    unittest.main()
