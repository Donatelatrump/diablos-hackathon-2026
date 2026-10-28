"""
03 - Modelo Stuff+ y validacion.

Modelo: LightGBM que predice el valor de carrera esperado de un lanzamiento
solo a partir de su "stuff". Stuff+ = 100 + 10 * z, donde z compara la
prediccion contra todos los lanzamientos de la misma categoria de altitud
(mas alto = mejor para el pitcher).

Validacion
  A. Escalera de baselines (B0..B4) en pitchers que el modelo nunca vio.
  B. Predicciones fuera de muestra por pitcher (5 grupos): ningun pitcher es
     calificado por un modelo que lo haya visto.
  C. Temporal: entrenar 2024-2025, probar 2026.
  D. Estabilidad y poder predictivo año contra año (lo que de verdad importa:
     ¿el Stuff+ de 2024 anticipa el rendimiento de 2025 mejor que el propio
     rendimiento de 2024?).
"""
import json
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import GroupKFold

d = pd.read_parquet("features.parquet")
FULL = ["RelSpeed", "ivb", "hb_arm", "SpinRate", "spin_axis_m", "Extension", "RelHeight",
        "rel_side_arm", "fb_relspeed", "fb_ivb", "d_velo", "d_ivb", "d_hb", "d_axis", "alt"]
PARAMS = dict(objective="regression", learning_rate=0.03, num_leaves=31, min_child_samples=800,
              feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=10,
              verbose=-1, num_threads=2)
N_TREES = 500

def fit(X, y):
    return lgb.train(PARAMS, lgb.Dataset(X, y), num_boost_round=N_TREES)

def group_corr(df, pred_col, min_n=100, by=("pitcher_anon_id", "AutoPitchType")):
    g = df.groupby(list(by)).agg(p=(pred_col, "mean"), y=("rv", "mean"), n=("rv", "size"))
    g = g[g.n >= min_n]
    return np.corrcoef(g.p, g.y)[0, 1], len(g)

