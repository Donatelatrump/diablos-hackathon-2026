"""
02_altitude.py — Cuantificación empírica del efecto altitud (diseño pareado dentro de pitcher × familia).
Salidas: out/altitude_effects.csv, out/altitude_summary.json, figuras JSON.
"""
import numpy as np, pandas as pd, json
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys; sys.path.insert(0, '/home/claude/stuffplus/src')
from viz import save, ALT_COLORS, ALT_LABEL, FAMILY_ORDER, FAMILY_ES, CAT, DIV_NEG, DIV_POS

df = pd.read_parquet('/home/claude/stuffplus/data/pitches.parquet')
MIN_N = 25
LEVELS = ['No Altitude', 'Medium Altitude', 'Extreme Altitude']
VARS = {'RelSpeed': 'Velocidad de salida (mph)', 'SpinRate': 'Spin (rpm)', 'SpeedDrop': 'Pérdida de velocidad al plato (mph)',
        'InducedVertBreak': 'IVB (in)', 'hb_arm': 'HB lado del brazo (in)', 'total_break': 'Movimiento total (in)',
        'VertApprAngle': 'Ángulo vertical de llegada (°)', 'ZoneTime': 'Tiempo al plato (s)', 'break_per_krpm': 'Movimiento por 1000 rpm (in)'}

# ---- 1. Pareado pitcher × familia × altitud ----
g = df.groupby(['pitcher_anon_id', 'pitch_family', 'altitude_category']).agg(n=('RelSpeed', 'size'), **{v: (v, 'mean') for v in VARS}).reset_index()
g = g[g.n >= MIN_N]
rows = []
for fam in FAMILY_ORDER:
    sub = g[g.pitch_family == fam]
    base = sub[sub.altitude_category == 'No Altitude'].set_index('pitcher_anon_id')
    for lvl in ['Medium Altitude', 'Extreme Altitude']:
        alt = sub[sub.altitude_category == lvl].set_index('pitcher_anon_id')
        common = base.index.intersection(alt.index)
        if len(common) < 8: continue
        for v in VARS:
            d = alt.loc[common, v] - base.loc[common, v]
            b = base.loc[common, v].mean()
            w = np.minimum(base.loc[common, 'n'], alt.loc[common, 'n'])
            dm = np.average(d, weights=w); se = d.std() / np.sqrt(len(d))
            rows.append(dict(family=fam, level=lvl, var=v, n_pairs=len(common), base_mean=b, delta=dm, se=se,
                             ci_lo=dm - 1.96 * se, ci_hi=dm + 1.96 * se, pct=100 * dm / b if abs(b) > 0.5 else np.nan))
eff = pd.DataFrame(rows)
eff.to_csv('/home/claude/stuffplus/out/altitude_effects.csv', index=False)

# ---- 2. Resumen físico: ratio de movimiento Magnus observado vs. predicción por densidad ----
rho = {'No Altitude': 0.995, 'Medium Altitude': 0.868, 'Extreme Altitude': 0.802}
summary = {}
for lvl in ['Medium Altitude', 'Extreme Altitude']:
    e = eff[(eff.level == lvl) & (eff['var'] == 'total_break')]
    # ratio ponderado por pares: (base+delta)/base
    ratio = np.average((e.base_mean + e.delta) / e.base_mean, weights=e.n_pairs)
    sd = eff[(eff.level == lvl) & (eff['var'] == 'SpeedDrop')]
    sd_ratio = np.average((sd.base_mean + sd.delta) / sd.base_mean, weights=sd.n_pairs)
    rs = eff[(eff.level == lvl) & (eff['var'] == 'RelSpeed')]
    sp = eff[(eff.level == lvl) & (eff['var'] == 'SpinRate')]
    summary[lvl] = dict(rho_rel_pred=rho[lvl] / rho['No Altitude'], break_ratio_obs=round(ratio, 3), speeddrop_ratio_obs=round(sd_ratio, 3),
                        relspeed_delta=round(np.average(rs.delta, weights=rs.n_pairs), 3), spin_delta=round(np.average(sp.delta, weights=sp.n_pairs), 1))
