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

# Dış ağ erişimini izole etme denetimi (EKRAN_SOZLUGU_OFFLINE_TEST=1)
if os.environ.get("EKRAN_SOZLUGU_OFFLINE_TEST") in ("1", "true", "True"):
    import socket
    _original_socket_connect = socket.socket.connect

    def _guard_offline_connect(self, address):
        host = address[0] if isinstance(address, (tuple, list)) else address
        # Yerel loopback bağlantılarına (yerel mock sunucuları vb.) izin ver
        if str(host).lower() in ("127.0.0.1", "localhost", "::1"):
            return _original_socket_connect(self, address)
        raise OSError(f"Dış ağ erişimi engellendi (EKRAN_SOZLUGU_OFFLINE_TEST=1): Hedef {address}")

    socket.socket.connect = _guard_offline_connect
