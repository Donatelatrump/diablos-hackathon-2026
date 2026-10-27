"""
01_pipeline.py — Limpieza, features físicas, features de arsenal y clustering de pitches.
Salida: data/pitches.parquet
"""
import numpy as np, pandas as pd, pyarrow.parquet as pq, json
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

SRC = '/mnt/user-data/uploads/stuff_model_df.parquet'
OUT = '/home/claude/stuffplus/data/pitches.parquet'
META = '/home/claude/stuffplus/out/pipeline_meta.json'

df = pq.read_table(SRC).to_pandas()
n0 = len(df)
meta = {'n_raw': n0}

# ---------- 1. Filtros ----------
df = df[df.altitude_category.isin(['No Altitude', 'Medium Altitude', 'Extreme Altitude'])]
df = df[df.PitcherThrows.isin(['Right', 'Left']) & df.BatterSide.isin(['Right', 'Left'])]
df = df[df.pitcher_anon_id.notna() & df.batter_anon_id.notna()]
# Sweeper -> familia Slider (588 pitches); tipos residuales fuera
df['AutoPitchType'] = df['AutoPitchType'].astype(str)
df.loc[df.AutoPitchType == 'Sweeper', 'AutoPitchType'] = 'Slider'
KEEP_TYPES = ['Four-Seam', 'Sinker', 'Cutter', 'Changeup', 'Splitter', 'Slider', 'Curveball']
df = df[df.AutoPitchType.isin(KEEP_TYPES)]
phys = ['RelSpeed', 'SpinRate', 'SpinAxis', 'InducedVertBreak', 'HorzBreak', 'RelHeight', 'RelSide', 'Extension',
        'VertApprAngle', 'HorzApprAngle', 'VertRelAngle', 'HorzRelAngle', 'ZoneSpeed', 'SpeedDrop']
df = df.dropna(subset=phys)
# Outliers físicos (errores de tracking)
df = df[(df.RelSpeed.between(60, 105)) & (df.SpinRate.between(300, 3600)) &
        (df.InducedVertBreak.abs() < 30) & (df.HorzBreak.abs() < 30) &
        (df.RelHeight.between(2, 8)) & (df.RelSide.abs() < 5) & (df.Extension.between(3, 8.5)) &
        (df.SpeedDrop.between(0, 15))]
meta['n_clean'] = len(df)
meta['dropped_pct'] = round(100 * (1 - len(df) / n0), 2)

# ---------- 2. Ambiente: densidad relativa del aire ----------
# ISA: rho/rho0 = (1 - 2.25577e-5 h)^4.2559. Harp Helú 2,240 m -> 0.802
def rho_rel(h):
    return (1 - 2.25577e-5 * h) ** 4.2559
ALT_M = {'No Altitude': 50, 'Medium Altitude': 1450, 'Extreme Altitude': 2240}  # Medium: representativo, se contrasta con la altitud implícita
df['altitude_m'] = df.altitude_category.map(ALT_M)
df['rho_rel'] = df.altitude_m.map(lambda h: rho_rel(h))
df['alt_level'] = df.altitude_category.map({'No Altitude': 0, 'Medium Altitude': 1, 'Extreme Altitude': 2})

# ---------- 3. Features físicas normalizadas por mano ----------
df['is_rhp'] = (df.PitcherThrows == 'Right').astype(int)
sign = np.where(df.is_rhp == 1, 1.0, -1.0)
df['hb_arm'] = df.HorzBreak * sign          # + = lado del brazo
df['rel_side_arm'] = df.RelSide * sign
df['haa_arm'] = df.HorzApprAngle * sign
df['hra_arm'] = df.HorzRelAngle * sign
# eje de spin normalizado a derecho (reflejar para zurdos): axis' = (360 - axis) % 360
df['spin_axis_arm'] = np.where(df.is_rhp == 1, df.SpinAxis, (360 - df.SpinAxis) % 360)
df['axis_sin'] = np.sin(np.deg2rad(df.spin_axis_arm)); df['axis_cos'] = np.cos(np.deg2rad(df.spin_axis_arm))
df['total_break'] = np.hypot(df.InducedVertBreak, df.hb_arm)
# Eficiencia de spin aproximada: movimiento por rpm (pulgadas por 1000 rpm), proxy de spin activo
df['break_per_krpm'] = df.total_break / (df.SpinRate / 1000)
# Bauer units
df['bauer'] = df.SpinRate / df.RelSpeed
df['same_side'] = (df.PitcherThrows == df.BatterSide).astype(int)

