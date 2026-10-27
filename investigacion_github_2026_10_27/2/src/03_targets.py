"""
03_targets.py — Linear weights derivados de la LMB, run expectancy por conteo, run value por pitch y xRunValue.
Salida: data/pitches_targets.parquet, out/linear_weights.json, out/re_count.csv
"""
import numpy as np, pandas as pd, json
import lightgbm as lgb
import plotly.graph_objects as go
import sys; sys.path.insert(0, '/home/claude/stuffplus/src')
from viz import save, ALT_COLORS, ALT_LABEL, CAT

df = pd.read_parquet('/home/claude/stuffplus/data/pitches.parquet')

# ---------- 1. Evento terminal de cada PA ----------
pr = df.play_result.astype(str)
df['pa_event'] = np.select(
    [pr == 'Single', pr == 'Double', pr == 'Triple', pr == 'HomeRun', pr == 'Walk', pr == 'HitByPitch', pr == 'Strikeout',
     pr == 'Error', pr.isin(['Out', 'FieldersChoice', 'Sacrifice'])],
    ['1B', '2B', '3B', 'HR', 'BB', 'HBP', 'K', 'ROE', 'OUT'], default=None)
df['is_terminal'] = df.pa_event.notna().astype(int)

# ---------- 2. Linear weights por regresión de carreras por media entrada ----------
half = df.groupby(['game_anon_id', 'Inning', 'Top/Bottom'], observed=True)
events = ['1B', '2B', '3B', 'HR', 'BB', 'HBP', 'K', 'ROE', 'OUT']
X = pd.DataFrame({e: half.pa_event.apply(lambda s, e=e: (s == e).sum()) for e in events})
y = half.RunsScored.sum()
# incluir sólo medias entradas completas (3 outs registrados) para evitar sesgo de truncamiento
outs = half.OutsOnPlay.sum()
complete = outs >= 3
Xc, yc = X[complete], y[complete]
from numpy.linalg import lstsq
coef, *_ = lstsq(Xc.values.astype(float), yc.values.astype(float), rcond=None)
lw_abs = dict(zip(events, coef))
# Normalizar: valor relativo al PA promedio (promedio ponderado por frecuencia = 0)
freq = df[df.is_terminal == 1].pa_event.value_counts(normalize=True)
avg = sum(lw_abs[e] * freq.get(e, 0) for e in events)
lw = {e: lw_abs[e] - avg for e in events}
json.dump(dict(absolute=lw_abs, relative=lw, n_half_innings=int(complete.sum()), avg_pa=avg), open('/home/claude/stuffplus/out/linear_weights.json', 'w'), indent=2)
print('Linear weights (relativos al PA promedio):', {k: round(v, 3) for k, v in lw.items()})

# ---------- 3. Run expectancy por conteo ----------
df['pa_lw'] = df.groupby('pa_key').pa_event.transform('last').map(lw)  # outcome final del PA (último pitch ordenado)
# PAs sin evento terminal (truncados) se excluyen de RE
valid_pa = df.groupby('pa_key').is_terminal.transform('max') == 1
re_count = df[valid_pa].groupby('count').pa_lw.mean()
re_count = re_count.reindex([f'{b}-{s}' for b in range(4) for s in range(3)]).dropna()
re_count.to_csv('/home/claude/stuffplus/out/re_count.csv')
print('RE por conteo:', re_count.round(3).to_dict())

# ---------- 4. Run value por pitch (perspectiva del bateador: + = malo para el pitcher) ----------
df['re_before'] = df['count'].map(re_count)
pc = df.PitchCall.astype(str)
b, s = df.Balls.astype(int), df.Strikes.astype(int)
nb = np.where(pc.isin(['BallCalled', 'BallinDirt']), b + 1, b)
ns = np.where(pc.isin(['StrikeCalled', 'StrikeSwinging']), s + 1, np.where(pc.str.startswith('Foul') & (s < 2), s + 1, s))
nb = np.clip(nb, 0, 3); ns = np.clip(ns, 0, 2)
next_count = pd.Series([f'{x}-{y}' for x, y in zip(nb, ns)], index=df.index)
re_after = next_count.map(re_count)
# bola 4 / strike 3 sin evento terminal (no debería pasar, pero por seguridad)
re_after = np.where((nb == 4) | (pc.isin(['BallCalled', 'BallinDirt']) & (b == 3)), lw['BB'], re_after)
re_after = np.where((pc.isin(['StrikeCalled', 'StrikeSwinging'])) & (s == 2), lw['K'], re_after)
df['rv_obs'] = np.where(df.is_terminal == 1, df.pa_event.map(lw) - df.re_before, re_after - df.re_before)
df = df[df.rv_obs.notna()].copy()