# altitud implícita de "Medium": invertir ISA sobre el ratio de break observado
def alt_from_rho(r):
    return (1 - r ** (1 / 4.2559)) / 2.25577e-5
r_med = summary['Medium Altitude']['break_ratio_obs'] * 0.995
summary['Medium Altitude']['implied_altitude_m'] = round(float(alt_from_rho(r_med)), 0)
r_ext = summary['Extreme Altitude']['break_ratio_obs'] * 0.995
summary['Extreme Altitude']['implied_altitude_m'] = round(float(alt_from_rho(r_ext)), 0)

# ---- 3. Outcomes de bateo por altitud ----
bip = df[df.is_bip == 1]
out = df.groupby('altitude_category').agg(pitches=('is_swing', 'size'), swing=('is_swing', 'mean'), whiff_per_swing=('is_whiff', lambda s: s.sum() / df.loc[s.index, 'is_swing'].sum()),
                                           called_strike=('is_called_strike', 'mean'), chase=('is_chase', 'mean'), hr_per_pitch=('is_hr', 'mean'))
bo = bip.groupby('altitude_category').agg(bip=('is_hr', 'size'), hr_per_bip=('is_hr', 'mean'), gb=('is_gb', 'mean'), hard=('is_hard', 'mean'), barrel=('is_barrel', 'mean'),
                                           ev=('ExitSpeed', 'mean'), weak=('is_weak', 'mean'))
fbs = bip[bip.hit_type == 'FlyBall'].groupby('altitude_category').agg(fb_dist=('Distance', 'mean'), hr_per_fb=('is_hr', 'mean'), fb_ev=('ExitSpeed', 'mean'))
outcomes = out.join(bo).join(fbs).loc[LEVELS]
outcomes.to_csv('/home/claude/stuffplus/out/altitude_outcomes.csv')
summary['outcomes'] = outcomes.round(4).to_dict(orient='index')

# Distancia de fly ball controlando EV y ángulo (misma pelota, distinto aire)
fb = bip[(bip.hit_type.isin(['FlyBall', 'LineDrive'])) & bip.Distance.notna() & bip.ExitSpeed.between(90, 110) & bip.Angle.between(20, 35)]
dist_ctrl = fb.groupby('altitude_category').Distance.agg(['mean', 'count', 'std']).loc[LEVELS]
dist_ctrl['se'] = dist_ctrl['std'] / np.sqrt(dist_ctrl['count'])
summary['fb_distance_controlled'] = dist_ctrl.round(1).to_dict(orient='index')
# HR por bola elevada a EV/LA controlados (riesgo adicional)
hr_ctrl = bip[bip.ExitSpeed.between(95, 110) & bip.Angle.between(20, 40)].groupby('altitude_category').is_hr.agg(['mean', 'count']).loc[LEVELS]
summary['hr_rate_controlled_95_110_20_40'] = hr_ctrl.round(4).to_dict(orient='index')
# GB vs run prevention por altitud (H3): corr entre GB% del pitcher y carreras permitidas por 100 pitches
pg = df.groupby(['pitcher_anon_id', 'altitude_category']).agg(n=('is_hr', 'size'), gb=('is_gb', 'mean'), runs=('RunsScored', 'sum'), hr=('is_hr', 'sum'), bip=('is_bip', 'sum')).reset_index()
pg = pg[(pg.n >= 300) & (pg.bip >= 60)]
pg['runs_per100'] = 100 * pg.runs / pg.n; pg['hr_per_bip'] = pg.hr / pg.bip
h3 = pg.groupby('altitude_category').apply(lambda s: pd.Series(dict(n_pitchers=len(s), corr_gb_runs=s.gb.corr(s.runs_per100), corr_gb_hr=s.gb.corr(s.hr_per_bip)))).loc[LEVELS]
summary['H3_gb_corr'] = h3.round(3).to_dict(orient='index')
json.dump(summary, open('/home/claude/stuffplus/out/altitude_summary.json', 'w'), indent=2, default=float)
print(json.dumps(summary, indent=2, default=float))

