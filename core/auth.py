"""登录认证模块 — 二维码扫码登录 + state 管理"""

import os
from playwright.sync_api import Page, BrowserContext

from utils.logger import setup_logger
from utils.paths import AUTH_DIR, QRCODE_PATH

logger = setup_logger("auth")

CHAT_URL = "https://www.douyin.com/chat"


def is_logged_in(page: Page, save_debug: bool = False) -> bool:
    """检测聊天页是否已登录，最长等待 15 秒让 JS 渲染完成"""
    # 如果 URL 包含 passport/login，肯定未登录
    url = page.url.lower()
    if "passport" in url or "/login" in url:
        logger.debug("URL 含 passport/login，判定未登录: %s", page.url)
        return False

    chat_item_selectors = [
        '[class*="conversationConversationItem"]',
        '[class*="ConversationItem"]',
        '[class*="chatItem"]',
        '[class*="contactItem"]',
        '[data-e2e="chat-item"]',
    ]

    # 一次性 OR 等待任意 selector 命中（最长 15 秒），替代顺序轮询 60 秒
    combined = ", ".join(chat_item_selectors)
    try:
        page.wait_for_selector(combined, timeout=15000)
        logger.debug("登录检测命中组合 selector")
        return True
    except Exception:
        pass

    # 兜底：列表区域有 ≥3 行 div
    try:
        list_items = page.locator('[class*="list"] > div, [class*="List"] > div').all()
        if len(list_items) >= 3:
            return True
    except Exception:
        pass

    # 未检测到会话列表，保存调试截图
    if save_debug:
        try:
            page.screenshot(path=os.path.join(AUTH_DIR, "debug_login_check.png"))
            logger.info("调试截图已保存: auth/debug_login_check.png")
            logger.info("当前 URL: %s | 标题: %s", page.url, page.title())
        except Exception:
            pass

    return False


def _find_qrcode(page: Page) -> bool:
    """在页面上查找二维码并截图保存，返回是否找到"""
    qrcode_selectors = [
        # 弹窗式登录
        'div[data-e2e="qrcode-login-container"] img',
        'img[class*="qrcode"]',
        'img[alt*="扫码"]',
        'img[alt*="二维码"]',
        'canvas[class*="qrcode"]',
        '[class*="qrcode"] img',
        '[class*="login-qrcode"] img',
        '[class*="loginContainer"] img',
        '[class*="modal"] img',
        '[class*="dialog"] img',
        'img[src*="qrcode"]',
        'img[src*="qr"]',
        # 全屏登录页 (douyin.com/chat 凭证失效时会进入这个页面)
        '[class*="login"] canvas',
        '[class*="Login"] canvas',
        '[class*="qrcode"] canvas',
        '[class*="QrCode"] canvas',
        '[class*="QRCode"] canvas',
        '[class*="scan"] canvas',
        'div[data-e2e*="qrcode"] canvas',
        'div[class*="QRCodeWrapper"]',
        'div[class*="QrCodeWrapper"]',
        'div[class*="qrcodeWrapper"]',
        # 兜底：页面里唯一的 canvas（>100px）
    ]

    # 一次性 OR 等待任意 selector 命中（最长 15 秒），替代顺序轮询 60 秒
    combined = ", ".join(qrcode_selectors)
    try:
        qr_el = page.wait_for_selector(combined, timeout=15000)
        if qr_el and qr_el.is_visible():
            # 验证尺寸像二维码（正方形 120-400px），不像就让兜底接管
            try:
                box = qr_el.bounding_box()
                if box:
                    w, h = box["width"], box["height"]
                    ratio = w / h if h > 0 else 0
                    if 80 < w < 500 and 0.7 < ratio < 1.3:
                        qr_el.screenshot(path=QRCODE_PATH)
                        logger.info("✅ 二维码已保存: %s", os.path.abspath(QRCODE_PATH))
                        logger.info("   请用抖音 App「扫一扫」扫描此二维码登录")
                        return True
                    logger.info("命中元素尺寸不像二维码 (%dx%d, ratio=%.2f)，走兜底", int(w), int(h), ratio)
            except Exception as e:
                logger.warning("尺寸验证异常: %s，直接截图", e)
                qr_el.screenshot(path=QRCODE_PATH)
                return True
    except Exception:
        pass

    return False


