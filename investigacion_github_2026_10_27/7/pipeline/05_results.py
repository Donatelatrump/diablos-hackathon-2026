"""
05 - Resultados: escala final, efecto CDMX proyectado, perfil ideal, tableros.

Escala: Stuff+ = 100 + 10 * (media - prediccion) / sd, con media y sd tomadas de
los promedios pitcher x tipo (>=100 lanz.) dentro de cada categoria de altitud.
Asi 110 = una desviacion estandar arriba del lanzamiento tipico de la liga en
ese tipo de sede.

Proyeccion a CDMX: cada lanzamiento lanzado a nivel del mar se "traslada" al
Harp Helu reduciendo su movimiento inducido con la ley fisica validada
(fuerza Magnus proporcional a rho^p, p por tipo) y se vuelve a calificar con
el modelo en contexto de altitud extrema.
"""
import json
import numpy as np
import pandas as pd
import lightgbm as lgb

d = pd.read_parquet("scored.parquet")
meta = json.load(open("model_meta.json"))
FEATS = meta["features"]
model = lgb.Booster(model_file="stuff_model.txt")
EXP = json.load(open("exponentes.json"))

# ---------------------------------------------------------- escala final
sc = {}
for a, x in d.groupby("alt"):
    g = x.groupby(["pitcher_anon_id", "AutoPitchType"]).agg(p=("pred", "mean"), n=("pred", "size"))
    g = g[g.n >= 100]
    sc[int(a)] = dict(mean=float(g.p.mean()), std=float(g.p.std()))
def to_plus(pred, alt):
    m = np.array([sc[int(a)]["mean"] for a in np.atleast_1d(alt)])
    s = np.array([sc[int(a)]["std"] for a in np.atleast_1d(alt)])
    return 100 + 10 * (m - pred) / s
d["stuff_plus"] = to_plus(d.pred.values, d.alt.values)
print("Escala por categoría:", {k: {kk: round(vv, 5) for kk, vv in v.items()} for k, v in sc.items()})

TYPE_MAP = {"Four-Seam": "Four-Seam", "Sinker": "Sinker", "Slider": "Slider", "Sweeper": "Slider",
            "Changeup": "Changeup", "Splitter": "Changeup", "Curveball": "Curveball", "Cutter": "Cutter"}
d["tipo"] = d.AutoPitchType.map(TYPE_MAP).fillna("Otro")

# ---------------------------------------------------------- proyeccion a CDMX
rho = lambda h: 1.225 * (1 - 0.0065 * h / 288.15) ** 4.2559
R_CDMX = rho(2240) / rho(EXP["altitudes_m"]["No Altitude"])
P = {k: v["p_magnus"] for k, v in EXP["por_tipo"].items()}
pglob = EXP["global"]["p_magnus"]
fac = lambda t: R_CDMX ** P.get(t, pglob)

low = d[d.alt == 0].copy()
f_pitch = low.tipo.map(fac).fillna(R_CDMX ** pglob).values
# recta principal del pitcher en esa temporada: su tipo determina su factor
fbtype = low[low.is_fb == 1].groupby(["pitcher_anon_id", "year"]).tipo.agg(lambda s: s.mode().iat[0])
f_fb = low.join(fbtype.rename("fbt"), on=["pitcher_anon_id", "year"]).fbt.map(fac).fillna(fac("Four-Seam")).values
X = low[FEATS].copy()
X["ivb"] *= f_pitch; X["hb_arm"] *= f_pitch
X["fb_ivb"] *= f_fb
fb_hb = low.hb_arm - low.d_hb
X["d_ivb"] = X.ivb - X.fb_ivb
X["d_hb"] = X.hb_arm - fb_hb * f_fb
X["alt"] = 2
low["stuff_cdmx"] = to_plus(model.predict(X), np.full(len(X), 2))
low["delta_cdmx"] = low.stuff_cdmx - low.stuff_plus

print("\nΔ Stuff+ proyectado al trasladar lanzamientos de nivel del mar al Harp Helú, por tipo:")
dt = low.groupby("tipo").agg(stuff_mar=("stuff_plus", "mean"), stuff_cdmx=("stuff_cdmx", "mean"),
                             delta=("delta_cdmx", "mean"), n=("delta_cdmx", "size"))
dt = dt[dt.n > 1000].sort_values("delta").round(2)
print(dt.to_string())

# observado: mismo pitcher y tipo, Extreme vs No (posicion relativa dentro de cada sede)
g = d.groupby(["pitcher_anon_id", "tipo", "alt"]).agg(s=("stuff_plus", "mean"), n=("rv", "size")).reset_index()
g = g[g.n >= 50]
w = g.pivot_table(index=["pitcher_anon_id", "tipo"], columns="alt", values="s").dropna(subset=[0, 2])
obs = (w[2] - w[0]).groupby(level="tipo").agg(["mean", "size"]).round(2)
print("\nObservado (mismo pitcher y tipo, Extreme − No, >=50 lanz. por celda):"); print(obs.to_string())

