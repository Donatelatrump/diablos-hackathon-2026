"""
06 - Exporta todo lo que necesita el dashboard (sin servidor, sin Python).

  public/data/model.json      arboles del modelo en formato compacto
  public/data/meta.json       escala, fisica, validacion, perfil, defaults del simulador
  public/data/pitchers.json   tablero de pitchers
  public/data/arsenal.json    arsenal por pitcher
  lib/stuffModel.ts           evaluador del modelo en TypeScript (y .mjs para pruebas)
"""
import json, os
import numpy as np
import pandas as pd
import lightgbm as lgb
import simcore

OUT = ".."  # raíz del repositorio
os.makedirs(f"{OUT}/public/data", exist_ok=True); os.makedirs(f"{OUT}/lib", exist_ok=True)
booster = lgb.Booster(model_file="stuff_model.txt")
dump = booster.dump_model()
FEATS = dump["feature_names"]

def flat(tree):
    """Recorre un arbol y lo aplana en arreglos: f (feature, -1 = hoja), t (umbral o valor), l, r."""
    f, t, l, r = [], [], [], []
    def go(n):
        i = len(f); f.append(0); t.append(0.0); l.append(-1); r.append(-1)
        if "leaf_value" in n:
            f[i] = -1; t[i] = round(n["leaf_value"], 8); return i
        assert n["decision_type"] == "<="
        f[i] = n["split_feature"]; t[i] = round(float(n["threshold"]), 6)
        l[i] = go(n["left_child"]); r[i] = go(n["right_child"]); return i
    go(tree["tree_structure"]); return [f, t, l, r]

model = {"features": FEATS, "trees": [flat(t) for t in dump["tree_info"]]}
json.dump(model, open(f"{OUT}/public/data/model.json", "w"), separators=(",", ":"))
print(f"model.json: {len(model['trees'])} árboles, {os.path.getsize(f'{OUT}/public/data/model.json')/1e6:.2f} MB")

TS = """// Evaluador del modelo Stuff+ (LightGBM aplanado). Sin dependencias.
export type Tree = [number[], number[], number[], number[]];
export interface StuffModel { features: string[]; trees: Tree[] }

export function predictRV(model: StuffModel, x: Record<string, number>): number {
  const v = model.features.map((k) => x[k]);
  let s = 0;
  for (const [f, t, l, r] of model.trees) {
    let i = 0;
    while (f[i] !== -1) i = v[f[i]] <= t[i] ? l[i] : r[i];
    s += t[i];
  }
  return s;
}

export interface Scale { mean: number; std: number }
/** Stuff+ = 100 + 10 * (media - prediccion) / sd  (mas alto = mejor para el pitcher) */
export function toStuffPlus(rv: number, scale: Scale): number {
  return 100 + (10 * (scale.mean - rv)) / scale.std;
}
"""
open(f"{OUT}/lib/stuffModel.ts", "w").write(TS)
open("stuffModel.test.mjs", "w").write(
    TS.replace("export type Tree = [number[], number[], number[], number[]];\n", "")
      .replace("export interface StuffModel { features: string[]; trees: Tree[] }\n", "")
      .replace("export interface Scale { mean: number; std: number }\n", "")
      .replace("(model: StuffModel, x: Record<string, number>): number", "(model, x)")
      .replace("(rv: number, scale: Scale): number", "(rv, scale)")
    + """
import { readFileSync } from "fs";
const m = JSON.parse(readFileSync(process.argv[2], "utf8"));
const rows = JSON.parse(readFileSync(process.argv[3], "utf8"));
console.log(JSON.stringify(rows.map((x) => predictRV(m, x))));
""")

# ------------------------------------------------------------- meta
meta = json.load(open("model_meta.json"))
EXP = json.load(open("exponentes.json"))
d = pd.read_parquet("scored.parquet")
low_r = d[(d.alt == 0) & (d.PitcherThrows == "Right")]
DEF = {}
for t in ["Four-Seam", "Sinker", "Slider", "Changeup", "Curveball", "Cutter"]:
    x = low_r[low_r.tipo == t]
    DEF[t] = {k: round(float(x[k].median()), 2) for k in
              ["RelSpeed", "ivb", "hb_arm", "SpinRate", "spin_axis_m", "Extension", "RelHeight", "rel_side_arm"]}
