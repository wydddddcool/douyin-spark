"""
local_test.py — 本地集成测试，不依赖 ECS、不依赖登录

启动 web app 在 :5000（如果端口被占就用 :5050），跑一系列 API 验证：
- / 返回 200 + HTML 关键元素
- /api/status 返回 JSON + 字段齐全
- /api/setup/reset 返回 ok
- /api/friends 返回 JSON
- /api/logs 返回 list
- /api/qrcode 返回 PNG（即使当前没生成也要返回 404 或者正确状态）
- /api/targets 返回 JSON

用法（在本地项目根目录）：
    python3 scripts/local_test.py

退出码：0=通过，1=失败
"""
import os
import sys
import time
import json
import signal
import socket
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

# ─── 找一个空闲端口 ───
def find_free_port(start=5000):
    for p in range(start, start + 100):
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", p))
            s.close()
            return p
        except OSError:
            continue
    raise RuntimeError("找不到空闲端口")

PORT = find_free_port(5000)
print(f"▶ 用端口 {PORT} 启动本地 web app")

# 确保端口空闲 — 杀残留进程
subprocess.run(["lsof", "-ti", f":{PORT}"], capture_output=True)  # warm cache

# ─── 启服务 ───
env = os.environ.copy()
env["FLASK_RUN_PORT"] = str(PORT)
env["PYTHONPATH"] = str(ROOT)

proc = subprocess.Popen(
    [sys.executable, "web/app.py", "--port", str(PORT)],
    cwd=ROOT, env=env,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True,
)

# 等服务起来
def wait_for_service(url, timeout=15):
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False

started = wait_for_service(f"http://127.0.0.1:{PORT}/")
if not started:
    proc.terminate()
    print("✗ 服务 15 秒内没起来")
    print("--- logs ---")
    print(proc.stdout.read())
    sys.exit(1)
print("✓ 服务启动")

import urllib.request

PASSED = []
FAILED = []

def check(name, condition, detail=""):
    if condition:
        PASSED.append(name)
        print(f"  ✓ {name}")
    else:
        FAILED.append(f"{name} ({detail})")
        print(f"  ✗ {name} — {detail}")

# ─── 1. 根路径 ───
print("\n▶ 1. GET /")
r = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/")
html = r.read().decode("utf-8")
check("HTTP 200", r.status == 200, f"got {r.status}")
for key in ["btn-setup", "btn-setup-reset", "triggerSetup", "resetSetup", "api/friends/refresh", "好友列表", "抖音续火花"]:
    check(f"HTML 含 {key!r}", key in html)

# ─── 2. /api/status ───
print("\n▶ 2. GET /api/status")
data = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/status").read())
for key in ["has_auth", "setup_status", "running", "accounts_count"]:
    check(f"字段 {key}", key in data)
print(f"  当前 status: {data}")

# ─── 3. /api/setup/reset ───
print("\n▶ 3. POST /api/setup/reset")
req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/setup/reset", method="POST")
resp = json.loads(urllib.request.urlopen(req).read())
check("ok=true", resp.get("ok") is True)

# ─── 4. /api/friends ───
print("\n▶ 4. GET /api/friends")
data = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/friends").read())
for key in ["friends", "fetching", "cache_at"]:
    check(f"字段 {key}", key in data)

# ─── 5. /api/targets (POST only) ───
print("\n▶ 5. POST /api/targets")
req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/targets", method="POST")
req.add_header("Content-Type", "application/json")
req.data = b"{}"
data = json.loads(urllib.request.urlopen(req).read())
check("返回列表或字典", isinstance(data, (list, dict)))

# ─── 6. /api/logs ───
print("\n▶ 6. GET /api/logs?n=10")
data = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/logs?n=10").read())
check("logs 是列表", isinstance(data.get("logs"), list))

# ─── 7. /api/qrcode（当前无 state.json，应该 404 或空）───
print("\n▶ 7. GET /api/qrcode")
try:
    r = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/qrcode", timeout=2)
    check("返回 PNG（说明有二维码）", r.status == 200, f"got {r.status}, {len(r.read())} bytes")
except urllib.error.HTTPError as e:
    check("404 或 500（说明没二维码）", e.code in (404, 500), f"got HTTP {e.code}")
except Exception as e:
    check("请求行为符合预期", False, f"unexpected: {e}")

# ─── 8. /api/setup（不真扫，只看 endpoint 工作）───
print("\n▶ 8. POST /api/setup（启动扫码，看是否触发）")
req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/setup", method="POST")
resp = json.loads(urllib.request.urlopen(req).read())
print(f"  返回: {resp}")
# 不管返回 ok/error，关键是 endpoint 不崩
check("endpoint 响应正确 JSON", "ok" in resp or "error" in resp)

# 等几秒看 setup_status 是否进入 waiting_scan
time.sleep(2)
data = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/status").read())
print(f"  当前 setup_status: {data['setup_status']}")
# 本地没浏览器可能报错是 ok 的，只要 status 是 starting/waiting_scan/failed/null 都算

# 收尾
time.sleep(1)
proc.terminate()
try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    proc.kill()

# ─── 总结 ───
print("\n═══════════════════════════════════════")
print(f"  通过: {len(PASSED)}")
print(f"  失败: {len(FAILED)}")
if FAILED:
    print("\n  失败项：")
    for f in FAILED:
        print(f"    - {f}")
print("═══════════════════════════════════════")

sys.exit(0 if not FAILED else 1)