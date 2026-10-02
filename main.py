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
        if issubclass(exc_type, KeyboardInterrupt):
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


def main():
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
    db = Database()

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
        gemini_model=config.get("gemini_model", "gemini-1.5-flash")
    )

    # 3. Tkinter Kök Penceresi
    root = tk.Tk()

    # 4. Pano Dinleyicisi
    def on_clipboard_text(text: str):
        root.after(0, lambda: overlay.lookup_text(text))

    clipboard_watcher = ClipboardWatcher(on_text_detected=on_clipboard_text)
    if config.get("clipboard_auto_lookup", True):
        clipboard_watcher.start()

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

    # 6. Temiz Çıkış İşleyicisi
    def on_quit():
        clipboard_watcher.stop()
        tray.stop()
        overlay.quit_completely()
        import sys; sys.exit(0)

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
