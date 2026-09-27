"""
Ayarlar Penceresi Modülü (Settings Dialog)
Kullanıcının pano dinleme, kart süresi, kısayol tuşları ve API ayarlarını düzenlemesini sağlar.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable
import threading
from app.config import save_config
from app.hotkey_manager import validate_hotkey_string, format_hotkey
from app.startup_manager import is_startup_enabled, enable_startup, disable_startup


class SettingsWindow:
    def __init__(self, parent: tk.Tk, config: dict, on_settings_changed: Callable[[dict], None]):
        self.config = config
        self.on_settings_changed = on_settings_changed

        self.window = tk.Toplevel(parent)
        self.window.title("Ayarlar • Ekran Sözlüğü")
        self.window.geometry("550x810")
        self.window.resizable(False, False)
        self.window.configure(bg="#18181b")

        self._init_ui()

    def _init_ui(self):
        main_frame = tk.Frame(self.window, bg="#18181b", padx=20, pady=16)
        main_frame.pack(fill="both", expand=True)

        tk.Label(
            main_frame,
            text="⚙️ Uygulama Ayarları",
            font=("Segoe UI", 13, "bold"),
            fg="#fafafa",
            bg="#18181b"
        ).pack(anchor="w", pady=(0, 10))

        # 1. Pano Dinleme
        self.var_clipboard = tk.BooleanVar(value=self.config.get("clipboard_auto_lookup", True))
        cb_clip = tk.Checkbutton(
            main_frame,
            text="Ctrl+C ile panodaki Almanca metinleri anında çevir",
            variable=self.var_clipboard,
            font=("Segoe UI", 9),
            fg="#fafafa",
            bg="#18181b",
            selectcolor="#27272a",
            activebackground="#18181b",
            activeforeground="#fafafa"
        )
        cb_clip.pack(anchor="w", pady=2)

        # 1b. Windows ile Otomatik Başlat
        self.var_startup = tk.BooleanVar(value=is_startup_enabled())
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
        self.var_topmost = tk.BooleanVar(value=self.config.get("always_on_top", True))
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

        # 3. Otomatik Kapanma Süresi
        duration_frame = tk.Frame(main_frame, bg="#18181b", pady=4)
        duration_frame.pack(fill="x")
        tk.Label(
            duration_frame,
            text="Kart Otomatik Kapanma Süresi (sn):",
            font=("Segoe UI", 9),
            fg="#d4d4d8",
            bg="#18181b"
        ).pack(side="left")

        self.var_duration = tk.IntVar(value=self.config.get("auto_hide_seconds", 12))
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
        tk.Label(duration_frame, text="(0 = Elle kapatana kadar açık kalır)", font=("Segoe UI", 8), fg="#71717a", bg="#18181b").pack(side="left")

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
        hover_section.pack(fill="x", pady=(6, 6))

        self.var_hover_enabled = tk.BooleanVar(value=self.config.get("hover_enabled", True))
        cb_hover = tk.Checkbutton(
            hover_section,
            text="Canlı Hover Modu (Farenin altındaki kelimeyi otomatik oku)",
            variable=self.var_hover_enabled,
            font=("Segoe UI", 9, "bold"),
            fg="#c084fc",
            bg="#18181b",
            selectcolor="#27272a",
            activebackground="#18181b",
            activeforeground="#fafafa"
        )
        cb_hover.pack(anchor="w", pady=2)

        f_hover_mode = tk.Frame(hover_section, bg="#18181b")
        f_hover_mode.pack(fill="x", pady=2)
        tk.Label(f_hover_mode, text="Tetikleme Kuralı:", font=("Segoe UI", 8, "bold"), fg="#d4d4d8", bg="#18181b", width=16, anchor="w").pack(side="left")

        self.var_hover_trigger = tk.StringVar(value=self.config.get("hover_trigger_mode", "mouse_side"))
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
        f_hover_delay.pack(fill="x", pady=2)
        tk.Label(f_hover_delay, text="Duraklama Süresi:", font=("Segoe UI", 8, "bold"), fg="#d4d4d8", bg="#18181b", width=16, anchor="w").pack(side="left")
        self.var_hover_delay = tk.IntVar(value=self.config.get("hover_delay_ms", 300))
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
        hotkey_section.pack(fill="x", pady=(4, 6))

        # 5a. OCR Kısayolu
        f_ocr = tk.Frame(hotkey_section, bg="#18181b")
        f_ocr.pack(fill="x", pady=1)
        tk.Label(f_ocr, text="Ekran Kırp / OCR:", font=("Segoe UI", 8), fg="#d4d4d8", bg="#18181b", width=18, anchor="w").pack(side="left")
        self.entry_hotkey_ocr = tk.Entry(f_ocr, font=("Segoe UI", 8, "bold"), bg="#27272a", fg="#38bdf8", insertbackground="white", width=14)
        self.entry_hotkey_ocr.pack(side="left", padx=4)
        self.entry_hotkey_ocr.insert(0, self.config.get("hotkey_ocr", "tab+space"))
        tk.Label(f_ocr, text="(Tavsiye: tab+space)", font=("Segoe UI", 7), fg="#71717a", bg="#18181b").pack(side="left", padx=4)

        # Hızlı seçim butonları (Presets)
        f_presets = tk.Frame(hotkey_section, bg="#18181b")
        f_presets.pack(fill="x", pady=(1, 4))
        tk.Label(f_presets, text="Hızlı Seçim:", font=("Segoe UI", 7), fg="#71717a", bg="#18181b", width=18, anchor="w").pack(side="left")
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
        tk.Label(f_hov_hot, text="Hover Modu Aç/Kapa:", font=("Segoe UI", 8), fg="#d4d4d8", bg="#18181b", width=18, anchor="w").pack(side="left")
        self.entry_hotkey_hover = tk.Entry(f_hov_hot, font=("Segoe UI", 8), bg="#27272a", fg="#fafafa", insertbackground="white", width=14)
        self.entry_hotkey_hover.pack(side="left", padx=4)
        self.entry_hotkey_hover.insert(0, self.config.get("hotkey_hover", "alt+v"))
        tk.Label(f_hov_hot, text="(Örn: alt+v)", font=("Segoe UI", 7), fg="#71717a", bg="#18181b").pack(side="left", padx=4)

        # 5c. Çubuğu Gizle / Göster
        f_overlay = tk.Frame(hotkey_section, bg="#18181b")
        f_overlay.pack(fill="x", pady=1)
        tk.Label(f_overlay, text="Çubuğu Gizle/Göster:", font=("Segoe UI", 8), fg="#d4d4d8", bg="#18181b", width=18, anchor="w").pack(side="left")
        self.entry_hotkey_overlay = tk.Entry(f_overlay, font=("Segoe UI", 8), bg="#27272a", fg="#fafafa", insertbackground="white", width=14)
        self.entry_hotkey_overlay.pack(side="left", padx=4)
        self.entry_hotkey_overlay.insert(0, self.config.get("hotkey_overlay", "alt+h"))
        tk.Label(f_overlay, text="(Örn: alt+h, f2)", font=("Segoe UI", 7), fg="#71717a", bg="#18181b").pack(side="left", padx=4)

        # 5d. Pano Metnini Çevir
        f_clip = tk.Frame(hotkey_section, bg="#18181b")
        f_clip.pack(fill="x", pady=1)
        tk.Label(f_clip, text="Panoyu Çevir:", font=("Segoe UI", 8), fg="#d4d4d8", bg="#18181b", width=18, anchor="w").pack(side="left")
        self.entry_hotkey_clip = tk.Entry(f_clip, font=("Segoe UI", 8), bg="#27272a", fg="#fafafa", insertbackground="white", width=14)
        self.entry_hotkey_clip.pack(side="left", padx=4)
        self.entry_hotkey_clip.insert(0, self.config.get("hotkey_clipboard", "alt+c"))
        tk.Label(f_clip, text="(Örn: alt+c)", font=("Segoe UI", 7), fg="#71717a", bg="#18181b").pack(side="left", padx=4)

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
        self.btn_test_api.pack(side="left")

        # Durum İbaresi (Status Label)
        init_status = "🔑 Kayıtlı anahtar mevcut. Test etmek için 'Test Et'e basın." if saved_key else "⚪ API anahtarı girilmedi (Temel çeviri motoru aktif)"
        init_color = "#38bdf8" if saved_key else "#71717a"
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
        self.var_use_gemini_direct = tk.BooleanVar(value=self.config.get("use_gemini_direct", False))
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

        self.var_gemini_model = tk.StringVar(value=self.config.get("gemini_model", "gemini-1.5-flash"))
        model_choices = [
            "gemini-1.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash-8b"
        ]
        self.cb_model_choice = ttk.Combobox(
            f_model,
            textvariable=self.var_gemini_model,
            values=model_choices,
            state="readonly",
            width=20,
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
            text="💡 İpucu: 'gemini-1.5-flash' modeli Google AI Studio ücretsiz planında (günde 1500 istek hakkı) neredeyse sıfır harcama ile en doğru artikel, çoğul ve dilbilgisi sonuçlarını üretir.",
            font=("Segoe UI", 7, "italic"),
            fg="#9ca3af",
            bg="#18181b",
            wraplength=480,
            justify="left"
        ).pack(fill="x", pady=(3, 2))

        # Kaydet Butonu
        btn_save = tk.Button(
            main_frame,
            text="💾 Ayarları Kaydet",
            font=("Segoe UI", 10, "bold"),
            bg="#6366f1",
            fg="#ffffff",
            relief="flat",
            padx=14,
            pady=5,
            cursor="hand2",
            command=self._save
        )
        btn_save.pack(side="bottom", fill="x", pady=(8, 0))

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

    def _test_gemini_api(self):
        """Gemini API anahtarını asenkron olarak test eder ve sonucu kullanıcıya bildirir."""
        key = self.entry_api.get().strip()
        if not key:
            self.lbl_api_status.configure(
                text="⚠️ Lütfen önce bir Gemini API anahtarı girin.",
                fg="#f59e0b"
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
                    if self.window.winfo_exists():
                        self.btn_test_api.configure(state="normal")
                        color = "#10b981" if success else "#ef4444"
                        self.lbl_api_status.configure(text=message, fg=color)
                except Exception:
                    pass

            try:
                if self.window.winfo_exists():
                    self.window.after(0, _update_ui)
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _save(self):
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
        for name, key_str in fields:
            if not key_str:
                messagebox.showerror("Hata", f"'{name}' kısayolu boş bırakılamaz.", parent=self.window)
                return
            valid, err = validate_hotkey_string(key_str)
            if not valid:
                messagebox.showerror(
                    "Geçersiz Kısayol",
                    f"'{name}' için geçersiz kısayol tuşu!\n{err}\n\nÖrnek tuşlar: tab, space, alt, ctrl, shift, f1-f12, a-z, 0-9",
                    parent=self.window
                )
                return

        self.config["clipboard_auto_lookup"] = self.var_clipboard.get()
        self.config.pop("sound_enabled", None)
        self.config["always_on_top"] = self.var_topmost.get()
        self.config["auto_hide_seconds"] = self.var_duration.get()
        self.config["gemini_api_key"] = self.entry_api.get().strip()
        self.config["use_gemini_direct"] = self.var_use_gemini_direct.get()
        self.config["gemini_model"] = self.var_gemini_model.get().strip() or "gemini-1.5-flash"

        # Hover Ayarları
        self.config["hover_enabled"] = self.var_hover_enabled.get()
        self.config["hover_trigger_mode"] = self.var_hover_trigger.get()
        self.config["hover_delay_ms"] = self.var_hover_delay.get()

        # Kısayollar
        self.config["hotkey_ocr"] = hotkey_ocr
        self.config["hotkey_hover"] = hotkey_hover
        self.config["hotkey_overlay"] = hotkey_overlay
        self.config["hotkey_clipboard"] = hotkey_clip

        # Otomatik başlatma kayıt defteri güncelleme
        want_startup = self.var_startup.get()
        if want_startup:
            enable_startup()
        else:
            disable_startup()

        save_config(self.config)
        self.on_settings_changed(self.config)
        messagebox.showinfo("Başarılı", "Ayarlar başarıyla kaydedildi.", parent=self.window)
        self.window.destroy()

