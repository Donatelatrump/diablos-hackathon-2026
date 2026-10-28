"""
04_models.py — Stuff+, Location+, Pitching+ con LightGBM. Validación: pitcher GroupKFold, season holdout, park holdout.
Salidas: data/oof.parquet, out/metrics.json, out/models/*.txt, out/models/stuff_rv.json (para el dashboard)
"""
import numpy as np, pandas as pd, json, time, warnings
import lightgbm as lgb
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score, log_loss, mean_squared_error
warnings.filterwarnings('ignore')

df = pd.read_parquet('/home/claude/stuffplus/data/pitches_targets.parquet')
df = df.reset_index(drop=True)
OUT = '/home/claude/stuffplus/out'

# ---------- Feature sets ----------
STUFF = ['RelSpeed', 'SpinRate', 'axis_sin', 'axis_cos', 'InducedVertBreak', 'hb_arm', 'total_break', 'break_per_krpm', 'bauer',
         'RelHeight', 'rel_side_arm', 'Extension', 'is_rhp', 'alt_level']
LOC = ['PlateLocHeight', 'plate_side_arm', 'dist_out_zone', 'zone9', 'Balls', 'Strikes', 'same_side', 'is_rhp', 'family_code', 'alt_level']
ARSENAL = ['velo_diff_vs_fb', 'ivb_diff_vs_fb', 'hb_diff_vs_fb', 'break_diff_vs_fb', 'tunnel_similarity', 'release_dist_vs_fb',
           'pitch_usage_pct', 'is_primary_fb', 'n_pitch_types', 'prev_family_code', 'prev_velo_diff', 'pitch_in_pa']
PITCH = sorted(set(STUFF) | set(LOC) | set(ARSENAL))
fam_codes = {f: i for i, f in enumerate(sorted(df.pitch_family.unique()))}
df['family_code'] = df.pitch_family.map(fam_codes)
prev_codes = {f: i for i, f in enumerate(sorted(df.prev_pitch_family.unique()))}
df['prev_family_code'] = df.prev_pitch_family.map(prev_codes)
CAT_FEATS = {'family_code', 'prev_family_code', 'zone9'}
json.dump(dict(STUFF=STUFF, LOC=LOC, ARSENAL=ARSENAL, PITCH=PITCH, fam_codes=fam_codes, prev_codes=prev_codes), open(f'{OUT}/feature_sets.json', 'w'), indent=2)

PARAMS_REG = dict(objective='regression', learning_rate=0.05, num_leaves=63, min_child_samples=300, feature_fraction=0.85, bagging_fraction=0.8, bagging_freq=1, lambda_l2=5.0, verbose=-1, num_threads=2)
PARAMS_BIN = dict(PARAMS_REG, objective='binary')
N_TREES = 400
metrics = {}
y = df.rv_pitcher.values
groups = df.pitcher_anon_id.values


def fit(X, yv, params, n=N_TREES, cats=None):
    ds = lgb.Dataset(X, yv, categorical_feature=[c for c in X.columns if c in CAT_FEATS] if cats is None else cats, free_raw_data=False)
    return lgb.train(params, ds, num_boost_round=n)


def null_by_count(train_idx, test_idx):
    m = pd.Series(y[train_idx]).groupby(df['count'].values[train_idx]).mean()
    return df['count'].iloc[test_idx].map(m).fillna(y[train_idx].mean()).values


def rmse(a, b): return float(np.sqrt(mean_squared_error(a, b)))


