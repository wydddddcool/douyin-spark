"""统一路径管理 — frozen / dev 模式下都正确指向用户数据目录和资源目录

设计原则（PyInstaller 打包应用的标准做法）：
- BUNDLE_DIR  : 只读资源目录（模板、默认 settings、Playwright 资源）
                frozen → sys._MEIPASS / sys.executable 所在目录
                dev    → 项目根目录
- DATA_DIR    : 用户可写数据目录（auth、用户 settings、logs、截图、browser_data）
                macOS   → ~/Library/Application Support/抖音续火花
                Windows → %APPDATA%\抖音续火花
                Linux   → ~/.local/share/抖音续火花
                dev     → 项目根目录（保持向后兼容）

为什么这么分？因为 macOS 把 .app 装到 /Applications/ 后，
bundle 内部是只读的，往 _BASE 写任何文件都会失败。
"""

import os
import sys


APP_NAME = "抖音续火花"

# ---------- 资源目录（只读） ----------
if getattr(sys, "frozen", False):
    # PyInstaller onefile: sys._MEIPASS 指向解压临时目录
    # PyInstaller onedir : sys._MEIPASS == sys.executable 所在目录
    BUNDLE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    BUNDLE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------- 用户数据目录（可写） ----------
def _user_data_dir() -> str:
    if not getattr(sys, "frozen", False):
        # dev 模式：保持往项目根目录写，方便调试
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    system = sys.platform
    if system == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif system == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, APP_NAME)


DATA_DIR = _user_data_dir()


# ---------- 子目录（用户可写） ----------
CONFIG_DIR = os.path.join(DATA_DIR, "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "settings.yaml")

AUTH_DIR = os.path.join(DATA_DIR, "auth")
STATE_PATH = os.path.join(AUTH_DIR, "state.json")
QRCODE_PATH = os.path.join(AUTH_DIR, "qrcode.png")
BROWSER_DATA_DIR = os.path.join(AUTH_DIR, "browser_data")

LOG_DIR = os.path.join(DATA_DIR, "logs")


# ---------- 资源文件（只读） ----------
DEFAULT_CONFIG_BUNDLED = os.path.join(BUNDLE_DIR, "config", "settings.yaml")
WEB_TEMPLATES_DIR = os.path.join(BUNDLE_DIR, "web", "templates")
WEB_STATIC_DIR = os.path.join(BUNDLE_DIR, "web", "static")


def ensure_user_dirs() -> None:
    """启动时确保所有用户数据目录存在"""
    for d in (DATA_DIR, CONFIG_DIR, AUTH_DIR, BROWSER_DATA_DIR, LOG_DIR):
        os.makedirs(d, exist_ok=True)


def ensure_default_config() -> None:
    """首次运行：从 bundle 复制默认 settings.yaml 到用户配置目录"""
    import shutil
    if os.path.exists(CONFIG_PATH):
        return
    if os.path.exists(DEFAULT_CONFIG_BUNDLED):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        shutil.copy2(DEFAULT_CONFIG_BUNDLED, CONFIG_PATH)
