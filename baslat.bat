@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

title Ekran Sözlüğü • Almanca Ekran ve Video Asistanı
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

echo ========================================================
echo   🇩🇪 Ekran Sözlüğü (Almanca Video ve Ekran Asistanı)
echo ========================================================
echo.

:: 1. Virtualenv veya Sistem Python Yürütülebilirini Tespit Et
set "PY_CMD="

:: 1a. Mevcut bir .venv var mı kontrol et
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0.venv\Scripts\python.exe"
    echo [1/3] Sanal ortam (.venv) tespit edildi.
    goto :python_ready
)

:: 1b. Sistemde Python ara
python --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "SYS_PY=python"
    goto :create_venv
)

py -3 --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "SYS_PY=py -3"
    goto :create_venv
)

py --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "SYS_PY=py"
    goto :create_venv
)

echo [HATA] Bilgisayarınızda Python bulunamadı!
echo.
echo Lütfen https://www.python.org/downloads/ adresinden Python'ı indirip kurun.
echo Kurulum sırasında "Add Python to PATH" seçeneğini İŞARETLEMEYİ UNUTMAYIN.
echo.
pause
exit /b 1

:create_venv
echo [1/3] Python bulundu: !SYS_PY!
echo [*] İzole sanal ortam (.venv) yapılandırılıyor...
!SYS_PY! -m venv "%~dp0.venv" >nul 2>&1
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0.venv\Scripts\python.exe"
    echo [*] Sanal ortam başarıyla oluşturuldu.
) else (
    echo [!] Sanal ortam oluşturulamadı, doğrudan sistem Python'ı kullanılacak.
    set "PY_CMD=!SYS_PY!"
)

:python_ready
:: 2. Gerekli Bağımlılıkları Kontrol Et
echo [2/3] Kütüphaneler kontrol ediliyor...
"!PY_CMD!" -c "import PIL, requests, pystray" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo [*] Eksik kütüphaneler tespit edildi. Otomatik olarak kuruluyor...
    echo     (Pillow, requests, pystray)
    echo.
    "!PY_CMD!" -m pip install -r "%~dp0requirements.txt"
    if !ERRORLEVEL! NEQ 0 (
        echo.
        echo [UYARI] Bazı kütüphaneler kurulamadı. İnternet bağlantınızı kontrol edin.
        pause
    )
) else (
    echo [2/3] Tüm kütüphaneler hazır.
)

:: 3. Uygulamayı Başlat
echo [3/3] Ekran Sözlüğü başlatılıyor...
echo.
echo • [Tab + Boşluk] : Anında Ekran Kırpma / OCR
echo • [Alt + V]       : Canlı Fare Hover (Mouse-Over) Modu
echo • [Alt + H]       : Çubuğu Gizle / Göster
echo • [Alt + C]       : Panodaki Metni Çevir
echo.

"!PY_CMD!" "%~dp0main.py" %*

if !ERRORLEVEL! NEQ 0 (
    echo.
    echo [HATA] Uygulama beklenmeyen bir hata ile sonlandı.
    echo Hata ayrıntıları için varsa 'ekran_sozlugu_error.log' dosyasını inceleyin.
    echo.
    pause
)
