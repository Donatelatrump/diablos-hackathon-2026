"""
13b - Park holdout estricto: el modelo no ve ni la categoria de altitud evaluada ni a los pitchers
evaluados. Referencia: modelo entrenado con los mismos pitchers pero con TODAS las sedes, evaluado
en los mismos lanzamientos. Si generaliza a sedes no vistas, ambas cifras deben ser parecidas.
"""
import sys, json
import numpy as np, pandas as pd, lightgbm as lgb
SRC = sys.argv[1] if len(sys.argv) > 1 else "../data/stuff_model_df.parquet"
d = pd.read_parquet("scored.parquet"); F = json.load(open("model_meta.json"))["features"]
cnt = pd.read_parquet(SRC, columns=["PitchUID", "Balls", "Strikes"]); d = d.merge(cnt, on="PitchUID")
d["conteo"] = d.Balls.astype(int).astype(str) + "-" + d.Strikes.astype(int).astype(str)
P = dict(objective="regression", learning_rate=0.03, num_leaves=31, min_child_samples=800, feature_fraction=0.8,
         bagging_fraction=0.8, bagging_freq=1, lambda_l2=10, verbose=-1, num_threads=2)
fit = lambda x: lgb.train(P, lgb.Dataset(x[F], x.rv), num_boost_round=500)
rng = np.random.default_rng(7); pits = d.pitcher_anon_id.unique()
test_p = set(rng.choice(pits, len(pits) // 5, replace=False)); te = d.pitcher_anon_id.isin(test_p)
def cpt(x, col):
    g = x.groupby(["pitcher_anon_id", "tipo"]).agg(p=(col, "mean"), y=("rv", "mean"), n=("rv", "size")); g = g[g.n >= 100]
    return float(np.corrcoef(g.p, g.y)[0, 1]), int(len(g))
rmse = lambda a, b: float(np.sqrt(np.mean((a - b) ** 2)))
m_all = fit(d[~te]); out = {}
NOM = {0: "sin altitud", 1: "altitud media", 2: "altitud extrema"}
for a in [2, 1, 0]:
    tr = d[~te & (d.alt != a)]; ts = d[te & (d.alt == a)].copy()
    m = fit(tr)
    ts["p_sin"] = m.predict(ts[F]); ts["p_con"] = m_all.predict(ts[F])
    ts["nulo"] = ts.conteo.map(tr.groupby("conteo").rv.mean()).fillna(tr.rv.mean())
    cs, n = cpt(ts, "p_sin"); cc, _ = cpt(ts, "p_con")
    r = {"n_pt": n, "corr_sin_ver_sede": cs, "corr_viendo_sede": cc,
         "rmse_sin_ver_sede": rmse(ts.p_sin, ts.rv), "rmse_viendo_sede": rmse(ts.p_con, ts.rv), "rmse_nulo_conteo": rmse(ts.nulo, ts.rv)}
    r["mejora_mse_vs_nulo_pct"] = 100 * (1 - (r["rmse_sin_ver_sede"] / r["rmse_nulo_conteo"]) ** 2)
    out[NOM[a]] = r
    print(f"{NOM[a]:16s} (n={n}): corr sin ver sede ni pitchers {cs:.3f} | viendo la sede {cc:.3f} | "
          f"MSE vs nulo por conteo {r['mejora_mse_vs_nulo_pct']:+.2f}%")
res = json.load(open("robustez.json")); res["park_holdout_estricto"] = out
json.dump(res, open("robustez.json", "w"), indent=1, default=float)
