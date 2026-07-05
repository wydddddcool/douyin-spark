"""
upload_state.py — 把 Mac 本地的 state.json 上传到 ECS 容器（分片版）

通过 aliyun CLI 分片传 base64，避开 URL 长度限制（414 错误）。

用法：
    python3 scripts/upload_state.py
"""
import os
import sys
import base64
import subprocess
import json
import time
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "auth" / "state.json"

ECS_INSTANCE_ID = os.environ.get("ECS_INSTANCE_ID", "i-j6c5u32x6bwnbu2xcrje")
ECS_REGION = os.environ.get("ECS_REGION", "cn-hongkong")
ECS_REMOTE_FILE = "/root/deploy/douyin-spark/data/auth/state.json"
ECS_TMP_FILE = "/tmp/state_upload.b64"

WEB_URL = os.environ.get("WEB_URL", "http://spark.whoisbot.online")

CHUNK_SIZE = 6000  # 每片字符数，远小于阿里云 RunCommand 的限制


def run_remote(cmd: str, timeout: int = 60) -> str:
    """执行 ECS 远程命令并返回 stdout（base64 解码后）"""
    r = subprocess.run(
        [
            "aliyun", "ecs", "RunCommand",
            "--RegionId", ECS_REGION,
            "--InstanceId.1", ECS_INSTANCE_ID,
            "--Type", "RunShellScript",
            "--CommandContent", cmd,
            "--Timeout", str(timeout),
        ],
        capture_output=True, text=True,
    )
    invoke_id = None
    command_id = None
    for line in (r.stdout + r.stderr).splitlines():
        m = re.search(r'"InvokeId":\s*"([^"]+)"', line)
        if m: invoke_id = m.group(1)
        m = re.search(r'"CommandId":\s*"([^"]+)"', line)
        if m: command_id = m.group(1)
    if not invoke_id:
        print("✗ 没拿到 InvokeId")
        print(r.stdout)
        print(r.stderr)
        sys.exit(1)

    # 等结果
    for _ in range(40):
        time.sleep(2)
        r2 = subprocess.run(
            [
                "aliyun", "ecs", "DescribeInvocationResults",
                "--RegionId", ECS_REGION,
                "--InvokeId", invoke_id,
                "--CommandId", command_id,
            ],
            capture_output=True, text=True,
        )
        try:
            data = json.loads(r2.stdout)
            inv = data["Invocation"]["InvocationResults"]["InvocationResult"]
            if isinstance(inv, list) and inv:
                inv = inv[0]
            if "Output" in inv:
                return base64.b64decode(inv["Output"]).decode(errors="replace")
            if "Error" in inv or "InvokeRecord" in inv:
                # 没 Output 但有 record
                return ""
        except Exception:
            continue
    print("✗ DescribeInvocationResults 超时")
    sys.exit(1)


def main():
    if not STATE_PATH.exists():
        print(f"✗ state.json 不存在: {STATE_PATH}")
        sys.exit(1)

    size = STATE_PATH.stat().st_size
    print(f"▶ 本地 state.json: {STATE_PATH} ({size} bytes)")
    with open(STATE_PATH, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    print(f"▶ base64 长度: {len(b64)} chars")

    # 分片
    chunks = [b64[i:i + CHUNK_SIZE] for i in range(0, len(b64), CHUNK_SIZE)]
    print(f"▶ 分 {len(chunks)} 片，每片 {CHUNK_SIZE} chars")

    # 第 1 步：清空目标文件
    print(f"\n=== Step 1: 清空远程文件 {ECS_TMP_FILE} ===")
    out = run_remote(f"rm -f {ECS_TMP_FILE} && echo cleared")
    print(f"  {out.strip()}")

    # 第 2 步：分片上传
    print(f"\n=== Step 2: 分片上传 ===")
    for i, chunk in enumerate(chunks):
        # 用 echo 追加，避免转义问题（base64 安全字符）
        cmd = f"echo -n '{chunk}' >> {ECS_TMP_FILE} && wc -c {ECS_TMP_FILE}"
        out = run_remote(cmd)
        m = re.search(r'(\d+)\s+\S*state_upload\.b64', out)
        size_now = int(m.group(1)) if m else "?"
        print(f"  片 {i + 1}/{len(chunks)}: 远程 base64 累计 {size_now} chars")
        if i == 0:
            assert size_now == len(chunk), f"第一片大小不对: {size_now} vs {len(chunk)}"

    # 第 3 步：base64 decode + 写最终文件
    print(f"\n=== Step 3: 解码 + 移动到目标位置 ===")
    cmd = (
        f"base64 -d {ECS_TMP_FILE} > {ECS_REMOTE_FILE} && "
        f"rm -f {ECS_TMP_FILE} && "
        f"ls -la {ECS_REMOTE_FILE} && "
        f"echo '---md5---' && md5sum {ECS_REMOTE_FILE}"
    )
    out = run_remote(cmd)
    print(out)

    # 第 4 步：重启容器
    print(f"\n=== Step 4: 重启容器加载新 state.json ===")
    out = run_remote(
        "docker restart douyin-spark && sleep 5 && "
        "curl -sS http://localhost:5000/api/status",
        timeout=60,
    )
    print(out)

    # 验证
    if '"has_auth": true' in out or '"has_auth":true' in out:
        print("\n✅ has_auth=true！state.json 已生效")
        print(f"\n刷新 {WEB_URL} → 直接进入主页面")
        print("然后点 '从抖音拉取好友列表' 验证完整链路")
    else:
        print("\n⚠ has_auth 仍为 false")
        print("  可能原因：")
        print("  1. state.json 不是有效的抖音登录态（cookie 过期）")
        print("  2. 抖音服务端对 ECS IP 段有限制")
        print("  3. web app 还没加载完，curl 太早")


if __name__ == "__main__":
    main()