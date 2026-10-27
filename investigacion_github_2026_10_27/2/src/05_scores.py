"""
05_scores.py — Escala Stuff+/Location+/Pitching+, scores por pitch/pitcher/arsenal, Δ CDMX vs nivel del mar,
sensibilidad por pitcher, SHAP y perfil físico ideal, estabilidad año a año.
"""
import numpy as np, pandas as pd, json, warnings
import lightgbm as lgb, shap
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys; sys.path.insert(0, '/home/claude/stuffplus/src')
from viz import save, ALT_COLORS, ALT_LABEL, FAMILY_ORDER, FAMILY_ES, CAT, DIV_NEG, DIV_POS
warnings.filterwarnings('ignore')
OUT = '/home/claude/stuffplus/out'; DEL = '/home/claude/stuffplus/deliverables'
df = pd.read_parquet('/home/claude/stuffplus/data/pitches_targets.parquet').reset_index(drop=True)
oof = pd.read_parquet('/home/claude/stuffplus/data/oof.parquet')
fs = json.load(open(f'{OUT}/feature_sets.json'))
assert (oof.PitchUID.values == df.PitchUID.values).all()
for c in ['full_stuff', 'full_location', 'full_pitching', 'pred_stuff', 'pred_location', 'pred_pitching'] + [c for c in oof.columns if c.startswith('full_stuff_') or c.startswith('p_')]:
    df[c] = oof[c].values
df['family_code'] = df.pitch_family.map(fs['fam_codes']); df['prev_family_code'] = df.prev_pitch_family.map(fs['prev_codes'])
LEVELS = ['No Altitude', 'Medium Altitude', 'Extreme Altitude']

# ---------- 1. Escala ----------
# Referencia absoluta: media y sd de la liga a nivel del mar (pooled 2024-26) -> permite comparar el mismo pitch entre ambientes
scale = {}
sea = df.alt_level == 0
for layer in ['stuff', 'location', 'pitching']:
    mu, sd = df.loc[sea, f'full_{layer}'].mean(), df.loc[sea, f'full_{layer}'].std()
    scale[layer] = dict(mu_sea=float(mu), sd_sea=float(sd))
    df[f'{layer}_plus'] = 100 + 10 * (df[f'full_{layer}'] - mu) / sd
    # Ajustado por temporada y ambiente: 100 = promedio de ese año en ese nivel de altitud
    grp = df.groupby(['year', 'alt_level'])[f'full_{layer}']
    df[f'{layer}_plus_adj'] = 100 + 10 * (df[f'full_{layer}'] - grp.transform('mean')) / grp.transform('std')
    # OOF (honesto) para validación de estabilidad
    df[f'{layer}_plus_oof'] = 100 + 10 * (df[f'pred_{layer}'] - mu) / sd
# distribución por ambiente para el dashboard (percentiles de Stuff+ absoluto en cada nivel)
for lvl in range(3):
    s = df.loc[df.alt_level == lvl, 'stuff_plus']
    scale[f'stuff_dist_alt{lvl}'] = dict(mean=float(s.mean()), sd=float(s.std()), pct=[float(np.percentile(s, p)) for p in range(0, 101, 5)])
    s = df.loc[df.alt_level == lvl, 'pitching_plus']
    scale[f'pitching_dist_alt{lvl}'] = dict(mean=float(s.mean()), sd=float(s.std()))
json.dump(scale, open(f'{OUT}/scale.json', 'w'), indent=2)
print('Stuff+ abs por ambiente:', df.groupby('altitude_category').stuff_plus.mean().round(2).to_dict())

# ---------- 2. Factores de traducción de movimiento (nivel del mar -> CDMX) por familia ----------
eff = pd.read_csv(f'{OUT}/altitude_effects.csv')
trans = {}
for fam in FAMILY_ORDER:
    e = eff[(eff.family == fam) & (eff.level == 'Extreme Altitude')].set_index('var')
    if 'total_break' not in e.index: continue
    tot = 1 + e.loc['total_break', 'pct'] / 100
    ivb_r = 1 + e.loc['InducedVertBreak', 'pct'] / 100 if abs(e.loc['InducedVertBreak', 'base_mean']) > 3 else tot
    hb_r = 1 + e.loc['hb_arm', 'pct'] / 100 if abs(e.loc['hb_arm', 'base_mean']) > 3 else tot
    trans[fam] = dict(ivb_ratio=float(np.clip(ivb_r, 0.5, 1.0)), hb_ratio=float(np.clip(hb_r, 0.5, 1.0)), total_ratio=float(tot),
                      speeddrop_delta=float(e.loc['SpeedDrop', 'delta']))
