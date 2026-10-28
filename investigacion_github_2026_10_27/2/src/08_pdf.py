import asyncio, os
from playwright.async_api import async_playwright
DEL = '/home/claude/stuffplus/deliverables'; shots = '/home/claude/stuffplus/out/shots'

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 1000, 'height': 1400})
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto('file://' + f'{DEL}/reporte_tecnico_stuff_plus_lmb.html')
        await pg.wait_for_timeout(4000)
        await pg.screenshot(path=f'{shots}/report_top.png', full_page=False)
        h = await pg.evaluate('document.body.scrollHeight'); print('page height px', h)
        await pg.set_viewport_size({'width': 720, 'height': 1100})
        await pg.emulate_media(media='print')
        await pg.evaluate('''() => { document.querySelectorAll('.fig > div').forEach(d => { const multi = !!(d.layout && d.layout.xaxis2); const rot = d.layout && d.layout.xaxis && d.layout.xaxis.tickangle; const hbar = d.data && d.data[0] && d.data[0].orientation === 'h'; const square = !!(d.layout && d.layout.yaxis && d.layout.yaxis.scaleanchor); const h = hbar ? 330 : (multi || square) ? 300 : 235; d.style.height=h+'px'; const w = d.parentElement.clientWidth; const hasLegendBelow = d.layout && d.layout.legend && d.layout.legend.y !== undefined && d.layout.legend.y < 0; Plotly.relayout(d, {height: h, width: w, 'font.size': 9.5, 'title.text': '', 'margin.t': multi ? 28 : 16, 'margin.b': hasLegendBelow ? 78 : (rot ? 70 : 40), 'margin.l': hbar ? 150 : 46, 'margin.r': 16, 'yaxis.scaleanchor': null}); }); }''')
        await pg.wait_for_timeout(2500)
        await pg.pdf(path=f'{DEL}/reporte_tecnico_stuff_plus_lmb.pdf', format='A4', print_background=True, margin={'top': '14mm', 'bottom': '14mm', 'left': '12mm', 'right': '12mm'}, prefer_css_page_size=False)
        print('errors', errs)
        await b.close()
asyncio.run(main())
