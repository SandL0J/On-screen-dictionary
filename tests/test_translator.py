"""
Çeviri Motoru Birim Testleri
"""
import unittest
from unittest.mock import patch, MagicMock
import tempfile
import time
import urllib.error
from pathlib import Path
from app.database import Database
from app.translator import TranslationEngine
from app.gemini_service import GeminiService

import json
import threading
import gc

class TestTranslator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = Database(self.db_path)
        self.translator = TranslationEngine(db=self.db)

    def tearDown(self):
        self.translator = None
        self.db = None
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_translate_offline_word(self):
        res = self.translator.translate_and_analyze("Buch")
        self.assertEqual(res["article"], "das")
        self.assertIn("kitap", res["turkish"].lower())
        self.assertFalse(res["is_sentence"])

    @patch.object(TranslationEngine, "_fetch_wiktionary_info")
    @patch.object(TranslationEngine, "_translate_via_gt")
    def test_translate_online_word_with_caching(self, mock_gt, mock_wiki):
        mock_gt.return_value = {
            "translated_text": "sonuç",
            "detected_lang": "de",
            "dict_entries": [{"pos": "isim", "meanings": ["sonuç"]}]
        }
        mock_wiki.return_value = {"article": "das", "plural": "die Ergebnisse", "pos": "İsim (Nomen)"}

        # İlk çağrı: Mock GT ve Wiktionary üzerinden çevrilir ve önbelleğe yazılır
        res = self.translator.translate_and_analyze("Ergebnis")
        self.assertEqual(res["article"], "das")
        self.assertIn("sonuç", res["turkish"].lower())
        self.assertEqual(mock_gt.call_count, 1)

        # İkinci çağrıda önbellekten gelmeli, mock_gt tekrar çağrılmamalı
        res_cached = self.translator.translate_and_analyze("Ergebnis")
        self.assertTrue(res_cached.get("from_cache", False))
        self.assertEqual(mock_gt.call_count, 1)
        self.assertEqual(res_cached["turkish"], "sonuç")

    @patch.object(TranslationEngine, "_translate_via_gt")
    def test_translate_sentence(self, mock_gt):
        mock_gt.return_value = {
            "translated_text": "Bugün Almanca konuşmalıyız.",
            "detected_lang": "de",
            "dict_entries": []
        }
        sentence = "Wir müssen heute Deutsch sprechen."
        res = self.translator.translate_and_analyze(sentence)
        self.assertTrue(res["is_sentence"])
        self.assertEqual(res["turkish"], "Bugün Almanca konuşmalıyız.")
        self.assertFalse(res.get("offline_mode", False))
        self.assertTrue(len(res.get("grammar_notes", [])) > 0)

    @patch.object(TranslationEngine, "_translate_via_gt")
    def test_translate_german_sentence_to_turkish(self, mock_gt):
        # Almanca cümle Türkçe'ye çevrilmeli
        mock_gt.return_value = {
            "translated_text": "Eve gidiyorum",
            "detected_lang": "de",
            "dict_entries": []
        }
        res = self.translator.translate_and_analyze("Ich gehe nach Hause")
        self.assertEqual(res["direction"], "de_to_tr")
        self.assertTrue(res["is_sentence"])
        self.assertFalse(res.get("offline_mode", False))
        self.assertEqual(res["turkish"], "Eve gidiyorum")
        self.assertIn("ev", res["turkish"].lower())

    @patch.object(TranslationEngine, "_translate_via_gt")
    def test_translate_german_sentence_offline_fallback(self, mock_gt):
        # Ağ kesildiğinde hata fırlatmamalı, çevrimdışı zarif hata dönmeli
        mock_gt.side_effect = OSError("Ağ bağlantısı yok")
        res = self.translator.translate_and_analyze("Ich gehe nach Hause")
        self.assertEqual(res["direction"], "de_to_tr")
        self.assertTrue(res["is_sentence"])
        self.assertTrue(res.get("offline_mode", False))
        self.assertIn("Çeviri alınamadı", res["turkish"])

    @patch.object(TranslationEngine, "_translate_via_gt")
    def test_translate_german_verb(self, mock_gt):
        # Almanca fiil Türkçe'ye çevrilmeli
        mock_gt.return_value = {
            "translated_text": "çaprazlamak",
            "detected_lang": "de",
            "dict_entries": [{"pos": "fiil", "meanings": ["çaprazlamak"]}]
        }
        res = self.translator.translate_and_analyze("Kreuzen")
        self.assertEqual(res["direction"], "de_to_tr")
        self.assertEqual(res["turkish"], "çaprazlamak")
        self.assertNotEqual(res["turkish"].lower(), "kreuzen")

    @patch.object(GeminiService, "translate_and_analyze")
    def test_translate_direct_gemini_mode(self, mock_gemini_trans):
        mock_gemini_trans.return_value = {
            "original": "Hund",
            "german": "der Hund",
            "turkish": "köpek",
            "article": "der",
            "plural": "die Hunde",
            "pos": "isim",
            "is_sentence": False,
            "grammar_notes": [],
            "dict_entries": [{"pos": "isim", "meanings": ["köpek"]}],
            "examples": [],
            "direction": "de_to_tr",
            "detected_lang": "de",
            "source": "gemini_ai",
            "model_used": "gemini-3.5-flash-lite"
        }
        self.translator.set_gemini_key("AIzaSyValidKeyForTesting123")
        self.translator.set_gemini_options(use_direct=True, model="gemini-3.5-flash-lite")

        res = self.translator.translate_and_analyze("Hund")
        self.assertEqual(res["source"], "gemini_ai")
        self.assertEqual(res["turkish"], "köpek")
        self.assertEqual(res["article"], "der")
        mock_gemini_trans.assert_called_once()
        self.assertEqual(mock_gemini_trans.call_args[0][0], "Hund")
        self.assertIn("deadline", mock_gemini_trans.call_args.kwargs)

    def test_translate_deadline_strictly_bounded_on_slow_network(self):
        """Yavaş ağ ve zaman aşımlarında çeviri bütçesinin (azami +0.15s tolerans) aşılmadığını doğrular."""
        def slow_urlopen(req, timeout=None):
            sleep_time = min(timeout if timeout else 0.1, 0.1)
            time.sleep(sleep_time)
            raise urllib.error.URLError("Simulated slow network timeout")

        with patch("urllib.request.urlopen", side_effect=slow_urlopen):
            start = time.monotonic()
            res = self.translator.translate_and_analyze("Das ist ein sehr langes und schwieriges Beispiel.", timeout_budget=0.8)
            elapsed = time.monotonic() - start
            self.assertLessEqual(elapsed, 0.95, f"Çeviri zaman bütçesini aştı: {elapsed:.2f}s")
            self.assertIsNotNone(res)
            self.assertTrue(res.get("offline_mode") or "çeviri" in res.get("turkish", "").lower())

    def test_translate_deadline_with_slow_chunked_streaming_network(self):
        """Yerel HTTP sunucusu üzerinden gecikmeli ve parça parça gönderilen tam JSON gövdesiyle
        çeviri bütçesinin (budget + yumuşak tolerans) korunduğunu doğrular."""
        import http.server

        test_sentence = "Das ist ein komplexer deutscher Satz fuer den lokalen HTTP-Stream-Test."
        expected_tr = "Bu yerel HTTP akış testinden dönen çeviridir."
        full_json = json.dumps([
            [[expected_tr, test_sentence, None, None]],
            None,
            "de"
        ]).encode("utf-8")

        class SlowStreamingHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.server.request_count += 1
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(full_json)))
                self.end_headers()
                half = len(full_json) // 2
                self.wfile.write(full_json[:half])
                self.wfile.flush()
                time.sleep(0.08)  # Parçalar arası gerçek TCP soket gecikmesi
                try:
                    self.wfile.write(full_json[half:])
                    self.wfile.flush()
                except Exception:
                    pass

        server = http.server.HTTPServer(("127.0.0.1", 0), SlowStreamingHandler)
        server.request_count = 0
        port = server.server_address[1]
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()

        # Özyinelemeyi engellemek için urllib.request.urlopen'ın orijinal fonksiyonunu patch'ten önce sakla
        original_urlopen = urllib.request.urlopen

        def redirect_urlopen(req, *args, **kwargs):
            # İstekleri yerel HTTP sunucusuna yönlendirirken orijinal urlopen'ı kullan
            local_url = f"http://127.0.0.1:{port}/translate_a/single"
            headers = getattr(req, "headers", {})
            new_req = urllib.request.Request(local_url, headers=headers)
            return original_urlopen(new_req, *args, **kwargs)

        try:
            with patch("urllib.request.urlopen", side_effect=redirect_urlopen):
                start = time.monotonic()
                budget = 0.8
                res = self.translator.translate_and_analyze(test_sentence, timeout_budget=budget)
                elapsed = time.monotonic() - start

                # 1. Yerel sunucuya ulaşan istek sayısını doğrula (çevrimdışı sözlükten dönmediğini kanıtlar)
                self.assertGreaterEqual(server.request_count, 1, "Yerel HTTP sunucusuna istek ulaşmalıdır!")

                # 2. Çevirinin yerel HTTP sunucusunun döndürdüğü yanıttan geldiğini doğrula
                self.assertIsNotNone(res)
                self.assertIn("yerel http akış testinden", res.get("turkish", "").lower())

                # 3. Soketteki parçalı gecikmenin gerçekten beklendiğini doğrula
                self.assertGreaterEqual(elapsed, 0.08, f"Soket gecikmesi ({elapsed:.3f}s) beklenmedi!")

                # 4. Toplam sürenin bütçe + yumuşak tolerans (azami 0.25s) sınırında kaldığını doğrula
                self.assertLessEqual(elapsed, budget + 0.25, f"Akış yanıtında zaman bütçesi aşıldı: {elapsed:.2f}s")
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=1.0)

    @patch.object(GeminiService, "translate_and_analyze")
    def test_translate_direct_gemini_fallback(self, mock_gemini_trans):
        # Gemini hata verirse otomatik olarak yerel / standart motora geçmeli
        mock_gemini_trans.side_effect = Exception("API connection timeout")
        self.translator.set_gemini_key("AIzaSyValidKeyForTesting123")
        self.translator.set_gemini_options(use_direct=True, model="gemini-3.5-flash-lite")

        res = self.translator.translate_and_analyze("Buch")
        self.assertIsNotNone(res)
        self.assertEqual(res["article"], "das")
        self.assertIn("kitap", res["turkish"].lower())

    def test_empty_input(self):
        res = self.translator.translate_and_analyze("")
        self.assertIn("error", res)


if __name__ == "__main__":
    unittest.main()
