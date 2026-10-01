"""
SQLite Veritabanı Modülü
Kelime Defteri (Wordbook), Geçmiş (History) ve Çevrimdışı Önbellek (Cache) tablolarını yönetir.
"""
import sqlite3
import json
import csv
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

DB_PATH = Path(__file__).resolve().parent.parent / "ekran_sozlugu.db"


from contextlib import contextmanager

class Database:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Kelime Defteri Tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wordbook (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    german TEXT NOT NULL,
                    article TEXT DEFAULT '',
                    plural TEXT DEFAULT '',
                    turkish TEXT NOT NULL,
                    part_of_speech TEXT DEFAULT '',
                    example_de TEXT DEFAULT '',
                    example_tr TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    status TEXT DEFAULT 'learning',
                    ease_factor REAL DEFAULT 2.5,
                    interval_days INTEGER DEFAULT 0,
                    repetitions INTEGER DEFAULT 0,
                    last_reviewed_at TIMESTAMP DEFAULT NULL,
                    next_review_date TEXT DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Sütun göçü (Migration) - Mevcut veritabanlarında SM-2 alanları yoksa ekle
            cursor.execute("PRAGMA table_info(wordbook)")
            cols = [col[1] for col in cursor.fetchall()]
            if "ease_factor" not in cols:
                cursor.execute("ALTER TABLE wordbook ADD COLUMN ease_factor REAL DEFAULT 2.5")
            if "interval_days" not in cols:
                cursor.execute("ALTER TABLE wordbook ADD COLUMN interval_days INTEGER DEFAULT 0")
            if "repetitions" not in cols:
                cursor.execute("ALTER TABLE wordbook ADD COLUMN repetitions INTEGER DEFAULT 0")
            if "last_reviewed_at" not in cols:
                cursor.execute("ALTER TABLE wordbook ADD COLUMN last_reviewed_at TIMESTAMP DEFAULT NULL")
            if "next_review_date" not in cols:
                cursor.execute("ALTER TABLE wordbook ADD COLUMN next_review_date TEXT DEFAULT NULL")

            # 2. Arama Geçmişi Tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_text TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    looked_up_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 3. Çeviri Önbelleği (Offline Cache)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    query_text TEXT PRIMARY KEY,
                    result_json TEXT NOT NULL,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    # --- ÖNBELLEK METOTLARI ---
    def get_cache(self, query: str) -> Optional[Dict[str, Any]]:
        clean_query = query.strip().lower()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT result_json FROM cache WHERE query_text = ?", (clean_query,))
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row["result_json"])
                except Exception:
                    return None
        return None

    def set_cache(self, query: str, data: Dict[str, Any]):
        clean_query = query.strip().lower()
        json_data = json.dumps(data, ensure_ascii=False)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cache (query_text, result_json, cached_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(query_text) DO UPDATE SET
                    result_json = excluded.result_json,
                    cached_at = CURRENT_TIMESTAMP
            """, (clean_query, json_data))
            conn.commit()

    # --- ARAMA GEÇMİŞİ METOTLARI ---
    def add_history(self, query: str, data: Dict[str, Any]):
        clean_query = query.strip()
        json_data = json.dumps(data, ensure_ascii=False)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO history (query_text, result_json)
                VALUES (?, ?)
            """, (clean_query, json_data))
            conn.commit()

    def get_recent_history(self, limit: int = 30) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, query_text, result_json, looked_up_at
                FROM history
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                try:
                    res_dict = json.loads(r["result_json"])
                except Exception:
                    res_dict = {}
                results.append({
                    "id": r["id"],
                    "query_text": r["query_text"],
                    "looked_up_at": r["looked_up_at"],
                    "result": res_dict
                })
            return results

    def clear_history(self):
        with self._get_connection() as conn:
            conn.cursor().execute("DELETE FROM history")
            conn.commit()

    # --- KELİME DEFTERİ METOTLARI ---
    def add_word(self, german: str, turkish: str, article: str = "", plural: str = "",
                 part_of_speech: str = "", example_de: str = "", example_tr: str = "",
                 notes: str = "", status: str = "learning", tags: str = "",
                 ease_factor: float = 2.5, interval_days: int = 0, repetitions: int = 0,
                 last_reviewed_at: Optional[str] = None, next_review_date: Optional[str] = None,
                 **kwargs) -> int:
        clean_german = (german or "").strip()
        if not clean_german:
            return -1

        clean_notes = (notes or "").strip()
        if tags:
            tag_label = f"[{tags.strip()}]"
            clean_notes = f"{clean_notes} {tag_label}".strip() if clean_notes else tag_label

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Aynı kelime var mı kontrol et
            cursor.execute("SELECT id FROM wordbook WHERE LOWER(german) = LOWER(?)", (clean_german,))
            existing = cursor.fetchone()
            if existing:
                # Güncelle: Var olan kelimenin SM-2 alanları ve öğrenme geçmişi korunur!
                cursor.execute("""
                    UPDATE wordbook SET
                        article = ?, plural = ?, turkish = ?, part_of_speech = ?,
                        example_de = ?, example_tr = ?, notes = ?
                    WHERE id = ?
                """, (article, plural, turkish, part_of_speech, example_de, example_tr, clean_notes, existing["id"]))
                conn.commit()
                return existing["id"]
            else:
                today_str = datetime.now().strftime("%Y-%m-%d")
                assigned_next_review = next_review_date or today_str
                cursor.execute("""
                    INSERT INTO wordbook (german, article, plural, turkish, part_of_speech,
                                          example_de, example_tr, notes, status,
                                          ease_factor, interval_days, repetitions,
                                          last_reviewed_at, next_review_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (german.strip(), article.strip(), plural.strip(), turkish.strip(),
                      part_of_speech.strip(), example_de.strip(), example_tr.strip(),
                      clean_notes, status,
                      ease_factor, interval_days, repetitions,
                      last_reviewed_at, assigned_next_review))
                conn.commit()
                return cursor.lastrowid

    def seed_starter_words(self) -> int:
        """Yeni başlayan kullanıcılar için temel kelimeleri deftere ekler (defter boşsa)."""
        starters = [
            ("Haus", "ev, konut", "das", "die Häuser", "İsim (Nomen)", "Ich gehe nach Hause.", "Eve gidiyorum.", "Başlangıç paketi"),
            ("Buch", "kitap", "das", "die Bücher", "İsim (Nomen)", "Ich lese ein spannendes Buch.", "Heyecan verici bir kitap okuyorum.", "Başlangıç paketi"),
            ("Zeit", "zaman, vakit", "die", "die Zeiten", "İsim (Nomen)", "Ich habe heute leider keine Zeit.", "Bugün vaktim yok.", "Başlangıç paketi"),
            ("Tisch", "masa", "der", "die Tische", "İsim (Nomen)", "Das Buch liegt auf dem Tisch.", "Kitap masanın üzerinde duruyor.", "Başlangıç paketi"),
            ("Freund", "arkadaş, dost", "der", "die Freunde", "İsim (Nomen)", "Er ist mein bester Freund.", "O benim en iyi arkadaşım.", "Başlangıç paketi")
        ]
        count = 0
        today_str = datetime.now().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM wordbook")
            if cursor.fetchone()["cnt"] == 0:
                for de, tr, art, pl, pos, ex_de, ex_tr, note in starters:
                    cursor.execute("""
                        INSERT INTO wordbook (german, article, plural, turkish, part_of_speech,
                                              example_de, example_tr, notes, status,
                                              ease_factor, interval_days, repetitions,
                                              last_reviewed_at, next_review_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'learning', 2.5, 0, 0, NULL, ?)
                    """, (de, art, pl, tr, pos, ex_de, ex_tr, note, today_str))
                    count += 1
                conn.commit()
        return count

    def is_word_saved(self, german: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM wordbook WHERE LOWER(german) = LOWER(?)", (german.strip(),))
            return cursor.fetchone() is not None

    def get_word_by_german(self, german: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM wordbook WHERE LOWER(german) = LOWER(?)", (german.strip(),))
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_word_by_german(self, german: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM wordbook WHERE LOWER(german) = LOWER(?)", (german.strip(),))
            conn.commit()
            return cursor.rowcount > 0

    def get_words(self, search: str = "", article_filter: str = "",
                  status_filter: str = "") -> List[Dict[str, Any]]:
        query = "SELECT * FROM wordbook WHERE 1=1"
        params = []
        if search:
            query += " AND (LOWER(german) LIKE ? OR LOWER(turkish) LIKE ?)"
            term = f"%{search.lower().strip()}%"
            params.extend([term, term])
        if article_filter:
            query += " AND LOWER(article) = LOWER(?)"
            params.append(article_filter.strip())
        if status_filter:
            query += " AND status = ?"
            params.append(status_filter.strip())
        query += " ORDER BY id DESC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def delete_word(self, word_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM wordbook WHERE id = ?", (word_id,))
            conn.commit()
            return cursor.rowcount > 0

    def update_word_status(self, word_id: int, new_status: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE wordbook SET status = ? WHERE id = ?", (new_status, word_id))
            conn.commit()
            return cursor.rowcount > 0

    def export_to_anki_csv(self, file_path: str) -> int:
        """Kelime defterini Anki uyumlu CSV/TXT olarak dışa aktarır."""
        words = self.get_words()
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter="\t")
            for w in words:
                front = f"{w['article']} {w['german']}".strip()
                if w['plural']:
                    front += f" (Pl: {w['plural']})"
                back = w['turkish']
                if w['example_de']:
                    back += f"<br><i>Örnek:</i> {w['example_de']}"
                    if w['example_tr']:
                        back += f" ({w['example_tr']})"
                writer.writerow([front, back, w['part_of_speech'], w['status']])
        return len(words)

    def get_word_by_id(self, word_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM wordbook WHERE id = ?", (word_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_sm2_review(self, word_id: int, quality: int,
                          review_date: Optional[Union[str, date, datetime]] = None) -> Optional[Dict[str, Any]]:
        """
        SuperMemo 2 (SM-2) Algoritması ile kelime tekrarını günceller.
        
        Parametreler:
            word_id: Kelimenin veritabanı ID'si
            quality: 0-5 arası hatırlama kalitesi:
                     0: Tamamen unutuldu / Blackout
                     1: Yanlış hatırlandı
                     2: Yanlış ancak cevabı görünce hatırlandı
                     3: Güçlükle hatırlandı (geçer)
                     4: Tereddütle hatırlandı (iyi)
                     5: Mükemmel hatırlandı (kolay)
            review_date: İsteğe bağlı tekrar tarihi (varsayılan: bugün)
            
        Dönüş:
            Güncellenmiş kelime sözlüğü veya kelime bulunamazsa None.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM wordbook WHERE id = ?", (word_id,))
            row = cursor.fetchone()
            if not row:
                return None

            row_dict = dict(row)
            ef = float(row_dict.get("ease_factor") if row_dict.get("ease_factor") is not None else 2.5)
            interval = int(row_dict.get("interval_days") if row_dict.get("interval_days") is not None else 0)
            reps = int(row_dict.get("repetitions") if row_dict.get("repetitions") is not None else 0)

            # Tarih belirleme
            if review_date is None:
                current_date = datetime.now().date()
            elif isinstance(review_date, str):
                current_date = datetime.strptime(review_date, "%Y-%m-%d").date()
            elif isinstance(review_date, datetime):
                current_date = review_date.date()
            else:
                current_date = review_date

            # SM-2 Mantığı:
            if quality < 3:
                # Başarısız hatırlama: tekrarlar sıfırlanır, aralık 1 güne iner, ease_factor DEĞİŞMEZ
                new_reps = 0
                new_interval = 1
                new_ef = ef
            else:
                # Başarılı hatırlama (quality >= 3)
                if reps == 0:
                    new_interval = 1
                elif reps == 1:
                    new_interval = 6
                else:
                    new_interval = max(1, int(round(interval * ef)))

                new_reps = reps + 1

                # EF güncelleme formülü: EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
                ef_delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
                new_ef = round(ef + ef_delta, 2)
                if new_ef < 1.3:
                    new_ef = 1.3

            next_date = current_date + timedelta(days=new_interval)
            next_date_str = next_date.strftime("%Y-%m-%d")
            last_reviewed_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                UPDATE wordbook SET
                    ease_factor = ?,
                    interval_days = ?,
                    repetitions = ?,
                    last_reviewed_at = ?,
                    next_review_date = ?,
                    status = 'reviewed'
                WHERE id = ?
            """, (new_ef, new_interval, new_reps, last_reviewed_str, next_date_str, word_id))
            conn.commit()

            cursor.execute("SELECT * FROM wordbook WHERE id = ?", (word_id,))
            updated_row = cursor.fetchone()
            return dict(updated_row) if updated_row else None

    def get_due_words(self, target_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Tekrar zamanı gelmiş (next_review_date <= target_date) kelimeleri döner."""
        if not target_date:
            target_date = datetime.now().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM wordbook
                WHERE next_review_date IS NOT NULL AND next_review_date <= ?
                ORDER BY next_review_date ASC, id ASC
            """, (target_date,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
