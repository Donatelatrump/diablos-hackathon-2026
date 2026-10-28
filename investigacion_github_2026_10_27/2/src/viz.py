"""Tema de visualización compartido (paleta validada, dataviz skill)."""
import plotly.graph_objects as go, plotly.io as pio, json, os

FIGS = '/home/claude/stuffplus/out/figs'
os.makedirs(FIGS, exist_ok=True)

CAT = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
ALT_COLORS = {'No Altitude': '#86b6ef', 'Medium Altitude': '#2a78d6', 'Extreme Altitude': '#0d366b'}  # ordinal, un solo tono
ALT_LABEL = {'No Altitude': 'Nivel del mar', 'Medium Altitude': 'Altitud media', 'Extreme Altitude': 'Altitud extrema (CDMX)'}
DIV_NEG, DIV_MID, DIV_POS = '#2a78d6', '#f0efec', '#e34948'
FAMILY_ORDER = ['Fastball-Ride', 'Fastball-Run', 'Fastball-Cut', 'Sinker', 'Cutter', 'Changeup', 'Slider-Gyro', 'Sweeper', 'Slurve', 'Curveball']
FAMILY_ES = {'Fastball-Ride': 'Recta con ride', 'Fastball-Run': 'Recta con run', 'Fastball-Cut': 'Recta con cut', 'Sinker': 'Sinker',
             'Cutter': 'Cutter', 'Changeup': 'Changeup', 'Slider-Gyro': 'Slider gyro', 'Sweeper': 'Sweeper', 'Slurve': 'Slurve', 'Curveball': 'Curva'}

TEMPLATE = go.layout.Template(layout=dict(
    font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif', size=13, color='#0b0b0b'),
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    xaxis=dict(gridcolor='#e1e0d9', zerolinecolor='#c3c2b7', linecolor='#c3c2b7', tickcolor='#c3c2b7', title_font=dict(color='#52514e'), tickfont=dict(color='#52514e')),
    yaxis=dict(gridcolor='#e1e0d9', zerolinecolor='#c3c2b7', linecolor='#c3c2b7', tickcolor='#c3c2b7', title_font=dict(color='#52514e'), tickfont=dict(color='#52514e')),
    legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color='#52514e')),
    margin=dict(l=60, r=30, t=60, b=60), colorway=CAT, hoverlabel=dict(font=dict(family='system-ui, sans-serif')),
))
pio.templates['stuff'] = TEMPLATE
pio.templates.default = 'stuff'


def save(fig, name, height=420):
    fig.update_layout(height=height)
    with open(f'{FIGS}/{name}.json', 'w') as f:
        f.write(fig.to_json())
    return fig
