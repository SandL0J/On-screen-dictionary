"""
Anlık Çeviri ve Dilbilgisi Kartı (Result HUD Overlay)
Kullanıcının o an izlediği videoyu veya okuduğu yazıyı kesintiye uğratmadan,
ekranın uygun bir yerinde beliren şık, modern ve bilgilendirici çeviri penceresi.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from typing import Dict, Any, Optional, Callable
from app.gui.hover_tooltip import get_monitor_work_area


class ResultHUD:
    _instance: Optional['ResultHUD'] = None

    @classmethod
    def show_result(cls, root: tk.Tk, data: Dict[str, Any], *args, db=None, config: dict = None, tts_engine=None, on_save_callback: Optional[Callable] = None, **kwargs):
        """Mevcut açık pencere varsa günceller, yoksa yenisini açar."""
        resolved_db = db
        resolved_config = config
        resolved_tts = tts_engine
        resolved_callback = on_save_callback

        if resolved_db is None and len(args) > 0:
            if hasattr(args[0], 'is_word_saved') or hasattr(args[0], 'get_word'):
                resolved_db = args[0]
                if len(args) > 1 and resolved_config is None:
                    resolved_config = args[1]
                if len(args) > 2 and resolved_callback is None:
                    resolved_callback = args[2]
            else:
                resolved_tts = args[0]
                if len(args) > 1:
                    resolved_db = args[1]
                if len(args) > 2 and resolved_config is None:
                    resolved_config = args[2]
                if len(args) > 3 and resolved_callback is None:
                    resolved_callback = args[3]

        if cls._instance and cls._instance.is_alive():
            cls._instance.update_data(data)
        else:
            cls._instance = ResultHUD(
                root, data,
                db=resolved_db,
                config=resolved_config,
                tts_engine=resolved_tts,
                on_save_callback=resolved_callback
            )
        cls._instance.bring_to_front()

    def __init__(self, root: tk.Tk, data: Dict[str, Any], *args, db=None, config: dict = None, tts_engine=None, on_save_callback: Optional[Callable] = None, **kwargs):
        resolved_db = db
        resolved_config = config
        resolved_tts = tts_engine
        resolved_callback = on_save_callback

        if resolved_db is None and len(args) > 0:
            if hasattr(args[0], 'is_word_saved') or hasattr(args[0], 'get_word'):
                resolved_db = args[0]
                if len(args) > 1 and resolved_config is None:
                    resolved_config = args[1]
                if len(args) > 2 and resolved_callback is None:
                    resolved_callback = args[2]
            else:
                resolved_tts = args[0]
                if len(args) > 1:
                    resolved_db = args[1]
                if len(args) > 2 and resolved_config is None:
                    resolved_config = args[2]
                if len(args) > 3 and resolved_callback is None:
                    resolved_callback = args[3]

        self.root = root
        self.data = data
        self.tts = resolved_tts
        self.db = resolved_db
        self.config = resolved_config or {}
        self.on_save_callback = resolved_callback

        self.window = tk.Toplevel(root)
        self.window.title("Ekran Sözlüğü - Çeviri")
        self.window.overrideredirect(True)  # Kenarlıksız modern pencere
        self.window.attributes("-topmost", True)  # Her zaman üstte
        self.window.attributes("-alpha", 0.96)  # Hafif modern şeffaflık

        self.auto_hide_id = None
        self._is_mouse_over = False
        self.context_label = None

        self._init_ui()
        self._position_window()
        self._bind_events()
        self._schedule_auto_hide()

    def is_alive(self) -> bool:
        try:
            return self.window.winfo_exists()
        except Exception:
            return False

    def bring_to_front(self):
        try:
            self.window.deiconify()
            self.window.attributes("-topmost", True)
            self.window.lift()
        except Exception:
            pass

    def _init_ui(self):
        # Renk Paleti
        self.bg_color = "#18181b"       # Çok koyu şık arka plan
        self.card_bg = "#27272a"        # Kart arkaplanı
        self.text_main = "#fafafa"      # Beyazımsı ana metin
        self.text_muted = "#a1a1aa"     # Gri açıklama
        self.accent_purple = "#8b5cf6"  # Vurgu rengi

        self.window.configure(bg=self.bg_color)

        # Dış Kenarlık Çerçevesi
        self.outer_frame = tk.Frame(self.window, bg="#3f3f46", padx=1, pady=1)
        self.outer_frame.pack(fill="both", expand=True)

        self.main_frame = tk.Frame(self.outer_frame, bg=self.bg_color, padx=14, pady=12)
        self.main_frame.pack(fill="both", expand=True)

        # 1. ÜST BAŞLIK (Sürükleme Alanı & Kapatma Butonu)
        self.header_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.header_frame.pack(fill="x", pady=(0, 8))

        self.app_title = tk.Label(
            self.header_frame,
            text="EKRAN SÖZLÜĞÜ • ALMANCA",
            font=("Segoe UI", 8, "bold"),
            fg="#71717a",
            bg=self.bg_color
        )
        self.app_title.pack(side="left")

        self.btn_close = tk.Label(
            self.header_frame,
            text="✕",
            font=("Segoe UI", 10, "bold"),
            fg="#a1a1aa",
            bg=self.bg_color,
            cursor="hand2"
        )
        self.btn_close.pack(side="right")
        self.btn_close.bind("<Button-1>", lambda e: self.close())
        self.btn_close.bind("<Enter>", lambda e: self.btn_close.configure(fg="#ef4444"))
        self.btn_close.bind("<Leave>", lambda e: self.btn_close.configure(fg="#a1a1aa"))

        # 2. İÇERİK KARTI
        self.content_frame = tk.Frame(self.main_frame, bg=self.card_bg, padx=12, pady=10)
        self.content_frame.pack(fill="both", expand=True)

        self._render_content()

        # 3. ALT BUTONLAR (Deftere Ekle, Kopyala)
        self.footer_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.footer_frame.pack(fill="x", pady=(10, 0))

        # Deftere Kaydet Butonu
        is_saved = self.db.is_word_saved(self.data.get("german", "")) if self.db else False
        self.save_btn_text = "✓ Kayıtlı" if is_saved else "⭐ Deftere Ekle"
        self.save_btn_bg = "#065f46" if is_saved else "#6366f1"

        self.btn_save = tk.Button(
            self.footer_frame,
            text=self.save_btn_text,
            font=("Segoe UI", 9, "bold"),
            bg=self.save_btn_bg,
            fg="#ffffff",
            activebackground="#4f46e5",
            activeforeground="#ffffff",
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._toggle_favorite
        )
        self.btn_save.pack(side="left")

        # Kopyala Butonu
        self.btn_copy = tk.Button(
            self.footer_frame,
            text="📋",
            font=("Segoe UI", 9),
            bg="#27272a",
            fg="#a1a1aa",
            activebackground="#3f3f46",
            activeforeground="#ffffff",
            relief="flat",
            padx=6,
            pady=4,
            cursor="hand2",
            command=self._copy_translation
        )
        self.btn_copy.pack(side="right")

    def _render_content(self):
        # Önceki içeriği temizle
        self.context_label = None
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        # Hata durumu kontrolü (ör. çevrimdışı veya geçersiz metin)
        if "error" in self.data:
            err_msg = str(self.data.get("error", "Bilinmeyen çeviri hatası"))
            self.app_title.configure(text="EKRAN SÖZLÜĞÜ • BİLGİ")

            err_frame = tk.Frame(self.content_frame, bg=self.card_bg, padx=6, pady=4)
            err_frame.pack(fill="both", expand=True)

            tk.Label(
                err_frame,
                text="⚠️ Çeviri Uyarısı",
                font=("Segoe UI", 11, "bold"),
                fg="#f59e0b",
                bg=self.card_bg
            ).pack(anchor="w", pady=(0, 4))

            tk.Label(
                err_frame,
                text=err_msg,
                font=("Segoe UI", 9),
                fg="#d4d4d8",
                bg=self.card_bg,
                wraplength=340,
                justify="left"
            ).pack(anchor="w")

            if hasattr(self, "btn_save"):
                self.btn_save.pack_forget()
            return

        if hasattr(self, "btn_save") and hasattr(self, "footer_frame"):
            self.btn_save.pack(side="left")

        is_sentence = self.data.get("is_sentence", False)
        direction = self.data.get("direction", "de_to_tr")

        if direction == "tr_to_de":
            self.app_title.configure(text="EKRAN SÖZLÜĞÜ • TÜRKÇE → ALMANCA")
        else:
            self.app_title.configure(text="EKRAN SÖZLÜĞÜ • ALMANCA → TÜRKÇE")

        if not is_sentence:
            # === KELİME GÖRÜNÜMÜ ===
            header_box = tk.Frame(self.content_frame, bg=self.card_bg)
            header_box.pack(fill="x", anchor="w")

            article = self.data.get("article", "")
            art_color = self.data.get("article_color", "#6b7280")

            if article:
                art_label = tk.Label(
                    header_box,
                    text=f" {article.upper()} ",
                    font=("Segoe UI", 11, "bold"),
                    bg=art_color,
                    fg="#ffffff",
                    padx=6,
                    pady=1
                )
                art_label.pack(side="left", padx=(0, 8))

            german_label = tk.Label(
                header_box,
                text=self.data.get("german", ""),
                font=("Segoe UI", 14, "bold"),
                fg=self.text_main,
                bg=self.card_bg
            )
            german_label.pack(side="left")

            plural = self.data.get("plural", "")
            if plural:
                plural_label = tk.Label(
                    self.content_frame,
                    text=f"Çoğul: {plural}",
                    font=("Segoe UI", 9, "italic"),
                    fg="#38bdf8",
                    bg=self.card_bg
                )
                plural_label.pack(anchor="w", pady=(2, 4))

            # Türkçe Anlamı
            tr_text = self.data.get("turkish", "")
            tr_display = f"Türkçe: {tr_text}" if direction == "tr_to_de" else tr_text
            tr_label = tk.Label(
                self.content_frame,
                text=tr_display,
                font=("Segoe UI", 12, "bold"),
                fg="#4ade80",  # Açık yeşil
                bg=self.card_bg,
                wraplength=340,
                justify="left"
            )
            tr_label.pack(anchor="w", pady=(4, 4))

            # Bağlam İçi Cümle (Sentence Mining)
            context_sentence = (self.data.get("context_sentence") or self.data.get("example_de") or "").strip()
            if context_sentence:
                self.context_label = tk.Label(
                    self.content_frame,
                    text=f'💬 Bağlam: "{context_sentence}"',
                    font=("Segoe UI", 9, "italic"),
                    fg="#a1a1aa",  # Hafif yarı saydam / gri
                    bg=self.card_bg,
                    wraplength=340,
                    justify="left"
                )
                self.context_label.pack(anchor="w", pady=(1, 4))

            # Kelime Türü ve Alternatif Anlamlar
            dict_entries = self.data.get("dict_entries", [])
            if dict_entries:
                for entry in dict_entries[:2]:
                    pos_txt = entry.get("pos", "")
                    meanings = ", ".join(entry.get("meanings", [])[:4])
                    entry_lbl = tk.Label(
                        self.content_frame,
                        text=f"• {pos_txt}: {meanings}",
                        font=("Segoe UI", 8),
                        fg=self.text_muted,
                        bg=self.card_bg,
                        wraplength=340,
                        justify="left"
                    )
                    entry_lbl.pack(anchor="w", pady=(1, 1))

            # Dilbilgisi Kuralı Notu (-ung kuralı vb.)
            rule_note = self.data.get("rule_note", "") or self.data.get("grammar_note", "")
            if rule_note:
                rule_lbl = tk.Label(
                    self.content_frame,
                    text=f"💡 {rule_note}",
                    font=("Segoe UI", 8),
                    fg="#facc15",  # Sarı ipucu rengi
                    bg=self.card_bg,
                    wraplength=340,
                    justify="left"
                )
                rule_lbl.pack(anchor="w", pady=(4, 2))

            # Örnek Cümle (Varsa ve bağlam cümlesinden farklıysa veya Türkçe çevirisi varsa)
            ex_de = (self.data.get("example_de") or "").strip()
            ex_tr = (self.data.get("example_tr") or "").strip()
            if ex_de and (ex_de != context_sentence or ex_tr):
                ex_frame = tk.Frame(self.content_frame, bg="#1f1f23", padx=8, pady=4)
                ex_frame.pack(fill="x", pady=(6, 2))
                ex_de_lbl = tk.Label(
                    ex_frame,
                    text=f"🇩🇪 {ex_de}",
                    font=("Segoe UI", 8),
                    fg="#e4e4e7",
                    bg="#1f1f23",
                    wraplength=320,
                    justify="left"
                )
                ex_de_lbl.pack(anchor="w")
                if ex_tr:
                    ex_tr_lbl = tk.Label(
                        ex_frame,
                        text=f"🇹🇷 {ex_tr}",
                        font=("Segoe UI", 8, "italic"),
                        fg="#a1a1aa",
                        bg="#1f1f23",
                        wraplength=320,
                        justify="left"
                    )
                    ex_tr_lbl.pack(anchor="w")

        else:
            # === CÜMLE GÖRÜNÜMÜ ===
            de_lbl = tk.Label(
                self.content_frame,
                text=f"🇩🇪 {self.data.get('german', '')}",
                font=("Segoe UI", 10, "bold"),
                fg=self.text_main,
                bg=self.card_bg,
                wraplength=340,
                justify="left"
            )
            de_lbl.pack(anchor="w", pady=(0, 4))

            tr_lbl = tk.Label(
                self.content_frame,
                text=f"🇹🇷 {self.data.get('turkish', '')}",
                font=("Segoe UI", 11, "bold"),
                fg="#4ade80",
                bg=self.card_bg,
                wraplength=340,
                justify="left"
            )
            tr_lbl.pack(anchor="w", pady=(0, 6))

            # Bağlam Cümlesi (Varsa ve Almanca metinden farklıysa)
            context_sentence = (self.data.get("context_sentence") or self.data.get("example_de") or "").strip()
            german_text = self.data.get("german", "").strip()
            if context_sentence and context_sentence.lower() != german_text.lower():
                self.context_label = tk.Label(
                    self.content_frame,
                    text=f'💬 Bağlam: "{context_sentence}"',
                    font=("Segoe UI", 9, "italic"),
                    fg="#a1a1aa",
                    bg=self.card_bg,
                    wraplength=340,
                    justify="left"
                )
                self.context_label.pack(anchor="w", pady=(0, 4))

            # Cümle Gramer İpuçları (Modal fiil, bağlaç, fiil sonda kuralı)
            notes = self.data.get("grammar_notes", [])
            if notes:
                notes_box = tk.Frame(self.content_frame, bg="#1f1f23", padx=6, pady=4)
                notes_box.pack(fill="x", pady=(2, 2))
                for n in notes:
                    note_title = n.get("title", "Dilbilgisi Notu")
                    note_text = n.get("text") or n.get("desc") or ""
                    if not note_text:
                        continue
                    n_badge = tk.Label(
                        notes_box,
                        text=f"📌 {note_title}",
                        font=("Segoe UI", 8, "bold"),
                        fg="#facc15",
                        bg="#1f1f23"
                    )
                    n_badge.pack(anchor="w")
                    n_txt = tk.Label(
                        notes_box,
                        text=note_text,
                        font=("Segoe UI", 8),
                        fg="#d4d4d8",
                        bg="#1f1f23",
                        wraplength=320,
                        justify="left"
                    )
                    n_txt.pack(anchor="w", pady=(0, 3))

    def update_data(self, data: Dict[str, Any]):
        """Açık olan kartın içeriğini yeni aramayla günceller."""
        self.data = data
        self._render_content()
        is_saved = self.db.is_word_saved(self.data.get("german", "")) if self.db else False
        self.btn_save.configure(
            text="✓ Kayıtlı" if is_saved else "⭐ Deftere Ekle",
            bg="#065f46" if is_saved else "#6366f1"
        )
        self._schedule_auto_hide()

    def _play_audio(self):
        """Dinleme özelliği devre dışı bırakılmıştır."""
        pass

    def _toggle_save_word(self):
        german = self.data.get("german", "").strip()
        turkish = self.data.get("turkish", "").strip()
        if not german or not self.db:
            return

        article = self.data.get("article", "").strip()
        plural = self.data.get("plural", "").strip()
        pos = self.data.get("pos", "").strip()
        ex_de = (self.data.get("context_sentence") or self.data.get("example_de") or "").strip()
        ex_tr = self.data.get("example_tr", "").strip()

        if self.db.is_word_saved(german):
            # Kayıtlıysa sil (Toggle)
            self.db.delete_word_by_german(german)
            self.btn_save.configure(text="⭐ Deftere Ekle", bg="#6366f1")
            if self.on_save_callback:
                self.on_save_callback(german, False)
        else:
            self.db.add_word(
                german=german,
                turkish=turkish,
                article=article,
                plural=plural,
                part_of_speech=pos,
                example_de=ex_de,
                example_tr=ex_tr,
                status="learning"
            )
            self.btn_save.configure(text="✓ Kayıtlı", bg="#065f46")
            if self.on_save_callback:
                self.on_save_callback(german, True)

    def _toggle_favorite(self):
        """⭐ (Kaydet / _toggle_favorite) Kelime defterine ekler veya çıkarır."""
        return self._toggle_save_word()

    def _copy_translation(self):
        try:
            german = self.data.get("german", "")
            turkish = self.data.get("turkish", "")
            self.root.clipboard_clear()
            self.root.clipboard_append(f"{german} -> {turkish}")
            self.btn_copy.configure(text="✓")
            self.window.after(1200, lambda: self.btn_copy.configure(text="📋"))
        except Exception:
            pass

    def _position_window(self):
        self.window.update_idletasks()
        w = max(self.window.winfo_reqwidth(), 360)
        h = max(self.window.winfo_reqheight(), 180)

        # Kullanıcının daha önce sürüklediği konum varsa oraya aç
        saved_x = self.config.get("hud_x")
        saved_y = self.config.get("hud_y")

        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()

        if saved_x is not None and saved_y is not None:
            # Kullanıcının kaydettiği konumun ait olduğu monitörün çalışma alanını al
            m_left, m_top, m_right, m_bottom = get_monitor_work_area(saved_x, saved_y)
            x = max(m_left + 10, min(int(saved_x), m_right - w - 10))
            y = max(m_top + 10, min(int(saved_y), m_bottom - h - 10))
        else:
            # Varsayılan: Ekranın sağ üst köşesi (videoyu engellemeyecek nokta)
            m_left, m_top, m_right, m_bottom = get_monitor_work_area(screen_w // 2, screen_h // 2)
            x = m_right - w - 24
            y = m_top + 50

        self.window.geometry(f"{w}x{h}+{x}+{y}")

    def _bind_events(self):
        # Pencereyi sürükleyebilme
        self.header_frame.bind("<ButtonPress-1>", self._start_drag)
        self.header_frame.bind("<B1-Motion>", self._do_drag)
        self.app_title.bind("<ButtonPress-1>", self._start_drag)
        self.app_title.bind("<B1-Motion>", self._do_drag)

        # Fare kartın üzerindeyken otomatik kapanmayı durdur
        self.window.bind("<Enter>", self._on_mouse_enter)
        self.window.bind("<Leave>", self._on_mouse_leave)

    def _start_drag(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _do_drag(self, event):
        x = self.window.winfo_x() + (event.x - self._drag_start_x)
        y = self.window.winfo_y() + (event.y - self._drag_start_y)
        self.window.geometry(f"+{x}+{y}")
        self.config["hud_x"] = x
        self.config["hud_y"] = y

    def _on_mouse_enter(self, event):
        self._is_mouse_over = True
        if self.auto_hide_id:
            self.window.after_cancel(self.auto_hide_id)
            self.auto_hide_id = None

    def _on_mouse_leave(self, event):
        self._is_mouse_over = False
        self._schedule_auto_hide()

    def _schedule_auto_hide(self):
        if self.auto_hide_id:
            try:
                self.window.after_cancel(self.auto_hide_id)
            except Exception:
                pass
        duration = self.config.get("auto_hide_seconds", 12)
        if duration > 0:
            self.auto_hide_id = self.window.after(duration * 1000, self._auto_close)

    def _auto_close(self):
        if not self._is_mouse_over and self.is_alive():
            self.close()

    def close(self):
        if self.auto_hide_id:
            try:
                self.window.after_cancel(self.auto_hide_id)
            except Exception:
                pass
            self.auto_hide_id = None
        if ResultHUD._instance is self:
            ResultHUD._instance = None
        try:
            self.window.destroy()
        except Exception:
            pass
