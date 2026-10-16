@echo off
cd /d "%~dp0\.."
echo ========================================================
echo   The Spike Cross - PyInstaller EXE 빌드 시작
echo ========================================================
python -m PyInstaller --noconsole --onefile --clean --name "TheSpikeLauncher" --collect-all PyQt6 --hidden-import PyQt6.sip --hidden-import pkgutil --add-data "config;config" --add-data "src/vgamepad;vgamepad" src/main.py
if errorlevel 1 (
    echo [오류] 빌드에 실패했습니다.
    pause
    exit /b 1
)

if exist dist\TheSpikeLauncher.exe (
    move /y dist\TheSpikeLauncher.exe TheSpikeLauncher.exe >nul
    rmdir /s /q dist 2>nul
    rmdir /s /q build 2>nul
    del /f /q TheSpikeLauncher.spec 2>nul
)

echo ========================================================
echo   [성공] 루트 TheSpikeLauncher.exe 빌드 완료!
echo ========================================================
pause
