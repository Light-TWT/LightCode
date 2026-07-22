from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    page = b.new_page(viewport={'width': 1440, 'height': 900})
    page.goto('http://127.0.0.1:5173', wait_until='networkidle')

    title = page.locator('.page-title')
    assert title.inner_text() == '继续你的工作', f'Expected 继续你的工作, got {title.inner_text()}'

    rows = page.locator('[data-testid=project-row]')
    assert rows.count() == 5
    assert rows.nth(0).locator('.status-badge').inner_text() == '等待审批'
    assert rows.nth(1).locator('.status-badge').inner_text() == '测试通过'

    page.locator('[data-testid=view-all-btn]').click()
    assert page.locator('[data-testid=workspace-drawer]').count() == 1

    items = page.locator('[data-testid=drawer-item]')
    assert items.count() == 7

    page.locator('[data-testid=drawer-search]').fill('cli')
    assert page.locator('[data-testid=drawer-item]:visible').count() == 1

    page.locator('[data-testid=drawer-overlay]').click(force=True)
    assert page.locator('[data-testid=workspace-drawer]').count() == 0

    b.close()
    print('home-browser-check: passed')
