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

from app.security import is_sensitive_clipboard_text

# Win32 API Tanımları
try:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    IS_WINDOWS = True
except (AttributeError, OSError):
    user32 = None
    kernel32 = None
    IS_WINDOWS = False

if IS_WINDOWS and user32 and kernel32:
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
SYNTHETIC_EXTRA_INFO = 0x535A4C51  # 'SZLQ' - Klavye kancasının (hook) ayırt etmesi için özel işaretçi
KEYEVENTF_KEYUP = 0x0002
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_C = 0x43


def get_clipboard_text() -> Optional[str]:
    """Sistem panosundaki UTF-16 metni güvenli bir şekilde çeker."""
    if not IS_WINDOWS or not user32 or not kernel32:
        return None
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


def copy_selected_text_windows(timeout_ms: int = 100) -> Optional[str]:
    """
    Windows üzerinde aktif penceredeki seçili metni panoya kopyalamak için
    Ctrl+C tuş kombinasyonunu simüle eder ve güncel pano metnini döner.

    1. Kullanıcı Alt tuşunu basılı tutuyorsa (ör. Alt+C basarken),
       önce Alt tuşunu geçici olarak serbest bırakır.
    2. Ardından Ctrl+C simülasyonunu çalıştırır.
    3. Panonun hedef uygulama tarafından doldurulması için bekler.
    4. Kopyalanan güncel metni döner.
    """
    if not IS_WINDOWS or not user32:
        return None

    try:
        # 1. Alt tuşunu geçici olarak serbest bırak (kullanıcının parmağı halen Alt'ta olabilir)
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, SYNTHETIC_EXTRA_INFO)
        time.sleep(0.015)

        # 2. Ctrl+C tuş kombinasyonunu gönder
        user32.keybd_event(VK_CONTROL, 0, 0, SYNTHETIC_EXTRA_INFO)
        user32.keybd_event(VK_C, 0, 0, SYNTHETIC_EXTRA_INFO)
        time.sleep(0.015)
        user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, SYNTHETIC_EXTRA_INFO)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, SYNTHETIC_EXTRA_INFO)

        # 3. Panonun hedef uygulama tarafından doldurulmasını bekle
        wait_steps = max(1, timeout_ms // 20)
        for _ in range(wait_steps):
            time.sleep(0.02)
            txt = get_clipboard_text()
            if txt and txt.strip():
                return txt.strip()
        return get_clipboard_text()
    except Exception as e:
        print(f"Seçili metin kopyalama simülasyonu hatası: {e}")
        return None


class ClipboardWatcher:
    def __init__(
        self,
        on_text_detected: Optional[Callable[[str], None]] = None,
        check_interval: float = 0.35,
        enabled: bool = False
    ):
        self.on_text_detected = on_text_detected or (lambda t: None)
        self.check_interval = check_interval
        self._running = False
        self._enabled = enabled
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
        # Hassas pano verilerini filtrele (parola, API anahtarı, token, IBAN, kart vb.)
        if is_sensitive_clipboard_text(text):
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
