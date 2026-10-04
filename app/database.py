"""
SQLite Veritabanı Modülü
Kelime Defteri (Wordbook), Geçmiş (History) ve Çevrimdışı Önbellek (Cache) tablolarını yönetir.
"""
import sqlite3
import json
import csv
import os
import sys
import uuid
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Tuple

from app.paths import get_db_path, CODE_DIR

DB_PATH = get_db_path()


def calculate_sm2(quality: int, repetitions: int, interval_days: int, ease_factor: float,
                  today: Optional[Union[str, date, datetime]] = None) -> Tuple[int, int, float, str]:
    """
    SuperMemo 2 (SM-2) Aralikli Tekrar Algoritmasi hesaplayicisi.

    Donus:
        (new_repetitions, new_interval_days, new_ease_factor, next_review_date_str)
    """
    quality = min(5, max(1, quality))
    if today is None:
        current_date = datetime.now().date()
    elif isinstance(today, str):
        current_date = datetime.strptime(today, "%Y-%m-%d").date()
    elif isinstance(today, datetime):
        current_date = today.date()
    else:
        current_date = today

    if quality < 3:
        # Basarisiz hatirlama: tekrarlar sifirlanir, aralik 1 gune iner, ease_factor DEGISMEZ
        new_reps = 0
        new_interval = 1
        new_ef = ease_factor
    else:
        # Basarili hatirlama (quality >= 3)
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = max(1, int(round(interval_days * ease_factor)))

        new_reps = repetitions + 1

        # EF guncelleme formulu: EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        ef_delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
        new_ef = round(ease_factor + ef_delta, 2)
        if new_ef < 1.3:
            new_ef = 1.3

    next_date = current_date + timedelta(days=new_interval)
    next_date_str = next_date.strftime("%Y-%m-%d")
    return new_reps, new_interval, new_ef, next_date_str


