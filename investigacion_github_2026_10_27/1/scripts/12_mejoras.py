"""Etapa 12, local. Prueba controlada de dos mejoras a Stuff+, con la misma validación agrupada por lanzador.

  objetivo xRV   cada batazo vale lo que se espera de su velocidad de salida y su ángulo, no si fue hit
  arsenal        las diferencias contra la recta del mismo lanzador entran a Stuff+
Todas las métricas se miden contra las carreras reales (rv), para que la comparación sea justa.
"""
import json, sys, time
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.model_selection import GroupKFold
sys.path.insert(0, ".")
from src.stuffplus import features as F, models

df = pd.read_pickle("artifacts/model_frame.pkl").reset_index(drop=True)
g = df.pitcher_anon_id.astype(str).fillna("x").to_numpy()
rv = df.rv.to_numpy()

# --- 1. objetivo sin ruido de batazo: xRV = E[rv | velocidad de salida, ángulo], fuera de muestra por lanzador
bip = (df.is_ball_in_play.fillna(0).to_numpy() == 1) & df.ExitSpeed.notna().to_numpy() & df.Angle.notna().to_numpy()
xrv = rv.copy()
Xb = df.loc[bip, ["ExitSpeed", "Angle"]].to_numpy(float); yb = rv[bip]; gb = g[bip]
pb = np.full(bip.sum(), np.nan)
for tr, te in GroupKFold(4).split(Xb, groups=gb):
    m = lgb.train({"objective": "regression", "learning_rate": 0.05, "num_leaves": 31, "min_data_in_leaf": 200, "verbose": -1},
                  lgb.Dataset(Xb[tr], yb[tr]), 300)
    pb[te] = m.predict(Xb[te])
xrv[bip] = pb
df["xrv"] = xrv
print(f"batazos {bip.sum():,}  var rv {np.var(rv):.5f}  var xrv {np.var(xrv):.5f}  corr {np.corrcoef(rv, xrv)[0,1]:.3f}", flush=True)

null = df.groupby("count")["rv"].transform("mean").to_numpy()
def r2(y, p): return 1 - np.mean((y - p) ** 2) / np.var(y)
def rmse(y, p): return float(np.sqrt(np.mean((y - p) ** 2)))

ARS = ["velo_diff_vs_fb", "ivb_diff_vs_fb", "hb_diff_vs_fb", "movement_diff_vs_fb"]
p_s, n_s = models.capa("stuff")
variantes = {"actual": (F.SHAPE, "rv"), "xrv": (F.SHAPE, "xrv"), "arsenal": (F.SHAPE + ARS, "rv"), "xrv_arsenal": (F.SHAPE + ARS, "xrv")}
res = {"null": {"rmse": rmse(rv, null), "r2": r2(rv, null)}}
rng = np.random.default_rng(0)
mitad = rng.random(len(df)) < 0.5
for nom, (feats, tgt) in variantes.items():
    t0 = time.time()
    oof, _ = models.cross_val(df, feats, target=tgt, n_splits=4, params=p_s, n_rounds=n_s)
    ok = np.isfinite(oof)
    # escala igual que Stuff+: centro y escala de la liga; el predicho de carreras se recentra por conteo como el nulo
    pred = oof - np.nanmean(oof) + null  # mismo nivel por conteo que el nulo
    d = {"variables": len(feats), "objetivo": tgt,
         "r2_vs_rv": float(r2(rv[ok], pred[ok])), "rmse_vs_rv": rmse(rv[ok], pred[ok]),
         "r2_vs_rv_crudo": float(r2(rv[ok], oof[ok])),
         "corr_rv": float(np.corrcoef(rv[ok], oof[ok])[0, 1])}
    q = pd.qcut(oof, 10, labels=False, duplicates="drop")
    d["brecha_100"] = float((rv[q == 9].mean() - rv[q == 0].mean()) * 100)   # peor 10 % (más carreras) menos mejor
    t = pd.DataFrame({"p": g, "s": -oof, "r": -rv, "h": mitad, "y": df.year.to_numpy()})
    a = t.groupby(["p", "h"]).agg(s=("s", "mean"), r=("r", "mean"), n=("s", "size")).unstack()
    a = a[(a["n"] >= 150).all(axis=1)]
    d["mitades"] = float(np.corrcoef(a["s"][False], a["s"][True])[0, 1]); d["mitades_n"] = int(len(a))
    py = t.groupby(["p", "y"]).agg(s=("s", "mean"), r=("r", "mean"), n=("s", "size")).reset_index()
    py = py[py.n >= 300]
    nx = py.assign(y=py.y - 1)[["p", "y", "r"]].rename(columns={"r": "r_sig"})
    pares = py.merge(nx, on=["p", "y"])
    d["futuro_stuff"] = float(np.corrcoef(pares.s, pares.r_sig)[0, 1])
    d["futuro_carreras"] = float(np.corrcoef(pares.r, pares.r_sig)[0, 1]); d["pares"] = int(len(pares))
    d["segundos"] = round(time.time() - t0, 1)
    res[nom] = d
    print(nom, json.dumps({k: (round(v, 5) if isinstance(v, float) else v) for k, v in d.items()}), flush=True)
# Se guarda como una prueba más de robustez, para que el documento, el reporte y el dashboard la lean solos.
for f in ("artifacts/robustez.json", "app/public/data/robustez.json"):
    try:
        R = json.load(open(f))
    except FileNotFoundError:
        R = {}
    R["mejoras"] = res
    json.dump(R, open(f, "w"), indent=2, ensure_ascii=False)
print("listo")
