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
import json as json_lib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "auth" / "state.json"
QR_SCREENSHOT = ROOT / "auth" / "qrcode_local.png"

CHAT_URL = "https://www.douyin.com/chat"

LOGGED_IN_SELECTORS_JS = """() => {
    const sels = [
        '[class*="conversationConversationItem"]',
        '[class*="ConversationItem"]',
        '[class*="chatItem"]',
        '[class*="contactItem"]',
        '[data-e2e="chat-item"]',
    ];
    for (const sel of sels) {
        const el = document.querySelector(sel);
        if (el && el.getBoundingClientRect().width > 0) return true;
    }
    return false;
}"""


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
            headless=False,
            channel="chrome",
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
        logged_in = page.evaluate(LOGGED_IN_SELECTORS_JS)

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
            print("│  如果窗口被挡住，看脚本打印的截图路径           │")
            print("│  脚本会每 5 秒检测一次登录状态（最多 5 分钟）  │")
            print("└────────────────────────────────────────────────┘")
            print()

            # 截图整页保存
            try:
                QR_SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(QR_SCREENSHOT), full_page=False)
                print(f"📷 已截图整页到: {QR_SCREENSHOT}")
            except Exception as e:
                print(f"⚠ 整页截图失败: {e}")

            # 尝试单独截二维码区域
            try:
                qr_box = page.locator('img.RhjdbXj8, [class*="qrcode"] img, [class*="QrCode"]').first
                if qr_box.is_visible(timeout=2000):
                    qr_box.screenshot(path=str(QR_SCREENSHOT))
                    print(f"📷 已截图二维码区域到: {QR_SCREENSHOT}")
            except Exception as e:
                print(f"⚠ 二维码区域截图失败: {e}")

            # 一直等（不超时）
            # 每 5 秒检测一次，最多 1 小时；登录成功立即保存
            MAX_WAIT_SECONDS = 3600
            for i in range(MAX_WAIT_SECONDS // 5):
                page.wait_for_timeout(5000)
                logged_in = page.evaluate(LOGGED_IN_SELECTORS_JS)
                if logged_in:
                    print(f"✅ 检测到登录成功！（{(i + 1) * 5} 秒）")
                    break
                if (i + 1) % 6 == 0:
                    print(f"  等待扫码... ({(i + 1) * 5} 秒)")
                    # 每 30 秒重新截一次图（防止二维码刷新）
                    try:
                        page.screenshot(path=str(QR_SCREENSHOT), full_page=False)
                    except Exception:
                        pass
            else:
                print("✗ 1 小时内未检测到登录，超时")
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
        with open(STATE_PATH) as f:
            state = json_lib.load(f)
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