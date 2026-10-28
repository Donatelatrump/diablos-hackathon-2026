"""
07 - ¿El simulador predice como rinde un pitcher en altitud?

Para cada pitcher con lanzamientos a nivel del mar Y en altitud extrema:
  1. Se entrena el modelo SIN ese pitcher (5 grupos de pitchers).
  2. Sus lanzamientos tirados a nivel del mar se trasladan a la altitud promedio de
     las sedes de altitud extrema (1,968 m) con la ley fisica, y se califican.
  3. Se compara contra el Stuff+ que ese mismo modelo le da a sus lanzamientos
     realmente tirados en altitud extrema.

Referencia ingenua: suponer que rinde en altitud igual que a nivel del mar.

Nota: los exponentes fisicos (6 numeros por tipo) se estimaron con todos los
pitchers; el modelo de Stuff+, que es lo que podria memorizar a un pitcher,
no lo ve.
"""
import json
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import GroupKFold

d = pd.read_parquet("scored.parquet")
meta = json.load(open("model_meta.json")); FEATS = meta["features"]
EXP = json.load(open("exponentes.json"))
PARAMS = dict(objective="regression", learning_rate=0.03, num_leaves=31, min_child_samples=800,
              feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=10,
              verbose=-1, num_threads=2)
MIN_N = 50

rho = lambda h: 1.225 * (1 - 0.0065 * h / 288.15) ** 4.2559
R_EXT = rho(EXP["altitudes_m"]["Extreme Altitude"]) / rho(EXP["altitudes_m"]["No Altitude"])
P = {k: v["p_magnus"] for k, v in EXP["por_tipo"].items()}; pglob = EXP["global"]["p_magnus"]
fac = lambda t: R_EXT ** P.get(t, pglob)

# escala: misma definicion que 05_results (promedios pitcher x tipo >=100, por categoria)
SC = {int(k): v for k, v in meta["scale"].items()}
plus = lambda pred, a: 100 + 10 * (SC[a]["mean"] - pred) / SC[a]["std"]

# solo pitchers con ambas sedes; los demas igual entran al entrenamiento
both = d.groupby(["pitcher_anon_id", "tipo", "alt"]).size().unstack()
elig = both[(both.get(0, 0) >= MIN_N) & (both.get(2, 0) >= MIN_N)].index.get_level_values(0).unique()
print(f"Pitchers con >= {MIN_N} lanzamientos de un mismo tipo en ambas sedes: {len(elig)}")

fbt = d[(d.is_fb == 1) & (d.alt == 0)].groupby(["pitcher_anon_id", "year"]).tipo \
       .agg(lambda s: s.mode().iat[0]).rename("fbt")
rows = []
for k, (tr, te) in enumerate(GroupKFold(5).split(d, groups=d.pitcher_anon_id)):
    m = lgb.train(PARAMS, lgb.Dataset(d.iloc[tr][FEATS], d.iloc[tr].rv), num_boost_round=500)
    t = d.iloc[te]; t = t[t.pitcher_anon_id.isin(elig)]
    obs = t[t.alt == 2].assign(s=lambda x: plus(m.predict(x[FEATS]), 2))
    low = t[t.alt == 0].join(fbt, on=["pitcher_anon_id", "year"])
    mar = plus(m.predict(low[FEATS]), 0)
    f = low.tipo.map(fac).fillna(R_EXT ** pglob).values
    ff = low.fbt.map(fac).fillna(fac("Four-Seam")).values
    X = low[FEATS].copy()
    X["ivb"] *= f; X["hb_arm"] *= f; X["fb_ivb"] *= ff
    fb_hb = low.hb_arm - low.d_hb
    X["d_ivb"] = X.ivb - X.fb_ivb; X["d_hb"] = X.hb_arm - fb_hb * ff; X["alt"] = 2
    low = low.assign(mar=mar, proy=plus(m.predict(X), 2))
    a = low.groupby(["pitcher_anon_id", "tipo"]).agg(mar=("mar", "mean"), proy=("proy", "mean"), n_mar=("rv", "size"))
    b = obs.groupby(["pitcher_anon_id", "tipo"]).agg(ext=("s", "mean"), n_ext=("rv", "size"))
    j = a.join(b, how="inner"); j = j[(j.n_mar >= MIN_N) & (j.n_ext >= MIN_N)]
    rows.append(j); print(f"  grupo {k+1}/5: {len(j)} pitcher x tipo")
r = pd.concat(rows).reset_index()

def met(pred, y):
    return dict(corr=float(np.corrcoef(pred, y)[0, 1]), mae=float(np.abs(pred - y).mean()))
res = {"n": int(len(r)), "n_pitchers": int(r.pitcher_anon_id.nunique()),
       "ingenuo": met(r.mar, r.ext), "proyeccion": met(r.proy, r.ext),
       "cambio_corr": float(np.corrcoef(r.proy - r.mar, r.ext - r.mar)[0, 1]),
       "por_tipo": {}}
res["reduccion_error_pct"] = 100 * (1 - res["proyeccion"]["mae"] / res["ingenuo"]["mae"])
print(f"\n{res['n']} combinaciones pitcher x tipo ({res['n_pitchers']} pitchers), ningun pitcher visto al entrenar")
print(f"  Ingenuo (rinde igual):  corr {res['ingenuo']['corr']:.3f} | error medio {res['ingenuo']['mae']:.2f}")
print(f"  Proyeccion simulador:   corr {res['proyeccion']['corr']:.3f} | error medio {res['proyeccion']['mae']:.2f}"
      f"  ({res['reduccion_error_pct']:.0f}% menos error)")
print(f"  ¿Predice el cambio de cada pitcher? corr {res['cambio_corr']:.3f}")
rng = np.random.default_rng(0)
bs = [1 - np.abs(x.proy - x.ext).mean() / np.abs(x.mar - x.ext).mean()
      for x in (r.sample(len(r), replace=True, random_state=int(rng.integers(1e9))) for _ in range(1000))]
res["reduccion_error_ic95"] = [100 * float(q) for q in np.percentile(bs, [2.5, 97.5])]
print(f"  IC95 de la reduccion de error: {res['reduccion_error_ic95'][0]:.0f}% a {res['reduccion_error_ic95'][1]:.0f}%")
print("\nPor tipo:")
for t, x in r.groupby("tipo"):
    if len(x) < 15: continue
    res["por_tipo"][t] = {"n": int(len(x)), "ingenuo": met(x.mar, x.ext), "proyeccion": met(x.proy, x.ext)}
    print(f"  {t:10s} n={len(x):3d}  ingenuo corr {np.corrcoef(x.mar, x.ext)[0,1]:.2f} MAE {np.abs(x.mar-x.ext).mean():.1f}"
          f"  |  proyeccion corr {np.corrcoef(x.proy, x.ext)[0,1]:.2f} MAE {np.abs(x.proy-x.ext).mean():.1f}")
r.to_parquet("projection_validation.parquet", index=False)
json.dump(res, open("projection_validation.json", "w"), indent=2)
print("\n-> projection_validation.json")
