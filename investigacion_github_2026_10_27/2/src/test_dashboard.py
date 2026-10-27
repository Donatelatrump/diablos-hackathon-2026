import asyncio, sys, os
from playwright.async_api import async_playwright
path = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/stuffplus/deliverables/dashboard_stuff_plus_lmb.html'
shots = '/home/claude/stuffplus/out/shots'; os.makedirs(shots, exist_ok=True)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 1280, 'height': 900})
        errs = []
        pg.on('console', lambda m: errs.append(m.text) if m.type in ('error',) else None)
        pg.on('pageerror', lambda e: errs.append('PAGEERROR ' + str(e)))
        await pg.goto('file://' + path); await pg.wait_for_timeout(2500)
        await pg.screenshot(path=f'{shots}/v2_hero.png', full_page=False)
        print('hero', await pg.inner_text('#sp-sea'), '|', await pg.inner_text('#sp-home'))
        await pg.select_option('#family', 'Curveball'); await pg.wait_for_timeout(800)
        print('curve', (await pg.inner_text('#verdict'))[:160])
        await pg.select_option('#family', 'Fastball-Ride'); await pg.wait_for_timeout(500)
        el = await pg.query_selector('#formas'); await el.scroll_into_view_if_needed(); await pg.wait_for_timeout(600)
        await pg.screenshot(path=f'{shots}/v2_formas.png', full_page=False)
        el = await pg.query_selector('#mapa'); await el.scroll_into_view_if_needed(); await pg.wait_for_timeout(2500)
        await pg.screenshot(path=f'{shots}/v2_mapa.png', full_page=False)
        el = await pg.query_selector('#prospecto'); await el.scroll_into_view_if_needed(); await pg.wait_for_timeout(800)
        await pg.screenshot(path=f'{shots}/v2_prospecto.png', full_page=False)
        await pg.screenshot(path=f'{shots}/v2_full.png', full_page=True)
        pm = await b.new_page(viewport={'width': 390, 'height': 844})
        await pm.goto('file://' + path); await pm.wait_for_timeout(2000)
        await pm.screenshot(path=f'{shots}/v2_mobile.png', full_page=False)
        print('mobile scrollWidth', await pm.evaluate('document.documentElement.scrollWidth'))
        print('errors:', errs[:10])
        await b.close()
asyncio.run(main())