# medio
for fam in FAMILY_ORDER:
    e = eff[(eff.family == fam) & (eff.level == 'Medium Altitude')].set_index('var')
    if 'total_break' in e.index and fam in trans:
        tot = 1 + e.loc['total_break', 'pct'] / 100
        trans[fam]['medium'] = dict(ivb_ratio=float(np.clip(1 + e.loc['InducedVertBreak', 'pct'] / 100 if abs(e.loc['InducedVertBreak', 'base_mean']) > 3 else tot, 0.5, 1)),
                                    hb_ratio=float(np.clip(1 + e.loc['hb_arm', 'pct'] / 100 if abs(e.loc['hb_arm', 'base_mean']) > 3 else tot, 0.5, 1)))
json.dump(trans, open(f'{OUT}/translation_factors.json', 'w'), indent=2)

# ---------- 3. Contrafactual: el mismo pitch (medido a nivel del mar) lanzado en Harp Helú ----------
stuff_m = lgb.Booster(model_file=f'{OUT}/models/stuff_rv.txt')
heads = {h: lgb.Booster(model_file=f'{OUT}/models/stuff_{h}.txt') for h in ['whiff', 'gb', 'hard', 'hr', 'called_strike', 'chase']}
def counterfactual(frame, level=2):
    cf = frame.copy()
    key = None if level == 2 else 'medium'
    ivb_r = cf.pitch_family.map(lambda f: trans.get(f, {}).get('ivb_ratio', 0.75) if key is None else trans.get(f, {}).get('medium', {}).get('ivb_ratio', 0.82))
    hb_r = cf.pitch_family.map(lambda f: trans.get(f, {}).get('hb_ratio', 0.75) if key is None else trans.get(f, {}).get('medium', {}).get('hb_ratio', 0.82))
    cf['InducedVertBreak'] = cf.InducedVertBreak * ivb_r; cf['hb_arm'] = cf.hb_arm * hb_r
    cf['total_break'] = np.hypot(cf.InducedVertBreak, cf.hb_arm); cf['break_per_krpm'] = cf.total_break / (cf.SpinRate / 1000)
    cf['alt_level'] = level
    return cf
sea_df = df[sea].copy()
cf = counterfactual(sea_df, 2)
sea_df['stuff_cf_cdmx'] = 100 + 10 * (stuff_m.predict(cf[fs['STUFF']]) - scale['stuff']['mu_sea']) / scale['stuff']['sd_sea']
for h, m in heads.items():
    sea_df[f'p_{h}_sea'] = m.predict(sea_df[fs['STUFF']]); sea_df[f'p_{h}_cdmx'] = m.predict(cf[fs['STUFF']])
sea_df['delta_cf'] = sea_df.stuff_cf_cdmx - sea_df.stuff_plus

# Δ Stuff+ por familia (contrafactual, mismo pitch) + observado (pitchers que lanzaron en ambos)
fam_delta = sea_df.groupby('pitch_family').agg(n=('delta_cf', 'size'), stuff_sea=('stuff_plus', 'mean'), stuff_cdmx_cf=('stuff_cf_cdmx', 'mean'), delta_cf=('delta_cf', 'mean'), delta_cf_sd=('delta_cf', 'std'),
                                                 whiff_sea=('p_whiff_sea', 'mean'), whiff_cdmx=('p_whiff_cdmx', 'mean'), gb_sea=('p_gb_sea', 'mean'), gb_cdmx=('p_gb_cdmx', 'mean'),
                                                 hard_sea=('p_hard_sea', 'mean'), hard_cdmx=('p_hard_cdmx', 'mean'), hr_sea=('p_hr_sea', 'mean'), hr_cdmx=('p_hr_cdmx', 'mean'))
fam_delta['delta_cf_se'] = fam_delta.delta_cf_sd / np.sqrt(fam_delta.n)
# observado pareado
pf = df.groupby(['pitcher_anon_id', 'pitch_family', 'altitude_category']).agg(n=('stuff_plus', 'size'), sp=('stuff_plus', 'mean')).reset_index()
pf = pf[pf.n >= 25]
w = pf.pivot_table(index=['pitcher_anon_id', 'pitch_family'], columns='altitude_category', values=['sp', 'n']).dropna(subset=[('sp', 'No Altitude'), ('sp', 'Extreme Altitude')])
w['d'] = w[('sp', 'Extreme Altitude')] - w[('sp', 'No Altitude')]
obs = w.groupby(level='pitch_family').d.agg(['mean', 'count', 'std']); obs['se'] = obs['std'] / np.sqrt(obs['count'])
fam_delta['delta_obs'] = obs['mean']; fam_delta['delta_obs_se'] = obs['se']; fam_delta['n_pairs_obs'] = obs['count']
fam_delta = fam_delta.reindex([f for f in FAMILY_ORDER if f in fam_delta.index])
fam_delta.round(3).to_csv(f'{OUT}/family_delta.csv')
print(fam_delta[['n', 'stuff_sea', 'stuff_cdmx_cf', 'delta_cf', 'delta_obs', 'n_pairs_obs']].round(2).to_string())