class Database:
    def __init__(self, db_path: Optional[Path] = None, history_limit: int = 100):
        self.db_path = db_path or get_db_path()
        self._lock = threading.RLock()
        self._is_closed = False
        self._active_operations = 0
        self._op_condition = threading.Condition(self._lock)
        try:
            self.history_limit = max(1, int(history_limit)) if history_limit is not None else 100
        except (ValueError, TypeError):
            self.history_limit = 100
        self._init_db()

    @property
    def is_closed(self) -> bool:
        """Veritabanının kapatılıp kapatılmadığını döner."""
        with getattr(self, "_lock", threading.RLock()):
            return getattr(self, "_is_closed", False)

    def set_history_limit(self, limit: int):
        """Arama geçmişi saklama üst sınırını günceller."""
        try:
            self.history_limit = max(1, int(limit))
        except (ValueError, TypeError):
            self.history_limit = 100

    @contextmanager
    def _get_connection(self):
        with getattr(self, "_lock", threading.RLock()):
            if getattr(self, "_is_closed", False):
                raise sqlite3.OperationalError("Veritabanı kapatılmış durumda; yeni işlem yapılamaz.")
            self._active_operations = getattr(self, "_active_operations", 0) + 1

        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout = 5000;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            yield conn
            conn.commit()
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            with getattr(self, "_lock", threading.RLock()):
                self._active_operations = max(0, getattr(self, "_active_operations", 1) - 1)
                cond = getattr(self, "_op_condition", None)
                if cond is not None:
                    cond.notify_all()

    def _quarantine_corrupt_db(self, err_msg: str):
        """Bozuk veritabanı dosyasını ve ilişkili WAL/SHM dosyalarını karantinaya alır."""
        if not isinstance(self.db_path, (str, Path)) or str(self.db_path) == ":memory:":
            return
        p = Path(self.db_path)
        if not p.exists():
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        corrupt_target = p.with_name(f"{p.name}.corrupt.{ts}")
        try:
            wal_file = p.with_name(f"{p.name}-wal")
            shm_file = p.with_name(f"{p.name}-shm")
            if wal_file.exists():
                try:
                    wal_file.rename(p.with_name(f"{p.name}-wal.corrupt.{ts}"))
                except Exception:
                    pass
            if shm_file.exists():
                try:
                    shm_file.rename(p.with_name(f"{p.name}-shm.corrupt.{ts}"))
                except Exception:
                    pass
            p.rename(corrupt_target)
            print(f"[Ekran Sözlüğü UYARI] Bozuk veritabanı karantinaya alındı ({err_msg}): {corrupt_target}")
        except Exception as q_err:
            print(f"[Ekran Sözlüğü HATA] Bozuk veritabanı karantinaya alınamadı: {q_err}")

    def _execute_schema_creation(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if str(self.db_path) != ":memory:":
                try:
                    cursor.execute("PRAGMA journal_mode = WAL;")
                except Exception as e:
                    print(f"[Ekran Sözlüğü UYARI] WAL modu ayarlanamadı: {e}")

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

    def _init_db(self):
        if isinstance(self.db_path, (str, Path)) and str(self.db_path) != ":memory:":
            try:
                Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"[Ekran Sözlüğü UYARI] Veritabanı dizini oluşturulamadı ({e}). Kod klasörüne dönülüyor.")
                self.db_path = CODE_DIR / "ekran_sozlugu.db"
                try:
                    Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass

        try:
            self._execute_schema_creation()
        except sqlite3.DatabaseError as e:
            print(f"[Ekran Sözlüğü UYARI] Veritabanı bozulması tespit edildi ({e}). Kurtarma ve karantina başlatılıyor...")
            self._quarantine_corrupt_db(str(e))
            self._execute_schema_creation()
            try:
                self.seed_starter_words()
            except Exception:
                pass

    # --- ÖNBELLEK METOTLARI ---
    def get_cache(self, query: str) -> Optional[Dict[str, Any]]:
        if self.is_closed:
            return None
        clean_query = query.strip().lower()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT result_json FROM cache WHERE query_text = ?", (clean_query,))
                row = cursor.fetchone()
                if row:
                    try:
                        return json.loads(row["result_json"])
                    except Exception:
                        return None
        except sqlite3.OperationalError:
            if self.is_closed:
                return None
            raise
        return None

    def set_cache(self, query: str, data: Dict[str, Any]) -> bool:
        if self.is_closed:
            print("[Ekran Sözlüğü UYARI] Kapalı veritabanına önbellek yazma denemesi reddedildi.")
            return False
        clean_query = query.strip().lower()
        json_data = json.dumps(data, ensure_ascii=False)
        try:
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
                return True
        except sqlite3.OperationalError:
            if self.is_closed:
                print("[Ekran Sözlüğü UYARI] Kapalı veritabanına önbellek yazma denemesi reddedildi.")
                return False
            raise

    # --- ARAMA GEÇMİŞİ METOTLARI ---
    def add_history(self, query: str, data: Dict[str, Any], limit: Optional[int] = None) -> bool:
        """
        Yeni bir arama kaydı ekler.
        Eğer toplam geçmiş sayısı history_limit sınırını aşarsa, YALNIZCA bu yeni kayıt
        eklenmesi anında en eski kayıtlar temizlenir.
        """
        if self.is_closed:
            print("[Ekran Sözlüğü UYARI] Kapalı veritabanına arama geçmişi yazma denemesi reddedildi.")
            return False
        clean_query = query.strip()
        json_data = json.dumps(data, ensure_ascii=False)
        eff_limit = limit if limit is not None else getattr(self, "history_limit", 100)
        try:
            eff_limit = max(1, int(eff_limit))
        except (ValueError, TypeError):
            eff_limit = 100

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO history (query_text, result_json)
                    VALUES (?, ?)
                """, (clean_query, json_data))

                if eff_limit > 0:
                    cursor.execute("""
                        DELETE FROM history
                        WHERE id NOT IN (
                            SELECT id FROM history ORDER BY id DESC LIMIT ?
                        )
                    """, (eff_limit,))
                conn.commit()
                return True
        except sqlite3.OperationalError:
            if self.is_closed:
                print("[Ekran Sözlüğü UYARI] Kapalı veritabanına arama geçmişi yazma denemesi reddedildi.")
                return False
            raise

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

        if self.is_closed:
            print("[Ekran Sözlüğü UYARI] Kapalı veritabanına kelime ekleme reddedildi.")
            return -1

        try:
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
        except sqlite3.OperationalError:
            if self.is_closed:
                print("[Ekran Sözlüğü UYARI] Kapalı veritabanına kelime ekleme reddedildi.")
                return -1
            raise

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

            new_reps, new_interval, new_ef, next_date_str = calculate_sm2(
                quality=quality,
                repetitions=reps,
                interval_days=interval,
                ease_factor=ef,
                today=review_date
            )

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

    # Ortak vade SQL kosulu (get_due_words ve get_review_statistics tarafindan paylasilir)
    DUE_WORDS_CONDITION = "(next_review_date <= ? OR next_review_date IS NULL)"

    @classmethod
    def get_due_condition_sql(cls) -> str:
        """Vadesi gelmis kelimeler icin ortak SQL WHERE kosulunu doner."""
        return cls.DUE_WORDS_CONDITION

    def get_due_words(self, target_date: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Tekrar zamani gelmis (next_review_date <= target_date VEYA next_review_date IS NULL) kelimeleri doner."""
        if not target_date:
            target_date = datetime.now().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = f"""
                SELECT * FROM wordbook
                WHERE {self.get_due_condition_sql()}
                ORDER BY next_review_date ASC, id ASC
            """
            params: List[Any] = [target_date]
            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_review_statistics(self, target_date: Optional[str] = None) -> Dict[str, int]:
        """
        Kelime defteri aralikli tekrar (SM-2) istatistiklerini doner.

        Donen anahtarlar ve SQL kosullari:
            - total_words: tum kayitlar (SELECT COUNT(*) FROM wordbook)
            - due_today: get_due_words ile BIREBIR ayni kosul (next_review_date <= ? OR next_review_date IS NULL)
            - learned_words: repetitions >= 3 (SELECT COUNT(*) FROM wordbook WHERE repetitions >= 3)
            - new_words: last_reviewed_at IS NULL (SELECT COUNT(*) FROM wordbook WHERE last_reviewed_at IS NULL)
            
            Geriye donuk uyumluluk anahtarlari:
            - total: total_words ile esdeger
            - due: due_today ile esdeger
            - learning: henuz ogrenilenler (repetitions < 3)
            - reviewed: en az 1 kez incelenenler (last_reviewed_at IS NOT NULL)
        """
        if not target_date:
            target_date = datetime.now().strftime("%Y-%m-%d")

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. total_words: tum kayitlar
            cursor.execute("SELECT COUNT(*) as cnt FROM wordbook")
            total_words = cursor.fetchone()["cnt"]

            # 2. due_today: get_due_words ile BIREBIR ayni kosul (limitsiz sayim)
            cursor.execute(f"""
                SELECT COUNT(*) as cnt FROM wordbook
                WHERE {self.get_due_condition_sql()}
            """, (target_date,))
            due_today = cursor.fetchone()["cnt"]

            # 3. learned_words: repetitions >= 3
            cursor.execute("SELECT COUNT(*) as cnt FROM wordbook WHERE repetitions >= 3")
            learned_words = cursor.fetchone()["cnt"]

            # 4. new_words: last_reviewed_at IS NULL
            cursor.execute("SELECT COUNT(*) as cnt FROM wordbook WHERE last_reviewed_at IS NULL")
            new_words = cursor.fetchone()["cnt"]

            return {
                "total_words": total_words,
                "due_today": due_today,
                "learned_words": learned_words,
                "new_words": new_words,
                # Geriye donuk uyumluluk:
                "total": total_words,
                "due": due_today,
                "learning": total_words - learned_words,
                "reviewed": total_words - new_words
            }

    def backup(self, target_path: Union[str, Path]) -> bool:
        """
        Canlı veritabanını hedef konuma SQLite Backup API ile atomik ve güvenli yedekler.
        Bütünlük kontrolü (PRAGMA integrity_check) başarılı olursa True döner.
        """
        target = Path(target_path).resolve()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            unique_suffix = f"tmp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
            tmp_target = target.with_name(f"{target.stem}.{unique_suffix}{target.suffix}")

            with self._get_connection() as src_conn:
                dst_conn = sqlite3.connect(str(tmp_target))
                try:
                    src_conn.backup(dst_conn)
                    cur = dst_conn.cursor()
                    cur.execute("PRAGMA integrity_check;")
                    check = cur.fetchone()
                    if not check or check[0] != "ok":
                        raise sqlite3.DatabaseError(f"Yedek bütünlük doğrulaması başarısız: {check}")
                finally:
                    dst_conn.close()

            os.replace(tmp_target, target)
            return True
        except Exception as e:
            print(f"[Ekran Sözlüğü HATA] Veritabanı yedeği alınamadı ({target}): {e}")
            if 'tmp_target' in locals() and tmp_target.exists():
                try:
                    tmp_target.unlink()
                except Exception:
                    pass
            return False

    def close(self, timeout: float = 3.0) -> bool:
        """
        Veritabanını güvenle kapatır.
        Aktif veritabanı işlemleri (yazma/okuma) varsa tamamlanmalarını timeout süresince bekler.
        İşlemler tamamlandıktan sonra veritabanını kapatır ve WAL modundaki bekleyen yazmaları diske temizler (checkpoint).
        Tüm işlemler güvenle tamamlanıp kapatıldıysa True, süre aşımı olduysa False döner.
        """
        with getattr(self, "_lock", threading.RLock()):
            if getattr(self, "_is_closed", False):
                return True
            end_time = time.monotonic() + max(0.1, timeout)
            cond = getattr(self, "_op_condition", None)
            while getattr(self, "_active_operations", 0) > 0:
                rem = end_time - time.monotonic()
                if rem <= 0:
                    break
                if cond is not None:
                    cond.wait(timeout=rem)
                else:
                    break

            if getattr(self, "_active_operations", 0) == 0:
                self._is_closed = True
                all_finished = True
            else:
                all_finished = False

        if all_finished and isinstance(self.db_path, (str, Path)) and str(self.db_path) != ":memory:":
            conn = None
            try:
                conn = sqlite3.connect(self.db_path, timeout=5.0)
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            except Exception as e:
                print(f"[Ekran Sözlüğü UYARI] Veritabanı kapatma checkpoint hatası: {e}")
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass
        return all_finished
