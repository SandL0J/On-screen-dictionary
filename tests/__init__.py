"""
Birim test paketi ortak kurulumu.
Tüm testlerin gerçek %APPDATA% yerine geçici bir klasörde çalışmasını garanti eder.
"""
import os
import shutil
import tempfile
import atexit

# Test süresince kullanılacak geçici veri klasörü
_TEST_DATA_DIR = tempfile.mkdtemp(prefix="ekran_sozlugu_test_data_")
os.environ["EKRAN_SOZLUGU_DATA_DIR"] = _TEST_DATA_DIR


def _cleanup_test_data_dir():
    try:
        shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)
    except Exception:
        pass


atexit.register(_cleanup_test_data_dir)