# ---------- 1. Regresión xRV: tres capas, tres esquemas de validación ----------
t0 = time.time()
oof = pd.DataFrame(index=df.index)
oof['rv_pitcher'] = y; oof['pitcher_anon_id'] = df.pitcher_anon_id; oof['year'] = df.year; oof['altitude_category'] = df.altitude_category
oof['count'] = df['count']; oof['pitch_family'] = df.pitch_family; oof['PitchUID'] = df.PitchUID
gkf = GroupKFold(n_splits=5)
folds = list(gkf.split(df, y, groups))
for name, feats in [('stuff', STUFF), ('location', LOC), ('pitching', PITCH)]:
    X = df[feats]
    pred = np.zeros(len(df)); null = np.zeros(len(df))
    for k, (tr, te) in enumerate(folds):
        m = fit(X.iloc[tr], y[tr], PARAMS_REG)
        pred[te] = m.predict(X.iloc[te]); null[te] = null_by_count(tr, te)
        print(f'{name} fold {k} done {time.time()-t0:.0f}s', flush=True)
    oof[f'pred_{name}'] = pred; oof['null_count'] = null
    metrics[f'{name}_pitcher_holdout'] = dict(rmse_model=rmse(y, pred), rmse_null_count=rmse(y, null), rmse_null_global=rmse(y, np.full(len(y), y.mean())),
                                              r2_vs_null=1 - mean_squared_error(y, pred) / mean_squared_error(y, null), corr=float(np.corrcoef(y, pred)[0, 1]))
    # season holdout: 2024-25 -> 2026
    tr = np.where(df.year < 2026)[0]; te = np.where(df.year == 2026)[0]
    m = fit(X.iloc[tr], y[tr], PARAMS_REG); p = m.predict(X.iloc[te])
    metrics[f'{name}_season_holdout_2026'] = dict(rmse_model=rmse(y[te], p), rmse_null_count=rmse(y[te], null_by_count(tr, te)), n_test=len(te), corr=float(np.corrcoef(y[te], p)[0, 1]))
    oof.loc[te, f'pred_{name}_season'] = p
    # park holdout A: sin altitud extrema -> predecir CDMX (extrapolación)
    tr = np.where(df.alt_level < 2)[0]; te = np.where(df.alt_level == 2)[0]
    m = fit(X.iloc[tr], y[tr], PARAMS_REG); p = m.predict(X.iloc[te])
    metrics[f'{name}_park_holdout_extreme'] = dict(rmse_model=rmse(y[te], p), rmse_null_count=rmse(y[te], null_by_count(tr, te)), n_test=len(te), corr=float(np.corrcoef(y[te], p)[0, 1]),
                                                  bias_mean_pred_minus_actual=float(p.mean() - y[te].mean()))
    oof.loc[te, f'pred_{name}_parkA'] = p
    # park holdout B: sin altitud media -> predecir media (interpolación)
    tr = np.where(df.alt_level != 1)[0]; te = np.where(df.alt_level == 1)[0]
    m = fit(X.iloc[tr], y[tr], PARAMS_REG); p = m.predict(X.iloc[te])
    metrics[f'{name}_park_holdout_medium'] = dict(rmse_model=rmse(y[te], p), rmse_null_count=rmse(y[te], null_by_count(tr, te)), n_test=len(te), corr=float(np.corrcoef(y[te], p)[0, 1]),
                                                 bias_mean_pred_minus_actual=float(p.mean() - y[te].mean()))
    # modelo completo
    m = fit(X, y, PARAMS_REG); m.save_model(f'{OUT}/models/{name}_rv.txt')
    oof[f'full_{name}'] = m.predict(X)
    imp = pd.Series(m.feature_importance('gain'), index=feats).sort_values(ascending=False)
    metrics[f'{name}_importance_gain'] = (imp / imp.sum()).round(4).to_dict()
    if name == 'stuff':
        json.dump(m.dump_model(), open(f'{OUT}/models/stuff_rv.json', 'w'))
    print(name, json.dumps({k: v for k, v in metrics.items() if k.startswith(name) and 'importance' not in k}, indent=1), flush=True)

# ---------- 2. Cabezas de clasificación (targets multi-objetivo) ----------
HEADS = {
    'whiff': ('is_whiff', None), 'chase': ('is_chase', None), 'called_strike': ('is_called_strike', None), 'swing': ('is_swing', None),
    'gb': ('is_gb', 'is_bip'), 'hard': ('is_hard', 'has_ev'), 'barrel': ('is_barrel', 'has_ev'), 'hr': ('is_hr', 'is_bip')}
for head, (col, mask_col) in HEADS.items():
    mask = np.ones(len(df), bool) if mask_col is None else df[mask_col].values.astype(bool)
    idx = np.where(mask & df[col].notna().values)[0]
    yb = df[col].values[idx].astype(int)
    for name, feats in [('stuff', STUFF), ('pitching', PITCH)]:
        X = df[feats].iloc[idx]
        # OOF por pitcher sólo para pitching (métricas); stuff sólo full (dashboard)
        if name == 'pitching':
            pred = np.zeros(len(idx)); nullp = np.zeros(len(idx))
            sub_groups = groups[idx]
            for tr, te in GroupKFold(n_splits=5).split(X, yb, sub_groups):
                m = fit(X.iloc[tr], yb[tr], PARAMS_BIN, n=300)
                pred[te] = m.predict(X.iloc[te])
                nullp[te] = pd.Series(yb[tr]).groupby(df['count'].values[idx][tr]).mean().reindex(df['count'].values[idx][te]).fillna(yb[tr].mean()).values
            metrics[f'head_{head}_pitching_pitcher_holdout'] = dict(auc=float(roc_auc_score(yb, pred)), logloss=float(log_loss(yb, np.clip(pred, 1e-6, 1 - 1e-6))),
                                                                   logloss_null_count=float(log_loss(yb, np.clip(nullp, 1e-6, 1 - 1e-6))), base_rate=float(yb.mean()), n=int(len(idx)))
            oof.loc[df.index[idx], f'p_{head}'] = pred
            # calibración (10 bins)
            bins = pd.qcut(pred, 10, duplicates='drop')
            cal = pd.DataFrame({'p': pred, 'y': yb}).groupby(bins, observed=True).agg(p=('p', 'mean'), y=('y', 'mean'), n=('y', 'size'))
            metrics[f'calibration_{head}'] = cal.round(4).to_dict(orient='list')
        m = fit(X, yb, PARAMS_BIN, n=300); m.save_model(f'{OUT}/models/{name}_{head}.txt')
        oof.loc[df.index[idx], f'full_{name}_{head}'] = m.predict(X)
        if name == 'stuff' and head in ('whiff', 'gb', 'hard', 'hr', 'called_strike', 'chase'):
            json.dump(m.dump_model(), open(f'{OUT}/models/stuff_{head}.json', 'w'))
    print('head', head, 'done', f'{time.time()-t0:.0f}s', flush=True)

oof.to_parquet('/home/claude/stuffplus/data/oof.parquet', index=False)
json.dump(metrics, open(f'{OUT}/metrics.json', 'w'), indent=2)
print('TOTAL', f'{time.time()-t0:.0f}s')