# Figura: Δ Stuff+ por familia (contrafactual vs observado)
fig = go.Figure()
fams = list(fam_delta.index)
fig.add_trace(go.Bar(name='Mismo pitch trasladado a Harp Helú (modelo)', x=[FAMILY_ES[f] for f in fams], y=fam_delta.delta_cf, marker_color=CAT[0],
                     error_y=dict(type='data', array=1.96 * fam_delta.delta_cf_se, color='#52514e', thickness=1.5, width=4), text=[f'{v:+.1f}' for v in fam_delta.delta_cf], textposition='outside', textfont=dict(size=11, color='#0b0b0b'),
                     hovertemplate='%{x}<br>Δ Stuff+ contrafactual: %{y:+.2f}<extra></extra>'))
fig.add_trace(go.Bar(name='Observado: mismos pitchers, casa vs. fuera', x=[FAMILY_ES[f] for f in fams], y=fam_delta.delta_obs, marker_color=CAT[1],
                     error_y=dict(type='data', array=1.96 * fam_delta.delta_obs_se, color='#52514e', thickness=1.5, width=4), text=[f'{v:+.1f}' for v in fam_delta.delta_obs], textposition='outside', textfont=dict(size=11, color='#0b0b0b'),
                     customdata=fam_delta.n_pairs_obs, hovertemplate='%{x}<br>Δ Stuff+ observado: %{y:+.2f}<br>Pares pitcher: %{customdata}<extra></extra>'))
fig.add_hline(y=0, line_color='#c3c2b7')
fig.update_layout(title='Δ Stuff+ por forma de pitch: Harp Helú vs. nivel del mar (escala absoluta, 10 pts = 1 DE)', barmode='group', yaxis_title='Δ Stuff+', legend=dict(orientation='h', y=1.08, x=0), bargap=0.25)
save(fig, 'family_delta_stuff', 470)

# ---------- 4. Scores por pitch (CSV entregable) ----------
cols = ['PitchUID', 'year', 'game_anon_id', 'pitcher_anon_id', 'batter_anon_id', 'altitude_category', 'PitcherThrows', 'BatterSide', 'AutoPitchType', 'pitch_family', 'count', 'zone9',
        'RelSpeed', 'SpinRate', 'SpinAxis', 'InducedVertBreak', 'HorzBreak', 'RelHeight', 'RelSide', 'Extension', 'velo_diff_vs_fb', 'ivb_diff_vs_fb', 'hb_diff_vs_fb', 'tunnel_similarity',
        'stuff_plus', 'location_plus', 'pitching_plus', 'stuff_plus_adj', 'location_plus_adj', 'pitching_plus_adj', 'rv_pitcher', 'rv_pitcher_obs'] + [c for c in df.columns if c.startswith('p_')]
pitch_out = df[cols].rename(columns={'rv_pitcher': 'xRunValue_pitcher', 'rv_pitcher_obs': 'RunValue_obs_pitcher'})
pitch_out['stuff_plus_cf_cdmx'] = np.nan; pitch_out.loc[sea_df.index, 'stuff_plus_cf_cdmx'] = sea_df.stuff_cf_cdmx
pitch_out.round(4).to_csv(f'{DEL}/stuff_plus_por_pitch.csv.gz', index=False, compression='gzip')

# ---------- 5. Por pitcher × familia × ambiente, y sensibilidad a la altitud ----------
pp = df.groupby(['pitcher_anon_id', 'PitcherThrows', 'pitch_family', 'altitude_category']).agg(
    n=('stuff_plus', 'size'), velo=('RelSpeed', 'mean'), spin=('SpinRate', 'mean'), ivb=('InducedVertBreak', 'mean'), hb=('hb_arm', 'mean'), relh=('RelHeight', 'mean'), ext=('Extension', 'mean'),
    stuff_plus=('stuff_plus', 'mean'), location_plus=('location_plus', 'mean'), pitching_plus=('pitching_plus', 'mean'), stuff_plus_adj=('stuff_plus_adj', 'mean'),
    whiff_rate=('is_whiff', 'mean'), gb_rate=('is_gb', 'mean'), hard_rate=('is_hard', 'mean'), xrv_per100=('rv_pitcher', lambda s: 100 * s.mean()), rv_obs_per100=('rv_pitcher_obs', lambda s: 100 * s.mean())).reset_index()
