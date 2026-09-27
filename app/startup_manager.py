"""
Windows Otomatik Başlatma (Startup) Yöneticisi
Uygulamayı Windows kayıt defterine (HKCU\\...\\Run) ekler veya kaldırır,
böylece bilgisayar her açıldığında uygulama kendiliğinden başlar.
"""
import winreg
import sys
import os
from pathlib import Path

STARTUP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "EkranSozlugu"


def _get_startup_command() -> str:
    """
    Kayıt defterine yazılacak başlatma komutunu döndürür.
    pythonw.exe kullanarak konsol penceresi açılmadan başlar.
    """
    python_exe = Path(sys.executable)
    # pythonw.exe varsa kullan (konsol penceresi açmaz)
    pythonw = python_exe.parent / "pythonw.exe"
    if not pythonw.exists():
        pythonw = python_exe  # fallback

    main_script = Path(__file__).resolve().parent.parent / "main.py"
    # Tırnak içinde, boşluklu yolları destekler
    return f'"{pythonw}" "{main_script}" --startup'


def is_startup_enabled() -> bool:
    """Uygulama Windows başlangıcına ekli mi?"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except (FileNotFoundError, OSError):
        return False


def enable_startup() -> bool:
    """Uygulamayı Windows başlangıcına ekler."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0,
            winreg.KEY_SET_VALUE | winreg.KEY_WRITE
        )
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _get_startup_command())
        winreg.CloseKey(key)
        print(f"Otomatik başlatma etkinleştirildi: {_get_startup_command()}")
        return True
    except OSError as e:
        print(f"Otomatik başlatma etkinleştirilemedi: {e}")
        return False


def disable_startup() -> bool:
    """Uygulamayı Windows başlangıcından kaldırır."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0,
            winreg.KEY_SET_VALUE | winreg.KEY_WRITE
        )
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
        print("Otomatik başlatma devre dışı bırakıldı.")
        return True
    except (FileNotFoundError, OSError):
        return True  # Zaten kayıtlı değilse sorun yok
