"""Prueba formal de las hipótesis H1 a H4 del reto. El Causal Forest está en 09_causal_forest.py.

Corre sobre lo que ya exportaron los scripts 01 a 07 (artifacts/*.csv, el modelo LightGBM y
artifacts/experimentos.json, que sale de app/scripts/experimentos.ts), así que no necesita los
datos crudos de la LMB.

  H1  La baja densidad reduce el movimiento inducido por giro y castiga más a las formas que más se mueven.
  H2  Los lanzamientos de diferencial de velocidad (cambio) ganan valor relativo en altura.
  H3  Los lanzadores de rodados valen más en altura.
  H4  El giro por sí solo no predice Stuff+: importa cuánto de ese giro se vuelve movimiento.

Toda incertidumbre sale de bootstrap por lanzador (se remuestrean lanzadores, no lanzamientos),
porque los lanzamientos de un mismo brazo no son independientes.
"""
import json, pathlib, warnings

import lightgbm as lgb
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
RAIZ = pathlib.Path(__file__).resolve().parent.parent
ART = RAIZ / "artifacts"
OUT = RAIZ / "app" / "public" / "data"
B = 2000
rng = np.random.default_rng(2026)
ES = {"Four-Seam": "Recta", "Slider": "Slider", "Curveball": "Curva", "Changeup": "Cambio",
      "Sinker": "Sinker", "Cutter": "Cutter", "Splitter": "Splitter"}


def ic(x, q=(2.5, 97.5)):
    lo, hi = np.percentile(x, q)
    return [round(float(lo), 3), round(float(hi), 3)]


def media_p(v, w):
    return float(np.sum(v * w) / np.sum(w))


ars = pd.read_csv(ART / "stuff_por_arsenal.csv")
pit = pd.read_csv(ART / "pitchers_jurado.csv")
spp = pd.read_csv(ART / "stuff_por_pitcher.csv")
alt = json.loads((ART / "altitude_deltas.json").read_text())
exp = json.loads((ART / "experimentos.json").read_text())
out = {}

# ---------------------------------------------------------------------------------------- H1
print("H1…", flush=True)
h1 = {"por_tipo": []}
for t, g in ars.groupby("pitch_type"):
    v, w = g.delta.to_numpy(), g.n.to_numpy()
    boot = [media_p(v[i], w[i]) for i in (rng.integers(0, len(g), len(g)) for _ in range(B))]
    mov_obs = float(np.hypot(alt["ivb"][t]["observado"], alt["hb"][t]["observado"])) if t in alt["ivb"] else None
    h1["por_tipo"].append({"tipo": ES[t], "pitchers": int(len(g)), "delta": round(media_p(v, w), 3), "ic": ic(boot),
                           "d_ivb_obs": alt["ivb"][t]["observado"], "d_hb_obs": alt["hb"][t]["observado"],
                           "celdas_obs": alt["ivb"][t]["n"], "perdida_mov_obs": round(mov_obs, 2) if mov_obs else None})
h1["por_tipo"].sort(key=lambda r: r["delta"], reverse=True)
# ¿pierde más quien más movimiento pierde? (Spearman entre tipos, movimiento perdido medido dentro del lanzador)
tt = [r for r in h1["por_tipo"] if r["celdas_obs"] >= 20]
from scipy.stats import spearmanr
rho, pval = spearmanr([r["perdida_mov_obs"] for r in tt], [r["delta"] for r in tt])
h1["spearman_mov_vs_delta"] = {"rho": round(float(rho), 3), "p": round(float(pval), 4), "tipos": len(tt)}
h1["nathan"] = exp["h1_nathan"]
h1["todos_pierden"] = all(r["ic"][1] < 0 for r in h1["por_tipo"])
out["h1"] = h1

# ---------------------------------------------------------------------------------------- H2
print("H2…", flush=True)
piv = ars.pivot_table(index="pitcher_anon_id", columns="pitch_type", values="delta")
pn = ars.pivot_table(index="pitcher_anon_id", columns="pitch_type", values="n")
h2 = []
for t in ["Changeup", "Cutter", "Slider", "Splitter", "Curveball", "Sinker"]:
    ok = piv[["Four-Seam", t]].dropna().index
    d = (piv.loc[ok, t] - piv.loc[ok, "Four-Seam"]).to_numpy()
    w = np.minimum(pn.loc[ok, t], pn.loc[ok, "Four-Seam"]).to_numpy()
    boot = [media_p(d[i], w[i]) for i in (rng.integers(0, len(d), len(d)) for _ in range(B))]
    h2.append({"tipo": ES[t], "pitchers": int(len(d)), "ventaja_vs_recta": round(media_p(d, w), 3), "ic": ic(boot),
               "pct_pitchers_gana": round(float(np.mean(d > 0)), 3)})