# ---- 4. Figuras ----
# Fig A: Δ movimiento (IVB y HB) por familia, nivel del mar -> altitud extrema, con IC
e = eff[(eff.level == 'Extreme Altitude') & eff['var'].isin(['InducedVertBreak', 'hb_arm'])]
fig = go.Figure()
fams = [f for f in FAMILY_ORDER if f in e.family.unique()]
for i, (v, lab, col) in enumerate([('InducedVertBreak', 'Δ IVB', CAT[0]), ('hb_arm', 'Δ HB (lado del brazo)', CAT[1])]):
    s = e[e['var'] == v].set_index('family').loc[fams]
    fig.add_trace(go.Bar(name=lab, x=[FAMILY_ES[f] for f in fams], y=s.delta, marker_color=col,
                         error_y=dict(type='data', array=1.96 * s.se, color='#52514e', thickness=1.5, width=4),
                         text=[f'{d:+.1f}"' for d in s.delta], textposition='outside', textfont=dict(color='#0b0b0b', size=11),
                         customdata=np.stack([s.base_mean, s.pct, s.n_pairs], axis=1),
                         hovertemplate='%{x}<br>' + lab + ': %{y:+.2f} in<br>Base nivel del mar: %{customdata[0]:.1f} in<br>Cambio: %{customdata[1]:+.0f}%<br>Pares pitcher: %{customdata[2]}<extra></extra>'))
fig.update_layout(title='Cambio de movimiento del mismo pitcher al lanzar en altitud extrema (vs. nivel del mar)', barmode='group',
                  yaxis_title='Δ pulgadas (IC 95%)', legend=dict(orientation='h', y=1.08, x=0), bargap=0.25)
fig.add_hline(y=0, line_color='#c3c2b7')
save(fig, 'alt_delta_movement', 460)

# Fig B: Ratio de movimiento observado vs predicción por densidad, en los tres niveles
fig = go.Figure()
xs = [0, 1, 2]
pred = [1.0, rho['Medium Altitude'] / 0.995, rho['Extreme Altitude'] / 0.995]
obs = [1.0, summary['Medium Altitude']['break_ratio_obs'], summary['Extreme Altitude']['break_ratio_obs']]
sdr = [1.0, summary['Medium Altitude']['speeddrop_ratio_obs'], summary['Extreme Altitude']['speeddrop_ratio_obs']]
fig.add_trace(go.Scatter(x=xs, y=pred, mode='lines+markers', name='Predicción física (∝ densidad del aire, ISA)', line=dict(color='#898781', dash='dash', width=2), marker=dict(size=9)))
fig.add_trace(go.Scatter(x=xs, y=obs, mode='lines+markers+text', name='Movimiento total observado (pareado)', line=dict(color=CAT[0], width=2), marker=dict(size=9), text=[f'{o:.2f}' for o in obs], textposition='bottom right'))
fig.add_trace(go.Scatter(x=xs, y=sdr, mode='lines+markers+text', name='Pérdida de velocidad observada (drag)', line=dict(color=CAT[1], width=2), marker=dict(size=9), text=[f'{o:.2f}' for o in sdr], textposition='top left'))
fig.update_layout(title='La física predice el dato: movimiento y drag caen con la densidad del aire', xaxis=dict(tickvals=xs, ticktext=['Nivel del mar', 'Altitud media', 'Altitud extrema (CDMX)']),
                  yaxis=dict(title='Ratio vs. nivel del mar', range=[0.7, 1.05]), legend=dict(orientation='h', y=-0.2, x=0))
