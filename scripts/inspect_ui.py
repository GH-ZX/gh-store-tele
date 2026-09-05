"""GH Store UI Visual Inspector.

Captures mobile-first Telegram WebView screenshots (390x844) across:
1. Storefront Home (Grid & List)
2. Live Operations Radar / Orders Activity
3. Wallet & Recharge
4. Settings & Admin Control Center

Outputs screenshots into static/ui_previews/ for visual inspection.
"""
import asyncio
import os
from pathlib import Path


async def capture_views():
    out_dir = Path("static/ui_previews")
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[WARN] playwright not installed. Run: uv pip install playwright && playwright install chromium")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            has_touch=True,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Telegram-iOS/10.0"
        )
        page = await context.new_page()

        for lang in ("ar", "en"):
            url = f"http://127.0.0.1:5000/app?tg_id=7635553403"
            await page.goto(url, wait_until="networkidle")
            await page.evaluate(f"""() => {{
                localStorage.setItem('ghstore_lang', '{lang}');
                if (typeof applyLanguage === 'function') applyLanguage('{lang}');
            }}""")
            await asyncio.sleep(0.5)

            # 1. Store view
            await page.screenshot(path=str(out_dir / f"store_{lang}.png"))

            # 2. Activity / Orders
            await page.evaluate("() => { if (typeof switchTab === 'function') switchTab('orders'); }")
            await asyncio.sleep(0.5)
            await page.screenshot(path=str(out_dir / f"activity_{lang}.png"))

            # 3. Wallet
            await page.evaluate("() => { if (typeof switchTab === 'function') switchTab('wallet'); }")
            await asyncio.sleep(0.5)
            await page.screenshot(path=str(out_dir / f"wallet_{lang}.png"))

            # 4. Settings / Admin
            await page.evaluate("() => { if (typeof switchTab === 'function') switchTab('settings'); }")
            await asyncio.sleep(0.5)
            await page.screenshot(path=str(out_dir / f"settings_{lang}.png"))

            print(f"[OK] Captured 4 mobile views in '{lang}' -> {out_dir}/")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(capture_views())
