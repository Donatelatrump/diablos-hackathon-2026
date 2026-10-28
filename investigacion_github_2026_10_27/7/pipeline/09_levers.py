"""
09 - Palancas de desarrollo: ¿que cambio sube mas el Stuff+ de un tipo de lanzamiento?

Efecto promedio de un cambio pequeño (por ejemplo +1 mph) sobre miles de
lanzamientos reales de ese tipo en cada categoria de altitud. Se usa el efecto
promedio y no el calculo sobre un solo lanzamiento porque un modelo de arboles
tiene ondulaciones locales: el promedio sobre lanzamientos reales es estable y
refleja lo que el modelo aprendio para ese tipo de lanzamiento.

Si el lanzamiento es la recta principal del pitcher, cambiarlo tambien cambia la
referencia contra la que se comparan sus otros lanzamientos; aqui se evalua solo
el efecto sobre el propio lanzamiento.
"""
import json
import numpy as np
import pandas as pd
import lightgbm as lgb

d = pd.read_parquet("scored.parquet")
meta = json.load(open("model_meta.json")); F = meta["features"]
b = lgb.Booster(model_file="stuff_model.txt")
STEPS = {"RelSpeed": 1.0, "ivb": 1.0, "hb_arm": 1.0, "SpinRate": 100.0, "spin_axis_m": 10.0, "Extension": 0.25}
DIFF = {"RelSpeed": ("d_velo", "fb_relspeed"), "ivb": ("d_ivb", "fb_ivb"), "hb_arm": ("d_hb", None),
        "spin_axis_m": ("d_axis", None)}
TIPOS = ["Four-Seam", "Sinker", "Slider", "Changeup", "Curveball", "Cutter"]
N = 8000

def shift(x, k, delta):
    y = x.copy(); y[k] = y[k] + delta
    if k in DIFF:
        dk, fbk = DIFF[k]
        y[dk] = y[dk] + delta * (1 - y.is_fb)          # no-recta: cambia su diferencia vs. la recta
        if fbk is not None:
            y.loc[y.is_fb == 1, fbk] += delta          # recta: cambia la referencia
    return y

out = {}
for a in [0, 1, 2]:
    sc = meta["scale"][str(a)]
    plus = lambda p: 100 + 10 * (sc["mean"] - p) / sc["std"]
    out[str(a)] = {}
    for t in TIPOS:
        x = d[(d.alt == a) & (d.tipo == t)]
        x = x.sample(min(N, len(x)), random_state=0)[F + ["is_fb"]]
        base = plus(b.predict(x[F]))
        out[str(a)][t] = {}
        for k, st in STEPS.items():
            r = {}
            for sgn, nom in [(1, "mas"), (-1, "menos")]:
                e = plus(b.predict(shift(x, k, sgn * st)[F])) - base
                r[nom] = round(float(e.mean()), 3); r[nom + "_se"] = round(float(e.std() / np.sqrt(len(e))), 3)
            out[str(a)][t][k] = r
    print(f"altitud {a} lista")

print("\nAltitud extrema, mejor dirección por palanca (Δ Stuff+ promedio):")
for t in TIPOS:
    row = []
    for k, st in STEPS.items():
        r = out["2"][t][k]; best = "mas" if r["mas"] >= r["menos"] else "menos"
        row.append(f"{k} {'+' if best=='mas' else '−'}{st:g}: {max(r['mas'], r['menos']):+.2f}")
    print(f"  {t:10s} " + " | ".join(row))
json.dump({"pasos": STEPS, "efecto": out}, open("levers.json", "w"), indent=1)
print("-> levers.json")
