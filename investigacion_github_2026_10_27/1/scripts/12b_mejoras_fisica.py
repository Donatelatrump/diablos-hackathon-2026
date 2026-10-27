"""Etapa 12b, local. Segunda prueba controlada: frenado relativo al aire y variables nuevas de física, misma validación."""
import json, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, ".")
from src.stuffplus import features as F, models

df = pd.read_pickle("artifacts/model_frame.pkl").reset_index(drop=True)
g = df.pitcher_anon_id.astype(str).fillna("x").to_numpy()
rv = df.rv.to_numpy()
mano = np.where(df.is_rhp.to_numpy() == 1, 1.0, -1.0)

# 4. frenado relativo al aire del juego: lo que frena la pelota dividido entre lo que frenaría en ese aire
df["SpeedDrop_rel"] = df.SpeedDrop / df.rho_game
df["ZoneSpeed_rel"] = df.RelSpeed - df.SpeedDrop_rel
# 5a. todo horizontal en dirección del brazo, para que zurdos y derechos compartan escala
df["HB_brazo"] = df.HorzBreak * mano
df["RelSide_brazo"] = df.RelSide * mano
df["SpinAxis_brazo"] = np.where(mano > 0, df.SpinAxis, 360 - df.SpinAxis)
# 5b. desfase del eje: dirección en que se movió contra la que indica el eje de giro (efecto de la costura)
dir_obs = np.degrees(np.arctan2(-df.HorzBreak, -df.InducedVertBreak)) % 360
dev = (dir_obs - df.SpinAxis + 180) % 360 - 180
df["desfase_eje"] = dev * mano
print("desfase eje, mediana absoluta", float(np.nanmedian(np.abs(dev))), flush=True)
# 5c. consistencia del punto de salida del lanzador con ese tipo de lanzamiento
k = ["pitcher_anon_id", "pitch_type"] if "pitch_type" in df else ["pitcher_anon_id"]
sd = df.groupby(k, observed=True)[["RelHeight", "RelSide"]].transform("std")
df["salida_sd"] = np.hypot(sd.RelHeight, sd.RelSide)

null = df.groupby("count")["rv"].transform("mean").to_numpy()
def r2(y, p): return 1 - np.mean((y - p) ** 2) / np.var(y)
base = list(F.SHAPE)
def cambia(fs, viejo, nuevo): return [nuevo.get(c, c) for c in fs if c not in viejo] + [v for v in nuevo.values() if v not in fs]
frenado = [c for c in base if c not in ("SpeedDrop", "ZoneSpeed")] + ["SpeedDrop_rel", "ZoneSpeed_rel"]
brazo = [c for c in base if c not in ("HorzBreak", "RelSide", "SpinAxis")] + ["HB_brazo", "RelSide_brazo", "SpinAxis_brazo"]
variantes = {"actual": base, "frenado_relativo": frenado, "brazo": brazo, "desfase_eje": base + ["desfase_eje"],
             "consistencia_salida": base + ["salida_sd"],
             "todas": [c for c in frenado if c not in ("HorzBreak", "RelSide", "SpinAxis")] + ["HB_brazo", "RelSide_brazo", "SpinAxis_brazo", "desfase_eje", "salida_sd"]}
p_s, n_s = models.capa("stuff")
rng = np.random.default_rng(0); mitad = rng.random(len(df)) < 0.5
res = {}
for nom, feats in variantes.items():
    t0 = time.time()
    oof, _ = models.cross_val(df, feats, target="rv", n_splits=4, params=p_s, n_rounds=n_s)
    ok = np.isfinite(oof)
    pred = oof - np.nanmean(oof) + null
    d = {"variables": len(feats), "r2_vs_rv": float(r2(rv[ok], pred[ok])), "corr_rv": float(np.corrcoef(rv[ok], oof[ok])[0, 1])}
    q = pd.qcut(oof, 10, labels=False, duplicates="drop")
    d["brecha_100"] = float((rv[q == 9].mean() - rv[q == 0].mean()) * 100)
    t = pd.DataFrame({"p": g, "s": -oof, "r": -rv, "h": mitad, "y": df.year.to_numpy()})
    a = t.groupby(["p", "h"]).agg(s=("s", "mean"), n=("s", "size")).unstack()
    a = a[(a["n"] >= 150).all(axis=1)]
    d["mitades"] = float(np.corrcoef(a["s"][False], a["s"][True])[0, 1])
    py = t.groupby(["p", "y"]).agg(s=("s", "mean"), r=("r", "mean"), n=("s", "size")).reset_index()
    py = py[py.n >= 300]
    pares = py.merge(py.assign(y=py.y - 1)[["p", "y", "r"]].rename(columns={"r": "r_sig"}), on=["p", "y"])
    d["futuro_stuff"] = float(np.corrcoef(pares.s, pares.r_sig)[0, 1])
    # ¿la calificación sigue sin saber dónde cayó la pelota?
    d["corr_distancia_zona"] = float(np.corrcoef(oof[ok], df.plate_dist.to_numpy()[ok])[0, 1]) if "plate_dist" in df else None
    d["segundos"] = round(time.time() - t0, 1)
    res[nom] = d
    print(nom, json.dumps({k: (round(v, 5) if isinstance(v, float) else v) for k, v in d.items()}), flush=True)
for f in ("artifacts/robustez.json", "app/public/data/robustez.json"):
    R = json.load(open(f))
    R.setdefault("mejoras", {}).update({k: v for k, v in res.items() if k != "actual"})
    json.dump(R, open(f, "w"), indent=2, ensure_ascii=False)
print("listo")