pp = pp[pp.n >= 25]
# contrafactual por pitcher-familia (desde nivel del mar)
cfp = sea_df.groupby(['pitcher_anon_id', 'pitch_family']).agg(n_sea=('stuff_plus', 'size'), stuff_sea=('stuff_plus', 'mean'), stuff_cf_cdmx=('stuff_cf_cdmx', 'mean')).reset_index()
cfp = cfp[cfp.n_sea >= 25]; cfp['delta_cf'] = cfp.stuff_cf_cdmx - cfp.stuff_sea
pp = pp.merge(cfp[['pitcher_anon_id', 'pitch_family', 'stuff_cf_cdmx', 'delta_cf']], on=['pitcher_anon_id', 'pitch_family'], how='left')
pp.round(3).to_csv(f'{DEL}/stuff_plus_por_pitcher_familia.csv', index=False)

# Sensibilidad: pitchers con >=150 pitches en nivel del mar y en extrema
pa = df.groupby(['pitcher_anon_id', 'altitude_category']).agg(n=('stuff_plus', 'size'), stuff=('stuff_plus', 'mean'), pitching=('pitching_plus', 'mean'), xrv=('rv_pitcher', 'mean'), ivb=('InducedVertBreak', 'mean'), hb=('hb_arm', lambda s: s.abs().mean()), velo=('RelSpeed', 'mean')).reset_index()
pa = pa[pa.n >= 150].pivot_table(index='pitcher_anon_id', columns='altitude_category', values=['n', 'stuff', 'pitching', 'xrv', 'ivb', 'hb', 'velo'])
pa = pa.dropna(subset=[('stuff', 'No Altitude'), ('stuff', 'Extreme Altitude')])
sens = pd.DataFrame({'n_sea': pa[('n', 'No Altitude')], 'n_cdmx': pa[('n', 'Extreme Altitude')], 'stuff_sea': pa[('stuff', 'No Altitude')], 'stuff_cdmx': pa[('stuff', 'Extreme Altitude')],
                     'pitching_sea': pa[('pitching', 'No Altitude')], 'pitching_cdmx': pa[('pitching', 'Extreme Altitude')], 'velo': pa[('velo', 'No Altitude')]})
sens['delta_stuff'] = sens.stuff_cdmx - sens.stuff_sea
# esperado por su mezcla de familias (contrafactual) -> resiliencia = observado - esperado
exp = cfp.merge(sea_df.groupby(['pitcher_anon_id', 'pitch_family']).size().rename('w').reset_index(), on=['pitcher_anon_id', 'pitch_family'])
exp = exp.groupby('pitcher_anon_id').apply(lambda g: np.average(g.delta_cf, weights=g.w)).rename('delta_expected')
sens = sens.join(exp); sens['resilience'] = sens.delta_stuff - sens.delta_expected
# mezcla de pitches (string)
mix = df[df.alt_level == 0].groupby(['pitcher_anon_id', 'pitch_family']).size().groupby(level=0, group_keys=False).apply(lambda s: ', '.join(f'{FAMILY_ES[i[1]]} {100*v/s.sum():.0f}%' for i, v in s.sort_values(ascending=False).head(4).items()))
sens['arsenal'] = mix
sens = sens.sort_values('delta_stuff')
sens.round(2).to_csv(f'{DEL}/sensibilidad_altitud_por_pitcher.csv')
print('\nMás afectados:'); print(sens.head(8)[['stuff_sea', 'stuff_cdmx', 'delta_stuff', 'delta_expected', 'arsenal']].round(1).to_string())
print('\nMás consistentes:'); print(sens.tail(8)[['stuff_sea', 'stuff_cdmx', 'delta_stuff', 'delta_expected', 'arsenal']].round(1).to_string())
json.dump(dict(n_pitchers=len(sens), delta_mean=float(sens.delta_stuff.mean()), delta_sd=float(sens.delta_stuff.std()), delta_p10=float(sens.delta_stuff.quantile(.1)), delta_p90=float(sens.delta_stuff.quantile(.9)),
               corr_delta_expected=float(sens[['delta_stuff', 'delta_expected']].corr().iloc[0, 1])), open(f'{OUT}/sensitivity_summary.json', 'w'), indent=2)