save(fig, 'alt_physics_ratio', 440)

# Fig C: chequeo de calibración: velocidad de salida y spin no cambian
e2 = eff[(eff.level == 'Extreme Altitude') & eff['var'].isin(['RelSpeed', 'SpinRate', 'SpeedDrop'])]
fig = make_subplots(rows=1, cols=3, subplot_titles=('Δ velocidad de salida (mph)', 'Δ spin (rpm)', 'Δ pérdida de velocidad al plato (mph)'), horizontal_spacing=0.08)
for i, v in enumerate(['RelSpeed', 'SpinRate', 'SpeedDrop']):
    s = e2[e2['var'] == v].set_index('family').loc[fams]
    fig.add_trace(go.Bar(x=[FAMILY_ES[f] for f in fams], y=s.delta, marker_color=CAT[0] if v != 'SpeedDrop' else CAT[1], error_y=dict(type='data', array=1.96 * s.se, color='#52514e', thickness=1.5, width=3), showlegend=False,
                         hovertemplate='%{x}: %{y:+.2f}<extra></extra>'), row=1, col=i + 1)
    fig.add_hline(y=0, line_color='#c3c2b7', row=1, col=i + 1)
fig.update_layout(title='Chequeo de calibración: lo que el pitcher controla no cambia; lo que el aire controla sí', bargap=0.3)
fig.update_xaxes(tickangle=-40, tickfont=dict(size=10))
save(fig, 'alt_calibration_check', 460)

# Fig D: outcomes de bateo
labels = ['HR por bola en juego', 'Contacto duro (EV≥95) por BIP', 'Rolling por BIP', 'Whiff por swing']
vals = {lvl: [outcomes.loc[lvl, 'hr_per_bip'], outcomes.loc[lvl, 'hard'], outcomes.loc[lvl, 'gb'], outcomes.loc[lvl, 'whiff_per_swing']] for lvl in LEVELS}
fig = go.Figure()
for lvl in LEVELS:
    fig.add_trace(go.Bar(name=ALT_LABEL[lvl], x=labels, y=[100 * v for v in vals[lvl]], marker_color=ALT_COLORS[lvl], text=[f'{100*v:.1f}%' for v in vals[lvl]], textposition='outside', textfont=dict(size=11, color='#0b0b0b'),
                         hovertemplate='%{x}<br>' + ALT_LABEL[lvl] + ': %{y:.1f}%<extra></extra>'))
fig.update_layout(title='Resultados del bateo por nivel de altitud', barmode='group', yaxis_title='%', legend=dict(orientation='h', y=1.08, x=0), bargap=0.25)
save(fig, 'alt_outcomes', 440)

# Fig E: distancia de fly ball controlada por EV/LA
fig = go.Figure()
fig.add_trace(go.Bar(x=[ALT_LABEL[l] for l in LEVELS], y=dist_ctrl['mean'], marker_color=[ALT_COLORS[l] for l in LEVELS],
                     error_y=dict(type='data', array=1.96 * dist_ctrl['se'], color='#52514e', thickness=1.5, width=4),
                     text=[f'{m:.0f} ft' for m in dist_ctrl['mean']], textposition='outside', textfont=dict(color='#0b0b0b'),
                     hovertemplate='%{x}<br>Distancia media: %{y:.0f} ft<extra></extra>'))
fig.update_layout(title='Misma pelota, distinto aire: distancia de batazos elevados con EV 90–110 mph y ángulo 20–35°', yaxis=dict(title='Distancia (ft)', range=[250, 380]), bargap=0.4)
save(fig, 'alt_fb_distance', 400)
print(eff[(eff.level == 'Extreme Altitude') & eff['var'].isin(['InducedVertBreak', 'hb_arm', 'total_break'])].pivot(index='family', columns='var', values=['base_mean', 'delta', 'pct']).round(2).to_string())
