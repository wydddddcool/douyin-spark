#!/bin/bash
set -e

PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"
PACK_NAME="douyin-spark-$(date +%Y%m%d)"
OUTPUT="$HOME/Desktop/${PACK_NAME}.zip"
WORK_DIR="/tmp/$PACK_NAME"

echo ""
echo "═══════════════════════════════════"
echo "  抖音续火花 — 打包"
echo "═══════════════════════════════════"

# 检查 settings.yaml（打包前确保存在）
if [ ! -f "$PROJ_DIR/config/settings.yaml" ]; then
  mkdir -p "$PROJ_DIR/config"
  cat > "$PROJ_DIR/config/settings.yaml" <<'YAML'
accounts:
- name: 我的主号
  state_file: auth/state.json
  targets: []
message:
  use_daily_style: true
runtime:
  headless: true
  log_level: INFO
  browser_timeout: 120000
  message_delay: 3.0
schedule:
  enabled: false
  time: "08:00"
  days: [1, 2, 3, 4, 5, 6, 7]
YAML
  echo "  ℹ️  创建了初始 config/settings.yaml"
fi

# 清理并准备临时目录
rm -rf "$WORK_DIR"
rsync -a --quiet \
  --exclude='.venv' \
  --exclude='logs' \
  --exclude='auth/state.json' \
  --exclude='auth/qrcode.png' \
  --exclude='auth/browser_data' \
  --exclude='auth/login_page_debug.*' \
  --exclude='auth/debug_*.png' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  --exclude='.claude' \
  --exclude='.git' \
  --exclude='*.zip' \
  "$PROJ_DIR/" "$WORK_DIR/"

# 确保必要目录存在（占位）
mkdir -p "$WORK_DIR/auth" "$WORK_DIR/logs"
touch "$WORK_DIR/auth/.gitkeep"
touch "$WORK_DIR/logs/.gitkeep"

# 打包
cd /tmp
rm -f "$OUTPUT"
zip -r "$OUTPUT" "$PACK_NAME" -q
rm -rf "$WORK_DIR"

SIZE=$(du -sh "$OUTPUT" | cut -f1)
echo ""
echo "  ✅ 打包完成！"
echo "  📦 $OUTPUT ($SIZE)"
echo ""
echo "  发给对方的操作："
echo "  1. 解压 zip"
echo "  2. 双击「双击安装.command」"
echo "  3. 扫码登录 + 添加好友 + 设置定时"
echo "═══════════════════════════════════"
echo ""
