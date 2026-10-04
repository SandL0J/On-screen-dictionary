# -*- mode: python ; coding: utf-8 -*-
"""
Ekran Sözlüğü (ScreenLingo) - PyInstaller Build Specification
Windows x64 için optimize edilmiş tek klasör (onedir) derleme konfigürasyonu.
"""
import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Proje kök dizini
PROJECT_DIR = Path(SPECPATH).resolve().parent

datas = [
    # İkon, konfigürasyon şablonu ve lisans bildirimleri
    (str(PROJECT_DIR / 'packaging' / 'app_icon.ico'), '.'),
    (str(PROJECT_DIR / 'config.example.json'), '.'),
    (str(PROJECT_DIR / 'LICENSE'), '.'),
    (str(PROJECT_DIR / 'packaging' / 'THIRD_PARTY_LICENSES.md'), '.'),
]

# Gizli importlar (Reflection, ctypes veya dinamik yüklenen modüller)
hiddenimports = [
    'tkinter',
    'tkinter.ttk',
    'tkinter.messagebox',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageTk',
    'PIL.ImageFilter',
    'PIL.ImageEnhance',
    'PIL.ImageOps',
    'pystray',
    'pystray._win32',
    'sqlite3',
    'requests',
    'urllib.request',
    'urllib.parse',
    'ctypes',
    'ctypes.wintypes',
    'json',
    're',
    'uuid',
    'shutil',
    'tempfile',
]

# Gereksiz kütüphanelerin pakete dahil edilmesini engelle (Boyut optimizasyonu)
excludes = [
    'matplotlib',
    'scipy',
    'pandas',
    'numpy',
    'torch',
    'tensorflow',
    'IPython',
    'jupyter',
    'pytest',
    'unittest',
    'unittest.mock',
]

a = Analysis(
    [str(PROJECT_DIR / 'main.py')],
    pathex=[str(PROJECT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='EkranSozlugu',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI uygulaması: Arka planda siyah konsol penceresi açılmaz
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJECT_DIR / 'packaging' / 'app_icon.ico'),
    manifest=str(PROJECT_DIR / 'packaging' / 'app.manifest'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='EkranSozlugu',
)
