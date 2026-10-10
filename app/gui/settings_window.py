"""
Ayarlar Penceresi Modülü (Settings Dialog)
Kullanıcının pano dinleme, kart süresi, kısayol tuşları ve API ayarlarını düzenlemesini sağlar.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable, Optional
import threading
import queue
from datetime import datetime
from app.config import save_config, DEFAULT_CONFIG
from app.gemini_service import DEFAULT_MODEL, SUPPORTED_MODELS
from app.hotkey_manager import validate_hotkey_string, format_hotkey
from app.startup_manager import is_startup_enabled, enable_startup, disable_startup


class SettingsWindow:
    def __init__(
        self,
        parent: tk.Tk,
        config: dict,
        on_settings_changed: Callable[[dict], None],
        ocr_engine=None,
        on_open_wizard: Optional[Callable[[], None]] = None
    ):
        self.config = config
        self.on_settings_changed = on_settings_changed
        self.ocr_engine = ocr_engine
        self.on_open_wizard = on_open_wizard
        self._restore_timer_id = None
        self._is_closed = False
        self._ui_queue = queue.Queue()
        self._ui_poll_id = None
        self._poll_interval_ms = 15

        self.window = tk.Toplevel(parent)
        self.window.title("Ayarlar • Ekran Sözlüğü")
        try:
            screen_h = self.window.winfo_screenheight()
            win_h = min(780, max(640, screen_h - 100))
        except Exception:
            win_h = 740
        self.window.geometry(f"580x{win_h}")
        self.window.minsize(540, 580)
        self.window.resizable(True, True)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind("<Destroy>", self._on_destroy)

        self._schedule_poll()
        self._init_ui()

    def _schedule_poll(self):
        if self._is_closed:
            return
        try:
            if self.window.winfo_exists():
                if self._ui_poll_id is not None:
                    try:
                        self.window.after_cancel(self._ui_poll_id)
                    except Exception:
                        pass
                    self._ui_poll_id = None
                self._ui_poll_id = self.window.after(self._poll_interval_ms, self._poll_queue)
        except Exception:
            pass

    def _poll_queue(self):
        self._ui_poll_id = None
        if self._is_closed:
            return
        while not self._ui_queue.empty():
            if self._is_closed:
                break
            try:
                fn = self._ui_queue.get_nowait()
                if not self._is_closed and self.window.winfo_exists():
                    fn()
            except queue.Empty:
                break
            except Exception as e:
                print(f"[Settings UI Hatası]: {e}")
        if not self._is_closed:
            self._schedule_poll()

    def post_to_ui(self, fn: Callable):
        """Worker iş parçacıklarından gelen UI görevlerini thread-safe kuyruğa ekler."""
        if not self._is_closed:
            self._ui_queue.put(fn)

    def _init_ui(self):
        # Alt Sabit Eylem ve Durum Çubuğu (Footer Frame) - Daima ekranın altında görünür kalır
        footer_frame = tk.Frame(self.window, bg="#18181b", padx=16, pady=10)
        footer_frame.pack(side="bottom", fill="x")

        # İnce ayırıcı çizgi
        tk.Frame(footer_frame, height=1, bg="#27272a").pack(fill="x", pady=(0, 6))

        # Canlı Durum Bildirim Çubuğu (Kullanıcı ayarın uygulandığını buradan anında anlar)
        self.lbl_save_status = tk.Label(
            footer_frame,
            text="💡 Değişiklikleri uygulamak için 'Ayarları Kaydet ve Uygula' butonuna basın.",
            font=("Segoe UI", 9, "bold"),
            fg="#a1a1aa",
            bg="#18181b",
            anchor="center"
        )
        self.lbl_save_status.pack(fill="x", pady=(0, 8))

        # Eylem Butonları Satırı
        action_bar = tk.Frame(footer_frame, bg="#18181b")
        action_bar.pack(fill="x")

        self.btn_reset = tk.Button(
            action_bar,
            text="🔄 Varsayılanlara Sıfırla",
            font=("Segoe UI", 9, "bold"),
            bg="#27272a",
            fg="#f59e0b",
            activebackground="#3f3f46",
            activeforeground="#fbbf24",
            relief="flat",
            padx=10,
            pady=6,
            cursor="hand2",
            command=self._reset_to_defaults
        )
        self.btn_reset.pack(side="left", padx=(0, 6))

        self.btn_save = tk.Button(
            action_bar,
            text="💾 Ayarları Kaydet ve Uygula",
            font=("Segoe UI", 9, "bold"),
            bg="#4f46e5",
            fg="#ffffff",
            activebackground="#4338ca",
            activeforeground="#ffffff",
            relief="flat",
            padx=14,
            pady=6,
            cursor="hand2",
            command=self._save
        )
        self.btn_save.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_close = tk.Button(
            action_bar,
            text="✕ Kapat",
            font=("Segoe UI", 9),
            bg="#27272a",
            fg="#d4d4d8",
            activebackground="#3f3f46",
            activeforeground="#ffffff",
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
            command=self.close
        )
        self.btn_close.pack(side="right")
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind("<Destroy>", self._on_destroy)

        # Kaydırılabilir İçerik Alanı (Canvas + Scrollbar)
        container = tk.Frame(self.window, bg="#18181b")
        container.pack(side="top", fill="both", expand=True)

        self.canvas = tk.Canvas(container, bg="#18181b", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        scrollable_frame = tk.Frame(self.canvas, bg="#18181b", padx=16, pady=10)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        canvas_frame = self.canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def _on_canvas_configure(event):
            self.canvas.itemconfig(canvas_frame, width=event.width)

        self.canvas.bind("<Configure>", _on_canvas_configure)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        def _on_mousewheel(event):
            try:
                if self.window.winfo_exists() and hasattr(self, "canvas") and self.canvas.winfo_exists():
                    self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass

        def _bind_mousewheel(event):
            self.canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(event):
            try:
                self.canvas.unbind_all("<MouseWheel>")
            except Exception:
                pass

        container.bind("<Enter>", _bind_mousewheel)
        container.bind("<Leave>", _unbind_mousewheel)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        main_frame = scrollable_frame

        tk.Label(
            main_frame,
            text="⚙️ Uygulama Ayarları",
            font=("Segoe UI", 13, "bold"),
            fg="#fafafa",
            bg="#18181b"
        ).pack(anchor="w", pady=(0, 10))

        # 1. Pano Dinleme
        # 1. Pano Dinleme (Varsayılan: Kapalı)
        self.var_clipboard = tk.BooleanVar(master=self.window, value=self.config.get("clipboard_auto_lookup", False))
        cb_clip = tk.Checkbutton(
            main_frame,
            text="📋 Panodaki Almanca metinleri otomatik çevir (Ctrl+C)",
            variable=self.var_clipboard,
            font=("Segoe UI", 9, "bold"),
            fg="#10b981",
            bg="#18181b",
            selectcolor="#27272a",
            activebackground="#18181b",
            activeforeground="#fafafa"
        )
        cb_clip.pack(anchor="w", pady=(2, 0))

        tk.Label(
            main_frame,
            text="   (Açıldığında panoya kopyalanan Almanca metinler çeviri için dış servise iletilir. Varsayılan: Kapalı)",
            font=("Segoe UI", 7, "italic"),
            fg="#a1a1aa",
            bg="#18181b"
        ).pack(anchor="w", pady=(0, 2))

        # 1b. Windows ile Otomatik Başlat
        self.var_startup = tk.BooleanVar(master=self.window, value=is_startup_enabled())
        cb_startup = tk.Checkbutton(
            main_frame,
            text="🚀 Windows başladığında otomatik olarak arka planda çalış",
            variable=self.var_startup,
            font=("Segoe UI", 9),
            fg="#38bdf8",
            bg="#18181b",
            selectcolor="#27272a",
            activebackground="#18181b",
            activeforeground="#fafafa"
        )
        cb_startup.pack(anchor="w", pady=2)

        # 2. Her Zaman Üstte
        self.var_topmost = tk.BooleanVar(master=self.window, value=self.config.get("always_on_top", True))
        cb_top = tk.Checkbutton(
            main_frame,
            text="Ana çubuk ve kartlar her zaman diğer pencerelerin üstünde kalsın",
            variable=self.var_topmost,
            font=("Segoe UI", 9),
            fg="#fafafa",
            bg="#18181b",
            selectcolor="#27272a",
            activebackground="#18181b",
            activeforeground="#fafafa"
        )
        cb_top.pack(anchor="w", pady=2)

        # 2b. Güvenlik ve Hassas Veri Uyarılarını Kapat
        self.var_disable_security = tk.BooleanVar(
            master=self.window,
            value=bool(
                self.config.get("disable_security_filter", False)
                or self.config.get("hide_security_warnings", False)
            )
        )
        cb_disable_sec = tk.Checkbutton(
            main_frame,
            text="🛡️ Güvenlik uyarısını ve korumasını kapat (Hassas veri engellemelerini kaldır)",
            variable=self.var_disable_security,
            font=("Segoe UI", 9),
            fg="#facc15",
            bg="#18181b",
            selectcolor="#27272a",
            activebackground="#18181b",
            activeforeground="#fafafa"
        )
        cb_disable_sec.pack(anchor="w", pady=2)

        tk.Label(
            main_frame,
            text="   (İşaretlendiğinde parola, token veya IBAN filtreleri kapatılır, güvenlik uyarısı çıkmaz; 'Kelime bulunamadı' gibi teknik hatalar korunur)",
            font=("Segoe UI", 7, "italic"),
            fg="#a1a1aa",
            bg="#18181b"
        ).pack(anchor="w", pady=(0, 2))

        # 2c. Sözlük Biçimi ve Ayrılabilir Fiil Tespiti (Lemmatizer)
        self.var_lemma_lookup = tk.BooleanVar(
            master=self.window,
            value=bool(self.config.get("lemma_lookup_enabled", True))
        )
        cb_lemma = tk.Checkbutton(
            main_frame,
            text="🔁 Kelimenin sözlük biçimini bul (ging → gehen, fängt … an → anfangen)",
            variable=self.var_lemma_lookup,
            font=("Segoe UI", 9),
            fg="#fafafa",
            bg="#18181b",
            selectcolor="#27272a",
            activebackground="#18181b",
            activeforeground="#fafafa"
        )
        cb_lemma.pack(anchor="w", pady=2)

        # 2d. Cümle Dilbilgisi Çözümlemesi Butonu
        self.var_grammar_analysis = tk.BooleanVar(
            master=self.window,
            value=bool(self.config.get("grammar_analysis_enabled", True))
        )
        cb_grammar = tk.Checkbutton(
            main_frame,
            text="🔍 Cümle dilbilgisi çözümlemesi butonunu göster (Akkusativ/Dativ, fiil konumu)",
            variable=self.var_grammar_analysis,
            font=("Segoe UI", 9),
            fg="#fafafa",
            bg="#18181b",
            selectcolor="#27272a",
            activebackground="#18181b",
            activeforeground="#fafafa"
        )
        cb_grammar.pack(anchor="w", pady=2)

        # 3. Otomatik Kapanma Süresi
        duration_frame = tk.Frame(main_frame, bg="#18181b", pady=3)
        duration_frame.pack(fill="x")
        tk.Label(
            duration_frame,
            text="Büyük Çeviri Kartı Süresi:",
            font=("Segoe UI", 9),
            fg="#d4d4d8",
            bg="#18181b"
        ).pack(side="left")

        self.var_duration = tk.IntVar(master=self.window, value=self.config.get("auto_hide_seconds", 12))
        sp_dur = tk.Spinbox(
            duration_frame,
            from_=0,
            to=60,
            textvariable=self.var_duration,
            width=5,
            font=("Segoe UI", 9),
            bg="#27272a",
            fg="#fafafa"
        )
        sp_dur.pack(side="left", padx=8)
        tk.Label(duration_frame, text="sn (OCR & Pano kartı için; 0 = elle kapatana kadar açık kalır)", font=("Segoe UI", 8), fg="#71717a", bg="#18181b").pack(side="left")

        # 3b. Arama Geçmişi Saklama Sınırı
        history_frame = tk.Frame(main_frame, bg="#18181b", pady=3)
        history_frame.pack(fill="x")
        tk.Label(
            history_frame,
            text="Arama Geçmişi Sınırı:",
            font=("Segoe UI", 9),
            fg="#d4d4d8",
            bg="#18181b"
        ).pack(side="left")

        self.var_history_limit = tk.IntVar(master=self.window, value=self.config.get("history_limit", 100))
        sp_hist = tk.Spinbox(
            history_frame,
            from_=10,
            to=1000,
            increment=10,
            textvariable=self.var_history_limit,
            width=5,
            font=("Segoe UI", 9),
            bg="#27272a",
            fg="#fafafa"
        )
        sp_hist.pack(side="left", padx=8)
        tk.Label(
            history_frame,
            text="kayıt (Sınıra ulaşılınca yeni aramada en eski kayıtlar silinir; Kelime Defteri etkilenmez)",
            font=("Segoe UI", 8),
            fg="#71717a",
            bg="#18181b"
        ).pack(side="left")

        # 4. Canlı Fare Üzerine Gelme (Hover) Ayarları
        hover_section = tk.LabelFrame(
            main_frame,
            text=" 🎯 Canlı Fare Üzerine Gelme (Hover OCR) Ayarları ",
            font=("Segoe UI", 9, "bold"),
            fg="#a855f7",
            bg="#18181b",
            padx=10,
            pady=6,
            relief="groove"
        )
        hover_section.pack(fill="x", pady=(4, 5))

        self.var_hover_enabled = tk.BooleanVar(master=self.window, value=self.config.get("hover_enabled", True))
        cb_hover = tk.Checkbutton(
            hover_section,
            text="Canlı Hover Modu (Farenin altındaki kelimeyi okuma aktif)",
            variable=self.var_hover_enabled,
            font=("Segoe UI", 9, "bold"),
            fg="#c084fc",
            bg="#18181b",
            selectcolor="#27272a",
            activebackground="#18181b",
            activeforeground="#fafafa"
        )
        cb_hover.pack(anchor="w", pady=1)

        f_hover_mode = tk.Frame(hover_section, bg="#18181b")
        f_hover_mode.pack(fill="x", pady=2)
        tk.Label(f_hover_mode, text="Çeviri Tetikleyicisi:", font=("Segoe UI", 8, "bold"), fg="#d4d4d8", bg="#18181b", width=16, anchor="w").pack(side="left")

        self.var_hover_trigger = tk.StringVar(master=self.window, value=self.config.get("hover_trigger_mode", "mouse_side"))
        trigger_options = [
            ("Fare Yan Tuşu (Mouse 4/5)", "mouse_side"),
            ("Orta Tuş (Tekerlek)", "mouse_middle"),
            ("Her zaman (durunca)", "always"),
            ("Ctrl basılıyken", "ctrl"),
            ("Alt basılıyken", "alt"),
            ("Shift basılıyken", "shift"),
        ]
        for opt_text, opt_val in trigger_options:
            rb = tk.Radiobutton(
                f_hover_mode,
                text=opt_text,
                variable=self.var_hover_trigger,
                value=opt_val,
                font=("Segoe UI", 8),
                fg="#fafafa",
                bg="#18181b",
                selectcolor="#27272a",
                activebackground="#18181b",
                activeforeground="#fafafa"
            )
            rb.pack(side="left", padx=2)

        f_hover_delay = tk.Frame(hover_section, bg="#18181b")
        f_hover_delay.pack(fill="x", pady=1)
        tk.Label(f_hover_delay, text="Duraklama Süresi:", font=("Segoe UI", 8, "bold"), fg="#d4d4d8", bg="#18181b", width=16, anchor="w").pack(side="left")
        self.var_hover_delay = tk.IntVar(master=self.window, value=self.config.get("hover_delay_ms", 300))
        sp_delay = tk.Spinbox(
            f_hover_delay,
            from_=150,
            to=1000,
            increment=50,
            textvariable=self.var_hover_delay,
            width=5,
            font=("Segoe UI", 8),
            bg="#27272a",
            fg="#fafafa"
        )
        sp_delay.pack(side="left", padx=4)
        tk.Label(f_hover_delay, text="ms (Tavsiye: 250 - 350 ms)", font=("Segoe UI", 8), fg="#71717a", bg="#18181b").pack(side="left", padx=4)

        f_hover_dur = tk.Frame(hover_section, bg="#18181b")
        f_hover_dur.pack(fill="x", pady=1)
        tk.Label(f_hover_dur, text="Baloncuk Süresi:", font=("Segoe UI", 8, "bold"), fg="#d4d4d8", bg="#18181b", width=16, anchor="w").pack(side="left")
        self.var_hover_duration = tk.IntVar(master=self.window, value=self.config.get("hover_auto_hide_seconds", 5))
        sp_h_dur = tk.Spinbox(
            f_hover_dur,
            from_=0,
            to=60,
            textvariable=self.var_hover_duration,
            width=5,
            font=("Segoe UI", 8),
            bg="#27272a",
            fg="#fafafa"
        )
        sp_h_dur.pack(side="left", padx=4)
        tk.Label(f_hover_dur, text="sn (Fare kutucuğu için; 0 = sadece çarpı veya tıklama ile kapanır)", font=("Segoe UI", 8), fg="#71717a", bg="#18181b").pack(side="left", padx=4)

        tk.Label(
            hover_section,
            text="💡 İpucu: Kelimeyi çevirmek için farenizi üstüne götürüp Fare Yan Tuşuna (Mouse 4/5) basmanız yeterlidir.\nKlavyedeki Alt+V tuşu ise bu özelliği komple açıp kapatmaya yarar.",
            font=("Segoe UI", 7, "italic"),
            fg="#94a3b8",
            bg="#18181b",
            wraplength=490,
            justify="left"
        ).pack(fill="x", pady=(2, 2))

        # 5. Kısayol Tuşları (Global Hotkeys)
        hotkey_section = tk.LabelFrame(
            main_frame,
            text=" ⌨️ Global Kısayol Tuşları ",
            font=("Segoe UI", 9, "bold"),
            fg="#38bdf8",
            bg="#18181b",
            padx=10,
            pady=6,
            relief="groove"
        )
        hotkey_section.pack(fill="x", pady=(4, 5))

        # 5a. OCR Kısayolu
        f_ocr = tk.Frame(hotkey_section, bg="#18181b")
        f_ocr.pack(fill="x", pady=1)
        tk.Label(f_ocr, text="Ekran Kırpıcı (OCR):", font=("Segoe UI", 8), fg="#d4d4d8", bg="#18181b", width=22, anchor="w").pack(side="left")
        self.entry_hotkey_ocr = tk.Entry(f_ocr, font=("Segoe UI", 8, "bold"), bg="#27272a", fg="#38bdf8", insertbackground="white", width=14)
        self.entry_hotkey_ocr.pack(side="left", padx=4)
        self.entry_hotkey_ocr.insert(0, self.config.get("hotkey_ocr", "tab+space"))
        tk.Label(f_ocr, text="(Tavsiye: tab+space - Donuk kare yakalar)", font=("Segoe UI", 7), fg="#71717a", bg="#18181b").pack(side="left", padx=4)

        # Hızlı seçim butonları (Presets)
        f_presets = tk.Frame(hotkey_section, bg="#18181b")
        f_presets.pack(fill="x", pady=(1, 3))
        tk.Label(f_presets, text="Hızlı OCR Tuşu:", font=("Segoe UI", 7), fg="#71717a", bg="#18181b", width=22, anchor="w").pack(side="left")
        presets = [("Tab + Boşluk", "tab+space"), ("Alt + X", "alt+x"), ("Ctrl + Boşluk", "ctrl+space")]
        for preset_name, preset_val in presets:
            btn_preset = tk.Button(
                f_presets,
                text=preset_name,
                font=("Segoe UI", 7, "bold"),
                bg="#27272a",
                fg="#d4d4d8",
                activebackground="#3f3f46",
                activeforeground="#ffffff",
                relief="flat",
                padx=4,
                pady=1,
                cursor="hand2",
                command=lambda val=preset_val: self._set_ocr_preset(val)
            )
            btn_preset.pack(side="left", padx=2)

        # 5b. Hover Aç/Kapa Kısayolu
        f_hov_hot = tk.Frame(hotkey_section, bg="#18181b")
        f_hov_hot.pack(fill="x", pady=1)
        tk.Label(f_hov_hot, text="Hover Modunu Aç/Kapa:", font=("Segoe UI", 8), fg="#d4d4d8", bg="#18181b", width=22, anchor="w").pack(side="left")
        self.entry_hotkey_hover = tk.Entry(f_hov_hot, font=("Segoe UI", 8), bg="#27272a", fg="#fafafa", insertbackground="white", width=14)
        self.entry_hotkey_hover.pack(side="left", padx=4)
        self.entry_hotkey_hover.insert(0, self.config.get("hotkey_hover", "alt+v"))
        tk.Label(f_hov_hot, text="(Örn: alt+v - Özelliği açar/kapatır)", font=("Segoe UI", 7), fg="#71717a", bg="#18181b").pack(side="left", padx=4)

        # 5c. Çubuğu Gizle / Göster
        f_overlay = tk.Frame(hotkey_section, bg="#18181b")
        f_overlay.pack(fill="x", pady=1)
        tk.Label(f_overlay, text="Ana Çubuğu Gizle/Göster:", font=("Segoe UI", 8), fg="#d4d4d8", bg="#18181b", width=22, anchor="w").pack(side="left")
        self.entry_hotkey_overlay = tk.Entry(f_overlay, font=("Segoe UI", 8), bg="#27272a", fg="#fafafa", insertbackground="white", width=14)
        self.entry_hotkey_overlay.pack(side="left", padx=4)
        self.entry_hotkey_overlay.insert(0, self.config.get("hotkey_overlay", "alt+h"))
        tk.Label(f_overlay, text="(Örn: alt+h, f2)", font=("Segoe UI", 7), fg="#71717a", bg="#18181b").pack(side="left", padx=4)

        # 5d. Seçili Metni / Panoyu Çevir (Kısayol)
        f_clip = tk.Frame(hotkey_section, bg="#18181b")
        f_clip.pack(fill="x", pady=1)
        tk.Label(f_clip, text="Seçili Metni / Panoyu Çevir:", font=("Segoe UI", 8), fg="#d4d4d8", bg="#18181b", width=22, anchor="w").pack(side="left")
        self.entry_hotkey_clip = tk.Entry(f_clip, font=("Segoe UI", 8), bg="#27272a", fg="#fafafa", insertbackground="white", width=14)
        self.entry_hotkey_clip.pack(side="left", padx=4)
        self.entry_hotkey_clip.insert(0, self.config.get("hotkey_clipboard", "alt+c"))
        tk.Label(f_clip, text="(Örn: alt+c - Seçili kelimeyi veya panodakini çevirir)", font=("Segoe UI", 7), fg="#71717a", bg="#18181b").pack(side="left", padx=4)

        # Netleştirici bilgi kutusu
        f_clip_info = tk.Frame(hotkey_section, bg="#27272a", padx=8, pady=4)
        f_clip_info.pack(fill="x", pady=(3, 2))
        tk.Label(
            f_clip_info,
            text="💡 Kısayol Bilgisi:\n"
                 "• Alt+C: Ekranda farenizle seçtiğiniz herhangi bir kelimeyi (veya panodaki metni) anında kopyalar ve çevirir.\n"
                 "• Ctrl+C: Windows'ta herhangi bir metni kopyaladığınızda otomatik çeviri paneli açılır.",
            font=("Segoe UI", 7),
            fg="#38bdf8",
            bg="#27272a",
            justify="left",
            wraplength=480
        ).pack(anchor="w")

        # 5e. OCR Motor Ayarları ve Canlı Test
        ocr_section = tk.LabelFrame(
            main_frame,
            text=" 🔍 Metin Tanıma (OCR) Motoru & Tesseract ",
            font=("Segoe UI", 9, "bold"),
            fg="#38bdf8",
            bg="#18181b",
            padx=10,
            pady=6,
            relief="groove"
        )
        ocr_section.pack(fill="x", pady=(4, 6))

        f_ocr_pref = tk.Frame(ocr_section, bg="#18181b")
        f_ocr_pref.pack(fill="x", pady=2)
        tk.Label(f_ocr_pref, text="OCR Tercihi:", font=("Segoe UI", 8, "bold"), fg="#d4d4d8", bg="#18181b", width=14, anchor="w").pack(side="left")

        self.var_ocr_pref = tk.StringVar(master=self.window, value=self.config.get("ocr_engine_preference", "auto"))
        ocr_opts = [
            ("Otomatik (Önerilen)", "auto"),
            ("Windows Media OCR", "windows_media"),
            ("Tesseract OCR", "tesseract"),
        ]
        for opt_lbl, opt_val in ocr_opts:
            rb = tk.Radiobutton(
                f_ocr_pref,
                text=opt_lbl,
                variable=self.var_ocr_pref,
                value=opt_val,
                font=("Segoe UI", 8),
                fg="#fafafa",
                bg="#18181b",
                selectcolor="#27272a",
                activebackground="#18181b",
                activeforeground="#fafafa"
            )
            rb.pack(side="left", padx=2)

        f_tess_path = tk.Frame(ocr_section, bg="#18181b")
        f_tess_path.pack(fill="x", pady=2)
        tk.Label(f_tess_path, text="Tesseract Yolu:", font=("Segoe UI", 8), fg="#d4d4d8", bg="#18181b", width=14, anchor="w").pack(side="left")
        self.entry_tess_cmd = tk.Entry(f_tess_path, font=("Segoe UI", 8), bg="#27272a", fg="#fafafa", insertbackground="white")
        self.entry_tess_cmd.pack(side="left", fill="x", expand=True, padx=4)
        self.entry_tess_cmd.insert(0, self.config.get("tesseract_cmd", ""))

        btn_browse_tess = tk.Button(
            f_tess_path,
            text="Gözat...",
            font=("Segoe UI", 8),
            bg="#3f3f46",
            fg="#fafafa",
            relief="flat",
            padx=6,
            cursor="hand2",
            command=self._browse_tesseract
        )
        btn_browse_tess.pack(side="left", padx=(2, 4))

        f_ocr_actions = tk.Frame(ocr_section, bg="#18181b")
        f_ocr_actions.pack(fill="x", pady=(3, 2))

        self.btn_test_ocr = tk.Button(
            f_ocr_actions,
            text="🧪 OCR Testi Yap",
            font=("Segoe UI", 8, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            activebackground="#0369a1",
            activeforeground="#ffffff",
            relief="flat",
            padx=8,
            pady=1,
            cursor="hand2",
            command=self._test_ocr_action
        )
        self.btn_test_ocr.pack(side="left")

        self.lbl_ocr_status = tk.Label(
            f_ocr_actions,
            text="OCR durumunu test etmek için butona tıklayın.",
            font=("Segoe UI", 8, "italic"),
            fg="#71717a",
            bg="#18181b",
            wraplength=380,
            justify="left",
            anchor="w"
        )
        self.lbl_ocr_status.pack(side="left", padx=8)

        # 6. Gemini API Anahtarı ve Bağlantı Kontrolü
        api_section = tk.LabelFrame(
            main_frame,
            text=" ✨ Google Gemini AI Entegrasyonu (Opsiyonel) ",
            font=("Segoe UI", 9, "bold"),
            fg="#60a5fa",
            bg="#18181b",
            padx=10,
            pady=6,
            relief="groove"
        )
        api_section.pack(fill="x", pady=(4, 6))

        tk.Label(
            api_section,
            text="Gemini API Anahtarı:",
            font=("Segoe UI", 8, "bold"),
            fg="#d4d4d8",
            bg="#18181b"
        ).pack(anchor="w")

        f_api_input = tk.Frame(api_section, bg="#18181b")
        f_api_input.pack(fill="x", pady=2)

        self.entry_api = tk.Entry(
            f_api_input,
            font=("Segoe UI", 9),
            bg="#27272a",
            fg="#fafafa",
            insertbackground="white",
            show="*"
        )
        self.entry_api.pack(side="left", fill="x", expand=True, padx=(0, 4))
        saved_key = self.config.get("gemini_api_key", "")
        self.entry_api.insert(0, saved_key)

        # Şifre Göster/Gizle Butonu
        self._api_masked = True
        self.btn_toggle_mask = tk.Button(
            f_api_input,
            text="👁",
            font=("Segoe UI", 8),
            bg="#3f3f46",
            fg="#d4d4d8",
            relief="flat",
            padx=5,
            cursor="hand2",
            command=self._toggle_api_mask
        )
        self.btn_toggle_mask.pack(side="left", padx=(0, 4))

        # Bağlantı Test Butonu
        self.btn_test_api = tk.Button(
            f_api_input,
            text="🔍 Test Et",
            font=("Segoe UI", 8, "bold"),
            bg="#2563eb",
            fg="#ffffff",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            relief="flat",
            padx=8,
            cursor="hand2",
            command=self._test_gemini_api
        )
        self.btn_test_api.pack(side="left", padx=(0, 4))

        # Anahtarı Temizle / Sil Butonu (Açık ve kasıtlı silme)
        self.btn_clear_api = tk.Button(
            f_api_input,
            text="🗑 Sil",
            font=("Segoe UI", 8),
            bg="#3f3f46",
            fg="#f87171",
            activebackground="#ef4444",
            activeforeground="#ffffff",
            relief="flat",
            padx=6,
            cursor="hand2",
            command=self._clear_api_key
        )
        self.btn_clear_api.pack(side="left")

        # Durum İbaresi (Status Label)
        has_decrypt_error = bool(self.config.get("_gemini_api_key_error") or (not saved_key and self.config.get("_gemini_api_key_encrypted_raw")))
        if has_decrypt_error:
            init_status = "⚠️ Kayıtlı anahtar bu cihazda çözülemedi (DPAPI hatası). Yeni anahtar girebilir veya silebilirsiniz."
            init_color = "#ef4444"
        elif saved_key:
            init_status = "🔑 Kayıtlı anahtar mevcut. Test etmek için 'Test Et'e basın."
            init_color = "#38bdf8"
        else:
            init_status = "⚪ API anahtarı girilmedi (Temel çeviri motoru aktif)"
            init_color = "#71717a"

        self.lbl_api_status = tk.Label(
            api_section,
            text=init_status,
            font=("Segoe UI", 8, "italic"),
            fg=init_color,
            bg="#18181b",
            wraplength=460,
            justify="left",
            anchor="w"
        )
        self.lbl_api_status.pack(fill="x", pady=(3, 4))

        # Ayırıcı ince çizgi
        tk.Frame(api_section, height=1, bg="#27272a").pack(fill="x", pady=4)

        # Doğrudan Gemini ile Çevir Seçeneği
        self.var_use_gemini_direct = tk.BooleanVar(master=self.window, value=self.config.get("use_gemini_direct", False))
        cb_gemini_direct = tk.Checkbutton(
            api_section,
            text="🤖 Her Şeyi Doğrudan Gemini AI ile Çevir (Öncelikli Mod)",
            variable=self.var_use_gemini_direct,
            font=("Segoe UI", 9, "bold"),
            fg="#93c5fd",
            bg="#18181b",
            selectcolor="#27272a",
            activebackground="#18181b",
            activeforeground="#fafafa"
        )
        cb_gemini_direct.pack(anchor="w", pady=(2, 2))

        # Model Seçimi
        f_model = tk.Frame(api_section, bg="#18181b")
        f_model.pack(fill="x", pady=3)

        tk.Label(
            f_model,
            text="Kullanılacak Model:",
            font=("Segoe UI", 8, "bold"),
            fg="#d4d4d8",
            bg="#18181b",
            width=18,
            anchor="w"
        ).pack(side="left")

        from app.gemini_service import SUPPORTED_MODELS
        self.var_gemini_model = tk.StringVar(master=self.window, value=self.config.get("gemini_model", DEFAULT_MODEL))
        model_choices = [m[0] for m in SUPPORTED_MODELS]
        self.cb_model_choice = ttk.Combobox(
            f_model,
            textvariable=self.var_gemini_model,
            values=model_choices,
            state="readonly",
            width=22,
            font=("Segoe UI", 8)
        )
        self.cb_model_choice.pack(side="left", padx=4)

        tk.Label(
            f_model,
            text="(⚡ Düşük Maliyet & Flash)",
            font=("Segoe UI", 8, "italic"),
            fg="#10b981",
            bg="#18181b"
        ).pack(side="left")

        # Bilgilendirme Notu
        tk.Label(
            api_section,
            text="💡 İpucu: Güncel Flash modelleri (ör. gemini-3.5-flash-lite, gemini-3.8-flash) Google AI Studio'da hızlı ve ekonomik artikel, çoğul ve dilbilgisi sonuçları üretir. Güncel model ve kota belgeleri için ai.google.dev adresini ziyaret edebilirsiniz.",
            font=("Segoe UI", 7, "italic"),
            fg="#9ca3af",
            bg="#18181b",
            wraplength=480,
            justify="left"
        ).pack(fill="x", pady=(3, 2))

        # Sihirbaz Butonu
        self.btn_wizard = tk.Button(
            main_frame,
            text="🚀 Başlangıç Rehberini & Kısayol Sihirbazını Aç",
            font=("Segoe UI", 9, "bold"),
            bg="#27272a",
            fg="#38bdf8",
            activebackground="#3f3f46",
            activeforeground="#ffffff",
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._launch_wizard
        )
        self.btn_wizard.pack(fill="x", pady=(4, 2))

    def _set_ocr_preset(self, preset_value: str):
        self.entry_hotkey_ocr.delete(0, tk.END)
        self.entry_hotkey_ocr.insert(0, preset_value)

    def _toggle_api_mask(self):
        """API anahtarı gizleme/gösterme durumunu değiştirir."""
        if self._api_masked:
            self.entry_api.configure(show="")
            self.btn_toggle_mask.configure(text="🔒")
            self._api_masked = False
        else:
            self.entry_api.configure(show="*")
            self.btn_toggle_mask.configure(text="👁")
            self._api_masked = True

    def _clear_api_key(self):
        """API anahtarı giriş kutusunu temizler ve açık silme durumunu işaretler."""
        self.entry_api.delete(0, tk.END)
        self._explicit_key_cleared = True
        self.config["gemini_api_key"] = ""
        self.config["_gemini_api_key_cleared"] = True
        self.config.pop("_gemini_api_key_encrypted_raw", None)
        self.config.pop("_gemini_api_key_error", None)
        self.lbl_api_status.configure(
            text="⚪ API anahtarı temizlendi (Ayarları Kaydet ile silinecektir)",
            fg="#a1a1aa"
        )

    def _test_gemini_api(self):
        """Gemini API anahtarını asenkron olarak test eder ve sonucu kullanıcıya bildirir."""
        key = self.entry_api.get().strip()
        if not key:
            if self.config.get("_gemini_api_key_encrypted_raw") or self.config.get("_gemini_api_key_error"):
                self.lbl_api_status.configure(
                    text="⚠️ Kayıtlı anahtar bu cihazda çözülemedi. Lütfen yeni bir API anahtarı girin.",
                    fg="#ef4444"
                )
            else:
                self.lbl_api_status.configure(
                    text="⚠️ Lütfen önce bir Gemini API anahtarı girin.",
                    fg="#f59e0b"
                )
            return

        from app.security import is_dpapi_protected
        if is_dpapi_protected(key):
            self.lbl_api_status.configure(
                text="⚠️ Şifreli metin doğrudan test edilemez. Lütfen geçerli bir Gemini API anahtarı girin.",
                fg="#ef4444"
            )
            return

        self.btn_test_api.configure(state="disabled")
        self.lbl_api_status.configure(
            text="⏳ Google sunucularına bağlanılıyor, lütfen bekleyin...",
            fg="#facc15"
        )

        def _worker():
            from app.gemini_service import GeminiService
            gs = GeminiService(key)
            success, message = gs.test_connection()

            def _update_ui():
                try:
                    if not self._is_closed and self.window.winfo_exists():
                        self.btn_test_api.configure(state="normal")
                        color = "#10b981" if success else "#ef4444"
                        self.lbl_api_status.configure(text=message, fg=color)
                except Exception:
                    pass

            self.post_to_ui(_update_ui)

        threading.Thread(target=_worker, daemon=True).start()

    def _save(self, is_reset: bool = False, close_window: bool = False):
        hotkey_ocr = self.entry_hotkey_ocr.get().strip().lower()
        hotkey_hover = self.entry_hotkey_hover.get().strip().lower()
        hotkey_overlay = self.entry_hotkey_overlay.get().strip().lower()
        hotkey_clip = self.entry_hotkey_clip.get().strip().lower()

        # Doğrulama (Validation)
        fields = [
            ("Ekran Kırp / OCR", hotkey_ocr),
            ("Hover Modu Aç/Kapa", hotkey_hover),
            ("Çubuğu Gizle/Göster", hotkey_overlay),
            ("Panoyu Çevir", hotkey_clip),
        ]
        seen_hotkeys = {}
        for name, key_str in fields:
            if not key_str:
                if hasattr(self, "lbl_save_status"):
                    self.lbl_save_status.configure(
                        text=f"⚠️ '{name}' kısayolu boş bırakılamaz.",
                        fg="#ef4444"
                    )
                messagebox.showerror("Hata", f"'{name}' kısayolu boş bırakılamaz.", parent=self.window)
                return
            valid, err = validate_hotkey_string(key_str)
            if not valid:
                if hasattr(self, "lbl_save_status"):
                    self.lbl_save_status.configure(
                        text=f"⚠️ '{name}' için geçersiz kısayol tuşu!",
                        fg="#ef4444"
                    )
                messagebox.showerror(
                    "Geçersiz Kısayol",
                    f"'{name}' için geçersiz kısayol tuşu!\n{err}\n\nÖrnek tuşlar: tab, space, alt, ctrl, shift, f1-f12, a-z, 0-9",
                    parent=self.window
                )
                return
            normalized = format_hotkey(key_str).lower()
            if normalized in seen_hotkeys:
                other_name = seen_hotkeys[normalized]
                if hasattr(self, "lbl_save_status"):
                    self.lbl_save_status.configure(
                        text=f"⚠️ Kısayol çakışması: '{name}' ile '{other_name}' aynı tuşa ({normalized}) sahip!",
                        fg="#ef4444"
                    )
                messagebox.showerror(
                    "Kısayol Çakışması",
                    f"'{name}' ve '{other_name}' için aynı kısayol tuşu ({normalized}) atanamaz!\n\nLütfen farklı tuş kombinasyonları belirleyin.",
                    parent=self.window
                )
                return
            seen_hotkeys[normalized] = name

        self.config["clipboard_auto_lookup"] = self.var_clipboard.get()
        self.config.pop("sound_enabled", None)
        self.config["always_on_top"] = self.var_topmost.get()
        if hasattr(self, "var_disable_security"):
            disable_sec = bool(self.var_disable_security.get())
            self.config["disable_security_filter"] = disable_sec
            self.config["hide_security_warnings"] = disable_sec
            self.config["hide_translation_warnings"] = False
            self.config["show_translation_warnings"] = True
        if hasattr(self, "var_lemma_lookup"):
            self.config["lemma_lookup_enabled"] = bool(self.var_lemma_lookup.get())
        if hasattr(self, "var_grammar_analysis"):
            self.config["grammar_analysis_enabled"] = bool(self.var_grammar_analysis.get())
        self.config["auto_hide_seconds"] = self.var_duration.get()
        if hasattr(self, "var_history_limit"):
            try:
                self.config["history_limit"] = int(self.var_history_limit.get())
            except (ValueError, TypeError):
                self.config["history_limit"] = 100
        entered_key = self.entry_api.get().strip()
        if entered_key:
            self.config["gemini_api_key"] = entered_key
            self.config.pop("_gemini_api_key_encrypted_raw", None)
            self.config.pop("_gemini_api_key_cleared", None)
            self.config.pop("_gemini_api_key_error", None)
        elif getattr(self, "_explicit_key_cleared", False):
            self.config["gemini_api_key"] = ""
            self.config["_gemini_api_key_cleared"] = True
            self.config.pop("_gemini_api_key_encrypted_raw", None)
            self.config.pop("_gemini_api_key_error", None)
        else:
            self.config["gemini_api_key"] = ""
        self.config["use_gemini_direct"] = self.var_use_gemini_direct.get()
        self.config["gemini_model"] = self.var_gemini_model.get().strip() or DEFAULT_MODEL

        # Hover Ayarları
        self.config["hover_enabled"] = self.var_hover_enabled.get()
        self.config["hover_trigger_mode"] = self.var_hover_trigger.get()
        self.config["hover_delay_ms"] = self.var_hover_delay.get()
        self.config["hover_auto_hide_seconds"] = self.var_hover_duration.get()

        # Kısayollar
        self.config["hotkey_ocr"] = hotkey_ocr
        self.config["hotkey_hover"] = hotkey_hover
        self.config["hotkey_overlay"] = hotkey_overlay
        self.config["hotkey_clipboard"] = hotkey_clip

        # OCR Motor Tercihleri
        if hasattr(self, "entry_tess_cmd"):
            self.config["tesseract_cmd"] = self.entry_tess_cmd.get().strip()
        if hasattr(self, "var_ocr_pref"):
            self.config["ocr_engine_preference"] = self.var_ocr_pref.get()

        # Otomatik başlatma kayıt defteri güncelleme
        want_startup = self.var_startup.get()
        if want_startup:
            enable_startup()
        else:
            disable_startup()

        saved = save_config(self.config)
        if not saved:
            if hasattr(self, "lbl_save_status"):
                self.lbl_save_status.configure(
                    text="❌ Ayarlar kaydedilemedi! Dosya yazma hatası.",
                    fg="#ef4444"
                )
            messagebox.showerror(
                "Kayıt Hatası",
                "Ayarlar dosyasına yazılamadı. Lütfen disk izinlerinizi kontrol edin.",
                parent=self.window
            )
            return

        self.on_settings_changed(self.config)

        # Durum bildirimi ve görsel geri bildirim
        time_str = datetime.now().strftime("%H:%M:%S")
        if is_reset:
            if hasattr(self, "lbl_save_status"):
                self.lbl_save_status.configure(
                    text=f"🔄 Ayarlar varsayılana sıfırlandı ve anında uygulandı! ({time_str})",
                    fg="#f59e0b"
                )
            messagebox.showinfo(
                "Sıfırlandı",
                "Tüm ayarlar başarıyla varsayılan fabrika değerlerine sıfırlandı ve uygulandı.",
                parent=self.window
            )
        else:
            if hasattr(self, "lbl_save_status"):
                self.lbl_save_status.configure(
                    text=f"✅ Ayarlar başarıyla kaydedildi ve tüm sisteme uygulandı! ({time_str})",
                    fg="#10b981"
                )
            if hasattr(self, "btn_save") and self.window.winfo_exists():
                self.btn_save.configure(text="✅ Kaydedildi ve Uygulandı!", bg="#059669")
                try:
                    if hasattr(self, "_restore_timer_id") and self._restore_timer_id:
                        self.window.after_cancel(self._restore_timer_id)
                    self._restore_timer_id = self.window.after(3000, self._restore_save_button)
                except Exception:
                    pass
            messagebox.showinfo(
                "Başarılı",
                "Ayarlar başarıyla kaydedildi ve tüm sisteme anında uygulandı.\n\nYeni ayarlarınız hemen geçerlidir.",
                parent=self.window
            )

        if close_window:
            self.close()

    def close(self):
        """Pencereyi kapatır ve bekleyen zamanlayıcıları iptal eder."""
        self._is_closed = True
        if hasattr(self, "_restore_timer_id") and self._restore_timer_id:
            try:
                self.window.after_cancel(self._restore_timer_id)
            except Exception:
                pass
            self._restore_timer_id = None
        if self._ui_poll_id is not None:
            try:
                self.window.after_cancel(self._ui_poll_id)
            except Exception:
                pass
            self._ui_poll_id = None
        while not self._ui_queue.empty():
            try:
                self._ui_queue.get_nowait()
            except Exception:
                break
        try:
            self.window.destroy()
        except Exception:
            pass

    def _on_destroy(self, event):
        """Pencere yok edildiğinde bekleyen zamanlayıcıları iptal eder."""
        if getattr(event, "widget", None) == self.window:
            self._is_closed = True
            if hasattr(self, "_restore_timer_id") and self._restore_timer_id:
                try:
                    self.window.after_cancel(self._restore_timer_id)
                except Exception:
                    pass
                self._restore_timer_id = None
            if self._ui_poll_id is not None:
                try:
                    self.window.after_cancel(self._ui_poll_id)
                except Exception:
                    pass
                self._ui_poll_id = None
            while not self._ui_queue.empty():
                try:
                    self._ui_queue.get_nowait()
                except Exception:
                    break
            try:
                if hasattr(self, "canvas") and self.canvas:
                    self.canvas.unbind_all("<MouseWheel>")
            except Exception:
                pass

    def _restore_save_button(self):
        self._restore_timer_id = None
        try:
            if hasattr(self, "btn_save") and self.window.winfo_exists():
                self.btn_save.configure(text="💾 Ayarları Kaydet ve Uygula", bg="#4f46e5")
        except Exception:
            pass

    def _reset_to_defaults(self):
        """Tüm ayarları DEFAULT_CONFIG değerlerine döndürür ve kullanıcıdan onay alır."""
        confirm = messagebox.askyesno(
            "Ayarları Sıfırla",
            "Tüm ayarları varsayılan fabrika değerlerine sıfırlamak istediğinize emin misiniz?\n\n"
            "• Kısayollar: Tab+Space (OCR), Alt+H (Çubuk), Alt+C (Seçili Metin / Pano), Alt+V (Hover Aç/Kapa)\n"
            "• Otomatik Çeviri: Ctrl+C ile kopyalama ve Fare Yan Tuşu ile Canlı Okuma\n"
            "• Canlı Hover: Açık, Fare Yan Tuşu (Mouse 4/5), 300 ms, 5 sn\n"
            "• OCR ve Yapay Zeka tercihleri varsayılana dönecektir.\n\n"
            "Sıfırlamayı onaylıyor musunuz?",
            parent=self.window
        )
        if not confirm:
            return

        # 1. Pano Dinleme, Otomatik Başlatma, Her Zaman Üstte, Süre, Geçmiş Limiti
        self.var_clipboard.set(DEFAULT_CONFIG.get("clipboard_auto_lookup", False))
        self.var_startup.set(False)
        self.var_topmost.set(DEFAULT_CONFIG.get("always_on_top", True))
        if hasattr(self, "var_disable_security"):
            self.var_disable_security.set(DEFAULT_CONFIG.get("disable_security_filter", False))
        if hasattr(self, "var_lemma_lookup"):
            self.var_lemma_lookup.set(DEFAULT_CONFIG.get("lemma_lookup_enabled", True))
        if hasattr(self, "var_grammar_analysis"):
            self.var_grammar_analysis.set(DEFAULT_CONFIG.get("grammar_analysis_enabled", True))
        self.var_duration.set(DEFAULT_CONFIG.get("auto_hide_seconds", 12))
        if hasattr(self, "var_history_limit"):
            self.var_history_limit.set(DEFAULT_CONFIG.get("history_limit", 100))

        # 2. Canlı Hover
        self.var_hover_enabled.set(DEFAULT_CONFIG.get("hover_enabled", True))
        self.var_hover_trigger.set(DEFAULT_CONFIG.get("hover_trigger_mode", "mouse_side"))
        self.var_hover_delay.set(DEFAULT_CONFIG.get("hover_delay_ms", 300))
        self.var_hover_duration.set(DEFAULT_CONFIG.get("hover_auto_hide_seconds", 5))

        # 3. Kısayollar
        self.entry_hotkey_ocr.delete(0, tk.END)
        self.entry_hotkey_ocr.insert(0, DEFAULT_CONFIG.get("hotkey_ocr", "tab+space"))

        self.entry_hotkey_hover.delete(0, tk.END)
        self.entry_hotkey_hover.insert(0, DEFAULT_CONFIG.get("hotkey_hover", "alt+v"))

        self.entry_hotkey_overlay.delete(0, tk.END)
        self.entry_hotkey_overlay.insert(0, DEFAULT_CONFIG.get("hotkey_overlay", "alt+h"))

        self.entry_hotkey_clip.delete(0, tk.END)
        self.entry_hotkey_clip.insert(0, DEFAULT_CONFIG.get("hotkey_clipboard", "alt+c"))

        # 4. OCR
        if hasattr(self, "var_ocr_pref"):
            self.var_ocr_pref.set(DEFAULT_CONFIG.get("ocr_engine_preference", "auto"))
        if hasattr(self, "entry_tess_cmd"):
            self.entry_tess_cmd.delete(0, tk.END)
            self.entry_tess_cmd.insert(0, DEFAULT_CONFIG.get("tesseract_cmd", ""))
        if hasattr(self, "lbl_ocr_status"):
            self.lbl_ocr_status.configure(
                text="OCR durumunu test etmek için butona tıklayın.",
                fg="#71717a"
            )

        # 5. Gemini API
        if hasattr(self, "entry_api"):
            self.entry_api.delete(0, tk.END)
            self.entry_api.insert(0, DEFAULT_CONFIG.get("gemini_api_key", ""))
            self._explicit_key_cleared = True
            self.config["_gemini_api_key_cleared"] = True
            self.config.pop("_gemini_api_key_encrypted_raw", None)
            self.config.pop("_gemini_api_key_error", None)
        if hasattr(self, "var_use_gemini_direct"):
            self.var_use_gemini_direct.set(DEFAULT_CONFIG.get("use_gemini_direct", False))
        if hasattr(self, "var_gemini_model"):
            self.var_gemini_model.set(DEFAULT_CONFIG.get("gemini_model", DEFAULT_MODEL))
        if hasattr(self, "lbl_api_status"):
            self.lbl_api_status.configure(
                text="⚪ API anahtarı girilmedi (Temel çeviri motoru aktif)",
                fg="#71717a"
            )

        # Sıfırlanan ayarları anında kaydet ve sisteme uygula
        self._save(is_reset=True, close_window=False)

    def _browse_tesseract(self):
        filename = filedialog.askopenfilename(
            parent=self.window,
            title="Tesseract Yürütülebilir Dosyasını Seçin (tesseract.exe)",
            filetypes=[("Yürütülebilir Dosyalar", "*.exe"), ("Tüm Dosyalar", "*.*")]
        )
        if filename:
            self.entry_tess_cmd.delete(0, tk.END)
            self.entry_tess_cmd.insert(0, filename)

    def _test_ocr_action(self):
        from app.ocr_engine import OCREngine
        tess_path = self.entry_tess_cmd.get().strip() if hasattr(self, "entry_tess_cmd") else ""
        pref = self.var_ocr_pref.get() if hasattr(self, "var_ocr_pref") else "auto"
        engine = self.ocr_engine or OCREngine(tesseract_cmd=tess_path, preference=pref)
        self.btn_test_ocr.configure(state="disabled")
        self.lbl_ocr_status.configure(text="⏳ OCR test ediliyor...", fg="#facc15")

        def _worker():
            success, msg = engine.test_ocr("Guten Tag")
            def _update():
                try:
                    if not self._is_closed and self.window.winfo_exists():
                        self.btn_test_ocr.configure(state="normal")
                        color = "#10b981" if success else "#ef4444"
                        self.lbl_ocr_status.configure(text=msg, fg=color)
                except Exception:
                    pass
            self.post_to_ui(_update)

        threading.Thread(target=_worker, daemon=True).start()

    def _launch_wizard(self):
        if self.on_open_wizard:
            self.window.destroy()
            self.on_open_wizard()
        else:
            from app.gui.onboarding_wizard import OnboardingWizard
            from app.ocr_engine import OCREngine
            from app.translator import TranslationEngine
            eng = self.ocr_engine or OCREngine()
            trans = TranslationEngine(gemini_api_key=self.config.get("gemini_api_key", ""))
            OnboardingWizard(self.window.master, self.config, eng, trans)
            self.window.destroy()
