@echo off
chcp 65001 >nul
cd /d "%~dp0"

call .venv\Scripts\activate.bat
start "抖音续火花" cmd /k "python web\app.py"

timeout /t 3 >nul

REM 读取实际端口（launcher 写入），找不到就用 5001
set PORT=5001
if exist "auth\web_port.txt" (
  set /p PORT=<auth\web_port.txt
)

REM 兜底：探测端口
curl -sf "http://127.0.0.1:%PORT%/api/status" >nul 2>&1
if errorlevel 1 (
  for %%P in (5001 5002 5003 5004 5005) do (
    curl -sf "http://127.0.0.1:%%P/api/status" >nul 2>&1
    if not errorlevel 1 (
      set PORT=%%P
      goto :OPEN
    )
  )
)
:OPEN
start "http://localhost:%PORT%"