# ---------- 4. Fastball primaria por pitcher-temporada y features de arsenal ----------
fb_types = ['Four-Seam', 'Sinker', 'Cutter']
fb = df[df.AutoPitchType.isin(fb_types)]
fb_counts = fb.groupby(['pitcher_anon_id', 'year', 'AutoPitchType']).size().reset_index(name='n')
primary = fb_counts.sort_values('n', ascending=False).drop_duplicates(['pitcher_anon_id', 'year'])
primary = primary.rename(columns={'AutoPitchType': 'primary_fb'})[['pitcher_anon_id', 'year', 'primary_fb']]
df = df.merge(primary, on=['pitcher_anon_id', 'year'], how='left')
# pitchers sin fastball etiquetada: usar el pitch más rápido como primaria
no_fb = df.primary_fb.isna()
if no_fb.any():
    fast = df[no_fb].groupby(['pitcher_anon_id', 'year']).apply(lambda g: g.groupby('AutoPitchType').RelSpeed.mean().idxmax()).reset_index(name='primary_fb2')
    df = df.merge(fast, on=['pitcher_anon_id', 'year'], how='left')
    df['primary_fb'] = df.primary_fb.fillna(df.primary_fb2); df = df.drop(columns='primary_fb2')

# Promedios de la fastball primaria por pitcher-temporada-altitud (el arsenal se compara en el mismo aire)
fbref = df[df.AutoPitchType == df.primary_fb].groupby(['pitcher_anon_id', 'year', 'altitude_category']).agg(
    fb_speed=('RelSpeed', 'mean'), fb_ivb=('InducedVertBreak', 'mean'), fb_hb=('hb_arm', 'mean'),
    fb_relh=('RelHeight', 'mean'), fb_rels=('rel_side_arm', 'mean'), fb_ext=('Extension', 'mean'),
    fb_vra=('VertRelAngle', 'mean'), fb_hra=('hra_arm', 'mean')).reset_index()
df = df.merge(fbref, on=['pitcher_anon_id', 'year', 'altitude_category'], how='left')
# fallback: promedio pitcher-temporada sin distinguir altitud
fbref2 = df[df.AutoPitchType == df.primary_fb].groupby(['pitcher_anon_id', 'year']).agg(
    fb_speed2=('RelSpeed', 'mean'), fb_ivb2=('InducedVertBreak', 'mean'), fb_hb2=('hb_arm', 'mean'),
    fb_relh2=('RelHeight', 'mean'), fb_rels2=('rel_side_arm', 'mean'), fb_ext2=('Extension', 'mean'),
    fb_vra2=('VertRelAngle', 'mean'), fb_hra2=('hra_arm', 'mean')).reset_index()
df = df.merge(fbref2, on=['pitcher_anon_id', 'year'], how='left')
for c in ['fb_speed', 'fb_ivb', 'fb_hb', 'fb_relh', 'fb_rels', 'fb_ext', 'fb_vra', 'fb_hra']:
    df[c] = df[c].fillna(df[c + '2']); df = df.drop(columns=c + '2')

