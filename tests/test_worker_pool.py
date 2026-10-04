"""
Sınırlı İş Parçacığı Havuzu (WorkerThreadPool) ve Görev Tutamaçları (TaskHandle) Testleri
"""
import unittest
import threading
import time
from unittest.mock import MagicMock, patch
import tempfile
import sqlite3
from pathlib import Path

from app.worker_pool import WorkerThreadPool, TaskHandle


class TestWorkerThreadPool(unittest.TestCase):
    def setUp(self):
        self.pool = WorkerThreadPool(max_workers=4, thread_name_prefix="TestWorker")

    def tearDown(self):
        self.pool.shutdown(wait=True, cancel_futures=True)

    def test_pool_initialization(self):
        """Havuz belirtilen iş parçacığı sayısı ile başlatılmalı ve aktif olmalıdır."""
        self.assertEqual(self.pool.max_workers, 4)
        self.assertFalse(self.pool.is_shutdown)
        self.assertEqual(self.pool.active_count, 0)

    def test_task_handle_lifecycle_and_result(self):
        """Görev başarıyla tamamlanmalı, handle result ve lifecycle doğru raporlanmalıdır."""
        def add(a, b):
            time.sleep(0.05)
            return a + b

        handle = self.pool.submit(add, 10, 20)
        self.assertIsNotNone(handle)
        self.assertIsInstance(handle, TaskHandle)
        self.assertTrue(handle.is_alive())
        self.assertFalse(handle.done())

        # join ile bekleme
        finished = handle.join(timeout=2.0)
        self.assertTrue(finished)
        self.assertTrue(handle.done())
        self.assertFalse(handle.is_alive())
        self.assertEqual(handle.result(), 30)
        self.assertIsNone(handle.exception())

    def test_task_handle_join_timeout(self):
        """join() zaman aşımında False dönmeli, görev bitince True dönmelidir."""
        gate = threading.Event()

        def slow_task():
            gate.wait(timeout=2.0)
            return "done"

        handle = self.pool.submit(slow_task)
        self.assertIsNotNone(handle)
        # 10ms içinde bitmemeli
        finished = handle.join(timeout=0.01)
        self.assertFalse(finished)
        self.assertTrue(handle.is_alive())

        # Kilidi aç ve tamamlanmasını bekle
        gate.set()
        finished = handle.join(timeout=2.0)
        self.assertTrue(finished)
        self.assertEqual(handle.result(), "done")

    def test_concurrency_bounded_to_max_workers(self):
        """Aynı anda en fazla max_workers (4) iş parçacığı aktif olarak çalışabilmelidir."""
        lock = threading.Lock()
        current_running = 0
        peak_running = 0
        gate = threading.Event()

        def worker_func():
            nonlocal current_running, peak_running
            with lock:
                current_running += 1
                if current_running > peak_running:
                    peak_running = current_running
            # Tüm worker'ların eşzamanlı çalışıp çalışmadığını ölçmek için beklet
            gate.wait(timeout=2.0)
            with lock:
                current_running -= 1
            return True

        # 8 adet görev gönder
        handles = [self.pool.submit(worker_func) for _ in range(8)]
        # Görevlerin başlaması için kısa bekleme
        time.sleep(0.1)

        with lock:
            observed_peak = peak_running

        # Havuz 4 worker'lı olduğundan aynı andaki aktif çalışan sayısı 4'ü geçmemelidir
        self.assertLessEqual(observed_peak, 4)
        self.assertGreaterEqual(observed_peak, 1)

        # Kilidi aç ve tümünün bitmesini bekle
        gate.set()
        for h in handles:
            if h is not None:
                h.join(timeout=2.0)

    def test_worker_threads_are_daemon(self):
        """Worker thread'leri daemon=True olmalıdır ki uygulama kapanışında açık soketler süreci asılı bırakmasın."""
        is_daemon = None

        def check_daemon():
            nonlocal is_daemon
            is_daemon = threading.current_thread().daemon
            return is_daemon

        handle = self.pool.submit(check_daemon)
        self.assertIsNotNone(handle)
        handle.join(timeout=2.0)
        self.assertTrue(is_daemon, "WorkerThreadPool thread'leri daemon=True olmalıdır")

    def test_task_exception_handling_resilience(self):
        """Hata fırlatan görev havuzu çökertmemeli, exception handle üzerinden okunabilmelidir."""
        def failing_task():
            raise ValueError("Kasıtlı test hatası")

        handle = self.pool.submit(failing_task)
        self.assertIsNotNone(handle)
        handle.join(timeout=2.0)

        self.assertTrue(handle.done())
        self.assertIsInstance(handle.exception(), ValueError)
        self.assertEqual(str(handle.exception()), "Kasıtlı test hatası")
        with self.assertRaises(ValueError):
            handle.result()

        # Havuz sonraki işleri kabul etmeye devam edebilmelidir
        handle2 = self.pool.submit(lambda: "healthy")
        self.assertIsNotNone(handle2)
        handle2.join(timeout=2.0)
        self.assertEqual(handle2.result(), "healthy")

    def test_shutdown_rejects_new_tasks(self):
        """shutdown() sonrası submit() çağrıları None dönmeli ve havuz kapatılmış olmalıdır."""
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.assertTrue(self.pool.is_shutdown)

        rejected_handle = self.pool.submit(lambda: 42)
        self.assertIsNone(rejected_handle)

    def test_shutdown_cancels_queued_tasks(self):
        """shutdown(cancel_futures=True) kuyrukta bekleyen henüz başlamamış görevleri iptal etmelidir."""
        gate = threading.Event()
        all_running = threading.Event()
        started_count = 0
        lock = threading.Lock()

        def block_worker():
            nonlocal started_count
            with lock:
                started_count += 1
                if started_count == 4:
                    all_running.set()
            gate.wait(timeout=2.0)

        # 4 worker'ı başlat ve hepsinin çalıştığından emin ol
        blocking_handles = [self.pool.submit(block_worker) for _ in range(4)]
        self.assertTrue(all_running.wait(timeout=2.0), "4 worker da çalışır duruma geçmeli")

        queued_ran = False

        def queued_task():
            nonlocal queued_ran
            queued_ran = True

        queued_handle = self.pool.submit(queued_task)
        self.assertIsNotNone(queued_handle)

        # Derhal shutdown çağır (kuyruktakileri iptal etmeli)
        self.pool.shutdown(wait=False, cancel_futures=True)

        # Blokajı kaldır
        gate.set()
        for h in blocking_handles:
            h.join(timeout=2.0)
        queued_handle.join(timeout=0.5)

        # Kuyrukta bekleyen görev iptal edildiği için çalışmamış olmalı
        self.assertFalse(queued_ran)