# Figura sensibilidad: dispersión Stuff+ nivel del mar vs CDMX
fig = go.Figure()
fig.add_trace(go.Scatter(x=sens.stuff_sea, y=sens.stuff_cdmx, mode='markers', marker=dict(size=8, color=CAT[0], opacity=0.75, line=dict(width=1, color='#fcfcfb')),
                         customdata=np.stack([sens.index, sens.delta_stuff, sens.arsenal], axis=1),
                         hovertemplate='%{customdata[0]}<br>Stuff+ nivel del mar: %{x:.1f}<br>Stuff+ CDMX: %{y:.1f}<br>Δ: %{customdata[1]:+.1f}<br>%{customdata[2]}<extra></extra>', name='Pitchers'))
lo, hi = 80, 125
fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode='lines', line=dict(color='#898781', dash='dash'), name='Sin cambio'))
fig.add_trace(go.Scatter(x=[lo, hi], y=[lo + sens.delta_stuff.mean(), hi + sens.delta_stuff.mean()], mode='lines', line=dict(color=CAT[1], dash='dot'), name=f'Caída promedio ({sens.delta_stuff.mean():+.1f})'))
fig.update_layout(title=f'Sensibilidad a la altitud: Stuff+ del mismo pitcher a nivel del mar vs. en Harp Helú (n={len(sens)})', xaxis_title='Stuff+ a nivel del mar', yaxis_title='Stuff+ en altitud extrema',
                  legend=dict(orientation='h', y=-0.18, x=0), xaxis=dict(range=[lo, hi]), yaxis=dict(range=[lo, hi], scaleanchor='x'))
save(fig, 'sensitivity_scatter', 520)

# ---------- 6. Arsenales en Harp Helú ----------
ext = df[df.alt_level == 2]
ars = ext.groupby(['pitcher_anon_id', 'year', 'PitcherThrows']).agg(n=('pitching_plus', 'size'), stuff_plus=('stuff_plus', 'mean'), location_plus=('location_plus', 'mean'), pitching_plus=('pitching_plus', 'mean'),
                                                                     stuff_plus_adj=('stuff_plus_adj', 'mean'), xrv_per100=('rv_pitcher', lambda s: 100 * s.mean()), rv_obs_per100=('rv_pitcher_obs', lambda s: 100 * s.mean()),
                                                                     whiff_per_swing=('is_whiff', lambda s: s.sum() / max(ext.loc[s.index, 'is_swing'].sum(), 1)), gb_rate=('is_gb', 'mean'), hard_rate=('is_hard', 'mean'), hr_per_bip=('is_hr', lambda s: s.sum() / max(ext.loc[s.index, 'is_bip'].sum(), 1))).reset_index()
ars = ars[ars.n >= 200]
mixe = ext.groupby(['pitcher_anon_id', 'year', 'pitch_family']).size().groupby(level=[0, 1], group_keys=False).apply(lambda s: ' · '.join(f'{FAMILY_ES[i[2]]} {100*v/s.sum():.0f}%' for i, v in s.sort_values(ascending=False).head(4).items()))
ars = ars.merge(mixe.rename('arsenal').reset_index(), on=['pitcher_anon_id', 'year'])
ars = ars.sort_values('pitching_plus', ascending=False)
ars.round(3).to_csv(f'{DEL}/arsenales_harp_helu.csv', index=False)
# Qué tipo de arsenal rinde más en CDMX: composición por familias de los pitchers top vs bottom cuartil
ars['q'] = pd.qcut(ars.pitching_plus, 4, labels=['Q1 (peor)', 'Q2', 'Q3', 'Q4 (mejor)'])
comp = ext.merge(ars[['pitcher_anon_id', 'year', 'q']], on=['pitcher_anon_id', 'year']).groupby(['q', 'pitch_family'], observed=True).size().unstack(fill_value=0)
comp = (comp.T / comp.sum(axis=1)).T
comp.round(3).to_csv(f'{OUT}/arsenal_composition_by_quartile.csv')
print('\nComposición de arsenal por cuartil de Pitching+ en CDMX:'); print(comp.round(2).to_string())
# Figura: uso por familia Q4 vs Q1
fig = go.Figure()
famsC = [f for f in FAMILY_ORDER if f in comp.columns]
for q, col in [('Q4 (mejor)', CAT[0]), ('Q1 (peor)', CAT[1])]:
    fig.add_trace(go.Bar(name=f'Pitchers {q} en Harp Helú', x=[FAMILY_ES[f] for f in famsC], y=100 * comp.loc[q, famsC], marker_color=col, text=[f'{100*v:.0f}%' for v in comp.loc[q, famsC]], textposition='outside', textfont=dict(size=11, color='#0b0b0b'),
                         hovertemplate='%{x}: %{y:.1f}% del repertorio<extra></extra>'))