df['velo_diff_vs_fb'] = df.RelSpeed - df.fb_speed
df['ivb_diff_vs_fb'] = df.InducedVertBreak - df.fb_ivb
df['hb_diff_vs_fb'] = df.hb_arm - df.fb_hb
df['break_diff_vs_fb'] = np.hypot(df.ivb_diff_vs_fb, df.hb_diff_vs_fb)
# Túnel: distancia del release point y del ángulo de salida respecto a la fastball (menor = mejor túnel)
df['release_dist_vs_fb'] = np.hypot(df.RelHeight - df.fb_relh, df.rel_side_arm - df.fb_rels)
df['angle_dist_vs_fb'] = np.hypot(df.VertRelAngle - df.fb_vra, df.hra_arm - df.fb_hra)
df['tunnel_similarity'] = 1 / (1 + df.release_dist_vs_fb + 0.5 * df.angle_dist_vs_fb)
df['is_primary_fb'] = (df.AutoPitchType == df.primary_fb).astype(int)
# Uso del pitch en el repertorio (pitcher-temporada)
usage = df.groupby(['pitcher_anon_id', 'year', 'AutoPitchType']).size() / df.groupby(['pitcher_anon_id', 'year']).size()
df = df.merge(usage.rename('pitch_usage_pct').reset_index(), on=['pitcher_anon_id', 'year', 'AutoPitchType'], how='left')
df['n_pitch_types'] = df.groupby(['pitcher_anon_id', 'year']).AutoPitchType.transform('nunique')

# ---------- 5. Clustering "shape over label" ----------
# GMM a nivel liga sobre forma relativa a la fastball + forma absoluta. Nombramos clusters por su centroide.
clus_feats = ['velo_diff_vs_fb', 'InducedVertBreak', 'hb_arm', 'RelSpeed', 'axis_sin', 'axis_cos', 'break_per_krpm']
X = df[clus_feats].values
scaler = StandardScaler().fit(X)
Xs = scaler.transform(X)
rng = np.random.RandomState(42)
idx = rng.choice(len(Xs), 120000, replace=False)
gmm = GaussianMixture(n_components=12, covariance_type='full', random_state=42, max_iter=300).fit(Xs[idx])
df['cluster_id'] = gmm.predict(Xs)
cent = pd.DataFrame(scaler.inverse_transform(gmm.means_), columns=clus_feats)
cent['n'] = df.cluster_id.value_counts().sort_index().values
# Nombre por reglas físicas sobre el centroide
def name_cluster(r):
    vd, ivb, hb, v = r.velo_diff_vs_fb, r.InducedVertBreak, r.hb_arm, r.RelSpeed
    if vd > -3.5:  # familia fastball (misma velocidad que la primaria)
        if hb < 5 and ivb >= 10: return 'Fastball-Cut'
        if hb < 4: return 'Cutter'
        if ivb >= 13 and hb < 10: return 'Fastball-Ride'
        if ivb >= 13: return 'Fastball-Run'
        return 'Sinker'
    # secundarios
    if ivb < -2:
        return 'Slurve' if hb <= -6 and ivb > -6 else 'Curveball'
    if hb >= 5 and vd <= -4 and ivb > 2: return 'Changeup'
    if hb >= 5 and ivb <= 2: return 'Splitter'
    if hb <= -6: return 'Sweeper'
    if hb < 4 and ivb > 4 and vd > -4: return 'Cutter'
    return 'Slider-Gyro'
cent['family'] = cent.apply(name_cluster, axis=1)
# Composición por etiqueta Trackman para auditar
ct = pd.crosstab(df.cluster_id, df.AutoPitchType, normalize='index').round(2)
cent = cent.join(ct)
df['pitch_family'] = df.cluster_id.map(cent.family)
# Si el GMM mezcla, mantener también la etiqueta Trackman; la familia es la unidad para reportar.

# ---------- 6. Secuencia: pitch previo dentro del turno (aprox. por progresión de conteo) ----------
df['pa_key'] = df.game_anon_id.astype(str) + '_' + df.Inning.astype(int).astype(str) + '_' + df['Top/Bottom'].astype(str) + '_' + df.batter_anon_id.astype(str)
df['count_ord'] = df.Balls + df.Strikes
df = df.sort_values(['pa_key', 'count_ord', 'Balls']).reset_index(drop=True)
df['prev_pitch_family'] = df.groupby('pa_key').pitch_family.shift(1).fillna('None')
df['prev_velo_diff'] = (df.RelSpeed - df.groupby('pa_key').RelSpeed.shift(1)).fillna(0)
df['pitch_in_pa'] = df.groupby('pa_key').cumcount() + 1

