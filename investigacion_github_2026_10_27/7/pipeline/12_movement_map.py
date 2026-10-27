"""
12 - Datos del mapa de movimiento: la forma de cada lanzamiento de la liga y su Stuff+.

Una fila por pitcher x tipo con al menos 50 lanzamientos a nivel del mar: su movimiento promedio
(IVB y HB hacia el lado del brazo) medido a nivel del mar, el mismo movimiento trasladado al Harp
Helu con la ley fisica, su Stuff+ a nivel del mar y su Stuff+ proyectado en el Harp Helu (05_results).
Permite ver que formas son las mas y menos efectivas en cada sede.
"""
import json, os
import numpy as np
import pandas as pd

OUT = os.environ.get("OUT", "..")
d = pd.read_parquet("scored.parquet", columns=["pitcher_anon_id", "tipo", "alt", "stuff_plus", "ivb", "hb_arm", "RelSpeed"])
ars = pd.read_parquet("arsenal.parquet")[["pitcher_anon_id", "tipo", "delta_cdmx"]]
meta = json.load(open(f"{OUT}/public/data/meta.json"))
R = meta["sedes"]["Harp Helu"]["rho_ratio"]; P = meta["physics"]["p_magnus_tipo"]
TIPOS = ["Four-Seam", "Sinker", "Slider", "Changeup", "Curveball", "Cutter"]

x = d[(d.alt == 0) & d.tipo.isin(TIPOS)].groupby(["pitcher_anon_id", "tipo"]).agg(
    n=("stuff_plus", "size"), s_mar=("stuff_plus", "mean"), ivb=("ivb", "mean"), hb=("hb_arm", "mean"),
    velo=("RelSpeed", "mean")).reset_index()
x = x[x.n >= 50].merge(ars, on=["pitcher_anon_id", "tipo"], how="inner").dropna(subset=["delta_cdmx"])
x["s_hh"] = x.s_mar + x.delta_cdmx
f = x.tipo.map(lambda t: R ** P[t])
x["ivb_hh"] = x.ivb * f; x["hb_hh"] = x.hb * f
# percentil dentro de su tipo, para resaltar los mas y menos efectivos
for c in ["s_mar", "s_hh"]:
    x[c + "_pct"] = x.groupby("tipo")[c].rank(pct=True).mul(100).round()
cols = ["tipo", "n", "velo", "ivb", "hb", "ivb_hh", "hb_hh", "s_mar", "s_hh", "s_mar_pct", "s_hh_pct"]
rows = x[cols].round({"velo": 1, "ivb": 1, "hb": 1, "ivb_hh": 1, "hb_hh": 1, "s_mar": 1, "s_hh": 1})
json.dump({"nota": "pitcher x tipo con >=50 lanzamientos a nivel del mar; movimiento en pulgadas, HB hacia el lado del brazo",
           "formas": rows.to_dict("records")}, open(f"{OUT}/public/data/movement_map.json", "w"), separators=(",", ":"))
print(f"movement_map.json: {len(rows)} formas, {os.path.getsize(f'{OUT}/public/data/movement_map.json')/1e3:.0f} KB")
print(rows.groupby("tipo").agg(n=("s_hh", "size"), s_mar=("s_mar", "mean"), s_hh=("s_hh", "mean")).round(1).to_string())
