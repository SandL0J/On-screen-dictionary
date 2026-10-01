"""
Canlı Fare Üzerine Gelme ve Fare Yan Tuşları (Mouse 4/5) ile Çeviri Takip Modülü
Kullanıcı altyazı veya ekran üzerindeki bir kelimede fareyi getirdiğinde:
- Farenin yan tuşuna (XBUTTON1 / XBUTTON2 - Mouse 4/5) bastığında ANINDA (0 gecikme)
  farenin altındaki kelimeyi okur ve çevirir.
- Win32 GDI (BitBlt) ile donanımsal ve doğrudan ekran yakalama yapar (PIL ImageGrab hatası vermez).
- En yakın kelime (proximity matching) algoritması sayesinde imleç kelimenin birkaç piksel
  yanında olsa bile hedef kelimeyi kaçırmaz.
- Tarayıcının geri/ileri gitmesini engelleyerek video akışını kesintisiz tutar.
"""
import ctypes
from ctypes import wintypes
import threading
import time
import math
from typing import Callable, Optional, Dict, Any, Tuple
from PIL import Image

try:
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    kernel32 = ctypes.windll.kernel32
    IS_WINDOWS = True
except (AttributeError, OSError):
    user32 = None
    gdi32 = None
    kernel32 = None
    IS_WINDOWS = False

# Win32 Sanal Tuş Kodları
VK_CONTROL = 0x11
VK_MENU = 0x12       # Alt
VK_SHIFT = 0x10
VK_MBUTTON = 0x04    # Orta Tuş (Tekerlek Tıklaması)
VK_XBUTTON1 = 0x05   # Fare Yan Tuş 1 (Mouse 4 / Geri)
VK_XBUTTON2 = 0x06   # Fare Yan Tuş 2 (Mouse 5 / İleri)

# Win32 Fare Kanca Sabitleri
WH_MOUSE_LL = 14
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_RBUTTONDOWN = 0x0204
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
WM_NCXBUTTONDOWN = 0x00AB
WM_NCXBUTTONUP = 0x00AC
WM_QUIT = 0x0012

# GDI BitBlt Raster İşlem Sabitleri
SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
SRCCOPY_CAPTUREBLT = SRCCOPY | CAPTUREBLT


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


if IS_WINDOWS:
    HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


def get_current_cursor_pos() -> Tuple[int, int]:
    """Ekrandaki anlık fare imleç koordinatlarını döner."""
    if IS_WINDOWS and user32:
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return int(pt.x), int(pt.y)
    return 0, 0


def is_key_down(vk_code: int) -> bool:
    """Verilen sanal tuşun basılı olup olmadığını kontrol eder."""
    if IS_WINDOWS and user32:
        return bool(user32.GetAsyncKeyState(vk_code) & 0x8000)
    return False


def capture_screen_rect_gdi(x: int, y: int, w: int, h: int) -> Optional[Image.Image]:
    """
    Win32 GDI BitBlt (CAPTUREBLT | SRCCOPY) kullanarak ekrandan donanımsal ve doğrudan görüntü yakalar.
    Katmanlı pencereleri, donanım hızlandırmalı video altyazılarını ve şeffaf katmanları kaçırmaz.
    GDI tanıtıcılarını (handles) daima finally bloğunda serbest bırakarak kaynak sızıntılarını önler.
    Çoklu monitörlerdeki negatif sanal ekran koordinatlarını destekler.
    """
    if not IS_WINDOWS or not user32 or not gdi32:
        return None

    w = max(int(w), 10)
    h = max(int(h), 10)
    x = int(x)
    y = int(y)

    hwin = None
    hwindc = None
    srcdc = None
    bmp = None
    old_bmp = None

    try:
        hwin = user32.GetDesktopWindow()
        if not hwin:
            return None
        hwindc = user32.GetWindowDC(hwin)
        if not hwindc:
            return None
        srcdc = gdi32.CreateCompatibleDC(hwindc)
        if not srcdc:
            return None
        bmp = gdi32.CreateCompatibleBitmap(hwindc, w, h)
        if not bmp:
            return None
        old_bmp = gdi32.SelectObject(srcdc, bmp)

        # Ekran görüntüsünü kopyala (SRCCOPY | CAPTUREBLT)
        gdi32.BitBlt(srcdc, 0, 0, w, h, hwindc, x, y, SRCCOPY_CAPTUREBLT)

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h  # Üstten alta (Top-down DIB)
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0

        buffer = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(hwindc, bmp, 0, h, buffer, ctypes.byref(bmi), 0)

        return Image.frombuffer("RGBA", (w, h), buffer, "raw", "BGRA", 0, 1).convert("RGB")
    except Exception as e:
        print(f"GDI Ekran yakalama hatası: {e}")
        return None
    finally:
        if srcdc and old_bmp:
            try:
                gdi32.SelectObject(srcdc, old_bmp)
            except Exception:
                pass
        if bmp:
            try:
                gdi32.DeleteObject(bmp)
            except Exception:
                pass
        if srcdc:
            try:
                gdi32.DeleteDC(srcdc)
            except Exception:
                pass
        if hwin and hwindc:
            try:
                user32.ReleaseDC(hwin, hwindc)
            except Exception:
                pass