# ---------- 5. xRunValue: para bolas en juego, valor esperado dado EV, ángulo, dirección y altitud ----------
bip = df[(df.is_bip == 1) & df.has_ev].copy()
feats_bb = ['ExitSpeed', 'Angle', 'Direction', 'alt_level']
Xb = bip[feats_bb].fillna(bip[feats_bb].median())
yb = bip.pa_event.map(lw)
m = lgb.LGBMRegressor(n_estimators=400, learning_rate=0.05, num_leaves=31, min_child_samples=100, subsample=0.8, subsample_freq=1, colsample_bytree=0.9, verbose=-1)
m.fit(Xb, yb)
bip['xlw'] = m.predict(Xb)
print('xLW batted-ball model R2 (in-sample):', round(1 - ((yb - bip.xlw) ** 2).mean() / yb.var(), 3))
df['xlw_bip'] = np.nan; df.loc[bip.index, 'xlw_bip'] = bip.xlw
df['rv_x'] = np.where(df.xlw_bip.notna(), df.xlw_bip - df.re_before, df.rv_obs)
# Objetivo para el pitcher: + = bueno para el pitcher
df['rv_pitcher'] = -df.rv_x
df['rv_pitcher_obs'] = -df.rv_obs
m.booster_.save_model('/home/claude/stuffplus/out/models/xlw_bip.txt')

# ---------- 6. Prueba directa de H3: valor de carrera por tipo de batazo y altitud ----------
h3 = df[df.is_bip == 1].groupby(['altitude_category', 'hit_type'], observed=True).rv_obs.agg(['mean', 'count']).reset_index()
h3 = h3[h3.hit_type.isin(['GroundBall', 'FlyBall', 'LineDrive', 'Popup'])]
h3.to_csv('/home/claude/stuffplus/out/h3_rv_by_hittype.csv', index=False)
print(h3.pivot(index='hit_type', columns='altitude_category', values='mean').round(3))
# Figura
fig = go.Figure()
order = ['GroundBall', 'LineDrive', 'FlyBall', 'Popup']; es = {'GroundBall': 'Rolling', 'LineDrive': 'Línea', 'FlyBall': 'Elevado', 'Popup': 'Pop-up'}
for lvl in ['No Altitude', 'Medium Altitude', 'Extreme Altitude']:
    sub = h3[h3.altitude_category == lvl].set_index('hit_type').reindex(order)
    fig.add_trace(go.Bar(name=ALT_LABEL[lvl], x=[es[o] for o in order], y=sub['mean'], marker_color=ALT_COLORS[lvl], text=[f'{v:+.3f}' for v in sub['mean']], textposition='outside', textfont=dict(size=11, color='#0b0b0b'),
                         hovertemplate='%{x}<br>' + ALT_LABEL[lvl] + ': %{y:+.3f} carreras<extra></extra>'))
fig.add_hline(y=0, line_color='#c3c2b7')
fig.update_layout(title='Costo en carreras de cada tipo de batazo (run value observado, perspectiva del bateador)', barmode='group', yaxis_title='Carreras por bola en juego', legend=dict(orientation='h', y=1.08, x=0), bargap=0.25)
save(fig, 'h3_rv_hittype', 420)

# RE por conteo figura
fig = go.Figure(go.Bar(x=re_count.index, y=re_count.values, marker_color=[CAT[0] if v >= 0 else CAT[1] for v in re_count.values], text=[f'{v:+.3f}' for v in re_count.values], textposition='outside', textfont=dict(size=10, color='#0b0b0b'),
                       hovertemplate='Conteo %{x}: %{y:+.3f} carreras vs. PA promedio<extra></extra>'))
fig.add_hline(y=0, line_color='#c3c2b7')
fig.update_layout(title='Run expectancy por conteo derivada de la LMB (carreras sobre el PA promedio)', yaxis_title='Carreras', xaxis_title='Conteo (bolas-strikes)')
save(fig, 're_count', 380)

df.to_parquet('/home/claude/stuffplus/data/pitches_targets.parquet', index=False)
print('rv_pitcher: mean', round(df.rv_pitcher.mean(), 4), 'sd', round(df.rv_pitcher.std(), 4), '| obs sd', round(df.rv_pitcher_obs.std(), 4))
print(df.groupby('altitude_category').rv_pitcher.mean().round(4))
