@echo off
chcp 65001 > nul
title Ekran Sozlugu - Almanca Asistani
cd /d "%~dp0"
echo ========================================================
echo   Ekran Sozlugu (Almanca Video ve Ekran Cevirmeni)
echo ========================================================
echo.
echo Uygulama baslatiliyor...

python "%~dp0main.py"
if %ERRORLEVEL% NEQ 0 (
    py "%~dp0main.py"
)
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Bir hata olustu! Python kurulu oldugundan emin olun.
    pause
)
