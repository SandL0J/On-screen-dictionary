"""
Kelime Defteri ve Çalışma Kartları Modülü (Wordbook & Flashcard Review)
Kullanıcının kaydettiği tüm kelimeleri filtreleme, arama,
çalışma kartları (Flashcards) ile pratik yapma ve Anki formatında dışa aktarma arayüzü.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import random
from typing import Optional, List, Dict, Any


class WordbookWindow:
    def __init__(self, parent: tk.Tk, db, tts_engine=None):
        self.db = db
        self.tts = tts_engine

        self.window = tk.Toplevel(parent)
        self.window.title("Kelime Defterim & Flashcards • Ekran Sözlüğü")
        self.window.geometry("820x560")
        self.window.minsize(700, 480)
        self.window.configure(bg="#18181b")

        # Flashcard durumu
        self.flashcard_words: List[Dict[str, Any]] = []
        self.flashcard_mode = "due"  # Varsayılan mod: "due"
        self.current_card_index = 0
        self.is_card_flipped = False

        self._init_ui()
        self._load_words()

    def _init_ui(self):
        # Üst Başlık & İstatistikler
        self.top_frame = tk.Frame(self.window, bg="#27272a", padx=16, pady=12)
        self.top_frame.pack(fill="x")

        self.title_lbl = tk.Label(
            self.top_frame,
            text="📚 Kişisel Almanca Kelime Defteri",
            font=("Segoe UI", 14, "bold"),
            fg="#fafafa",
            bg="#27272a"
        )
        self.title_lbl.pack(side="left")

        self.stats_lbl = tk.Label(
            self.top_frame,
            text="Toplam: 0 | Bugün Tekrar: 0 | Öğrenilen: 0",
            font=("Segoe UI", 9),
            fg="#a1a1aa",
            bg="#27272a"
        )
        self.stats_lbl.pack(side="right")

        # Sekme Kontrolü (1. Defter Listesi, 2. Flashcard Çalışması)
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=10)

        # Sekme 1: Kelime Listesi Tablosu
        self.tab_list = tk.Frame(self.notebook, bg="#18181b")
        self.notebook.add(self.tab_list, text="📋 Kelime Listesi")

        # Sekme 2: Flashcards
        self.tab_flashcards = tk.Frame(self.notebook, bg="#18181b")
        self.notebook.add(self.tab_flashcards, text="🎴 Flashcard / Alıştırma")

        self._setup_list_tab()
        self._setup_flashcard_tab()

    def _setup_list_tab(self):
        # Filtre ve Arama Alanı
        filter_bar = tk.Frame(self.tab_list, bg="#18181b", pady=8)
        filter_bar.pack(fill="x")

        # Arama Kutusu
        tk.Label(filter_bar, text="🔍 Ara:", font=("Segoe UI", 9, "bold"), fg="#fafafa", bg="#18181b").pack(side="left", padx=(0, 6))
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(filter_bar, textvariable=self.search_var, font=("Segoe UI", 9), bg="#27272a", fg="#fafafa", insertbackground="white", width=20)
        self.search_entry.pack(side="left", padx=(0, 12))
        self.search_entry.bind("<KeyRelease>", lambda e: self._load_words())

        # Artikel Filtresi
        tk.Label(filter_bar, text="Artikel:", font=("Segoe UI", 9), fg="#a1a1aa", bg="#18181b").pack(side="left", padx=(0, 4))
        self.article_var = tk.StringVar(value="Hepsi")
        art_cb = ttk.Combobox(filter_bar, textvariable=self.article_var, values=["Hepsi", "der", "die", "das"], width=8, state="readonly")
        art_cb.pack(side="left", padx=(0, 12))
        art_cb.bind("<<ComboboxSelected>>", lambda e: self._load_words())

        # Anki Dışa Aktar Butonu
        btn_export = tk.Button(
            filter_bar,
            text="📥 Anki / CSV İndir",
            font=("Segoe UI", 9, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._export_to_anki
        )
        btn_export.pack(side="right")

        # Sil Butonu
        btn_delete = tk.Button(
            filter_bar,
            text="🗑️ Seçileni Sil",
            font=("Segoe UI", 9),
            bg="#dc2626",
            fg="#ffffff",
            relief="flat",
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._delete_selected_word
        )
        btn_delete.pack(side="right", padx=(0, 8))

        # Kelime Tablosu (Treeview)
        tree_frame = tk.Frame(self.tab_list, bg="#18181b")
        tree_frame.pack(fill="both", expand=True)

        columns = ("id", "article", "german", "plural", "turkish", "pos", "example_de", "status")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("id", text="#")
        self.tree.heading("article", text="Artikel")
        self.tree.heading("german", text="Almanca")
        self.tree.heading("plural", text="Çoğul")
        self.tree.heading("turkish", text="Türkçe Anlamı")
        self.tree.heading("pos", text="Tür")
        self.tree.heading("example_de", text="Örnek Cümle")
        self.tree.heading("status", text="Durum")

        self.tree.column("id", width=35, anchor="center")
        self.tree.column("article", width=65, anchor="center")
        self.tree.column("german", width=120)
        self.tree.column("plural", width=110)
        self.tree.column("turkish", width=160)
        self.tree.column("pos", width=90)
        self.tree.column("example_de", width=180)
        self.tree.column("status", width=80, anchor="center")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self._on_row_double_click)

    def _setup_flashcard_tab(self):
        # Mod Seçim Çubuğu (Due vs All)
        self.fc_mode_frame = tk.Frame(self.tab_flashcards, bg="#18181b", pady=6)
        self.fc_mode_frame.pack(fill="x", padx=20, pady=(10, 0))

        tk.Label(
            self.fc_mode_frame,
            text="Çalışma Modu:",
            font=("Segoe UI", 9, "bold"),
            fg="#a1a1aa",
            bg="#18181b"
        ).pack(side="left", padx=(0, 8))

        self.btn_mode_due = tk.Button(
            self.fc_mode_frame,
            text="🎯 Vadesi Gelenler (Due)",
            font=("Segoe UI", 9, "bold"),
            bg="#3b82f6",
            fg="#ffffff",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            command=lambda: self._set_flashcard_mode("due")
        )
        self.btn_mode_due.pack(side="left", padx=4)

        self.btn_mode_all = tk.Button(
            self.fc_mode_frame,
            text="📚 Tüm Kelimeler",
            font=("Segoe UI", 9),
            bg="#27272a",
            fg="#d4d4d8",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2",
            command=lambda: self._set_flashcard_mode("all")
        )
        self.btn_mode_all.pack(side="left", padx=4)

        # Kart Konteyneri
        self.card_container = tk.Frame(self.tab_flashcards, bg="#18181b", pady=10)
        self.card_container.pack(fill="both", expand=True)

        self.card_box = tk.Frame(self.card_container, bg="#27272a", padx=30, pady=25, relief="solid", bd=1)
        self.card_box.pack(pady=15, ipadx=40, ipady=25)

        self.fc_progress_lbl = tk.Label(self.card_box, text="", font=("Segoe UI", 8), fg="#71717a", bg="#27272a")
        self.fc_progress_lbl.pack(anchor="e", pady=(0, 4))

        self.fc_article_lbl = tk.Label(self.card_box, text="", font=("Segoe UI", 13, "bold"), fg="#38bdf8", bg="#27272a")
        self.fc_article_lbl.pack(pady=(0, 4))

        self.fc_german_lbl = tk.Label(self.card_box, text="Alıştırma Yükleniyor...", font=("Segoe UI", 22, "bold"), fg="#fafafa", bg="#27272a")
        self.fc_german_lbl.pack(pady=(0, 8))

        self.fc_plural_lbl = tk.Label(self.card_box, text="", font=("Segoe UI", 10, "italic"), fg="#a1a1aa", bg="#27272a")
        self.fc_plural_lbl.pack(pady=(0, 10))

        self.fc_divider = tk.Frame(self.card_box, bg="#3f3f46", height=1)
        self.fc_divider.pack(fill="x", pady=8)

        self.fc_turkish_lbl = tk.Label(self.card_box, text="[ Kartı Çevir butonuna tıklayın ]", font=("Segoe UI", 14), fg="#71717a", bg="#27272a")
        self.fc_turkish_lbl.pack(pady=10)

        # Kart Alt Butonları
        self.fc_btn_frame = tk.Frame(self.tab_flashcards, bg="#18181b")
        self.fc_btn_frame.pack(pady=(0, 8))

        self.btn_prev = tk.Button(self.fc_btn_frame, text="⬅️ Önceki", font=("Segoe UI", 10), bg="#3f3f46", fg="#fafafa", relief="flat", padx=12, pady=6, cursor="hand2", command=self._prev_card)
        self.btn_prev.pack(side="left", padx=6)

        self.btn_flip = tk.Button(self.fc_btn_frame, text="🔄 Kartı Çevir", font=("Segoe UI", 10, "bold"), bg="#6366f1", fg="#ffffff", relief="flat", padx=16, pady=6, cursor="hand2", command=self._flip_card)
        self.btn_flip.pack(side="left", padx=6)

        self.btn_next = tk.Button(self.fc_btn_frame, text="➡️ Sonraki", font=("Segoe UI", 10, "bold"), bg="#10b981", fg="#ffffff", relief="flat", padx=14, pady=6, cursor="hand2", command=self._next_card)
        self.btn_next.pack(side="left", padx=6)

        # SM-2 Derecelendirme Butonları Çerçevesi (Kart çevrildiğinde açılır)
        self.rating_frame = tk.Frame(self.tab_flashcards, bg="#18181b")

        self.btn_rate_again = tk.Button(
            self.rating_frame,
            text="🔴 Yeniden (1)",
            font=("Segoe UI", 9, "bold"),
            bg="#ef4444",
            fg="#ffffff",
            relief="flat",
            padx=12,
            pady=5,
            cursor="hand2",
            command=lambda: self._rate_card(1)
        )
        self.btn_rate_again.pack(side="left", padx=4)

        self.btn_rate_hard = tk.Button(
            self.rating_frame,
            text="🟠 Zor (3)",
            font=("Segoe UI", 9, "bold"),
            bg="#f97316",
            fg="#ffffff",
            relief="flat",
            padx=12,
            pady=5,
            cursor="hand2",
            command=lambda: self._rate_card(3)
        )
        self.btn_rate_hard.pack(side="left", padx=4)

        self.btn_rate_good = tk.Button(
            self.rating_frame,
            text="🟢 İyi (4)",
            font=("Segoe UI", 9, "bold"),
            bg="#10b981",
            fg="#ffffff",
            relief="flat",
            padx=12,
            pady=5,
            cursor="hand2",
            command=lambda: self._rate_card(4)
        )
        self.btn_rate_good.pack(side="left", padx=4)

        self.btn_rate_easy = tk.Button(
            self.rating_frame,
            text="🔵 Kolay (5)",
            font=("Segoe UI", 9, "bold"),
            bg="#3b82f6",
            fg="#ffffff",
            relief="flat",
            padx=12,
            pady=5,
            cursor="hand2",
            command=lambda: self._rate_card(5)
        )
        self.btn_rate_easy.pack(side="left", padx=4)

    @property
    def is_rating_visible(self) -> bool:
        """Puanlama butonları çerçevesinin görünür olup olmadığını döner."""
        if not hasattr(self, "rating_frame"):
            return False
        try:
            return bool(self.rating_frame.pack_info())
        except (tk.TclError, Exception):
            return False

    def _set_flashcard_mode(self, mode: str):
        """Flashcard çalışma modunu değiştirir ('due' veya 'all')."""
        self.flashcard_mode = mode
        if mode == "due":
            self.btn_mode_due.configure(bg="#3b82f6", fg="#ffffff", font=("Segoe UI", 9, "bold"))
            self.btn_mode_all.configure(bg="#27272a", fg="#d4d4d8", font=("Segoe UI", 9))
        else:
            self.btn_mode_due.configure(bg="#27272a", fg="#d4d4d8", font=("Segoe UI", 9))
            self.btn_mode_all.configure(bg="#3b82f6", fg="#ffffff", font=("Segoe UI", 9, "bold"))
        self._load_flashcard_words()

    def _load_flashcard_words(self):
        """Seçili moda göre flashcard kelimelerini yükler."""
        if self.flashcard_mode == "due":
            if hasattr(self.db, "get_due_words"):
                self.flashcard_words = list(self.db.get_due_words(target_date=None, limit=None))
            else:
                self.flashcard_words = []
        else:
            if hasattr(self.db, "get_words"):
                self.flashcard_words = list(self.db.get_words())
                if self.flashcard_words:
                    random.shuffle(self.flashcard_words)
            else:
                self.flashcard_words = []

        self.current_card_index = 0
        self._show_current_flashcard()

    def _update_stats_display(self):
        """Üst istatistik etiketini (stats_lbl) SM-2 verilerine göre günceller."""
        if hasattr(self.db, "get_review_statistics"):
            stats = self.db.get_review_statistics()
            self.stats_lbl.configure(
                text=f"Toplam: {stats['total_words']} | Bugün Tekrar: {stats['due_today']} | Öğrenilen: {stats['learned_words']}"
            )
        elif hasattr(self.db, "get_words"):
            total = len(self.db.get_words())
            self.stats_lbl.configure(text=f"Toplam: {total} | Bugün Tekrar: 0 | Öğrenilen: 0")

    def _load_words(self):
        # Listeyi temizle
        for item in self.tree.get_children():
            self.tree.delete(item)

        search_txt = self.search_var.get().strip()
        art_filter = self.article_var.get()
        if art_filter == "Hepsi":
            art_filter = ""

        words = self.db.get_words(search=search_txt, article_filter=art_filter)

        for w in words:
            self.tree.insert("", "end", values=(
                w["id"],
                w["article"].upper() if w["article"] else "-",
                w["german"],
                w["plural"] or "-",
                w["turkish"],
                w["part_of_speech"] or "-",
                w["example_de"] or "-",
                w["status"]
            ))

        self._update_stats_display()
        self._load_flashcard_words()

    def _show_current_flashcard(self):
        total_words = 0
        if hasattr(self.db, "get_review_statistics"):
            stats = self.db.get_review_statistics()
            total_words = stats.get("total_words", 0)
        elif hasattr(self.db, "get_words"):
            total_words = len(self.db.get_words())

        if hasattr(self, "rating_frame"):
            self.rating_frame.pack_forget()

        if not self.flashcard_words:
            self.fc_progress_lbl.configure(text="")
            self.fc_article_lbl.configure(text="")
            self.fc_plural_lbl.configure(text="")
            self.is_card_flipped = False

            if total_words == 0:
                self.fc_german_lbl.configure(text="Henüz kayıtlı kelime yok")
                self.fc_turkish_lbl.configure(text="Sözlük kartından kelimeleri deftere ekleyin.", fg="#71717a")
            else:
                self.fc_german_lbl.configure(text="Tebrikler! Bugünlük tekrar bitti.")
                self.fc_turkish_lbl.configure(text="Bugün tekrar edilecek başka kelime kalmadı.", fg="#4ade80")
            return

        total = len(self.flashcard_words)
        if self.current_card_index >= total:
            self.current_card_index = 0

        self.fc_progress_lbl.configure(text=f"Kart {self.current_card_index + 1} / {total}")
        w = self.flashcard_words[self.current_card_index]
        self.is_card_flipped = False
        art = w.get("article", "").upper()
        self.fc_article_lbl.configure(text=art if art else "")
        self.fc_german_lbl.configure(text=w.get("german", ""))
        self.fc_plural_lbl.configure(text=f"Çoğul: {w.get('plural', '')}" if w.get("plural") else "")
        self.fc_turkish_lbl.configure(text="[ Kartı Çevir butonuna tıklayın ]", fg="#71717a")

    def _flip_card(self):
        if not self.flashcard_words:
            return
        w = self.flashcard_words[self.current_card_index]
        if not self.is_card_flipped:
            self.fc_turkish_lbl.configure(text=w.get("turkish", ""), fg="#4ade80")
            self.is_card_flipped = True
            if hasattr(self, "rating_frame"):
                self.rating_frame.pack(pady=(0, 15))
        else:
            self.fc_turkish_lbl.configure(text="[ Kartı Çevir butonuna tıklayın ]", fg="#71717a")
            self.is_card_flipped = False
            if hasattr(self, "rating_frame"):
                self.rating_frame.pack_forget()

    def _rate_card(self, quality: int):
        """SM-2 puanlaması yapar ve sıradaki karta geçer."""
        if not self.flashcard_words:
            return

        if self.current_card_index >= len(self.flashcard_words):
            self.current_card_index = 0

        current_card = self.flashcard_words[self.current_card_index]
        word_id = current_card.get("id")

        if word_id is not None and hasattr(self.db, "update_sm2_review"):
            self.db.update_sm2_review(word_id, quality)

        if self.flashcard_mode == "due":
            # Değerlendirilen kelime kuyruktan çıkarılır
            self.flashcard_words.pop(self.current_card_index)
            if self.flashcard_words and self.current_card_index >= len(self.flashcard_words):
                self.current_card_index = 0
        else:
            # Tüm kelimeler modunda kelime listeden çıkarılmaz, sadece sıradaki karta ilerlenir
            if self.flashcard_words:
                self.current_card_index = (self.current_card_index + 1) % len(self.flashcard_words)

        self._update_stats_display()
        self._show_current_flashcard()

    def _prev_card(self):
        if not self.flashcard_words:
            return
        self.current_card_index = (self.current_card_index - 1) % len(self.flashcard_words)
        self._show_current_flashcard()

    def _next_card(self):
        if not self.flashcard_words:
            return
        self.current_card_index = (self.current_card_index + 1) % len(self.flashcard_words)
        self._show_current_flashcard()


    def _play_flashcard_audio(self):
        """Dinleme özelliği devre dışı bırakılmıştır."""
        pass

    def _on_row_double_click(self, event):
        """Çift tıklamada ses çalma özelliği devre dışı bırakılmıştır."""
        pass

    def _delete_selected_word(self):
        item_id = self.tree.focus()
        if not item_id:
            messagebox.showinfo("Seçim Yapın", "Lütfen silmek istediğiniz kelimeyi tablodan seçin.", parent=self.window)
            return
        vals = self.tree.item(item_id, "values")
        word_id = int(vals[0])
        german_word = vals[2]

        if messagebox.askyesno("Kelimeyi Sil", f"'{german_word}' kelimesini silmek istediğinize emin misiniz?", parent=self.window):
            self.db.delete_word(word_id)
            self._load_words()

    def _export_to_anki(self):
        file_path = filedialog.asksaveasfilename(
            parent=self.window,
            title="Anki / CSV Dışa Aktar",
            defaultextension=".txt",
            filetypes=[("Metin / TSV (Anki uyumlu)", "*.txt"), ("CSV Dosyası", "*.csv")]
        )
        if file_path:
            count = self.db.export_to_anki_csv(file_path)
            messagebox.showinfo("Başarılı", f"{count} kelime Anki uyumlu olarak dışa aktarıldı:\n{file_path}", parent=self.window)
