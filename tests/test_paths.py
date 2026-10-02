"""
Birim testleri: app/paths.py modülü ve kullanıcı veri yolları / veri göçü (migration).
"""
import importlib
import os
import shutil
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
        self.temp_test_dir = tempfile.mkdtemp(prefix="test_paths_suite_")
        self.data_dir = Path(self.temp_test_dir) / "data"
        self.legacy_dir = Path(self.temp_test_dir) / "legacy"
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
        src_db.write_text("DUMMY_SQLITE_CONTENT", encoding="utf-8")

        copied = migrate_legacy_data(self.legacy_dir)

        self.assertIn("config.json", copied)
        self.assertIn("ekran_sozlugu.db", copied)

        dst_cfg = self.data_dir / "config.json"
        dst_db = self.data_dir / "ekran_sozlugu.db"

        self.assertTrue(dst_cfg.exists())
        self.assertTrue(dst_db.exists())
        self.assertEqual(dst_cfg.read_text(encoding="utf-8"), '{"theme": "light"}')
        self.assertEqual(dst_db.read_text(encoding="utf-8"), "DUMMY_SQLITE_CONTENT")

        # Kaynak dosyalar ASLA silinmemelidir
        self.assertTrue(src_cfg.exists())
        self.assertTrue(src_db.exists())

    def test_migrate_does_not_overwrite_and_does_not_delete_source(self):
        """Hedefte zaten dosya varsa ÜZERİNE YAZILMAZ ve kaynak silinmez."""
        src_cfg = self.legacy_dir / "config.json"
        src_db = self.legacy_dir / "ekran_sozlugu.db"
        src_cfg.write_text('{"theme": "old_legacy"}', encoding="utf-8")
        src_db.write_text("OLD_LEGACY_DB", encoding="utf-8")

        dst_cfg = self.data_dir / "config.json"
        dst_db = self.data_dir / "ekran_sozlugu.db"
        dst_cfg.write_text('{"theme": "new_target"}', encoding="utf-8")
        dst_db.write_text("NEW_TARGET_DB", encoding="utf-8")

        copied = migrate_legacy_data(self.legacy_dir)

        # Hiçbir dosya kopyalanmamalıdır
        self.assertEqual(copied, [])
        # Hedefteki mevcut veriler korunmalıdır
        self.assertEqual(dst_cfg.read_text(encoding="utf-8"), '{"theme": "new_target"}')
        self.assertEqual(dst_db.read_text(encoding="utf-8"), "NEW_TARGET_DB")
        # Kaynak dosyalar silinmemiş olmalıdır
        self.assertTrue(src_cfg.exists())
        self.assertTrue(src_db.exists())

    def test_migrate_copies_sqlite_wal_and_shm(self):
        """SQLite -wal ve -shm yan dosyaları varsa kopyalanmalıdır."""
        src_db = self.legacy_dir / "ekran_sozlugu.db"
        src_wal = self.legacy_dir / "ekran_sozlugu.db-wal"
        src_shm = self.legacy_dir / "ekran_sozlugu.db-shm"

        src_db.write_text("MAIN_DB", encoding="utf-8")
        src_wal.write_text("WAL_DATA", encoding="utf-8")
        src_shm.write_text("SHM_DATA", encoding="utf-8")

        copied = migrate_legacy_data(self.legacy_dir)

        self.assertIn("ekran_sozlugu.db", copied)
        self.assertIn("ekran_sozlugu.db-wal", copied)
        self.assertIn("ekran_sozlugu.db-shm", copied)

        self.assertTrue((self.data_dir / "ekran_sozlugu.db-wal").exists())
        self.assertTrue((self.data_dir / "ekran_sozlugu.db-shm").exists())
        self.assertEqual((self.data_dir / "ekran_sozlugu.db-wal").read_text(encoding="utf-8"), "WAL_DATA")
        self.assertEqual((self.data_dir / "ekran_sozlugu.db-shm").read_text(encoding="utf-8"), "SHM_DATA")

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
        src_wal = self.legacy_dir / "ekran_sozlugu.db-wal"
        src_shm = self.legacy_dir / "ekran_sozlugu.db-shm"

        src_db.write_text("OLD_DB", encoding="utf-8")
        src_wal.write_text("OLD_WAL", encoding="utf-8")
        src_shm.write_text("OLD_SHM", encoding="utf-8")

        dst_db = self.data_dir / "ekran_sozlugu.db"
        dst_db.write_text("EXISTING_TARGET_DB", encoding="utf-8")

        copied = migrate_legacy_data(self.legacy_dir)

        # db hedefte olduğu için ne db ne de wal/shm kopyalanmalıdır
        self.assertEqual(copied, [])
        self.assertFalse((self.data_dir / "ekran_sozlugu.db-wal").exists())
        self.assertFalse((self.data_dir / "ekran_sozlugu.db-shm").exists())
        self.assertEqual(dst_db.read_text(encoding="utf-8"), "EXISTING_TARGET_DB")

    def test_migrate_does_not_copy_orphan_wal_without_db(self):
        """Kaynaktan ekran_sozlugu.db yoksa yetim -wal veya -shm kopyalanmamalıdır."""
        src_wal = self.legacy_dir / "ekran_sozlugu.db-wal"
        src_wal.write_text("ORPHAN_WAL", encoding="utf-8")

        copied = migrate_legacy_data(self.legacy_dir)
        self.assertEqual(copied, [])
        self.assertFalse((self.data_dir / "ekran_sozlugu.db-wal").exists())

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
