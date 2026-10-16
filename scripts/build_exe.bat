@echo off
cd /d "%~dp0\.."
if exist TheSpikeLauncher.exe del /f /q TheSpikeLauncher.exe
python -m PyInstaller --noconsole --onefile --clean --name "TheSpikeLauncher" --collect-all PyQt6 --hidden-import PyQt6.sip --hidden-import pkgutil --hidden-import win32gui --hidden-import win32ui --hidden-import win32con --hidden-import PIL --add-data "config;config" --add-data "src/vgamepad;vgamepad" src/main.py
if exist dist\TheSpikeLauncher.exe (
    copy /y dist\TheSpikeLauncher.exe TheSpikeLauncher.exe >nul
    rmdir /s /q dist 2>nul
    rmdir /s /q build 2>nul
    del /f /q TheSpikeLauncher.spec 2>nul
)
