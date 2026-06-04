@echo off
chcp 65001 >nul
echo.
echo ============================================
echo   抖音续火花 - Windows 构建脚本
echo ============================================
echo.

cd /d "%~dp0"

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python！
    echo.
    echo 请先安装 Python 3.9 或更高版本：
    echo   https://www.python.org/downloads/
    echo.
    echo 安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

echo [1/3] 安装依赖...
if exist "wheels\" (
    echo      从本地 wheels 目录离线安装...
    pip install --no-index --find-links=wheels\ pyinstaller playwright PyYAML flask apscheduler
) else (
    echo      从网络安装...
    pip install pyinstaller playwright PyYAML flask apscheduler
)
if %errorlevel% neq 0 goto error

echo.
echo [2/3] 清理旧构建...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

echo.
echo [3/3] 打包中（约 1-3 分钟）...
pyinstaller --clean douyin_spark.spec
if %errorlevel% neq 0 goto error

echo.
echo 打包为 ZIP...
if exist "dist\抖音续火花" (
    powershell -Command "Compress-Archive -Path 'dist\抖音续火花' -DestinationPath 'dist\抖音续火花-Windows.zip' -Force"
)

echo.
echo ============================================
echo   ✅ 构建完成！
echo.
echo   分发文件: dist\抖音续火花-Windows.zip
echo   解压后双击"抖音续火花.exe"即可运行
echo.
echo   用户需安装 Google Chrome 才能使用
echo ============================================
echo.
pause
goto end

:error
echo.
echo ❌ 构建失败！请截图上方错误信息
pause
exit /b 1

:end