def _find_qrcode_from_all_images(page: Page) -> bool:
    """兜底：遍历页面所有图片，找正方形尺寸像二维码的截图保存"""
    logger.info("尝试兜底方案：扫描页面所有图片...")
    images = page.locator("img").all()
    logger.info("页面上共找到 %d 张图片", len(images))

    for i, img in enumerate(images):
        try:
            if not img.is_visible(timeout=1000):
                continue
            box = img.bounding_box()
            if not box:
                continue
            w, h = box["width"], box["height"]
            ratio = w / h if h > 0 else 0
            # 二维码：正方形，120-400px
            if 120 < w < 400 and 0.7 < ratio < 1.3:
                img.screenshot(path=QRCODE_PATH)
                src = img.get_attribute("src") or ""
                logger.info("找到疑似二维码图片 #%d: %dx%d src=%s", i, int(w), int(h), src[:60])
                logger.info("✅ 已截图保存: %s", os.path.abspath(QRCODE_PATH))
                logger.info("   请用抖音 App「扫一扫」扫描此二维码登录")
                return True
        except Exception:
            continue

    return False


def wait_for_qrcode_and_login(
    page: Page,
    context: BrowserContext,
    state_path: str,
) -> bool:
    """扫码登录流程：访问聊天页 → 检查登录状态 → 找二维码 → 等扫码 → 保存 state

    策略：
    - 直接访问 douyin.com/chat
    - 如果已登录（会话列表可见）→ 直接保存 state
    - 如果未登录（弹出登录弹窗）→ 截二维码 → 等待扫码
    - 扫码成功判断：等待会话列表出现（不依赖特定 cookie 名称）
    """
    # 第 1 步：访问聊天页
    logger.info("正在打开抖音聊天页...")
    page.goto(CHAT_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)

    # 第 2 步：检查是否已经登录（通过页面元素判断）
    if is_logged_in(page):
        logger.info("✅ 检测到已登录（会话列表可见），保存凭证...")
        context.storage_state(path=state_path)
        logger.info("✅ 凭证已保存: %s", os.path.abspath(state_path))
        return True

    # 第 3 步：查找二维码
    logger.info("未检测到会话列表，正在查找登录二维码...")
    qr_found = _find_qrcode(page)

    if not qr_found:
        qr_found = _find_qrcode_from_all_images(page)

    if not qr_found:
        logger.error("找不到二维码")
        page.screenshot(path=os.path.join(AUTH_DIR, "login_page_debug.png"))
        try:
            with open(os.path.join(AUTH_DIR, "login_page_debug.html"), "w", encoding="utf-8") as f:
                f.write(page.content())
            logger.info("调试信息已保存: auth/login_page_debug.png + .html")
        except Exception:
            pass
        return False

    # 第 4 步：等待扫码成功（轮询页面直到会话列表出现）
    logger.info("   等待扫码（最长 120 秒）...")
    login_ok = False
    for i in range(60):  # 120 秒 = 60 次 × 2 秒
        page.wait_for_timeout(2000)
        if is_logged_in(page):
            login_ok = True
            break
        if i > 0 and i % 5 == 0:
            logger.info("   仍在等待扫码... (%d秒)", i * 2)

    if not login_ok:
        logger.error("登录超时（120 秒），请重新运行 python main.py --setup")
        return False

    logger.info("✅ 扫码登录成功！")
    page.wait_for_timeout(5000)

    # 第 5 步：保存完整上下文状态
    context.storage_state(path=state_path)
    logger.info("✅ 登录凭证已保存: %s", os.path.abspath(state_path))
    return True


def check_login(page: Page) -> bool:
    """导航到聊天页，检查登录状态是否有效"""
    logger.info("正在进入抖音聊天页...")
    try:
        page.goto(CHAT_URL, wait_until="domcontentloaded", timeout=120000)
    except Exception as e:
        logger.warning("加载聊天页超时或出错: %s", e)

    page.wait_for_timeout(5000)

    if not is_logged_in(page):
        logger.error("❌ 登录凭证已过期，请重新运行: python main.py --setup")
        return False

    logger.info("✅ 登录状态有效")
    return True
