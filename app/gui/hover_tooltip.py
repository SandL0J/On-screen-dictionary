"""
Canlı Fare Üzerine Gelme (Hover Tooltip) Balon Arayüzü
Video veya metin izlerken farenin tam üstünde veya yanında beliren;
artikel rengi, çoğul hali, Türkçe karşılığı ve hızlı kaydetme yıldızı
içeren kompakt, yarı saydam ve hafif mini kart.
"""
import threading
import tkinter as tk
from typing import Dict, Any, Optional, Callable

GENDER_COLORS = {
    "der": "#3b82f6",  # Mavi (Eril)
    "die": "#ef4444",  # Kırmızı (Dişil)
    "das": "#10b981",  # Yeşil (Nötr)
}


def get_monitor_work_area(x: int, y: int):
    """
    Verilen (x, y) koordinatının bulunduğu monitörün çalışma alanını
    (left, top, right, bottom) piksel cinsinden döner.
    Win32 API erişilemezse sanal masaüstü veya birincil ekran sınırlarına geri düşer.
    """
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long)
            ]
        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD)
            ]
        pt = wintypes.POINT(int(x), int(y))
        h_monitor = user32.MonitorFromPoint(pt, 2)  # MONITOR_DEFAULTTONEAREST = 2
        if h_monitor:
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(h_monitor, ctypes.byref(mi)):
                return (mi.rcWork.left, mi.rcWork.top, mi.rcWork.right, mi.rcWork.bottom)
    except Exception:
        pass

    try:
        import ctypes
        user32 = ctypes.windll.user32
        vx = user32.GetSystemMetrics(76)
        vy = user32.GetSystemMetrics(77)
        vw = user32.GetSystemMetrics(78)
        vh = user32.GetSystemMetrics(79)
        if vw > 0 and vh > 0:
            return (vx, vy, vx + vw, vy + vh)
    except Exception:
        pass

    return (0, 0, 1920, 1080)


