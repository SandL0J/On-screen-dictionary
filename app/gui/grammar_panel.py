"""
Cümle Dilbilgisi Çözümleme Paneli (Grammar Analysis Panel)
Gemini AI veya Kural Tabanlı Cümle Dilbilgisi Analizini (Haller, Fiil Sırası, Yan Cümleler)
Kullanıcı dostu, renk kodlu ve modern koyu temalı bir arayüzde gösterir.
"""

import tkinter as tk
from typing import Optional, Dict, Any, Callable


class GrammarPanel:
    """Cümle dilbilgisi çözümleme sonuçlarını gösteren modern Toplevel pencere."""

    _instance: Optional["GrammarPanel"] = None

    CASE_COLORS = {
        "Nominativ": "#9ca3af",  # Gri
        "Akkusativ": "#ef4444",  # Kırmızı
        "Dativ": "#3b82f6",      # Mavi
        "Genitiv": "#10b981",    # Yeşil
    }

    @classmethod
    def get_or_create(cls, root: tk.Tk, sentence: str, on_close: Optional[Callable] = None) -> "GrammarPanel":
        if cls._instance and cls._instance.is_alive():
            cls._instance.sentence = sentence
            cls._instance.on_close = on_close
            cls._instance.bring_to_front()
            return cls._instance
        cls._instance = GrammarPanel(root, sentence, on_close=on_close)
        return cls._instance

    def __init__(self, root: tk.Tk, sentence: str, on_close: Optional[Callable] = None):
        GrammarPanel._instance = self
        self.root = root
        self.sentence = sentence
        self.on_close = on_close

        self.window = tk.Toplevel(root)
        self.window.title("Ekran Sözlüğü • Dilbilgisi Çözümlemesi")
        self.window.geometry("520x620")
        self.window.minsize(440, 480)
        self.window.configure(bg="#18181b")

        # Her zaman üstte ve modern görünüm
        self.window.attributes("-topmost", True)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind("<Escape>", lambda e: self.close())

        self._init_ui()
        self._position_window()

    def is_alive(self) -> bool:
        try:
            return bool(self.window and self.window.winfo_exists())
        except Exception:
            return False

    def bring_to_front(self):
        try:
            if self.is_alive():
                self.window.deiconify()
                self.window.attributes("-topmost", True)
                self.window.lift()
        except Exception:
            pass

    def close(self):
        try:
            if GrammarPanel._instance is self:
                GrammarPanel._instance = None
            if self.is_alive():
                self.window.destroy()
        except Exception:
            pass
        if self.on_close:
            try:
                self.on_close()
            except Exception:
                pass

    def _init_ui(self):
        # 1. Başlık Çubuğu
        header_frame = tk.Frame(self.window, bg="#27272a", padx=16, pady=12)
        header_frame.pack(fill="x", side="top")

        title_lbl = tk.Label(
            header_frame,
            text="🔍 CÜMLE DİLBİLGİSİ ÇÖZÜMLEMESİ",
            font=("Segoe UI", 11, "bold"),
            fg="#fafafa",
            bg="#27272a"
        )
        title_lbl.pack(side="left")

        close_btn = tk.Label(
            header_frame,
            text="✕",
            font=("Segoe UI", 11, "bold"),
            fg="#ef4444",
            bg="#27272a",
            cursor="hand2"
        )
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda e: self.close())

        # 2. İncelenen Cümle Kutusu
        sub_header = tk.Frame(self.window, bg="#18181b", padx=16, pady=10)
        sub_header.pack(fill="x")

        self.lbl_sentence = tk.Label(
            sub_header,
            text=f'"{self.sentence}"',
            font=("Segoe UI", 10, "italic bold"),
            fg="#e0e7ff",
            bg="#18181b",
            wraplength=480,
            justify="left",
            anchor="w"
        )
        self.lbl_sentence.pack(fill="x")

        tk.Frame(self.window, height=1, bg="#27272a").pack(fill="x")

        # 3. Kaydırılabilir İçerik Alanı (Canvas + Scrollbar)
        container = tk.Frame(self.window, bg="#18181b")
        container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(container, bg="#18181b", highlightthickness=0)
        self.scrollbar = tk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.scroll_content = tk.Frame(self.canvas, bg="#18181b", padx=16, pady=12)

        self.scroll_content.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scroll_content, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width)
        )
        # Mousewheel desteği
        self.window.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        try:
            if self.is_alive() and self.canvas.winfo_exists():
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    def _position_window(self):
        try:
            self.window.update_idletasks()
            w = 520
            h = 620
            sw = self.window.winfo_screenwidth()
            sh = self.window.winfo_screenheight()
            x = (sw - w) // 2
            y = (sh - h) // 2
            self.window.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def show_loading(self, message: str = "🔍 Gemini AI cümle dilbilgisini çözümlüyor..."):
        """Yükleniyor göstergesi."""
        if not self.is_alive():
            return
        for widget in self.scroll_content.winfo_children():
            widget.destroy()

        loading_frame = tk.Frame(self.scroll_content, bg="#18181b", pady=40)
        loading_frame.pack(fill="both", expand=True)

        tk.Label(
            loading_frame,
            text="⏳",
            font=("Segoe UI", 28),
            fg="#818cf8",
            bg="#18181b"
        ).pack(pady=(0, 10))

        tk.Label(
            loading_frame,
            text=message,
            font=("Segoe UI", 10, "bold"),
            fg="#a1a1aa",
            bg="#18181b"
        ).pack()

    def show_error(self, message: str):
        """Hata mesajı gösterir."""
        if not self.is_alive():
            return
        for widget in self.scroll_content.winfo_children():
            widget.destroy()

        err_frame = tk.Frame(self.scroll_content, bg="#18181b", pady=30)
        err_frame.pack(fill="both", expand=True)

        tk.Label(
            err_frame,
            text="⚠️",
            font=("Segoe UI", 26),
            fg="#f59e0b",
            bg="#18181b"
        ).pack(pady=(0, 8))

        tk.Label(
            err_frame,
            text=message,
            font=("Segoe UI", 10),
            fg="#fca5a5",
            bg="#18181b",
            wraplength=440,
            justify="center"
        ).pack()

    def show_result(self, data: Dict[str, Any]):
        """Analiz sonucunu modern kartlar halinde çizer."""
        if not self.is_alive():
            return

        for widget in self.scroll_content.winfo_children():
            widget.destroy()

        if not data or "error" in data:
            self.show_error(data.get("error", "Dilbilgisi çözümlemesi alınamadı."))
            return

        source = data.get("source", "")

        # A) Kural Tabanlı Sonuç (Gemini API anahtarı yoksa veya hata oluştuysa)
        if source == "rule_based":
            self._render_rule_based_result(data)
            return

        # B) Gemini AI Detaylı Dilbilgisi Sonucu
        self._render_gemini_result(data)

    def _render_gemini_result(self, data: Dict[str, Any]):
        """Gemini AI detaylı gramer sonucunu kartlar halinde çizer."""
        # 1. Çeviri Bölümü
        tr_text = data.get("translation_tr", "")
        if tr_text:
            sec_trans = self._create_section("🇹🇷 Türkçe Anlamı")
            tk.Label(
                sec_trans,
                text=tr_text,
                font=("Segoe UI", 11, "bold"),
                fg="#38bdf8",
                bg="#27272a",
                wraplength=440,
                justify="left"
            ).pack(anchor="w", padx=10, pady=8)

        # 2. Cümle Yapısı ve Yan Cümleler (Clauses)
        clauses = data.get("clauses", [])
        if clauses:
            sec_clauses = self._create_section("🏗️ Cümle Yapısı ve Bağlaçlar")
            for c in clauses:
                card = tk.Frame(sec_clauses, bg="#1f1f23", padx=8, pady=6)
                card.pack(fill="x", pady=3, padx=6)

                top_bar = tk.Frame(card, bg="#1f1f23")
                top_bar.pack(fill="x")

                c_type = c.get("type", "ana")
                type_colors = {"ana": "#4f46e5", "yan": "#0284c7", "mastar": "#059669"}
                badge_bg = type_colors.get(c_type, "#52525b")

                tk.Label(
                    top_bar,
                    text=f" {c_type.upper()} CÜMLE ",
                    font=("Segoe UI", 8, "bold"),
                    fg="#ffffff",
                    bg=badge_bg,
                    padx=4, pady=1
                ).pack(side="left", padx=(0, 6))

                verb_pos = c.get("verb_position", "")
                if verb_pos:
                    tk.Label(
                        top_bar,
                        text=f"Fiil Konumu: {verb_pos}",
                        font=("Segoe UI", 8, "bold"),
                        fg="#facc15",
                        bg="#1f1f23"
                    ).pack(side="left", padx=(0, 6))

                conj = c.get("conjunction")
                if conj:
                    tk.Label(
                        top_bar,
                        text=f"Bağlaç: '{conj}'",
                        font=("Segoe UI", 8, "italic"),
                        fg="#a1a1aa",
                        bg="#1f1f23"
                    ).pack(side="left")

                # Cümle parçası
                tk.Label(
                    card,
                    text=f'"{c.get("text", "")}"',
                    font=("Segoe UI", 9, "bold"),
                    fg="#fafafa",
                    bg="#1f1f23",
                    wraplength=420,
                    justify="left"
                ).pack(anchor="w", pady=(4, 2))

                # Açıklama
                expl = c.get("explanation_tr", "")
                if expl:
                    tk.Label(
                        card,
                        text=expl,
                        font=("Segoe UI", 8),
                        fg="#a1a1aa",
                        bg="#1f1f23",
                        wraplength=420,
                        justify="left"
                    ).pack(anchor="w")

        # 3. Fiiller ve Çekimleri (Verbs)
        verbs = data.get("verbs", [])
        if verbs:
            sec_verbs = self._create_section("⚡ Fiiller ve Zamanlar")
            for v in verbs:
                v_card = tk.Frame(sec_verbs, bg="#1f1f23", padx=8, pady=6)
                v_card.pack(fill="x", pady=3, padx=6)

                v_top = tk.Frame(v_card, bg="#1f1f23")
                v_top.pack(fill="x")

                surf = v.get("surface", "")
                lemma = v.get("lemma", "")
                tense = v.get("tense", "")

                tk.Label(
                    v_top,
                    text=f"{surf} → {lemma}",
                    font=("Segoe UI", 10, "bold"),
                    fg="#a78bfa",
                    bg="#1f1f23"
                ).pack(side="left", padx=(0, 8))

                if tense:
                    tk.Label(
                        v_top,
                        text=f"[{tense}]",
                        font=("Segoe UI", 8, "italic"),
                        fg="#38bdf8",
                        bg="#1f1f23"
                    ).pack(side="left", padx=(0, 6))

                if v.get("is_modal"):
                    tk.Label(
                        v_top,
                        text="MODAL",
                        font=("Segoe UI", 7, "bold"),
                        fg="#ffffff",
                        bg="#f59e0b",
                        padx=3, pady=1
                    ).pack(side="left", padx=(0, 4))

                sep_pfx = v.get("separable_prefix")
                if sep_pfx:
                    tk.Label(
                        v_top,
                        text=f"Ayrılan Önek: '{sep_pfx}'",
                        font=("Segoe UI", 8),
                        fg="#4ade80",
                        bg="#1f1f23"
                    ).pack(side="left")

                note = v.get("position_note_tr", "")
                if note:
                    tk.Label(
                        v_card,
                        text=note,
                        font=("Segoe UI", 8),
                        fg="#a1a1aa",
                        bg="#1f1f23",
                        wraplength=420,
                        justify="left"
                    ).pack(anchor="w", pady=(2, 0))

        # 4. Haller ve Nesneler (Cases: Akkusativ / Dativ / Genitiv / Nominativ)
        cases = data.get("cases", [])
        if cases:
            sec_cases = self._create_section("🎯 İsim Halleri (Kasus / Cases)")
            for cs in cases:
                cs_card = tk.Frame(sec_cases, bg="#1f1f23", padx=8, pady=5)
                cs_card.pack(fill="x", pady=2, padx=6)

                cs_top = tk.Frame(cs_card, bg="#1f1f23")
                cs_top.pack(fill="x")

                c_name = cs.get("case", "Nominativ")
                c_color = self.CASE_COLORS.get(c_name, "#9ca3af")

                tk.Label(
                    cs_top,
                    text=f" {c_name.upper()} ",
                    font=("Segoe UI", 8, "bold"),
                    fg="#ffffff",
                    bg=c_color,
                    padx=4, pady=1
                ).pack(side="left", padx=(0, 8))

                tk.Label(
                    cs_top,
                    text=cs.get("phrase", ""),
                    font=("Segoe UI", 9, "bold"),
                    fg="#fafafa",
                    bg="#1f1f23"
                ).pack(side="left")

                reason = cs.get("reason_tr", "")
                if reason:
                    tk.Label(
                        cs_card,
                        text=f"Sebep: {reason}",
                        font=("Segoe UI", 8, "italic"),
                        fg="#a1a1aa",
                        bg="#1f1f23",
                        wraplength=420,
                        justify="left"
                    ).pack(anchor="w", pady=(2, 0))

        # 5. Odak Kelime (Varsa)
        fw = data.get("focus_word")
        if fw and isinstance(fw, dict) and fw.get("surface"):
            sec_focus = self._create_section("🔍 Odak Kelime İncelemesi")
            fw_box = tk.Frame(sec_focus, bg="#1f1f23", padx=8, pady=6)
            fw_box.pack(fill="x", padx=6, pady=4)
            tk.Label(
                fw_box,
                text=f"{fw.get('surface', '')} (Mastar: {fw.get('lemma', '')})",
                font=("Segoe UI", 9, "bold"),
                fg="#facc15",
                bg="#1f1f23"
            ).pack(anchor="w")
            tk.Label(
                fw_box,
                text=fw.get("role_tr", ""),
                font=("Segoe UI", 8),
                fg="#d4d4d8",
                bg="#1f1f23",
                wraplength=420,
                justify="left"
            ).pack(anchor="w", pady=(2, 0))

        # 6. Öğrenme İpuçları (Tips)
        tips = data.get("tips_tr", [])
        if tips:
            sec_tips = self._create_section("💡 Gramer İpuçları")
            for tip in tips:
                t_row = tk.Frame(sec_tips, bg="#27272a")
                t_row.pack(fill="x", padx=8, pady=2)
                tk.Label(
                    t_row,
                    text="•",
                    font=("Segoe UI", 10, "bold"),
                    fg="#eab308",
                    bg="#27272a"
                ).pack(side="left", anchor="n", padx=(0, 4))
                tk.Label(
                    t_row,
                    text=tip,
                    font=("Segoe UI", 8),
                    fg="#d4d4d8",
                    bg="#27272a",
                    wraplength=410,
                    justify="left"
                ).pack(side="left", anchor="w")

    def _render_rule_based_result(self, data: Dict[str, Any]):
        """Kural tabanlı sonuçları ve Gemini anahtarı uyarısını gösterir."""
        rule_notes = data.get("rule_notes", [])
        needs_gemini = data.get("needs_gemini", True)

        if needs_gemini:
            info_banner = tk.Frame(self.scroll_content, bg="#2e1065", padx=12, pady=10)
            info_banner.pack(fill="x", pady=(0, 10))

            tk.Label(
                info_banner,
                text="🤖 Detaylı AI Dilbilgisi Çözümlemesi İçin:",
                font=("Segoe UI", 9, "bold"),
                fg="#c084fc",
                bg="#2e1065"
            ).pack(anchor="w")

            tk.Label(
                info_banner,
                text="Cümledeki Akkusativ/Dativ halleri, fiil konumları ve derin yan cümle yapısını "
                     "görmek için Ayarlar penceresinden ücretsiz bir Google Gemini API anahtarı ekleyebilirsiniz.",
                font=("Segoe UI", 8),
                fg="#e9d5ff",
                bg="#2e1065",
                wraplength=440,
                justify="left"
            ).pack(anchor="w", pady=(4, 0))

        sec_rules = self._create_section("📋 Kural Tabanlı Dilbilgisi Notları")
        if rule_notes:
            for note in rule_notes:
                card = tk.Frame(sec_rules, bg="#1f1f23", padx=8, pady=6)
                card.pack(fill="x", pady=3, padx=6)

                badge = note.get("badge", "Kural")
                title = note.get("title", "")
                text = note.get("text", "")

                top_bar = tk.Frame(card, bg="#1f1f23")
                top_bar.pack(fill="x")

                tk.Label(
                    top_bar,
                    text=f" {badge} ",
                    font=("Segoe UI", 8, "bold"),
                    fg="#ffffff",
                    bg="#6366f1",
                    padx=4, pady=1
                ).pack(side="left", padx=(0, 6))

                tk.Label(
                    top_bar,
                    text=title,
                    font=("Segoe UI", 9, "bold"),
                    fg="#fafafa",
                    bg="#1f1f23"
                ).pack(side="left")

                tk.Label(
                    card,
                    text=text,
                    font=("Segoe UI", 8),
                    fg="#a1a1aa",
                    bg="#1f1f23",
                    wraplength=420,
                    justify="left"
                ).pack(anchor="w", pady=(3, 0))
        else:
            tk.Label(
                sec_rules,
                text="Bu cümle için özel bir kural (modal/ayrılabilir fiil/yan cümle bağlacı) saptanamadı.",
                font=("Segoe UI", 8, "italic"),
                fg="#71717a",
                bg="#27272a",
                padx=10, pady=8
            ).pack(anchor="w")

    def _create_section(self, title: str) -> tk.Frame:
        """Bölüm başlığı ve çerçevesi oluşturur."""
        frame = tk.Frame(self.scroll_content, bg="#27272a", padx=8, pady=8)
        frame.pack(fill="x", pady=6)

        tk.Label(
            frame,
            text=title,
            font=("Segoe UI", 9, "bold"),
            fg="#e4e4e7",
            bg="#27272a"
        ).pack(anchor="w", padx=6, pady=(0, 6))

        return frame
