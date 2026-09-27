"""
Windows Genel Kısayol Tuşu Yöneticisi (Global Hotkey Manager)
Düşük Seviyeli Klavye Kancası (Low-Level Keyboard Hook - WH_KEYBOARD_LL) ile:
- Tab+Space (Tab ve Boşluk ile anında video/ekran OCR seçici)
- Alt+H (Yüzen mini çubuğu gizle/göster)
- Alt+C (Panodaki kelimeyi hemen çevir)
- Ctrl+Space, Alt+X, F2 veya kullanıcının tanımladığı herhangi bir tuş kombinasyonunu
tüm video oynatıcılarda (YouTube, Netflix, VLC) ve arka planda çalışan uygulamalarda
gecikme yapmadan ve normal yazmayı engellemeden sorunsuz yakalar.
"""
import ctypes
from ctypes import wintypes
import threading
import time
from typing import Callable, Dict, Any, Optional, Set, Tuple

try:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    IS_WINDOWS = True
except (AttributeError, OSError):
    user32 = None
    kernel32 = None
    IS_WINDOWS = False

# Win32 Kanca ve Mesaj Sabitleri
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012

# Win32 RegisterHotKey Eski Modifier Sabitleri (Geriye Uyumluluk İçin)
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

# Standart Sanal Tuş Kodları (Virtual Keys)
VK_TAB = 0x09
VK_SPACE = 0x20
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_BACK = 0x08
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12       # Alt
VK_PAUSE = 0x13
VK_CAPITAL = 0x14
VK_PRIOR = 0x21      # Page Up
VK_NEXT = 0x22       # Page Down
VK_END = 0x23
VK_HOME = 0x24
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_SNAPSHOT = 0x2C   # Print Screen
VK_INSERT = 0x2D
VK_DELETE = 0x2E
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU = 0xA4
VK_RMENU = 0xA5

VK_X = 0x58
VK_H = 0x48
VK_C = 0x43
VK_S = 0x53

# Sistem genelinde tanınan değiştirici tuşlar (Modifiers)
ALL_MODIFIERS = {VK_CONTROL, VK_MENU, VK_SHIFT, VK_LWIN}

# Sol/sağ ayrımı olan tuşları kanonik tuş koduna eşle
VK_CANONICAL_MAP = {
    VK_LMENU: VK_MENU,
    VK_RMENU: VK_MENU,
    VK_LCONTROL: VK_CONTROL,
    VK_RCONTROL: VK_CONTROL,
    VK_LSHIFT: VK_SHIFT,
    VK_RSHIFT: VK_SHIFT,
    VK_RWIN: VK_LWIN,
}

# İsim -> VK Kodu Eşlemesi
KEY_NAME_TO_VK = {
    # Değiştiriciler
    "alt": VK_MENU,
    "menu": VK_MENU,
    "option": VK_MENU,
    "ctrl": VK_CONTROL,
    "control": VK_CONTROL,
    "shift": VK_SHIFT,
    "win": VK_LWIN,
    "windows": VK_LWIN,
    "cmd": VK_LWIN,
    "super": VK_LWIN,

    # Özel tuşlar
    "tab": VK_TAB,
    "space": VK_SPACE,
    "bosluk": VK_SPACE,
    "boşluk": VK_SPACE,
    "spacebar": VK_SPACE,
    "enter": VK_RETURN,
    "return": VK_RETURN,
    "esc": VK_ESCAPE,
    "escape": VK_ESCAPE,
    "backspace": VK_BACK,
    "capslock": VK_CAPITAL,
    "caps_lock": VK_CAPITAL,
    "printscreen": VK_SNAPSHOT,
    "prtscr": VK_SNAPSHOT,
    "insert": VK_INSERT,
    "ins": VK_INSERT,
    "delete": VK_DELETE,
    "del": VK_DELETE,
    "home": VK_HOME,
    "end": VK_END,
    "pageup": VK_PRIOR,
    "page_up": VK_PRIOR,
    "pgup": VK_PRIOR,
    "pagedown": VK_NEXT,
    "page_down": VK_NEXT,
    "pgdn": VK_NEXT,
    "up": VK_UP,
    "down": VK_DOWN,
    "left": VK_LEFT,
    "right": VK_RIGHT,
}

# F1-F24 tuşları
for _i in range(1, 25):
    KEY_NAME_TO_VK[f"f{_i}"] = 0x70 + (_i - 1)

# A-Z harfleri (0x41 - 0x5A)
for _c in range(ord('a'), ord('z') + 1):
    KEY_NAME_TO_VK[chr(_c)] = 0x41 + (_c - ord('a'))

# 0-9 rakamları (0x30 - 0x39)
for _n in range(ord('0'), ord('9') + 1):
    KEY_NAME_TO_VK[chr(_n)] = 0x30 + (_n - ord('0'))

