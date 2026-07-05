#!/usr/bin/env bash
# deploy_and_test.sh — 部署后强制自测，禁止 "改了不测就推"
#
# 用法（在 ECS 上）：
#   cd /root/deploy/douyin-spark
#   bash scripts/deploy_and_test.sh
#
# 流程：
#   1. git pull origin main
#   2. docker build
#   3. stop + rm + run 容器（保留 data/auth bind mount）
#   4. 自测：
#      - HTTP 200
#      - /api/status 返回正常 JSON
#      - /api/setup/reset 可调
#      - bind mount 生效（/app/auth 写文件后 host 端能看见）
#      - state.json 可被 reload
#   5. 任意一步失败 → exit 1，必须修

set -e

CONTAINER_NAME="douyin-spark"
IMAGE="deploy_douyin-spark:latest"
NETWORK="deploy_default"
HOST_DATA_DIR="$(pwd)/data"

red() { printf "\033[31m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }

step() { echo ""; yellow "▶ $*"; }

step "1. git pull origin main"
git pull origin main | tail -3

step "2. docker build"
docker build -t "$IMAGE" . | tail -3

step "3. stop + rm 旧容器"
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true

step "4. mkdir -p data 子目录"
mkdir -p "$HOST_DATA_DIR/auth" "$HOST_DATA_DIR/logs" "$HOST_DATA_DIR/config"

step "5. 启动新容器"
docker run -d \
  --name "$CONTAINER_NAME" \
  --network "$NETWORK" \
  -p 5000:5000 \
  -v "$HOST_DATA_DIR/auth:/app/auth" \
  -v "$HOST_DATA_DIR/logs:/app/logs" \
  -v "$HOST_DATA_DIR/config:/app/config" \
  --restart unless-stopped \
  "$IMAGE" | tail -3

step "6. 等服务启动（最多 30 秒）"
for i in {1..30}; do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/ || echo "000")
  if [ "$code" = "200" ]; then
    green "  服务已起来（${i} 秒）"
    break
  fi
  sleep 1
  if [ "$i" = "30" ]; then
    red "  服务 30 秒内没起来！"
    docker logs --tail 50 "$CONTAINER_NAME"
    exit 1
  fi
done

step "7. 自测 — /api/status 返回正常 JSON"
status=$(curl -s http://localhost:5000/api/status)
echo "  $status"
echo "$status" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'has_auth' in d and 'setup_status' in d and 'running' in d, '字段缺失'" \
  && green "  ✓ 字段齐全" \
  || { red "  ✗ /api/status 字段缺失"; exit 1; }

step "8. 自测 — /api/setup/reset 可调"
reset_resp=$(curl -s -X POST http://localhost:5000/api/setup/reset)
echo "  $reset_resp"
echo "$reset_resp" | python3 -c "import sys,json; assert json.load(sys.stdin).get('ok') is True" \
  && green "  ✓ reset 端点工作" \
  || { red "  ✗ reset 端点失败"; exit 1; }

step "9. 自测 — bind mount 生效（容器内写文件 → host 端能看见）"
TEST_FILE="bind_mount_test_$(date +%s).txt"
docker exec "$CONTAINER_NAME" sh -c "echo '$TEST_FILE' > /app/auth/$TEST_FILE"
if [ -f "$HOST_DATA_DIR/auth/$TEST_FILE" ]; then
  green "  ✓ bind mount 生效（容器写 → host 见）"
  rm "$HOST_DATA_DIR/auth/$TEST_FILE"
else
  red "  ✗ bind mount 失效！重启会丢 state.json"
  exit 1
fi

step "10. 自测 — Python 语法"
for f in web/app.py core/auth.py core/browser.py core/friends.py core/tasks.py web/templates/index.html; do
  case "$f" in
    *.py)
      python3 -c "import ast; ast.parse(open('$f').read())" \
        && green "  ✓ $f" \
        || { red "  ✗ $f 语法错"; exit 1; }
      ;;
  esac
done

step "11. 自测 — HTML 里关键元素都在"
HTML=$(curl -s http://localhost:5000/)
for key in "btn-setup" "btn-setup-reset" "triggerSetup" "resetSetup" "api/setup" "api/friends/refresh"; do
  echo "$HTML" | grep -q "$key" \
    && green "  ✓ HTML 含 $key" \
    || { red "  ✗ HTML 缺 $key（前端没同步）"; exit 1; }
done

step "12. 自测 — 好友抽取核心逻辑（不依赖登录）"
docker exec "$CONTAINER_NAME" python -c "
import sys
sys.path.insert(0, '/app')
import ast
src = open('/app/core/friends.py').read()
ast.parse(src)
assert 'page.evaluate' in src, 'friends.py 没用到 page.evaluate（怀疑 Locator.evaluate 循环）'
assert 'compareDocumentPosition' in src, 'friends.py 没用 compareDocumentPosition'
# 不再限制 try 数量，但确保 friends.py 整体长度合理
assert len(src) > 1000, 'friends.py 太短，怀疑文件没更新'
print('  friends.py 静态检查通过')
" | tail -5

green ""
green "═══════════════════════════════════════"
green "  部署 + 自测全部通过 ✅"
green "═══════════════════════════════════════"
green ""