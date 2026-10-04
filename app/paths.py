"""
Uygulama Veri Yolları ve Göç (Migration) Modülü

Kullanıcı verilerini (config.json, ekran_sozlugu.db, ekran_sozlugu_error.log)
kod klasöründen işletim sistemi standart kullanıcı veri dizinine (%APPDATA%\\EkranSozlugu)
yönlendirir ve eski kullanıcı verilerini otomatik olarak yedek korumalı şekilde taşır.
"""
import os
import shutil
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import List, Optional, Set

# Kod / Proje kök dizini (fallback)
CODE_DIR = Path(__file__).resolve().parent.parent

# Yazılamayan hedef dizinleri önbelleğe alarak gereksiz tekrarları ve tutarsızlıkları önler
_UNWRITABLE_TARGETS: Set[Path] = set()


def _reset_paths_state():
    """Birim testleri için iç durum önbelleğini sıfırlar."""
    _UNWRITABLE_TARGETS.clear()


def _atomic_install_exclusive(tmp_path: Path, dst_path: Path) -> bool:
    """
    tmp_path dosyasını dst_path konumuna atomik ve münhasır (exclusive) olarak kurar.
    Hedef dosya zaten varsa ASLA üzerine yazmaz ve False döner.
    Kurulum başarılı olursa True döner.
    PermissionError ve diğer beklenmeyen I/O hataları çağırana fırlatılır.
    """
    if not tmp_path.exists():
        raise FileNotFoundError(f"Kurulacak geçici dosya bulunamadı: {tmp_path}")

    if sys.platform == "win32":
        try:
            # Windows'ta os.rename hedef dosya zaten varsa FileExistsError ([WinError 183])
            # fırlatır; os.replace'in aksine mevcut hedefi asla üzerine yazmaz.
            os.rename(tmp_path, dst_path)
            return True
        except FileExistsError:
            return False
        except OSError as e:
            # WinError 183 (ERROR_ALREADY_EXISTS) veya 80 (ERROR_FILE_EXISTS)
            if getattr(e, "winerror", None) in (80, 183):
                return False
            # PermissionError ([WinError 5]), Disk full ([WinError 112]) vb. çağırana iletilir
            raise
    else:
        # POSIX sistemlerde atomik link + unlink yöntemi hedef varsa FileExistsError verir
        try:
            os.link(tmp_path, dst_path)
            tmp_path.unlink(missing_ok=True)
            return True
        except FileExistsError:
            return False
        except OSError as e:
            import errno
            if getattr(e, "errno", None) == errno.EEXIST:
                return False
            # Beklenmeyen hardlink hatalarında (PermissionError, ENOTSUP, vb.) yarış durumunda
            # hedefi ezme riski bulunan güvensiz bir fallback yapılmaz; hata fırlatılır.
            raise