# Numpad tuşları
for _n in range(10):
    KEY_NAME_TO_VK[f"numpad{_n}"] = 0x60 + _n
    KEY_NAME_TO_VK[f"num{_n}"] = 0x60 + _n

# Ters Eşleme: VK Kodu -> Gösterim İsmi
VK_TO_DISPLAY_NAME = {
    VK_TAB: "Tab",
    VK_SPACE: "Space",
    VK_RETURN: "Enter",
    VK_ESCAPE: "Esc",
    VK_BACK: "Backspace",
    VK_CONTROL: "Ctrl",
    VK_MENU: "Alt",
    VK_SHIFT: "Shift",
    VK_LWIN: "Win",
    VK_DELETE: "Del",
    VK_INSERT: "Ins",
    VK_HOME: "Home",
    VK_END: "End",
    VK_PRIOR: "PgUp",
    VK_NEXT: "PgDn",
    VK_UP: "Up",
    VK_DOWN: "Down",
    VK_LEFT: "Left",
    VK_RIGHT: "Right",
}
for _i in range(1, 25):
    VK_TO_DISPLAY_NAME[0x70 + (_i - 1)] = f"F{_i}"
for _c in range(ord('a'), ord('z') + 1):
    VK_TO_DISPLAY_NAME[0x41 + (_c - ord('a'))] = chr(_c).upper()
for _n in range(ord('0'), ord('9') + 1):
    VK_TO_DISPLAY_NAME[0x30 + (_n - ord('0'))] = chr(_n)


def parse_hotkey(combo_str: str) -> frozenset[int]:
    """
    Kısayol metnini (örn: 'tab+space', 'Alt + X', 'ctrl+shift+a')
    kanonik sanal tuş kodları kümesine (frozenset[int]) dönüştürür.
    Geçersiz bir tuş varsa ValueError fırlatır.
    """
    if not combo_str or not combo_str.strip():
        raise ValueError("Kısayol metni boş olamaz.")

    parts = [p.strip().lower() for p in combo_str.split("+") if p.strip()]
    if not parts:
        raise ValueError(f"Geçersiz kısayol formatı: '{combo_str}'")

    vk_codes = set()
    for p in parts:
        if p not in KEY_NAME_TO_VK:
            raise ValueError(f"Tanınmayan tuş: '{p}'")
        vk = KEY_NAME_TO_VK[p]
        canonical = VK_CANONICAL_MAP.get(vk, vk)
        vk_codes.add(canonical)

    return frozenset(vk_codes)


def validate_hotkey_string(combo_str: str) -> Tuple[bool, str]:
    """
    Kısayol metnini doğrular.
    Geçerliyse (True, "") döner; hatalıysa (False, "hata açıklaması") döner.
    """
    try:
        keys = parse_hotkey(combo_str)
        if not keys:
            return False, "En az bir tuş belirtilmelidir."
        return True, ""
    except ValueError as e:
        return False, str(e)


def format_hotkey(combo_str: str) -> str:
    """
    Kullanıcı arayüzünde şık görünüm için kısayol metnini biçimlendirir.
    Örn: 'tab+space' -> 'Tab+Space', 'alt+x' -> 'Alt+X'
    """
    try:
        keys = parse_hotkey(combo_str)
        names = []
        # Önce değiştiriciler
        for mod_vk, mod_name in [(VK_CONTROL, "Ctrl"), (VK_MENU, "Alt"), (VK_SHIFT, "Shift"), (VK_LWIN, "Win")]:
            if mod_vk in keys:
                names.append(mod_name)
        # Sonra diğer tuşlar
        for k in sorted(keys):
            if k not in (VK_CONTROL, VK_MENU, VK_SHIFT, VK_LWIN):
                names.append(VK_TO_DISPLAY_NAME.get(k, f"0x{k:02X}"))
        return "+".join(names)
    except Exception:
        return combo_str.strip().title()


if IS_WINDOWS:
    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("vkCode", wintypes.DWORD),
            ("scanCode", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_size_t),
        ]

    PKBDLLHOOKSTRUCT = ctypes.POINTER(KBDLLHOOKSTRUCT)
    HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
    user32.SetWindowsHookExW.restype = wintypes.HHOOK

    user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
    user32.CallNextHookEx.restype = ctypes.c_longlong

    user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
    user32.UnhookWindowsHookEx.restype = wintypes.BOOL

    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = wintypes.SHORT


class _HotkeyBinding:
    def __init__(self, identifier: Any, required_keys: frozenset[int], callback: Callable[[], None]):
        self.identifier = identifier
        self.required_keys = required_keys
        self.callback = callback
        self.triggered = False


