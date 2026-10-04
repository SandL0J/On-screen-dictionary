"""
50 Ardışık Arama, Hızlı Peş Peşe Arama ve Kapanış Dayanıklılık Testleri (Stress & Resilience)
"""
import unittest
import tkinter as tk
import threading
import time
from unittest.mock import MagicMock

from app.gui.main_overlay import MainOverlay
from app.worker_pool import WorkerThreadPool


class TestStressAndResilience(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.mock_translator = MagicMock()
        self.mock_translator.translate_and_analyze.side_effect = lambda w: {
            "original": w,
            "translation": f"{w}_tr",
            "article": "der" if len(w) % 2 == 0 else "die",
        }
        self.mock_ocr = MagicMock()
        self.mock_db = MagicMock()
        self.mock_db.is_word_saved.return_value = False
        self.mock_clip = MagicMock()
        self.mock_clip.is_enabled.return_value = False

        self.overlay = MainOverlay(
            root=self.root,
            translator=self.mock_translator,
            ocr_engine=self.mock_ocr,
            db=self.mock_db,
            clipboard_watcher=self.mock_clip,
            config={"first_run_completed": True, "hover_enabled": False}
        )
        self.overlay._show_hud = MagicMock()

    def tearDown(self):
        if getattr(self, "overlay", None):
            try:
                self.overlay.stop()
            except Exception:
                pass
        try:
            for child in list(self.root.winfo_children()):
                try:
                    child.destroy()
                except Exception:
                    pass
            self.root.update()
        except Exception:
            pass

    def test_50_consecutive_lookups(self):
        """50 ardışık kelime aratıldığında hiçbir UI kilitlenmesi veya çökme yaşanmamalıdır."""
        words = [f"Wort{i}" for i in range(50)]
        for w in words:
            handle = self.overlay.lookup_text(w)
            self.assertIsNotNone(handle)
            handle.join(timeout=1.0)
            self.overlay._poll_ui_queue()

        self.assertEqual(self.overlay._show_hud.call_count, 50)
        self.assertEqual(self.overlay._lookup_generation, 50)

    def test_rapid_fire_lookups_stale_discard(self):
        """Hızla peş peşe 20 arama yapıldığında yalnızca en son neslin HUD'ı güncellediği doğrulanmalıdır."""
        # Yavaş ve değişken gecikmeli çevirici simülasyonu
        def variable_speed_translate(w):
            idx = int(w.replace("Schnell", ""))
            # İlk aramalar daha yavaş, son arama hızlı
            delay = 0.05 if idx == 19 else 0.1
            time.sleep(delay)
            return {"original": w, "translation": f"{w}_tr"}

        self.mock_translator.translate_and_analyze.side_effect = variable_speed_translate

        handles = []
        for i in range(20):
            h = self.overlay.lookup_text(f"Schnell{i}")
            handles.append(h)

        # Tüm işlerin bitmesini bekle
        for h in handles:
            if h:
                h.join(timeout=3.0)

        self.overlay._poll_ui_queue()

        # En son nesil 20 olmalıdır
        self.assertEqual(self.overlay._lookup_generation, 20)
        # Gösterilen en son arama Schnell19 olmalıdır
        last_call_data = self.overlay._show_hud.call_args[0][0]
        self.assertEqual(last_call_data["original"], "Schnell19")

    def test_repeated_start_stop_cycles(self):
        """Uygulama arka arkaya 10 kez durdurulup tekrar başlatıldığında zombi zamanlayıcı veya kilit oluşmamalıdır."""
        for _ in range(10):
            self.overlay.stop()
            self.assertTrue(self.overlay._worker_pool.is_shutdown)
            self.assertTrue(self.overlay._is_stopped)

            # Yeniden başlat
            self.overlay._is_stopped = False
            self.overlay._worker_pool = WorkerThreadPool(max_workers=4, thread_name_prefix="CycleWorker")
            self.overlay._schedule_ui_queue_poll()

            # Bir arama yap ve doğrula
            h = self.overlay.lookup_text("Zyklus")
            self.assertIsNotNone(h)
            h.join(timeout=1.0)
            self.overlay._poll_ui_queue()

        self.overlay.stop()

    def test_in_flight_tasks_on_overlay_stop(self):
        """Çalışmakta olan 4 iş varken overlay durdurulursa, dönen sonuçlar UI'a dokunmamalıdır."""
        gate = threading.Event()

        def slow_task(w):
            gate.wait(timeout=2.0)
            return {"original": w, "translation": "blocked"}

        self.mock_translator.translate_and_analyze.side_effect = slow_task

        handles = [self.overlay.lookup_text(f"Warten{i}") for i in range(4)]

        # İşler çalışırken overlay'i derhal durdur
        self.overlay.stop()

        # Kilitleri aç ve iş parçacıklarının sonlanmasını bekle
        gate.set()
        for h in handles:
            if h:
                h.join(timeout=2.0)

        self.overlay._poll_ui_queue()
        # Durdurulmuş overlay'de HUD çağrısı 0 olmalıdır
        self.overlay._show_hud.assert_not_called()


if __name__ == "__main__":
    unittest.main()
