"""
İlk Çalıştırma ve Başlangıç Sihirbazı (First-Run Onboarding Wizard)
Sıfır bir kullanıcının uygulamayı ilk açtığında:
1. Uygulamanın ne yaptığını anlamasını,
2. Kısayol tuşlarını (Tab+Space, Fare Yan Tuşu, Alt+V, Alt+H) öğrenmesini,
3. OCR motorunun (Windows Media OCR / Tesseract) sistemde çalışıp çalışmadığını test etmesini,
4. İsteğe bağlı Gemini AI anahtarı girmesini veya %100 çevrimdışı kullanım seçmesini,
5. Tek tıkla hazır hale gelmesini sağlar.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from typing import Callable, Optional, Dict, Any
from app.config import save_config
from app.hotkey_manager import format_hotkey


class OnboardingWizard:
    def __init__(
        self,
        parent: tk.Tk,
        config: dict,
        ocr_engine,
        translator,
        db=None,
        on_complete: Optional[Callable[[], None]] = None
    ):
        self.parent = parent
        self.config = config
        self.ocr_engine = ocr_engine
        self.translator = translator
        self.db = db
        self.on_complete = on_complete

        self.current_step = 0
        self.total_steps = 4

        self.window = tk.Toplevel(parent)
        self.window.title("Ekran Sözlüğü • Hoş Geldiniz")
        self.window.geometry("620x680")
        self.window.minsize(580, 620)
        self.window.resizable(False, False)
        self.window.configure(bg="#18181b")

        # Pencereyi ekranın ortasında konumlandır
        self._center_window()

        self._init_ui()
        self.window.protocol("WM_DELETE_WINDOW", self._finish_wizard)
        self._show_step(0)

    def _center_window(self):
        self.window.update_idletasks()
        w = 620
        h = 680
        sw = self.window.winfo_screenwidth()
        sh = self.window.winfo_screenheight()
        x = max(20, (sw - w) // 2)
        y = max(20, (sh - h) // 2)
        self.window.geometry(f"{w}x{h}+{x}+{y}")
        self.window.attributes("-topmost", True)
        self.window.lift()

    def _init_ui(self):
        # 1. Üst Başlık ve İlerleme Çubuğu
        self.header_frame = tk.Frame(self.window, bg="#27272a", padx=24, pady=16)
        self.header_frame.pack(fill="x")

        self.lbl_title = tk.Label(
            self.header_frame,
            text="🇩🇪 Ekran Sözlüğü'ne Hoş Geldiniz",
            font=("Segoe UI", 14, "bold"),
            fg="#fafafa",
            bg="#27272a"
        )
        self.lbl_title.pack(anchor="w")

        self.lbl_step_counter = tk.Label(
            self.header_frame,
            text="Adım 1 / 4",
            font=("Segoe UI", 9),
            fg="#a1a1aa",
            bg="#27272a"
        )
        self.lbl_step_counter.pack(anchor="w", pady=(2, 6))

        # İlerleme göstergesi
        self.progress_bar = ttk.Progressbar(self.header_frame, orient="horizontal", mode="determinate")
        self.progress_bar.pack(fill="x")

        # 2. Orta İçerik Alanı
        self.content_frame = tk.Frame(self.window, bg="#18181b", padx=24, pady=16)
        self.content_frame.pack(fill="both", expand=True)

        # 3. Alt Buton Çubuğu (Geri, İleri, Bitir)
        self.nav_frame = tk.Frame(self.window, bg="#27272a", padx=24, pady=14)
        self.nav_frame.pack(fill="x", side="bottom")

        self.btn_back = tk.Button(
            self.nav_frame,
            text="◀ Geri",
            font=("Segoe UI", 9),
            bg="#3f3f46",
            fg="#fafafa",
            activebackground="#52525b",
            activeforeground="#ffffff",
            relief="flat",
            padx=16,
            pady=4,
            cursor="hand2",
            command=self._prev_step
        )
        self.btn_back.pack(side="left")

        self.btn_skip = tk.Button(
            self.nav_frame,
            text="Hepsini Atla & Başla",
            font=("Segoe UI", 8),
            bg="#27272a",
            fg="#71717a",
            activebackground="#3f3f46",
            activeforeground="#fafafa",
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._finish_wizard
        )
        self.btn_skip.pack(side="left", padx=12)

        self.btn_next = tk.Button(
            self.nav_frame,
            text="İleri ▶",
            font=("Segoe UI", 9, "bold"),
            bg="#6366f1",
            fg="#ffffff",
            activebackground="#4f46e5",
            activeforeground="#ffffff",
            relief="flat",
            padx=20,
            pady=4,
            cursor="hand2",
            command=self._next_step
        )
        self.btn_next.pack(side="right")

    def _clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def _show_step(self, step: int):
        self.current_step = step
        self._clear_content()

        self.lbl_step_counter.configure(text=f"Adım {step + 1} / {self.total_steps}")
        self.progress_bar["value"] = ((step + 1) / self.total_steps) * 100

        self.btn_back.configure(state="normal" if step > 0 else "disabled")
        if step == self.total_steps - 1:
            self.btn_next.configure(text="🚀 Ekran Sözlüğü'nü Başlat", bg="#10b981", activebackground="#059669")
        else:
            self.btn_next.configure(text="İleri ▶", bg="#6366f1", activebackground="#4f46e5")

        if step == 0:
            self._render_step_welcome()
        elif step == 1:
            self._render_step_hotkeys()
        elif step == 2:
            self._render_step_ocr_check()
        elif step == 3:
            self._render_step_ai_settings()

    # =========================================================================
    # ADIM 1: HOŞ GELDİNİZ VE ÖZET
    # =========================================================================
    def _render_step_welcome(self):
        tk.Label(
            self.content_frame,
            text="Almanca Öğrenenler İçin Akıllı Ekran Asistanı",
            font=("Segoe UI", 12, "bold"),
            fg="#38bdf8",
            bg="#18181b"
        ).pack(anchor="w", pady=(0, 10))

        desc = (
            "Ekran Sözlüğü, bilgisayarınızda film, dizi veya YouTube videosu izlerken, "
            "PDF veya e-kitap okurken ekrandaki Almanca altyazı ve kelimeleri "
            "kesintisizce anlamanıza yardımcı olmak için tasarlandı.\n"
        )
        tk.Label(
            self.content_frame,
            text=desc,
            font=("Segoe UI", 9),
            fg="#d4d4d8",
            bg="#18181b",
            wraplength=560,
            justify="left"
        ).pack(anchor="w", pady=(0, 12))

        # Öne çıkan özellikler listesi
        features = [
            ("✂️ Anında Ekran Kırpma", "Tab+Space kısayoluyla ekrandaki altyazıyı kutu içine alın, video donmadan çevrilsin."),
            ("👁️ Canlı Fare Üzerine Gelme (Hover)", "Farenizi kelimenin üzerine getirin veya yan tuşa tıklayın, mini çeviri balonu açılsın."),
            ("🎨 Renkli Artikel ve Çoğul Desteği", "der (Mavi), die (Kırmızı), das (Yeşil) ile artikel hafızanızı güçlendirin."),
            ("📚 Kişisel Kelime Defteri & Flashcards", "Beğendiğiniz kelimeleri ⭐ ile deftere ekleyin, Anki'ye aktarın veya kartlarla tekrar edin."),
            ("📴 %100 Çevrimdışı Çalışabilme", "İnternet veya harici API olmasa bile dahili sözlük ve dilbilgisi kuralları hazırdır.")
        ]

        for icon_title, text_detail in features:
            f_item = tk.Frame(self.content_frame, bg="#27272a", padx=12, pady=8)
            f_item.pack(fill="x", pady=4)
            tk.Label(f_item, text=icon_title, font=("Segoe UI", 9, "bold"), fg="#fafafa", bg="#27272a").pack(anchor="w")
            tk.Label(f_item, text=text_detail, font=("Segoe UI", 8), fg="#a1a1aa", bg="#27272a", wraplength=530, justify="left").pack(anchor="w", pady=(2, 0))

    # =========================================================================
    # ADIM 2: KISAYOL TUŞLARI REHBERİ
    # =========================================================================
    def _render_step_hotkeys(self):
        tk.Label(
            self.content_frame,
            text="Sihirli Kısayollar ve Fare Kontrolleri",
            font=("Segoe UI", 12, "bold"),
            fg="#38bdf8",
            bg="#18181b"
        ).pack(anchor="w", pady=(0, 6))

        tk.Label(
            self.content_frame,
            text="Uygulama arka planda simge durumundayken bile bu tuşlar her zaman çalışır:",
            font=("Segoe UI", 9),
            fg="#a1a1aa",
            bg="#18181b"
        ).pack(anchor="w", pady=(0, 10))

        hotkey_ocr = format_hotkey(self.config.get("hotkey_ocr", "tab+space"))
        hotkey_hover = format_hotkey(self.config.get("hotkey_hover", "alt+v"))
        hotkey_overlay = format_hotkey(self.config.get("hotkey_overlay", "alt+h"))
        hotkey_clip = format_hotkey(self.config.get("hotkey_clipboard", "alt+c"))

        cards = [
            (f"✂️ {hotkey_ocr}", "Anında Ekran Kırpıcı (OCR)", "Ekranda altyazı veya metin gördüğünüzde basın. Karartmalı ekranda kelimeyi seçin.", "#0284c7"),
            (f"👁️ Fare Yan Tuşu veya {hotkey_hover}", "Canlı Hover Çevirisi", "Farenizi kelimenin üzerine götürüp yan tuşa (Mouse 4/5) tıklayın. Anında balon açılır.", "#8b5cf6"),
            (f"📋 {hotkey_clip}", "Panodaki Metni Çevir", "Herhangi bir uygulamada metin kopyaladığınızda bu kısayolla hemen çevirin.", "#10b981"),
            (f"📌 {hotkey_overlay}", "Ana Çubuğu Gizle / Göster", "Üstteki mini çubuğu ekrandan geçici olarak gizlemek veya geri getirmek için basın.", "#f59e0b")
        ]

        for key_label, title, desc, color in cards:
            c_box = tk.Frame(self.content_frame, bg="#27272a", padx=12, pady=8, highlightthickness=1, highlightbackground=color)
            c_box.pack(fill="x", pady=4)

            top = tk.Frame(c_box, bg="#27272a")
            top.pack(fill="x")
            tk.Label(top, text=key_label, font=("Segoe UI", 10, "bold"), fg=color, bg="#27272a").pack(side="left")
            tk.Label(top, text=f"— {title}", font=("Segoe UI", 9, "bold"), fg="#fafafa", bg="#27272a").pack(side="left", padx=6)

            tk.Label(c_box, text=desc, font=("Segoe UI", 8), fg="#a1a1aa", bg="#27272a", wraplength=520, justify="left").pack(anchor="w", pady=(3, 0))

        tk.Label(
            self.content_frame,
            text="💡 İpucu: Kısayol tuşlarını dilediğiniz zaman ⚙️ Ayarlar menüsünden değiştirebilirsiniz.",
            font=("Segoe UI", 8, "italic"),
            fg="#71717a",
            bg="#18181b"
        ).pack(anchor="w", pady=(8, 0))

    # =========================================================================
    # ADIM 3: SİSTEM & OCR UYUMLULUK KONTROLÜ
    # =========================================================================
    def _render_step_ocr_check(self):
        tk.Label(
            self.content_frame,
            text="Optik Karakter Tanıma (OCR) Kontrolü",
            font=("Segoe UI", 12, "bold"),
            fg="#38bdf8",
            bg="#18181b"
        ).pack(anchor="w", pady=(0, 6))

        tk.Label(
            self.content_frame,
            text="Ekran Sözlüğü, harici bir kurulum gerektirmeden Windows 10/11'in yerleşik Media OCR motorunu kullanır. Dilerseniz Tesseract OCR desteği de mevcuttur.",
            font=("Segoe UI", 9),
            fg="#d4d4d8",
            bg="#18181b",
            wraplength=560,
            justify="left"
        ).pack(anchor="w", pady=(0, 10))

        # Durum Kartı
        status = self.ocr_engine.get_status()
        self.box_status = tk.Frame(self.content_frame, bg="#27272a", padx=16, pady=12)
        self.box_status.pack(fill="x", pady=6)

        # Windows OCR
        win_ok = status.get("windows_media_ocr", False)
        win_txt = "✅ Aktif & Hazır (Windows 10/11 Yerleşik)" if win_ok else "⚠️ Aktif Değil (Almanca dil paketi kontrol edilmeli)"
        win_color = "#10b981" if win_ok else "#f59e0b"

        row1 = tk.Frame(self.box_status, bg="#27272a")
        row1.pack(fill="x", pady=3)
        tk.Label(row1, text="Windows Media OCR:", font=("Segoe UI", 9, "bold"), fg="#fafafa", bg="#27272a", width=20, anchor="w").pack(side="left")
        tk.Label(row1, text=win_txt, font=("Segoe UI", 9), fg=win_color, bg="#27272a").pack(side="left")

        # Tesseract
        tess_ok = status.get("tesseract_ocr", False)
        tess_txt = f"✅ Kurulu ({status.get('tesseract_path', '')})" if tess_ok else "⚪ Bulunamadı (İsteğe bağlı alternatif)"
        tess_color = "#10b981" if tess_ok else "#71717a"

        row2 = tk.Frame(self.box_status, bg="#27272a")
        row2.pack(fill="x", pady=3)
        tk.Label(row2, text="Tesseract OCR:", font=("Segoe UI", 9, "bold"), fg="#fafafa", bg="#27272a", width=20, anchor="w").pack(side="left")
        tk.Label(row2, text=tess_txt, font=("Segoe UI", 9), fg=tess_color, bg="#27272a").pack(side="left")

        # Aktif Motor
        row3 = tk.Frame(self.box_status, bg="#27272a")
        row3.pack(fill="x", pady=3)
        tk.Label(row3, text="Etkin Motor:", font=("Segoe UI", 9, "bold"), fg="#fafafa", bg="#27272a", width=20, anchor="w").pack(side="left")
        tk.Label(row3, text=status.get("active_backend", "Bilinmiyor"), font=("Segoe UI", 9), fg="#38bdf8", bg="#27272a").pack(side="left")

        # Test Butonu ve Sonuç Alanı
        f_test = tk.Frame(self.content_frame, bg="#18181b")
        f_test.pack(fill="x", pady=(12, 6))

        self.btn_run_test = tk.Button(
            f_test,
            text="🧪 OCR Testi Yap (Örnek Metin Oku)",
            font=("Segoe UI", 9, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            activebackground="#0369a1",
            activeforeground="#ffffff",
            relief="flat",
            padx=14,
            pady=5,
            cursor="hand2",
            command=self._run_ocr_test
        )
        self.btn_run_test.pack(side="left")

        self.lbl_test_result = tk.Label(
            self.content_frame,
            text="Test başlatmak için yukarıdaki butona tıklayın.",
            font=("Segoe UI", 8, "italic"),
            fg="#a1a1aa",
            bg="#18181b",
            wraplength=540,
            justify="left"
        )
        self.lbl_test_result.pack(anchor="w", pady=(4, 0))

    def _run_ocr_test(self):
        self.btn_run_test.configure(state="disabled")
        self.lbl_test_result.configure(text="⏳ Sentetik test resmi taranıyor...", fg="#facc15")

        def _worker():
            success, msg = self.ocr_engine.test_ocr("Guten Tag")

            def _update():
                try:
                    if self.window.winfo_exists():
                        self.btn_run_test.configure(state="normal")
                        color = "#10b981" if success else "#ef4444"
                        self.lbl_test_result.configure(text=msg, fg=color)
                except Exception:
                    pass

            try:
                if self.window.winfo_exists():
                    self.window.after(0, _update)
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    # =========================================================================
    # ADIM 4: GEMINI AI & ÇEVRİMDIŞI KULLANIM TERCİHİ
    # =========================================================================
    def _render_step_ai_settings(self):
        tk.Label(
            self.content_frame,
            text="Çeviri ve Yapay Zeka Tercihleri",
            font=("Segoe UI", 12, "bold"),
            fg="#38bdf8",
            bg="#18181b"
        ).pack(anchor="w", pady=(0, 6))

        info = (
            "Ekran Sözlüğü, Google Gemini AI (Flash) entegrasyonu ile derin dilbilgisi "
            "açıklamaları ve pratik artikel ipuçları sunabilir. "
            "Bu özellik TAMAMEN OPSİYONELDİR. Anahtarınız olmasa bile uygulama yerel çevrimdışı "
            "veritabanı ve hızlı web çevirisiyle eksiksiz çalışır.\n"
        )
        tk.Label(
            self.content_frame,
            text=info,
            font=("Segoe UI", 9),
            fg="#d4d4d8",
            bg="#18181b",
            wraplength=560,
            justify="left"
        ).pack(anchor="w", pady=(0, 10))

        # Seçenekler Kutusu
        box_ai = tk.LabelFrame(
            self.content_frame,
            text=" 🔑 Google Gemini API Anahtarı (İsteğe Bağlı) ",
            font=("Segoe UI", 9, "bold"),
            fg="#60a5fa",
            bg="#18181b",
            padx=14,
            pady=10
        )
        box_ai.pack(fill="x", pady=4)

        f_input = tk.Frame(box_ai, bg="#18181b")
        f_input.pack(fill="x", pady=4)

        self.entry_key = tk.Entry(
            f_input,
            font=("Segoe UI", 9),
            bg="#27272a",
            fg="#fafafa",
            insertbackground="white"
        )
        self.entry_key.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry_key.insert(0, self.config.get("gemini_api_key", ""))

        self.btn_validate_key = tk.Button(
            f_input,
            text="🔍 Doğrula",
            font=("Segoe UI", 8, "bold"),
            bg="#2563eb",
            fg="#ffffff",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            relief="flat",
            padx=10,
            cursor="hand2",
            command=self._validate_gemini_key
        )
        self.btn_validate_key.pack(side="left")

        self.lbl_key_status = tk.Label(
            box_ai,
            text="💡 Ücretsiz API anahtarınızı aistudio.google.com adresinden alabilirsiniz. Boş bırakırsanız temel sözlük kullanılır.",
            font=("Segoe UI", 8, "italic"),
            fg="#9ca3af",
            bg="#18181b",
            wraplength=510,
            justify="left"
        )
        self.lbl_key_status.pack(anchor="w", pady=(4, 0))

        # Çevrimdışı Mod Hatırlatması
        f_offline_badge = tk.Frame(self.content_frame, bg="#27272a", padx=14, pady=10)
        f_offline_badge.pack(fill="x", pady=(12, 0))

        tk.Label(
            f_offline_badge,
            text="📴 %100 Çevrimdışı Mod Hazır!",
            font=("Segoe UI", 9, "bold"),
            fg="#10b981",
            bg="#27272a"
        ).pack(anchor="w")

        tk.Label(
            f_offline_badge,
            text="Hiçbir ayar yapmadan devam edebilirsiniz. Temel sözlük, artikel renklendirmesi ve kelime defteri hemen kullanılabilir.",
            font=("Segoe UI", 8),
            fg="#d4d4d8",
            bg="#27272a",
            wraplength=520,
            justify="left"
        ).pack(anchor="w", pady=(2, 0))

    def _validate_gemini_key(self):
        key = self.entry_key.get().strip()
        if not key:
            self.lbl_key_status.configure(
                text="⚠️ Lütfen bir API anahtarı girin veya çevrimdışı mod için bu adımı atlayın.",
                fg="#f59e0b"
            )
            return

        self.btn_validate_key.configure(state="disabled")
        self.lbl_key_status.configure(text="⏳ Google sunucularına bağlanılıyor...", fg="#facc15")

        def _worker():
            from app.gemini_service import GeminiService
            gs = GeminiService(key)
            ok, msg = gs.test_connection()

            def _update():
                try:
                    if self.window.winfo_exists():
                        self.btn_validate_key.configure(state="normal")
                        color = "#10b981" if ok else "#ef4444"
                        self.lbl_key_status.configure(text=msg, fg=color)
                        if ok:
                            self.config["gemini_api_key"] = key
                            self.translator.set_gemini_key(key)
                except Exception:
                    pass

            try:
                if self.window.winfo_exists():
                    self.window.after(0, _update)
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    # =========================================================================
    # NAVİGASYON VE BİTİRME
    # =========================================================================
    def _prev_step(self):
        if self.current_step > 0:
            self._show_step(self.current_step - 1)

    def _next_step(self):
        if self.current_step < self.total_steps - 1:
            self._show_step(self.current_step + 1)
        else:
            self._finish_wizard()

    def _finish_wizard(self):
        # 1. API anahtarını kaydet (eğer girilmişse)
        if hasattr(self, "entry_key"):
            key = self.entry_key.get().strip()
            self.config["gemini_api_key"] = key
            if self.translator:
                self.translator.set_gemini_key(key)

        # 2. İlk kurulum tamamlandı olarak işaretle
        self.config["first_run_completed"] = True
        save_config(self.config)

        # 3. Veritabanına başlangıç örnek kelimelerini yükle (boşsa)
        if self.db:
            try:
                self.db.seed_starter_words()
            except Exception as e:
                print(f"Başlangıç kelimeleri yükleme uyarısı: {e}")

        # 4. Pencereyi kapat
        try:
            self.window.destroy()
        except Exception:
            pass

        # 5. Callback çalıştır
        if self.on_complete:
            try:
                self.on_complete()
            except Exception as e:
                print(f"Sihirbaz tamamlama callback hatası: {e}")