class HotkeyManager:
    """
    Windows Düşük Seviyeli Klavye Kancası (WH_KEYBOARD_LL) tabanlı,
    özelleştirilebilir ve çoklu tuş kombinasyonlarını (Tab+Space, Alt+H, vb.)
    destekleyen genel kısayol yöneticisi.
    """
    def __init__(self, consume_hotkeys: bool = True, verify_physical: bool = False):
        self.consume_hotkeys = consume_hotkeys
        self.verify_physical = verify_physical
        self._thread: Optional[threading.Thread] = None
        self._thread_id: Optional[int] = None
        self._running = False
        self._hook = None
        self._hook_proc_ref = None  # GC tarafından silinmesini önlemek için referans
        self._lock = threading.Lock()

        # Kayıtlı kısayollar: identifier -> _HotkeyBinding
        self._bindings: Dict[Any, _HotkeyBinding] = {}

        # Halihazırda basılı tutulan kanonik tuş kodları
        self._pressed_keys: Set[int] = set()

        # Tüketilen (swallowed) tuş kodları (KeyUp geldiğinde de yakalamak için)
        self._swallowed_keys: Set[int] = set()

        # Geriye dönük uyumluluk için registered_ids listesi
        self._registered_ids = []

    def register(self, identifier: Any, *args, callback: Optional[Callable[[], None]] = None, combo: Optional[str] = None):
        """
        Kısayol kaydeder. Hem yeni esnek imzaları hem de eski Win32 imzasını destekler:
        1. register('ocr', 'tab+space', callback)
        2. register(1, MOD_ALT, VK_X, callback)
        3. register(1, 0, 0, callback)
        4. register('ocr', callback=cb, combo='tab+space')
        """
        resolved_combo: Optional[str] = combo
        resolved_callback: Optional[Callable[[], None]] = callback

        if len(args) == 3:
            # Eski imza: (hotkey_id, mod, vk, callback)
            mod = args[0]
            vk = args[1]
            resolved_callback = args[2]
            if mod or vk:
                # Mod ve VK'dan combo string türet
                parts = []
                if mod & MOD_CONTROL:
                    parts.append("ctrl")
                if mod & MOD_ALT:
                    parts.append("alt")
                if mod & MOD_SHIFT:
                    parts.append("shift")
                if mod & MOD_WIN:
                    parts.append("win")
                if vk in VK_TO_DISPLAY_NAME:
                    parts.append(VK_TO_DISPLAY_NAME[vk].lower())
                else:
                    parts.append(chr(vk).lower() if 0x41 <= vk <= 0x5A else f"0x{vk:02x}")
                resolved_combo = "+".join(parts)
            else:
                # mod=0, vk=0 ise varsayılan ID eşleşmesi
                legacy_defaults = {1: "tab+space", 2: "alt+h", 3: "alt+c"}
                resolved_combo = legacy_defaults.get(identifier, "tab+space")

        elif len(args) == 2:
            # register(id_or_name, combo_str, callback)
            resolved_combo = args[0]
            resolved_callback = args[1]

        elif len(args) == 1:
            if callable(args[0]):
                resolved_callback = args[0]
            elif isinstance(args[0], str):
                resolved_combo = args[0]

        if not resolved_combo:
            legacy_defaults = {1: "tab+space", 2: "alt+h", 3: "alt+c", "ocr": "tab+space", "overlay": "alt+h", "clipboard": "alt+c"}
            resolved_combo = legacy_defaults.get(identifier, "tab+space")

        if not resolved_callback:
            raise ValueError("Kısayol için geçerli bir callback fonksiyonu belirtilmelidir.")

        parsed_keys = parse_hotkey(resolved_combo)
        with self._lock:
            self._bindings[identifier] = _HotkeyBinding(identifier, parsed_keys, resolved_callback)
            if identifier not in self._registered_ids:
                self._registered_ids.append(identifier)

    def register_hotkey(self, identifier: Any, combo_str: str, callback: Callable[[], None]):
        """Yeni stil kısayol kaydetme metodu."""
        self.register(identifier, combo_str, callback)

    def unregister(self, identifier: Any):
        """Kayıtlı bir kısayolu siler."""
        with self._lock:
            self._bindings.pop(identifier, None)
            if identifier in self._registered_ids:
                self._registered_ids.remove(identifier)

    def clear(self):
        """Tüm kayıtlı kısayolları temizler."""
        with self._lock:
            self._bindings.clear()
            self._registered_ids.clear()

    def start(self):
        """Kısayol dinleme kancasını arka plan iş parçacığında başlatır."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Kısayol dinleyicisini durdurur ve kancayı kaldırır."""
        self._running = False
        if IS_WINDOWS:
            if self._hook:
                try:
                    user32.UnhookWindowsHookEx(self._hook)
                except Exception:
                    pass
                self._hook = None
            if self._thread_id:
                try:
                    user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
                except Exception:
                    pass
        self._pressed_keys.clear()
        self._swallowed_keys.clear()

    def _safe_invoke(self, callback: Callable[[], None]):
        """Callback fonksiyonunu kanca iş parçacığını bekletmeden güvenle çalıştırır."""
        try:
            callback()
        except Exception as e:
            print(f"Kısayol tetikleme hatası: {e}")

    def _handle_key_event(self, vk: int, is_down: bool) -> bool:
        """
        Klavye olayını işler ve tuş durumlarını günceller.
        Tuş tüketilecekse (swallow) True döner, aksi halde False döner.
        Bu metod testlerde doğrudan simülasyon için de kullanılabilir.
        """
        canonical_vk = VK_CANONICAL_MAP.get(vk, vk)

        with self._lock:
            if is_down:
                self._pressed_keys.add(canonical_vk)
                self._pressed_keys.add(vk)

                # Windows ortamında fiziksel tuş durumu teyidi (Opsiyonel / Desync önleyici)
                if self.verify_physical and IS_WINDOWS and user32:
                    for k in list(self._pressed_keys):
                        try:
                            # 0x8000 biti tuşun şu an fiziksel olarak basılı olduğunu belirtir
                            if not (user32.GetAsyncKeyState(k) & 0x8000):
                                self._pressed_keys.discard(k)
                        except Exception:
                            pass

                # Aktif basılı tutulan değiştiriciler
                current_modifiers = self._pressed_keys & ALL_MODIFIERS

                # Eşleşen kısayolları kontrol et
                swallow = False
                for binding in self._bindings.values():
                    # Kısayol bu tuşu içeriyor mu?
                    if canonical_vk in binding.required_keys or vk in binding.required_keys:
                        # Değiştiriciler tam uyuşuyor mu?
                        required_modifiers = binding.required_keys & ALL_MODIFIERS
                        if current_modifiers == required_modifiers:
                            # Kısayolun gerektirdiği tüm tuşlar basılı mı?
                            if binding.required_keys.issubset(self._pressed_keys):
                                # Fiziksel tuş durumu teyidi
                                if self.verify_physical and IS_WINDOWS and user32:
                                    phys_down = all(
                                        bool(user32.GetAsyncKeyState(k) & 0x8000)
                                        for k in binding.required_keys
                                    )
                                    if not phys_down:
                                        continue

                                if not binding.triggered:
                                    binding.triggered = True
                                    threading.Thread(
                                        target=self._safe_invoke,
                                        args=(binding.callback,),
                                        daemon=True
                                    ).start()

                                    if self.consume_hotkeys:
                                        self._swallowed_keys.add(vk)
                                        swallow = True

                return swallow

            else:  # KeyUp
                self._pressed_keys.discard(vk)
                self._pressed_keys.discard(canonical_vk)

                # Bırakılan tuşu içeren kısayolların tetiklenme durumunu sıfırla
                for binding in self._bindings.values():
                    if canonical_vk in binding.required_keys or vk in binding.required_keys:
                        binding.triggered = False

                if vk in self._swallowed_keys:
                    self._swallowed_keys.remove(vk)
                    return True if self.consume_hotkeys else False

                return False

    def _hook_callback(self, nCode: int, wParam: int, lParam: int) -> int:
        """Windows WH_KEYBOARD_LL geri çağırma fonksiyonu."""
        if nCode < 0 or not lParam or not self._running:
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        try:
            p_kbd = ctypes.cast(lParam, PKBDLLHOOKSTRUCT).contents
            vk = p_kbd.vkCode
            is_down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
            is_up = wParam in (WM_KEYUP, WM_SYSKEYUP)

            if is_down:
                swallow = self._handle_key_event(vk, True)
                if swallow:
                    return 1
            elif is_up:
                swallow = self._handle_key_event(vk, False)
                if swallow:
                    return 1

        except Exception as e:
            print(f"Hook işleme hatası: {e}")

        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    def _run_loop(self):
        """Kanca iş parçacığının mesaj döngüsü."""
        if not IS_WINDOWS:
            return

        self._thread_id = kernel32.GetCurrentThreadId()
        self._hook_proc_ref = HOOKPROC(self._hook_callback)

        self._hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self._hook_proc_ref,
            None,
            0
        )

        if not self._hook:
            err = kernel32.GetLastError()
            print(f"Düşük seviyeli klavye kancası başlatılamadı. Hata Kodu: {err}")
            return

        msg = wintypes.MSG()
        while self._running:
            b_ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if b_ret <= 0:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self._hook:
            try:
                user32.UnhookWindowsHookEx(self._hook)
            except Exception:
                pass
            self._hook = None