def _is_writable(path: Path) -> bool:
    """Verilen dizinin oluşturulabilir ve yazılabilir olduğunu test eder."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".write_test_{os.getpid()}_{uuid.uuid4().hex}"
        try:
            probe.touch(exist_ok=True)
        finally:
            probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def get_data_dir(create: bool = True) -> Path:
    """
    Kullanıcı veri dizinini döndürür.

    Öncelik Sırası:
    1. EKRAN_SOZLUGU_DATA_DIR ortam değişkeni varsa o kullanılır.
    2. %APPDATA%\\EkranSozlugu (Windows varsayılanı).
    3. Path.home() / ".ekran_sozlugu" (APPDATA tanımlı değilse).

    create=True ise dizin oluşturulur (parents=True, exist_ok=True) ve yazılabilirlik doğrulanır.
    Yazılamıyorsa kod klasörüne geri düşülür (fallback) ve konsola/loga uyarı basılır.
    """
    env_dir = os.environ.get("EKRAN_SOZLUGU_DATA_DIR")

    if env_dir and env_dir.strip():
        target = Path(env_dir.strip()).resolve()
    else:
        appdata = os.environ.get("APPDATA")
        if appdata and appdata.strip():
            target = (Path(appdata.strip()) / "EkranSozlugu").resolve()
        else:
            target = (Path.home() / ".ekran_sozlugu").resolve()

    if target in _UNWRITABLE_TARGETS:
        return CODE_DIR

    if not create:
        return target

    if _is_writable(target):
        return target

    _UNWRITABLE_TARGETS.add(target)
    print(f"[Ekran Sözlüğü UYARI] Veri dizini ({target}) oluşturulamadı veya yazılamıyor. Kod klasörüne ({CODE_DIR}) geri düşülüyor.")
    return CODE_DIR


def get_config_path(create_dir: bool = False) -> Path:
    """Yapılandırma dosyası (config.json) yolunu döner."""
    return get_data_dir(create=create_dir) / "config.json"


def get_db_path(create_dir: bool = False) -> Path:
    """SQLite veritabanı (ekran_sozlugu.db) yolunu döner."""
    return get_data_dir(create=create_dir) / "ekran_sozlugu.db"


def get_log_path(create_dir: bool = False) -> Path:
    """Hata günlüğü (ekran_sozlugu_error.log) yolunu döner."""
    return get_data_dir(create=create_dir) / "ekran_sozlugu_error.log"


def migrate_legacy_data(legacy_dir: Optional[Path] = None) -> List[str]:
    """
    legacy_dir içindeki config.json ve ekran_sozlugu.db dosyalarını,
    HEDEFTE ZATEN YOKSA data dir'e KOPYALA / TAŞI (asla üzerine yazma, kaynak silinmez).

    SQLite veritabanı göçü:
    - Kaynak DB kesinlikle salt-okunur (mode=ro) olarak açılır (yazılabilir fallback YOK).
    - sqlite3.Connection.backup() ile eşzamanlı çakışmasız benzersiz geçici dosyaya aktarılır.
    - PRAGMA integrity_check ile doğrulanır.
    - Doğrulama başarılıysa _atomic_install_exclusive ile münhasır atomik kurulum yapılır
      (hedef son anda oluşmuşsa bile ASLA üzerine yazılmaz).
    - Hata veya bozuk DB durumunda ham dosya kopyalama fallback'i KULLANILMAZ;
      geçici dosya temizlenir, kaynak ve hedef korunur.
    - WAL/SHM dosyaları ham kopyalanmaz; backup() tüm veriyi tek dosyada konsolide eder.

    config.json göçü:
    - Benzersiz geçici dosyaya kopyalanıp _atomic_install_exclusive ile hedefe kurulur.

    Kopyalanan dosya adlarının listesini döndürür.
    Hata olursa uygulama çökmez; hata yakalanıp raporlanır.
    """
    copied: List[str] = []
    if legacy_dir is None:
        legacy_dir = CODE_DIR

    try:
        legacy_path = Path(legacy_dir).resolve()
        if not legacy_path.exists() or not legacy_path.is_dir():
            return copied

        target_dir = get_data_dir(create=True).resolve()
        if legacy_path == target_dir:
            # Kaynak ve hedef aynı ise kopyalama yapma
            return copied

        # 1. config.json göçü (benzersiz geçici dosya ve münhasır atomik kurulum)
        src_cfg = legacy_path / "config.json"
        dst_cfg = target_dir / "config.json"
        if src_cfg.is_file() and not dst_cfg.exists():
            unique_cfg = uuid.uuid4().hex
            tmp_cfg = target_dir / f"config.json.tmp_{os.getpid()}_{unique_cfg}"
            try:
                shutil.copy2(src_cfg, tmp_cfg)
                if _atomic_install_exclusive(tmp_cfg, dst_cfg):
                    copied.append("config.json")
                else:
                    tmp_cfg.unlink(missing_ok=True)
            except Exception as e:
                print(f"[Ekran Sözlüğü UYARI] 'config.json' göçü sırasında hata: {e}")
            finally:
                if tmp_cfg.exists():
                    try:
                        tmp_cfg.unlink(missing_ok=True)
                    except Exception:
                        pass

        # 2. SQLite veritabanı göçü (salt-okunur backup + integrity_check + münhasır atomik kurulum)
        # Kural: Hedefte zaten ekran_sozlugu.db varsa ÜZERİNE YAZMA
        src_db = legacy_path / "ekran_sozlugu.db"
        dst_db = target_dir / "ekran_sozlugu.db"

        if src_db.is_file() and not dst_db.exists():
            unique_db = uuid.uuid4().hex
            dst_tmp = target_dir / f"ekran_sozlugu.db.tmp_{os.getpid()}_{unique_db}"
            src_conn = None
            dst_conn = None
            try:
                # Kaynak veritabanı YALNIZCA salt-okunur (mode=ro) olarak açılmalıdır.
                # Kaynak dosyanın değişmesini önlemek için yazılabilir bağlantıya asla fallback yapılmaz!
                src_conn = sqlite3.connect(f"{src_db.resolve().as_uri()}?mode=ro", uri=True)

                dst_conn = sqlite3.connect(str(dst_tmp.resolve()))
                src_conn.backup(dst_conn)

                # Bütünlük kontrolü (PRAGMA integrity_check)
                cursor = dst_conn.cursor()
                cursor.execute("PRAGMA integrity_check;")
                check_result = cursor.fetchone()
                if not check_result or check_result[0] != "ok":
                    raise sqlite3.DatabaseError(f"Hedef veritabanı bütünlük doğrulaması başarısız: {check_result}")

                # Windows dosya kilitlemesini önlemek için kurulum öncesi bağlantıları kapat
                dst_conn.close()
                dst_conn = None
                src_conn.close()
                src_conn = None

                # Hedefe münhasır (exclusive) kurulum yap; hedef son anda oluştuysa asla ezme!
                if _atomic_install_exclusive(dst_tmp, dst_db):
                    copied.append("ekran_sozlugu.db")
                else:
                    dst_tmp.unlink(missing_ok=True)
            except Exception as e:
                print(f"[Ekran Sözlüğü UYARI] 'ekran_sozlugu.db' SQLite göçü sırasında hata: {e}")
                # Bozuk DB, salt-okunur açılamama veya hata durumunda ASLA ham dosya fallback'i yapılmaz!
            finally:
                if dst_conn is not None:
                    try:
                        dst_conn.close()
                    except Exception:
                        pass
                if src_conn is not None:
                    try:
                        src_conn.close()
                    except Exception:
                        pass
                if dst_tmp.exists():
                    try:
                        dst_tmp.unlink(missing_ok=True)
                    except Exception:
                        pass

    except Exception as e:
        print(f"[Ekran Sözlüğü UYARI] Veri göçü sırasında beklenmeyen hata: {e}")

    return copied
