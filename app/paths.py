"""
Uygulama Veri Yolları ve Göç (Migration) Modülü

Kullanıcı verilerini (config.json, ekran_sozlugu.db, ekran_sozlugu_error.log)
kod klasöründen işletim sistemi standart kullanıcı veri dizinine (%APPDATA%\\EkranSozlugu)
yönlendirir ve eski kullanıcı verilerini otomatik olarak yedek korumalı şekilde taşır.
"""
import os
import shutil
import sys
from pathlib import Path
from typing import List, Optional, Set

# Kod / Proje kök dizini (fallback)
CODE_DIR = Path(__file__).resolve().parent.parent

# Yazılamayan hedef dizinleri önbelleğe alarak gereksiz tekrarları ve tutarsızlıkları önler
_UNWRITABLE_TARGETS: Set[Path] = set()


def _reset_paths_state():
    """Birim testleri için iç durum önbelleğini sıfırlar."""
    _UNWRITABLE_TARGETS.clear()


def _is_writable(path: Path) -> bool:
    """Verilen dizinin oluşturulabilir ve yazılabilir olduğunu test eder."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".write_test_{os.getpid()}"
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
    HEDEFTE ZATEN YOKSA data dir'e KOPYALA (taşıma değil, silme YOK, asla üzerine yazma).
    SQLite -wal/-shm yan dosyaları varsa onları da kopyala.

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

        # 1. config.json göçü
        src_cfg = legacy_path / "config.json"
        dst_cfg = target_dir / "config.json"
        if src_cfg.is_file() and not dst_cfg.exists():
            try:
                shutil.copy2(src_cfg, dst_cfg)
                copied.append("config.json")
            except Exception as e:
                print(f"[Ekran Sözlüğü UYARI] 'config.json' kopyalanırken hata oluştu: {e}")

        # 2. SQLite veritabanı ve yan dosyaları (-wal, -shm) göçü
        # Kural: Hedefte zaten ekran_sozlugu.db varsa ÜZERİNE YAZMA ve yan dosyalarını da kopyalama
        src_db = legacy_path / "ekran_sozlugu.db"
        dst_db = target_dir / "ekran_sozlugu.db"

        if src_db.is_file() and not dst_db.exists():
            try:
                shutil.copy2(src_db, dst_db)
                copied.append("ekran_sozlugu.db")

                # Yan dosyalar (-wal ve -shm) yalnızca db kopyalandıysa ve hedefte yoksa kopyalanır
                for ext in ("-wal", "-shm"):
                    sidecar_name = f"ekran_sozlugu.db{ext}"
                    src_sidecar = legacy_path / sidecar_name
                    dst_sidecar = target_dir / sidecar_name
                    if src_sidecar.is_file() and not dst_sidecar.exists():
                        try:
                            shutil.copy2(src_sidecar, dst_sidecar)
                            copied.append(sidecar_name)
                        except Exception as e:
                            print(f"[Ekran Sözlüğü UYARI] '{sidecar_name}' kopyalanırken hata oluştu: {e}")
            except Exception as e:
                print(f"[Ekran Sözlüğü UYARI] 'ekran_sozlugu.db' kopyalanırken hata oluştu: {e}")

    except Exception as e:
        print(f"[Ekran Sözlüğü UYARI] Veri göçü sırasında beklenmeyen hata: {e}")

    return copied