class HoverTooltip:
    """
    Farenin yanında açılan, video akışını engellemeyen,
    hafif ve şık mini çeviri balonu.
    """

    def __init__(
        self,
        root: tk.Tk,
        db=None,
        auto_hide_seconds: int = 5,
        post_to_ui: Optional[Callable[[Callable], None]] = None
    ):
        self.root = root
        self.db = db
        self.auto_hide_seconds = max(0, int(auto_hide_seconds))
        self.post_to_ui = post_to_ui
        self._current_data: Optional[Dict[str, Any]] = None
        self._auto_hide_id: Optional[str] = None

        self.window = tk.Toplevel(self.root)
        self.window.withdraw()  # Başlangıçta gizli
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.94)
        self.window.configure(bg="#27272a")
        self.window.bind("<Destroy>", lambda e: self._cancel_auto_hide())

        self._init_ui()

    def set_auto_hide_seconds(self, seconds: int):
        """Kutucuğun otomatik kapanma süresini saniye cinsinden günceller (0 = otomatik kapanmaz)."""
        try:
            self.auto_hide_seconds = max(0, int(seconds))
        except (ValueError, TypeError):
            self.auto_hide_seconds = 5

    def _cancel_auto_hide(self):
        """Aktif otomatik kapanma zamanlayıcısını iptal eder."""
        if threading.current_thread() is not threading.main_thread():
            if self.post_to_ui:
                self.post_to_ui(self._cancel_auto_hide)
            else:
                print("[HoverTooltip UYARI] Worker thread'den _cancel_auto_hide çağrısı reddedildi: UI dispatcher (post_to_ui) tanımlı değil.")
            return

        if self._auto_hide_id is not None:
            try:
                if self.root.winfo_exists():
                    self.root.after_cancel(self._auto_hide_id)
            except Exception:
                pass
            self._auto_hide_id = None

    def has_active_auto_hide(self) -> bool:
        """Aktif bir otomatik kapanma zamanlayıcısı (sayacı) olup olmadığını döner."""
        return self._auto_hide_id is not None

    def is_visible(self) -> bool:
        """Kutucuğun şu an ekranda görünür olup olmadığını döner."""
        if threading.current_thread() is not threading.main_thread():
            return False
        try:
            return bool(self.window.winfo_exists() and self.window.winfo_viewable())
        except Exception:
            return False

    def _init_ui(self):
        # Dış çerçeve ve dolgu
        self.outer_frame = tk.Frame(self.window, bg="#18181b", padx=10, pady=7)
        self.outer_frame.pack(fill="both", expand=True, padx=1, pady=1)

        # Üst Satır: [Artikel] [Kelime] [Çoğul] [⭐]
        self.top_row = tk.Frame(self.outer_frame, bg="#18181b")
        self.top_row.pack(fill="x", anchor="w")

        # Artikel etiketi
        self.lbl_article = tk.Label(
            self.top_row,
            text="",
            font=("Segoe UI", 9, "bold"),
            fg="#3b82f6",
            bg="#18181b",
        )
        self.lbl_article.pack(side="left", padx=(0, 4))

        # Almanca Kelime
        self.lbl_german = tk.Label(
            self.top_row,
            text="",
            font=("Segoe UI", 11, "bold"),
            fg="#fafafa",
            bg="#18181b",
        )
        self.lbl_german.pack(side="left", padx=(0, 6))

        # Çoğul Bilgisi
        self.lbl_plural = tk.Label(
            self.top_row,
            text="",
            font=("Segoe UI", 8, "italic"),
            fg="#a1a1aa",
            bg="#18181b",
        )
        self.lbl_plural.pack(side="left", padx=(0, 6))

        # Kapatma Çarpısı (Sağ üst köşe)
        self.btn_close = tk.Label(
            self.top_row,
            text="✕",
            font=("Segoe UI", 9, "bold"),
            fg="#ef4444",
            bg="#18181b",
            cursor="hand2",
            padx=2,
            pady=0,
        )
        self.btn_close.pack(side="right", padx=(4, 0))
        self.btn_close.bind("<Button-1>", lambda e: self.hide())
        self.btn_close.bind("<Enter>", lambda e: self.btn_close.configure(fg="#f87171"))
        self.btn_close.bind("<Leave>", lambda e: self.btn_close.configure(fg="#ef4444"))

        # Hızlı Kaydet Yıldızı
        self.btn_star = tk.Label(
            self.top_row,
            text="☆",
            font=("Segoe UI", 11),
            fg="#eab308",
            bg="#18181b",
            cursor="hand2",
        )
        self.btn_star.pack(side="right", padx=(4, 2))
        self.btn_star.bind("<Button-1>", lambda e: self._toggle_save())

        # Lemma / Ayrılabilir Fiil İpucu Satırı (Örn. 🔁 ging → gehen · Präteritum veya 🧩 fängt … an → anfangen)
        self.lbl_lemma_hint = tk.Label(
            self.outer_frame,
            text="",
            font=("Segoe UI", 8, "italic"),
            fg="#a1a1aa",
            bg="#18181b",
            wraplength=340,
            justify="left",
            anchor="w",
        )

        # Alt Satır: Türkçe Anlamı
        self.lbl_turkish = tk.Label(
            self.outer_frame,
            text="",
            font=("Segoe UI", 9, "bold"),
            fg="#38bdf8",
            bg="#18181b",
            wraplength=340,
            justify="left",
            anchor="w",
        )
        self.lbl_turkish.pack(fill="x", anchor="w", pady=(3, 0))

        # Fare kartın üzerine geldiğinde otomatik kapanmayı durdur
        self.window.bind("<Enter>", lambda e: self._cancel_auto_hide())
        self.outer_frame.bind("<Enter>", lambda e: self._cancel_auto_hide())

    def show_loading(self, cursor_x: int, cursor_y: int, message: str = "🔍 Okunuyor..."):
        """Tetikleme anında hemen beliren hafif yükleniyor göstergesi."""
        if threading.current_thread() is not threading.main_thread():
            if self.post_to_ui:
                self.post_to_ui(lambda: self.show_loading(cursor_x, cursor_y, message))
            else:
                print("[HoverTooltip UYARI] Worker thread'den show_loading çağrısı reddedildi: UI dispatcher (post_to_ui) tanımlı değil.")
            return

        self._cancel_auto_hide()
        self._current_data = None
        try:
            if not self.window.winfo_exists():
                return
            self.lbl_article.pack_forget()
            self.lbl_plural.pack_forget()
            self.btn_star.pack_forget()
            self.lbl_turkish.pack_forget()
            self.lbl_lemma_hint.pack_forget()

            self.btn_close.pack(side="right", padx=(4, 0))

            self.lbl_german.configure(
                text=message,
                font=("Segoe UI", 9, "italic"),
                fg="#a1a1aa"
            )
            self.lbl_german.pack(side="left", padx=2)

            self.window.update_idletasks()
            w = max(self.window.winfo_reqwidth(), 140)
            h = max(self.window.winfo_reqheight(), 32)

            m_left, m_top, m_right, m_bottom = get_monitor_work_area(cursor_x, cursor_y)
            x = cursor_x - 20
            y = cursor_y - h - 12
            if y < m_top + 10:
                y = cursor_y + 24
            if x + w > m_right - 10:
                x = m_right - w - 10
            if x < m_left + 10:
                x = m_left + 10
            if y + h > m_bottom - 10:
                y = m_bottom - h - 10
            if y < m_top + 10:
                y = m_top + 10

            self.window.geometry(f"{w}x{h}+{x}+{y}")
            self.window.deiconify()
            self.window.attributes("-topmost", True)
            self.window.lift()
        except Exception:
            pass

    def show_message(self, cursor_x: int, cursor_y: int, message: str, auto_hide_ms: int = 1400):
        """Kısa durum mesajı gösterir (ör. Metin bulunamadı)."""
        if threading.current_thread() is not threading.main_thread():
            if self.post_to_ui:
                self.post_to_ui(lambda: self.show_message(cursor_x, cursor_y, message, auto_hide_ms))
            else:
                print("[HoverTooltip UYARI] Worker thread'den show_message çağrısı reddedildi: UI dispatcher (post_to_ui) tanımlı değil.")
            return

        self._cancel_auto_hide()
        self._current_data = None

        if auto_hide_ms > 0 and self.root.winfo_exists():
            self._auto_hide_id = self.root.after(auto_hide_ms, self.hide)

        try:
            if not self.window.winfo_exists():
                return
            self.lbl_article.pack_forget()
            self.lbl_plural.pack_forget()
            self.btn_star.pack_forget()
            self.lbl_turkish.pack_forget()
            self.lbl_lemma_hint.pack_forget()

            self.btn_close.pack(side="right", padx=(4, 0))

            self.lbl_german.configure(
                text=message,
                font=("Segoe UI", 9, "bold"),
                fg="#f59e0b"
            )
            self.lbl_german.pack(side="left", padx=2)

            self.window.update_idletasks()
            w = max(self.window.winfo_reqwidth(), 150)
            h = max(self.window.winfo_reqheight(), 32)

            m_left, m_top, m_right, m_bottom = get_monitor_work_area(cursor_x, cursor_y)
            x = cursor_x - 20
            y = cursor_y - h - 12
            if y < m_top + 10:
                y = cursor_y + 24
            if x + w > m_right - 10:
                x = m_right - w - 10
            if x < m_left + 10:
                x = m_left + 10
            if y + h > m_bottom - 10:
                y = m_bottom - h - 10
            if y < m_top + 10:
                y = m_top + 10

            self.window.geometry(f"{w}x{h}+{x}+{y}")
            self.window.deiconify()
            self.window.attributes("-topmost", True)
            self.window.lift()
        except Exception:
            pass

    def show(self, word_data: Dict[str, Any], cursor_x: int, cursor_y: int, auto_hide_seconds: Optional[int] = None):
        """Kartı verilen kelime verisiyle farenin yakınında konumlandırıp gösterir."""
        if not word_data:
            return

        if threading.current_thread() is not threading.main_thread():
            if self.post_to_ui:
                self.post_to_ui(lambda: self.show(word_data, cursor_x, cursor_y, auto_hide_seconds))
            else:
                print("[HoverTooltip UYARI] Worker thread'den show çağrısı reddedildi: UI dispatcher (post_to_ui) tanımlı değil.")
            return

        self._cancel_auto_hide()
        self._current_data = word_data

        duration = self.auto_hide_seconds if auto_hide_seconds is None else max(0, int(auto_hide_seconds))
        if duration > 0 and self.root.winfo_exists():
            self._auto_hide_id = self.root.after(int(duration * 1000), self.hide)

        try:
            if not self.window.winfo_exists():
                return
        except Exception:
            return

        analysis = word_data.get("analysis", {})

        # 1. Almanca Kelime
        german_word = (
            word_data.get("german") or
            word_data.get("original") or
            word_data.get("text") or ""
        ).strip()

        # 2. Türkçe Anlam ve Ek Anlamlar
        turkish_meaning = (
            word_data.get("turkish") or
            word_data.get("translation") or ""
        ).strip()

        dict_entries = word_data.get("dict_entries", [])
        extra_meanings = []
        if dict_entries and isinstance(dict_entries, list):
            for entry in dict_entries:
                meanings = entry.get("meanings", [])
                for m in meanings:
                    if m and m.lower() != turkish_meaning.lower() and m not in extra_meanings:
                        extra_meanings.append(m)

        if extra_meanings:
            display_meanings = turkish_meaning + " (" + ", ".join(extra_meanings[:3]) + ")"
        else:
            display_meanings = turkish_meaning

        # 3. Artikel ve Çoğul Bilgisi
        article = (
            word_data.get("article") or
            analysis.get("article") or ""
        ).strip().lower()

        plural = (
            word_data.get("plural") or
            analysis.get("plural") or ""
        ).strip()

        pos = (
            word_data.get("pos") or ""
        ).strip()

        # Artikel etiketi
        if article in GENDER_COLORS:
            self.lbl_article.configure(text=article, fg=GENDER_COLORS[article])
            self.lbl_article.pack(side="left", padx=(0, 4))
        else:
            self.lbl_article.configure(text="")
            self.lbl_article.pack_forget()

        # Almanca Kelime etiketi
        self.lbl_german.configure(
            text=german_word,
            font=("Segoe UI", 11, "bold"),
            fg="#fafafa"
        )
        self.lbl_german.pack(side="left", padx=(0, 6))

        # Çoğul veya Sözcük Türü
        if plural and plural != "-":
            self.lbl_plural.configure(text=f"(Pl: {plural})")
            self.lbl_plural.pack(side="left", padx=(0, 6))
        elif pos and pos != "Kelime":
            self.lbl_plural.configure(text=f"[{pos}]")
            self.lbl_plural.pack(side="left", padx=(0, 6))
        else:
            self.lbl_plural.configure(text="")
            self.lbl_plural.pack_forget()

        # Kapatma Çarpısı (Sağ üst köşe)
        self.btn_close.pack(side="right", padx=(4, 0))

        # Hızlı Kaydet Yıldızı
        self.btn_star.pack(side="right", padx=(4, 2))
        save_lookup = (word_data.get("lemma") or german_word).strip()
        if self.db and self.db.is_word_saved(save_lookup):
            self.btn_star.configure(text="★", fg="#eab308")
        else:
            self.btn_star.configure(text="☆", fg="#71717a")

        # Türkçe Anlam etiketi
        direction = word_data.get("direction", "de_to_tr")
        if direction == "tr_to_de":
            self.lbl_turkish.configure(text=f"🇹🇷 {display_meanings}")
        else:
            self.lbl_turkish.configure(text=display_meanings)
        self.lbl_turkish.pack(fill="x", anchor="w", pady=(3, 0))

        # Lemma / Ayrılabilir Fiil İpucu
        lemma_hint = (word_data.get("lemma_hint") or "").strip()
        if lemma_hint:
            self.lbl_lemma_hint.configure(text=lemma_hint)
            self.lbl_lemma_hint.pack(fill="x", anchor="w", pady=(1, 0))
        else:
            self.lbl_lemma_hint.configure(text="")
            self.lbl_lemma_hint.pack_forget()

        # Akıllı Konumlandırma
        self.window.update_idletasks()
        w = max(self.window.winfo_reqwidth(), 160)
        h = max(self.window.winfo_reqheight(), 46)

        m_left, m_top, m_right, m_bottom = get_monitor_work_area(cursor_x, cursor_y)

        # Varsayılan: Farenin 14px yukarısı
        x = cursor_x - 30
        y = cursor_y - h - 14

        # Eğer ekranın üst sınırına taşarsa farenin 26px altına koy
        if y < m_top + 10:
            y = cursor_y + 26

        # Yatay ekran sınırları
        if x + w > m_right - 10:
            x = m_right - w - 10
        if x < m_left + 10:
            x = m_left + 10

        # Dikey ekran sınırları
        if y + h > m_bottom - 10:
            y = m_bottom - h - 10
        if y < m_top + 10:
            y = m_top + 10

        if not self.window.winfo_exists():
            return
        self.window.geometry(f"{w}x{h}+{x}+{y}")
        self.window.deiconify()
        self.window.attributes("-topmost", True)
        self.window.lift()

    def hide(self):
        """Kartı gizler."""
        if threading.current_thread() is not threading.main_thread():
            if self.post_to_ui:
                self.post_to_ui(self.hide)
            else:
                print("[HoverTooltip UYARI] Worker thread'den hide çağrısı reddedildi: UI dispatcher (post_to_ui) tanımlı değil.")
            return

        self._cancel_auto_hide()
        self._current_data = None
        try:
            if self.window.winfo_exists():
                self.window.withdraw()
        except Exception:
            pass

    def _toggle_save(self):
        """Kelime defterine ekler veya çıkarır."""
        if not self._current_data or not self.db:
            return

        german = (
            self._current_data.get("lemma") or
            self._current_data.get("german") or
            self._current_data.get("original") or ""
        ).strip()
        if not german:
            return
        turkish = (
            self._current_data.get("turkish") or
            self._current_data.get("translation") or ""
        ).strip()
        analysis = self._current_data.get("analysis", {})
        article = (self._current_data.get("article") or analysis.get("article") or "").strip()
        plural = (self._current_data.get("plural") or analysis.get("plural") or "").strip()
        example = (self._current_data.get("context_sentence") or self._current_data.get("example_de") or "").strip()
        example_tr = (self._current_data.get("example_tr") or "").strip()
        surface = (self._current_data.get("surface_form") or "").strip()
        extra_kwargs = {}
        if surface:
            extra_kwargs["surface_form"] = surface

        if self.db.is_word_saved(german):
            self.db.delete_word_by_german(german)
            self.btn_star.configure(text="☆", fg="#71717a")
        else:
            note_text = f"Hover OCR ({surface})" if surface and surface.lower() != german.lower() else "Hover OCR"
            self.db.add_word(
                german=german,
                turkish=turkish,
                article=article,
                plural=plural,
                example_de=example,
                example_tr=example_tr,
                notes=note_text,
                status="learning",
                **extra_kwargs
            )
            self.btn_star.configure(text="★", fg="#eab308")
