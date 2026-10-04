"""
Birim testleri: app/paths.py modülü ve kullanıcı veri yolları / veri göçü (migration).
"""
import importlib
import io
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.paths import (
    CODE_DIR,
    get_data_dir,
    get_config_path,
    get_db_path,
    get_log_path,
    migrate_legacy_data,
    _reset_paths_state,
)
import app.config
import app.database


class TestPathsAndMigration(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()
        self.temp_test_dir = Path(tempfile.mkdtemp(prefix="test_paths_suite_")).resolve()
        self.data_dir = self.temp_test_dir / "data"
        self.legacy_dir = self.temp_test_dir / "legacy"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.legacy_dir.mkdir(parents=True, exist_ok=True)
        os.environ["EKRAN_SOZLUGU_DATA_DIR"] = str(self.data_dir)
        _reset_paths_state()

    def tearDown(self):
        _reset_paths_state()
        os.environ.clear()
        os.environ.update(self.original_env)
        importlib.reload(app.config)
        importlib.reload(app.database)
        shutil.rmtree(self.temp_test_dir, ignore_errors=True)

    def test_get_data_dir_from_env(self):
        """EKRAN_SOZLUGU_DATA_DIR ortam değişkeni ayarlandığında onu kullanmalıdır."""
        custom_dir = Path(self.temp_test_dir) / "custom_data"
        os.environ["EKRAN_SOZLUGU_DATA_DIR"] = str(custom_dir)

        resolved = get_data_dir(create=True)
        self.assertEqual(resolved, custom_dir.resolve())
        self.assertTrue(custom_dir.exists())
        self.assertTrue(custom_dir.is_dir())

    def test_get_data_dir_appdata_fallback(self):
        """EKRAN_SOZLUGU_DATA_DIR yoksa %APPDATA%\\EkranSozlugu kullanılmalıdır."""
        os.environ.pop("EKRAN_SOZLUGU_DATA_DIR", None)
        fake_appdata = Path(self.temp_test_dir) / "AppData" / "Roaming"
        os.environ["APPDATA"] = str(fake_appdata)

        resolved = get_data_dir(create=True)
        expected = (fake_appdata / "EkranSozlugu").resolve()
        self.assertEqual(resolved, expected)
        self.assertTrue(expected.exists())

    def test_get_data_dir_home_fallback(self):
        """EKRAN_SOZLUGU_DATA_DIR ve APPDATA yoksa home / .ekran_sozlugu kullanılmalıdır."""
        os.environ.pop("EKRAN_SOZLUGU_DATA_DIR", None)
        os.environ.pop("APPDATA", None)
        fake_home = Path(self.temp_test_dir) / "home_user"
        fake_home.mkdir(parents=True, exist_ok=True)

        with patch("pathlib.Path.home", return_value=fake_home):
            resolved = get_data_dir(create=True)
            expected = (fake_home / ".ekran_sozlugu").resolve()
            self.assertEqual(resolved, expected)
            self.assertTrue(expected.exists())

    def test_get_data_dir_unwritable_fallback_to_code_dir(self):
        """Veri dizini oluşturulamaz veya yazılamazsa kod klasörüne geri düşülmelidir."""
        unwritable_dir = Path(self.temp_test_dir) / "non_writable_target"
        os.environ["EKRAN_SOZLUGU_DATA_DIR"] = str(unwritable_dir)

        with patch.object(Path, "mkdir", side_effect=PermissionError("Erişim engellendi")):
            resolved = get_data_dir(create=True)
            self.assertEqual(resolved, CODE_DIR)

    def test_helper_paths(self):
        """get_config_path, get_db_path, get_log_path doğru alt yolları üretmelidir."""
        self.assertEqual(get_config_path(), self.data_dir.resolve() / "config.json")
        self.assertEqual(get_db_path(), self.data_dir.resolve() / "ekran_sozlugu.db")
        self.assertEqual(get_log_path(), self.data_dir.resolve() / "ekran_sozlugu_error.log")

    def test_migrate_copies_when_target_missing(self):
        """Hedefte dosyalar yoksa kaynak dosyalar kopyalanmalı, kaynak silinmemelidir."""
        src_cfg = self.legacy_dir / "config.json"
        src_db = self.legacy_dir / "ekran_sozlugu.db"
        src_cfg.write_text('{"theme": "light"}', encoding="utf-8")

        conn = sqlite3.connect(str(src_db))
        conn.execute("CREATE TABLE words (id INTEGER PRIMARY KEY, de TEXT, tr TEXT);")
        conn.execute("INSERT INTO words (de, tr) VALUES ('Apfel', 'Elma');")
        conn.commit()
        conn.close()

        copied = migrate_legacy_data(self.legacy_dir)

        self.assertIn("config.json", copied)
        self.assertIn("ekran_sozlugu.db", copied)

        dst_cfg = self.data_dir / "config.json"
        dst_db = self.data_dir / "ekran_sozlugu.db"

        self.assertTrue(dst_cfg.exists())
        self.assertTrue(dst_db.exists())
        self.assertEqual(dst_cfg.read_text(encoding="utf-8"), '{"theme": "light"}')

        # Hedef DB bütünlüğü ve verilerini doğrula
        dst_conn = sqlite3.connect(str(dst_db))
        check = dst_conn.execute("PRAGMA integrity_check;").fetchone()
        self.assertEqual(check, ("ok",))
        rows = dst_conn.execute("SELECT de, tr FROM words;").fetchall()
        self.assertEqual(rows, [("Apfel", "Elma")])
        dst_conn.close()

        # Kaynak dosyalar ASLA silinmemelidir
        self.assertTrue(src_cfg.exists())
        self.assertTrue(src_db.exists())
        src_conn = sqlite3.connect(str(src_db))
        self.assertEqual(src_conn.execute("SELECT de, tr FROM words;").fetchall(), [("Apfel", "Elma")])
        src_conn.close()

    def test_migrate_does_not_overwrite_and_does_not_delete_source(self):
        """Hedefte zaten dosya varsa ÜZERİNE YAZILMAZ ve kaynak silinmez."""
        src_cfg = self.legacy_dir / "config.json"
        src_db = self.legacy_dir / "ekran_sozlugu.db"
        src_cfg.write_text('{"theme": "old_legacy"}', encoding="utf-8")

        conn_src = sqlite3.connect(str(src_db))
        conn_src.execute("CREATE TABLE words (val TEXT);")
        conn_src.execute("INSERT INTO words (val) VALUES ('old_legacy_val');")
        conn_src.commit()
        conn_src.close()

        dst_cfg = self.data_dir / "config.json"
        dst_db = self.data_dir / "ekran_sozlugu.db"
        dst_cfg.write_text('{"theme": "new_target"}', encoding="utf-8")

        conn_dst = sqlite3.connect(str(dst_db))
        conn_dst.execute("CREATE TABLE words (val TEXT);")
        conn_dst.execute("INSERT INTO words (val) VALUES ('new_target_val');")
        conn_dst.commit()
        conn_dst.close()

        copied = migrate_legacy_data(self.legacy_dir)

        # Hiçbir dosya kopyalanmamalıdır
        self.assertEqual(copied, [])
        # Hedefteki mevcut veriler korunmalıdır
        self.assertEqual(dst_cfg.read_text(encoding="utf-8"), '{"theme": "new_target"}')
        conn_dst2 = sqlite3.connect(str(dst_db))
        self.assertEqual(conn_dst2.execute("SELECT val FROM words;").fetchall(), [("new_target_val",)])
        conn_dst2.close()
        # Kaynak dosyalar silinmemiş olmalıdır
        self.assertTrue(src_cfg.exists())
        self.assertTrue(src_db.exists())
        conn_src2 = sqlite3.connect(str(src_db))
        self.assertEqual(conn_src2.execute("SELECT val FROM words;").fetchall(), [("old_legacy_val",)])
        conn_src2.close()

    def test_migrate_sqlite_wal_uncheckpointed_data(self):
        """WAL modunda açık ve checkpoint edilmemiş kayıtlar içeren SQLite DB eksiksiz ve bütünlüklü göç etmelidir."""
        src_db = self.legacy_dir / "ekran_sozlugu.db"
        conn_src = sqlite3.connect(str(src_db))
        conn_src.execute("PRAGMA journal_mode=WAL;")
        conn_src.execute("CREATE TABLE words (id INTEGER PRIMARY KEY, de TEXT, tr TEXT);")
        conn_src.execute("INSERT INTO words (de, tr) VALUES ('Haus', 'Ev');")
        conn_src.commit()

        # Checkpoint edilmemiş açık WAL kaydı ekle
        conn_src.execute("INSERT INTO words (de, tr) VALUES ('Baum', 'Ağaç');")
        conn_src.commit()

        # WAL dosyasının oluştuğunu ve sıfırdan büyük olduğunu doğrula
        src_wal = Path(f"{src_db}-wal")
        self.assertTrue(src_wal.exists())
        self.assertGreater(src_wal.stat().st_size, 0)

        try:
            copied = migrate_legacy_data(self.legacy_dir)

            # Yalnızca ekran_sozlugu.db raporlanmalıdır; -wal ve -shm ham kopyalanmaz
            self.assertIn("ekran_sozlugu.db", copied)
            self.assertNotIn("ekran_sozlugu.db-wal", copied)
            self.assertNotIn("ekran_sozlugu.db-shm", copied)

            dst_db = self.data_dir / "ekran_sozlugu.db"
            self.assertTrue(dst_db.exists())
            # Hedefe ham wal veya shm kopyalanmamış olmalıdır
            self.assertFalse((self.data_dir / "ekran_sozlugu.db-wal").exists())
            self.assertFalse((self.data_dir / "ekran_sozlugu.db-shm").exists())

            # Hedef DB bütünlüğü doğrulanmalıdır
            dst_conn = sqlite3.connect(str(dst_db))
            check = dst_conn.execute("PRAGMA integrity_check;").fetchone()
            self.assertEqual(check, ("ok",))

            # Hem ana sayfadaki hem de WAL içindeki checkpoint edilmemiş tüm kayıtlar hedefe geçmiş olmalıdır
            rows = dst_conn.execute("SELECT de, tr FROM words ORDER BY id;").fetchall()
            self.assertEqual(rows, [("Haus", "Ev"), ("Baum", "Ağaç")])
            dst_conn.close()
        finally:
            conn_src.close()

    def test_migrate_idempotent(self):
        """İkinci kez migrate_legacy_data çağrıldığında hiçbir şey kopyalamamalıdır."""
        src_cfg = self.legacy_dir / "config.json"
        src_cfg.write_text('{"theme": "dark"}', encoding="utf-8")

        first_run = migrate_legacy_data(self.legacy_dir)
        self.assertEqual(first_run, ["config.json"])

        second_run = migrate_legacy_data(self.legacy_dir)
        self.assertEqual(second_run, [])

    def test_migrate_missing_source_no_error(self):
        """Kaynak klasör veya dosyalar yoksa hata fırlatmamalı ve boş liste dönmelidir."""
        non_existent = Path(self.temp_test_dir) / "does_not_exist"
        result = migrate_legacy_data(non_existent)
        self.assertEqual(result, [])

        empty_dir = Path(self.temp_test_dir) / "empty_dir"
        empty_dir.mkdir(parents=True, exist_ok=True)
        result_empty = migrate_legacy_data(empty_dir)
        self.assertEqual(result_empty, [])

    def test_migrate_same_source_and_target_noop(self):
        """Kaynak ve hedef dizin aynıysa işlem yapılmamalıdır."""
        result = migrate_legacy_data(self.data_dir)
        self.assertEqual(result, [])

    def test_config_and_database_paths_derived_from_paths(self):
        """config.py ve database.py dosya yollarının app/paths.py üzerinden türetildiğini doğrular."""
        importlib.reload(app.config)
        importlib.reload(app.database)

        self.assertEqual(app.config.CONFIG_FILE.name, "config.json")
        self.assertEqual(app.database.DB_PATH.name, "ekran_sozlugu.db")

        self.assertEqual(app.config.CONFIG_FILE, get_config_path())
        self.assertEqual(app.database.DB_PATH, get_db_path())
        self.assertEqual(app.config.CONFIG_FILE.parent, self.data_dir.resolve())
        self.assertEqual(app.database.DB_PATH.parent, self.data_dir.resolve())

    def test_migrate_does_not_copy_wal_when_db_already_exists_in_target(self):
        """Hedefte zaten ekran_sozlugu.db varsa, kaynaktaki -wal ve -shm dosyaları kopyalanmamalıdır."""
        src_db = self.legacy_dir / "ekran_sozlugu.db"
        src_conn = sqlite3.connect(str(src_db))
        src_conn.execute("PRAGMA journal_mode=WAL;")
        src_conn.execute("CREATE TABLE t (val TEXT);")
        src_conn.execute("INSERT INTO t VALUES ('old');")
        src_conn.commit()
        src_conn.close()

        src_wal = self.legacy_dir / "ekran_sozlugu.db-wal"
        src_shm = self.legacy_dir / "ekran_sozlugu.db-shm"

        dst_db = self.data_dir / "ekran_sozlugu.db"
        dst_conn = sqlite3.connect(str(dst_db))
        dst_conn.execute("CREATE TABLE t (val TEXT);")
        dst_conn.execute("INSERT INTO t VALUES ('existing_target');")
        dst_conn.commit()
        dst_conn.close()

        copied = migrate_legacy_data(self.legacy_dir)

        # db hedefte olduğu için ne db ne de wal/shm kopyalanmalıdır
        self.assertEqual(copied, [])
        self.assertFalse((self.data_dir / "ekran_sozlugu.db-wal").exists())
        self.assertFalse((self.data_dir / "ekran_sozlugu.db-shm").exists())

        dst_conn2 = sqlite3.connect(str(dst_db))
        rows = dst_conn2.execute("SELECT val FROM t;").fetchall()
        self.assertEqual(rows, [("existing_target",)])
        dst_conn2.close()

    def test_migrate_does_not_copy_orphan_wal_without_db(self):
        """Kaynaktan ekran_sozlugu.db yoksa yetim -wal veya -shm kopyalanmamalıdır."""
        src_wal = self.legacy_dir / "ekran_sozlugu.db-wal"
        src_wal.write_text("ORPHAN_WAL", encoding="utf-8")

        copied = migrate_legacy_data(self.legacy_dir)
        self.assertEqual(copied, [])
        self.assertFalse((self.data_dir / "ekran_sozlugu.db-wal").exists())

    def test_migrate_corrupted_sqlite_db_fails_safely(self):
        """Bozuk SQLite dosyasında göç güvenle başarısız olmalı; geçici veya hedef DB bırakmamalı, kaynağa dokunmamalıdır."""
        src_db = self.legacy_dir / "ekran_sozlugu.db"
        corrupt_bytes = b"CORRUPTED_NON_SQLITE_GARBAGE_PAYLOAD_12345"
        src_db.write_bytes(corrupt_bytes)

        copied = migrate_legacy_data(self.legacy_dir)

        # ekran_sozlugu.db kopyalanmamış olmalı
        self.assertNotIn("ekran_sozlugu.db", copied)

        dst_db = self.data_dir / "ekran_sozlugu.db"
        self.assertFalse(dst_db.exists())

        # Hedef dizinde hiçbir .tmp dosyası kalmamış olmalı
        tmp_files = list(self.data_dir.glob("*.tmp*"))
        self.assertEqual(tmp_files, [])

        # Kaynak dosya bozulmamış ve dokunulmamış olmalıdır
        self.assertTrue(src_db.exists())
        self.assertEqual(src_db.read_bytes(), corrupt_bytes)

    def test_migrate_malformed_sqlite_page_fails_safely(self):
        """B-tree veya sayfası bozuk SQLite dosyasında bütünlük kontrolü başarısız olmalı ve hedef oluşturulmamalıdır."""
        src_db = self.legacy_dir / "ekran_sozlugu.db"
        conn = sqlite3.connect(str(src_db))
        conn.execute("CREATE TABLE t (x text);")
        for i in range(100):
            conn.execute("INSERT INTO t VALUES (?)", (f"data_{i}",))
        conn.commit()
        conn.close()

        # Sayfa içeriğini boz
        data = bytearray(src_db.read_bytes())
        for i in range(100, len(data)):
            data[i] = data[i] ^ 0xAA
        src_db.write_bytes(bytes(data))

        copied = migrate_legacy_data(self.legacy_dir)
        self.assertNotIn("ekran_sozlugu.db", copied)
        self.assertFalse((self.data_dir / "ekran_sozlugu.db").exists())
        self.assertEqual(list(self.data_dir.glob("*.tmp*")), [])

    def test_migrate_db_install_error_cleans_up_tmp(self):
        """Kurulum hatası durumunda geçici dosya temizlenmeli ve hedef dosya oluşturulmamalıdır."""
        src_db = self.legacy_dir / "ekran_sozlugu.db"
        conn = sqlite3.connect(str(src_db))
        conn.execute("CREATE TABLE t (x text);")
        conn.execute("INSERT INTO t VALUES ('test');")
        conn.commit()
        conn.close()

        with patch("app.paths._atomic_install_exclusive", return_value=False):
            copied = migrate_legacy_data(self.legacy_dir)

        self.assertNotIn("ekran_sozlugu.db", copied)
        self.assertFalse((self.data_dir / "ekran_sozlugu.db").exists())
        self.assertEqual(list(self.data_dir.glob("*.tmp*")), [])

    def test_migrate_db_sentinel_created_before_install_race_condition(self):
        """Hedef DB son kurulum adımından hemen önce oluşsa bile ezilmemeli, kaynak ve hedef korunmalıdır."""
        src_db = self.legacy_dir / "ekran_sozlugu.db"
        conn_src = sqlite3.connect(str(src_db))
        conn_src.execute("CREATE TABLE words (val TEXT);")
        conn_src.execute("INSERT INTO words (val) VALUES ('src_value');")
        conn_src.commit()
        conn_src.close()

        dst_db = self.data_dir / "ekran_sozlugu.db"

        orig_install = app.paths._atomic_install_exclusive

        def hook_install(tmp, dst):
            if dst.resolve() == dst_db.resolve() or dst.name == "ekran_sozlugu.db":
                # Yarış durumunu simüle et: tam bu anda başka bir süreç/iş parçacığı hedefe sentinel yazdı!
                conn_sentinel = sqlite3.connect(str(dst_db))
                conn_sentinel.execute("CREATE TABLE sentinel (data TEXT);")
                conn_sentinel.execute("INSERT INTO sentinel VALUES ('sentinel_preserved_db');")
                conn_sentinel.commit()
                conn_sentinel.close()
            return orig_install(tmp, dst)

        with patch("app.paths._atomic_install_exclusive", side_effect=hook_install):
            copied = migrate_legacy_data(self.legacy_dir)

        # 1. Göç sonucu bu dosyanın başarıyla kopyalandığını söylememeli
        self.assertNotIn("ekran_sozlugu.db", copied)

        # 2. Sentinel içeriği aynen korunmalı
        conn_check = sqlite3.connect(str(dst_db))
        rows = conn_check.execute("SELECT data FROM sentinel;").fetchall()
        self.assertEqual(rows, [("sentinel_preserved_db",)])
        conn_check.close()

        # 3. Kaynak DB değişmemeli
        conn_src_check = sqlite3.connect(str(src_db))
        src_rows = conn_src_check.execute("SELECT val FROM words;").fetchall()
        self.assertEqual(src_rows, [("src_value",)])
        conn_src_check.close()

        # 4. Geçici dosya kalmamalı
        tmp_files = list(self.data_dir.glob("*.tmp*"))
        self.assertEqual(tmp_files, [])

    def test_migrate_config_sentinel_created_before_install_race_condition(self):
        """Hedef config.json son kurulum adımından hemen önce oluşsa bile ezilmemeli, kaynak ve hedef korunmalıdır."""
        src_cfg = self.legacy_dir / "config.json"
        src_cfg.write_text('{"theme": "src_legacy"}', encoding="utf-8")

        dst_cfg = self.data_dir / "config.json"

        orig_install = app.paths._atomic_install_exclusive

        def hook_install(tmp, dst):
            if dst.resolve() == dst_cfg.resolve() or dst.name == "config.json":
                # Yarış durumunu simüle et: tam bu anda başka bir süreç hedefe sentinel config yazdı!
                dst_cfg.write_text('{"theme": "sentinel_preserved"}', encoding="utf-8")
            return orig_install(tmp, dst)

        with patch("app.paths._atomic_install_exclusive", side_effect=hook_install):
            copied = migrate_legacy_data(self.legacy_dir)

        # 1. Göç sonucu bu dosyanın başarıyla kopyalandığını söylememeli
        self.assertNotIn("config.json", copied)

        # 2. Sentinel içeriği aynen korunmalı
        self.assertEqual(dst_cfg.read_text(encoding="utf-8"), '{"theme": "sentinel_preserved"}')

        # 3. Kaynak değişmemeli
        self.assertEqual(src_cfg.read_text(encoding="utf-8"), '{"theme": "src_legacy"}')

        # 4. Geçici dosya kalmamalı
        tmp_files = list(self.data_dir.glob("*.tmp*"))
        self.assertEqual(tmp_files, [])

    def test_migrate_concurrent_calls_do_not_corrupt_or_overwrite(self):
        """Eşzamanlı iki göç çağrısında hedefin ezilmediğini, bozulmadığını ve geçici dosya kalmadığını doğrular."""
        import concurrent.futures

        src_cfg = self.legacy_dir / "config.json"
        src_cfg.write_text('{"concurrent": "test"}', encoding="utf-8")

        src_db = self.legacy_dir / "ekran_sozlugu.db"
        conn_src = sqlite3.connect(str(src_db))
        conn_src.execute("CREATE TABLE t (id INT, txt TEXT);")
        for i in range(50):
            conn_src.execute("INSERT INTO t VALUES (?, ?);", (i, f"txt_{i}"))
        conn_src.commit()
        conn_src.close()

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(migrate_legacy_data, self.legacy_dir)
            f2 = executor.submit(migrate_legacy_data, self.legacy_dir)
            results.append(f1.result())
            results.append(f2.result())

        # İki çağrının toplamında config.json ve ekran_sozlugu.db en fazla bir kez kopyalanmış olmalı
        all_copied = results[0] + results[1]
        self.assertEqual(all_copied.count("config.json"), 1)
        self.assertEqual(all_copied.count("ekran_sozlugu.db"), 1)

        # Hedef DB sağlam ve bütünlüklü olmalı
        dst_db = self.data_dir / "ekran_sozlugu.db"
        self.assertTrue(dst_db.exists())
        dst_conn = sqlite3.connect(str(dst_db))
        self.assertEqual(dst_conn.execute("PRAGMA integrity_check;").fetchone(), ("ok",))
        count = dst_conn.execute("SELECT count(*) FROM t;").fetchone()[0]
        self.assertEqual(count, 50)
        dst_conn.close()

        # Hedef config sağlam olmalı
        dst_cfg = self.data_dir / "config.json"
        self.assertTrue(dst_cfg.exists())
        self.assertEqual(dst_cfg.read_text(encoding="utf-8"), '{"concurrent": "test"}')

        # Kaynak dosyalar korunmalı
        self.assertTrue(src_cfg.exists())
        self.assertTrue(src_db.exists())

        # Geçici dosya kalmamalı
        tmp_files = list(self.data_dir.glob("*.tmp*"))
        self.assertEqual(tmp_files, [])

    def test_migrate_ro_connection_failure_does_not_fallback_to_writable(self):
        """Kaynak DB salt-okunur açılamazsa yazılabilir bağlantıya düşülmemeli, güvenle başarısız olunmalıdır."""
        src_db = self.legacy_dir / "ekran_sozlugu.db"
        conn_src = sqlite3.connect(str(src_db))
        conn_src.execute("CREATE TABLE t (val TEXT);")
        conn_src.execute("INSERT INTO t VALUES ('read_only_test');")
        conn_src.commit()
        conn_src.close()

        orig_connect = sqlite3.connect
        connect_calls = []

        def mocked_connect(*args, **kwargs):
            connect_calls.append((args, kwargs))
            # Eğer uri=True ile salt-okunur açılmaya çalışılıyorsa hata fırlat
            if kwargs.get("uri"):
                raise sqlite3.OperationalError("Simulated read-only open error")
            return orig_connect(*args, **kwargs)

        with patch("sqlite3.connect", side_effect=mocked_connect):
            copied = migrate_legacy_data(self.legacy_dir)

        self.assertNotIn("ekran_sozlugu.db", copied)
        self.assertFalse((self.data_dir / "ekran_sozlugu.db").exists())
        self.assertEqual(list(self.data_dir.glob("*.tmp*")), [])

        # Kaynak DB için uri=False (yazılabilir) bir bağlantı çağrısı YAPILMADIĞINI doğrula!
        writable_calls = [
            call for call in connect_calls
            if not call[1].get("uri") and str(src_db.resolve()) in str(call[0])
        ]
        self.assertEqual(writable_calls, [], "Kaynak DB için yazılabilir bağlantı açılmamalıdır!")

    def test_migrate_db_permission_error_reported_and_cleaned_up(self):
        """os.rename PermissionError verdiğinde hata sessiz kalmamalı, hedef oluşmamalı ve geçici dosya temizlenmelidir."""
        src_db = self.legacy_dir / "ekran_sozlugu.db"
        conn = sqlite3.connect(str(src_db))
        conn.execute("CREATE TABLE t (x text);")
        conn.execute("INSERT INTO t VALUES ('test');")
        conn.commit()
        conn.close()

        captured_output = io.StringIO()
        with patch("sys.stdout", captured_output), patch("os.rename", side_effect=PermissionError("[WinError 5] Erişim engellendi")):
            copied = migrate_legacy_data(self.legacy_dir)

        # 1. Hata sessiz kalmamalı (konsola/tanıya açık uyarı düşmeli)
        output_str = captured_output.getvalue()
        self.assertIn("[Ekran Sözlüğü UYARI]", output_str)
        self.assertIn("ekran_sozlugu.db", output_str)
        self.assertIn("Erişim engellendi", output_str)

        # 2. Göç sonucu kopyalandı olarak listelenmemeli
        self.assertNotIn("ekran_sozlugu.db", copied)

        # 3. Hedef oluşmamalı
        self.assertFalse((self.data_dir / "ekran_sozlugu.db").exists())

        # 4. Geçici dosya temizlenmeli
        self.assertEqual(list(self.data_dir.glob("*.tmp*")), [])

    def test_migrate_config_permission_error_reported_and_cleaned_up(self):
        """config.json göçünde os.rename PermissionError verdiğinde hata açıkça bildirilmeli ve temp temizlenmelidir."""
        src_cfg = self.legacy_dir / "config.json"
        src_cfg.write_text('{"theme": "dark"}', encoding="utf-8")

        captured_output = io.StringIO()
        with patch("sys.stdout", captured_output), patch("os.rename", side_effect=PermissionError("[WinError 5] Erişim engellendi")):
            copied = migrate_legacy_data(self.legacy_dir)

        # 1. Hata sessiz kalmamalı
        output_str = captured_output.getvalue()
        self.assertIn("[Ekran Sözlüğü UYARI]", output_str)
        self.assertIn("config.json", output_str)
        self.assertIn("Erişim engellendi", output_str)

        # 2. Listelenmemeli
        self.assertNotIn("config.json", copied)

        # 3. Hedef oluşmamalı
        self.assertFalse((self.data_dir / "config.json").exists())

        # 4. Geçici dosya temizlenmeli
        self.assertEqual(list(self.data_dir.glob("*.tmp*")), [])

    def test_atomic_install_exclusive_posix_unexpected_error_does_not_overwrite(self):
        """POSIX dalında beklenmeyen hardlink hatasında (PermissionError vb.) hedef ezilmemeli ve hata fırlatılmalıdır."""
        from app.paths import _atomic_install_exclusive

        tmp_file = self.data_dir / "temp_file.tmp"
        tmp_file.write_text("new_payload", encoding="utf-8")

        dst_file = self.data_dir / "target_file.dat"
        dst_file.write_text("sentinel_existing_payload", encoding="utf-8")

        with patch("sys.platform", "linux"), patch("os.link", side_effect=PermissionError("Permission denied on hard link")):
            # Beklenmeyen hata çağırana fırlatılmalıdır (yutulmamalıdır)
            with self.assertRaises(PermissionError):
                _atomic_install_exclusive(tmp_file, dst_file)

        # Hedef dosya asla ezilmemeli
        self.assertEqual(dst_file.read_text(encoding="utf-8"), "sentinel_existing_payload")
        # Temizlik
        tmp_file.unlink(missing_ok=True)
        dst_file.unlink(missing_ok=True)

    def test_migrate_never_overwrites_existing_target_even_if_checked(self):
        """Mevcut hedef dosya varsa asla üzerine yazılmamalıdır."""
        src_db = self.legacy_dir / "ekran_sozlugu.db"
        conn_src = sqlite3.connect(str(src_db))
        conn_src.execute("CREATE TABLE t (x text);")
        conn_src.execute("INSERT INTO t VALUES ('src');")
        conn_src.commit()
        conn_src.close()

        dst_db = self.data_dir / "ekran_sozlugu.db"
        conn_dst = sqlite3.connect(str(dst_db))
        conn_dst.execute("CREATE TABLE t (x text);")
        conn_dst.execute("INSERT INTO t VALUES ('dst');")
        conn_dst.commit()
        conn_dst.close()

        copied = migrate_legacy_data(self.legacy_dir)
        self.assertEqual(copied, [])

        conn_check = sqlite3.connect(str(dst_db))
        rows = conn_check.execute("SELECT x FROM t;").fetchall()
        self.assertEqual(rows, [("dst",)])
        conn_check.close()

    def test_probe_cleanup_guarantee(self):
        """get_data_dir writability testinde oluşturulan geçici probe dosyaları geride kalmamalıdır."""
        target_dir = Path(self.temp_test_dir) / "probe_check"
        os.environ["EKRAN_SOZLUGU_DATA_DIR"] = str(target_dir)

        resolved = get_data_dir(create=True)
        self.assertEqual(resolved, target_dir.resolve())

        # Dizin içinde .write_test_ ile başlayan dosya kalmamalı
        probes = list(target_dir.glob(".write_test_*"))
        self.assertEqual(probes, [])

    def test_paths_unwritable_fallback_updates_database_and_config(self):
        """Veri dizini yazılamadığında Database ve save_config çökmeksizin kod klasörüne dönmelidir."""
        unwritable_dir = Path(self.temp_test_dir) / "unwritable_full"
        os.environ["EKRAN_SOZLUGU_DATA_DIR"] = str(unwritable_dir)

        with patch.object(Path, "mkdir", side_effect=PermissionError("Yazma engellendi")):
            resolved_dir = get_data_dir(create=True)
            self.assertEqual(resolved_dir, CODE_DIR)
            self.assertEqual(get_config_path(), CODE_DIR / "config.json")
            self.assertEqual(get_db_path(), CODE_DIR / "ekran_sozlugu.db")

            # Database nesnesi çökmeden CODE_DIR altında başlatılabilmelidir
            with patch("sqlite3.connect") as mock_conn:
                db = app.database.Database()
                self.assertEqual(db.db_path, CODE_DIR / "ekran_sozlugu.db")

    def test_no_tests_import_in_paths_module(self):
        """app/paths.py üretim kodu tests paketini import etmemelidir."""
        paths_file = Path(app.paths.__file__)
        content = paths_file.read_text(encoding="utf-8")
        self.assertNotIn("import tests", content)


if __name__ == "__main__":
    unittest.main()
