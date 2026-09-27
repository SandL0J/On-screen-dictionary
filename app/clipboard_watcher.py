"""
Pano Dinleyici Modülü (Clipboard Watcher)
Kullanıcı ekrandaki bir kelimeyi veya cümleyi seçip Ctrl+C yaptığında otomatik olarak yakalar.
Arka planda hafif bir iş parçacığında çalışır ve CPU tüketimi ihmal edilebilir düzeydedir.
"""
import time
import threading
import ctypes
import re
from typing import Callable, Optional

# Win32 API Tanımları
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.OpenClipboard.argtypes = [ctypes.c_void_p]
user32.OpenClipboard.restype = ctypes.c_bool
user32.CloseClipboard.restype = ctypes.c_bool
user32.GetClipboardData.argtypes = [ctypes.c_uint]
user32.GetClipboardData.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
kernel32.GlobalUnlock.restype = ctypes.c_bool

CF_UNICODETEXT = 13


def get_clipboard_text() -> Optional[str]:
    """Sistem panosundaki UTF-16 metni güvenli bir şekilde çeker."""
    if not user32.OpenClipboard(None):
        return None
    try:
        h_mem = user32.GetClipboardData(CF_UNICODETEXT)
        if not h_mem:
            return None
        p_mem = kernel32.GlobalLock(h_mem)
        if not p_mem:
            return None
        text = ctypes.c_wchar_p(p_mem).value
        kernel32.GlobalUnlock(h_mem)
        return text
    except Exception:
        return None
    finally:
        user32.CloseClipboard()


class ClipboardWatcher:
    def __init__(self, on_text_detected: Callable[[str], None], check_interval: float = 0.35):
        self.on_text_detected = on_text_detected
        self.check_interval = check_interval
        self._running = False
        self._enabled = True
        self._thread: Optional[threading.Thread] = None
        self._last_text = ""

    def start(self):
        """Pano dinleyicisini başlatır."""
        if self._running:
            return
        self._running = True
        # Mevcut panoyu ilk metin olarak kaydet ki uygulama başlar başlamaz popup açılmasın
        initial_text = get_clipboard_text() or ""
        self._last_text = initial_text.strip()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Pano dinleyicisini durdurur."""
        self._running = False

    def set_enabled(self, enabled: bool):
        """Dinlemeyi geçici olarak açar veya kapatır."""
        self._enabled = enabled

    def is_enabled(self) -> bool:
        return self._enabled

    def _loop(self):
        while self._running:
            try:
                if self._enabled:
                    current_text = get_clipboard_text()
                    if current_text:
                        clean = current_text.strip()
                        if clean and clean != self._last_text:
                            self._last_text = clean
                            if self._is_valid_candidate(clean):
                                self.on_text_detected(clean)
            except Exception:
                pass
            time.sleep(self.check_interval)

    def _is_valid_candidate(self, text: str) -> bool:
        """Kopyalanan metnin çeviriye uygun olup olmadığını doğrular."""
        if len(text) > 500:  # Çok uzun metinleri atla
            return False
        # Sadece sayılardan mı oluşuyor?
        if text.replace(" ", "").isdigit():
            return False
        # URL veya dosya yolu mu?
        if text.startswith(("http://", "https://", "www.", "file://", "C:\\", "D:\\")):
            return False
        # Çok fazla özel karakter var mı (örn: kod blokları)?
        special_chars = len(re.findall(r"[{}\[\]<>=;\\/@#$%^&*]", text))
        if special_chars > 4:
            return False
        return True
