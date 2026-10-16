@echo off
chcp 65001 > nul
title THE SPIKE CROSS - Web Launcher
echo ========================================================
echo   THE SPIKE CROSS - 풀 모션 차세대 웹 런처 실행 중...
echo   (GSAP, Lenis, React Bits, Magic UI, shadcn/ui 탑재)
echo ========================================================
cd /d "%~dp0frontend"

start "" http://localhost:5173
npx vite --host
if errorlevel 1 pause
