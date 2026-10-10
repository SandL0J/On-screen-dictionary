"""
Yüzen Ana Kontrol Çubuğu (Floating Companion Bar / Mini-Widget)
Videoların veya okuma uygulamalarının üzerinde sessizce duran,
hızlı arama, ekran kırpma (OCR), genel kısayollar (Alt+X, Alt+H, Alt+C) ve kelime defteri erişimi sağlayan mini arayüz.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
from typing import Callable, Optional

from app.gui.result_hud import ResultHUD
from app.gui.snipper import ScreenSnipper
from app.gui.wordbook_window import WordbookWindow
from app.gui.settings_window import SettingsWindow
from app.gui.hover_tooltip import HoverTooltip
from app.gui.onboarding_wizard import OnboardingWizard
from app.hover_tracker import HoverTracker
from app.hotkey_manager import HotkeyManager, format_hotkey
from app.clipboard_watcher import get_clipboard_text, copy_selected_text_windows
from app.security import check_sensitive_clipboard
from app.worker_pool import WorkerThreadPool
from app.german_analyzer import is_single_word
from app.lemmatizer import resolve_lemma, format_lemma_hint


class MainOverlay:
    def __init__(self, root: tk.Tk, translator, *args, tts_engine=None, ocr_engine=None, db=None, clipboard_watcher=None, config: dict = None, **kwargs):
        self.root = root
        self.translator = translator

        resolved_ocr = ocr_engine
        resolved_db = db
        resolved_clip = clipboard_watcher
        resolved_config = config
        resolved_tts = tts_engine

        if resolved_ocr is None and len(args) > 0:
            if len(args) >= 5:
                # Eski imza: (tts_engine, ocr_engine, db, clipboard_watcher, config)
                resolved_tts = args[0]
                resolved_ocr = args[1]
                resolved_db = args[2]
                resolved_clip = args[3]
                resolved_config = args[4]
            elif len(args) == 4:
                # Yeni imza: (ocr_engine, db, clipboard_watcher, config)
                resolved_ocr = args[0]
                resolved_db = args[1]
                resolved_clip = args[2]
                resolved_config = args[3]
            elif len(args) == 3:
                resolved_ocr = args[0]
                resolved_db = args[1]
                resolved_clip = args[2]

        self.tts = resolved_tts
        self.ocr = resolved_ocr
        self.db = resolved_db
        self.clipboard_watcher = resolved_clip
        self.config = resolved_config or {}

        worker_pool = kwargs.pop("worker_pool", None)
        self._worker_pool = worker_pool or WorkerThreadPool(max_workers=4, thread_name_prefix="EkranSozlugu-Worker")

        self._is_bar_visible = True
        self._is_stopped = False
        self._ui_queue: queue.Queue = queue.Queue()
        self._ui_poll_id: Optional[str] = None
        self._poll_interval_ms: int = 15
        self._onboarding_after_id: Optional[str] = None
        self._after_ids: set = set()
        self._lookup_generation: int = 0
        self._lookup_lock = threading.Lock()

        # Tk ana iş parçacığı periyodik kuyruk dinleyicisini başlat
        self._schedule_ui_queue_poll()

        self.root.title("Ekran Sözlüğü • Almanca Asistanı")
        self.root.overrideredirect(True)  # Kenarlıksız modern çubuk
        self.root.attributes("-topmost", self.config.get("always_on_top", True))
        self.root.attributes("-alpha", 0.96)

        # Snipper başlatıcı
        self.snipper = ScreenSnipper(
            self.root,
            self.ocr,
            self.lookup_text,
            post_to_ui=self.post_to_ui,
            worker_pool=self._worker_pool,
            config=self.config
        )

        # Canlı Hover Tooltip ve Takipçisi (İş parçacığı güvenli sarmalayıcılar ile)
        self.hover_tooltip = HoverTooltip(
            self.root,
            db=self.db,
            auto_hide_seconds=self.config.get("hover_auto_hide_seconds", 5),
            post_to_ui=self.post_to_ui
        )

        def _safe_hover_show(word_data, x, y):
            self.post_to_ui(self.hover_tooltip.show, word_data, x, y)

        def _safe_hover_hide():
            # Hover modu kapatıldıysa kutucuğu kesinlikle gizle
            if hasattr(self, "hover_tracker") and not self.hover_tracker.is_enabled():
                self.post_to_ui(self.hover_tooltip.hide)
                return
            # Yan tuş ve orta tuş modlarında fare hareketi kutucuğu kapatmaz.
            # Otomatik kapanma süresi (hover_auto_hide_seconds) veya kullanıcı [✕] ile kapatır.
            if hasattr(self, "hover_tracker") and self.hover_tracker.trigger_mode in ("mouse_side", "mouse_middle"):
                return
            if hasattr(self, "hover_tooltip") and (self.hover_tooltip.has_active_auto_hide() or self.hover_tooltip.auto_hide_seconds == 0):
                return
            self.post_to_ui(self.hover_tooltip.hide)

        def _safe_hover_loading(x, y):
            self.post_to_ui(self.hover_tooltip.show_loading, x, y)

        def _safe_hover_not_found(x, y):
            self.post_to_ui(self.hover_tooltip.show_message, x, y, "⚠️ Kelime bulunamadı", 1300)

        if getattr(self, "clipboard_watcher", None) and hasattr(self.clipboard_watcher, "config"):
            self.clipboard_watcher.config = self.config

        self.hover_tracker = HoverTracker(
            ocr_engine=self.ocr,
            translator=self.translator,
            on_word_hover=_safe_hover_show,
            on_hover_leave=_safe_hover_hide,
            on_loading=_safe_hover_loading,
            on_not_found=_safe_hover_not_found,
            hover_delay_ms=self.config.get("hover_delay_ms", 300),
            trigger_mode=self.config.get("hover_trigger_mode", "mouse_side"),
            enabled=self.config.get("hover_enabled", True),
            worker_pool=self._worker_pool,
            config=self.config,
        )
        self.hover_tracker.start()

        self._init_ui()
        self._set_initial_position()
        self._bind_drag_events()
        self._setup_hotkeys()

        # İlk çalıştırma sihirbazı
        if not self.config.get("first_run_completed", False):
            try:
                self._onboarding_after_id = self.root.after(450, self._open_onboarding_wizard)
                self._after_ids.add(self._onboarding_after_id)
            except Exception:
                pass

    def _setup_hotkeys(self):
        """Global Windows kısayol tuşlarını bağlar."""
        self.hotkey_mgr = HotkeyManager()
        self._register_configured_hotkeys()
        self.hotkey_mgr.start()

    def _register_configured_hotkeys(self):
        """Yapılandırmadaki güncel kısayolları bağlar."""
        hotkey_ocr = self.config.get("hotkey_ocr", "tab+space")
        hotkey_hover = self.config.get("hotkey_hover", "alt+v")
        hotkey_overlay = self.config.get("hotkey_overlay", "alt+h")
        hotkey_clipboard = self.config.get("hotkey_clipboard", "alt+c")

        # Güvenli kısayol kaydı: yapılandırmadaki tuş geçersizse varsayılana dön
        try:
            self.hotkey_mgr.register("ocr", hotkey_ocr, lambda: self.post_to_ui(self._trigger_ocr_hotkey))
        except Exception:
            self.hotkey_mgr.register("ocr", "tab+space", lambda: self.post_to_ui(self._trigger_ocr_hotkey))

        try:
            self.hotkey_mgr.register("hover", hotkey_hover, lambda: self.post_to_ui(self._toggle_hover))
        except Exception:
            self.hotkey_mgr.register("hover", "alt+v", lambda: self.post_to_ui(self._toggle_hover))

        try:
            self.hotkey_mgr.register("overlay", hotkey_overlay, lambda: self.post_to_ui(self._toggle_bar_visibility))
        except Exception:
            self.hotkey_mgr.register("overlay", "alt+h", lambda: self.post_to_ui(self._toggle_bar_visibility))

        try:
            self.hotkey_mgr.register("clipboard", hotkey_clipboard, lambda: self.post_to_ui(self._lookup_from_clipboard))
        except Exception:
            self.hotkey_mgr.register("clipboard", "alt+c", lambda: self.post_to_ui(self._lookup_from_clipboard))

    def _trigger_ocr_hotkey(self):
        """Kısayol basıldığında pencereyi görünür yapıp öne getirir ve OCR kırpıcıyı açar."""
        if not self._is_bar_visible:
            self.root.deiconify()
            self.root.attributes("-topmost", self.config.get("always_on_top", True))
            self.root.lift()
            self._is_bar_visible = True
        else:
            self.root.deiconify()
            self.root.attributes("-topmost", self.config.get("always_on_top", True))
            self.root.lift()
        self._start_ocr_snip()

    def _init_ui(self):
        self.bg_color = "#18181b"
        self.border_color = "#3f3f46"

        self.root.configure(bg=self.border_color)

        self.bar_frame = tk.Frame(self.root, bg=self.bg_color, padx=8, pady=5)
        self.bar_frame.pack(padx=1, pady=1, fill="both", expand=True)

        # 1. Sürükleme Tutamacı / Logo
        self.drag_grip = tk.Label(
            self.bar_frame,
            text="⋮⋮ DE",
            font=("Segoe UI", 9, "bold"),
            fg="#6366f1",
            bg=self.bg_color,
            cursor="fleur"
        )
        self.drag_grip.pack(side="left", padx=(2, 6))

        # 2. Hızlı Arama Kutusu
        self.search_var = tk.StringVar(master=self.root)
        self.search_entry = tk.Entry(
            self.bar_frame,
            textvariable=self.search_var,
            font=("Segoe UI", 9),
            bg="#27272a",
            fg="#fafafa",
            insertbackground="white",
            width=15,
            relief="flat"
        )
        self.search_entry.pack(side="left", padx=(0, 6), ipady=3)
        self.search_entry.bind("<Return>", lambda e: self._on_search_enter())
        self.search_entry.insert(0, "Almanca yaz/ara...")
        self.search_entry.bind("<FocusIn>", self._on_entry_focus_in)
        self.search_entry.bind("<FocusOut>", self._on_entry_focus_out)

        # 3. Ekran Kırp / OCR Butonu
        hotkey_ocr_label = format_hotkey(self.config.get("hotkey_ocr", "tab+space"))
        self.btn_snip = tk.Button(
            self.bar_frame,
            text=f"✂ Kırp ({hotkey_ocr_label})",
            font=("Segoe UI", 8, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            activebackground="#0369a1",
            activeforeground="#ffffff",
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._start_ocr_snip
        )
        self.btn_snip.pack(side="left", padx=(0, 4))

        # 4. Pano Dinleme Aç/Kapa Butonu
        clip_active = self.clipboard_watcher.is_enabled() if self.clipboard_watcher else self.config.get("clipboard_auto_lookup", False)
        self.btn_clip = tk.Button(
            self.bar_frame,
            text="📋 Pano: AÇIK" if clip_active else "📋 Pano: KAPALI",
            font=("Segoe UI", 8, "bold"),
            bg="#059669" if clip_active else "#52525b",
            fg="#ffffff",
            activebackground="#047857",
            activeforeground="#ffffff",
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._toggle_clipboard
        )
        self.btn_clip.pack(side="left", padx=(0, 4))

        # 4b. Canlı Hover Modu Aç/Kapa Butonu
        hover_active = self.hover_tracker.is_enabled()
        self.btn_hover = tk.Button(
            self.bar_frame,
            text="👁️ Hover: AÇIK" if hover_active else "👁️ Hover: KAPALI",
            font=("Segoe UI", 8, "bold"),
            bg="#8b5cf6" if hover_active else "#52525b",
            fg="#ffffff",
            activebackground="#7c3aed",
            activeforeground="#ffffff",
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._toggle_hover
        )
        self.btn_hover.pack(side="left", padx=(0, 4))

        # 5. Kelime Defteri Butonu
        self.btn_words = tk.Button(
            self.bar_frame,
            text="📚 Defterim",
            font=("Segoe UI", 8, "bold"),
            bg="#3f3f46",
            fg="#fafafa",
            activebackground="#52525b",
            activeforeground="#ffffff",
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._open_wordbook
        )
        self.btn_words.pack(side="left", padx=(0, 4))

        # 6. Ayarlar Butonu
        self.btn_settings = tk.Button(
            self.bar_frame,
            text="⚙",
            font=("Segoe UI", 8),
            bg="#27272a",
            fg="#a1a1aa",
            activebackground="#3f3f46",
            activeforeground="#ffffff",
            relief="flat",
            padx=6,
            pady=2,
            cursor="hand2",
            command=self._open_settings
        )
        self.btn_settings.pack(side="left", padx=(0, 4))

        # 6b. Başlangıç Rehberi Butonu (?)
        self.btn_guide = tk.Button(
            self.bar_frame,
            text="?",
            font=("Segoe UI", 8, "bold"),
            bg="#27272a",
            fg="#38bdf8",
            activebackground="#3f3f46",
            activeforeground="#ffffff",
            relief="flat",
            padx=6,
            pady=2,
            cursor="hand2",
            command=self._open_onboarding_wizard
        )
        self.btn_guide.pack(side="left", padx=(0, 4))

        # 7. Gizle / Küçült Butonu (Alt+H)
        self.btn_hide = tk.Label(
            self.bar_frame,
            text="—",
            font=("Segoe UI", 9, "bold"),
            fg="#71717a",
            bg=self.bg_color,
            cursor="hand2"
        )
        self.btn_hide.pack(side="right", padx=(2, 4))
        self.btn_hide.bind("<Button-1>", lambda e: self._toggle_bar_visibility())
        self.btn_hide.bind("<Enter>", lambda e: self.btn_hide.configure(fg="#38bdf8"))
        self.btn_hide.bind("<Leave>", lambda e: self.btn_hide.configure(fg="#71717a"))

        # 8. Kapat Butonu
        self.btn_close = tk.Label(
            self.bar_frame,
            text="✕",
            font=("Segoe UI", 9, "bold"),
            fg="#71717a",
            bg=self.bg_color,
            cursor="hand2"
        )
        self.btn_close.pack(side="right", padx=(4, 2))
        self.btn_close.bind("<Button-1>", lambda e: self._on_close_clicked())
        self.btn_close.bind("<Enter>", lambda e: self.btn_close.configure(fg="#ef4444"))
        self.btn_close.bind("<Leave>", lambda e: self.btn_close.configure(fg="#71717a"))

    def _on_entry_focus_in(self, event):
        if self.search_var.get() == "Almanca yaz/ara...":
            self.search_entry.delete(0, tk.END)

    def _on_entry_focus_out(self, event):
        if not self.search_var.get().strip():
            self.search_entry.insert(0, "Almanca yaz/ara...")

    def _on_search_enter(self):
        text = self.search_var.get().strip()
        if text and text != "Almanca yaz/ara...":
            self.lookup_text(text)
            self.search_entry.select_range(0, tk.END)

    def _schedule_ui_queue_poll(self):
        if self._is_stopped:
            return
        try:
            if hasattr(self, "root") and self.root and self.root.winfo_exists():
                # Varsa eski bekleyen zamanlayıcıyı iptal et
                if self._ui_poll_id is not None:
                    try:
                        self.root.after_cancel(self._ui_poll_id)
                    except Exception:
                        pass
                    if hasattr(self, "_after_ids"):
                        self._after_ids.discard(self._ui_poll_id)
                    self._ui_poll_id = None

                poll_timer_id = None

                def _poller_callback():
                    # Callback yalnızca kendi zamanlayıcı kimliğini temizler
                    if hasattr(self, "_after_ids") and poll_timer_id in self._after_ids:
                        self._after_ids.discard(poll_timer_id)
                    if self._ui_poll_id == poll_timer_id:
                        self._ui_poll_id = None
                    if not self._is_stopped:
                        self._poll_ui_queue()

                poll_timer_id = self.root.after(self._poll_interval_ms, _poller_callback)
                self._ui_poll_id = poll_timer_id
                if hasattr(self, "_after_ids"):
                    self._after_ids.add(poll_timer_id)
        except Exception:
            pass

    def _poll_ui_queue(self):
        """Kuyruktaki arka plan UI görevlerini YALNIZCA Tk ana iş parçacığında çalıştırır."""
        # Doğrudan veya manuel çağrılarda bekleyen zamanlayıcıyı iptal et (zombi timer oluşmasını engeller)
        if self._ui_poll_id is not None:
            try:
                self.root.after_cancel(self._ui_poll_id)
            except Exception:
                pass
            if hasattr(self, "_after_ids"):
                self._after_ids.discard(self._ui_poll_id)
            self._ui_poll_id = None

        if self._is_stopped:
            return

        while not self._ui_queue.empty():
            if self._is_stopped:
                break
            try:
                item = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                func, args = item
                if not self._is_stopped:
                    func(*args)
            except Exception as e:
                print(f"[UI Kuyruk Hatası]: {e}")

        if not self._is_stopped:
            self._schedule_ui_queue_poll()

    def post_to_ui(self, func: Callable, *args):
        """Worker iş parçacıklarından gelen UI görevlerini thread-safe kuyruğa ekler."""
        if not self._is_stopped:
            self._ui_queue.put((func, args))

    def _safe_after(self, ms: int, func: Callable, *args):
        """
        Thread-safe UI zamanlayıcı/çağırıcı.
        Arka plan iş parçacığından çağrıldığında asla doğrudan func(*args) veya Tk işlemi
        çalıştırmaz; görevi iş parçacığı güvenli _ui_queue kuyruğuna aktarır.
        Tk ana iş parçacığında ise iptal edilebilir after() zamanlayıcısı ile planlar.
        """
        if self._is_stopped:
            return None

        if threading.current_thread() is not threading.main_thread():
            # Arka plan iş parçacığı: Yalnızca kuyruğa ekle, Tk metodlarına ASLA dokunma
            self.post_to_ui(func, *args)
            return None

        # Tk ana iş parçacığı
        try:
            if hasattr(self, "root") and self.root and self.root.winfo_exists():
                after_id = None
                def _wrapper():
                    if hasattr(self, "_after_ids") and after_id in self._after_ids:
                        self._after_ids.discard(after_id)
                    if not self._is_stopped:
                        func(*args)

                after_id = self.root.after(ms, _wrapper)
                if hasattr(self, "_after_ids"):
                    self._after_ids.add(after_id)
                return after_id
            elif not self._is_stopped:
                func(*args)
        except Exception:
            if not self._is_stopped:
                try:
                    func(*args)
                except Exception:
                    pass
        return None

    def _lookup_from_clipboard(self):
        """
        Alt+C basıldığında ekrandaki seçili metni kopyalar veya panodaki güncel metni çevirir.
        Kullanıcı bir kelimeyi fareyle seçip Alt+C'ye bastığında otomatik kopyalar ve çevirir.
        Eğer hem seçim hem de pano boşsa kullanıcıya bilgilendirici bir uyarı kartı gösterir.
        """
        if self._is_stopped:
            return None

        def _worker():
            if self._is_stopped:
                return
            # 1. Önce aktif pencerede kullanıcının seçili tuttuğu metni kopyalamayı dene
            txt = copy_selected_text_windows(timeout_ms=100)
            if not txt or not txt.strip():
                # Kopyalama yeni bir metin getirmediyse mevcut panoya bak
                txt = get_clipboard_text()

            if self._is_stopped:
                return

            if txt and txt.strip():
                clean_text = txt.strip()
                if self.clipboard_watcher:
                    self.clipboard_watcher._last_text = clean_text

                is_sec_off = bool(self.config.get("disable_security_filter", False) or self.config.get("hide_security_warnings", False))
                if not is_sec_off:
                    # Hassas veri kontrolü (parola, API anahtarı, token, IBAN, kart vb.)
                    is_sens, reason = check_sensitive_clipboard(clean_text)
                    if is_sens:
                        sensitive_msg = {
                            "error": f"🛡️ Güvenlik Koruması:\n"
                                     f"Kopyalanan metin hassas veri ({reason}) kalıbı "
                                     f"içerdiği için otomatik çeviriye gönderilmedi."
                        }
                        self._safe_after(0, lambda: self._show_hud(sensitive_msg))
                        return

                self._safe_after(0, lambda: self.lookup_text(clean_text))
            else:
                # Pano ve seçim boşsa kullanıcıya net görsel geri bildirim ver
                empty_msg = {
                    "error": "Panoda veya ekranda çevrilecek bir Almanca metin bulunamadı.\n\n"
                             "💡 İpucu: Çevirmek istediğiniz kelimeyi fareyle seçip Alt+C'ye basabilir "
                             "veya doğrudan Ctrl+C ile kopyalayabilirsiniz."
                }
                self._safe_after(0, lambda: self._show_hud(empty_msg))

        return self._worker_pool.submit(_worker)

    def _toggle_bar_visibility(self):
        """Alt+H veya gizle butonuna basıldığında çubuğu gizler / gösterir."""
        if self._is_bar_visible:
            self.root.withdraw()
            self._is_bar_visible = False
        else:
            self.root.deiconify()
            self.root.attributes("-topmost", self.config.get("always_on_top", True))
            self.root.lift()
            self._is_bar_visible = True

    def _on_close_clicked(self):
        """✕ butonuna basınca tamamen kapanmaz — tepsiye küçülür, kısayollar aktif kalır."""
        self.root.withdraw()
        self._is_bar_visible = False

    def quit_completely(self):
        """Yalnızca tepsi menüsünden 'Çıkış' seçilince gerçek kapatma yapılır."""
        self.stop()
        try:
            self.root.destroy()
        except Exception:
            pass

    def stop(self):
        """Temiz kapatma: zamanlayıcıları iptal eder, kuyruğu boşaltır ve hook'ları durdurur."""
        self._is_stopped = True

        # Worker havuzunu kapat ve yeni iş kabulünü derhal durdur
        if hasattr(self, "_worker_pool") and self._worker_pool:
            try:
                self._worker_pool.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass

        # Poller zamanlayıcısını iptal et
        if self._ui_poll_id:
            try:
                self.root.after_cancel(self._ui_poll_id)
            except Exception:
                pass
            if hasattr(self, "_after_ids"):
                self._after_ids.discard(self._ui_poll_id)
            self._ui_poll_id = None

        # Kuyruğu boşalt ve geç kalan iş parçacığı sonuçlarının UI'ya dokunmasını engelle
        while not self._ui_queue.empty():
            try:
                self._ui_queue.get_nowait()
            except queue.Empty:
                break

        # Onboarding zamanlayıcısını iptal et
        if hasattr(self, "_onboarding_after_id") and self._onboarding_after_id:
            try:
                self.root.after_cancel(self._onboarding_after_id)
            except Exception:
                pass
            if hasattr(self, "_after_ids"):
                self._after_ids.discard(self._onboarding_after_id)
            self._onboarding_after_id = None

        # Kalan tüm planlanmış UI zamanlayıcılarını iptal et
        if hasattr(self, "_after_ids"):
            for aid in list(self._after_ids):
                try:
                    self.root.after_cancel(aid)
                except Exception:
                    pass
            self._after_ids.clear()

        if getattr(self, "hotkey_mgr", None):
            try:
                self.hotkey_mgr.stop()
            except Exception:
                pass
        if getattr(self, "clipboard_watcher", None):
            try:
                self.clipboard_watcher.stop()
            except Exception:
                pass
        if getattr(self, "hover_tracker", None):
            try:
                self.hover_tracker.stop()
            except Exception:
                pass
        if getattr(self, "hover_tooltip", None):
            try:
                self.hover_tooltip.hide()
            except Exception:
                pass

    def lookup_text(self, text: str):
        """
        Metni çevirir ve HUD kartında gösterir.
        İstek kimliği (Generation ID) mekanizması ile geciken eski sorguların
        daha yeni bir aramanın sonucunun üstüne yazması engellenir.
        Arama nesli kontrolü ve HUD çizimi yarış durumu (race condition) olmadan kilit altında uygulanır.
        """
        if not text or not text.strip():
            return None

        # Hassas veri kontrolü (OCR snip ve doğrudan aramalarda veri sızıntısını engeller)
        is_sec_off = bool(self.config.get("disable_security_filter", False) or self.config.get("hide_security_warnings", False))
        if not is_sec_off:
            is_sens, reason = check_sensitive_clipboard(text)
            if is_sens:
                sensitive_msg = {
                    "error": f"🛡️ Güvenlik Koruması:\n"
                             f"Metin hassas veri ({reason}) kalıbı "
                             f"içerdiği için çeviriye gönderilmedi."
                }
                self._safe_after(0, lambda: self._show_hud(sensitive_msg))
                return None

        with self._lookup_lock:
            if self._is_stopped:
                return None
            self._lookup_generation += 1
            gen_id = self._lookup_generation

        def _worker():
            try:
                cleaned_text = text.strip()
                lookup_target = cleaned_text
                lemma_res = None
                if is_single_word(cleaned_text) and self.config.get("lemma_lookup_enabled", True):
                    lemma_res = resolve_lemma(cleaned_text)
                    if lemma_res and lemma_res.confidence in ("high", "medium") and lemma_res.lemma.lower() != cleaned_text.lower():
                        lookup_target = lemma_res.lemma

                res = self.translator.translate_and_analyze(lookup_target)
                if lookup_target != cleaned_text and (not res or "error" in res):
                    res = self.translator.translate_and_analyze(cleaned_text)
                    lookup_target = cleaned_text

                if res:
                    res = dict(res)
                    if lookup_target != cleaned_text and lemma_res:
                        res["surface_form"] = cleaned_text
                        res["lemma"] = lemma_res.lemma
                        res["lemma_form"] = lemma_res.form_label
                        res["separable_prefix"] = lemma_res.separable_prefix
                        res["lemma_hint"] = format_lemma_hint(lemma_res)
                    elif lemma_res and lemma_res.confidence in ("high", "medium"):
                        hint = format_lemma_hint(lemma_res)
                        if hint:
                            res["surface_form"] = cleaned_text
                            res["lemma"] = lemma_res.lemma
                            res["lemma_form"] = lemma_res.form_label
                            res["separable_prefix"] = lemma_res.separable_prefix
                            res["lemma_hint"] = hint

                def _ui_dispatch():
                    with self._lookup_lock:
                        if self._is_stopped:
                            return
                        if gen_id != self._lookup_generation:
                            # Daha yeni bir arama başlatılmış; eski geciken sonucu yoksay
                            return
                        self._show_hud(res)

                self._safe_after(0, _ui_dispatch)
            except Exception as e:
                print(f"Çeviri hatası: {e}")

        return self._worker_pool.submit(_worker)

    def _show_hud(self, result_data: dict):
        if "error" in result_data:
            err_str = str(result_data.get("error", ""))
            err_lower = err_str.lower()
            if "güvenlik" in err_lower or "hassas veri" in err_lower:
                if self.config.get("disable_security_filter", False) or self.config.get("hide_security_warnings", False):
                    return
        ResultHUD.show_result(
            self.root,
            result_data,
            db=self.db,
            config=self.config,
            on_grammar_request=self._request_grammar
        )

    def _request_grammar(self, sentence: str, focus_word: Optional[str] = None):
        """Kullanıcı '🔍 Dilbilgisi' butonuna bastığında asenkron olarak analizi başlatır."""
        if not sentence or not sentence.strip():
            return
        clean_sentence = sentence.strip()

        with self._lookup_lock:
            if self._is_stopped:
                return
            if not hasattr(self, "_grammar_generation"):
                self._grammar_generation = 0
            self._grammar_generation += 1
            gen_id = self._grammar_generation

        from app.gui.grammar_panel import GrammarPanel
        panel = GrammarPanel.get_or_create(self.root, clean_sentence)
        panel.show_loading()

        def _worker():
            try:
                grammar_data = self.translator.analyze_grammar(clean_sentence, focus_word=focus_word)
                def _ui_dispatch():
                    with self._lookup_lock:
                        if self._is_stopped:
                            return
                        if gen_id != getattr(self, "_grammar_generation", 0):
                            return
                        if panel.is_alive():
                            panel.show_result(grammar_data)
                self.post_to_ui(_ui_dispatch)
            except Exception as e:
                print(f"[Dilbilgisi Analizi Hatası]: {e}")
                def _err_dispatch():
                    if panel.is_alive():
                        panel.show_error(f"Analiz sırasında beklenmeyen bir hata oluştu: {e}")
                self.post_to_ui(_err_dispatch)

        self._worker_pool.submit(_worker)

    def _start_ocr_snip(self):
        self.snipper.start_selection()

    def _toggle_clipboard(self):
        new_state = not self.clipboard_watcher.is_enabled()
        self.clipboard_watcher.set_enabled(new_state)
        self.config["clipboard_auto_lookup"] = new_state
        from app.config import save_config
        save_config(self.config)
        self.btn_clip.configure(
            text="📋 Pano: AÇIK" if new_state else "📋 Pano: KAPALI",
            bg="#059669" if new_state else "#52525b"
        )

    def _toggle_hover(self):
        """Hover modunu açar veya kapatır."""
        new_state = not self.hover_tracker.is_enabled()
        self.hover_tracker.set_enabled(new_state)
        self.config["hover_enabled"] = new_state
        from app.config import save_config
        save_config(self.config)
        self.btn_hover.configure(
            text="👁️ Hover: AÇIK" if new_state else "👁️ Hover: KAPALI",
            bg="#8b5cf6" if new_state else "#52525b"
        )
        if not new_state and hasattr(self, "hover_tooltip"):
            self.hover_tooltip.hide()

    def _open_wordbook(self):
        if getattr(self, "_wordbook_window", None) and hasattr(self._wordbook_window, "window"):
            try:
                if self._wordbook_window.window.winfo_exists():
                    self._wordbook_window.window.deiconify()
                    self._wordbook_window.window.lift()
                    self._wordbook_window.window.focus_force()
                    return
            except Exception:
                pass
        self._wordbook_window = WordbookWindow(self.root, self.db)

    def _open_settings(self):
        if getattr(self, "_settings_window", None) and hasattr(self._settings_window, "window"):
            try:
                if self._settings_window.window.winfo_exists():
                    self._settings_window.window.deiconify()
                    self._settings_window.window.lift()
                    self._settings_window.window.focus_force()
                    return
            except Exception:
                pass
        self._settings_window = SettingsWindow(
            self.root,
            self.config,
            self._apply_settings,
            ocr_engine=self.ocr,
            on_open_wizard=self._open_onboarding_wizard
        )

    def _open_onboarding_wizard(self):
        """İlk çalıştırma veya başlangıç rehberi sihirbazını açar."""
        if hasattr(self, "_onboarding_after_id") and self._onboarding_after_id:
            if hasattr(self, "_after_ids"):
                self._after_ids.discard(self._onboarding_after_id)
            self._onboarding_after_id = None

        if self._is_stopped:
            return

        if getattr(self, "_wizard_window", None) and hasattr(self._wizard_window, "window"):
            try:
                if self._wizard_window.window.winfo_exists():
                    self._wizard_window.window.deiconify()
                    self._wizard_window.window.lift()
                    self._wizard_window.window.focus_force()
                    return
            except Exception:
                pass

        self._wizard_window = OnboardingWizard(
            parent=self.root,
            config=self.config,
            ocr_engine=self.ocr,
            translator=self.translator,
            db=self.db,
            on_complete=self._on_wizard_complete
        )

    def _on_wizard_complete(self):
        """Sihirbaz tamamlandığında ayarları güncelle."""
        self._apply_settings(self.config)

    def _apply_settings(self, new_config: dict):
        self.config = new_config
        self.root.attributes("-topmost", self.config.get("always_on_top", True))
        clip_on = self.config.get("clipboard_auto_lookup", False)
        self.clipboard_watcher.set_enabled(clip_on)
        self.btn_clip.configure(
            text="📋 Pano: AÇIK" if clip_on else "📋 Pano: KAPALI",
            bg="#059669" if clip_on else "#52525b"
        )
        if hasattr(self.db, "set_history_limit") and "history_limit" in new_config:
            self.db.set_history_limit(new_config["history_limit"])

        hover_on = self.config.get("hover_enabled", True)
        self.hover_tracker.update_settings(
            self.config.get("hover_delay_ms", 300),
            self.config.get("hover_trigger_mode", "mouse_side")
        )
        self.hover_tracker.set_enabled(hover_on)
        self.btn_hover.configure(
            text="👁️ Hover: AÇIK" if hover_on else "👁️ Hover: KAPALI",
            bg="#8b5cf6" if hover_on else "#52525b"
        )
        if hasattr(self, "hover_tooltip"):
            self.hover_tooltip.set_auto_hide_seconds(
                self.config.get("hover_auto_hide_seconds", 5)
            )
            if not hover_on:
                self.hover_tooltip.hide()

        # Kısayol buton metnini ve tuş kayıtlarını güncelle
        hotkey_ocr_label = format_hotkey(self.config.get("hotkey_ocr", "tab+space"))
        self.btn_snip.configure(text=f"✂ Kırp ({hotkey_ocr_label})")
        self._register_configured_hotkeys()

        # OCR Motor Tercihlerini Güncelle
        if hasattr(self.ocr, "set_tesseract_cmd") and "tesseract_cmd" in new_config:
            self.ocr.set_tesseract_cmd(new_config["tesseract_cmd"])
        if hasattr(self.ocr, "set_preference") and "ocr_engine_preference" in new_config:
            self.ocr.set_preference(new_config["ocr_engine_preference"])

        if hasattr(self, "snipper") and self.snipper:
            self.snipper.config = new_config
        if hasattr(self, "clipboard_watcher") and self.clipboard_watcher:
            self.clipboard_watcher.config = new_config
        if hasattr(self, "hover_tracker") and self.hover_tracker:
            self.hover_tracker.config = new_config

        if "gemini_api_key" in new_config:
            self.translator.set_gemini_key(new_config["gemini_api_key"])
        self.translator.set_gemini_options(
            new_config.get("use_gemini_direct", False),
            new_config.get("gemini_model", "gemini-3.5-flash-lite")
        )

    def _set_initial_position(self):
        self.root.update_idletasks()
        w = max(self.root.winfo_reqwidth(), 650)
        h = max(self.root.winfo_reqheight(), 38)
        screen_w = self.root.winfo_screenwidth()
        # Ekranın üst orta kısmında konumlandır
        x = (screen_w - w) // 2
        y = 12
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _bind_drag_events(self):
        for widget in [self.drag_grip, self.bar_frame]:
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._do_drag)

    def _start_drag(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _do_drag(self, event):
        x = self.root.winfo_x() + (event.x - self._drag_start_x)
        y = self.root.winfo_y() + (event.y - self._drag_start_y)
        self.root.geometry(f"+{x}+{y}")
