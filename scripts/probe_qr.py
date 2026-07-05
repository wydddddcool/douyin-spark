import sys, os
sys.path.insert(0, '/app')
from playwright.sync_api import sync_playwright
from core.browser import get_browser, create_context, is_system_chrome_available

state_path = '/app/auth/state.json'
use_system = is_system_chrome_available()
print('use_system_chrome =', use_system, 'state_exists =', os.path.exists(state_path))

with sync_playwright() as p:
    browser = get_browser(p, headless=True, use_system_chrome=use_system)
    if os.path.exists(state_path):
        context = create_context(browser, storage_state=state_path)
    else:
        context = browser.new_context()
    page = context.new_page()
    page.goto('https://www.douyin.com/chat', wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(8000)
    print('=== URL ===', page.url)
    print('=== Title ===', page.title())
    text = page.locator('body').text_content() or ''
    print('=== body text ===', text[:1500])

    candidates = page.evaluate("""() => {
        const sels = [
            '[class*="qrcode"]', '[class*="QrCode"]', '[class*="QRCode"]',
            '[class*="scanCode"]', '[class*="scan-code"]',
            '[class*="login"]', '[data-e2e*="qr"]', '[data-e2e*="scan"]',
            'canvas',
        ];
        const results = [];
        for (const sel of sels) {
            document.querySelectorAll(sel).forEach(el => {
                const r = el.getBoundingClientRect();
                if (r.width > 50 && r.height > 50 && r.width < 800) {
                    results.push({
                        sel, tag: el.tagName,
                        cls: (el.className && typeof el.className === 'string') ? el.className.slice(0,100) : '',
                        w: Math.round(r.width), h: Math.round(r.height),
                    });
                }
            });
        }
        return results.slice(0, 30);
    }""")
    print('=== QR candidates (50<size<800) ===')
    for c in candidates:
        print(f"  sel={c['sel']!r:50} tag={c['tag']} {c['w']}x{c['h']} cls={c['cls'][:60]}")

    print('=== iframe ===')
    iframes = page.evaluate("() => Array.from(document.querySelectorAll('iframe')).map(f => ({src: f.src.slice(0,80), id: f.id, w: f.getBoundingClientRect().width}))")
    for f in iframes[:5]:
        print(f"  {f}")

    context.close()
    browser.close()