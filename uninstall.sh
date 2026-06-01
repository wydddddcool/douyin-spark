#!/bin/bash
# 抖音续火花 — 卸载脚本

PLIST_NAME="com.douyin-spark"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

echo ""
echo "═══════════════════════════════════"
echo "  抖音续火花 — 卸载程序"
echo "═══════════════════════════════════"
echo ""

# 停止并注销 launchd 服务
if [ -f "$PLIST_DST" ]; then
  echo "▶ 停止并注销服务..."
  launchctl unload "$PLIST_DST" 2>/dev/null || true
  rm -f "$PLIST_DST"
  echo "  ✅ 服务已停止并移除"
else
  echo "  ℹ️  服务未注册，跳过"
fi

echo ""
echo "═══════════════════════════════════"
echo "  ✅ 卸载完成"
echo "  （项目文件、配置和日志已保留）"
echo "  如需彻底删除，请手动移除整个项目目录"
echo "═══════════════════════════════════"
echo ""
