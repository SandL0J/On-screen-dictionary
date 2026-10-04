"""
Ekran Sözlüğü (ScreenLingo - DeutschOverlay)
Almanca Öğrenenler İçin Akıllı Ekran ve Video Çeviri Asistanı

Giriş Noktası (Entry Point)
--startup bayrağı ile çalıştırıldığında pencere gizli başlar,
sistem tepsisinde simge gösterilir ve kısayol (Tab+Space) aktif olur.
"""
import sys
import os
import ctypes
import tkinter as tk
from pathlib import Path

# Proje dizinini sys.path'e ekle
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Windows DPI ve Türkçe karakter desteği
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from app.paths import get_log_path, get_config_path, get_db_path, migrate_legacy_data

def setup_exception_logging():
    def excepthook(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        import traceback
        import datetime
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        err_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        try:
            enc = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
            msg = str(exc_value).encode(enc, errors="replace").decode(enc)
            print(f"[Ekran Sözlüğü Hatası]: {msg}")
        except Exception:
            pass
        try:
            log_file = get_log_path()
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n[{now_str}] UNCAUGHT EXCEPTION:\n{err_str}\n" + "-"*50 + "\n")
        except Exception:
            pass
    sys.excepthook = excepthook

setup_exception_logging()

import app.config
import app.database
from app.config import load_config, save_config
from app.database import Database
from app.tts_engine import GermanTTSEngine
from app.ocr_engine import OCREngine
from app.translator import TranslationEngine
from app.clipboard_watcher import ClipboardWatcher
from app.gui.main_overlay import MainOverlay
from app.tray_manager import TrayManager
from app.startup_manager import is_startup_enabled


_SINGLE_INSTANCE_MUTEX = None


def _setup_win32_api():
    """Win32 API fonksiyonlarının argtypes ve restype değerlerini HANDLE türleriyle tanımlar."""
    if sys.platform != "win32":
        return None, None
    try:
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.GetLastError.argtypes = []
        kernel32.GetLastError.restype = wintypes.DWORD
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        user32 = ctypes.windll.user32
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.FindWindowW.restype = wintypes.HWND
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.ShowWindow.restype = wintypes.BOOL
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.SetForegroundWindow.restype = wintypes.BOOL
        return kernel32, user32
    except Exception as e:
        print(f"[SingleInstance UYARI] Win32 API tipleri yüklenemedi: {e}")
        return None, None


def _acquire_single_instance_mutex(mutex_name: str = "EkranSozlugu_SingleInstance_Mutex_Global") -> bool:
    """
    Windows üzerinde uygulamanın tek bir örneğinin çalışmasını garanti eder.
    Zaten çalışan bir örnek varsa False döner.
    """
    global _SINGLE_INSTANCE_MUTEX
    if sys.platform != "win32":
        return True

    kernel32, _ = _setup_win32_api()
    if not kernel32:
        return True

    try:
        handle = kernel32.CreateMutexW(None, False, mutex_name)
        if not handle:
            return True
        last_error = kernel32.GetLastError()
        if last_error == 183:  # ERROR_ALREADY_EXISTS
            kernel32.CloseHandle(handle)
            return False
        _SINGLE_INSTANCE_MUTEX = handle
        return True
    except Exception as e:
        print(f"[SingleInstance UYARI] Mutex denetimi yapılamadı: {e}")
        return True


def _release_single_instance_mutex():
    """Kapanışta mutex tutamacını güvenle serbest bırakır."""
    global _SINGLE_INSTANCE_MUTEX
    if _SINGLE_INSTANCE_MUTEX and sys.platform == "win32":
        try:
            kernel32, _ = _setup_win32_api()
            if kernel32:
                kernel32.CloseHandle(_SINGLE_INSTANCE_MUTEX)
        except Exception:
            pass
        finally:
            _SINGLE_INSTANCE_MUTEX = None


def _restore_existing_window() -> bool:
    """Çalışmakta olan mevcut ana pencereyi bulup öne getirir."""
    if sys.platform != "win32":
        return False
    _, user32 = _setup_win32_api()
    if not user32:
        return False
    try:
        hwnd = user32.FindWindowW(None, "Ekran Sözlüğü • Almanca Asistanı")
        if hwnd:
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE = 9
            user32.SetForegroundWindow(hwnd)
            return True
    except Exception:
        pass
    return False


def perform_application_shutdown(
    overlay,
    tray=None,
    clipboard_watcher=None,
    db=None,
    mutex_release_fn=None,
    exit_fn=sys.exit,
    pool_timeout: float = 1.5,
    pool_grace: float = 2.0,
    db_timeout: float = 3.0,
    db_grace: float = 2.0
) -> int:
    """
    Uygulamanın tüm bileşenlerini (dinleyiciler, overlay, worker havuzu, veritabanı, GUI)
    güvenli ve sonlu zaman aşımı sözleşmesine uygun şekilde kapatır.
    Kapanış temiz tamamlandıysa 0, zaman aşımı veya açık DB işlemi kaldıysa 1 döner.
    """
    # 1. Giriş dinleyicilerini durdur
    if clipboard_watcher:
        try:
            clipboard_watcher.stop()
        except Exception:
            pass
    if hasattr(overlay, "hover_tracker") and overlay.hover_tracker:
        try:
            overlay.hover_tracker.stop()
        except Exception:
            pass
    if hasattr(overlay, "hotkey_mgr") and overlay.hotkey_mgr:
        try:
            overlay.hotkey_mgr.stop()
        except Exception:
            pass

    # 2. Overlay'i durdur (yeni görev kabulü durur, kuyruk boşaltılır, zamanlayıcılar iptal edilir)
    if overlay:
        try:
            overlay.stop()
        except Exception:
            pass
    if tray:
        try:
            tray.stop()
        except Exception:
            pass

    # 3. Worker havuzundaki aktif çalışan görevlerin tamamlanmasını sonlu bir süre bekle
    pool_ok = True
    if hasattr(overlay, "_worker_pool") and overlay._worker_pool:
        try:
            pool_ok = overlay._worker_pool.shutdown(wait=True, cancel_futures=True, timeout=pool_timeout)
            if not pool_ok and pool_grace > 0:
                print(f"[Ekran Sözlüğü Kapanış UYARI] Worker havuzundaki bazı görevler {pool_timeout}s içinde sonlanmadı; veri kaybını önlemek için ek süre bekleniyor...")
                pool_ok = overlay._worker_pool.wait(timeout=pool_grace)
            if not pool_ok:
                print("[Ekran Sözlüğü Kapanış KRİTİK] Worker havuzu kapanışı zaman aşımına uğradı; bazı görevler sonlanmadı.")
                try:
                    log_file = get_log_path()
                    log_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(log_file, "a", encoding="utf-8") as f:
                        import datetime
                        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        f.write(f"[{now_str}] CRITICAL SHUTDOWN: Worker pool tasks timed out after grace period.\n")
                except Exception:
                    pass
        except Exception as e:
            pool_ok = False
            print(f"[Ekran Sözlüğü Kapanış Hatası] Worker havuzu kapatma hatası: {e}")

    # 4. Veritabanını, ona yazabilecek tüm worker işleri bittikten sonra güvenle kapat ve checkpoint et
    db_closed_ok = False
    if db:
        try:
            db_closed_ok = db.close(timeout=db_timeout)
            if not db_closed_ok and db_grace > 0:
                print(f"[Ekran Sözlüğü Kapanış UYARI] Veritabanında aktif işlem sürüyor; {db_grace}s ek grace süresi bekleniyor...")
                db_closed_ok = db.close(timeout=db_grace)
                if not db_closed_ok:
                    print("[Ekran Sözlüğü Kapanış KRİTİK] Veritabanı kapanışı zaman aşımına uğradı; bazı işlemler tamamlanamadı.")
                    try:
                        log_file = get_log_path()
                        log_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(log_file, "a", encoding="utf-8") as f:
                            import datetime
                            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            f.write(f"[{now_str}] CRITICAL SHUTDOWN: Database operations timed out after grace period.\n")
                    except Exception:
                        pass
        except Exception as e:
            print(f"[Ekran Sözlüğü Kapanış Hatası] Veritabanı kapatma hatası: {e}")
    else:
        db_closed_ok = True

    # 5. Tkinter pencerelerini kapat ve kaynakları temizle
    if overlay:
        try:
            overlay.quit_completely()
        except Exception:
            pass

    # 6. Tekil uygulama mutex tutamacını serbest bırak
    if mutex_release_fn:
        try:
            mutex_release_fn()
        except Exception:
            pass

    # 7. Çıkış kodu: Ancak worker havuzu VE veritabanı güvenle kapandıysa 0, aksi halde 1
    clean_shutdown = bool(pool_ok and db_closed_ok)
    exit_code = 0 if clean_shutdown else 1
    if exit_fn:
        exit_fn(exit_code)
    return exit_code


def main():
    # 0a. Tek Uygulama Örneği (Single Instance Mutex) Kontrolü
    if not _acquire_single_instance_mutex():
        print("[Ekran Sözlüğü] Uygulama zaten çalışıyor. İkinci kopya sonlandırılıyor.")
        _restore_existing_window()
        sys.exit(0)

    # 0. Eski verileri taşı (Migration)
    migrated_files = migrate_legacy_data(BASE_DIR)
    if migrated_files:
        print(f"[Ekran Sözlüğü] Eski kullanıcı verileri yeni konuma kopyalandı: {', '.join(migrated_files)}")

    # Geri düşüş (fallback) durumunda modül yollarını güncelle
    app.config.CONFIG_FILE = get_config_path()
    app.database.DB_PATH = get_db_path()

    # --startup bayrağı: Windows ile otomatik açılışta gizli başla
    start_hidden = "--startup" in sys.argv

    if not start_hidden:
        print("=====================================================")
        print("  Ekran Sözlüğü • Almanca Asistanı Başlatılıyor...  ")
        print("=====================================================")

    # 1. Yapılandırma ve Veritabanı
    config = load_config()
    db = Database(history_limit=config.get("history_limit", 100))

    # 2. Motorlar
    tts_engine = GermanTTSEngine()
    ocr_engine = OCREngine(
        tesseract_cmd=config.get("tesseract_cmd", ""),
        preference=config.get("ocr_engine_preference", "auto")
    )
    translator = TranslationEngine(
        db=db,
        gemini_api_key=config.get("gemini_api_key", ""),
        use_gemini_direct=config.get("use_gemini_direct", False),
        gemini_model=config.get("gemini_model", "gemini-3.5-flash-lite")
    )

    # 3. Tkinter Kök Penceresi
    root = tk.Tk()

    # 4. Pano Dinleyicisi nesnesini oluştur (overlay sonrasında başlatılır)
    clipboard_watcher = ClipboardWatcher(on_text_detected=None)
    clipboard_watcher.set_enabled(config.get("clipboard_auto_lookup", False))

    # 5. Yüzen Ana Arayüz (Mini Bar)
    overlay = MainOverlay(
        root=root,
        translator=translator,
        tts_engine=tts_engine,
        ocr_engine=ocr_engine,
        db=db,
        clipboard_watcher=clipboard_watcher,
        config=config
    )

    # Pano geri çağrısını overlay.post_to_ui ile bağla ve başlat
    def on_clipboard_text(text: str):
        overlay.post_to_ui(overlay.lookup_text, text)

    clipboard_watcher.on_text_detected = on_clipboard_text
    clipboard_watcher.start()

    # 6. Temiz Çıkış İşleyicisi
    def on_quit():
        perform_application_shutdown(
            overlay=overlay,
            tray=tray,
            clipboard_watcher=clipboard_watcher,
            db=db,
            mutex_release_fn=_release_single_instance_mutex,
            exit_fn=sys.exit
        )

    # 7. Sistem Tepsisi (Tray)
    def show_bar():
        root.deiconify()
        root.attributes("-topmost", config.get("always_on_top", True))
        root.lift()
        overlay._is_bar_visible = True

    def hide_bar():
        root.withdraw()
        overlay._is_bar_visible = False

    def open_settings_from_tray():
        show_bar()
        overlay._open_settings()

    def open_wizard_from_tray():
        show_bar()
        overlay._open_onboarding_wizard()

    tray = TrayManager(
        on_show=show_bar,
        on_hide=hide_bar,
        on_open_settings=open_settings_from_tray,
        on_quit=on_quit,
        root=root,
        on_open_wizard=open_wizard_from_tray,
        post_to_ui=overlay.post_to_ui,
    )
    tray.start()

    # 8. Pencere kapatma butonunu tray'e gönder (X = tepsiye küçült)
    def on_window_close():
        hide_bar()

    root.protocol("WM_DELETE_WINDOW", on_window_close)

    # 9. --startup ile gizli başlatma
    if start_hidden:
        root.withdraw()
        overlay._is_bar_visible = False
    else:
        print("Uygulama hazır!")
        print(" • [Tab + Boşluk] : Anında Ekran Kırpma / OCR")
        print(" • [Alt+V]        : Canlı Fare Hover (Mouse-Over) Modu Aç / Kapat")
        print(" • [Alt+H]        : Çubuğu Gizle / Göster")
        print(" • [Alt+C]        : Pano metnini çevir")
        print(" • Sistem tepsisi simgesine sağ tıklayarak kontrol edebilirsiniz.")

    root.mainloop()


if __name__ == "__main__":
    main()