h2.sort(key=lambda r: r["ventaja_vs_recta"], reverse=True)
cam = next(r for r in h2 if r["tipo"] == "Cambio")
out["h2"] = {"pares": h2, "cambio": cam,
             "veredicto": "parcial: el cambio gana valor relativo contra la recta del mismo lanzador, pero menos que cutter, slider y splitter"}

# ---------------------------------------------------------------------------------------- H3
print("H3…", flush=True)
p3 = pit.dropna(subset=["carreras_hh", "carreras_mar"]).copy()
p3["w"] = 2 / (1 / p3.n_hh + 1 / p3.n_mar)          # media armónica: la precisión de una diferencia


def pendiente(x, y, w):
    X = np.column_stack([np.ones_like(x), x])
    W = np.diag(w)
    b = np.linalg.solve(X.T @ W @ X, X.T @ W @ y)
    return float(b[1])


x, w = p3.gb.to_numpy() * 10, p3.w.to_numpy()     # por cada 10 puntos de % de rodados
yh, ym = p3.carreras_hh.to_numpy(), p3.carreras_mar.to_numpy()
est = {"alt": pendiente(x, yh, w), "mar": pendiente(x, ym, w)}
boot = {"alt": [], "mar": [], "dif": []}
for _ in range(B):
    i = rng.integers(0, len(p3), len(p3))
    a, m = pendiente(x[i], yh[i], w[i]), pendiente(x[i], ym[i], w[i])
    boot["alt"].append(a); boot["mar"].append(m); boot["dif"].append(a - m)
terciles = []
p3["tercil"] = pd.qcut(p3.gb, 3, labels=["Pocos rodados", "Medio", "Muchos rodados"])
for k, g in p3.groupby("tercil", observed=True):
    terciles.append({"grupo": str(k), "gb": round(float(g.gb.mean()), 3), "pitchers": int(len(g)),
                     "carreras_mar": round(media_p(g.carreras_mar, g.n_mar), 2),
                     "carreras_hh": round(media_p(g.carreras_hh, g.n_hh), 2)})
for r in terciles:
    r["castigo"] = round(r["carreras_hh"] - r["carreras_mar"], 2)
out["h3"] = {"pitchers": int(len(p3)),
             "pendiente_alt": round(est["alt"], 3), "ic_alt": ic(boot["alt"]),
             "pendiente_mar": round(est["mar"], 3), "ic_mar": ic(boot["mar"]),
             "diferencia": round(est["alt"] - est["mar"], 3), "ic_dif": ic(boot["dif"]),
             "p_una_cola": round(float(np.mean(np.array(boot["dif"]) >= 0)), 4),
             "terciles": terciles,
             "unidad": "carreras por 100 lanzamientos por cada 10 puntos de % de rodados (negativo = previene carreras)"}

# ---------------------------------------------------------------------------------------- H4
print("H4…", flush=True)
bst = lgb.Booster(model_file=str(ART / "model_stuff.txt"))
gain = pd.Series(bst.feature_importance("gain"), index=bst.feature_name())
gain = gain / gain.sum()
grupos = {
    "Giro (rpm)": ["SpinRate"],
    "Movimiento (quiebres)": ["InducedVertBreak", "HorzBreak", "VertBreak", "movement_total"],
    "Giro que se vuelve movimiento (eficiencia)": ["spin_efficiency"],
    "Eje de giro": ["SpinAxis"],
    "Velocidad": ["RelSpeed", "EffectiveVelo", "ZoneSpeed", "SpeedDrop", "ZoneTime"],
    "Punto de salida": ["RelHeight", "RelSide", "Extension"],
    "Mano": ["is_rhp"],
}
# Sólo las variables que el modelo tiene: los ángulos de salida y llegada ya no entran (codifican puntería).
grupos = {k: [f for f in v if f in gain.index] for k, v in grupos.items()}
grupos = {k: v for k, v in grupos.items() if v}
imp = sorted(({"grupo": k, "peso": round(float(gain[v].sum()), 4)} for k, v in grupos.items()), key=lambda r: -r["peso"])
rank = {f: i + 1 for i, f in enumerate(gain.sort_values(ascending=False).index)}
out["h4"] = {"importancia": imp, "rango_spinrate": rank["SpinRate"], "n_features": len(rank),
             "top5": [{"f": f, "peso": round(float(gain[f]), 4)} for f in gain.sort_values(ascending=False).index[:5]],
             "experimento": exp["h4"]}

# El Causal Forest vive en scripts/09_causal_forest.py.

(ART / "hipotesis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, allow_nan=False))
(OUT / "hipotesis.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
print(json.dumps({k: v for k, v in out.items() if k != "h4"}, ensure_ascii=False, indent=1)[:6000])
print(json.dumps(out["h4"]["importancia"], ensure_ascii=False))