class HoverTracker:
    """
    Fare imlecini izleyen; fare yan tuşları (Mouse 4/5) veya duraklama anında
    mikro OCR ve çeviri tetikleyen akıllı takipçi.
    """

    def __init__(
        self,
        ocr_engine,
        translator,
        on_word_hover: Callable[[Dict[str, Any], int, int], None],
        on_hover_leave: Callable[[], None],
        on_loading: Optional[Callable[[int, int], None]] = None,
        on_not_found: Optional[Callable[[int, int], None]] = None,
        hover_delay_ms: int = 300,
        trigger_mode: str = "mouse_side",  # "mouse_side", "always", "ctrl", "alt", "shift", "mouse_middle"
        enabled: bool = True,
        consume_xbutton: bool = True,
        crop_width: int = 440,
        crop_height: int = 120,
    ):
        self.ocr_engine = ocr_engine
        self.translator = translator
        self.on_word_hover = on_word_hover
        self.on_hover_leave = on_hover_leave
        self.on_loading = on_loading
        self.on_not_found = on_not_found

        self.hover_delay_sec = max(hover_delay_ms, 150) / 1000.0
        self.trigger_mode = trigger_mode.lower()
        self.enabled = enabled
        self.consume_xbutton = consume_xbutton

        self.crop_width = crop_width
        self.crop_height = crop_height

        self._running = False
        self._hook_thread: Optional[threading.Thread] = None
        self._timer_thread: Optional[threading.Thread] = None
        self._hook_thread_id: Optional[int] = None
        self._mouse_hook = None
        self._hook_proc_ref = None
        self._lock = threading.Lock()

        # Durum Değişkenleri
        self._last_x = -1
        self._last_y = -1
        self._hover_start_time = 0.0
        self._scanned_this_pause = False
        self._active_word: Optional[str] = None
        self._active_word_screen_rect: Optional[Tuple[int, int, int, int]] = None

    def _trigger_loading_feedback(self, cursor_x: int, cursor_y: int):
        """Kullanıcıya tıklama veya tetikleme anında anında görsel geri bildirim verir."""
        if self.on_loading:
            try:
                self.on_loading(cursor_x, cursor_y)
            except Exception:
                pass

    def _trigger_not_found_feedback(self, cursor_x: int, cursor_y: int):
        """Hedef bölgede metin bulunamadığında kullanıcıya bilgi verir."""
        if self.on_not_found:
            try:
                self.on_not_found(cursor_x, cursor_y)
            except Exception:
                pass

    def set_enabled(self, enabled: bool):
        """Hover / Fare takip modunu açar veya kapatır."""
        with self._lock:
            self.enabled = enabled
            if not enabled:
                self._reset_state()
                self._safe_call_leave()

    def is_enabled(self) -> bool:
        return self.enabled

    def update_settings(self, hover_delay_ms: int, trigger_mode: str, consume_xbutton: bool = True):
        """Ayarları dinamik olarak günceller."""
        with self._lock:
            self.hover_delay_sec = max(hover_delay_ms, 150) / 1000.0
            self.trigger_mode = trigger_mode.lower()
            self.consume_xbutton = consume_xbutton

    def start(self):
        """Kanca ve izleme iş parçacıklarını başlatır."""
        if self._running:
            return
        self._running = True

        # 1. Fare Kancası İş Parçacığı (Yan Tuşları anında yakalar ve tüketir)
        if IS_WINDOWS:
            self._hook_thread = threading.Thread(target=self._run_hook_loop, daemon=True)
            self._hook_thread.start()

        # 2. Duraklama ve Tuş İzleme İş Parçacığı (Çift güvence)
        self._timer_thread = threading.Thread(target=self._run_timer_loop, daemon=True)
        self._timer_thread.start()

    def stop(self):
        """Takipçiyi güvenle durdurur ve kancayı kaldırır."""
        self._running = False
        self.enabled = False

        if IS_WINDOWS:
            if self._hook_thread_id:
                try:
                    user32.PostThreadMessageW(self._hook_thread_id, WM_QUIT, 0, 0)
                except Exception:
                    pass
            if self._mouse_hook:
                try:
                    user32.UnhookWindowsHookEx(self._mouse_hook)
                except Exception:
                    pass
                self._mouse_hook = None

        self._reset_state()
        self._safe_call_leave()

    def _reset_state(self):
        self._scanned_this_pause = False
        self._active_word = None
        self._active_word_screen_rect = None

    def _safe_call_leave(self):
        try:
            self.on_hover_leave()
        except Exception as e:
            print(f"Hover leave callback hatası: {e}")

    def _is_trigger_condition_met(self) -> bool:
        """Kullanıcının belirlediği tetikleme kuralını denetler."""
        if self.trigger_mode in ("mouse_side", "mouse_middle"):
            return False  # Yalnızca fare tuşuna basınca çalışır
        elif self.trigger_mode == "ctrl":
            return is_key_down(VK_CONTROL)
        elif self.trigger_mode == "alt":
            return is_key_down(VK_MENU)
        elif self.trigger_mode == "shift":
            return is_key_down(VK_SHIFT)
        return True  # "always" modu

    def _mouse_hook_callback(self, nCode: int, wParam: int, lParam: int) -> int:
        """Windows Düşük Seviyeli Fare Kancası (WH_MOUSE_LL) geri çağırma fonksiyonu."""
        if nCode < 0 or not lParam or not self._running:
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        try:
            # Fare Yan Tuşuna (XBUTTON1 / XBUTTON2 - Mouse 4/5) veya Orta Tuşa (MBUTTON) basıldı
            is_xbutton_down = (wParam in (WM_XBUTTONDOWN, WM_NCXBUTTONDOWN))
            is_mbutton_down = (self.trigger_mode == "mouse_middle" and wParam == WM_MBUTTONDOWN)
            is_trigger_down = is_xbutton_down or is_mbutton_down

            is_xbutton_up = (wParam in (WM_XBUTTONUP, WM_NCXBUTTONUP))
            is_mbutton_up = (self.trigger_mode == "mouse_middle" and wParam == WM_MBUTTONUP)
            is_trigger_up = is_xbutton_up or is_mbutton_up

            if is_trigger_down:
                p_ms = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                cx, cy = int(p_ms.pt.x), int(p_ms.pt.y)

                print(f"[Ekran Sozlugu] Fare Tusuna Basildi (WH_MOUSE_LL)! Konum: ({cx}, {cy})")

                # Kullanıcıya anında görsel geri bildirim ver ("Okunuyor...")
                self._trigger_loading_feedback(cx, cy)

                # Anında farenin altındaki kelimeyi tara
                threading.Thread(
                    target=self._inspect_hover_area,
                    args=(cx, cy),
                    daemon=True
                ).start()

                if self.consume_xbutton and is_xbutton_down:
                    return 1

            elif is_trigger_up:
                if self.consume_xbutton and is_xbutton_up:
                    return 1

            elif wParam == WM_MOUSEMOVE:
                if self._active_word_screen_rect:
                    p_ms = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    cx, cy = int(p_ms.pt.x), int(p_ms.pt.y)
                    rx1, ry1, rx2, ry2 = self._active_word_screen_rect
                    # Kelime etrafında 35px tolerans
                    if not (rx1 - 35 <= cx <= rx2 + 35 and ry1 - 25 <= cy <= ry2 + 25):
                        self._reset_state()
                        self._safe_call_leave()

        except Exception as e:
            print(f"Fare kancası hatası: {e}")

        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    def _run_hook_loop(self):
        """Kanca iş parçacığı mesaj döngüsü."""
        if not IS_WINDOWS:
            return

        self._hook_thread_id = kernel32.GetCurrentThreadId()
        self._hook_proc_ref = HOOKPROC(self._mouse_hook_callback)

        self._mouse_hook = user32.SetWindowsHookExW(
            WH_MOUSE_LL,
            self._hook_proc_ref,
            None,
            0
        )

        if not self._mouse_hook:
            print("Bilgi: WH_MOUSE_LL kancası açılamadı. GetAsyncKeyState yedeği devrede.")
            return

        msg = wintypes.MSG()
        while self._running:
            b_ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if b_ret <= 0:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self._mouse_hook:
            try:
                user32.UnhookWindowsHookEx(self._mouse_hook)
            except Exception:
                pass
            self._mouse_hook = None

    def _run_timer_loop(self):
        """Arka plan zamanlayıcı ve GetAsyncKeyState çift güvenceli tuş izleme döngüsü."""
        check_interval = 0.025  # 25ms
        jitter_threshold = 4
        last_xbtn_down = False

        while self._running:
            time.sleep(check_interval)

            curr_x, curr_y = get_current_cursor_pos()
            now = time.time()

            # 1. GetAsyncKeyState ile Çift Güvenceli Tuş Kontrolü
            xbtn_now = is_key_down(VK_XBUTTON1) or is_key_down(VK_XBUTTON2)
            if self.trigger_mode == "mouse_middle":
                xbtn_now = xbtn_now or is_key_down(VK_MBUTTON)

            if xbtn_now and not last_xbtn_down:
                print(f"[Ekran Sozlugu] Yan tus algilandi (GetAsyncKeyState)! Konum: ({curr_x}, {curr_y})")
                self._trigger_loading_feedback(curr_x, curr_y)
                threading.Thread(target=self._inspect_hover_area, args=(curr_x, curr_y), daemon=True).start()
            last_xbtn_down = xbtn_now

            # 2. Pasif Hover (Sadece fareyi bekletme modu)
            # Eğer pasif hover kapalıysa veya sadece tuş modu seçiliyse bekleme taraması yapma
            if not self.enabled or self.trigger_mode in ("mouse_side", "mouse_middle"):
                continue

            # Tuş gereksinimi kontrolü (always, ctrl, alt, shift)
            if not self._is_trigger_condition_met():
                if self._active_word is not None:
                    self._reset_state()
                    self._safe_call_leave()
                self._hover_start_time = now
                self._last_x, self._last_y = curr_x, curr_y
                continue

            # Fare hareket etti mi?
            dx = abs(curr_x - self._last_x)
            dy = abs(curr_y - self._last_y)

            if dx > jitter_threshold or dy > jitter_threshold:
                self._last_x, self._last_y = curr_x, curr_y
                self._hover_start_time = now
                self._scanned_this_pause = False

                if self._active_word_screen_rect:
                    rx1, ry1, rx2, ry2 = self._active_word_screen_rect
                    if not (rx1 - 35 <= curr_x <= rx2 + 35 and ry1 - 25 <= curr_y <= ry2 + 25):
                        self._reset_state()
                        self._safe_call_leave()
            else:
                # Fare durakladı (Hover)
                if not self._scanned_this_pause and (now - self._hover_start_time) >= self.hover_delay_sec:
                    self._scanned_this_pause = True
                    self._trigger_loading_feedback(curr_x, curr_y)
                    self._inspect_hover_area(curr_x, curr_y)

    def trigger_at_current_cursor(self):
        """Manuel olarak mevcut imleç konumundaki kelimeyi tarar."""
        cx, cy = get_current_cursor_pos()
        self._trigger_loading_feedback(cx, cy)
        self._inspect_hover_area(cx, cy)

    def _inspect_hover_area(self, cursor_x: int, cursor_y: int):
        """İmleç etrafındaki mikro bölgeyi yakalar ve OCR ile farenin altındaki kelimeyi arar."""
        half_w = self.crop_width // 2
        half_h = self.crop_height // 2

        left = cursor_x - half_w
        top = cursor_y - half_h

        try:
            # 1. Donanımsal Win32 GDI ile mikro ekran görüntüsü al
            crop_img = capture_screen_rect_gdi(left, top, self.crop_width, self.crop_height)
            if not crop_img:
                # Fallback: PIL ImageGrab
                from PIL import ImageGrab
                try:
                    crop_img = ImageGrab.grab(bbox=(left, top, left + self.crop_width, top + self.crop_height))
                except Exception:
                    crop_img = None

            if not crop_img:
                print("[Ekran Sozlugu] Ekran goruntusu alinamadi.")
                self._trigger_not_found_feedback(cursor_x, cursor_y)
                return

            # 2. Windows Media OCR ile kelime ve koordinatları çıkar
            boxes = self.ocr_engine.recognize_words_with_boxes(crop_img)
            if not boxes:
                print(f"[Ekran Sozlugu] Imlec etrafinda metin bulunamadi: ({cursor_x}, {cursor_y})")
                self._trigger_not_found_feedback(cursor_x, cursor_y)
                return

            # Farenin mikro görüntüdeki rölatif konumu
            rel_cursor_x = cursor_x - left
            rel_cursor_y = cursor_y - top

            # 3. Akıllı Kelime Eşleştirme (Doğrudan Kutu + En Yakın Komşu)
            target_word = None
            target_box = None
            margin_x = 24
            margin_y = 16

            # 3a. İmleç doğrudan kelime kutusunun içindeyse (en yakın olanı seç)
            candidate_boxes = []
            for b in boxes:
                bx = b["x"]
                by = b["y"]
                bw = b["w"]
                bh = b["h"]

                if (bx - margin_x <= rel_cursor_x <= bx + bw + margin_x) and \
                   (by - margin_y <= rel_cursor_y <= by + bh + margin_y):
                    center_x = bx + bw / 2.0
                    center_y = by + bh / 2.0
                    dist = math.hypot(center_x - rel_cursor_x, center_y - rel_cursor_y)
                    candidate_boxes.append((dist, b))

            if candidate_boxes:
                candidate_boxes.sort(key=lambda item: item[0])
                target_box = candidate_boxes[0][1]
                target_word = target_box["text"].strip()

            # 3b. İmleç birkaç piksel dışındaysa en yakın kelimeyi seç (yakınlık toleransı)
            if not target_word and boxes:
                closest_dist = 999999.0
                best_box = None
                for b in boxes:
                    center_x = b["x"] + b["w"] / 2.0
                    center_y = b["y"] + b["h"] / 2.0
                    dist = math.hypot(center_x - rel_cursor_x, center_y - rel_cursor_y)
                    if dist < closest_dist:
                        closest_dist = dist
                        best_box = b

                if best_box and closest_dist <= 75.0:
                    target_word = best_box["text"].strip()
                    target_box = best_box

            # 4. Kelimeyi Temizle ve Çevir
            if target_word:
                cleaned_word = target_word.strip(".,;:!?\"'()[]{}«»“”„…- ")
                if not cleaned_word:
                    cleaned_word = target_word

                print(f"[Ekran Sozlugu] Hedef kelime bulundu: '{cleaned_word}'")

                screen_x1 = left + target_box["x"]
                screen_y1 = top + target_box["y"]
                screen_x2 = screen_x1 + target_box["w"]
                screen_y2 = screen_y1 + target_box["h"]

                self._active_word = cleaned_word
                self._active_word_screen_rect = (screen_x1, screen_y1, screen_x2, screen_y2)

                try:
                    result_data = self.translator.translate_and_analyze(cleaned_word)
                    if result_data:
                        self.on_word_hover(result_data, cursor_x, cursor_y)
                    else:
                        self._trigger_not_found_feedback(cursor_x, cursor_y)
                except Exception as e:
                    print(f"Hover çeviri hatası: {e}")
                    self._trigger_not_found_feedback(cursor_x, cursor_y)
            else:
                bulunanlar = [b['text'] for b in boxes]
                print(f"[Ekran Sozlugu] Farenin altinda kelime bulunamadi. (Bolgedeki kelimeler: {bulunanlar})")
                self._trigger_not_found_feedback(cursor_x, cursor_y)

        except Exception as e:
            print(f"Hover inceleme genel hatası: {e}")
            self._trigger_not_found_feedback(cursor_x, cursor_y)
