@ECHO OFF
TITLE pause_zoffline

powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -Verb RunAs powershell -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File %cd%/unpause_zoffline.ps1'"

ECHO.

TASKKILL /F /IM ZwiftLauncher.exe >nul 2>&1

PAUSE