fb = low_r[low_r.is_fb == 1]
DEF["_fastball"] = {"fb_relspeed": round(float(fb.RelSpeed.median()), 2), "fb_ivb": round(float(fb.ivb.median()), 2),
                    "fb_hb": round(float(fb.hb_arm.median()), 2), "fb_axis": round(float(fb.spin_axis_m.median()), 1)}
RANGES = {k: [round(float(d[k].quantile(.005)), 1), round(float(d[k].quantile(.995)), 1)]
          for k in ["RelSpeed", "ivb", "hb_arm", "SpinRate", "spin_axis_m", "Extension", "RelHeight", "rel_side_arm"]}
rho = lambda h: 1.225 * (1 - 0.0065 * h / 288.15) ** 4.2559
h0 = EXP["altitudes_m"]["No Altitude"]
SEDES = {"No Altitude": {"alt": 0, "h": EXP["altitudes_m"]["No Altitude"], "label": "Sin altitud (0–700 m)"},
         "Medium Altitude": {"alt": 1, "h": EXP["altitudes_m"]["Medium Altitude"], "label": "Altitud media (800–1,600 m)"},
         "Extreme Altitude": {"alt": 2, "h": EXP["altitudes_m"]["Extreme Altitude"], "label": "Altitud extrema (≥1,800 m)"},
         "Harp Helu": {"alt": 2, "h": 2240.0, "label": "Estadio Alfredo Harp Helú (2,240 m)"}}
for v in SEDES.values():
    v["rho"] = rho(v["h"]); v["rho_ratio"] = rho(v["h"]) / rho(h0)
stuff_pct = {str(a): [round(float(q), 2) for q in x.stuff_plus.quantile(np.linspace(0, 1, 101))]
             for a, x in d.groupby("alt")}
out = {
    "features": FEATS, "scale": meta["scale"], "sedes": SEDES,
    "physics": {"p_magnus_global": EXP["global"]["p_magnus"], "p_drag_global": EXP["global"]["p_drag"],
                "p_magnus_tipo": {k: v["p_magnus"] for k, v in EXP["por_tipo"].items()},
                "ic95_tipo": {k: v["ic95"] for k, v in EXP["por_tipo"].items()},
                "valida_medium": {k: v["valida_medium"] for k, v in EXP["por_tipo"].items()}},
    "defaults": DEF, "ranges": RANGES, "percentiles_por_alt": stuff_pct,
    "validation": {k: meta[k] for k in ["ladder", "oof_corr", "oof_n", "temporal_corr", "temporal_new_corr",
                                        "year_to_year", "small_sample", "importance"]},
    "delta_tipo_proyectado": meta["delta_tipo_proyectado"], "delta_tipo_observado": meta["delta_tipo_observado"],
    "perfil": meta["perfil"],
    # Fuente: verificacion_sin_etiquetas.py (mismo pitcher, tipo invariante, Extreme vs No)
    "perdida_mov_tipo": {"observado": {"Four-Seam": -24.8, "Sinker": -26.1, "Slider": -22.0, "Changeup": -30.7,
                                       "Curveball": -28.6, "Cutter": -22.3},
                         "lineal_densidad": -16.4, "observado_promedio": -25.5,
                         "modelo_fisico_explica_pct": 91, "densidad_sola_explica_pct": 64},
    "calibration": json.load(open("calibration.json")),
    "levers": json.load(open("levers.json")),
    "projection_validation": json.load(open("projection_validation.json")),
    "robustez": json.load(open("robustez.json")),
    "contacto": json.load(open("contacto.json")),
    "smoothing": {"fields": simcore.FIELDS, "sigma": simcore.SIGMA, "offsets": simcore.make_offsets().tolist()},
    "dataset": {"lanzamientos": int(len(d)), "pitchers": int(d.pitcher_anon_id.nunique()),
                "juegos": int(d.game_anon_id.nunique()), "temporadas": sorted(int(y) for y in d.year.unique())},
}
def clean(o):
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list): return [clean(v) for v in o]
    if isinstance(o, float) and not np.isfinite(o): return None
    return o
json.dump(clean(json.loads(json.dumps(out, default=float))), open(f"{OUT}/public/data/meta.json", "w"),
          indent=1, allow_nan=False)

