"""Etapa 10, se corre en la máquina que tiene los datos de la LMB. Tres análisis que pide el reto.

  A. Causal Forest táctico. La pregunta del reto, "¿qué hubiera pasado si el pitcher lanzara slider en vez
     de cambio en este conteo, contra este bateador?", con el efecto separado por entorno (nivel del mar
     contra altitud extrema). Así el club sabe qué lanzamiento conviene en cada conteo en su casa.
  B. SHAP. Cuánto pesa cada variable en Stuff+, Location+ y Pitching+, con contribuciones de LightGBM.
  C. Stuff+ por tipo en los tres entornos de la LMB (nivel del mar, altitud media, altitud extrema).

Necesita artifacts/scored.pkl (sale de 03_models.py) y econml.

  uv pip install econml
  python scripts/10_local_extras.py

Escribe artifacts/extras.json y app/public/data/extras.json. Cada parte va en su propio bloque: si una
falla, las otras igual se guardan.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
ART = RAIZ / "artifacts"
OUT = RAIZ / "app" / "public" / "data"
ES = {"Four-Seam": "Recta", "Slider": "Slider", "Curveball": "Curva", "Changeup": "Cambio",
      "Sinker": "Sinker", "Cutter": "Cutter", "Splitter": "Splitter"}
rng = np.random.default_rng(2026)


def guardar(salida: dict) -> None:
    texto = json.dumps(salida, ensure_ascii=False, allow_nan=False, default=float)
    (ART / "extras.json").write_text(json.dumps(json.loads(texto), ensure_ascii=False, indent=1))
    (OUT / "extras.json").write_text(texto)


def limpio(x):
    """Redondea y cambia NaN por None para que el JSON sea válido."""
    if isinstance(x, dict):
        return {k: limpio(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [limpio(v) for v in x]
    if isinstance(x, (float, np.floating)):
        return None if not np.isfinite(x) else round(float(x), 4)
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


# ================================================================================ A. Causal Forest táctico
CONTRASTES = [("Slider", "Changeup"), ("Slider", "Four-Seam"), ("Changeup", "Four-Seam"), ("Curveball", "Slider")]
MAX_FILAS = 150_000


def cf_tactico(df: pd.DataFrame) -> dict:
    from econml.dml import CausalForestDML

    base = df[df.altitude_category.isin(["No Altitude", "Extreme Altitude"])].copy()
    base["altura"] = (base.altitude_category == "Extreme Altitude").astype(float)
    base["pt"] = base.pitch_type.astype(str)
    # Rasgos del lanzador que confunden la elección (un lanzador con buen slider lo usa más): controles W.
    uso = base.groupby(["pitcher_anon_id", "pt"]).size().unstack(fill_value=0)
    uso = uso.div(uso.sum(axis=1), axis=0)
    calidad = base.groupby("pitcher_anon_id")["pitching_plus"].mean().rename("calidad_lanzador")
    resultados = {}
    for a, b in CONTRASTES:
        t0 = time.time()
        d = base[base.pt.isin([a, b])].copy()
        d = d.join(calidad, on="pitcher_anon_id")
        d[f"uso_{a}"] = d.pitcher_anon_id.map(uso.get(a, pd.Series(dtype=float))).fillna(0)
        d[f"uso_{b}"] = d.pitcher_anon_id.map(uso.get(b, pd.Series(dtype=float))).fillna(0)
        # Sin lanzador no hay grupo para el bosque (0.2 % de los lanzamientos), y econml no acepta NaN en groups.
        d = d.dropna(subset=["rv", "balls", "strikes", "is_rhb", "platoon_same", "pitcher_anon_id"])
        if len(d) > MAX_FILAS:
            d = d.sample(MAX_FILAS, random_state=7)
        T = (d.pt == a).astype(int).to_numpy()
        Y = d.rv.to_numpy() * 100                     # carreras por cada 100 lanzamientos, signo del bateador
        XC = ["balls", "strikes", "platoon_same", "altura", "prev_is_fastball"]
        WC = ["calidad_lanzador", f"uso_{a}", f"uso_{b}", "times_through", "is_rhp", "is_rhb", "fb_velo", "arsenal_size"]
        X = d[XC].fillna(0).to_numpy()
        W = d[WC].fillna(d[WC].median()).to_numpy()
        est = CausalForestDML(
            model_y=lgb.LGBMRegressor(n_estimators=300, learning_rate=0.05, num_leaves=31, min_child_samples=200, verbose=-1),
            model_t=lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31, min_child_samples=200, verbose=-1),
            discrete_treatment=True, n_estimators=600, min_samples_leaf=300, max_depth=8, cv=3, random_state=0)
        est.fit(Y, T, X=X, W=W, groups=d.pitcher_anon_id.to_numpy())
        celdas = []
        for alt in (0.0, 1.0):
            for bl in range(4):
                for st in range(3):
                    for plat in (0.0, 1.0):
                        x = np.array([[bl, st, plat, alt, 0.5]])
                        m = (d.altura == alt) & (d.balls == bl) & (d.strikes == st) & (d.platoon_same == plat)
                        lo, hi = est.effect_interval(x, alpha=0.1)
                        celdas.append({"altura": int(alt), "conteo": f"{bl}-{st}", "mismo_lado": int(plat),
                                       "efecto": float(est.effect(x)[0]), "ic90": [float(lo[0]), float(hi[0])],
                                       "n": int(m.sum())})
        por_entorno = {}
        for alt, nombre in ((0.0, "mar"), (1.0, "altura")):
            m = d.altura.to_numpy() == alt
            inf = est.ate_inference(X=X[m])
            por_entorno[nombre] = {"efecto": float(inf.mean_point), "ic90": [float(v) for v in inf.conf_int_mean(alpha=0.1)],
                                   "n": int(m.sum())}
        # La pregunta del club: ¿cambia la mejor elección en casa?
        x0, x1 = X.copy(), X.copy()
        x0[:, 3], x1[:, 3] = 0, 1
        dif = est.effect(x1) - est.effect(x0)
        clave = f"{ES[a]} en vez de {ES[b]}"
        resultados[clave] = limpio({
            "a": ES[a], "b": ES[b], "filas": int(len(d)), "segundos": round(time.time() - t0, 1),
            "por_entorno": por_entorno, "cambio_por_altura": float(np.mean(dif)),
            "importancia": dict(zip(XC, map(float, est.feature_importances_))), "celdas": celdas,
        })
        print(f"  {clave}: mar {por_entorno['mar']['efecto']:+.2f}  altura {por_entorno['altura']['efecto']:+.2f}"
              f"  ({len(d):,} lanzamientos, {time.time() - t0:.0f}s)", flush=True)
    return {"contrastes": resultados,
            "unidad": "carreras por cada 100 lanzamientos al elegir A en vez de B; negativo = A es mejor para el pitcher",
            "x": "conteo, mismo lado lanzador y bateador, entorno, lanzamiento anterior recta",
            "w": "calidad del lanzador, uso de cada tipo, vuelta al orden, manos, velocidad de su recta, tamaño de arsenal"}


# ================================================================================ B. SHAP
GRUPOS = {
    "Física del lanzamiento": ["RelSpeed", "EffectiveVelo", "SpinRate", "SpinAxis", "InducedVertBreak", "HorzBreak",
                               "VertBreak", "RelHeight", "RelSide", "Extension", "VertRelAngle", "HorzRelAngle",
                               "VertApprAngle", "HorzApprAngle", "SpeedDrop", "ZoneTime", "ZoneSpeed",
                               "spin_efficiency", "movement_total", "is_rhp"],
    "Ubicación y conteo": ["PlateLocHeight", "PlateLocSide", "plate_dist", "balls", "strikes", "is_rhb", "platoon_same"],
    "Arsenal y secuencia": ["velo_diff_vs_fb", "ivb_diff_vs_fb", "hb_diff_vs_fb", "movement_diff_vs_fb",
                            "tunnel_similarity", "pitch_usage_pct", "arsenal_size", "prev_is_fastball",
                            "prev_velo_diff", "times_through"],
}


def shap(df: pd.DataFrame) -> dict:
    muestra = df.sample(min(40_000, len(df)), random_state=3)
    out = {}
    for capa in ("stuff", "location", "pitching"):
        bst = lgb.Booster(model_file=str(ART / f"model_{capa}.txt"))
        feats = bst.feature_name()
        contrib = bst.predict(muestra[feats], pred_contrib=True)[:, :-1]
        media = np.abs(contrib).mean(axis=0)
        total = media.sum()
        por_var = sorted(({"variable": f, "peso": float(v / total)} for f, v in zip(feats, media)), key=lambda r: -r["peso"])
        por_grupo = {g: float(sum(r["peso"] for r in por_var if r["variable"] in fs)) for g, fs in GRUPOS.items()}
        out[capa] = limpio({"top": por_var[:12], "grupos": por_grupo})
        print(f"  SHAP {capa}: " + ", ".join(f"{g} {v:.0%}" for g, v in por_grupo.items() if v > 0), flush=True)
    return out


# ================================================================================ C. tres entornos
def tres_entornos(df: pd.DataFrame) -> dict:
    from src.stuffplus import physics
    phys = json.loads((ART / "physics.json").read_text())
    scale = json.loads((ART / "scale.json").read_text())["stuff"]
    bst = lgb.Booster(model_file=str(ART / "model_stuff.txt"))
    feats = bst.feature_name()
    aero = physics.decompose(df)
    kw = dict(rho_observed=df.rho_game.to_numpy(), aero=aero,
              magnus_gamma=phys["magnus_gamma_vertical"], magnus_gamma_h=phys["magnus_gamma_horizontal"])
    ref = physics.observed_shape(df)

    def puntuar(rho):
        X = physics.transfer_features(df[feats], ref, physics.transfer_shape(df, rho, **kw))
        return 100.0 + 10.0 * (-bst.predict(X) - scale["center"]) / scale["scale"]

    cub = phys["rho_por_cubeta"]
    for nombre, rho in (("mar", 1.0), ("media", cub["Medium Altitude"]), ("extrema", cub["Extreme Altitude"])):
        df[f"plus_{nombre}"] = puntuar(rho)
    filas = []
    for t, g in df.groupby(df.pitch_type.astype(str)):
        if t not in ES:
            continue
        filas.append({"tipo": ES[t], "n": int(len(g)), "mar": float(g.plus_mar.mean()),
                      "media": float(g.plus_media.mean()), "extrema": float(g.plus_extrema.mean())})
    print("  tres entornos listo", flush=True)
    return limpio({"indice_aire": {"mar": 1.0, "media": cub["Medium Altitude"], "extrema": cub["Extreme Altitude"]},
                   "por_tipo": sorted(filas, key=lambda r: r["extrema"] - r["mar"], reverse=True),
                   "liga": {k: float(df[f"plus_{k}"].mean()) for k in ("mar", "media", "extrema")}})


def main() -> None:
    """Sin argumentos corre las tres partes. Con nombres corre sólo esas y conserva las demás:
    python scripts/10_local_extras.py cf_tactico"""
    t0 = time.time()
    partes = (("tres_entornos", tres_entornos), ("shap", shap), ("cf_tactico", cf_tactico))
    pedidas = set(sys.argv[1:]) or {n for n, _ in partes}
    previo = ART / "extras.json"
    salida: dict = json.loads(previo.read_text()) if previo.exists() and set(sys.argv[1:]) else {}
    df = pd.read_pickle(ART / "scored.pkl")
    print(f"scored.pkl: {len(df):,} lanzamientos", flush=True)
    for nombre, f in partes:
        if nombre not in pedidas:
            continue
        print(f"{nombre}…", flush=True)
        try:
            salida[nombre] = f(df)
        except Exception as e:                       # una parte que falla no tumba a las demás
            salida[nombre] = {"error": f"{type(e).__name__}: {e}"}
            traceback.print_exc()
        guardar(salida)
    print(f"listo en {time.time() - t0:.0f}s → app/public/data/extras.json")


if __name__ == "__main__":
    main()
