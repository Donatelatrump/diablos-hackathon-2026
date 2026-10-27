"""
11 - Riesgo de contacto duro y jonron por perfil en altitud, e hipotesis H3 (rodados).

Compara sedes sin altitud contra altitud extrema usando solo pitchers que lanzaron en ambas
(misma composicion de pitchers en las dos columnas).

  A. Por tipo de lanzamiento: % de contacto duro (>= 95 mph) por bola en juego, jonrones por cada
     100 bolas en juego y valor de carrera por bola en juego.
  B. Perfiles de recta: "ride" alto contra bajo (tercio superior e inferior de IVB a nivel del mar).
  C. H3: ¿un rodado vale relativamente mas en altitud? Valor medio en carreras de cada tipo de batazo
     por sede, y correlacion entre % de rodados de un pitcher y las carreras que permite, por sede.
"""
import sys, json
import numpy as np
import pandas as pd

SRC = sys.argv[1] if len(sys.argv) > 1 else "../data/stuff_model_df.parquet"
LW = json.load(open("target_params.json"))
EV_LW = {"Out": LW["LW_out"], "Single": LW["LW_1B"], "Double": LW["LW_2B"], "Triple": LW["LW_3B"],
         "HomeRun": LW["LW_HR"], "Error": LW["LW_E"], "FieldersChoice": LW["LW_FC"], "Sacrifice": LW["LW_SAC"]}

d = pd.read_parquet("scored.parquet", columns=["PitchUID", "pitcher_anon_id", "tipo", "alt", "ivb", "is_fb", "rv"])
o = pd.read_parquet(SRC, columns=["PitchUID", "PitchCall", "play_result", "hit_type", "ExitSpeed"])
for c in ["PitchCall", "play_result"]: o[c] = o[c].astype(str)
d = d.merge(o, on="PitchUID")
d = d[d.alt.isin([0, 2])]
both = d.groupby("pitcher_anon_id").alt.nunique(); d = d[d.pitcher_anon_id.isin(both[both == 2].index)]
bip = d[d.PitchCall == "InPlay"].copy()
bip["valor"] = bip.play_result.map(EV_LW).fillna(LW["LW_out"])
bip["duro"] = bip.ExitSpeed >= 95
bip["hr"] = bip.play_result == "HomeRun"
SEDE = {0: "mar", 2: "extrema"}
res = {"pitchers": int(d.pitcher_anon_id.nunique())}

def tabla(x, by):
    g = x.groupby(by + ["alt"]).agg(bip=("valor", "size"), duro=("duro", "mean"), hr=("hr", "mean"), valor=("valor", "mean"))
    g = g.unstack("alt")
    out = pd.DataFrame({
        "bip_mar": g["bip"][0], "bip_extrema": g["bip"][2],
        "duro_mar": 100 * g["duro"][0], "duro_extrema": 100 * g["duro"][2],
        "hr100_mar": 100 * g["hr"][0], "hr100_extrema": 100 * g["hr"][2],
        "valor_mar": g["valor"][0], "valor_extrema": g["valor"][2]})
    out["hr_riesgo_pct"] = 100 * (out.hr100_extrema / out.hr100_mar - 1)
    out["valor_extra"] = out.valor_extrema - out.valor_mar
    return out

# A. por tipo
A = tabla(bip[bip.tipo.isin(["Four-Seam", "Sinker", "Slider", "Changeup", "Curveball", "Cutter"])], ["tipo"])
A = A.sort_values("hr_riesgo_pct", ascending=False)
print(f"A. Por tipo de lanzamiento ({res['pitchers']} pitchers que lanzaron en ambas sedes)")
print(A.round(2).to_string())
tot = tabla(bip.assign(t="Todos"), ["t"]); print(tot.round(2).to_string())

# B. perfiles de recta por "ride" (IVB medido a nivel del mar, por pitcher)
fs = d[(d.tipo == "Four-Seam") & (d.alt == 0)].groupby("pitcher_anon_id").ivb.mean()
q1, q2 = fs.quantile([1 / 3, 2 / 3])
perfil = pd.cut(fs, [-np.inf, q1, q2, np.inf], labels=["ride bajo", "ride medio", "ride alto"]).rename("perfil")
B = tabla(bip[bip.tipo == "Four-Seam"].join(perfil, on="pitcher_anon_id").dropna(subset=["perfil"]), ["perfil"])
print(f"\nB. Rectas de 4 costuras por 'ride' a nivel del mar (cortes: {q1:.1f} y {q2:.1f} in de IVB)")
print(B.round(2).to_string())

# C. H3: valor de cada tipo de batazo por sede, y % de rodados vs carreras permitidas por pitcher
bt = bip[bip.hit_type.isin(["GroundBall", "LineDrive", "FlyBall", "Popup"])]
C1 = bt.groupby(["hit_type", "alt"]).valor.mean().unstack("alt").rename(columns=SEDE)
C1["diferencia"] = C1.extrema - C1.mar
print("\nC. Valor medio en carreras de cada tipo de batazo (+ favorece al bateador)")
print(C1.round(3).to_string())
gb_vs_fb = {s: float(C1.loc["FlyBall", s] - C1.loc["GroundBall", s]) for s in ["mar", "extrema"]}
print(f"   Un elevado cuesta {gb_vs_fb['mar']:.3f} carreras más que un rodado a nivel del mar y {gb_vs_fb['extrema']:.3f} en altitud extrema "
      f"({100*(gb_vs_fb['extrema']/gb_vs_fb['mar']-1):+.0f}%)")
pt = bt.groupby(["pitcher_anon_id", "alt"]).agg(n=("valor", "size"), gb=("hit_type", lambda s: (s == "GroundBall").mean()))
rvp = d.groupby(["pitcher_anon_id", "alt"]).rv.agg(["mean", "size"])
pt = pt.join(rvp); pt = pt[(pt.n >= 60) & (pt["size"] >= 300)]
rng = np.random.default_rng(0); C2 = {}
for a in [0, 2]:
    x = pt.xs(a, level="alt")
    c = float(-np.corrcoef(x.gb, x["mean"])[0, 1])
    bs = [-np.corrcoef(*x.sample(len(x), replace=True, random_state=int(rng.integers(1e9)))[["gb", "mean"]].values.T)[0, 1] for _ in range(2000)]
    C2[SEDE[a]] = {"n": int(len(x)), "corr": c, "ic95": [float(q) for q in np.percentile(bs, [2.5, 97.5])]}
    print(f"   {SEDE[a]:8s}: corr(% rodados, menos carreras permitidas) = {c:.3f}  IC95 [{C2[SEDE[a]]['ic95'][0]:.2f}, {C2[SEDE[a]]['ic95'][1]:.2f}]  (n={len(x)})")

res.update({"por_tipo": A.reset_index().to_dict("records"), "total": tot.reset_index().to_dict("records"),
            "recta_por_ride": B.reset_index().to_dict("records"), "ride_cortes_in": [float(q1), float(q2)],
            "h3": {"valor_por_batazo": C1.reset_index().to_dict("records"), "elevado_menos_rodado": gb_vs_fb,
                   "corr_rodados_vs_carreras": C2}})
json.dump(res, open("contacto.json", "w"), indent=1, default=float)
print("-> contacto.json")
