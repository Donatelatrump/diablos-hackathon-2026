"""
08 - ¿Que significa un punto de Stuff+ en el campo?

Agrupa combinaciones pitcher x tipo x sede (>=100 lanzamientos) por nivel de
Stuff+ y mide lo que realmente paso con esos lanzamientos:
  - carreras permitidas por cada 100 lanzamientos, frente al promedio de su tipo de sede
  - % de fallos por swing (whiff%)
  - % de strikes cantados o con swing fallado (CSW%)
  - % de contacto fuerte (bolas en juego a 95 mph o mas)
Y la pendiente: cuanto cambia cada cosa por cada 10 puntos de Stuff+.
"""
import sys, json
import numpy as np
import pandas as pd

SRC = sys.argv[1] if len(sys.argv) > 1 else "../data/stuff_model_df.parquet"
d = pd.read_parquet("scored.parquet", columns=["PitchUID", "pitcher_anon_id", "tipo", "alt", "rv", "stuff_plus"])
o = pd.read_parquet(SRC, columns=["PitchUID", "is_swing", "is_whiff", "is_called_strike", "PitchCall", "ExitSpeed"])
o["PitchCall"] = o.PitchCall.astype(str)
d = d.merge(o, on="PitchUID", how="left")
d["bip"] = d.PitchCall == "InPlay"
d["hard"] = d.bip & (d.ExitSpeed >= 95)
d["rv_rel"] = d.rv - d.groupby("alt").rv.transform("mean")      # vs. promedio de su tipo de sede

g = d.groupby(["pitcher_anon_id", "tipo", "alt"]).agg(
    n=("rv", "size"), s=("stuff_plus", "mean"), rv100=("rv_rel", lambda x: 100 * x.mean()),
    sw=("is_swing", "sum"), wh=("is_whiff", "sum"), cs=("is_called_strike", "sum"),
    bip=("bip", "sum"), hard=("hard", "sum")).reset_index()
g = g[g.n >= 100]
BINS = [-np.inf, 90, 95, 100, 105, 110, np.inf]
LAB = ["< 90", "90–95", "95–100", "100–105", "105–110", "≥ 110"]
g["nivel"] = pd.cut(g.s, BINS, labels=LAB)
t = g.groupby("nivel", observed=True).apply(lambda x: pd.Series({
    "combinaciones": len(x), "lanzamientos": int(x.n.sum()),
    "carreras_100": float(np.average(x.rv100, weights=x.n)),
    "whiff_pct": 100 * x.wh.sum() / x.sw.sum(),
    "csw_pct": 100 * (x.wh.sum() + x.cs.sum()) / x.n.sum(),
    "contacto_fuerte_pct": 100 * x.hard.sum() / x.bip.sum()}), include_groups=False).reset_index()
print("Lo que pasó con los lanzamientos según su nivel de Stuff+ (pitcher × tipo × sede, ≥100 lanz.):")
print(t.round(2).to_string(index=False))

def slope(y, w):
    X = np.c_[np.ones(len(g)), g.s / 10]
    W = np.sqrt(w)
    return float(np.linalg.lstsq(X * W[:, None], y * W, rcond=None)[0][1])
sl = {"carreras_100": slope(g.rv100.values, g.n.values),
      "whiff_pct": slope(100 * g.wh / g.sw.clip(lower=1), g.sw.values),
      "csw_pct": slope(100 * (g.wh + g.cs) / g.n, g.n.values),
      "contacto_fuerte_pct": slope(100 * g.hard / g.bip.clip(lower=1), g.bip.values)}
per1000 = -10 * sl["carreras_100"]
print(f"\nPor cada 10 puntos de Stuff+: {sl['carreras_100']:+.2f} carreras por 100 lanzamientos "
      f"({per1000:.1f} carreras menos por cada 1,000 lanzamientos), whiff {sl['whiff_pct']:+.1f} pp, "
      f"CSW {sl['csw_pct']:+.1f} pp, contacto fuerte {sl['contacto_fuerte_pct']:+.1f} pp")
json.dump({"tabla": t.to_dict("records"), "por_10_puntos": sl, "carreras_por_1000_lanz_por_10_puntos": per1000,
           "nota": "pitcher x tipo x sede con >=100 lanzamientos; carreras relativas al promedio de su tipo de sede"},
          open("calibration.json", "w"), indent=2, default=float)
print("-> calibration.json")