fig.update_layout(title='Qué lanzan los mejores en Harp Helú: uso por familia, cuartil superior vs. inferior de Pitching+', barmode='group', yaxis_title='% del repertorio', legend=dict(orientation='h', y=1.08, x=0), bargap=0.25)
save(fig, 'arsenal_quartiles', 440)

# ---------- 7. SHAP y perfil físico ideal ----------
rng = np.random.RandomState(0)
samp = df.sample(25000, random_state=0)
expl = shap.TreeExplainer(stuff_m)
sv = expl.shap_values(samp[fs['STUFF']])
imp = pd.Series(np.abs(sv).mean(0), index=fs['STUFF']).sort_values(ascending=False)
imp_alt = {lvl: pd.Series(np.abs(sv[samp.alt_level.values == lvl]).mean(0), index=fs['STUFF']) for lvl in [0, 2]}
shap_tbl = pd.DataFrame({'all': imp, 'sea': imp_alt[0], 'cdmx': imp_alt[2]}).sort_values('all', ascending=False)
shap_tbl.round(5).to_csv(f'{OUT}/shap_importance.csv')
print('\nSHAP |mean| (en unidades de xRV):'); print((shap_tbl * 1000).round(2).to_string())
NAMES = {'RelSpeed': 'Velocidad', 'SpinRate': 'Spin rate', 'axis_sin': 'Eje de spin (sen)', 'axis_cos': 'Eje de spin (cos)', 'InducedVertBreak': 'IVB', 'hb_arm': 'HB (lado brazo)', 'total_break': 'Movimiento total',
         'break_per_krpm': 'Movimiento por rpm (eficiencia)', 'bauer': 'Bauer units (spin/velo)', 'RelHeight': 'Altura de release', 'rel_side_arm': 'Lado de release', 'Extension': 'Extensión', 'is_rhp': 'Mano', 'alt_level': 'Altitud'}
fig = go.Figure()
order = shap_tbl.index[::-1]
fig.add_trace(go.Bar(name='Nivel del mar', y=[NAMES[i] for i in order], x=1000 * shap_tbl.loc[order, 'sea'], orientation='h', marker_color=ALT_COLORS['No Altitude'], hovertemplate='%{y}: %{x:.2f}<extra>Nivel del mar</extra>'))
fig.add_trace(go.Bar(name='Altitud extrema', y=[NAMES[i] for i in order], x=1000 * shap_tbl.loc[order, 'cdmx'], orientation='h', marker_color=ALT_COLORS['Extreme Altitude'], hovertemplate='%{y}: %{x:.2f}<extra>CDMX</extra>'))
fig.update_layout(title='Qué pesa en el Stuff+: importancia SHAP media (milésimas de carrera por pitch)', barmode='group', xaxis_title='|SHAP| medio × 1000', legend=dict(orientation='h', y=1.06, x=0), bargap=0.2, margin=dict(l=190))
save(fig, 'shap_importance', 520)

# Dependencia parcial: Stuff+ vs velocidad y vs IVB para recta con ride, en los dos ambientes
def pdp(fam, feat, grid, level):
    base = df[(df.pitch_family == fam) & (df.alt_level == level)].sample(4000, random_state=1)[fs['STUFF']].copy()
    ys = []
    for v in grid:
        b = base.copy(); b[feat] = v
        if feat in ('InducedVertBreak', 'hb_arm'):
            b['total_break'] = np.hypot(b.InducedVertBreak, b.hb_arm); b['break_per_krpm'] = b.total_break / (b.SpinRate / 1000)
        if feat == 'RelSpeed': b['bauer'] = b.SpinRate / b.RelSpeed
        ys.append(100 + 10 * (stuff_m.predict(b).mean() - scale['stuff']['mu_sea']) / scale['stuff']['sd_sea'])
    return ys
