"""
Ekran Bölgesi Seçme ve Kırpma Aracı (Screen Snipping Tool for OCR)
Kullanıcının video izlerken veya okurken ekranın herhangi bir bölgesindeki (altyazı, resim, pdf)
Almanca metni fareyle çerçeve içine alıp anında OCR ile okumasını sağlar.
Video altyazısının kaybolmaması için seçim başladığı an anlık ekran görüntüsünü dondurur.
"""
import tkinter as tk
from PIL import Image, ImageGrab
import threading
from typing import Callable, Optional, Any
import ctypes
from app.hover_tracker import capture_screen_rect_gdi

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


class ScreenSnipper:
    def __init__(
        self,
        root: tk.Tk,
        ocr_engine,
        on_text_extracted: Callable[[str], None],
        post_to_ui: Optional[Callable[[Callable], None]] = None,
        worker_pool: Optional[Any] = None,
        config: Optional[dict] = None
    ):
        self.root = root
        self.ocr_engine = ocr_engine
        self.on_text_extracted = on_text_extracted
        self.post_to_ui = post_to_ui
        self.worker_pool = worker_pool
        self.config = config or {}

        self.overlay: Optional[tk.Toplevel] = None
        self.canvas: Optional[tk.Canvas] = None
        self.start_x = 0
        self.start_y = 0
        self.rect_id = None
        self.text_id = None
        self._screenshot: Optional[Image.Image] = None

    def _dispatch_to_ui(self, fn: Callable):
        """Worker thread'den Tk ana thread'ine görev aktarır."""
        if threading.current_thread() is threading.main_thread():
            fn()
            return

        if self.post_to_ui:
            self.post_to_ui(fn)
        else:
            print("[ScreenSnipper UYARI] Worker thread'den Tk çağrısı reddedildi: UI dispatcher (post_to_ui) tanımlı değil.")

    def start_selection(self):
        """Ekran seçim modunu başlatır. Altyazı kaybolmasın diye ekranı o an dondurur."""
        if self.overlay and self.overlay.winfo_exists():
            return

        # 1. Altyazının geçmesini önlemek için anında ekran görüntüsü yakala (tüm ekranlar)
        try:
            user32 = ctypes.windll.user32
            vx = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
            vy = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
            vw = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
            vh = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
            if vw <= 0 or vh <= 0:
                vx, vy = 0, 0
                vw = user32.GetSystemMetrics(0)
                vh = user32.GetSystemMetrics(1)
            self._virtual_origin = (vx, vy)
            self._screenshot = capture_screen_rect_gdi(vx, vy, vw, vh)
            if self._screenshot is None:
                self._screenshot = ImageGrab.grab(all_screens=True)
        except Exception as e:
            print(f"Ön ekran yakalama uyarısı: {e}")
            self._screenshot = None
            vx, vy, vw, vh = 0, 0, 1920, 1080
            self._virtual_origin = (0, 0)

        # 2. Karartmalı seçim penceresini aç (tüm sanal masaüstünü kapla)
        self.overlay = tk.Toplevel(self.root)
        self.overlay.overrideredirect(True)
        self.overlay.geometry(f"{vw}x{vh}+{vx}+{vy}")
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-alpha", 0.28)  # Yarı saydam kararık ekran
        self.overlay.configure(bg="#000000", cursor="crosshair")

        self.canvas = tk.Canvas(self.overlay, bg="#000000", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)

        # Bilgilendirme etiketi
        label_x = vw // 2
        self.canvas.create_text(
            label_x, 40,
            text="✂ Çevirmek istediğiniz Almanca kelimeyi veya altyazıyı seçin (İptal: ESC / Sağ Tık)",
            fill="#ffffff",
            font=("Segoe UI", 12, "bold")
        )

        # Fare olaylarını bağla
        self.canvas.bind("<ButtonPress-1>", self._on_button_press)
        self.canvas.bind("<B1-Motion>", self._on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self._on_button_release)
        self.canvas.bind("<Escape>", lambda e: self._cancel())
        self.canvas.bind("<Button-3>", lambda e: self._cancel())
        self.overlay.bind("<Escape>", lambda e: self._cancel())
        self.overlay.bind("<Button-3>", lambda e: self._cancel())
        try:
            self.overlay.focus_force()
            self.canvas.focus_set()
        except Exception:
            pass

    def _on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        if self.text_id:
            self.canvas.delete(self.text_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="#38bdf8", width=2, fill="#0284c7", stipple="gray25"
        )

    def _on_move_press(self, event):
        cur_x, cur_y = event.x, event.y
        self.canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)
        w = abs(cur_x - self.start_x)
        h = abs(cur_y - self.start_y)
        if self.text_id:
            self.canvas.delete(self.text_id)
        self.text_id = self.canvas.create_text(
            cur_x + 12, cur_y + 12,
            text=f"{w}x{h} px",
            fill="#38bdf8",
            font=("Segoe UI", 9, "bold")
        )

    def _on_button_release(self, event):
        end_x, end_y = event.x, event.y
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)

        w = x2 - x1
        h = y2 - y1

        # Tuval genişlik/yükseklik ve DPI ölçeklemesi
        c_w = max(self.canvas.winfo_width(), 1)
        c_h = max(self.canvas.winfo_height(), 1)

        frozen_img = self._screenshot
        self._screenshot = None
        self._close_overlay()

        if w > 8 and h > 8:
            self._process_region(frozen_img, x1, y1, x2, y2, c_w, c_h)

    def _process_region(self, frozen_img: Optional[Image.Image],
                        x1: int, y1: int, x2: int, y2: int,
                        canvas_w: int, canvas_h: int):
        def _worker():
            try:
                img_to_ocr = None
                if frozen_img:
                    # DPI ölçeklemesini uygula
                    s_w, s_h = frozen_img.size
                    scale_x = s_w / canvas_w
                    scale_y = s_h / canvas_h
                    rx1 = max(0, int(x1 * scale_x))
                    ry1 = max(0, int(y1 * scale_y))
                    rx2 = min(s_w, int(x2 * scale_x))
                    ry2 = min(s_h, int(y2 * scale_y))
                    if rx2 > rx1 and ry2 > ry1:
                        img_to_ocr = frozen_img.crop((rx1, ry1, rx2, ry2))

                if img_to_ocr is None:
                    # Donanımsal GDI yakalama fallback
                    vx, vy = getattr(self, "_virtual_origin", (0, 0))
                    img_to_ocr = capture_screen_rect_gdi(x1 + vx, y1 + vy, x2 - x1, y2 - y1)
                    if img_to_ocr is None:
                        img_to_ocr = ImageGrab.grab(bbox=(x1 + vx, y1 + vy, x2 + vx, y2 + vy), all_screens=True)

                recognized = self.ocr_engine.recognize_from_image(img_to_ocr)
                if recognized and recognized.strip():
                    text = recognized.strip()
                    self._dispatch_to_ui(lambda: self.on_text_extracted(text))
                else:
                    self._dispatch_to_ui(self._notify_no_text)
            except Exception as e:
                print(f"Ekran OCR işleme hatası: {e}")
                self._dispatch_to_ui(self._notify_no_text)

        if getattr(self, "worker_pool", None):
            self.worker_pool.submit(_worker)
        else:
            threading.Thread(target=_worker, daemon=True).start()

    def _notify_no_text(self):
        """Kullanıcıya seçim bölgesinde metin okunamadığını bildiren geçici toast."""
        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.attributes("-alpha", 0.92)
        toast.configure(bg="#27272a")

        frame = tk.Frame(toast, bg="#27272a", padx=14, pady=8, highlightthickness=1, highlightbackground="#ef4444")
        frame.pack()

        tk.Label(
            frame,
            text="⚠️ Seçilen alanda okunabilir metin bulunamadı.\n(Lütfen altyazıyı biraz daha geniş seçin)",
            font=("Segoe UI", 9),
            fg="#f87171",
            bg="#27272a",
            justify="center"
        ).pack()

        # Ekranın ortasında göster
        toast.update_idletasks()
        tw = toast.winfo_reqwidth()
        th = toast.winfo_reqheight()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        toast.geometry(f"+{(sw - tw)//2}+{(sh - th)//2}")

        # 2.2 saniye sonra otomatik kapat
        toast.after(2200, lambda: toast.destroy())

    def _cancel(self):
        self._screenshot = None
        self._close_overlay()

    def _close_overlay(self):
        if self.overlay:
            try:
                self.overlay.destroy()
            except Exception:
                pass
            self.overlay = None
            self.canvas = None
