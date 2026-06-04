#!/usr/bin/env python3
"""
抖音续火花 — 桌面启动器
双击运行：自动启动控制面板并打开浏览器
"""

import os
import sys
import threading
import time
import webbrowser

# frozen 模式下，把 bundle 目录加入 sys.path，让打包进 bundle 的 utils/core/web 能被 import
if getattr(sys, 'frozen', False):
    _BUNDLE = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    sys.path.insert(0, _BUNDLE)

from utils.paths import (
    ensure_user_dirs,
    ensure_default_config,
)

DEFAULT_PORT = 5733  # 避开 macOS AirPlay Receiver 占用的 5000 端口


def _pick_free_port(start: int = DEFAULT_PORT, tries: int = 20) -> int:
    """从 start 开始找一个未被占用的端口；最多尝试 tries 次"""
    import socket
    for offset in range(tries):
        port = start + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start  # 都不行就用默认值，让 Flask 自己报错


def _chrome_installed() -> bool:
    import platform
    system = platform.system()
    if system == "Darwin":
        paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    elif system == "Windows":
        appdata = os.environ.get("LOCALAPPDATA", "")
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.join(appdata, r"Google\Chrome\Application\chrome.exe"),
        ]
    else:
        return True
    return any(os.path.exists(p) for p in paths)


def _show_error(title: str, msg: str):
    import platform
    if platform.system() == "Windows":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, title, 0x10)
        except Exception:
            print(f"{title}: {msg}")
    elif platform.system() == "Darwin":
        # macOS .app 双击运行没有 stdout，必须用原生弹窗
        try:
            import subprocess
            script = f'display dialog "{msg}" with title "{title}" buttons {{"OK"}} default button "OK" with icon stop'
            subprocess.run(["osascript", "-e", script], check=False)
        except Exception:
            print(f"{title}: {msg}")
    else:
        print(f"{title}: {msg}")


def _start_flask(port: int):
    try:
        from web.app import app, _scheduler, _apply_schedule
        _scheduler.start()
        _apply_schedule()
        app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)
    except Exception as e:
        # frozen 模式下没 stdout，写崩溃日志到用户数据目录
        import traceback
        from utils.paths import LOG_DIR
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, "launcher_crash.log"), "w", encoding="utf-8") as f:
            f.write(f"{e}\n\n{traceback.format_exc()}")
        _show_error("抖音续火花 — 启动失败",
                    f"Flask 启动时崩溃，详见 logs/launcher_crash.log\n\n{e}")
        raise


def main():
    if not _chrome_installed():
        _show_error(
            "抖音续火花 — 缺少依赖",
            "未检测到 Google Chrome 浏览器。\n请先安装 Chrome 后再运行本软件。\n\n下载：https://www.google.com/chrome/",
        )
        sys.exit(1)

    # 准备用户数据目录 + 首次运行复制默认配置
    ensure_user_dirs()
    ensure_default_config()

    port = _pick_free_port()
    t = threading.Thread(target=_start_flask, args=(port,), daemon=True)
    t.start()

    # 等 Flask 绑定端口
    time.sleep(1.5)

    url = f'http://127.0.0.1:{port}'
    webbrowser.open(url)
    print(f"抖音续火花已启动 → {url}")

    t.join()


if __name__ == '__main__':
    main()