fig = make_subplots(rows=1, cols=3, subplot_titles=('Recta con ride: velocidad', 'Recta con ride: IVB', 'Slider gyro / sweeper: HB (guante)'))
g1 = np.arange(84, 98.1, 1); g2 = np.arange(8, 22.1, 1); g3 = -np.arange(0, 16.1, 1)
for level, lab in [(0, 'Nivel del mar'), (2, 'Altitud extrema')]:
    col = ALT_COLORS['No Altitude' if level == 0 else 'Extreme Altitude']
    fig.add_trace(go.Scatter(x=g1, y=pdp('Fastball-Ride', 'RelSpeed', g1, level), mode='lines', name=lab, line=dict(color=col, width=2), legendgroup=lab, hovertemplate='%{x} mph: Stuff+ %{y:.1f}<extra>' + lab + '</extra>'), row=1, col=1)
    fig.add_trace(go.Scatter(x=g2, y=pdp('Fastball-Ride', 'InducedVertBreak', g2, level), mode='lines', name=lab, line=dict(color=col, width=2), legendgroup=lab, showlegend=False, hovertemplate='IVB %{x}": Stuff+ %{y:.1f}<extra>' + lab + '</extra>'), row=1, col=2)
    fig.add_trace(go.Scatter(x=g3, y=pdp('Sweeper', 'hb_arm', g3, level), mode='lines', name=lab, line=dict(color=col, width=2), legendgroup=lab, showlegend=False, hovertemplate='HB %{x}": Stuff+ %{y:.1f}<extra>' + lab + '</extra>'), row=1, col=3)
fig.update_layout(title='Curvas de respuesta del Stuff+ (dependencia parcial) en los dos ambientes', legend=dict(orientation='h', y=-0.2, x=0))
fig.update_xaxes(title_text='mph', row=1, col=1); fig.update_xaxes(title_text='IVB (in)', row=1, col=2); fig.update_xaxes(title_text='HB hacia el guante (in)', row=1, col=3)
fig.update_yaxes(title_text='Stuff+', row=1, col=1)
save(fig, 'pdp_curves', 420)

# Perfil ideal: decil superior de Stuff+ en CDMX por familia (rangos p25-p75) vs liga en CDMX
prof = []
for fam in FAMILY_ORDER:
    sub = ext[ext.pitch_family == fam]
    if len(sub) < 2000: continue
    top = sub[sub.stuff_plus >= sub.stuff_plus.quantile(0.9)]
    row = dict(family=fam, n=len(sub), stuff_top=top.stuff_plus.mean(), stuff_league=sub.stuff_plus.mean())
    for v, lab in [('RelSpeed', 'velo'), ('InducedVertBreak', 'ivb'), ('hb_arm', 'hb'), ('SpinRate', 'spin'), ('break_per_krpm', 'eff'), ('RelHeight', 'relh'), ('Extension', 'ext'), ('velo_diff_vs_fb', 'vdiff')]:
        row[f'{lab}_top_p25'], row[f'{lab}_top_p50'], row[f'{lab}_top_p75'] = top[v].quantile([.25, .5, .75]).values
        row[f'{lab}_league_p50'] = sub[v].median()
        row[f'{lab}_whiff_top'] = top.is_whiff.mean(); row[f'{lab}_whiff_lg'] = sub.is_whiff.mean()
    row['gb_top'] = top.is_gb.mean(); row['gb_league'] = sub.is_gb.mean(); row['hard_top'] = top.is_hard.mean(); row['hard_league'] = sub.is_hard.mean()
    row['whiff_top'] = top.is_whiff.mean(); row['whiff_league'] = sub.is_whiff.mean()
    prof.append(row)
prof = pd.DataFrame(prof).set_index('family')
prof.round(2).to_csv(f'{OUT}/ideal_profile.csv')
print('\nPerfil ideal (decil superior en CDMX):'); print(prof[['n', 'stuff_top', 'stuff_league', 'velo_top_p50', 'velo_league_p50', 'ivb_top_p50', 'ivb_league_p50', 'hb_top_p50', 'hb_league_p50', 'eff_top_p50', 'eff_league_p50', 'whiff_top', 'whiff_league', 'gb_top', 'gb_league']].round(1).to_string())

