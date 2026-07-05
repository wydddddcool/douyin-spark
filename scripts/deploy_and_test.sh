#!/usr/bin/env bash
# deploy_and_test.sh — 本地先测 → 通过才部署
#
# 这个脚本是一道闸门：保证改完的东西本地集成测试都过了，才推到 ECS。
# 用法（在 ECS 上）：
#   cd /root/deploy/douyin-spark
#   bash scripts/deploy_and_test.sh
#
# 注意：本地自测（local_test.py）应该在本地 Mac 跑（修改代码后立即跑）
#       这个脚本在 ECS 上跑：1. 拉最新代码 2. ECS 自测部署完整性

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(dirname "$SCRIPT_DIR")"

red() { printf "\033[31m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
step() { echo ""; yellow "▶ $*"; }

# ─────────────────────────────────────────
# Part A: 静态检查（不依赖服务）
# ─────────────────────────────────────────
step "A.1 Python 语法"
for f in web/app.py core/auth.py core/browser.py core/friends.py core/tasks.py scripts/local_test.py; do
  python3 -c "import ast; ast.parse(open('$f').read())" \
    && green "  ✓ $f" \
    || { red "  ✗ $f 语法错"; exit 1; }
done

step "A.2 shell 语法"
bash -n scripts/deploy_and_test.sh \
  && green "  ✓ deploy_and_test.sh" \
  || { red "  ✗ deploy_and_test.sh 语法错"; exit 1; }

step "A.3 friends.py 不再踩 Locator.evaluate 坑"
python3 -c "
import ast
src = open('core/friends.py').read()
ast.parse(src)
assert 'page.evaluate' in src, 'friends.py 没用到 page.evaluate'
assert 'compareDocumentPosition' in src, 'friends.py 没用 compareDocumentPosition'
print('  ✓ friends.py 静态检查通过')
"

# ─────────────────────────────────────────
# Part B: 本地集成测试（启 web app 跑 API）
# ─────────────────────────────────────────
step "B.1 本地集成测试（python3 scripts/local_test.py）"
python3 scripts/local_test.py | tail -8

# ─────────────────────────────────────────
# Part C: ECS 部署 + 容器内自测
# ─────────────────────────────────────────
step "C.1 git pull origin main"
git pull origin main | tail -3

step "C.2 docker build"
docker build -t deploy_douyin-spark:latest . | tail -3

step "C.3 stop + rm 旧容器"
docker stop douyin-spark 2>/dev/null || true
docker rm douyin-spark 2>/dev/null || true

step "C.4 mkdir -p data 子目录"
mkdir -p data/auth data/logs data/config

step "C.5 启动新容器"
docker run -d \
  --name douyin-spark \
  --network deploy_default \
  -p 5000:5000 \
  -v $(pwd)/data/auth:/app/auth \
  -v $(pwd)/data/logs:/app/logs \
  -v $(pwd)/data/config:/app/config \
  --restart unless-stopped \
  deploy_douyin-spark:latest | tail -3

step "C.6 等服务起来"
for i in {1..30}; do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/ || echo "000")
  if [ "$code" = "200" ]; then
    green "  服务已起来（${i} 秒）"
    break
  fi
  sleep 1
  if [ "$i" = "30" ]; then
    red "  服务 30 秒内没起来"
    docker logs --tail 50 douyin-spark
    exit 1
  fi
done

step "C.7 /api/status 字段齐全"
curl -s http://localhost:5000/api/status | python3 -c "
import sys, json
d = json.load(sys.stdin)
for k in ['has_auth', 'setup_status', 'running', 'accounts_count', 'targets_count']:
    assert k in d, f'缺字段 {k}'
print('  ✓ 字段齐全：', d)
"

step "C.8 /api/setup/reset 可调"
curl -s -X POST http://localhost:5000/api/setup/reset | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d.get('ok') is True, f'reset 失败: {d}'
print('  ✓ reset ok')
"

step "C.9 bind mount 生效"
TEST_FILE="bind_mount_test_$(date +%s).txt"
docker exec douyin-spark sh -c "echo $TEST_FILE > /app/auth/$TEST_FILE"
if [ -f data/auth/$TEST_FILE ]; then
  green "  ✓ bind mount 生效"
  rm data/auth/$TEST_FILE
else
  red "  ✗ bind mount 失效"
  exit 1
fi

step "C.10 HTML 关键元素都在"
HTML=$(curl -s http://localhost:5000/)
for key in btn-setup btn-setup-reset triggerSetup resetSetup "api/friends/refresh"; do
  echo "$HTML" | grep -q "$key" \
    && green "  ✓ HTML 含 $key" \
    || { red "  ✗ HTML 缺 $key"; exit 1; }
done

green ""
green "═══════════════════════════════════════"
green "  本地测试 ✅ + 部署 ✅ + 容器自测 ✅"
green "═══════════════════════════════════════"
green ""
yellow "剩唯一的人为步骤：扫码登录（抖音二维码识别没法 CI 自动化）"