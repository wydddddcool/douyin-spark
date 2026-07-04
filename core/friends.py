"""好友列表拉取 — 从抖音聊天页抓取会话列表（昵称、头像、火花天数）

只读操作，不会发送任何消息。供 Web 面板"好友列表可视化"功能使用。
"""

import os
from typing import Optional

from playwright.sync_api import Page, BrowserContext

from utils.logger import setup_logger
from utils.paths import AUTH_DIR

logger = setup_logger("friends")

CHAT_URL = "https://www.douyin.com/chat"
MAX_SCROLLS = 8  # 拉取好友列表最多滚动 8 次，避免太久


def _extract_conversations(page: Page) -> list[dict]:
    """从当前可见的会话列表抽取出好友信息

    Returns:
        [{"name": "...", "avatar": "https://...", "fire": "3 天"}, ...]
    """
    items = []

    # 抖音会话列表 selector（覆盖多版本）
    item_selectors = [
        '[class*="conversationConversationItem"]',
        '[class*="ConversationItem"]',
        '[class*="conversationItem"]',
        '[class*="chatItem"]',
        '[data-e2e="chat-item"]',
    ]

    seen_names = set()
    for sel in item_selectors:
        try:
            elements = page.locator(sel).all()
            if not elements:
                continue
            for el in elements:
                try:
                    if not el.is_visible(timeout=500):
                        continue
                    # 昵称
                    name = ""
                    for title_sel in ['[class*="title"]', '[class*="name"]', '[class*="nickname"]']:
                        try:
                            t = el.locator(title_sel).first
                            if t.is_visible(timeout=300):
                                name = (t.text_content(timeout=500) or "").strip()
                                if name:
                                    break
                        except Exception:
                            continue
                    if not name:
                        continue
                    if name in seen_names:
                        continue

                    # 头像
                    avatar = ""
                    for img_sel in ['img[class*="avatar"]', 'img[class*="Avatar"]', 'img']:
                        try:
                            img = el.locator(img_sel).first
                            if img.is_visible(timeout=300):
                                avatar = img.get_attribute("src") or ""
                                if avatar:
                                    break
                        except Exception:
                            continue

                    # 火花天数（在副标题/红标里）
                    fire = ""
                    for fire_sel in ['[class*="fire"]', '[class*="spark"]', '[class*="streak"]', '[class*="sub"]']:
                        try:
                            f = el.locator(fire_sel).first
                            if f.is_visible(timeout=300):
                                fire = (f.text_content(timeout=500) or "").strip()
                                if fire:
                                    break
                        except Exception:
                            continue

                    items.append({"name": name, "avatar": avatar, "fire": fire})
                    seen_names.add(name)
                except Exception:
                    continue
            if items:
                break  # 命中一个 selector 就不再尝试后面的
        except Exception:
            continue

    return items


def list_friends(
    page: Page,
    context: BrowserContext,
    state_path: str,
    headless: bool = True,
) -> list[dict]:
    """打开聊天页，拉取好友列表

    Args:
        page: 已创建的 Page
        context: 已创建的 BrowserContext
        state_path: 登录凭证路径
        headless: 是否无头模式（拉取列表无需有头）

    Returns:
        [{"name": ..., "avatar": ..., "fire": ...}, ...]
        登录失效返回空列表
    """
    from core.auth import is_logged_in

    logger.info("导航到聊天页拉取好友列表...")
    try:
        page.goto(CHAT_URL, wait_until="domcontentloaded", timeout=120000)
    except Exception as e:
        logger.warning("加载聊天页超时: %s", e)
        return []
    page.wait_for_timeout(8000)

    if not is_logged_in(page, save_debug=True):
        logger.warning("登录凭证已过期，无法拉取好友列表")
        return []

    items = list(_extract_conversations(page))

    # 滚动加载更多
    scroll_count = 0
    while scroll_count < MAX_SCROLLS:
        prev_count = len(items)
        # 滚动会话列表
        scrollables = [
            '[class*="conversationConversationList"]',
            '[class*="conversationList"]',
            '[class*="chatList"]',
            ".semi-scrollbar",
        ]
        scrolled = False
        for sel in scrollables:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=1000):
                    old_top = el.evaluate("el => el.scrollTop")
                    el.evaluate("el => el.scrollTop += 600")
                    page.wait_for_timeout(1200)
                    new_top = el.evaluate("el => el.scrollTop")
                    if new_top > old_top:
                        scrolled = True
                    break
            except Exception:
                continue

        if not scrolled:
            break

        new_items = _extract_conversations(page)
        # 合并去重
        seen = {it["name"] for it in items}
        for it in new_items:
            if it["name"] not in seen:
                items.append(it)
                seen.add(it["name"])

        if len(items) == prev_count:
            # 滚动后没有新好友，可能到底了
            scroll_count += 1
            if scroll_count >= 3:
                break
        else:
            scroll_count = 0  # 还有新内容，重置计数

    # 刷新登录状态
    try:
        context.storage_state(path=state_path)
    except Exception as e:
        logger.warning("刷新 state 失败: %s", e)

    logger.info("共拉取到 %d 位好友", len(items))
    return items


def fetch_friends_with_state(state_path: str, headless: bool = True) -> list[dict]:
    """便捷入口：自行启动浏览器拉取好友列表

    Args:
        state_path: 登录凭证路径
        headless: 是否无头
    """
    if not os.path.exists(state_path):
        logger.error("登录凭证不存在: %s", state_path)
        return []

    from playwright.sync_api import sync_playwright
    from core.browser import get_browser, create_context

    items: list[dict] = []
    with sync_playwright() as p:
        browser = get_browser(p, headless=headless)
        context = create_context(browser, storage_state=state_path)
        page = context.new_page()
        try:
            items = list_friends(page, context, state_path, headless=headless)
        except Exception as e:
            logger.error("拉取好友列表异常: %s", e)
            try:
                page.screenshot(path=os.path.join(AUTH_DIR, "debug_friends.png"))
            except Exception:
                pass
        finally:
            page.close()
            browser.close()
    return items
