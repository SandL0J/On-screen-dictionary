"""
Canlı Fare Üzerine Gelme (Hover Tooltip) Balon Arayüzü
Video veya metin izlerken farenin tam üstünde veya yanında beliren;
artikel rengi, çoğul hali, Türkçe karşılığı ve hızlı kaydetme yıldızı
içeren kompakt, yarı saydam ve hafif mini kart.
"""
import tkinter as tk
from typing import Dict, Any, Optional

GENDER_COLORS = {
    "der": "#3b82f6",  # Mavi (Eril)
    "die": "#ef4444",  # Kırmızı (Dişil)
    "das": "#10b981",  # Yeşil (Nötr)
}


class HoverTooltip:
    """
    Farenin yanında açılan, video akışını engellemeyen,
    hafif ve şık mini çeviri balonu.
    """

    def __init__(self, root: tk.Tk, db=None):
        self.root = root
        self.db = db
        self._current_data: Optional[Dict[str, Any]] = None

        self.window = tk.Toplevel(self.root)
        self.window.withdraw()  # Başlangıçta gizli
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.94)
        self.window.configure(bg="#27272a")

        self._init_ui()

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

        # Hızlı Kaydet Yıldızı
        self.btn_star = tk.Label(
            self.top_row,
            text="☆",
            font=("Segoe UI", 11),
            fg="#eab308",
            bg="#18181b",
            cursor="hand2",
        )
        self.btn_star.pack(side="right", padx=(4, 0))
        self.btn_star.bind("<Button-1>", lambda e: self._toggle_save())

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

    def show_loading(self, cursor_x: int, cursor_y: int, message: str = "🔍 Okunuyor..."):
        """Tetikleme anında hemen beliren hafif yükleniyor göstergesi."""
        def _do_loading():
            self._current_data = None
            try:
                self.lbl_article.pack_forget()
                self.lbl_plural.pack_forget()
                self.btn_star.pack_forget()
                self.lbl_turkish.pack_forget()

                self.lbl_german.configure(
                    text=message,
                    font=("Segoe UI", 9, "italic"),
                    fg="#a1a1aa"
                )
                self.lbl_german.pack(side="left", padx=2)

                self.window.update_idletasks()
                w = max(self.window.winfo_reqwidth(), 120)
                h = max(self.window.winfo_reqheight(), 32)

                x = cursor_x - 20
                y = cursor_y - h - 12
                if y < 10:
                    y = cursor_y + 24

                self.window.geometry(f"{w}x{h}+{x}+{y}")
                self.window.deiconify()
                self.window.attributes("-topmost", True)
                self.window.lift()
            except Exception:
                pass

        try:
            if self.root.winfo_exists():
                self.root.after(0, _do_loading)
        except Exception:
            pass

    def show_message(self, cursor_x: int, cursor_y: int, message: str, auto_hide_ms: int = 1400):
        """Kısa durum mesajı gösterir (ör. Metin bulunamadı)."""
        def _do_msg():
            self._current_data = None
            try:
                self.lbl_article.pack_forget()
                self.lbl_plural.pack_forget()
                self.btn_star.pack_forget()
                self.lbl_turkish.pack_forget()

                self.lbl_german.configure(
                    text=message,
                    font=("Segoe UI", 9, "bold"),
                    fg="#f59e0b"
                )
                self.lbl_german.pack(side="left", padx=2)

                self.window.update_idletasks()
                w = max(self.window.winfo_reqwidth(), 140)
                h = max(self.window.winfo_reqheight(), 32)

                x = cursor_x - 20
                y = cursor_y - h - 12
                if y < 10:
                    y = cursor_y + 24

                self.window.geometry(f"{w}x{h}+{x}+{y}")
                self.window.deiconify()
                self.window.attributes("-topmost", True)
                self.window.lift()

                if auto_hide_ms > 0:
                    self.root.after(auto_hide_ms, self.hide)
            except Exception:
                pass

        try:
            if self.root.winfo_exists():
                self.root.after(0, _do_msg)
        except Exception:
            pass

    def show(self, word_data: Dict[str, Any], cursor_x: int, cursor_y: int):
        """Kartı verilen kelime verisiyle farenin yakınında konumlandırıp gösterir."""
        if not word_data:
            return

        def _do_show():
            self._current_data = word_data
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

            # Hızlı Kaydet Yıldızı
            self.btn_star.pack(side="right", padx=(4, 0))
            if self.db and self.db.is_word_saved(german_word):
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

            # Akıllı Konumlandırma
            self.window.update_idletasks()
            w = max(self.window.winfo_reqwidth(), 160)
            h = max(self.window.winfo_reqheight(), 46)

            screen_w = self.window.winfo_screenwidth()
            screen_h = self.window.winfo_screenheight()

            # Varsayılan: Farenin 12px yukarısı
            x = cursor_x - 30
            y = cursor_y - h - 14

            # Eğer ekranın üst sınırına taşarsa farenin 24px altına koy
            if y < 10:
                y = cursor_y + 26

            # Yatay ekran sınırları
            if x + w > screen_w - 10:
                x = screen_w - w - 10
            if x < 10:
                x = 10

            if not self.window.winfo_exists():
                return
            self.window.geometry(f"{w}x{h}+{x}+{y}")
            self.window.deiconify()
            self.window.attributes("-topmost", True)
            self.window.lift()

        try:
            if self.root.winfo_exists():
                self.root.after(0, _do_show)
        except Exception:
            pass

    def hide(self):
        """Kartı gizler."""
        def _do_hide():
            self._current_data = None
            try:
                if self.window.winfo_exists():
                    self.window.withdraw()
            except Exception:
                pass

        try:
            if self.root.winfo_exists():
                self.root.after(0, _do_hide)
        except Exception:
            pass

    def _toggle_save(self):
        """Kelime defterine ekler veya çıkarır."""
        if not self._current_data or not self.db:
            return

        german = (
            self._current_data.get("german") or
            self._current_data.get("original") or ""
        ).strip()
        turkish = (
            self._current_data.get("turkish") or
            self._current_data.get("translation") or ""
        ).strip()
        analysis = self._current_data.get("analysis", {})
        article = (self._current_data.get("article") or analysis.get("article") or "").strip()
        plural = (self._current_data.get("plural") or analysis.get("plural") or "").strip()
        example = self._current_data.get("example_de", "")
        example_tr = self._current_data.get("example_tr", "")

        if self.db.is_word_saved(german):
            self.db.delete_word_by_german(german)
            self.btn_star.configure(text="☆", fg="#71717a")
        else:
            self.db.add_word(
                german=german,
                turkish=turkish,
                article=article,
                plural=plural,
                example_de=example,
                example_tr=example_tr,
                tags="hover_ocr"
            )
            self.btn_star.configure(text="★", fg="#eab308")
