#!/bin/bash
# 抖音续火花 — 一键安装脚本（macOS）
set -e

PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.douyin-spark"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
VENV="$PROJ_DIR/.venv"
PYTHON_BIN=""

echo ""
echo "═══════════════════════════════════"
echo "  抖音续火花 — 安装程序"
echo "═══════════════════════════════════"
echo ""

# ── 0. 检查 Google Chrome ───────────────────────────────────
echo "▶ 检查 Google Chrome..."
CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [ ! -f "$CHROME_BIN" ] && ! command -v google-chrome &>/dev/null; then
  echo ""
  echo "  ❌ 未找到 Google Chrome，需要先安装："
  echo "     https://www.google.com/chrome/"
  echo ""
  echo "  （扫码登录必须通过系统 Chrome 完成，安装后重新运行此脚本）"
  echo ""
  exit 1
fi
echo "  ✅ 已找到 Google Chrome"
echo ""

# ── 1. 检查 Python ──────────────────────────────────────────
echo "▶ 检查 Python 版本..."

for cmd in python3.12 python3.11 python3.10 python3.9 python3; do
  if command -v "$cmd" &>/dev/null; then
    VER="$($cmd --version 2>&1 | awk '{print $2}')"
    MAJOR="$(echo "$VER" | cut -d. -f1)"
    MINOR="$(echo "$VER" | cut -d. -f2)"
    if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 9 ]; then
      PYTHON_BIN="$(command -v "$cmd")"
      echo "  ✅ 找到 $PYTHON_BIN ($VER)"
      break
    fi
  fi
done

if [ -z "$PYTHON_BIN" ]; then
  echo ""
  echo "  ❌ 未找到 Python 3.9+，请先安装："
  echo "     https://www.python.org/downloads/"
  echo "     或通过 Homebrew: brew install python@3.11"
  echo ""
  exit 1
fi

# ── 2. 创建虚拟环境 ─────────────────────────────────────────
echo ""
echo "▶ 创建虚拟环境..."
if [ ! -d "$VENV" ]; then
  "$PYTHON_BIN" -m venv "$VENV"
  echo "  ✅ 已创建 .venv"
else
  echo "  ✅ 已存在 .venv，跳过"
fi

PIP="$VENV/bin/pip"
VENV_PYTHON="$VENV/bin/python"

# ── 3. 安装 Python 依赖 ─────────────────────────────────────
echo ""
echo "▶ 安装依赖..."
"$PIP" install --upgrade pip -q
"$PIP" install -r "$PROJ_DIR/requirements.txt" -q
echo "  ✅ 依赖安装完成"

# ── 4. 安装 Playwright 浏览器 ───────────────────────────────
echo ""
echo "▶ 安装 Playwright 浏览器（首次可能需要几分钟）..."
"$VENV_PYTHON" -m playwright install chromium
echo "  ✅ Playwright 浏览器安装完成"

# ── 5. 创建必要目录 ─────────────────────────────────────────
mkdir -p "$PROJ_DIR/auth"
mkdir -p "$PROJ_DIR/logs"
mkdir -p "$HOME/Library/LaunchAgents"

# ── 5b. 初始化配置文件 ───────────────────────────────────────
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
  echo "  ✅ 已创建初始配置文件（稍后在控制面板添加好友）"
fi

# ── 6. 写入 launchd plist（开机自启）────────────────────────
echo ""
echo "▶ 注册开机自启服务..."

PATH_FOR_PLIST="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$VENV/bin"

sed \
  -e "s|PLACEHOLDER_PYTHON|$VENV_PYTHON|g" \
  -e "s|PLACEHOLDER_APP|$PROJ_DIR/web/app.py|g" \
  -e "s|PLACEHOLDER_DIR|$PROJ_DIR|g" \
  -e "s|PLACEHOLDER_PATH|$PATH_FOR_PLIST|g" \
  "$PROJ_DIR/com.douyin-spark.plist" > "$PLIST_DST"

# 如果服务已在运行，先卸载再重新加载
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"
echo "  ✅ 服务已注册（开机自动启动）"

# ── 7. 等待服务启动 ─────────────────────────────────────────
echo ""
echo "▶ 正在启动 Web 服务..."
sleep 3

for i in 1 2 3 4 5; do
  if curl -sf http://127.0.0.1:5001/api/status > /dev/null 2>&1; then
    echo "  ✅ Web 服务已启动"
    break
  fi
  sleep 2
done

# ── 完成 ────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════"
echo "  ✅ 安装完成！"
echo ""
echo "  打开浏览器访问控制面板："
echo "  👉 http://localhost:5001"
echo ""
echo "  接下来："
echo "  1. 点击「扫码登录」，用抖音 App 扫码"
echo "  2. 添加要续火花的好友昵称"
echo "  3. 设置每天自动运行时间"
echo "  4. 完成！之后重启电脑也会自动运行"
echo "═══════════════════════════════════"
echo ""

# 自动打开浏览器
open "http://localhost:5001" 2>/dev/null || true
