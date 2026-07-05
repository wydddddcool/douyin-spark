"""
mac_login.py — 在 Mac 本地用真实 Chrome 扫码登录抖音

为什么需要这个脚本？
- ECS 容器里跑的是 headless Chromium，抖音反爬虫识别后给假二维码
- 你之前在 Mac 上真实 Chrome 里登录过的 state.json 已经过期（sessionid 2026-06-22 过期）
- 必须用 Mac 上的真实 Chrome 重新扫码生成新的 state.json
- 然后上传到 ECS 容器，ECS 容器直接加载 state.json 跳过扫码环节

用法：
    python3 scripts/mac_login.py
    # 会自动弹出 Chrome 窗口 → 打开抖音聊天页 → 等你扫码
    # 扫完后会自动保存 state.json 到 auth/state.json

依赖：
    pip3 install playwright
    python3 -m playwright install chromium
"""
import os
import sys
import time
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "auth" / "state.json"

CHAT_URL = "https://www.douyin.com/chat"


def check_dependencies():
    try:
        import playwright  # noqa
    except ImportError:
        print("⚠ playwright 未安装，正在安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        print("✓ playwright 安装完成")


def main():
    check_dependencies()

    from playwright.sync_api import sync_playwright

    # 先备份现有 state.json（如果存在）
    if STATE_PATH.exists():
        backup = STATE_PATH.with_suffix(".json.bak")
        import shutil
        shutil.copy2(STATE_PATH, backup)
        print(f"已备份旧 state.json -> {backup.name}")

    print("\n=== 启动真实 Chrome 打开抖音 ===")
    print(f"URL: {CHAT_URL}")
    print(f"State: {STATE_PATH}")
    print()

    with sync_playwright() as p:
        # channel="chrome" = 用系统装的 Google Chrome，不是 headless Chromium
        browser = p.chromium.launch(
            headless=False,  # 真实窗口，必须
            channel="chrome",  # 用 Chrome 不是 Chromium
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        page = context.new_page()
        page.goto(CHAT_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)

        print(f"页面已打开：{page.url}")
        print(f"页面标题：{page.title()}")
        print()

        # 检查是否已经登录
        logged_in = page.evaluate("""() => {
            const sels = [
                '[class*="conversationConversationItem"]',
                '[class*="ConversationItem"]',
                '[data-e2e="chat-item"]',
            ];
            for (const sel of sels) {
                const el = document.querySelector(sel);
                if (el && el.getBoundingClientRect().width > 0) return true;
            }
            return false;
        }""")

        if logged_in:
            print("✅ 检测到已登录！直接保存 state.json")
        else:
            print("⚠ 需要扫码登录")
            print()
            print("┌────────────────────────────────────────────────┐")
            print("│  请在弹出的 Chrome 窗口里：                     │")
            print("│  1. 找到抖音登录二维码（页面中央）             │")
            print("│  2. 用你的抖音 App 「扫一扫」对准它           │")
            print("│  3. 在手机上点「登录」                         │")
            print("│                                                │")
            print("│  本脚本会每 5 秒检测一次登录状态                │")
            print("│  登录成功（看到会话列表）后会自动继续          │")
            print("└────────────────────────────────────────────────┘")
            print()

            # 最多等 3 分钟
            for i in range(36):
                page.wait_for_timeout(5000)
                logged_in = page.evaluate("""() => {
                    const sels = [
                        '[class*="conversationConversationItem"]',
                        '[class*="ConversationItem"]',
                        '[data-e2e="chat-item"]',
                    ];
                    for (const sel of sels) {
                        const el = document.querySelector(sel);
                        if (el && el.getBoundingClientRect().width > 0) return true;
                    }
                    return false;
                }""")
                if logged_in:
                    print(f"✅ 检测到登录成功！（{i * 5 + 5} 秒）")
                    break
                print(f"  等待扫码... ({i * 5 + 5} 秒)")
            else:
                print("✗ 3 分钟内未检测到登录，超时")
                browser.close()
                sys.exit(1)

        # 登录成功后多等几秒让 cookie 稳定
        page.wait_for_timeout(3000)

        # 保存 storage state
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(STATE_PATH))
        print(f"\n✅ state.json 已保存到：{STATE_PATH}")
        print(f"   大小：{STATE_PATH.stat().st_size} bytes")

        # 验证
        import json
        with open(STATE_PATH) as f:
            state = json.load(f)
        cookies = state.get("cookies", [])
        print(f"   cookies: {len(cookies)} 个")
        dy_cookies = [c for c in cookies if "douyin.com" in c.get("domain", "")]
        print(f"   douyin.com 相关：{len(dy_cookies)} 个")
        session_cookies = [c for c in cookies if c["name"] in ("sessionid", "sessionid_ss")]
        print(f"   sessionid: {[c['name'] for c in session_cookies]}")

        browser.close()

    print()
    print("✅ 完成！")
    print()
    print("下一步：")
    print("  python3 scripts/upload_state.py")
    print("  → 把 state.json 上传到 ECS 容器")


if __name__ == "__main__":
    main()