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
    """从会话列表 scroll container 内部抽出好友信息

    关键约束：必须在会话列表的滚动容器内查找，避免命中侧边栏、
    tooltip、未关闭弹窗等相同 class 子串。

    Returns:
        [{"name": "...", "avatar": "https://...", "fire": "3 天"}, ...]
    """
    items = []

    # 先定位会话列表的滚动容器（一次），然后只在它内部找 item
    list_container_selectors = [
        '[class*="conversationConversationList"]',
        '[class*="conversationList"]',
        '[class*="chatList"]',
        '[class*="messageList"]',
    ]

    container = None
    for sel in list_container_selectors:
        try:
            cand = page.locator(sel).first
            if cand.is_visible(timeout=1000):
                container = cand
                logger.debug("会话列表容器命中: %s", sel)
                break
        except Exception:
            continue

    # 容器内查找 item 的 selectors（按精准度降序）
    if container is not None:
        item_selectors_in_container = [
            '[class*="conversationConversationItem"]',
            '[class*="ConversationItem"]',
            '[data-e2e="chat-item"]',
        ]
    else:
        # 兜底：找不到容器时退回全文档（不再命中过宽的 selector）
        item_selectors_in_container = [
            '[class*="conversationConversationItem"]',
            '[data-e2e="chat-item"]',
        ]

    seen_keys = set()
    for sel in item_selectors_in_container:
        scope = container.locator(sel) if container is not None else page.locator(sel)
        try:
            elements = scope.all()
        except Exception:
            continue
        if not elements:
            continue

        for el in elements:
            try:
                if not el.is_visible(timeout=500):
                    continue

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

                # 头像（必须取到 src，没 avatar 的视为骨架屏跳过）
                avatar = ""
                for img_sel in ['img[class*="avatar"]', 'img[class*="Avatar"]', 'img']:
                    try:
                        img = el.locator(img_sel).first
                        if img.is_visible(timeout=300):
                            src = img.get_attribute("src") or ""
                            if src and not src.startswith("data:image/svg"):
                                avatar = src
                                break
                    except Exception:
                        continue

                # 双键去重：(name, avatar 末段) — 同一会话复用 avatar
                # 即便 name 出现细微差异（emoji 后缀/时间戳），avatar 相同也合并
                avatar_key = ""
                if avatar:
                    # 取 URL 末段作为 key（避免长 URL 哈希开销）
                    avatar_key = avatar.split("/")[-1].split("?")[0][:50]
                dedup_key = (name, avatar_key)
                if dedup_key in seen_keys:
                    continue

                # 火花天数
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
                seen_keys.add(dedup_key)
            except Exception:
                continue

        if items:
            break  # 命中精准 selector 后不再试后面的

    logger.info("抽取到 %d 位不重复好友", len(items))
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

    # 滚动加载更多：只在会话列表容器内滚，先滚到底再统一抽一次
    scrollables = [
        '[class*="conversationConversationList"]',
        '[class*="conversationList"]',
        '[class*="chatList"]',
        ".semi-scrollbar",
    ]

    scroll_container = None
    for sel in scrollables:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1000):
                scroll_container = el
                break
        except Exception:
            continue

    # 循环滚动到底：每次滚 ~scrollHeight 的距离，连续 N 次没有新内容即停
    if scroll_container is not None:
        no_progress_rounds = 0
        for _ in range(MAX_SCROLLS):
            try:
                scroll_height = scroll_container.evaluate("el => el.scrollHeight")
                client_height = scroll_container.evaluate("el => el.clientHeight")
                old_top = scroll_container.evaluate("el => el.scrollTop")
                target = min(old_top + client_height - 40, scroll_height - client_height)
                if target <= old_top:
                    # 已到底
                    no_progress_rounds += 1
                    if no_progress_rounds >= 2:
                        break
                else:
                    scroll_container.evaluate(f"el => el.scrollTop = {target}")
                    page.wait_for_timeout(800)
                    new_top = scroll_container.evaluate("el => el.scrollTop")
                    if new_top == old_top:
                        no_progress_rounds += 1
                        if no_progress_rounds >= 2:
                            break
                    else:
                        no_progress_rounds = 0
            except Exception:
                break
        # 滚完后滚回顶部，再做一次性抽取（虚拟滚动 DOM 已稳定）
        try:
            scroll_container.evaluate("el => el.scrollTop = 0")
            page.wait_for_timeout(500)
        except Exception:
            pass

    # 最终一次性抽取（容器内查 + 双键去重，已经不会再重复）
    items = _extract_conversations(page)

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
    from core.browser import get_browser, create_context, is_system_chrome_available

    items: list[dict] = []
    use_system = is_system_chrome_available()
    with sync_playwright() as p:
        browser = get_browser(p, headless=headless, use_system_chrome=use_system)
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
