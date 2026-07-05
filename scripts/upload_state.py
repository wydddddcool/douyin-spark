"""
upload_state.py — 把 Mac 本地的 state.json 上传到 ECS 容器

前置：先跑 mac_login.py 生成新的 state.json

用法：
    python3 scripts/upload_state.py
    # 默认上传到 ECS i-j6c5u32x6bwnbu2xcrje /root/deploy/douyin-spark/data/auth/state.json
    # 然后 docker exec cp 到 /app/auth/state.json

为什么走 ECS host 而不直接 docker cp？
- bind mount data/auth -> /app/auth，直接写 host 端就生效
- 写完可以立刻看到 /api/status 的 has_auth 变 true
"""
import os
import sys
import base64
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "auth" / "state.json"

ECS_INSTANCE_ID = os.environ.get("ECS_INSTANCE_ID", "i-j6c5u32x6bwnbu2xcrje")
ECS_REGION = os.environ.get("ECS_REGION", "cn-hongkong")
ECS_REMOTE_DIR = "/root/deploy/douyin-spark/data/auth"
ECS_REMOTE_FILE = f"{ECS_REMOTE_DIR}/state.json"

WEB_URL = os.environ.get("WEB_URL", "http://spark.whoisbot.online")


def main():
    if not STATE_PATH.exists():
        print(f"✗ state.json 不存在: {STATE_PATH}")
        print("  请先跑 python3 scripts/mac_login.py 生成 state.json")
        sys.exit(1)

    size = STATE_PATH.stat().st_size
    print(f"▶ 本地 state.json: {STATE_PATH} ({size} bytes)")

    # 检查阿里云 CLI
    aliyun = subprocess.run(["which", "aliyun"], capture_output=True, text=True)
    if aliyun.returncode != 0:
        print("✗ aliyun CLI 未安装")
        sys.exit(1)

    # 用 base64 + aliyun RunCommand 上传（绕过 scp/rsync）
    print(f"▶ 上传到 ECS {ECS_INSTANCE_ID} {ECS_REMOTE_FILE}")
    with open(STATE_PATH, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    cmd = (
        f"mkdir -p {ECS_REMOTE_DIR} && "
        f"echo '{b64}' | base64 -d > {ECS_REMOTE_FILE} && "
        f"echo 'uploaded' && "
        f"ls -la {ECS_REMOTE_FILE} && "
        f"docker exec douyin-spark ls -la /app/auth/state.json 2>&1"
    )

    result = subprocess.run(
        [
            "aliyun", "ecs", "RunCommand",
            "--RegionId", ECS_REGION,
            "--InstanceId.1", ECS_INSTANCE_ID,
            "--Type", "RunShellScript",
            "--CommandContent", cmd,
            "--Timeout", "60",
        ],
        capture_output=True, text=True,
    )

    # 提取 InvokeId 和 CommandId
    import re
    invoke_id = None
    command_id = None
    for line in (result.stdout + result.stderr).splitlines():
        m = re.search(r'"InvokeId":\s*"([^"]+)"', line)
        if m:
            invoke_id = m.group(1)
        m = re.search(r'"CommandId":\s*"([^"]+)"', line)
        if m:
            command_id = m.group(1)

    if not invoke_id:
        print("✗ 没拿到 InvokeId")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)

    print(f"  InvokeId: {invoke_id}")

    # 轮询结果
    print("▶ 等命令执行...")
    for i in range(20):
        result = subprocess.run(
            [
                "aliyun", "ecs", "DescribeInvocationResults",
                "--RegionId", ECS_REGION,
                "--InvokeId", invoke_id,
                "--CommandId", command_id,
            ],
            capture_output=True, text=True,
        )
        out = result.stdout
        if '"CommandId"' in out or '"Finished"' in out or "uploaded" in out:
            break
        import time
        time.sleep(2)

    # 解析最终输出
    try:
        data = json.loads = __import__("json").loads(out)
        from json import loads as jl
        data = jl(out)
        out_b64 = data["Invocation"]["InvocationResults"]["InvocationResult"][0]["Output"]
        final = base64.b64decode(out_b64).decode()
    except Exception as e:
        print(f"解析失败: {e}")
        print("raw:", out[:500])
        sys.exit(1)

    print("─── ECS 端输出 ───")
    print(final)
    print("──────────────────")

    if "uploaded" not in final:
        print("✗ 上传失败")
        sys.exit(1)

    # 重启容器让 web app 重新加载 state.json
    print("\n▶ 重启 ECS 容器让 web app 加载新 state.json")
    restart = subprocess.run(
        [
            "aliyun", "ecs", "RunCommand",
            "--RegionId", ECS_REGION,
            "--InstanceId.1", ECS_INSTANCE_ID,
            "--Type", "RunShellScript",
            "--CommandContent",
            "docker restart douyin-spark && sleep 5 && curl -sS http://localhost:5000/api/status",
            "--Timeout", "60",
        ],
        capture_output=True, text=True,
    )
    invoke_id = None
    command_id = None
    for line in (restart.stdout + restart.stderr).splitlines():
        m = re.search(r'"InvokeId":\s*"([^"]+)"', line)
        if m: invoke_id = m.group(1)
        m = re.search(r'"CommandId":\s*"([^"]+)"', line)
        if m: command_id = m.group(1)

    if not invoke_id:
        print("✗ 重启失败")
        print(restart.stdout)
        print(restart.stderr)
        sys.exit(1)

    import time
    time.sleep(15)

    result = subprocess.run(
        [
            "aliyun", "ecs", "DescribeInvocationResults",
            "--RegionId", ECS_REGION,
            "--InvokeId", invoke_id,
            "--CommandId", command_id,
        ],
        capture_output=True, text=True,
    )
    try:
        from json import loads as jl
        data = jl(result.stdout)
        out_b64 = data["Invocation"]["InvocationResults"]["InvocationResult"][0]["Output"]
        final = base64.b64decode(out_b64).decode()
        print("─── 重启后状态 ───")
        print(final)
        print("──────────────────")

        # 验证 has_auth
        if '"has_auth": true' in final or '"has_auth":true' in final:
            print("\n✅ 上传 + 加载成功！has_auth = true")
            print(f"\n刷新 {WEB_URL} → 跳过扫码直接进主页面")
            print("然后点 '从抖音拉取好友列表' 验证")
        else:
            print("\n⚠ has_auth 仍为 false — state.json 可能不被认作有效登录态")
            print("  可能原因：抖音服务器侧 session 已失效")
            print("  这种情况需要重新扫码，请确认 mac_login.py 扫码成功")
    except Exception as e:
        print(f"解析失败: {e}")
        print("raw:", result.stdout[:500])


if __name__ == "__main__":
    main()