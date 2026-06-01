"""Playwright 浏览器初始化 + 反检测"""

import os
from typing import Optional
from playwright.sync_api import (
    Playwright,
    Browser,
    BrowserContext,
)

# 用户数据目录（持久化浏览器状态，更像真人）
USER_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "auth", "browser_data")

# 更新的 User-Agent
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def get_browser(p: Playwright, headless: bool = True) -> Browser:
    """启动 Chromium 浏览器（无持久化）"""
    return p.chromium.launch(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    )


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


def create_persistent_context(p: Playwright, headless: bool = False) -> BrowserContext:
    """创建持久化浏览器上下文（用于 setup 登录）

    使用系统 Chrome（channel="chrome"）而非 Playwright 内置 Chromium，
    因为抖音会对内置 Chromium 触发人机验证，而系统 Chrome 指纹真实不会。
    持久化 context 拥有完整的用户数据目录，行为更像真实用户浏览器。
    """
    os.makedirs(USER_DATA_DIR, exist_ok=True)

    context = p.chromium.launch_persistent_context(
        USER_DATA_DIR,
        channel="chrome",          # 关键：用系统 Chrome 而非 Playwright Chromium
        headless=headless,
        viewport={"width": 1920, "height": 1080},
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
        args=[
            "--disable-blink-features=AutomationControlled",
        ],
    )
    # 系统 Chrome 不需要注入 stealth JS（它本身就是真实浏览器）
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
