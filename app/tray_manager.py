"""
Sistem Tepsisi (System Tray) Yöneticisi
Uygulama arka planda çalışırken Windows sistem tepsisinde simge gösterir.
Kullanıcı simgeye sağ tıklayarak:
  - Çubuğu gösterebilir/gizleyebilir
  - Ayarları açabilir
  - Uygulamayı tamamen kapatabilir
"""
import threading
import tkinter as tk
from typing import Callable, Optional

try:
    import pystray
    from PIL import Image, ImageDraw
    PYSTRAY_AVAILABLE = True

    # Windows üzerinde başsız (headless), sanal veya kısıtlı masaüstü oturumlarında
    # pystray'in GetCursorPos çağrısının PermissionError (WinError 5) vermesini önle
    if hasattr(pystray, "_win32"):
        import pystray._win32 as _pystray_win32
        _orig_get_cursor_pos = getattr(_pystray_win32.win32, "GetCursorPos", None)
        if _orig_get_cursor_pos is not None:
            def _safe_get_cursor_pos(pt_ref):
                try:
                    return _orig_get_cursor_pos(pt_ref)
                except Exception:
                    try:
                        pt_ref._obj.x = 100
                        pt_ref._obj.y = 100
                    except Exception:
                        pass
                    return 1
            _pystray_win32.win32.GetCursorPos = _safe_get_cursor_pos
except ImportError:
    PYSTRAY_AVAILABLE = False


def _build_icon_image(size: int = 64) -> "Image.Image":
    """
    Küçük bir 'DE' yazılı koyu renkli tray ikonu oluşturur.
    Harici dosyaya gerek kalmadan bellekte üretilir.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Yuvarlak koyu arka plan
    draw.ellipse([2, 2, size - 2, size - 2], fill=(24, 24, 27, 230))
    # 'DE' metni
    text_x = size // 2 - 11
    text_y = size // 2 - 9
    draw.text((text_x, text_y), "DE", fill=(99, 102, 241), font=None)
    return img


class TrayManager:
    """
    Windows sistem tepsisi yöneticisi.
    Uygulama penceresi gizliyken bile çalışmaya devam eder
    ve tray simgesi üzerinden kontrol sağlanır.
    """

    def __init__(
        self,
        on_show: Callable[[], None],
        on_hide: Callable[[], None],
        on_open_settings: Callable[[], None],
        on_quit: Callable[[], None],
        root: Optional[tk.Tk] = None,
        on_open_wizard: Optional[Callable[[], None]] = None,
        post_to_ui: Optional[Callable[[Callable], None]] = None,
    ):
        self.on_show = on_show
        self.on_hide = on_hide
        self.on_open_settings = on_open_settings
        self.on_quit = on_quit
        self.root = root
        self.on_open_wizard = on_open_wizard
        self.post_to_ui = post_to_ui
        self._icon: Optional["pystray.Icon"] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Tray ikonunu arka plan thread'inde başlatır."""
        if not PYSTRAY_AVAILABLE:
            print("Uyarı: pystray kurulu değil, sistem tepsisi devre dışı.")
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Tray ikonunu durdurur ve tepsiden kaldırır."""
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass

    def _tk_call(self, fn: Callable):
        """Tkinter thread'ine güvenli geçiş sağlar."""
        if threading.current_thread() is threading.main_thread():
            fn()
            return

        if self.post_to_ui:
            self.post_to_ui(fn)
        else:
            print("[TrayManager UYARI] Worker thread'den Tk çağrısı reddedildi: UI dispatcher (post_to_ui) tanımlı değil.")

    def _run(self):
        icon_image = _build_icon_image(64)
        menu = pystray.Menu(
            pystray.MenuItem(
                "🇩🇪 Ekran Sözlüğü",
                lambda icon, item: self._tk_call(self.on_show),
                default=True,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "📋 Çubuğu Göster",
                lambda icon, item: self._tk_call(self.on_show),
            ),
            pystray.MenuItem(
                "— Çubuğu Gizle",
                lambda icon, item: self._tk_call(self.on_hide),
            ),
            pystray.MenuItem(
                "⚙️ Ayarlar",
                lambda icon, item: self._tk_call(self.on_open_settings),
            ),
            pystray.MenuItem(
                "🚀 Başlangıç Rehberi",
                lambda icon, item: self._tk_call(self.on_open_wizard) if self.on_open_wizard else self._tk_call(self.on_open_settings),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "✕ Çıkış",
                lambda icon, item: self._tk_call(self.on_quit),
            ),
        )
        self._icon = pystray.Icon(
            "ekran_sozlugu",
            icon_image,
            "Ekran Sözlüğü • Tab+Space ile OCR",
            menu,
        )
        self._icon.run()