class TestMainOverlayWorkerPoolIntegration(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        try:
            for child in list(self.root.winfo_children()):
                try:
                    child.destroy()
                except Exception:
                    pass
            self.root.destroy()
        except Exception:
            pass

    def test_overlay_worker_pool_shutdown(self):
        """MainOverlay.stop() çağrıldığında havuz kapatılmalı ve yeni arama reddedilmelidir."""
        from app.gui.main_overlay import MainOverlay

        mock_translator = MagicMock()
        mock_translator.translate_and_analyze.return_value = {"original": "Hund", "translation": "Köpek"}
        mock_ocr = MagicMock()
        mock_db = MagicMock()
        mock_db.is_word_saved.return_value = False
        mock_clip = MagicMock()
        mock_clip.is_enabled.return_value = False

        overlay = MainOverlay(
            root=self.root,
            translator=mock_translator,
            ocr_engine=mock_ocr,
            db=mock_db,
            clipboard_watcher=mock_clip,
            config={"first_run_completed": True, "hover_enabled": False}
        )

        self.assertIsNotNone(overlay._worker_pool)
        self.assertFalse(overlay._worker_pool.is_shutdown)

        # Arama görevi gönderildiğinde TaskHandle dönmeli
        handle = overlay.lookup_text("Hund")
        self.assertIsNotNone(handle)
        self.assertTrue(isinstance(handle, TaskHandle))
        handle.join(timeout=2.0)

        # stop() çağrıldığında havuz kapatılmalı
        overlay.stop()
        self.assertTrue(overlay._worker_pool.is_shutdown)

        # Kapanış sonrası yeni arama None dönmeli
        rejected = overlay.lookup_text("Katze")
        self.assertIsNone(rejected)

        rejected_clip = overlay._lookup_from_clipboard()
        self.assertIsNone(rejected_clip)

    def test_overlay_delayed_result_after_stop_does_not_call_ui(self):
        """Durdurulmuş overlay'e dönen gecikmiş worker sonucu UI kuyruğuna veya HUD'a yazılmamalıdır."""
        from app.gui.main_overlay import MainOverlay

        gate = threading.Event()

        def slow_translate(word):
            gate.wait(timeout=2.0)
            return {"original": word, "translation": "Test"}

        mock_translator = MagicMock()
        mock_translator.translate_and_analyze.side_effect = slow_translate
        mock_ocr = MagicMock()
        mock_db = MagicMock()
        mock_clip = MagicMock()
        mock_clip.is_enabled.return_value = False

        overlay = MainOverlay(
            root=self.root,
            translator=mock_translator,
            ocr_engine=mock_ocr,
            db=mock_db,
            clipboard_watcher=mock_clip,
            config={"first_run_completed": True, "hover_enabled": False}
        )

        # Görevi başlat
        handle = overlay.lookup_text("Buch")
        self.assertIsNotNone(handle)

        # Görev çalışırken overlay'i durdur
        overlay.stop()

        # Artık çevirinin tamamlanmasına izin ver
        gate.set()
        handle.join(timeout=2.0)

        # UI kuyruğu boş olmalı veya kapanış sonrası eklenen öğe olmamalı
        self.assertEqual(overlay._ui_queue.qsize(), 0)

    def test_generation_id_protects_against_stale_lookups(self):
        """Eski generation ID'ye sahip arama sonucu, yeni nesil aktifken UI'ı güncellememelidir."""
        from app.gui.main_overlay import MainOverlay

        event1_start = threading.Event()
        event1_finish = threading.Event()

        def slow_translate_1(word):
            event1_start.set()
            event1_finish.wait(timeout=2.0)
            return {"original": "slow", "translation": "Yavaş"}

        mock_translator = MagicMock()
        mock_translator.translate_and_analyze.side_effect = slow_translate_1
        mock_ocr = MagicMock()
        mock_db = MagicMock()
        mock_clip = MagicMock()
        mock_clip.is_enabled.return_value = False

        overlay = MainOverlay(
            root=self.root,
            translator=mock_translator,
            ocr_engine=mock_ocr,
            db=mock_db,
            clipboard_watcher=mock_clip,
            config={"first_run_completed": True, "hover_enabled": False}
        )
        mock_show_hud = MagicMock()
        overlay._show_hud = mock_show_hud

        # 1. Aramayı gönder (Generation ID = 1)
        h1 = overlay.lookup_text("slow")
        self.assertTrue(event1_start.wait(timeout=1.0))
        self.assertEqual(overlay._lookup_generation, 1)

        # 2. Aramayı gönder (Generation ID = 2) - mock'u hızlı sonuca dönüştür
        mock_translator.translate_and_analyze.side_effect = lambda w: {"original": "fast", "translation": "Hızlı"}
        h2 = overlay.lookup_text("fast")
        self.assertEqual(overlay._lookup_generation, 2)
        h2.join(timeout=2.0)

        # UI kuyruğunu işle
        overlay._poll_ui_queue()

        # Şimdi 1. eski aramanın bitmesine izin ver
        event1_finish.set()
        h1.join(timeout=2.0)

        overlay._poll_ui_queue()

        # 1. arama eski nesil (gen=1) olduğu için HUD'a 'slow' basılmamalıdır
        # Yalnızca 'fast' sonucu gösterilmiş olmalıdır
        calls = [c[0][0]["original"] for c in mock_show_hud.call_args_list]
        self.assertIn("fast", calls)
        self.assertNotIn("slow", calls)

        overlay.stop()

    def test_shutdown_timeout_triggered_while_active_db_write_persists(self):
        """
        Havuz kapanış zaman aşımı tetiklendiğinde (timeout sonucu dikkate alınarak)
        aktif DB yazmasının sessizce kaybolmadığını, tamamlanan yazmanın kalıcı olduğunu
        ve veritabanı bütünlüğünün korunduğunu deterministik olarak doğrular.
        Yazma işi shutdown çağrısından ÖNCE serbest bırakılmaz.
        """
        import tempfile
        import sqlite3
        from pathlib import Path
        from app.database import Database

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_db_path = Path(tmp_dir) / "test_shutdown_persistence.db"
            db = Database(test_db_path)
            pool = WorkerThreadPool(max_workers=2, thread_name_prefix="DBPersistPool")

            write_entered = threading.Event()
            write_release_gate = threading.Event()
            write_completed = threading.Event()
            write_error = None

            def controlled_db_write():
                nonlocal write_error
                try:
                    with db._get_connection() as conn:
                        cursor = conn.cursor()
                        # Gerçek SQLite yazma transaction'ı başlat ve INSERT yap (henüz commit edilmedi)
                        cursor.execute("BEGIN IMMEDIATE;")
                        cursor.execute(
                            "INSERT INTO cache (query_text, result_json) VALUES (?, ?)",
                            ("hund", '{"original": "Hund", "turkish": "köpek"}')
                        )
                        write_entered.set()
                        # SHUTDOWN VE DB.CLOSE ÇAĞRILIP ZAMAN AŞIMINA UĞRAYANA KADAR COMMIT ETMEDEN BEKLE:
                        if not write_release_gate.wait(timeout=5.0):
                            raise TimeoutError("Test release gate açılmadı!")
                    write_completed.set()
                except Exception as e:
                    write_error = e

            handle = pool.submit(controlled_db_write)
            self.assertIsNotNone(handle)
            # Görevin INSERT'i yaptığını ve transaction'ın açık olduğunu doğrula
            self.assertTrue(write_entered.wait(timeout=2.0))
            self.assertEqual(db._active_operations, 1)

            # 1. Havuzu kapatırken kısa timeout (50ms) vererek kapanış zaman aşımını tetikle
            #    Yazma transaction'ı henüz commit edilmemiştir!
            pool_shutdown_ok = pool.shutdown(wait=True, cancel_futures=True, timeout=0.05)
            self.assertFalse(pool_shutdown_ok, "Yazma transaction'ı açıkken shutdown False dönmelidir!")
            self.assertTrue(pool.is_shutdown)

            # 2. db.close() çağrısı açık transaction varken başarıyla kapandı dememeli (False dönmeli)
            #    ve checkpoint başlatmamalıdır
            db_closed_early = db.close(timeout=0.05)
            self.assertFalse(db_closed_early, "Açık transaction varken db.close() timeout verip False dönmelidir!")
            self.assertFalse(db.is_closed, "İşlem sürerken veritabanı kapalı duruma geçmemelidir!")

            # 3. Timeout tetiklendikten SONRA işlemi serbest bırak ve commit edilmesini sağla
            write_release_gate.set()
            self.assertTrue(write_completed.wait(timeout=2.0))
            self.assertIsNone(write_error, f"DB yazma hatasız tamamlanmalıydı: {write_error}")

            # 4. İşlem commit edildikten sonra db.close() çağrısı başarıyla kapanmalıdır
            db_closed_ok = db.close(timeout=3.0)
            self.assertTrue(db_closed_ok, "İşlem commit edildikten sonra db.close() True dönmelidir.")
            self.assertTrue(db.is_closed)

            # 5. Veritabanının bütünlüğünü ve tamamlanan yazmanın kalıcılığını doğrudan bağımsız SQLite ile doğrula
            check_conn = sqlite3.connect(test_db_path)
            try:
                cursor = check_conn.cursor()
                cursor.execute("PRAGMA integrity_check;")
                self.assertEqual(cursor.fetchone()[0], "ok")

                cursor.execute("SELECT result_json FROM cache WHERE query_text = 'hund'")
                row = cursor.fetchone()
                self.assertIsNotNone(row, "Kapanış sırasında yazılan veri veritabanında bulunmalıdır!")
                self.assertIn("köpek", row[0])
            finally:
                check_conn.close()

            # 6. DB kapandıktan sonra yeni işlem denemesi engellenmelidir
            self.assertFalse(db.set_cache("Katze", {"original": "Katze", "turkish": "kedi"}))

            db = None
            pool = None
            import gc
            gc.collect()

    def test_perform_application_shutdown_clean_exit(self):
        """Tüm bileşenler boşta ve veri tabanı işlemi yokken on_quit akışı temiz çıkış (kod 0) üretmelidir."""
        from main import perform_application_shutdown
        from app.database import Database

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_db = Database(Path(tmp_dir) / "test_clean_quit.db")
            mock_overlay = MagicMock()
            mock_overlay._worker_pool = WorkerThreadPool(max_workers=2)
            mock_tray = MagicMock()
            mock_clip = MagicMock()
            mock_exit = MagicMock()

            code = perform_application_shutdown(
                overlay=mock_overlay,
                tray=mock_tray,
                clipboard_watcher=mock_clip,
                db=test_db,
                exit_fn=mock_exit,
                pool_timeout=0.5,
                pool_grace=0.5,
                db_timeout=0.5,
                db_grace=0.5
            )

            self.assertEqual(code, 0)
            mock_exit.assert_called_once_with(0)
            self.assertTrue(test_db.is_closed)
            mock_overlay.stop.assert_called_once()
            mock_tray.stop.assert_called_once()
            mock_clip.stop.assert_called_once()
            test_db = None
            import gc
            gc.collect()

    def test_perform_application_shutdown_reports_non_clean_when_db_operation_times_out(self):
        """Aktif DB işlemi grace süreleri boyunca açık kaldığında, on_quit temiz kapanış iddia etmemeli ve kod 1 dönmelidir."""
        from main import perform_application_shutdown
        from app.database import Database

        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_timeout_quit.db"
            test_db = Database(db_path)
            pool = WorkerThreadPool(max_workers=2, thread_name_prefix="GraceTimeoutPool")

            mock_overlay = MagicMock()
            mock_overlay._worker_pool = pool
            mock_tray = MagicMock()
            mock_clip = MagicMock()
            mock_exit = MagicMock()

            write_active = threading.Event()
            write_gate = threading.Event()
            write_done = threading.Event()

            def uncommitted_tx():
                try:
                    with test_db._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("BEGIN IMMEDIATE;")
                        cursor.execute("INSERT INTO cache (query_text, result_json) VALUES (?, ?)", ("wasser", '{"turkish": "su"}'))
                        write_active.set()
                        if not write_gate.wait(timeout=5.0):
                            raise TimeoutError("Gate timeout")
                finally:
                    write_done.set()

            pool.submit(uncommitted_tx)
            self.assertTrue(write_active.wait(timeout=2.0))

            # on_quit akışını çalıştır (tüm timeout/grace süreleri aşılacak):
            code = perform_application_shutdown(
                overlay=mock_overlay,
                tray=mock_tray,
                clipboard_watcher=mock_clip,
                db=test_db,
                exit_fn=mock_exit,
                pool_timeout=0.05,
                pool_grace=0.05,
                db_timeout=0.05,
                db_grace=0.05
            )

            # 1. db.close() açık işlem varken başarıyla kapandı dememelidir
            self.assertEqual(code, 1, "Açık DB işlemi zaman aşımına uğradığında çıkış kodu 1 (hata) olmalıdır!")
            mock_exit.assert_called_once_with(1)
            self.assertFalse(test_db.is_closed, "İşlem sürerken veritabanı kapalı duruma geçmemelidir!")

            # 2. Timeout sonrası işlem kapısı açıldığında commit ve bütünlük doğrulanmalıdır
            write_gate.set()
            self.assertTrue(write_done.wait(timeout=2.0))

            # 3. Bağımsız bağlantı ile commit edilen veriyi ve integrity_check'i doğrula
            check_conn = sqlite3.connect(db_path)
            try:
                cursor = check_conn.cursor()
                cursor.execute("PRAGMA integrity_check;")
                self.assertEqual(cursor.fetchone()[0], "ok")
                cursor.execute("SELECT result_json FROM cache WHERE query_text = 'wasser'")
                row = cursor.fetchone()
                self.assertIsNotNone(row)
                self.assertIn("su", row[0])
            finally:
                check_conn.close()

            test_db = None
            pool = None
            import gc
            gc.collect()

    def test_perform_application_shutdown_reports_non_clean_when_worker_times_out_with_idle_db(self):
        """DB'de aktif işlem yokken bile bir worker görevi zaman aşımına uğrarsa kapanış temiz sayılmamalı, exit_fn 1 almalıdır."""
        from main import perform_application_shutdown
        from app.database import Database

        with tempfile.TemporaryDirectory() as tmp_dir:
            test_db = Database(Path(tmp_dir) / "test_worker_timeout_idle_db.db")
            pool = WorkerThreadPool(max_workers=2, thread_name_prefix="StuckWorkerPool")

            mock_overlay = MagicMock()
            mock_overlay._worker_pool = pool
            mock_tray = MagicMock()
            mock_clip = MagicMock()
            mock_exit = MagicMock()

            worker_running = threading.Event()
            worker_release = threading.Event()

            def stuck_task():
                worker_running.set()
                if not worker_release.wait(timeout=5.0):
                    raise TimeoutError("Test worker release gate açılmadı")

            pool.submit(stuck_task)
            self.assertTrue(worker_running.wait(timeout=2.0))

            # DB'de hiçbir aktif işlem yok (test_db._active_operations == 0)
            self.assertEqual(test_db._active_operations, 0)

            # on_quit akışını çalıştır (pool_timeout ve pool_grace kısa tutularak aşılacak):
            code = perform_application_shutdown(
                overlay=mock_overlay,
                tray=mock_tray,
                clipboard_watcher=mock_clip,
                db=test_db,
                exit_fn=mock_exit,
                pool_timeout=0.05,
                pool_grace=0.05,
                db_timeout=0.5,
                db_grace=0.5
            )

            # pool_ok False olduğu için nihai çıkış kodu 1 olmalıdır!
            self.assertEqual(code, 1, "Worker havuzu zaman aşımına uğradığında DB boşta olsa dahi çıkış kodu 1 olmalıdır!")
            mock_exit.assert_called_once_with(1)

            # Test sonunda worker'ı serbest bırak ve kaynakları temizle
            worker_release.set()
            pool.shutdown(wait=True, timeout=2.0)
            test_db = None
            pool = None
            import gc
            gc.collect()

    def test_perform_application_shutdown_late_worker_db_write_fails_explicitly_with_exit_code_1(self):
        """Worker havuzu zaman aşımına uğradıktan sonra geç kalan worker'ın kapalı DB'ye yazma denemesi sessizce kaybolmamalı, False dönmeli ve süreç kodu 1 vermelidir."""
        from main import perform_application_shutdown
        from app.database import Database

        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_late_worker_write.db"
            test_db = Database(db_path)
            pool = WorkerThreadPool(max_workers=2, thread_name_prefix="LateWorkerPool")

            mock_overlay = MagicMock()
            mock_overlay._worker_pool = pool
            mock_tray = MagicMock()
            mock_clip = MagicMock()
            mock_exit = MagicMock()

            worker_started = threading.Event()
            worker_release = threading.Event()
            write_results = {}

            def late_worker_task():
                worker_started.set()
                if not worker_release.wait(timeout=5.0):
                    raise TimeoutError("Gate timeout")
                # Kapanış ve db.close() sonrasında yazma denemeleri:
                write_results["cache_res"] = test_db.set_cache("apfel", {"turkish": "elma"})
                write_results["hist_res"] = test_db.add_history("apfel", {"turkish": "elma"})

            pool.submit(late_worker_task)
            self.assertTrue(worker_started.wait(timeout=2.0))

            # Shutdown'u kısa zaman aşımıyla çağır (pool_timeout aşılacak, pool_ok=False)
            code = perform_application_shutdown(
                overlay=mock_overlay,
                tray=mock_tray,
                clipboard_watcher=mock_clip,
                db=test_db,
                exit_fn=mock_exit,
                pool_timeout=0.05,
                pool_grace=0.05,
                db_timeout=0.5,
                db_grace=0.5
            )

            # 1. Havuz zaman aşımına uğradığı için kapanış kodu 1 olmalı
            self.assertEqual(code, 1, "Zaman aşımına uğrayan worker olduğunda kapanış kodu 1 olmalıdır")
            mock_exit.assert_called_once_with(1)

            # 2. DB kapatılmış olmalı
            self.assertTrue(test_db.is_closed)

            # 3. Geç kalan worker'ı serbest bırak ve yazma denemesini yapmasını sağla
            worker_release.set()
            pool.shutdown(wait=True, timeout=2.0)

            # 4. Yazma denemeleri sessizce başarı varsayılmamalı veya yutulmamalı; açıkça False dönmelidir
            self.assertIn("cache_res", write_results)
            self.assertFalse(write_results["cache_res"], "Kapalı DB'ye set_cache açıkça False dönmelidir")
            self.assertFalse(write_results["hist_res"], "Kapalı DB'ye add_history açıkça False dönmelidir")

            # 5. Bağımsız bağlantı ile DB bütünlüğünü ve kayıtların yazılmadığını doğrula
            check_conn = sqlite3.connect(db_path)
            try:
                cur = check_conn.cursor()
                cur.execute("PRAGMA integrity_check;")
                self.assertEqual(cur.fetchone()[0], "ok")
                cur.execute("SELECT COUNT(*) FROM cache WHERE query_text = 'apfel'")
                self.assertEqual(cur.fetchone()[0], 0, "Kapalı DB'ye yazılan veri önbelleğe girmemelidir")
                cur.execute("SELECT COUNT(*) FROM history WHERE query_text = 'apfel'")
                self.assertEqual(cur.fetchone()[0], 0, "Kapalı DB'ye yazılan veri geçmişe girmemelidir")
            finally:
                check_conn.close()

            test_db = None
            pool = None
            import gc
            gc.collect()


if __name__ == "__main__":
    unittest.main()