# ------------------------------------------------------------------ A. escalera
print("=" * 70); print("A. ESCALERA DE BASELINES (pitchers no vistos, 20%)"); print("=" * 70)
rng = np.random.default_rng(7)
pits = d.pitcher_anon_id.unique(); test_p = set(rng.choice(pits, len(pits) // 5, replace=False))
te = d.pitcher_anon_id.isin(test_p); tr, ts = d[~te], d[te].copy()
LADDER = {
    "B0 promedio general (sin stuff)": None,
    "B1 solo velocidad": ["RelSpeed"],
    "B2 velocidad + movimiento + spin": ["RelSpeed", "ivb", "hb_arm", "SpinRate", "spin_axis_m"],
    "B3 + liberacion + arsenal (diferenciales)": [f for f in FULL if f != "alt"],
    "B4 + altitud (modelo final)": FULL,
}
ladder = []
base_mse = ((ts.rv - tr.rv.mean()) ** 2).mean()
for name, fs in LADDER.items():
    if fs is None:
        ladder.append(dict(modelo=name, mejora_mse_pct=0.0, corr_pitcher_tipo=np.nan)); continue
    m = fit(tr[fs], tr.rv); ts["p"] = m.predict(ts[fs])
    mse = ((ts.rv - ts.p) ** 2).mean()
    c, n = group_corr(ts, "p")
    ladder.append(dict(modelo=name, mejora_mse_pct=100 * (1 - mse / base_mse), corr_pitcher_tipo=c))
    print(f"  {name:45s} mejora MSE {100*(1-mse/base_mse):5.2f}% | corr pitcher×tipo {c:.3f} (n={n})")
ladder = pd.DataFrame(ladder)

# ------------------------------------------------------------------ B. OOF
print("\n" + "=" * 70); print("B. PREDICCIONES FUERA DE MUESTRA (5 grupos por pitcher)"); print("=" * 70)
d["pred"] = np.nan
for k, (a, b) in enumerate(GroupKFold(5).split(d, groups=d.pitcher_anon_id)):
    m = fit(d.iloc[a][FULL], d.iloc[a].rv)
    d.iloc[b, d.columns.get_loc("pred")] = m.predict(d.iloc[b][FULL])
    print(f"  grupo {k+1}/5 listo")
c_oof, n_oof = group_corr(d, "pred")
print(f"  corr(predicción, RV real) a nivel pitcher×tipo: {c_oof:.3f} (n={n_oof})")

# Escala Stuff+ dentro de cada categoria de altitud
stats = d.groupby("alt").pred.agg(["mean", "std"])
d = d.join(stats, on="alt")
d["stuff_plus"] = 100 + 10 * (d["mean"] - d.pred) / d["std"]
d = d.drop(columns=["mean", "std"])

# ------------------------------------------------------------------ C. temporal
print("\n" + "=" * 70); print("C. TEMPORAL: entrenar 2024-2025, probar 2026"); print("=" * 70)
tr, ts = d[d.year < 2026], d[d.year == 2026].copy()
m = fit(tr[FULL], tr.rv); ts["p"] = m.predict(ts[FULL])
c_t, n_t = group_corr(ts, "p")
nuevos = ~ts.pitcher_anon_id.isin(tr.pitcher_anon_id.unique())
c_tn, n_tn = group_corr(ts[nuevos], "p", min_n=50)
print(f"  corr pitcher×tipo 2026: {c_t:.3f} (n={n_t}) | solo pitchers nuevos en 2026: {c_tn:.3f} (n={n_tn})")

# ------------------------------------------------------------------ D. año contra año
print("\n" + "=" * 70); print("D. ESTABILIDAD Y PODER PREDICTIVO (pitcher×tipo, >=100 lanz. en ambos años)"); print("=" * 70)
def yy(y1, y2):
    g = d[d.year.isin([y1, y2])].groupby(["pitcher_anon_id", "AutoPitchType", "year"]) \
        .agg(s=("stuff_plus", "mean"), rv=("rv", "mean"), n=("rv", "size")).reset_index()
    g = g[g.n >= 100]
    a = g[g.year == y1].set_index(["pitcher_anon_id", "AutoPitchType"])
    b = g[g.year == y2].set_index(["pitcher_anon_id", "AutoPitchType"])
    j = a.join(b, lsuffix="1", rsuffix="2", how="inner")
    return dict(par=f"{y1}->{y2}", n=len(j),
                estab_stuff=np.corrcoef(j.s1, j.s2)[0, 1],
                estab_rv=np.corrcoef(j.rv1, j.rv2)[0, 1],
                pred_stuff=-np.corrcoef(j.s1, j.rv2)[0, 1],
                pred_rv=np.corrcoef(j.rv1, j.rv2)[0, 1])
yrs = pd.DataFrame([yy(2024, 2025), yy(2025, 2026)])
for _, r in yrs.iterrows():
    print(f"  {r.par} (n={r.n}): estabilidad Stuff+ {r.estab_stuff:.2f} vs RV real {r.estab_rv:.2f} | "
          f"predice RV del año siguiente: Stuff+ {r.pred_stuff:.2f} vs RV real {r.pred_rv:.2f}")

# ------------------------------------------------------------------ modelo final
final = fit(d[FULL], d.rv)
final.save_model("stuff_model.txt")
imp = pd.Series(final.feature_importance("gain"), index=FULL).sort_values(ascending=False)
imp = (100 * imp / imp.sum()).round(1)
print("\nImportancia (ganancia %):"); print(imp.to_string())

d.to_parquet("scored.parquet", index=False)
json.dump({"features": FULL, "scale": {str(int(k)): {"mean": float(v["mean"]), "std": float(v["std"])}
                                       for k, v in stats.iterrows()},
           "ladder": ladder.to_dict("records"), "oof_corr": c_oof, "oof_n": n_oof,
           "temporal_corr": c_t, "temporal_new_corr": c_tn, "year_to_year": yrs.to_dict("records"),
           "importance": imp.to_dict()}, open("model_meta.json", "w"), indent=2, default=float)
print("\n-> stuff_model.txt, scored.parquet, model_meta.json")
