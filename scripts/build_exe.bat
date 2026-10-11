@echo off
cd /d "%~dp0\.."
echo ========================================================
echo   The Spike Cross - PyInstaller EXE 빌드 시작
echo ========================================================
python -m PyInstaller --noconsole --onefile --clean --name "TheSpikeLauncher" --collect-all PyQt6 --hidden-import PyQt6.sip --hidden-import pkgutil src/main.py
if errorlevel 1 (
    echo [오류] 빌드에 실패했습니다.
    pause
    exit /b 1
)
echo ========================================================
echo   [성공] dist/TheSpikeLauncher.exe 빌드 완료!
echo ========================================================
pause