# ---------------------------------------------------------- perfil ideal en altitud extrema
print("\nPerfil físico: cuartil superior de Stuff+ vs. promedio, en altitud extrema y a nivel del mar")
VARS = {"RelSpeed": "velocidad (mph)", "ivb": "IVB (in)", "hb_arm": "HB lado brazo (in)",
        "SpinRate": "spin (rpm)", "Extension": "extensión (ft)", "RelHeight": "altura liberación (ft)",
        "d_velo": "Δ velo vs recta (mph)", "d_ivb": "Δ IVB vs recta (in)", "d_hb": "Δ HB vs recta (in)"}
perfil = {}
for t in ["Four-Seam", "Sinker", "Slider", "Changeup", "Curveball", "Cutter"]:
    perfil[t] = {}
    for a, nom in [(0, "mar"), (2, "extrema")]:
        x = d[(d.tipo == t) & (d.alt == a)]
        top = x[x.stuff_plus >= x.stuff_plus.quantile(0.75)]
        perfil[t][nom] = {v: dict(top=float(top[v].mean()), avg=float(x[v].mean())) for v in VARS}
    print(f"\n  {t}")
    for v, lab in VARS.items():
        e, m = perfil[t]["extrema"][v], perfil[t]["mar"][v]
        print(f"    {lab:26s} extrema: top {e['top']:7.1f} vs prom {e['avg']:7.1f}  |  mar: top {m['top']:7.1f} vs prom {m['avg']:7.1f}")

# ---------------------------------------------------------- tableros
pit = d.groupby(["pitcher_anon_id"]).agg(
    mano=("PitcherThrows", "first"), n=("rv", "size"), stuff=("stuff_plus", "mean"),
    rv100=("rv", lambda s: 100 * s.mean()))
for a, nom in [(0, "stuff_mar"), (1, "stuff_media"), (2, "stuff_extrema")]:
    x = d[d.alt == a].groupby("pitcher_anon_id").agg(s=("stuff_plus", "mean"), n=("rv", "size"))
    pit[nom] = x.s.where(x.n >= 50); pit["n_" + nom.split("_")[1]] = x.n
proj = low.groupby("pitcher_anon_id").agg(stuff_cdmx_proy=("stuff_cdmx", "mean"), n_proy=("rv", "size"))
pit = pit.join(proj)
pit["delta_cdmx_proy"] = pit.stuff_cdmx_proy - pit.stuff_mar
pit = pit[pit.n >= 300].sort_values("stuff", ascending=False)
ars = d.groupby(["pitcher_anon_id", "tipo"]).agg(
    n=("rv", "size"), stuff=("stuff_plus", "mean"), velo=("RelSpeed", "mean"), ivb=("ivb", "mean"),
    hb=("hb_arm", "mean"), spin=("SpinRate", "mean")).reset_index()
ars = ars[(ars.n >= 50) & ars.pitcher_anon_id.isin(pit.index)]
ars = ars.join(low.groupby(["pitcher_anon_id", "tipo"]).delta_cdmx.mean(), on=["pitcher_anon_id", "tipo"])
ars["uso"] = ars.n / ars.groupby("pitcher_anon_id").n.transform("sum")
print(f"\nPitchers en tablero (>=300 lanz.): {len(pit)} | filas de arsenal: {len(ars)}")
print("\nTop 10 Stuff+:"); print(pit.head(10)[["mano", "n", "stuff", "stuff_mar", "stuff_extrema", "delta_cdmx_proy"]].round(1).to_string())
print("\nMejor 'viajan' a CDMX (Δ proyectado, >=500 lanz. a nivel del mar):")
print(pit[pit.n_proy >= 500].sort_values("delta_cdmx_proy", ascending=False).head(8)[["mano", "stuff_mar", "stuff_cdmx_proy", "delta_cdmx_proy"]].round(1).to_string())

pit.reset_index().to_parquet("pitchers.parquet", index=False)
ars.to_parquet("arsenal.parquet", index=False)
d.to_parquet("scored.parquet", index=False)
meta["scale"] = {str(k): v for k, v in sc.items()}
meta["cdmx_rho_ratio"] = R_CDMX
meta["delta_tipo_proyectado"] = dt.reset_index().to_dict("records")
meta["delta_tipo_observado"] = obs.reset_index().to_dict("records")
meta["perfil"] = perfil
json.dump(meta, open("model_meta.json", "w"), indent=2, default=float)
print("\n-> pitchers.parquet, arsenal.parquet, model_meta.json actualizados")
