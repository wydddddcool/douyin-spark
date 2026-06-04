@echo off
chcp 65001 >nul
echo ═══════════════════════════════════════
echo   抖音续火花 — Windows 一键安装
echo ═══════════════════════════════════════
echo.

cd /d "%~dp0"

:CHECK_WINGET
echo [准备] 检查 winget 包管理器...
winget --version >nul 2>&1
if errorlevel 1 (
  echo.
  echo ⚠️  未检测到 winget（Windows 包管理器）
  echo.
  echo 你有两个选择：
  echo   1. 手动安装 Python 和 Chrome（推荐，最简单）
  echo   2. 先安装 winget（需要更新 Windows 应用商店）
  echo.
  echo 选择 1 继续手动安装，按 Ctrl+C 退出。
  echo.
  pause
  goto MANUAL_INSTALL
)
echo ✅ winget 可用
echo.

:CHECK_CHROME
echo [1/6] 检查 Google Chrome...
set CHROME_FOUND=0

:: 检查系统级安装（64位）
reg query "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" >nul 2>&1
if not errorlevel 1 (
  set CHROME_FOUND=1
)

:: 检查系统级安装（32位）
if %CHROME_FOUND%==0 (
  reg query "HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" >nul 2>&1
  if not errorlevel 1 (
    set CHROME_FOUND=1
  )
)

:: 检查用户级安装
if %CHROME_FOUND%==0 (
  if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" (
    set CHROME_FOUND=1
  )
)

:: 检查 Program Files
if %CHROME_FOUND%==0 (
  if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    set CHROME_FOUND=1
  )
)

:: 检查 Program Files (x86)
if %CHROME_FOUND%==0 (
  if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    set CHROME_FOUND=1
  )
)

if %CHROME_FOUND%==1 (
  echo ✅ Chrome 已安装
) else (
  echo ⚠️  未安装 Chrome，正在自动安装...
  winget install --id=Google.Chrome -e --accept-source-agreements --accept-package-agreements
  if errorlevel 1 (
    echo ❌ Chrome 安装失败，请手动下载安装：https://www.google.com/chrome/
    echo.
    pause
    exit /b 1
  )
  echo ✅ Chrome 安装完成
)
echo.

:CHECK_PYTHON
echo [2/6] 检查 Python...
python --version >nul 2>&1
if errorlevel 1 (
  echo ⚠️  未安装 Python，正在自动安装...
  winget install --id=Python.Python.3.11 -e --accept-source-agreements --accept-package-agreements
  if errorlevel 1 (
    echo ❌ Python 安装失败，请手动下载安装：https://www.python.org/downloads/
    echo    安装时请勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
  )
  echo ✅ Python 安装完成
  echo.
  echo ⚠️  需要刷新环境变量，请重新运行此脚本！
  echo.
  pause
  exit /b 0
)
echo ✅ Python 已安装
echo.

:INSTALL_APP
echo [3/6] 创建虚拟环境...
if not exist .venv (
  python -m venv .venv
)
echo ✅ 虚拟环境已创建

echo.
echo [4/6] 安装依赖...
call .venv\Scripts\activate.bat
pip install -r requirements.txt
echo ✅ 依赖已安装

echo.
echo [5/6] 安装 Playwright 浏览器...
playwright install chromium
echo ✅ 浏览器已安装

echo.
echo [6/6] 启动控制面板...
start "抖音续火花" cmd /k "call .venv\Scripts\activate.bat && python web\app.py"

timeout /t 3 >nul
start http://localhost:5001

echo.
echo ═══════════════════════════════════════
echo   ✅ 安装完成！
echo   浏览器已打开 http://localhost:5001
echo.
echo   下一步：
echo   1. 扫码登录
echo   2. 添加续火花好友
echo   3. 设置定时时间
echo.
echo   日常使用：双击「打开控制面板.bat」
echo ═══════════════════════════════════════
echo.
pause
exit /b 0

:MANUAL_INSTALL
echo.
echo ───────────────────────────────────────
echo   手动安装步骤
echo ───────────────────────────────────────
echo.
echo 1. 安装 Google Chrome
echo    下载地址：https://www.google.com/chrome/
echo.
echo 2. 安装 Python 3.9 或更高版本
echo    下载地址：https://www.python.org/downloads/
echo    ^ 重要：安装时请勾选 "Add Python to PATH"
echo.
echo 3. 安装完成后，重新运行此脚本
echo.
echo 或按任意键继续尝试用当前环境安装...
echo.
pause >nul
goto CHECK_PYTHON
