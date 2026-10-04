"""
Kontrollü İş Parçacığı Havuzu (Worker Thread Pool) Modülü

Bu modül, uygulama genelinde başıboş (unmanaged) thread üretimini
en fazla 4 iş parçacıklı sınırlı bir havuza bağlar.
Worker iş parçacıkları daemon=True olarak başlatılır; uygulama kapanışında
açık soketler veya yavaş ağ çağrıları sürecin kapanışını (sys.exit) asılı bırakmaz.
Özel CPython iç API'lerine bağımlılık içermez (Python 3.10, 3.11, 3.12 ile %100 uyumlu).
"""
from __future__ import annotations

import concurrent.futures
import queue
import threading
import time
from typing import Any, Callable, List, Optional, Set


class TaskHandle:
    """
    Havuzda yürütülen bir görevi temsil eden iş parçacığı güvenli tutamaç.
    threading.Thread arayüzü ile geriye dönük uyumluluk (join, is_alive) sağlar.
    """

    def __init__(self, future: concurrent.futures.Future):
        self._future = future
        self._done_event = threading.Event()
        self._future.add_done_callback(lambda _: self._done_event.set())

    def join(self, timeout: Optional[float] = None) -> bool:
        """Görevin tamamlanmasını bekler. Süre aşımında False, bittiğinde True döner."""
        return self._done_event.wait(timeout=timeout)

    def is_alive(self) -> bool:
        """Görev henüz tamamlanmadıysa (çalışıyor veya kuyrukta bekliyor) True döner."""
        return not self._future.done()

    def cancel(self) -> bool:
        """Kuyrukta bekleyen görevi iptal eder. Başlamış görev iptal edilemeyebilir."""
        return self._future.cancel()

    def done(self) -> bool:
        """Görev tamamlandıysa (veya iptal edildiyse) True döner."""
        return self._future.done()

    def result(self, timeout: Optional[float] = None) -> Any:
        """Görevin dönüş değerini döner; hata fırlatıldıysa o hatayı yükseltir."""
        return self._future.result(timeout=timeout)

    def exception(self, timeout: Optional[float] = None) -> Optional[BaseException]:
        """Görev sırasında fırlatılan istisnayı döner."""
        return self._future.exception(timeout=timeout)

    @property
    def future(self) -> concurrent.futures.Future:
        """Altta yatan Future nesnesi."""
        return self._future


class WorkerThreadPool:
    """
    Sınırlı sayıda (varsayılan 4) daemon iş parçacığı barındıran kontrollü thread havuzu.
    Uygulama veya bileşen kapatıldığında yeni iş kabulünü durdurur ve
    kuyrukta bekleyen görevleri iptal eder.
    CPython iç API'lerine ihtiyaç duymadan standart queue ve daemon threading kullanır.
    """

    def __init__(
        self,
        max_workers: int = 4,
        thread_name_prefix: str = "EkranSozlugu-Worker"
    ):
        self._max_workers = max(1, int(max_workers))
        self._thread_name_prefix = thread_name_prefix
        self._lock = threading.RLock()
        self._work_queue: queue.Queue = queue.Queue()
        self._threads: List[threading.Thread] = []
        self._is_shutdown = False
        self._active_handles: Set[TaskHandle] = set()

    @property
    def is_shutdown(self) -> bool:
        """Havuzun kapatılıp kapatılmadığını döner."""
        with self._lock:
            return self._is_shutdown

    @property
    def max_workers(self) -> int:
        """Maksimum çalışan iş parçacığı sayısı."""
        return self._max_workers

    @property
    def active_count(self) -> int:
        """Şu anda kuyrukta bekleyen veya çalışmakta olan aktif görev sayısı."""
        with self._lock:
            return len(self._active_handles)

    def _worker_loop(self):
        """Worker thread döngüsü: kuyruktan görev alır ve çalıştırır."""
        while True:
            try:
                item = self._work_queue.get()
            except Exception:
                break

            if item is None:
                # Kapanış sentineli: thread sonlanır
                self._work_queue.task_done()
                break

            fut, fn, args, kwargs = item
            # Görev başlamadan önce iptal edilmiş mi kontrol et
            if not fut.set_running_or_notify_cancel():
                self._work_queue.task_done()
                continue

            try:
                res = fn(*args, **kwargs)
                fut.set_result(res)
            except BaseException as exc:
                fut.set_exception(exc)
            finally:
                self._work_queue.task_done()

    def submit(
        self,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any
    ) -> Optional[TaskHandle]:
        """
        Havuzda yeni bir arka plan görevi yürütür.
        Havuz kapatılmışsa iş kabul edilmez ve None döner.
        """
        with self._lock:
            if self._is_shutdown:
                return None

            # İhtiyaç duyuldukça azami max_workers kadar daemon thread başlat
            if len(self._threads) < self._max_workers:
                t = threading.Thread(
                    target=self._worker_loop,
                    name=f"{self._thread_name_prefix}_{len(self._threads)}",
                    daemon=True,
                )
                t.start()
                self._threads.append(t)

            future = concurrent.futures.Future()
            handle = TaskHandle(future)
            self._active_handles.add(handle)

            def _on_done(_):
                with self._lock:
                    self._active_handles.discard(handle)

            future.add_done_callback(_on_done)
            self._work_queue.put((future, fn, args, kwargs))
            return handle

    def shutdown(
        self,
        wait: bool = False,
        cancel_futures: bool = True,
        timeout: Optional[float] = None
    ) -> bool:
        """
        Havuzu kapatır, yeni iş kabulünü derhal durdurur ve bekleyen görevleri iptal eder.
        timeout belirtilmişse, çalışan görevlerin tamamlanmasını timeout süresince bekler.
        Tüm görevler tamamlandıysa True, süre aşımı olduysa False döner.
        """
        with self._lock:
            if self._is_shutdown:
                if timeout is not None:
                    return self.wait(timeout=timeout)
                return len(self._active_handles) == 0
            self._is_shutdown = True
            handles_to_cancel = list(self._active_handles)

        if cancel_futures:
            # Kuyrukta henüz başlamamış olan görevleri tahliye et ve iptal et
            while True:
                try:
                    item = self._work_queue.get_nowait()
                except queue.Empty:
                    break
                if item is not None:
                    fut = item[0]
                    fut.cancel()
                    self._work_queue.task_done()

        # Tutamaçları da iptal durumuna geçir
        for handle in handles_to_cancel:
            try:
                handle.cancel()
            except Exception:
                pass

        # İş parçacıklarını uyandırmak ve sonlandırmak için sentinel gönder
        with self._lock:
            for _ in self._threads:
                self._work_queue.put(None)

        if wait or (timeout is not None and timeout > 0):
            return self.wait(timeout=timeout)

        with self._lock:
            return len(self._active_handles) == 0

    def wait(self, timeout: Optional[float] = None) -> bool:
        """
        Havuzdaki aktif çalışan görevlerin tamamlanmasını bekler.
        Tüm görevler tamamlandıysa True, süre aşımı olduysa False döner.
        """
        with self._lock:
            handles = list(self._active_handles)

        if not handles:
            return True

        start_time = time.time()
        for handle in handles:
            if timeout is None:
                handle.join()
            else:
                elapsed = time.time() - start_time
                remaining = max(0.0, timeout - elapsed)
                if remaining <= 0 or not handle.join(timeout=remaining):
                    return False
        return True
