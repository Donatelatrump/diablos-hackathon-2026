"""Utilidades para armar el reporte técnico HTML (figuras Plotly embebidas, tablas, estilos de impresión)."""
import json, os, pandas as pd
FIGS = '/home/claude/stuffplus/out/figs'
_fig_counter = [0]


def fig(name, caption='', height=None):
    """Figura Plotly embebida (render en el navegador; en PDF se imprime vía Chromium)."""
    j = json.load(open(f'{FIGS}/{name}.json'))
    if height: j['layout']['height'] = height
    _fig_counter[0] += 1
    i = _fig_counter[0]
    h = j['layout'].get('height', 420)
    j['layout']['font'] = dict(family='system-ui, -apple-system, "Segoe UI", sans-serif', size=12, color='#0b0b0b')
    return f'''<figure class="fig"><div id="fig{i}" style="height:{h}px"></div>
<script>Plotly.newPlot("fig{i}", {json.dumps(j["data"])}, {json.dumps(j["layout"])}, {{displayModeBar:false, responsive:true, staticPlot:false}});</script>
<figcaption><b>Figura {i}.</b> {caption}</figcaption></figure>'''


def table(df: pd.DataFrame, caption='', fmt=None, index=True, cls=''):
    fmt = fmt or {}
    d = df.copy()
    for c in d.columns:
        if c in fmt: d[c] = d[c].map(lambda v: fmt[c].format(v) if pd.notna(v) else '—')
        elif d[c].dtype.kind == 'f': d[c] = d[c].map(lambda v: f'{v:.2f}' if pd.notna(v) else '—')
    html = d.to_html(index=index, escape=False, border=0, classes='tbl ' + cls)
    cap = f'<div class="tcap">{caption}</div>' if caption else ''
    return f'<div class="tblwrap">{cap}{html}</div>'


CSS = """
:root{--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--line:#e1e0d9;--surface:#fcfcfb;--soft:#f3f2ee;--accent:#b3202c;--blue:#2a78d6;--orange:#eb6834}
*{box-sizing:border-box}
html,body{margin:0;background:#fff;color:var(--ink);font:14.5px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
.page{max-width:900px;margin:0 auto;padding:40px 44px}
h1{font-size:30px;line-height:1.15;margin:0 0 6px;letter-spacing:-.02em}
h2{font-size:21px;margin:38px 0 10px;padding-top:14px;border-top:2px solid var(--ink);letter-spacing:-.01em;break-after:avoid}
h3{font-size:16px;margin:22px 0 6px;break-after:avoid}
p{margin:8px 0}
.lead{font-size:16px;color:var(--ink2)}
.meta{color:var(--ink2);font-size:13px;margin-bottom:24px}
.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:18px 0}
.kpi{background:var(--soft);border-radius:10px;padding:14px 16px}
.kpi .v{font-size:30px;font-weight:800;letter-spacing:-.03em;line-height:1.05}
.kpi .k{font-size:13px;color:var(--ink2);margin-top:4px}
.callout{border-left:4px solid var(--accent);background:var(--soft);padding:12px 16px;border-radius:0 10px 10px 0;margin:16px 0}
.callout.blue{border-color:var(--blue)}
.fig{margin:18px 0;break-inside:avoid}
figcaption{font-size:12.5px;color:var(--ink2);margin-top:4px}
.tblwrap{margin:14px 0;break-inside:avoid;overflow-x:auto}
.tcap{font-size:12.5px;color:var(--ink2);margin-bottom:4px;font-weight:600}
table.tbl{border-collapse:collapse;width:100%;font-size:12.5px;font-variant-numeric:tabular-nums}
table.tbl th{text-align:right;color:var(--ink2);font-weight:600;border-bottom:1.5px solid var(--ink);padding:5px 7px;font-size:11.5px;text-transform:uppercase;letter-spacing:.03em}
table.tbl td{text-align:right;border-bottom:1px solid var(--line);padding:5px 7px}
table.tbl th:first-child,table.tbl td:first-child,table.tbl tbody th{text-align:left}
table.tbl tbody th{font-weight:600;color:var(--ink);text-transform:none;letter-spacing:0;font-size:12.5px;border-bottom:1px solid var(--line)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media (max-width:700px){.two,.kpis{grid-template-columns:1fr}}
.eq{background:var(--soft);padding:10px 14px;border-radius:8px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;white-space:pre;overflow-x:auto;margin:10px 0}
ul,ol{padding-left:22px} li{margin:3px 0}
.small{font-size:12.5px;color:var(--ink2)}
.toc{columns:2;font-size:13px;color:var(--ink2);margin:10px 0 0} .toc div{margin:2px 0}
.tag{display:inline-block;background:var(--soft);border-radius:999px;padding:1px 9px;font-size:12px;color:var(--ink2);margin-right:4px}
.good{color:#006300;font-weight:600}.bad{color:#b3202c;font-weight:600}
.cover{display:flex;flex-direction:column;gap:6px;padding-bottom:22px;border-bottom:1px solid var(--line);margin-bottom:22px}
.brand{display:flex;align-items:center;gap:10px;color:var(--ink2);font-size:13px}
.brand i{display:inline-grid;place-items:center;width:30px;height:30px;border-radius:7px;background:var(--accent);color:#fff;font-weight:800;font-style:normal}
@page{size:A4;margin:16mm 14mm}
@media print{.page{padding:0;max-width:none} h2{break-before:auto;margin:22px 0 6px;font-size:17px;padding-top:8px} h3{font-size:13.5px;margin:12px 0 4px} .fig,.kpis,.callout{break-inside:avoid} .tblwrap{break-inside:auto} table.tbl tr{break-inside:avoid} .fig{margin:6px 0} body{font-size:11px;line-height:1.4} p{margin:5px 0} .kpi{padding:8px 10px} .kpi .v{font-size:22px} .kpi .k{font-size:11px} h1{font-size:24px} .lead{font-size:13px} table.tbl{font-size:10px} table.tbl td,table.tbl th{padding:3px 5px} figcaption{font-size:10.5px} .eq{font-size:9.5px;padding:6px 10px;white-space:pre-wrap} .toc{font-size:11px} li{margin:1px 0} .meta{margin-bottom:10px} .cover{padding-bottom:10px;margin-bottom:10px}}
"""


def shell(title, body, subtitle=''):
    return f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<script src="__PLOTLY__"></script><style>{CSS}</style></head><body><div class="page">{body}</div></body></html>'''