# ---------- 7. Zona (9 cuadrantes + fuera) ----------
# Zona MLB: ancho 17" => ±0.708 ft; alto típico 1.5–3.5 ft
side_bins = [-np.inf, -0.708, -0.236, 0.236, 0.708, np.inf]
h_bins = [-np.inf, 1.5, 2.167, 2.833, 3.5, np.inf]
sx = np.digitize(df.PlateLocSide, side_bins[1:-1])  # 0..4 ; 1-3 dentro
sz = np.digitize(df.PlateLocHeight, h_bins[1:-1])
inside = (sx >= 1) & (sx <= 3) & (sz >= 1) & (sz <= 3)
df['zone9'] = np.where(inside, (sz - 1) * 3 + sx, 0)  # 1..9 dentro; 0 = fuera
# Distancia al borde de la zona (negativo adentro)
dx = np.maximum(np.abs(df.PlateLocSide) - 0.708, 0); dz = np.maximum(np.maximum(1.5 - df.PlateLocHeight, df.PlateLocHeight - 3.5), 0)
df['dist_out_zone'] = np.hypot(dx, dz)
df['plate_side_arm'] = df.PlateLocSide * sign  # + = lado del brazo del pitcher
df['count'] = df.Balls.astype(int).astype(str) + '-' + df.Strikes.astype(int).astype(str)

# ---------- 8. Flags de outcomes para targets ----------
df['is_swing'] = df.is_swing.fillna(0).astype(int)
df['is_whiff'] = df.is_whiff.fillna(0).astype(int)
df['is_called_strike'] = df.is_called_strike.fillna(0).astype(int)
df['is_chase'] = df.swung_outside_strike_zone.fillna(0).astype(int)
df['is_bip'] = (df.PitchCall == 'InPlay').astype(int)
df['has_ev'] = (df.is_bip == 1) & df.ExitSpeed.notna() & df.Angle.notna()
df['is_gb'] = np.where(df.is_bip == 1, (df.hit_type == 'GroundBall').astype(float), np.nan)
df['is_hard'] = np.where(df.has_ev, (df.ExitSpeed >= 95).astype(float), np.nan)
df['is_weak'] = np.where(df.has_ev, ((df.ExitSpeed < 80) | (df.hit_type == 'Popup')).astype(float), np.nan)
# Barrel aprox (Statcast): EV>=98 y LA en [26-30] ampliándose con EV
def barrel(ev, la):
    if np.isnan(ev) or np.isnan(la) or ev < 98: return 0.0
    lo = max(26 - (ev - 98) * 1.0, 8); hi = min(30 + (ev - 98) * 1.5, 50)
    return float(lo <= la <= hi)
df['is_barrel'] = np.where(df.has_ev, [barrel(e, a) for e, a in zip(df.ExitSpeed, df.Angle)], np.nan)
df['is_hr'] = df.home_run.fillna(0).astype(int)

df.to_parquet(OUT, index=False)
cent.to_csv('/home/claude/stuffplus/out/cluster_centroids.csv')
meta['n_final'] = len(df); meta['n_pitchers'] = int(df.pitcher_anon_id.nunique()); meta['n_games'] = int(df.game_anon_id.nunique())
meta['alt_counts'] = df.altitude_category.value_counts().to_dict(); meta['ALT_M'] = ALT_M
meta['rho'] = {k: round(rho_rel(v), 3) for k, v in ALT_M.items()}
meta['family_counts'] = df.pitch_family.value_counts().to_dict()
json.dump(meta, open(META, 'w'), indent=2)
print(json.dumps(meta, indent=2))
print(cent.round(2).to_string())
print(pd.crosstab(df.pitch_family, df.AutoPitchType))
