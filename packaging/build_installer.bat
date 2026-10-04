@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

title Ekran Sözlüğü • Paketleme ve Windows Installer Derleyici
cd /d "%~dp0.."

echo ========================================================
echo   📦 Ekran Sözlüğü - Windows Dağıtım Paketi Derleyici
echo ========================================================
echo.

:: 1. İkon Üret
echo [1/4] Çoklu çözünürlüklü uygulama ikonu üretiliyor...
python packaging/generate_icon.py
if !ERRORLEVEL! NEQ 0 (
    echo [HATA] İkon üretilemedi!
    pause
    exit /b 1
)

:: 2. PyInstaller ile Onedir Derleme
echo [2/4] PyInstaller ile bağımsız yürütülebilir paket derleniyor...
pyinstaller --noconfirm --clean packaging/ekran_sozlugu.spec
if !ERRORLEVEL! NEQ 0 (
    echo [HATA] PyInstaller derleme hatası!
    pause
    exit /b 1
)

:: 3. Inno Setup ile Installer Üret
echo [3/4] Inno Setup ile kurulum paketi derleniyor...
set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "!ISCC_PATH!" (
    set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
)
if not exist "!ISCC_PATH!" (
    set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
)

if exist "!ISCC_PATH!" (
    "!ISCC_PATH!" packaging/setup.iss
    if !ERRORLEVEL! NEQ 0 (
        echo [HATA] Inno Setup kurulum paketi derlenemedi!
        pause
        exit /b 1
    )
) else (
    echo [UYARI] Inno Setup (ISCC.exe) sistemde bulunamadı.
    echo Yalnızca 'dist\EkranSozlugu' bağımsız klasörü hazırlandı.
    echo Installer üretmek için https://jrsoftware.org/isdl.php adresinden Inno Setup kurun.
)

:: 4. Checksum Üret
echo [4/4] SHA-256 Sağlama toplamları hesaplanıyor...
powershell -Command "if (Test-Path 'dist\EkranSozlugu-Setup-*.exe') { Get-FileHash -Algorithm SHA256 dist\EkranSozlugu-Setup-*.exe | Select-Object -Property Hash, Path | Format-Table -AutoSize | Out-File -Encoding utf8 'dist\SHA256SUMS.txt'; Get-Content 'dist\SHA256SUMS.txt' }"

echo.
echo ========================================================
echo   ✅ Paketleme İşlemi Tamamlandı!
echo   Çıktı klasörü: dist\
echo ========================================================
echo.
pause
