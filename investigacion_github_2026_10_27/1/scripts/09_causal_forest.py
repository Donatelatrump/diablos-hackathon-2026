"""Modelo secundario exploratorio: Causal Forest sobre carreras observadas.

Pregunta táctica. ¿A qué lanzador le cuesta más lanzar en el Harp Helú, medido en carreras que de verdad
permitió y no en Stuff+? El diseño es observacional y no identifica por sí solo un efecto causal.
Las tasas de whiff y rodados provienen de ambos entornos y pueden ser posteriores al tratamiento.
No se usa el bosque para recomendar una asignación individual de abridores.

Diseño
  Cada lanzador con al menos 120 lanzamientos en altitud extrema y 120 a nivel del mar aparece dos veces,
  una por entorno. El tratamiento T es lanzar en altura y el resultado Y son sus carreras permitidas por
  cada 100 lanzamientos (valor en carreras, signo del bateador). Así cada lanzador se compara consigo mismo.

  Double Machine Learning (Chernozhukov y coautores, 2018) con un bosque causal honesto (Wager y Athey, 2018;
  econml CausalForestDML). Validación cruzada agrupada por lanzador y pesos por número de lanzamientos.

Pruebas de que la heterogeneidad es real (no sólo ruido del bosque)
  1. Efecto fuera de muestra. Cada lanzador recibe su efecto de un bosque que no lo vio (5 pliegues).
  2. GATES (Chernozhukov, Demirer, Duflo y Fernández Val, 2018). Se agrupa a los lanzadores por su efecto
     predicho y se mide el castigo observado en cada grupo. Si el bosque acierta, el castigo observado sube
     de grupo en grupo.
  3. Pendiente del castigo observado contra el efecto predicho, con bootstrap por lanzador.

Salida: app/public/data/causal.json y artifacts/causal.json
"""
import json, pathlib, warnings

import numpy as np
import pandas as pd
from econml.dml import CausalForestDML
from scipy.stats import pearsonr, spearmanr
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import GroupKFold

warnings.filterwarnings("ignore")
RAIZ = pathlib.Path(__file__).resolve().parent.parent
ART = RAIZ / "artifacts"
OUT = RAIZ / "app" / "public" / "data"
B = 2000
rng = np.random.default_rng(2026)
ES = {"Four-Seam": "Recta", "Slider": "Slider", "Curveball": "Curva", "Changeup": "Cambio",
      "Sinker": "Sinker", "Cutter": "Cutter", "Splitter": "Splitter"}
# Un abridor de la LMB lanza unas 1,600 veces por temporada; la mitad en casa.
LANZ_CASA_TEMPORADA = 800

ars = pd.read_csv(ART / "stuff_por_arsenal.csv")
pit = pd.read_csv(ART / "pitchers_jurado.csv")
spp = pd.read_csv(ART / "stuff_por_pitcher.csv")

shares = ars.pivot_table(index="pitcher_anon_id", columns="pitch_type", values="n", fill_value=0)
shares = shares.div(shares.sum(axis=1), axis=0).add_prefix("uso_")
cf = (pit.dropna(subset=["carreras_hh", "carreras_mar"])
         .merge(spp[["pitcher_anon_id", "ext"]], on="pitcher_anon_id", how="left")
         .merge(shares, left_on="pitcher_anon_id", right_index=True, how="left").fillna(0)
         .reset_index(drop=True))
cf["zurdo"] = (cf.mano == "Left").astype(int)
cf["w"] = 2 / (1 / cf.n_hh + 1 / cf.n_mar)        # precisión de una diferencia
XCOLS = ["stuff_mar", "velo", "whiff", "gb", "ext", "zurdo"] + [c for c in shares.columns if c != "uso_Splitter"]
NOMBRES = {"stuff_mar": "Stuff+ a nivel del mar", "velo": "Velocidad", "whiff": "Swings fallidos", "gb": "Rodados",
           "ext": "Extensión", "zurdo": "Zurdo", **{f"uso_{k}": f"Uso de {ES[k].lower()}" for k in ES}}


def largo(d):
    return pd.concat([d.assign(T=1, Y=d.carreras_hh, peso=d.n_hh),
                      d.assign(T=0, Y=d.carreras_mar, peso=d.n_mar)], ignore_index=True)


def bosque(seed=0):
    return CausalForestDML(
        model_y=RandomForestRegressor(n_estimators=300, min_samples_leaf=20, random_state=seed),
        model_t=RandomForestClassifier(n_estimators=300, min_samples_leaf=20, random_state=seed),
        discrete_treatment=True, n_estimators=2000, min_samples_leaf=15, max_depth=6,
        cv=5, random_state=seed, inference=True)


def ajustar(est, d):
    L = largo(d)
    est.fit(L.Y.to_numpy(), L["T"].to_numpy(), X=L[XCOLS].to_numpy(),
            sample_weight=L.peso.to_numpy(), groups=L.pitcher_anon_id.to_numpy())
    return est


def mp(v, w):
    return float(np.sum(v * w) / np.sum(w))


def ic(x):
    lo, hi = np.percentile(x, [2.5, 97.5])
    return [round(float(lo), 3), round(float(hi), 3)]


# ------------------------------------------------------------------ 1. el bosque con todos los lanzadores
print("bosque completo…", flush=True)
est = ajustar(bosque(), cf)
X1 = cf[XCOLS].to_numpy()
cf["tau"] = est.effect(X1)
lo, hi = est.effect_interval(X1, alpha=0.1)
cf["tau_lo"], cf["tau_hi"] = lo, hi
ate = est.ate_inference(X=X1)
imp = sorted(({"variable": NOMBRES[c], "clave": c, "peso": round(float(v), 4)}
              for c, v in zip(XCOLS, est.feature_importances_)), key=lambda r: -r["peso"])

