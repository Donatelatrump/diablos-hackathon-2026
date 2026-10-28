"""
01 - Target: valor de carrera por lanzamiento, neutral al contexto.

Idea en una frase: cada lanzamiento cambia el conteo (o termina el turno), y
cada conteo vale cierta cantidad de carreras esperadas. El valor del
lanzamiento es cuanto movio esa expectativa.

  RV = valor(estado despues) - valor(conteo antes)      (+ favorece al bateador)

Pasos
  1. Pesos lineales de los eventos terminales (out, K, BB, HBP, 1B, 2B, 3B, HR),
     escalados al ambiente de carreras de la LMB.
  2. Valor esperado de cada bola en juego segun velocidad de salida y angulo
     (y categoria de altitud): quita la suerte de donde cayo la pelota.
  3. Valor de cada conteo resolviendo la cadena de Markov de conteos con las
     probabilidades de transicion observadas en la LMB.
  4. RV de cada lanzamiento.

Salida: target.parquet  (PitchUID + rv + componentes)
"""
import sys
import numpy as np
import pandas as pd
import lightgbm as lgb

SRC = sys.argv[1] if len(sys.argv) > 1 else "../data/stuff_model_df.parquet"

cols = ["PitchUID", "year", "altitude_category", "PitchCall", "play_result", "KorBB",
        "Balls", "Strikes", "RunsScored", "ExitSpeed", "Angle", "game_anon_id"]
d = pd.read_parquet(SRC, columns=cols)
for c in ["PitchCall", "play_result"]:
    d[c] = d[c].astype(str)
d = d[(d.PitchCall != "Undefined") & d.Balls.between(0, 3) & d.Strikes.between(0, 2)].copy()
d["b"] = d.Balls.astype(int); d["s"] = d.Strikes.astype(int)

# ------------------------------------------------------------------
# 1. Pesos lineales (base MLB tipo RE24, escalados a la LMB)
# ------------------------------------------------------------------
LW_BASE = {"out": -0.27, "K": -0.28, "BB": 0.31, "HBP": 0.33, "1B": 0.47,
           "2B": 0.77, "3B": 1.04, "HR": 1.40, "E": 0.47, "FC": -0.20, "SAC": -0.10}

term = d.PitchCall.isin(["InPlay", "HitByPitch"]) | d.KorBB.isin(["Strikeout", "Walk"])
pa = int(term.sum())
runs = float(d.RunsScored.fillna(0).sum())
R_PA_LMB, R_PA_MLB = runs / pa, 0.117
ESC = R_PA_LMB / R_PA_MLB
LW = {k: v * ESC for k, v in LW_BASE.items()}
print(f"Turnos terminados: {pa:,} | carreras: {runs:,.0f} | R/PA LMB = {R_PA_LMB:.3f} "
      f"(MLB ~{R_PA_MLB}) -> escala {ESC:.3f}")

BIP_MAP = {"Out": "out", "Single": "1B", "Double": "2B", "Triple": "3B", "HomeRun": "HR",
           "Error": "E", "FieldersChoice": "FC", "Sacrifice": "SAC"}
bip = d.PitchCall == "InPlay"
d["bip_actual"] = np.where(bip, d.play_result.map(BIP_MAP).map(LW), np.nan)
d.loc[bip & d.bip_actual.isna(), "bip_actual"] = LW["out"]

# ------------------------------------------------------------------
# 2. Valor esperado de bola en juego: f(EV, LA, altitud)
# ------------------------------------------------------------------
ALT = {"No Altitude": 0, "Medium Altitude": 1, "Extreme Altitude": 2}
d["alt"] = d.altitude_category.map(ALT)
B = d[bip & d.ExitSpeed.notna() & d.Angle.notna()]
xb = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.05, num_leaves=63,
                       min_child_samples=200, verbose=-1)
