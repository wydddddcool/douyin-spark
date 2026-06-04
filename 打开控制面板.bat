@echo off
chcp 65001 >nul
cd /d "%~dp0"

call .venv\Scripts\activate.bat
start "抖音续火花" cmd /k "python web\app.py"

timeout /t 3 >nul
start http://localhost:5001
