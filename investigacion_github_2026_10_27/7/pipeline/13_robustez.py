"""
13 - Robustez: baseline nulo por conteo, validacion por sede (park holdout) y SHAP.

A. Baseline de la convocatoria: "xRunValue promedio por conteo". Se compara contra el modelo en
   pitchers no vistos (mismo corte 80/20 que la escalera de 03_model.py): RMSE por lanzamiento y
   correlacion a nivel pitcher x tipo.
B. Park holdout: sin identificador de estadio, la unidad mas fina es la categoria de altitud. Para
   cada categoria se entrena SIN ninguno de sus lanzamientos y se evalua en ella. Para altitud
   extrema el modelo nunca vio esa altitud: es la prueba de generalizar a sedes no vistas.
C. SHAP (contribucion de cada variable a cada prediccion, nativo de LightGBM), en puntos de Stuff+.
"""
import sys, json
import numpy as np
import pandas as pd
import lightgbm as lgb

SRC = sys.argv[1] if len(sys.argv) > 1 else "../data/stuff_model_df.parquet"
d = pd.read_parquet("scored.parquet")
meta = json.load(open("model_meta.json")); F = meta["features"]
cnt = pd.read_parquet(SRC, columns=["PitchUID", "Balls", "Strikes"])
d = d.merge(cnt, on="PitchUID", how="left")
d["conteo"] = d.Balls.astype(int).astype(str) + "-" + d.Strikes.astype(int).astype(str)
PARAMS = dict(objective="regression", learning_rate=0.03, num_leaves=31, min_child_samples=800,
              feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=10, verbose=-1, num_threads=2)
fit = lambda X, y: lgb.train(PARAMS, lgb.Dataset(X, y), num_boost_round=500)
rmse = lambda a, b: float(np.sqrt(np.mean((a - b) ** 2)))

def corr_pt(df, col, min_n=100):
    g = df.groupby(["pitcher_anon_id", "tipo"]).agg(p=(col, "mean"), y=("rv", "mean"), n=("rv", "size"))
    g = g[g.n >= min_n]
    return float(np.corrcoef(g.p, g.y)[0, 1]) if len(g) > 2 else float("nan"), int(len(g))

def evaluar(tr, ts, etiqueta):
    m = fit(tr[F], tr.rv)
    ts = ts.assign(pred=m.predict(ts[F]),
                   nulo=ts.conteo.map(tr.groupby("conteo").rv.mean()).fillna(tr.rv.mean()),
                   media=tr.rv.mean())
    r = {"n_lanzamientos": int(len(ts)),
         "rmse_modelo": rmse(ts.pred, ts.rv), "rmse_nulo_conteo": rmse(ts.nulo, ts.rv), "rmse_media": rmse(ts.media, ts.rv)}
    r["mejora_rmse_vs_nulo_pct"] = 100 * (1 - r["rmse_modelo"] / r["rmse_nulo_conteo"])
    r["mejora_mse_vs_nulo_pct"] = 100 * (1 - (r["rmse_modelo"] / r["rmse_nulo_conteo"]) ** 2)
    r["corr_modelo"], r["n_pt"] = corr_pt(ts, "pred")
    r["corr_nulo_conteo"], _ = corr_pt(ts, "nulo")
    # calibracion: deciles de prediccion vs valor real
    q = pd.qcut(ts.pred, 10, labels=False, duplicates="drop")
    cal = ts.groupby(q).agg(pred=("pred", "mean"), real=("rv", "mean"))
    r["calibracion_deciles"] = (100 * cal).round(3).to_dict("records")          # carreras por 100 lanzamientos
    r["calibracion_pendiente"] = float(np.polyfit(cal.pred, cal.real, 1)[0])
    print(f"  {etiqueta:40s} RMSE modelo {r['rmse_modelo']:.5f} vs nulo por conteo {r['rmse_nulo_conteo']:.5f} "
          f"({r['mejora_mse_vs_nulo_pct']:+.2f}% MSE) | corr pitcher×tipo modelo {r['corr_modelo']:.3f} vs nulo {r['corr_nulo_conteo']:.3f} "
          f"(n={r['n_pt']}) | pendiente calibración {r['calibracion_pendiente']:.2f}")
    return r, m

res = {}
print("A. Pitchers no vistos (mismo corte 80/20 que la escalera)")
rng = np.random.default_rng(7)
pits = d.pitcher_anon_id.unique(); test_p = set(rng.choice(pits, len(pits) // 5, replace=False))
te = d.pitcher_anon_id.isin(test_p)
res["pitcher_holdout"], _ = evaluar(d[~te], d[te], "pitcher holdout")

print("\nB. Park holdout: entrenar sin una categoría de altitud completa y evaluar en ella")
NOM = {0: "sin altitud", 1: "altitud media", 2: "altitud extrema"}
res["park_holdout"] = {}
for a in [2, 1, 0]:
    r, _ = evaluar(d[d.alt != a], d[d.alt == a], f"sin {NOM[a]} → evaluar en {NOM[a]}")
    # referencia: mismo conjunto evaluado con predicciones fuera de muestra por pitcher (modelo que si vio la sede)
    r["corr_con_sede_vista"], _ = corr_pt(d[d.alt == a], "pred")
    res["park_holdout"][NOM[a]] = r
    print(f"  {'':40s} referencia con la sede vista (pitcher holdout): corr {r['corr_con_sede_vista']:.3f}")

print("\nC. SHAP del modelo final (muestra de 30,000 lanzamientos), en puntos de Stuff+")
final = lgb.Booster(model_file="stuff_model.txt")
s = d.sample(30000, random_state=3)
contrib = final.predict(s[F], pred_contrib=True)[:, :-1]
std = s.alt.map({int(k): v["std"] for k, v in meta["scale"].items()}).values[:, None]
pts = -10 * contrib / std                                   # + = sube el Stuff+
glob = pd.Series(np.abs(pts).mean(axis=0), index=F).sort_values(ascending=False)
print(glob.round(2).to_string())
por = {}
for (t, a), g in s.assign(i=np.arange(len(s))).groupby(["tipo", "alt"]):
    if a not in (0, 2) or t not in ["Four-Seam", "Sinker", "Slider", "Changeup", "Curveball", "Cutter"]: continue
    v = pd.Series(np.abs(pts[g.i.values]).mean(axis=0), index=F).sort_values(ascending=False)
    por.setdefault(t, {})["mar" if a == 0 else "extrema"] = v.round(3).to_dict()
for t in por:
    top = lambda k: ", ".join(list(por[t][k])[:3])
    print(f"  {t:10s} mar: {top('mar'):45s} | extrema: {top('extrema')}")
res["shap"] = {"global": glob.round(3).to_dict(), "por_tipo": por,
               "nota": "promedio del valor absoluto de la contribucion SHAP, en puntos de Stuff+"}
json.dump(res, open("robustez.json", "w"), indent=1, default=float)
print("-> robustez.json")