xb.fit(B[["ExitSpeed", "Angle", "alt"]], B.bip_actual)
d["bip_x"] = np.nan
m = bip & d.ExitSpeed.notna() & d.Angle.notna()
d.loc[m, "bip_x"] = xb.predict(d.loc[m, ["ExitSpeed", "Angle", "alt"]])
d.loc[bip & d.bip_x.isna(), "bip_x"] = d.loc[bip, "bip_actual"].mean()
print(f"Bolas en juego: {bip.sum():,} | con EV/LA: {m.sum():,} | "
      f"corr(x, real) = {np.corrcoef(d.loc[m,'bip_x'], d.loc[m,'bip_actual'])[0,1]:.3f}")
for a, k in ALT.items():
    print(f"   valor medio BIP esperado en {a:17s}: {d.loc[bip & (d.alt==k),'bip_x'].mean():+.4f}")

# ------------------------------------------------------------------
# 3. Cadena de Markov de conteos
# ------------------------------------------------------------------
BALL = {"BallCalled", "BallinDirt", "BallIntentional", "AutomaticBall"}
STRK = {"StrikeCalled", "StrikeSwinging", "AutomaticStrike"}
FOUL = {"FoulBall", "FoulBallNotFieldable", "FoulBallFieldable"}
d["ev"] = np.select([d.PitchCall.isin(BALL), d.PitchCall.isin(STRK), d.PitchCall.isin(FOUL),
                     d.PitchCall == "HitByPitch", d.PitchCall == "InPlay"],
                    ["ball", "strike", "foul", "hbp", "bip"], "otro")
d = d[d.ev != "otro"].copy()

P = d.groupby(["b", "s"]).ev.value_counts(normalize=True).unstack(fill_value=0)
BIPV = d[d.ev == "bip"].groupby(["b", "s"]).bip_x.mean()

V = {(b, s): 0.0 for b in range(4) for s in range(3)}
def nxt(b, s, ev):
    if ev == "ball":   return LW["BB"] if b == 3 else V[(b + 1, s)]
    if ev == "strike": return LW["K"] if s == 2 else V[(b, s + 1)]
    if ev == "foul":   return V[(b, min(s + 1, 2))]
    if ev == "hbp":    return LW["HBP"]
for _ in range(200):
    for b in range(3, -1, -1):
        for s in range(2, -1, -1):
            p = P.loc[(b, s)]
            V[(b, s)] = sum(p[e] * nxt(b, s, e) for e in ["ball", "strike", "foul", "hbp"]) \
                        + p["bip"] * BIPV.loc[(b, s)]
print("\nValor de cada conteo (carreras esperadas vs. turno promedio):")
print(pd.DataFrame([[V[(b, s)] for s in range(3)] for b in range(4)],
                   index=[f"{b} bolas" for b in range(4)],
                   columns=[f"{s} strikes" for s in range(3)]).round(3).to_string())

# ------------------------------------------------------------------
# 4. RV por lanzamiento
# ------------------------------------------------------------------
after = np.empty(len(d))
for i, (b, s, ev, bx) in enumerate(zip(d.b.values, d.s.values, d.ev.values, d.bip_x.values)):
    after[i] = bx if ev == "bip" else nxt(b, s, ev)
d["rv"] = after - np.array([V[(b, s)] for b, s in zip(d.b.values, d.s.values)])

print("\nRV medio por resultado (carreras, + favorece al bateador):")
print(d.groupby("ev").rv.agg(["mean", "size"]).round(4).to_string())
print(f"\nRV total: media {d.rv.mean():+.5f}, desv {d.rv.std():.4f}")

d[["PitchUID", "rv", "ev", "bip_x"]].to_parquet("target.parquet", index=False)
pd.Series({**{f"V_{b}{s}": V[(b, s)] for b in range(4) for s in range(3)},
           **{f"LW_{k}": v for k, v in LW.items()}, "escala_lmb": ESC}).to_json("target_params.json")
print("-> target.parquet, target_params.json")
