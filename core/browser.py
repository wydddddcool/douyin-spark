"""Playwright 浏览器初始化 + 反检测"""

import os
import shutil
from typing import Optional
from playwright.sync_api import (
    Playwright,
    Browser,
    BrowserContext,
)

from utils.paths import BROWSER_DATA_DIR as USER_DATA_DIR

# 更新的 User-Agent
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def is_system_chrome_available() -> bool:
    """检测当前环境是否安装了系统 Chrome

    Docker 容器通常没有系统 Chrome，需要回退到 Playwright 内置 Chromium。
    """
    # 容器环境标志
    if os.path.exists("/.dockerenv"):
        return False
    # 常见 Chrome 可执行文件路径
    chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/usr/bin/google-chrome-stable",
    ]
    for path in chrome_paths:
        if os.path.exists(path):
            return True
    # which 命令兜底
    return shutil.which("google-chrome") is not None or shutil.which("chrome") is not None


def get_browser(
    p: Playwright,
    headless: bool = True,
    use_system_chrome: bool = True,
) -> Browser:
    """启动浏览器（无持久化）— 默认用系统 Chrome 而非 Playwright 内置 Chromium

    原因：1) 打包后内置 Chromium 不在 bundle 里，frozen 模式必崩；
    2) 抖音对 Playwright 内置 Chromium 触发人机验证，系统 Chrome 不会。

    参数：
        use_system_chrome: True=系统 Chrome（本地 macOS 推荐），
                          False=Playwright 内置 Chromium（Docker 环境）
    """
    launch_kwargs = {
        "headless": headless,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    }
    if use_system_chrome:
        launch_kwargs["channel"] = "chrome"
    return p.chromium.launch(**launch_kwargs)


def create_context(
    browser: Browser,
    storage_state: Optional[str] = None,
) -> BrowserContext:
    """创建浏览器上下文，可选加载已保存的登录状态"""
    kwargs = {}
    if storage_state and os.path.exists(storage_state):
        kwargs["storage_state"] = storage_state

    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
        user_agent=UA,
        **kwargs,
    )
    _inject_stealth(context)
    return context


def create_persistent_context(
    p: Playwright,
    headless: bool = False,
    use_system_chrome: bool = True,
) -> BrowserContext:
    """创建持久化浏览器上下文（用于 setup 登录）

    使用系统 Chrome（channel="chrome"）而非 Playwright 内置 Chromium，
    因为抖音会对内置 Chromium 触发人机验证，而系统 Chrome 指纹真实不会。
    持久化 context 拥有完整的用户数据目录，行为更像真实用户浏览器。

    参数：
        headless: 是否无头模式（Docker/服务器环境必须 True）
        use_system_chrome: True=用系统 Chrome（本地 macOS 推荐），
                          False=用 Playwright 内置 Chromium（Docker 环境）
    """
    os.makedirs(USER_DATA_DIR, exist_ok=True)

    launch_kwargs = {
        "headless": headless,
        "viewport": {"width": 1920, "height": 1080},
        "locale": "zh-CN",
        "timezone_id": "Asia/Shanghai",
        "user_agent": UA,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    }
    if use_system_chrome:
        launch_kwargs["channel"] = "chrome"

    context = p.chromium.launch_persistent_context(USER_DATA_DIR, **launch_kwargs)

    # 内置 Chromium 需要注入 stealth JS 反检测；系统 Chrome 不需要
    if not use_system_chrome:
        _inject_stealth(context)
    return context


def _inject_stealth(context: BrowserContext) -> None:
    """注入反检测 JS 脚本"""
    context.add_init_script("""
        // 隐藏 webdriver 特征
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

        // 设置语言
        Object.defineProperty(navigator, 'languages', {
            get: () => ['zh-CN', 'zh', 'en'],
        });

        // 模拟 plugins（比空数组更真实）
        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                const plugins = [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer',
                      description: 'Portable Document Format' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
                      description: '' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin',
                      description: '' },
                ];
                plugins.length = 3;
                return plugins;
            },
        });

        // 覆盖 chrome 对象
        if (!window.chrome) {
            window.chrome = {};
        }
        window.chrome.runtime = {
            connect: function() {},
            sendMessage: function() {},
        };

        // 伪装 permissions API
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (params) => (
            params.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(params)
        );

        // 伪装 WebGL vendor/renderer（headless GPU 特征）
        const getParameterOrig = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(param) {
            if (param === 37445) return 'Intel Inc.';
            if (param === 37446) return 'Intel Iris OpenGL Engine';
            return getParameterOrig.call(this, param);
        };

        // 隐藏 HeadlessChrome 特征
        const origDesc = Object.getPrototypeOf(navigator).constructor;
        Object.defineProperty(navigator, 'connection', {
            get: () => ({
                effectiveType: '4g',
                rtt: 50,
                downlink: 10,
                saveData: false,
            }),
        });
    """)


def save_state(context: BrowserContext, path: str) -> None:
    """保存浏览器上下文状态（cookie + localStorage）"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    context.storage_state(path=path)
