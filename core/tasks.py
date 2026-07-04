"""核心任务 — 导航聊天页 → 查找好友 → 发送消息"""

import os
import platform
import random
import time
from playwright.sync_api import Page, BrowserContext

from utils.paths import AUTH_DIR

_SELECT_ALL = "Meta+a" if platform.system() == "Darwin" else "Control+a"

from core.message import compose_message, record_sent
from utils.logger import setup_logger

logger = setup_logger("tasks")

CHAT_URL = "https://www.douyin.com/chat"
MAX_SCROLLS = 30
SCROLL_STEP = 500
SCROLL_WAIT = 1.5


def scroll_conversation_list(page: Page) -> bool:
    """向下滚动会话列表，返回 True 表示还有更多内容"""
    scrollable_selectors = [
        '[class*="conversationConversationList"]',
        '[class*="conversationList"]',
        '[class*="chatList"]',
        ".semi-scrollbar",
    ]

    for sel in scrollable_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                old_top = el.evaluate("el => el.scrollTop")
                el.evaluate("el => el.scrollTop += %d" % SCROLL_STEP)
                page.wait_for_timeout(int(SCROLL_WAIT * 1000))
                new_top = el.evaluate("el => el.scrollTop")
                return new_top > old_top
        except Exception:
            continue
    return False


def find_target_on_page(page: Page, target_name: str) -> bool:
    """在当前页面上查找目标好友，返回是否找到并点击"""
    # 策略 1：精确文本匹配
    strategies = [
        # text locator
        lambda: page.get_by_text(target_name, exact=True).first,
        # 模糊匹配
        lambda: page.locator(f'text="{target_name}"').first,
        # 包含文本的任意元素
        lambda: page.locator(f':text-is("{target_name}")').first,
    ]

    for strategy in strategies:
        try:
            locator = strategy()
            if locator.is_visible(timeout=3000):
                locator.click()
                logger.info("   ✅ 点击好友: %s", target_name)
                time.sleep(2)
                return True
        except Exception:
            continue
    return False


def list_all_visible_conversations(page: Page) -> list[str]:
    """列出当前可见的所有会话名称（用于调试/检查）"""
    names = []
    text_selectors = [
        '[class*="conversationConversationItem"] [class*="title"]',
        '[class*="ConversationItem"] [class*="title"]',
        '[class*="conversationItem"] [class*="name"]',
        '[class*="chatItem"] [class*="title"]',
    ]

    for sel in text_selectors:
        try:
            elements = page.locator(sel).all()
            for el in elements:
                try:
                    text = el.text_content(timeout=1000)
                    if text and text.strip():
                        names.append(text.strip())
                except Exception:
                    continue
            if names:
                break
        except Exception:
            continue

    return names


def find_and_send(page: Page, targets: list[str], cfg: dict, state_path: str) -> tuple[list[str], list[str]]:
    """滚动查找好友并发送消息"""
    sent = []
    not_found = list(targets)

    # 等待会话列表加载
    logger.info("等待会话列表加载...")
    page.wait_for_timeout(5000)

    # 列出可见会话（调试用）
    visible = list_all_visible_conversations(page)
    if visible:
        logger.info("当前可见会话: %s", visible[:10])

    scroll_count = 0
    while not_found and scroll_count < MAX_SCROLLS:
        # 查找当前可见的好友
        for target in list(not_found):
            if find_target_on_page(page, target):
                # 找到并点击了，现在发送消息
                if _do_send(page, target, cfg):
                    sent.append(target)
                not_found.remove(target)
                # 好友间随机间隔，更像真人操作
                time.sleep(random.uniform(2, 6))

        if not not_found:
            break

        # 滚动加载更多
        logger.debug("滚动会话列表 (%d/%d)...", scroll_count + 1, MAX_SCROLLS)
        has_more = scroll_conversation_list(page)
        if not has_more:
            logger.info("已滚动到底部，未找到: %s", not_found)
            break
        scroll_count += 1

    if not_found:
        logger.warning("以下好友未找到: %s", not_found)
    if sent:
        logger.info("成功发送 %d 条消息", len(sent))

    return sent, not_found


def _do_send(page: Page, target: str, cfg: dict) -> bool:
    """在已点击会话的状态下发送消息"""
    msg = compose_message(target, cfg)
    logger.info("   准备发送 -> %s: %s", target, msg)

    # 查找输入框：优先找 contenteditable，避免匹配到外层容器 div
    input_selectors = [
        '[class*="messageEditor"] [contenteditable="true"]',
        '[class*="chatInput"] [contenteditable="true"]',
        '[contenteditable="true"]',
        'div[role="textbox"]',
        '[class*="inputArea"] [contenteditable="true"]',
    ]

    input_el = None
    for sel in input_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=3000):
                input_el = el
                logger.debug("   输入框选择器命中: %s", sel)
                break
        except Exception:
            continue

    if not input_el:
        logger.warning("   ❌ 未找到输入框 (好友: %s)", target)
        page.screenshot(path=os.path.join(AUTH_DIR, "debug_no_input.png"))
        return False

    try:
        input_el.click()
        time.sleep(0.5)

        # contenteditable 不支持 fill()，用键盘全选后删除来清空
        page.keyboard.press(_SELECT_ALL)
        page.keyboard.press("Backspace")
        page.wait_for_timeout(300)
        # 随机打字速度，更像真人
        input_el.type(msg, delay=random.randint(30, 80))

        # 发送（Enter）
        page.keyboard.press("Enter")
        page.wait_for_timeout(2000)

        logger.info("   ✅ 消息已发送 -> %s", target)
        record_sent(msg)
        return True

    except Exception as e:
        logger.warning("   ❌ 发送失败 (%s): %s", target, e)
        page.screenshot(path=os.path.join(AUTH_DIR, "debug_send_fail.png"))
        return False


def run_tasks(
    page: Page,
    context: BrowserContext,
    account_cfg: dict,
    msg_cfg: dict,
    state_path: str,
) -> bool:
    """执行一个账号的完整续火花任务"""
    # 1. 导航到聊天页
    logger.info("导航到聊天页...")
    page.goto(CHAT_URL, wait_until="domcontentloaded", timeout=120000)
    page.wait_for_timeout(8000)  # 给 JS 渲染更多时间

    # 2. 检查登录（save_debug=True 会在失败时保存截图）
    from core.auth import is_logged_in
    if not is_logged_in(page, save_debug=True):
        logger.error("登录凭证已过期，请运行 python main.py --setup")
        return False

    # 3. 查找好友并发送
    targets = account_cfg.get("targets", [])
    if not targets:
        logger.warning("未配置好友目标，跳过")
        return True

    sent, not_found = find_and_send(page, targets, msg_cfg, state_path)

    # 4. 保存 state（延长有效期）
    try:
        context.storage_state(path=state_path)
        logger.info("登录状态已刷新")
    except Exception as e:
        logger.warning("保存 state 失败: %s", e)

    if not_found:
        logger.info("未找到的好友: %s", not_found)

    return len(not_found) == 0
