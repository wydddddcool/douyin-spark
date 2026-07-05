import sys, os
sys.path.insert(0, '/app')
from playwright.sync_api import sync_playwright
from core.browser import get_browser, create_context, is_system_chrome_available

state_path = '/app/auth/state.json'
use_system = is_system_chrome_available()
with sync_playwright() as p:
    browser = get_browser(p, headless=True, use_system_chrome=use_system)
    context = create_context(browser, storage_state=state_path)
    page = context.new_page()
    page.goto('https://www.douyin.com/chat', wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(8000)

    candidates = page.locator('[class*="conversationConversationItem"], [class*="ConversationItem"], [data-e2e="chat-item"]').all()
    print(f'got {len(candidates)} candidates via Locator.all()')

    if len(candidates) >= 2:
        el0 = candidates[0]
        el1 = candidates[1]
        # 用 Python-side evaluate，模仿 friends.py
        try:
            pos = el0.evaluate(
                "(el, other) => el.compareDocumentPosition(other)",
                el1,
            )
            print(f'pos el0.contains(el1) = {pos}, & 8 = {pos & 8}')
        except Exception as e:
            print(f'eval failed: {e}')

        # 看看两个元素实际是不是 ancestor
        cls0 = el0.evaluate("(el) => el.className")
        cls1 = el1.evaluate("(el) => el.className")
        print(f'el0 cls: {cls0[:80]}')
        print(f'el1 cls: {cls1[:80]}')

        # 在 page context 里手动比
        manual = page.evaluate("""(els) => {
            const [a, b] = els;
            return {
                aClass: a.className.slice(0,80),
                bClass: b.className.slice(0,80),
                aContainsB: a.compareDocumentPosition(b),
                bContainsA: b.compareDocumentPosition(a),
            };
        }""", [el0.element_handle(), el1.element_handle()])
        print('manual:', manual)

    context.close()
    browser.close()