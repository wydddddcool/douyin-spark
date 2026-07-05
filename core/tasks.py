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

_MSG_SELECTORS = [
    '[class*="MessageItem"]',
    '[class*="messageItem"]',
    '[class*="chatMessage"]',
    '[class*="bubble"]',
    '[data-e2e="message-item"]',
    '[class*="contentItem"]',
]


def _get_latest_messages(page: Page, n: int = 10) -> list:
    """从聊天记录里拉最新的 n 条消息文本"""
    for sel in _MSG_SELECTORS:
        try:
            els = page.locator(sel).all()
            if els:
                texts = []
                for e in els[:n]:
                    try:
                        t = e.text_content(timeout=1000)
                        if t and t.strip():
                            texts.append(t.strip())
                    except Exception:
                        pass
                if texts:
                    return texts
        except Exception:
            continue
    return []


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
    """在当前页面上查找目标好友，返回是否找到并点击。

    抖音会话列表里同一个好友会出现两次：
      - 完整文本："cc不想熬夜 346 17分钟前"
      - 纯昵称短版本："cc不想熬夜"
    所以 config 里只存稳定昵称（如"cc不想熬夜"），匹配时按多级降级策略：

      1. 精确匹配纯昵称（最高优先级，能精准点击短文本节点）
      2. 包含匹配（target 出现在 title 文本里）
      3. startsWith 匹配（兜底，处理 emoji 昵称等边界情况）
    """
    escaped = target_name.replace('"', '\\"')

    # 策略 1：精确匹配（优先命中抖音渲染的"纯昵称短版本"）
    strategy_exact = lambda: page.get_by_text(target_name, exact=True).first
    # 策略 2：包含匹配（target 出现在 title 里）
    strategy_contains = lambda: page.locator(f'text="{escaped}"').first
    # 策略 3：包含语法的 locator
    strategy_has_text = lambda: page.locator(f':has-text("{escaped}")').first

    strategies = [strategy_exact, strategy_contains, strategy_has_text]

    for idx, strategy in enumerate(strategies, 1):
        try:
            locator = strategy()
            if locator.is_visible(timeout=3000):
                locator.click()
                logger.info("   ✅ 点击好友: %s (命中策略 %d)", target_name, idx)
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
        page.wait_for_timeout(3000)

        # 验证：检查最新消息里有没有我们发的内容
        latest_msgs = _get_latest_messages(page, n=15)
        msg_in_chat = any(msg in t for t in latest_msgs) if latest_msgs else False

        if msg_in_chat:
            logger.info("   ✅ 消息已发送 -> %s", target)
            record_sent(msg)
            return True
        else:
            # 没出现在聊天记录里 = 被拦截/发送失败
            logger.warning("   ❌ 消息发送后未出现在聊天记录，可能被拦截 (%s)", target)
            logger.debug("   最新消息: %s", [t[:40] for t in latest_msgs[:5]])
            page.screenshot(path=os.path.join(AUTH_DIR, "debug_send_not_delivered.png"))
            return False

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

    send_failed = [t for t in targets if t not in sent and t not in not_found]
    if send_failed:
        logger.warning("发送失败的好友: %s", send_failed)

    all_ok = len(sent) == len(targets)
    return all_ok
