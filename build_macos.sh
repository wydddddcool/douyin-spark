#!/bin/bash
# 构建 macOS 版抖音续火花
set -e

echo "=== 构建 macOS 版抖音续火花 ==="
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 优先使用本项目 venv 里的 pyinstaller，避免污染全局环境
if [ -x ".venv/bin/pyinstaller" ]; then
    PYI=".venv/bin/pyinstaller"
else
    echo ">>> .venv 缺失或没装 pyinstaller，请先："
    echo "    python3.11 -m venv .venv"
    echo "    .venv/bin/pip install -r requirements.txt pyinstaller"
    exit 1
fi

echo ">>> 清理旧构建..."
rm -rf build dist

echo ">>> 运行 PyInstaller..."
"$PYI" -y douyin_spark.spec

echo ""

APP="dist/抖音续火花.app"
DMG="dist/抖音续火花-macOS.dmg"

if [ -d "$APP" ]; then
    echo ">>> 创建带 Applications 快捷方式的 DMG..."

    STAGE="dist/dmg_stage"
    rm -rf "$STAGE"
    mkdir -p "$STAGE"

    # .app 拷进暂存目录 + 创建 /Applications 软链
    cp -R "$APP" "$STAGE/"
    ln -s /Applications "$STAGE/Applications"

    rm -f "$DMG"
    hdiutil create \
        -volname "抖音续火花" \
        -srcfolder "$STAGE" \
        -ov -format UDZO \
        "$DMG"

    rm -rf "$STAGE"

    echo ""
    echo "✅ 构建完成！"
    echo "   分发文件: $DMG"
    echo "   安装方法: 双击 DMG → 拖 .app 到 Applications → 双击运行"
elif [ -d "dist/抖音续火花" ]; then
    echo "✅ 构建完成！"
    echo "   分发目录: dist/抖音续火花/"
    echo "   运行方式: 双击 dist/抖音续火花/抖音续火花"
fi

echo ""
echo "注意：用户系统需安装 Google Chrome 才能正常使用"
