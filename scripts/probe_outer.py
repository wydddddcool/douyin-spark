import sys, os
sys.path.insert(0, '/app')
from playwright.sync_api import sync_playwright
from core.browser import get_browser, create_context, is_system_chrome_available

state_path = '/app/auth/state.json'
print('state_exists =', os.path.exists(state_path))

use_system = is_system_chrome_available()
with sync_playwright() as p:
    browser = get_browser(p, headless=True, use_system_chrome=use_system)
    context = create_context(browser, storage_state=state_path)
    page = context.new_page()
    page.goto('https://www.douyin.com/chat', wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(8000)

    # 完全复刻 friends.py 里的逻辑，但打印每一步
    info = page.evaluate("""() => {
        const sels = [
            '[class*="conversationConversationItem"]',
            '[class*="ConversationItem"]',
            '[data-e2e="chat-item"]',
        ];
        const scope = document.querySelector('[class*="conversationConversationList"]') || document.body;
        const all = [];
        for (const sel of sels) {
            scope.querySelectorAll(sel).forEach(el => {
                all.push({sel, el});
            });
        }
        const n = all.length;
        console.log('total candidates:', n);

        const outermost = [];
        const classes = {};
        for (let i = 0; i < n; i++) {
            const el_i = all[i].el;
            const cls = (el_i.className && typeof el_i.className === 'string') ? el_i.className.slice(0, 60) : '';
            classes[cls] = (classes[cls] || 0) + 1;

            let is_outer = true;
            let ancestorIdx = -1;
            for (let j = 0; j < n; j++) {
                if (i === j) continue;
                const el_j = all[j].el;
                const pos = el_i.compareDocumentPosition(el_j);
                // pos & 8 (CONTAINS) means el_j is descendant of el_i
                if (pos & 8) {
                    is_outer = false;
                    ancestorIdx = j;
                    break;
                }
            }
            if (is_outer) outermost.push({i, sel: all[i].sel, cls});
            else if (outermost.length < 5) {
                // log the inner ones too for first 5
                outermost.push({i, sel: all[i].sel, cls, isInner: true, ancestorIdx});
            }
        }
        return {n, outermost: outermost.slice(0, 30), classes};
    }""")

    print('total candidates:', info['n'])
    print('class breakdown:')
    for c, n in sorted(info['classes'].items(), key=lambda x: -x[1])[:10]:
        print(f'  count={n:3d}  cls={c!r}')
    print('---')
    print('outermost (first 30):')
    for o in info['outermost'][:30]:
        print(f"  i={o['i']:3d} sel={o['sel'][:50]:50} cls={o.get('cls','')[:60]} {'INNER->'+str(o.get('ancestorIdx')) if o.get('isInner') else 'OUTER'}")

    context.close()
    browser.close()