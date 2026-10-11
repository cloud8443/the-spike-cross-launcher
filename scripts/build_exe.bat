@echo off
cd /d "%~dp0\.."
echo ========================================================
echo   The Spike Cross - PyInstaller EXE 빌드 시작
echo ========================================================
python -m PyInstaller --noconsole --onefile --name "TheSpikeLauncher" --add-data "%LOCALAPPDATA%\Python\pythoncore-3.14-64\Lib\site-packages\PyQt6\Qt6\plugins;PyQt6/Qt6/plugins" --add-data "%LOCALAPPDATA%\Python\pythoncore-3.14-64\Lib\site-packages\PyQt6\Qt6\bin;PyQt6/Qt6/bin" src/main.py
if errorlevel 1 (
    echo [오류] 빌드에 실패했습니다.
    pause
    exit /b 1
)
echo ========================================================
echo   [성공] dist/TheSpikeLauncher.exe 빌드 완료!
echo ========================================================
pause
