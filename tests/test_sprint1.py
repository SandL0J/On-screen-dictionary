"""
Birim testleri: Sprint 1 İyileştirmeleri ve Güvenlik Doğrulamaları
- Gemini API anahtarının URL yerine x-goog-api-key başlığında gönderilmesi ve loglarda maskelenmesi
- Database history_limit sınırı ve yalnızca ekleme sırasında budama (wordbook ve cache dokunulmazlığı)
- MainOverlay _onboarding_after_id ve bekleyen timer iptalleri (Tcl hatasız temiz kapanış)
- MainOverlay lookup_generation yarışı engelleme (eski yanıtların yeni aramaların üzerine yazmaması)
- Pano gizlilik varsayılanı (False), kullanıcı tercihinin korunması ve model normalizasyonu
"""
import io
import json
import os
import shutil
import tempfile
import threading
import time
import tkinter as tk
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.config import DEFAULT_CONFIG, load_config, save_config
from app.database import Database
from app.gemini_service import GeminiService, SUPPORTED_MODELS
from app.gui.main_overlay import MainOverlay
from app.ocr_engine import OCREngine
from app.translator import TranslationEngine
from app.clipboard_watcher import ClipboardWatcher


class TestGeminiSecurityAndErrors(unittest.TestCase):
    def setUp(self):
        self.api_key = "AIzaSyFakeSecretKeySprint1_9876543210"
        self.service = GeminiService(api_key=self.api_key, model="gemini-3.5-flash-lite")

    @patch("urllib.request.urlopen")
    def test_gemini_calls_use_header_not_query_param(self, mock_urlopen):
        """API çağrısında anahtar URL query parametresinde değil, x-goog-api-key başlığında gönderilmelidir."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "candidates": [{
                "content": {
                    "parts": [{"text": "{\"turkish\": \"ev\", \"article\": \"das\", \"plural\": \"die Häuser\"}"}]
                }
            }]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        result = self.service.translate_and_analyze("Haus")
        self.assertIsNotNone(result)

        # urllib.request.Request nesnesini kontrol et
        args, kwargs = mock_urlopen.call_args
        req = args[0]
        self.assertNotIn("?key=", req.full_url)
        self.assertNotIn(self.api_key, req.full_url)
        self.assertEqual(req.headers.get("X-goog-api-key"), self.api_key)

    @patch("urllib.request.urlopen")
    def test_test_connection_masks_key_in_errors(self, mock_urlopen):
        """test_connection hata aldığında hata metninde gerçek anahtar asla yer almamalıdır."""
        fake_url = "https://generativelanguage.googleapis.com/v1beta/models"
        # 1. HTTP 500 ve hata gövdesinde anahtar varsa maskelenmeli
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url=fake_url,
            code=500,
            msg="Server Error",
            hdrs={},
            fp=io.BytesIO(f'{{"error": {{"message": "API key {self.api_key} failed"}}}}'.encode("utf-8"))
        )

        ok, msg = self.service.test_connection(self.api_key)
        self.assertFalse(ok)
        self.assertNotIn(self.api_key, msg)
        self.assertIn("[GİZLENDİ]", msg)

        # 2. Beklenmeyen bir Exception içinde anahtar varsa maskelenmeli
        mock_urlopen.side_effect = Exception(f"Socket connection error for key {self.api_key}")
        ok2, msg2 = self.service.test_connection(self.api_key)
        self.assertFalse(ok2)
        self.assertNotIn(self.api_key, msg2)
        self.assertIn("[GİZLENDİ]", msg2)

    @patch("urllib.request.urlopen")
    def test_http_error_status_codes_graceful_handling(self, mock_urlopen):
        """401, 429 ve 500 HTTP hatalarında translate_and_analyze() çökmemeli ve None/güvenli dönmelidir."""
        for code, err_msg in [(401, "Unauthorized"), (429, "Too Many Requests"), (500, "Internal Server Error")]:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                url="https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent",
                code=code,
                msg=err_msg,
                hdrs={},
                fp=io.BytesIO(b'{"error": {"message": "Service unavailable"}}')
            )
            res = self.service.translate_and_analyze("Wasser")
            self.assertIsNone(res, f"HTTP {code} durumunda translate_and_analyze None döndürmelidir.")


class TestDatabaseHistoryLimit(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_hist.db"
        self.db = Database(self.db_path, history_limit=5)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_history_limit_pruned_only_on_insert(self):
        """Geçmiş sınırı aşıldığında sadece en eski kayıtlar budanmalıdır."""
        # 10 adet geçmiş kaydı ekle
        for i in range(10):
            self.db.add_history(f"kelime_{i}", {"turkish": f"anlam_{i}"})

        history = self.db.get_recent_history(limit=50)
        self.assertEqual(len(history), 5)
        # En son eklenen kelimeler kalmalı: kelime_9, kelime_8, kelime_7, kelime_6, kelime_5
        stored_words = [row["query_text"] for row in history]
        self.assertEqual(stored_words, ["kelime_9", "kelime_8", "kelime_7", "kelime_6", "kelime_5"])

    def test_history_limit_does_not_prune_on_init(self):
        """Veritabanı başlatılırken (init) geçmiş tablosu silinmemeli/budanmamalıdır."""
        for i in range(8):
            self.db.add_history(f"eski_{i}", {"turkish": f"anlam_{i}"})

        # history_limit=3 olan yeni bir Database örneği aç (mevcut DB dosyası üzerinde)
        new_db = Database(self.db_path, history_limit=3)
        # Henüz yeni insert yapılmadığı için 5 kayıt aynen korunmalı (önceki db'nin limiti 5 idi)
        history_before = new_db.get_recent_history(limit=50)
        self.assertEqual(len(history_before), 5)

        # Yeni bir kayıt eklendiğinde yeni limit (3) devreye girmeli
        new_db.add_history("yeni_kelime", {"turkish": "yeni_anlam"})
        history_after = new_db.get_recent_history(limit=50)
        self.assertEqual(len(history_after), 3)
        self.assertEqual(history_after[0]["query_text"], "yeni_kelime")

    def test_wordbook_and_cache_are_never_pruned_by_history_limit(self):
        """Geçmiş budaması wordbook veya cache tablolarına ASLA dokunmamalıdır."""
        # Deftere ve önbelleğe veri ekle
        self.db.add_word(german="Baum", turkish="ağaç", article="der")
        self.db.set_cache("Baum", {"turkish": "ağaç", "article": "der"})

        # Geçmişi doldurup taşıralım
        for i in range(20):
            self.db.add_history(f"temp_{i}", {"turkish": f"anlam_{i}"})

        # wordbook ve cache aynen durmalı
        word = self.db.get_word_by_german("Baum")
        self.assertIsNotNone(word)
        self.assertEqual(word["turkish"], "ağaç")

        cached = self.db.get_cache("Baum")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["turkish"], "ağaç")


class TestMainOverlayLifecycleAndGenerations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
            cls.tk_available = True
        except Exception:
            cls.tk_available = False

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "tk_available", False) and cls.root:
            try:
                cls.root.destroy()
            except Exception:
                pass

    def setUp(self):
        if not getattr(self, "tk_available", False):
            self.skipTest("Tkinter mevcut değil")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_overlay.db"
        self.db = Database(self.db_path)
        self.ocr = OCREngine()
        self.translator = TranslationEngine(db=self.db)
        self.watcher = ClipboardWatcher(on_text_detected=lambda t: None)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass
        if getattr(self, "tk_available", False) and self.root:
            for child in list(self.root.winfo_children()):
                try:
                    child.destroy()
                except Exception:
                    pass
            try:
                self.root.update()
            except Exception:
                pass

    @patch("app.hover_tracker.HoverTracker.start")
    @patch("app.hotkey_manager.HotkeyManager.start")
    def test_overlay_stop_cancels_onboarding_and_after_ids(self, mock_hotkey_start, mock_hover_start):
        """stop() çağrıldığında _onboarding_after_id ve bekleyen timerlar iptal edilmeli, Tcl hatası olmamalıdır."""
        config = {
            "first_run_completed": False,
            "clipboard_auto_lookup": False
        }
        overlay = MainOverlay(
            root=self.root,
            translator=self.translator,
            ocr_engine=self.ocr,
            db=self.db,
            clipboard_watcher=self.watcher,
            config=config
        )

        # _onboarding_after_id tanımlı olmalı
        self.assertIsNotNone(overlay._onboarding_after_id)

        # overlay.stop() çağır
        overlay.stop()
        self.assertIsNone(overlay._onboarding_after_id)
        self.assertEqual(len(overlay._after_ids), 0)

        # root update edildiğinde Tcl 'invalid command name' hatası oluşmamalıdır
        try:
            self.root.update()
        except Exception as e:
            self.fail(f"root.update() hata fırlattı: {e}")

    @patch("app.hover_tracker.HoverTracker.start")
    @patch("app.hotkey_manager.HotkeyManager.start")
    def test_lookup_generation_discards_stale_results(self, mock_hotkey_start, mock_hover_start):
        """Eski (yavaş) bir arama tamamlandığında, daha yeni başlatılan bir aramanın üzerine yazmamalıdır."""
        overlay = MainOverlay(
            root=self.root,
            translator=self.translator,
            ocr_engine=self.ocr,
            db=self.db,
            clipboard_watcher=self.watcher,
            config={"first_run_completed": True, "clipboard_auto_lookup": False}
        )
        try:
            req1_started = threading.Event()
            req1_proceed = threading.Event()
            req2_started = threading.Event()
            req2_proceed = threading.Event()

            hud_calls = []
            executing_threads = []

            def mock_translate_and_analyze(query):
                if query == "yavas":
                    req1_started.set()
                    req1_proceed.wait(timeout=3.0)
                    return {"turkish": "eski_anlam", "original": "yavas"}
                elif query == "hizli":
                    req2_started.set()
                    req2_proceed.wait(timeout=3.0)
                    return {"turkish": "yeni_anlam", "original": "hizli"}
                return {"turkish": "diger", "original": query}

            def mock_show_hud(result_data):
                executing_threads.append(threading.current_thread().ident)
                hud_calls.append(result_data)

            self.translator.translate_and_analyze = mock_translate_and_analyze
            overlay._show_hud = mock_show_hud

            # 1. İstek (yavaş) önce başlatılır
            t1 = overlay.lookup_text("yavas")
            self.assertTrue(req1_started.wait(timeout=2.0), "1. istek başlatılamadı")

            # 2. İstek (hızlı) hemen sonra başlatılır
            t2 = overlay.lookup_text("hizli")
            self.assertTrue(req2_started.wait(timeout=2.0), "2. istek başlatılamadı")

            # Tamamlama sırasını tersine çevir: 2. isteğin (hızlı) 1. istekten önce bitmesini sağla
            req2_proceed.set()
            t2.join(timeout=2.0)
            self.assertFalse(t2.is_alive())

            # Tk ana iş parçacığında kuyruğu tüket ve UI'yı güncelle
            overlay._poll_ui_queue()
            self.root.update()

            # Şimdi 1. isteğin (yavaş) tamamlanmasına izin ver
            req1_proceed.set()
            t1.join(timeout=2.0)
            self.assertFalse(t1.is_alive())

            # Tk ana iş parçacığında kuyruğu tekrar tüket ve UI'yı güncelle
            overlay._poll_ui_queue()
            self.root.update()

            # Doğrulamalar:
            # 1. Yalnızca yeni sonucun (2. istek - hizli) gösterildiğini doğrula
            self.assertEqual(len(hud_calls), 1)
            self.assertEqual(hud_calls[0]["original"], "hizli")
            self.assertEqual(hud_calls[0]["turkish"], "yeni_anlam")

            # 2. Geri çağırmanın YALNIZCA Tk ana iş parçacığında çalıştığını doğrula
            main_thread_id = threading.main_thread().ident
            self.assertEqual(len(executing_threads), 1)
            self.assertEqual(executing_threads[0], main_thread_id)

        finally:
            overlay.stop()

    @patch("app.hover_tracker.HoverTracker.start")
    @patch("app.hotkey_manager.HotkeyManager.start")
    def test_overlay_post_to_ui_stop_and_update_has_no_tcl_error_or_lingering_timers(self, mock_hotkey_start, mock_hover_start):
        """MainOverlay kurulup UI görevi çalıştırıldıktan sonra stop() ve root.update() çağrıldığında Tcl hatası ve bekleyen timer kalmamalıdır."""
        import io
        import sys

        config = {
            "first_run_completed": False,  # Onboarding zamanlayıcısını da dahil ederek sızıntı kontrolü yap
            "clipboard_auto_lookup": False
        }
        overlay = MainOverlay(
            root=self.root,
            translator=self.translator,
            ocr_engine=self.ocr,
            db=self.db,
            clipboard_watcher=self.watcher,
            config=config
        )

        # Poller ve onboarding zamanlayıcılarının kurulduğunu doğrula
        self.assertIsNotNone(overlay._ui_poll_id)
        self.assertIsNotNone(overlay._onboarding_after_id)
        self.assertIn(overlay._ui_poll_id, overlay._after_ids)
        self.assertIn(overlay._onboarding_after_id, overlay._after_ids)

        executed = []
        overlay.post_to_ui(lambda: executed.append("task_executed"))

        # Kuyruğu doğrudan manuel işle (eski poller timer'ını iptal edip yenisini kurar)
        overlay._poll_ui_queue()
        self.assertEqual(executed, ["task_executed"])

        # overlay.stop() çağır
        overlay.stop()

        # Doğrula: Tüm zamanlayıcılar iptal edilmiş ve kayıtlar temizlenmiş olmalı
        self.assertIsNone(overlay._ui_poll_id)
        self.assertIsNone(overlay._onboarding_after_id)
        self.assertEqual(len(overlay._after_ids), 0)

        # Stderr çıktısını yakalayarak Tcl 'invalid command name' uyarısı üretilmediğini doğrula
        stderr_capture = io.StringIO()
        old_stderr = sys.stderr
        try:
            sys.stderr = stderr_capture
            self.root.update()
            self.root.update_idletasks()
        finally:
            sys.stderr = old_stderr

        captured_output = stderr_capture.getvalue()
        self.assertNotIn("invalid command name", captured_output)

    @patch("app.hover_tracker.HoverTracker.start")
    @patch("app.hotkey_manager.HotkeyManager.start")
    def test_overlay_repeated_create_stop_cycles(self, mock_hotkey_start, mock_hover_start):
        """Tekrarlanan MainOverlay kur/durdur döngülerinde Tcl invalid command uyarısı ve bekleyen timer sızıntısı olmamalıdır."""
        import io
        import sys

        stderr_capture = io.StringIO()
        old_stderr = sys.stderr
        try:
            sys.stderr = stderr_capture

            for cycle in range(5):
                cfg = {
                    "first_run_completed": (cycle % 2 == 0),
                    "clipboard_auto_lookup": False
                }
                overlay = MainOverlay(
                    root=self.root,
                    translator=self.translator,
                    ocr_engine=self.ocr,
                    db=self.db,
                    clipboard_watcher=self.watcher,
                    config=cfg
                )

                task_results = []
                overlay.post_to_ui(lambda c=cycle: task_results.append(c))
                overlay._poll_ui_queue()
                self.assertEqual(task_results, [cycle])

                overlay.stop()
                self.assertEqual(len(overlay._after_ids), 0)
                self.assertIsNone(overlay._ui_poll_id)

                self.root.update()
                self.root.update_idletasks()

                for child in list(self.root.winfo_children()):
                    try:
                        child.destroy()
                    except Exception:
                        pass
                self.root.update()

        finally:
            sys.stderr = old_stderr

        captured_output = stderr_capture.getvalue()
        self.assertNotIn("invalid command name", captured_output)


class TestConfigPrivacyAndNormalization(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.json"

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_default_config_clipboard_is_false_and_model_is_3_5_flash_lite(self):
        """Varsayılan ayarlarda pano dinleme False ve model gemini-3.5-flash-lite olmalıdır."""
        self.assertFalse(DEFAULT_CONFIG["clipboard_auto_lookup"])
        self.assertEqual(DEFAULT_CONFIG["gemini_model"], "gemini-3.5-flash-lite")
        self.assertIn("gemini-3.5-flash-lite", [m[0] for m in SUPPORTED_MODELS])
        self.assertIn("gemini-3.8-flash", [m[0] for m in SUPPORTED_MODELS])
        self.assertIn("gemini-3.5-flash", [m[0] for m in SUPPORTED_MODELS])

    def test_load_config_preserves_explicit_user_clipboard_true(self):
        """Kullanıcının config.json dosyasında önceden True yaptığı ayar ve geçerli modeller ezilmemelidir."""
        user_cfg = {
            "clipboard_auto_lookup": True,
            "gemini_model": "gemini-3.8-flash"
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(user_cfg, f)

        loaded = load_config(self.config_path)
        self.assertTrue(loaded["clipboard_auto_lookup"])
        self.assertEqual(loaded["gemini_model"], "gemini-3.8-flash")

    def test_load_config_normalizes_outdated_models(self):
        """Eski veya kapatılmış modeller gemini-3.5-flash-lite'a normalize edilmeli; 3.1-flash-lite ve 2.5 korunmalıdır."""
        # 1. Kapatılmış gemini-2.0-flash normalize edilmeli
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump({"gemini_model": "gemini-2.0-flash"}, f)
        loaded = load_config(self.config_path)
        self.assertEqual(loaded["gemini_model"], "gemini-3.5-flash-lite")

        # 2. Kapatılmış gemini-1.5-flash normalize edilmeli
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump({"gemini_model": "gemini-1.5-flash"}, f)
        loaded = load_config(self.config_path)
        self.assertEqual(loaded["gemini_model"], "gemini-3.5-flash-lite")

        # 3. Geçerli gemini-3.1-flash-lite korunmalı (2.5'e veya başkasına zorlanmamalı)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump({"gemini_model": "gemini-3.1-flash-lite"}, f)
        loaded = load_config(self.config_path)
        self.assertEqual(loaded["gemini_model"], "gemini-3.1-flash-lite")

        # 4. Mevcut kullanıcı tercihi gemini-2.5-flash korunmalı
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump({"gemini_model": "gemini-2.5-flash"}, f)
        loaded = load_config(self.config_path)
        self.assertEqual(loaded["gemini_model"], "gemini-2.5-flash")

        # 5. gemini-flash-latest takma adı (alias) gemini-3.5-flash'a normalize edilmeli
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump({"gemini_model": "gemini-flash-latest"}, f)
        loaded = load_config(self.config_path)
        self.assertEqual(loaded["gemini_model"], "gemini-3.5-flash")


class TestThreadSafeUiDispatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except Exception:
            cls.root = None

    @classmethod
    def tearDownClass(cls):
        if cls.root:
            try:
                cls.root.destroy()
            except Exception:
                pass

    def setUp(self):
        if not self.root:
            self.skipTest("Tkinter root initialization unavailable")
        self.db = MagicMock()
        self.ocr = MagicMock()
        self.translator = MagicMock()
        self.watcher = MagicMock()

    @patch("app.hover_tracker.HoverTracker.start")
    @patch("app.hotkey_manager.HotkeyManager.start")
    def test_hotkey_callbacks_dispatch_via_queue(self, mock_hotkey_start, mock_hover_start):
        """HotkeyManager geri çağrımları doğrudan Tk çağırmamalı, kuyruk üzerinden aktarılmalıdır."""
        overlay = MainOverlay(
            root=self.root,
            translator=self.translator,
            ocr_engine=self.ocr,
            db=self.db,
            clipboard_watcher=self.watcher,
            config={"first_run_completed": True, "clipboard_auto_lookup": False}
        )
        try:
            binding = overlay.hotkey_mgr._bindings.get("ocr")
            self.assertIsNotNone(binding)
            ocr_cb = binding.callback
            self.assertIsNotNone(ocr_cb)

            executed_threads = []
            overlay._trigger_ocr_hotkey = lambda: executed_threads.append(threading.current_thread().ident)

            # Arka plan iş parçacığından kısayol callback'ini tetikle
            t = threading.Thread(target=ocr_cb)
            t.start()
            t.join(timeout=1.0)

            # Kuyrukta 1 iş olmalı, henüz çalıştırılmamış olmalı (çünkü Tk ana iş parçacığında poll edilmedi)
            self.assertEqual(overlay._ui_queue.qsize(), 1)
            self.assertEqual(len(executed_threads), 0)

            # Şimdi Tk ana iş parçacığında kuyruğu tüket
            overlay._poll_ui_queue()
            self.assertEqual(len(executed_threads), 1)
            self.assertEqual(executed_threads[0], threading.main_thread().ident)
        finally:
            overlay.stop()

    @patch("app.hover_tracker.HoverTracker.start")
    @patch("app.hotkey_manager.HotkeyManager.start")
    def test_clipboard_callback_dispatch_via_post_to_ui(self, mock_hotkey_start, mock_hover_start):
        """Clipboard callback'i overlay.post_to_ui ile kuyruğa alınmalı ve Tk ana iş parçacığında çalışmalıdır."""
        overlay = MainOverlay(
            root=self.root,
            translator=self.translator,
            ocr_engine=self.ocr,
            db=self.db,
            clipboard_watcher=self.watcher,
            config={"first_run_completed": True, "clipboard_auto_lookup": False}
        )
        try:
            executed_threads = []
            received_texts = []
            overlay.lookup_text = lambda txt: (executed_threads.append(threading.current_thread().ident), received_texts.append(txt))

            def on_clipboard_text(text: str):
                overlay.post_to_ui(overlay.lookup_text, text)

            # Arka plan thread'inden panodan metin geldiğini simüle et
            bg_thread = threading.Thread(target=lambda: on_clipboard_text("Guten Morgen"))
            bg_thread.start()
            bg_thread.join(timeout=1.0)

            self.assertEqual(overlay._ui_queue.qsize(), 1)
            self.assertEqual(len(executed_threads), 0)

            # Ana iş parçacığında poll et
            overlay._poll_ui_queue()
            self.assertEqual(len(executed_threads), 1)
            self.assertEqual(executed_threads[0], threading.main_thread().ident)
            self.assertEqual(received_texts, ["Guten Morgen"])
        finally:
            overlay.stop()

    def test_tray_manager_tk_call_uses_post_to_ui(self):
        """TrayManager _tk_call, post_to_ui sağlandığında doğrudan Tk çağırmadan kuyruğa iletmelidir."""
        from app.tray_manager import TrayManager
        ui_queue = []
        def mock_post_to_ui(fn):
            ui_queue.append(fn)

        tray = TrayManager(
            on_show=MagicMock(),
            on_hide=MagicMock(),
            on_open_settings=MagicMock(),
            on_quit=MagicMock(),
            root=self.root,
            post_to_ui=mock_post_to_ui
        )

        called = []
        # Arka plan thread'inden _tk_call çağır
        bg_thread = threading.Thread(target=lambda: tray._tk_call(lambda: called.append("done")))
        bg_thread.start()
        bg_thread.join(timeout=1.0)

        # Doğrudan çağrılmadı, kuyruğa aktarıldı
        self.assertEqual(len(called), 0)
        self.assertEqual(len(ui_queue), 1)

        # Kuyruktaki görev çalıştırılınca çağrılmalı
        ui_queue[0]()
        self.assertEqual(called, ["done"])

    def test_snipper_worker_dispatches_via_post_to_ui(self):
        """ScreenSnipper OCR bittiğinde sonucu post_to_ui ile Tk ana iş parçacığına aktarmalıdır."""
        from app.gui.snipper import ScreenSnipper
        ui_queue = []
        def mock_post_to_ui(fn):
            ui_queue.append(fn)

        ocr_engine = MagicMock()
        ocr_engine.recognize_from_image.return_value = "Apfel"

        extracted = []
        snipper = ScreenSnipper(
            root=self.root,
            ocr_engine=ocr_engine,
            on_text_extracted=lambda t: extracted.append(t),
            post_to_ui=mock_post_to_ui
        )

        canvas = MagicMock()
        canvas.winfo_width.return_value = 100
        canvas.winfo_height.return_value = 50
        snipper.canvas = canvas
        snipper.start_x = 10
        snipper.start_y = 10

        with patch("app.gui.snipper.capture_screen_rect_gdi", return_value=MagicMock()):
            snipper._on_button_release(MagicMock(x=60, y=40))
            time.sleep(0.3)

        self.assertGreaterEqual(len(ui_queue), 1)
        ui_queue[0]()
        self.assertEqual(extracted, ["Apfel"])

    def test_tray_manager_worker_without_dispatcher_rejects_without_tk(self):
        """post_to_ui olmadan worker thread'den çağrıldığında TrayManager Tk çağırmadan güvenle reddetmelidir."""
        from app.tray_manager import TrayManager
        mock_root = MagicMock()
        tray = TrayManager(
            on_show=MagicMock(),
            on_hide=MagicMock(),
            on_open_settings=MagicMock(),
            on_quit=MagicMock(),
            root=mock_root,
            post_to_ui=None
        )

        called = []
        bg_thread = threading.Thread(target=lambda: tray._tk_call(lambda: called.append("ran")))
        bg_thread.start()
        bg_thread.join(timeout=1.0)

        self.assertEqual(len(called), 0)
        self.assertEqual(mock_root.after.call_count, 0)
        self.assertEqual(mock_root.winfo_exists.call_count, 0)

    def test_snipper_worker_without_dispatcher_rejects_without_tk(self):
        """post_to_ui olmadan worker thread'den çağrıldığında ScreenSnipper Tk çağırmadan güvenle reddetmelidir."""
        from app.gui.snipper import ScreenSnipper
        mock_root = MagicMock()
        snipper = ScreenSnipper(
            root=mock_root,
            ocr_engine=MagicMock(),
            on_text_extracted=MagicMock(),
            post_to_ui=None
        )

        called = []
        bg_thread = threading.Thread(target=lambda: snipper._dispatch_to_ui(lambda: called.append("ran")))
        bg_thread.start()
        bg_thread.join(timeout=1.0)

        self.assertEqual(len(called), 0)
        self.assertEqual(mock_root.after.call_count, 0)
        self.assertEqual(mock_root.winfo_exists.call_count, 0)

    def test_hover_tooltip_worker_without_dispatcher_rejects_without_tk(self):
        """post_to_ui olmadan worker thread'den çağrıldığında HoverTooltip Tk metodlarına dokunmadan reddetmelidir."""
        from app.gui.hover_tooltip import HoverTooltip
        tooltip = HoverTooltip(
            root=self.root,
            db=MagicMock(),
            post_to_ui=None
        )
        mock_root = MagicMock()
        mock_window = MagicMock()
        tooltip.root = mock_root
        tooltip.window = mock_window

        # Arka plandan show, hide, show_loading, show_message, _cancel_auto_hide çağır
        def worker_actions():
            tooltip.show({"german": "Buch", "turkish": "kitap"}, 100, 100)
            tooltip.show_loading(100, 100)
            tooltip.show_message(100, 100, "Uyarı")
            tooltip.hide()
            tooltip._cancel_auto_hide()

        bg_thread = threading.Thread(target=worker_actions)
        bg_thread.start()
        bg_thread.join(timeout=1.0)

        # Hiçbir Tk methodu çağrılmamalı
        self.assertEqual(mock_root.after.call_count, 0)
        self.assertEqual(mock_root.after_cancel.call_count, 0)
        self.assertEqual(mock_window.geometry.call_count, 0)
        self.assertEqual(mock_window.deiconify.call_count, 0)
        self.assertEqual(mock_window.withdraw.call_count, 0)

    def test_hover_tooltip_worker_dispatches_to_post_to_ui_and_executes_on_main(self):
        """Worker thread'den çağrılan HoverTooltip.show, post_to_ui üzerinden aktarılmalı ve Tk ana iş parçacığında çalışmalıdır."""
        from app.gui.hover_tooltip import HoverTooltip
        ui_queue = []
        def mock_post_to_ui(fn):
            ui_queue.append(fn)

        tooltip = HoverTooltip(
            root=self.root,
            db=MagicMock(),
            post_to_ui=mock_post_to_ui
        )
        word_data = {
            "german": "Tisch",
            "turkish": "masa",
            "article": "der",
            "plural": "die Tische"
        }

        # Arka plan iş parçacığından show çağır
        bg_thread = threading.Thread(target=lambda: tooltip.show(word_data, 150, 200))
        bg_thread.start()
        bg_thread.join(timeout=1.0)

        # Worker thread doğrudan widget değiştirmedi, kuyruğa aktardı
        self.assertEqual(len(ui_queue), 1)

        # Ana iş parçacığında kuyruktaki görevi çalıştır
        executing_threads = []
        def run_task():
            executing_threads.append(threading.current_thread().ident)
            ui_queue[0]()

        run_task()
        self.root.update()

        # Ana thread'de çalıştığını ve widget metninin güncellendiğini doğrula
        self.assertEqual(executing_threads, [threading.main_thread().ident])
        self.assertEqual(tooltip.lbl_german.cget("text"), "Tisch")
        self.assertEqual(tooltip.lbl_turkish.cget("text"), "masa")
        self.assertEqual(tooltip.lbl_article.cget("text"), "der")

        tooltip.hide()

    @patch("app.gui.onboarding_wizard.save_config")
    def test_window_destroy_with_pending_queue_avoids_dead_widget_crash(self, mock_save_config):
        """Pencereler kapatıldığında kuyrukta bekleyen veya sonradan gelen worker görevleri yok edilmiş widget'lara dokunmamalıdır."""
        from app.gui.settings_window import SettingsWindow
        from app.gui.onboarding_wizard import OnboardingWizard

        # 1. SettingsWindow testi
        settings = SettingsWindow(
            parent=self.root,
            config={"gemini_model": "gemini-3.5-flash-lite"},
            on_settings_changed=MagicMock()
        )
        # Kuyruğa tehlikeli bir Tk işlemi ekle
        touch_called = []
        def dangerous_action():
            touch_called.append("touched")
            settings.lbl_save_status.configure(text="Hatalı dokunma")

        settings.post_to_ui(dangerous_action)
        # Pencereyi kapat/yok et
        settings.close()

        # Kapatıldıktan sonra poll veya kuyruk boşaltma tehlikeli işlemi çalıştırmamalı
        settings._poll_queue()
        self.assertEqual(len(touch_called), 0)

        # Kapatıldıktan sonra gelen yeni worker görevleri de reddedilmeli
        settings.post_to_ui(dangerous_action)
        self.assertEqual(settings._ui_queue.qsize(), 0)

        # 2. OnboardingWizard testi
        wizard = OnboardingWizard(
            parent=self.root,
            config={"gemini_model": "gemini-3.5-flash-lite"},
            ocr_engine=MagicMock(),
            translator=MagicMock()
        )
        wizard_touch = []
        def wizard_dangerous_action():
            wizard_touch.append("touched")

        wizard.post_to_ui(wizard_dangerous_action)
        # Sihirbazı kapat
        wizard._finish_wizard()

        wizard._poll_queue()
        self.assertEqual(len(wizard_touch), 0)

        wizard.post_to_ui(wizard_dangerous_action)
        self.assertEqual(wizard._ui_queue.qsize(), 0)


if __name__ == "__main__":
    unittest.main()