# ---------- 8. Estabilidad año a año (Stuff+ OOF vs run value observado) ----------
py = df.groupby(['pitcher_anon_id', 'year']).agg(n=('stuff_plus_oof', 'size'), stuff=('stuff_plus_oof', 'mean'), pitching=('pitching_plus_oof', 'mean'), rv_obs=('rv_pitcher_obs', 'mean'), xrv=('rv_pitcher', 'mean'), whiff=('is_whiff', 'mean')).reset_index()
py = py[py.n >= 300]
pairs = py.merge(py, on='pitcher_anon_id', suffixes=('_a', '_b'))
pairs = pairs[pairs.year_b == pairs.year_a + 1]
stab = {k: float(pairs[[f'{k}_a', f'{k}_b']].corr().iloc[0, 1]) for k in ['stuff', 'pitching', 'rv_obs', 'xrv', 'whiff']}
stab['n_pairs'] = int(len(pairs))
# predictivo: Stuff+ año a predice rv_obs año b?
stab['stuff_a_vs_rvobs_b'] = float(pairs[['stuff_a', 'rv_obs_b']].corr().iloc[0, 1]); stab['pitching_a_vs_rvobs_b'] = float(pairs[['pitching_a', 'rv_obs_b']].corr().iloc[0, 1])
stab['rvobs_a_vs_rvobs_b'] = float(pairs[['rv_obs_a', 'rv_obs_b']].corr().iloc[0, 1])
json.dump(stab, open(f'{OUT}/stability.json', 'w'), indent=2)
print('\nEstabilidad año a año:', {k: round(v, 3) if isinstance(v, float) else v for k, v in stab.items()})
fig = go.Figure()
keys = [('stuff', 'Stuff+ (OOF)'), ('pitching', 'Pitching+ (OOF)'), ('xrv', 'xRunValue'), ('whiff', 'Whiff %'), ('rv_obs', 'Run value observado')]
fig.add_trace(go.Bar(x=[k[1] for k in keys], y=[stab[k[0]] for k in keys], marker_color=[CAT[0], CAT[0], CAT[2], CAT[2], CAT[1]], text=[f'{stab[k[0]]:.2f}' for k in keys], textposition='outside', textfont=dict(color='#0b0b0b'),
                     hovertemplate='%{x}: r = %{y:.3f}<extra></extra>'))
fig.update_layout(title=f'Estabilidad año a año por pitcher (≥300 pitches cada año, n={stab["n_pairs"]} pares): correlación', yaxis=dict(title='r', range=[0, 1]), bargap=0.4)
save(fig, 'stability', 400)

# ---------- 9. Datos para el dashboard ----------
# mapa de movimiento: pitcher×familia×ambiente (n>=25)
mm = pp[['pitcher_anon_id', 'PitcherThrows', 'pitch_family', 'altitude_category', 'n', 'velo', 'spin', 'ivb', 'hb', 'relh', 'ext', 'stuff_plus', 'pitching_plus', 'whiff_rate', 'gb_rate', 'hard_rate', 'stuff_cf_cdmx', 'delta_cf']].copy()
mm['alt'] = mm.altitude_category.map({'No Altitude': 0, 'Medium Altitude': 1, 'Extreme Altitude': 2})
mm = mm.drop(columns='altitude_category').round(2)
mm.to_json(f'{OUT}/dash_movement.json', orient='records')
# presets por familia (mediana liga nivel del mar)
presets = df[sea].groupby('pitch_family').agg(RelSpeed=('RelSpeed', 'median'), SpinRate=('SpinRate', 'median'), SpinAxis=('spin_axis_arm', 'median'), InducedVertBreak=('InducedVertBreak', 'median'), hb_arm=('hb_arm', 'median'),
                                               RelHeight=('RelHeight', 'median'), rel_side_arm=('rel_side_arm', 'median'), Extension=('Extension', 'median')).round(2)
presets.to_json(f'{OUT}/dash_presets.json', orient='index')
# comparables para el perfilador: pitcher-año en CDMX con arsenal y features medias por familia
comp_rows = []
for (pid, yr), g in ext.groupby(['pitcher_anon_id', 'year']):
    if len(g) < 200: continue
    fam = g.groupby('pitch_family').agg(n=('RelSpeed', 'size'), velo=('RelSpeed', 'mean'), ivb=('InducedVertBreak', 'mean'), hb=('hb_arm', 'mean'), spin=('SpinRate', 'mean'), sp=('stuff_plus', 'mean')).round(1)
    fam = fam[fam.n >= 15].sort_values('n', ascending=False).head(4)
    comp_rows.append(dict(id=pid, year=int(yr), hand=g.PitcherThrows.iloc[0], n=int(len(g)), stuff=round(g.stuff_plus.mean(), 1), pitching=round(g.pitching_plus.mean(), 1), xrv100=round(100 * g.rv_pitcher.mean(), 2), rvobs100=round(100 * g.rv_pitcher_obs.mean(), 2),
                          gb=round(g.is_gb.mean(), 3), hard=round(g.is_hard.mean(), 3), whiff=round(g.is_whiff.sum() / max(g.is_swing.sum(), 1), 3), hr_bip=round(g.is_hr.sum() / max(g.is_bip.sum(), 1), 3),
                          pitches=[dict(fam=f, n=int(r.n), usage=round(r.n / fam.n.sum(), 2), velo=r.velo, ivb=r.ivb, hb=r.hb, spin=r.spin, sp=r.sp) for f, r in fam.iterrows()]))
json.dump(comp_rows, open(f'{OUT}/dash_comparables.json', 'w'))
print('\nDone 05.')