pit = pd.read_parquet("pitchers.parquet").round(2)
pit.to_json(f"{OUT}/public/data/pitchers.json", orient="records")
ars = pd.read_parquet("arsenal.parquet").round(3)
ars.to_json(f"{OUT}/public/data/arsenal.json", orient="records")
for f in ["meta", "pitchers", "arsenal"]:
    print(f"{f}.json: {os.path.getsize(f'{OUT}/public/data/{f}.json')/1e3:.0f} KB")

# ------------------------------------------------------------- prueba de paridad Python vs JS
s = d.sample(500, random_state=1)
s[FEATS].to_json("parity_rows.json", orient="records")
import subprocess
js = np.array(json.loads(subprocess.check_output(
    ["node", "stuffModel.test.mjs", f"{OUT}/public/data/model.json", "parity_rows.json"])))
py = booster.predict(s[FEATS])
print(f"Paridad Python vs JS en 500 lanzamientos: diferencia máxima {np.abs(js - py).max():.2e}")

# ------------------------------------------------------------- arsenal listo para el simulador
# Valores promedio por pitcher x tipo, preferentemente medidos a nivel del mar.
SIMF = ["RelSpeed", "ivb", "hb_arm", "SpinRate", "spin_axis_m", "Extension", "RelHeight", "rel_side_arm"]
SEDE_DE_ALT = {0: "No Altitude", 1: "Medium Altitude", 2: "Extreme Altitude"}
g = d.groupby(["pitcher_anon_id", "tipo", "alt"])
a = g[SIMF].mean().join(g.size().rename("n")).reset_index()
a = a[a.n >= 30].sort_values(["pitcher_anon_id", "tipo", "alt", "n"], ascending=[True, True, True, False])
a = a.groupby(["pitcher_anon_id", "tipo"]).head(1)        # alt mas baja disponible
a["measuredAt"] = a.alt.map(SEDE_DE_ALT)
fbk = d[d.is_fb == 1].groupby(["pitcher_anon_id", "alt"]).agg(
    fbTipo=("tipo", lambda s: s.mode().iat[0]), fb_relspeed=("RelSpeed", "mean"), fb_ivb=("ivb", "mean"),
    fb_hb=("hb_arm", "mean"), fb_axis=("spin_axis_m", "mean")).reset_index()
a = a.merge(fbk, on=["pitcher_anon_id", "alt"], how="left")
a["fbTipo"] = a.fbTipo.where(a.fbTipo.isin(["Four-Seam", "Sinker", "Cutter"]), "Four-Seam")
a["isFastball"] = a.tipo == a.fbTipo
a = a[a.tipo.isin(["Four-Seam", "Sinker", "Slider", "Changeup", "Curveball", "Cutter"])]
a = a[a.pitcher_anon_id.isin(pit.pitcher_anon_id)]
ars2 = ars.merge(a.drop(columns=["alt", "n"]).rename(columns={c: "sim_" + c for c in SIMF}),
                 on=["pitcher_anon_id", "tipo"], how="left")
ars2.round(3).to_json(f"{OUT}/public/data/arsenal.json", orient="records")
print(f"arsenal.json (con campos del simulador): {os.path.getsize(f'{OUT}/public/data/arsenal.json')/1e3:.0f} KB, "
      f"{ars2.sim_RelSpeed.notna().mean()*100:.0f}% filas cargables")

# ------------------------------------------------------------- casos de prueba para la interfaz
def ref_sim(p, measuredAt="No Altitude"):
    return {k: round(v, 3) for k, v in simcore.simulate(booster, out, p, measuredAt).items()}
FB = out["defaults"]["_fastball"]
cases = []
for t in ["Four-Seam", "Slider", "Changeup"]:
    p = {"tipo": t, **out["defaults"][t], "isFastball": t == "Four-Seam", "fbTipo": "Four-Seam",
         "fb_relspeed": FB["fb_relspeed"], "fb_ivb": FB["fb_ivb"], "fb_hb": FB["fb_hb"], "fb_axis": FB["fb_axis"]}
    cases.append({"input": p, "measuredAt": "No Altitude", "expectedStuffPlus": ref_sim(p)})
json.dump(cases, open(f"{OUT}/tests/fixtures.json", "w"), indent=1)
print("fixtures.json:", [(c["input"]["tipo"], c["expectedStuffPlus"]) for c in cases])
