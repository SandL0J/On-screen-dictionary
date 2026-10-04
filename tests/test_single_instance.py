"""
Birim testleri: Tek Uygulama Örneği (Single Instance Mutex) ve Pencere Öne Getirme
Win32 API tipleri (HANDLE, DWORD, BOOL), Mutex edinimi, çakışma (183) tespiti,
serbest bırakma ve mevcut pencereyi geri yükleme.
"""
import sys
import os
import time
import unittest
from unittest.mock import patch, MagicMock

import main


class TestSingleInstanceMutex(unittest.TestCase):
    def setUp(self):
        # Test öncesinde mutex durumunu sıfırla
        main._release_single_instance_mutex()

    def tearDown(self):
        main._release_single_instance_mutex()

    def test_setup_win32_api_types(self):
        """Win32 API fonksiyonlarının argtypes ve restype değerlerinin 64-bit uyumlu HANDLE türleriyle tanımlandığını doğrular."""
        if sys.platform != "win32":
            self.skipTest("Yalnızca Windows platformunda çalışır.")

        kernel32, user32 = main._setup_win32_api()
        self.assertIsNotNone(kernel32)
        self.assertIsNotNone(user32)

        # kernel32 türleri
        self.assertEqual(len(kernel32.CreateMutexW.argtypes), 3)
        self.assertIsNotNone(kernel32.CreateMutexW.restype)
        self.assertEqual(len(kernel32.CloseHandle.argtypes), 1)
        self.assertIsNotNone(kernel32.CloseHandle.restype)
        self.assertIsNotNone(kernel32.GetLastError.restype)

        # user32 türleri
        self.assertEqual(len(user32.FindWindowW.argtypes), 2)
        self.assertIsNotNone(user32.FindWindowW.restype)
        self.assertEqual(len(user32.ShowWindow.argtypes), 2)
        self.assertIsNotNone(user32.ShowWindow.restype)
        self.assertEqual(len(user32.SetForegroundWindow.argtypes), 1)
        self.assertIsNotNone(user32.SetForegroundWindow.restype)

    def test_acquire_and_release_single_instance_mutex(self):
        """Benzersiz bir mutex adıyla edinim, serbest bırakma ve yeniden edinim döngüsünü doğrular."""
        if sys.platform != "win32":
            self.skipTest("Yalnızca Windows platformunda çalışır.")

        test_mutex_name = f"EkranSozlugu_TestMutex_{os.getpid()}_{int(time.time() * 1000)}"

        # 1. İlk edinim başarılı olmalı
        acquired = main._acquire_single_instance_mutex(test_mutex_name)
        self.assertTrue(acquired)
        self.assertIsNotNone(main._SINGLE_INSTANCE_MUTEX)

        # 2. Serbest bırak
        main._release_single_instance_mutex()
        self.assertIsNone(main._SINGLE_INSTANCE_MUTEX)

        # 3. Serbest bırakıldıktan sonra tekrar edinilebilmeli
        reacquired = main._acquire_single_instance_mutex(test_mutex_name)
        self.assertTrue(reacquired)
        self.assertIsNotNone(main._SINGLE_INSTANCE_MUTEX)

        # Temizlik
        main._release_single_instance_mutex()

    def test_acquire_single_instance_mutex_conflict_detection(self):
        """Aynı mutex adına sahip ikinci çağrının ERROR_ALREADY_EXISTS (183) alıp False dönmesini doğrular."""
        if sys.platform != "win32":
            self.skipTest("Yalnızca Windows platformunda çalışır.")

        kernel32, _ = main._setup_win32_api()
        if not kernel32:
            self.skipTest("kernel32 API bulunamadı.")

        test_mutex_name = f"EkranSozlugu_ConflictTest_{os.getpid()}_{int(time.time() * 1000)}"

        # İlk tutamacı doğrudan Win32 API ile oluştur
        h1 = kernel32.CreateMutexW(None, False, test_mutex_name)
        self.assertTrue(bool(h1))

        try:
            # Şimdi ana uygulamanın mutex edinme fonksiyonu çağrıldığında çakışmayı (183) yakalayıp False dönmeli
            acquired = main._acquire_single_instance_mutex(test_mutex_name)
            self.assertFalse(acquired, "Mevcut mutex varken _acquire_single_instance_mutex False dönmelidir.")
            self.assertIsNone(main._SINGLE_INSTANCE_MUTEX)
        finally:
            kernel32.CloseHandle(h1)

    def test_restore_existing_window_not_found(self):
        """Pencere bulunamadığında _restore_existing_window False dönmelidir."""
        if sys.platform != "win32":
            self.skipTest("Yalnızca Windows platformunda çalışır.")

        mock_user32 = MagicMock()
        mock_user32.FindWindowW.return_value = 0

        with patch("main._setup_win32_api", return_value=(MagicMock(), mock_user32)):
            restored = main._restore_existing_window()
            self.assertFalse(restored)
            mock_user32.ShowWindow.assert_not_called()
            mock_user32.SetForegroundWindow.assert_not_called()

    def test_restore_existing_window_found(self):
        """Pencere bulunduğunda SW_RESTORE (9) ve SetForegroundWindow çağrılmalıdır."""
        if sys.platform != "win32":
            self.skipTest("Yalnızca Windows platformunda çalışır.")

        mock_user32 = MagicMock()
        mock_user32.FindWindowW.return_value = 999888

        with patch("main._setup_win32_api", return_value=(MagicMock(), mock_user32)):
            restored = main._restore_existing_window()
            self.assertTrue(restored)
            mock_user32.ShowWindow.assert_called_once_with(999888, 9)
            mock_user32.SetForegroundWindow.assert_called_once_with(999888)


if __name__ == "__main__":
    unittest.main()
