@echo off
cd /d "%~dp0\..\frontend"
start "" http://localhost:5173
npx vite --host
if errorlevel 1 pause
