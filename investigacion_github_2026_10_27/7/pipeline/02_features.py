"""
02 - Features de "stuff": solo lo que sale de la mano y lo que hace la pelota.

Excluye a proposito: ubicacion (PlateLoc*), conteo, bateador, etiqueta de
tipo de lanzamiento (contaminada por la altitud; ver verificacion_sin_etiquetas.py).

Espejo para zurdos: todo lo horizontal se expresa como "hacia el lado del
brazo" para que diestros y zurdos compartan el mismo espacio.

Diferenciales vs. la recta principal del pitcher, calculados dentro de la
misma temporada y la misma categoria de altitud (el bateador ve ambos
lanzamientos en el mismo aire).
"""
import sys
import numpy as np
import pandas as pd

SRC = sys.argv[1] if len(sys.argv) > 1 else "../data/stuff_model_df.parquet"
cols = ["PitchUID", "year", "game_anon_id", "pitcher_anon_id", "PitcherThrows", "altitude_category",
        "AutoPitchType", "RelSpeed", "SpinRate", "SpinAxis", "RelHeight", "RelSide", "Extension",
        "InducedVertBreak", "HorzBreak"]
d = pd.read_parquet(SRC, columns=cols)
d["AutoPitchType"] = d.AutoPitchType.astype(str)
d = d[d.PitcherThrows.isin(["Right", "Left"]) & d.altitude_category.notna()]
d = d.dropna(subset=["RelSpeed", "SpinRate", "SpinAxis", "RelHeight", "RelSide", "Extension",
                     "InducedVertBreak", "HorzBreak"]).copy()

ALT = {"No Altitude": 0, "Medium Altitude": 1, "Extreme Altitude": 2}
d["alt"] = d.altitude_category.map(ALT).astype(int)
sgn = np.where(d.PitcherThrows == "Right", 1.0, -1.0)
d["hb_arm"] = d.HorzBreak * sgn
d["rel_side_arm"] = -d.RelSide * sgn
d["spin_axis_m"] = np.where(sgn > 0, d.SpinAxis, 360 - d.SpinAxis)
d["ivb"] = d.InducedVertBreak
d["is_rhp"] = (sgn > 0).astype(int)

print("Chequeo de espejo (recta 4S): hb_arm y rel_side_arm deben ser positivos en ambos lados")
print(d[d.AutoPitchType == "Four-Seam"].groupby("PitcherThrows")[["hb_arm", "rel_side_arm", "spin_axis_m"]]
      .mean().round(2).to_string())

# Recta principal: la mas usada entre Four-Seam/Sinker; si no hay, Cutter; si no, la mas rapida
key = ["pitcher_anon_id", "year", "alt"]
fbc = d[d.AutoPitchType.isin(["Four-Seam", "Sinker"])].groupby(key + ["AutoPitchType"]).size()
prim = fbc.reset_index(name="n").sort_values("n").groupby(key).tail(1).set_index(key).AutoPitchType
cut = d[d.AutoPitchType == "Cutter"].groupby(key).size()
cut = pd.Series("Cutter", index=cut.index.difference(prim.index))
prim = pd.concat([prim, cut]).rename("fb_type")
d = d.join(prim, on=key)
fast = d[d.fb_type.isna()].groupby(key + ["AutoPitchType"]).RelSpeed.mean().reset_index() \
       .sort_values("RelSpeed").groupby(key).tail(1).set_index(key).AutoPitchType.rename("fb2")
d = d.join(fast, on=key); d["fb_type"] = d.fb_type.fillna(d.fb2)

fbstats = d[d.AutoPitchType == d.fb_type].groupby(key)[["RelSpeed", "ivb", "hb_arm", "spin_axis_m"]] \
          .mean().rename(columns=lambda c: "fb_" + c.lower())
d = d.join(fbstats, on=key)
d["d_velo"] = d.RelSpeed - d.fb_relspeed
d["d_ivb"] = d.ivb - d.fb_ivb
d["d_hb"] = d.hb_arm - d.fb_hb_arm
d["d_axis"] = ((d.spin_axis_m - d.fb_spin_axis_m + 180) % 360) - 180
d["is_fb"] = (d.AutoPitchType == d.fb_type).astype(int)

FEATS = ["RelSpeed", "ivb", "hb_arm", "SpinRate", "spin_axis_m", "Extension", "RelHeight",
         "rel_side_arm", "fb_relspeed", "fb_ivb", "d_velo", "d_ivb", "d_hb", "d_axis", "alt"]
t = pd.read_parquet("target.parquet")
d = d.merge(t, on="PitchUID", how="inner").dropna(subset=FEATS)
keep = ["PitchUID", "year", "game_anon_id", "pitcher_anon_id", "PitcherThrows", "altitude_category",
        "AutoPitchType", "is_fb", "rv", "ev"] + FEATS
d[keep].to_parquet("features.parquet", index=False)
print(f"\n-> features.parquet: {len(d):,} lanzamientos, {d.pitcher_anon_id.nunique()} pitchers, "
      f"{len(FEATS)} features")
print("Sin recta identificada:", int(d.fb_relspeed.isna().sum()))