# ------------------------------------------------------------------ 2. efecto fuera de muestra
print("efecto fuera de muestra…", flush=True)
cf["tau_oof"] = np.nan
for k, (tr, te) in enumerate(GroupKFold(n_splits=5).split(cf, groups=cf.pitcher_anon_id)):
    e = ajustar(bosque(seed=k + 1), cf.iloc[tr])
    cf.loc[cf.index[te], "tau_oof"] = e.effect(cf.iloc[te][XCOLS].to_numpy())

# ------------------------------------------------------------------ 3. GATES y pendiente
print("GATES…", flush=True)
cf["grupo"] = pd.qcut(cf.tau_oof.rank(method="first"), 4, labels=["Q1", "Q2", "Q3", "Q4"])
obs, pred = cf.carreras_delta.to_numpy(), cf.tau_oof.to_numpy()
w, g = cf.w.to_numpy(), cf.grupo.astype(str).to_numpy()
gates = []
for q, et in zip(["Q1", "Q2", "Q3", "Q4"], ["Aguantan más", "Segundo grupo", "Tercer grupo", "Sufren más"]):
    m = g == q
    idx = np.where(m)[0]
    boot = [mp(obs[i], w[i]) for i in (rng.choice(idx, len(idx)) for _ in range(B))]
    gates.append({"grupo": q, "etiqueta": et, "pitchers": int(m.sum()), "predicho": round(mp(pred[m], w[m]), 3),
                  "observado": round(mp(obs[m], w[m]), 3), "ic": ic(boot)})


def pendiente(x, y, ww):
    X = np.column_stack([np.ones_like(x), x - np.average(x, weights=ww)])
    W = np.diag(ww)
    return float(np.linalg.solve(X.T @ W @ X, X.T @ W @ y)[1])


bs = [pendiente(pred[i], obs[i], w[i]) for i in (rng.integers(0, len(cf), len(cf)) for _ in range(B))]
dif = [mp(obs[i][g[i] == "Q4"], w[i][g[i] == "Q4"]) - mp(obs[i][g[i] == "Q1"], w[i][g[i] == "Q1"])
       for i in (rng.integers(0, len(cf), len(cf)) for _ in range(B))]
q1, q4 = gates[0]["observado"], gates[-1]["observado"]

# ------------------------------------------------------------------ 4. cómo cambia el efecto con cada rasgo
print("dependencias…", flush=True)
dependencias = []
for c in [r["clave"] for r in imp[:6]]:
    if cf[c].nunique() < 5:
        continue
    b = pd.qcut(cf[c].rank(method="first"), 5, labels=False)
    filas = []
    for k in range(5):
        m = (b == k).to_numpy()
        filas.append({"x": round(float(cf.loc[m, c].mean()), 3), "tau": round(float(cf.loc[m, "tau_oof"].mean()), 3),
                      "observado": round(mp(obs[m], w[m]), 3)})
    dependencias.append({"variable": NOMBRES[c], "clave": c, "quintiles": filas})

# ------------------------------------------------------------------ 5. acuerdo con Stuff+
r_s, p_s = pearsonr(cf.tau_oof, -cf.delta_hh)
rho_s, _ = spearmanr(cf.tau_oof, -cf.delta_hh)

# ------------------------------------------------------------------ 6. por lanzador
cols = ["nombre", "arsenal", "mano", "tau", "tau_lo", "tau_hi", "tau_oof", "stuff_mar", "stuff_hh", "delta_hh",
        "carreras_delta", "n_hh", "n_mar", "gb", "whiff", "velo"]
por = cf[cols].copy()
por["rank"] = por.tau.rank(method="first").astype(int)
por = por.sort_values("tau")
pitchers = json.loads(por.round(3).to_json(orient="records"))

salida = {
    "interpretacion": {
        "tipo": "exploratorio observacional",
        "identifica_efecto_causal": False,
        "limites": "Covariables agregadas sobre ambos entornos, sin controles completos de rivales, temporada o estadio. Las diferencias individuales requieren validación externa.",
    },
    "pitchers_n": int(len(cf)),
    "ate": round(float(ate.mean_point), 3),
    "ate_ic90": [round(float(v), 3) for v in ate.conf_int_mean(alpha=0.1)],
    "tau_rango": [round(float(cf.tau.min()), 3), round(float(cf.tau.max()), 3)],
    "importancia": imp,
    "gates": gates,
    "pendiente": {"valor": round(pendiente(pred, obs, w), 3), "ic": ic(bs), "p_una_cola": round(float(np.mean(np.array(bs) <= 0)), 4)},
    "q4_menos_q1": {"valor": round(q4 - q1, 3), "ic": ic(dif)},
    "politica": {
        "carreras_100_ahorradas": round(q4 - q1, 3),
        "lanzamientos_casa_temporada": LANZ_CASA_TEMPORADA,
        "carreras_temporada": round((q4 - q1) * LANZ_CASA_TEMPORADA / 100, 1),
    },
    "dependencias": dependencias,
    "acuerdo_stuff": {"pearson": round(float(r_s), 3), "p": round(float(p_s), 5), "spearman": round(float(rho_s), 3)},
    "pitchers": pitchers,
    "unidad": "carreras extra por cada 100 lanzamientos al pasar de nivel del mar a altitud extrema (positivo = sufre)",
}
(ART / "causal.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1, allow_nan=False))
(OUT / "causal.json").write_text(json.dumps(salida, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
print(json.dumps({k: v for k, v in salida.items() if k not in ("pitchers", "dependencias")}, ensure_ascii=False, indent=1))
print(json.dumps(dependencias, ensure_ascii=False)[:2500])
