import numpy as np, pandas as pd, json
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys; sys.path.insert(0, '/home/claude/stuffplus/src')
from viz import save, CAT, ALT_COLORS
OUT = '/home/claude/stuffplus/out'
oof = pd.read_parquet('/home/claude/stuffplus/data/oof.parquet')
df = pd.read_parquet('/home/claude/stuffplus/data/pitches_targets.parquet', columns=['is_whiff', 'is_swing', 'is_gb', 'is_hard', 'is_hr', 'is_bip', 'rv_pitcher_obs'])
m = json.load(open(f'{OUT}/metrics.json'))
scale = json.load(open(f'{OUT}/scale.json'))

# Deciles OOF: Stuff+ y Pitching+ (holdout por pitcher) vs xRV real y whiff real
res = {}
fig = make_subplots(rows=1, cols=3, subplot_titles=('xRunValue real por decil (carreras / 100 pitches)', 'Run value observado por decil', 'Whiff por swing real por decil'))
for name, col, color in [('Stuff+', 'pred_stuff', CAT[0]), ('Pitching+', 'pred_pitching', CAT[1])]:
    dec = pd.qcut(oof[col], 10, labels=False) + 1
    g = pd.DataFrame({'dec': dec, 'xrv': oof.rv_pitcher, 'rvobs': df.rv_pitcher_obs, 'whiff': df.is_whiff, 'swing': df.is_swing}).groupby('dec')
    xrv = 100 * g.xrv.mean(); rvo = 100 * g.rvobs.mean(); wh = g.whiff.sum() / g.swing.sum()
    res[name] = dict(xrv_d1=float(xrv.iloc[0]), xrv_d10=float(xrv.iloc[-1]), whiff_d1=float(wh.iloc[0]), whiff_d10=float(wh.iloc[-1]), rvobs_d1=float(rvo.iloc[0]), rvobs_d10=float(rvo.iloc[-1]))
    fig.add_trace(go.Scatter(x=xrv.index, y=xrv.values, mode='lines+markers', name=name, line=dict(color=color, width=2), marker=dict(size=8), legendgroup=name, hovertemplate='Decil %{x}: %{y:+.2f}<extra>' + name + '</extra>'), row=1, col=1)
    fig.add_trace(go.Scatter(x=rvo.index, y=rvo.values, mode='lines+markers', name=name, line=dict(color=color, width=2), marker=dict(size=8), legendgroup=name, showlegend=False, hovertemplate='Decil %{x}: %{y:+.2f}<extra>' + name + '</extra>'), row=1, col=2)
    fig.add_trace(go.Scatter(x=wh.index, y=100 * wh.values, mode='lines+markers', name=name, line=dict(color=color, width=2), marker=dict(size=8), legendgroup=name, showlegend=False, hovertemplate='Decil %{x}: %{y:.1f}%<extra>' + name + '</extra>'), row=1, col=3)
for c in (1, 2): fig.add_hline(y=0, line_color='#c3c2b7', row=1, col=c)
fig.update_xaxes(title_text='Decil de score (holdout por pitcher)', row=1, col=2)
fig.update_layout(title='Discriminación fuera de muestra: los deciles del score ordenan los resultados reales', legend=dict(orientation='h', y=-0.25, x=0))
save(fig, 'deciles', 400)
json.dump(res, open(f'{OUT}/deciles.json', 'w'), indent=2)
print(res)

# Calibración de cabezas (Pitching+ holdout por pitcher)
fig = make_subplots(rows=1, cols=4, subplot_titles=('P(whiff)', 'P(chase)', 'P(rolling | en juego)', 'P(contacto duro | en juego)'))
for i, h in enumerate(['whiff', 'chase', 'gb', 'hard']):
    c = m[f'calibration_{h}']
    mx = max(max(c['p']), max(c['y'])) * 1.05
    fig.add_trace(go.Scatter(x=[0, mx], y=[0, mx], mode='lines', line=dict(color='#898781', dash='dash'), showlegend=False, hoverinfo='skip'), row=1, col=i + 1)
    fig.add_trace(go.Scatter(x=c['p'], y=c['y'], mode='lines+markers', line=dict(color=CAT[0], width=2), marker=dict(size=8), showlegend=False, hovertemplate='Predicho %{x:.3f} · Observado %{y:.3f}<extra></extra>'), row=1, col=i + 1)
    fig.update_xaxes(title_text='Predicho', row=1, col=i + 1);
fig.update_yaxes(title_text='Observado', row=1, col=1)
fig.update_layout(title='Calibración de las probabilidades (deciles, holdout por pitcher)')
save(fig, 'calibration', 360)

# Tabla de validación
rows = []
for layer, lab in [('stuff', 'Stuff+'), ('location', 'Location+'), ('pitching', 'Pitching+')]:
    for scheme, slab in [('pitcher_holdout', 'Pitcher holdout (5-fold)'), ('season_holdout_2026', 'Season holdout (→2026)'), ('park_holdout_extreme', 'Park holdout (→ CDMX, extrapola)'), ('park_holdout_medium', 'Park holdout (→ media, interpola)')]:
        k = m[f'{layer}_{scheme}']
        rows.append(dict(Modelo=lab, Esquema=slab, RMSE_modelo=k['rmse_model'], RMSE_nulo=k['rmse_null_count'], Mejora_pct=100 * (1 - k['rmse_model'] / k['rmse_null_count']), r=k['corr'], Sesgo=k.get('bias_mean_pred_minus_actual', np.nan)))
val = pd.DataFrame(rows)
val.to_csv(f'{OUT}/validation_table.csv', index=False)
print(val.round(4).to_string())
heads = []
for h, lab in [('whiff', 'P(whiff)'), ('chase', 'P(chase)'), ('called_strike', 'P(strike cantado)'), ('swing', 'P(swing)'), ('gb', 'P(rolling | BIP)'), ('hard', 'P(contacto duro | BIP)'), ('barrel', 'P(barril | BIP)'), ('hr', 'P(HR | BIP)')]:
    k = m[f'head_{h}_pitching_pitcher_holdout']
    heads.append(dict(Target=lab, AUC=k['auc'], LogLoss=k['logloss'], LogLoss_nulo=k['logloss_null_count'], Mejora_pct=100 * (1 - k['logloss'] / k['logloss_null_count']), Tasa_base=k['base_rate'], n=k['n']))
pd.DataFrame(heads).to_csv(f'{OUT}/heads_table.csv', index=False)
print(pd.DataFrame(heads).round(3).to_string())
