"""Etapa 11, se corre en la máquina que tiene los datos de la LMB. Las pruebas de robustez que tapan los huecos
que un jurado técnico le encontraría al modelo.

  A. parque          El holdout de parque como debe ser. Entrenamos Stuff+ sólo con juegos a nivel del mar, con
                     lanzadores separados por pliegue, y predecimos los juegos de altitud extrema de dos maneras,
                     con la forma que la pelota tuvo en altura y con esa misma pelota volada a nivel del mar. La
                     diferencia entre las dos es la parte del exceso de carreras en altura que explica la física
                     del lanzamiento, y la comparamos con el exceso observado. También por tipo de lanzamiento.
  B. discriminacion  Qué tanto separa Stuff+ en unidades de un coach. Carreras por cada 100 lanzamientos del 10 %
                     mejor contra el 10 % peor, fuera de muestra, con intervalo por bootstrap de lanzadores.
  C. confiabilidad   ¿La estabilidad de 0.988 entre mitades es calidad o es la mezcla de lanzamientos? Repetimos la
                     prueba restando el promedio de cada tipo, y sólo con rectas.
  D. futuro          ¿Predice el año siguiente? Pares 2024 a 2025 y 2025 a 2026, carreras y swings fallidos, contra
                     las carreras del año anterior, con intervalos y el aporte incremental de Stuff+.
  E. combinacion     La versión que sugiere el reto. Ocho modelos de componente (y la probabilidad de out en el
                     turno) con las variables de Stuff+, combinados con pesos aprendidos por regresión, contra el
                     modelo directo en carreras.
  F. especificaciones ¿Las conclusiones dependen de SpeedDrop? Pérdida por tipo al pasar a altura con tres versiones
                     de Stuff+, la de producción, una sin las tres variables de frenado y una entrenada con todos los
                     juegos, como el modelo anterior.

Necesita artifacts/scored.pkl, artifacts/oof_rv.npy, artifacts/physics.json y artifacts/scale.json (salen de 01 a 03).

  python scripts/11_robustez.py                 # todo, 40 a 90 minutos
  python scripts/11_robustez.py parque futuro   # sólo esas partes, conserva las demás

Escribe artifacts/robustez.json y app/public/data/robustez.json. Cada parte en su propio bloque: si una falla, las
otras se guardan igual.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

warnings.filterwarnings("ignore")
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from src.stuffplus import features as F  # noqa: E402
from src.stuffplus import models, physics  # noqa: E402

# Se pueden redirigir para probar con datos sintéticos sin tocar los artefactos reales.
ART = Path(os.environ.get("DIABLOS_ART", RAIZ / "artifacts"))
OUT = Path(os.environ.get("DIABLOS_OUT", RAIZ / "app" / "public" / "data"))
ES = {"Four-Seam": "Recta", "Slider": "Slider", "Curveball": "Curva", "Changeup": "Cambio",
      "Sinker": "Sinker", "Cutter": "Cutter", "Splitter": "Splitter"}
B = int(os.environ.get("ROBUSTEZ_B", 1000))          # remuestreos de bootstrap
PLIEGUES = 4
rng = np.random.default_rng(2026)
MAR, EXT = "No Altitude", "Extreme Altitude"


# ------------------------------------------------------------------------------------------------ utilidades
def guardar(salida: dict) -> None:
    texto = json.dumps(salida, ensure_ascii=False, allow_nan=False, default=float)
    (ART / "robustez.json").write_text(json.dumps(json.loads(texto), ensure_ascii=False, indent=1))
    (OUT / "robustez.json").write_text(texto)


def limpio(x):
    """Redondea y cambia NaN por None para que el JSON sea válido."""
    if isinstance(x, dict):
        return {str(k): limpio(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [limpio(v) for v in x]
    if isinstance(x, (float, np.floating)):
        return None if not np.isfinite(x) else round(float(x), 5)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def ic(muestras, q=(2.5, 97.5)) -> list[float]:
    m = np.asarray(muestras, dtype=float)
    m = m[np.isfinite(m)]
    return [float(np.percentile(m, q[0])), float(np.percentile(m, q[1]))] if len(m) else [np.nan, np.nan]


def boot_lanzadores(ids: np.ndarray, estadistico, b: int = B) -> list[float]:
    """Bootstrap por lanzador. `estadistico(idx)` recibe índices de filas de un remuestreo de lanzadores completos."""
    if len(ids) == 0:
        raise ValueError("ningún lanzador cumple el mínimo de lanzamientos para esta prueba")
    unicos, inv, cuantos = np.unique(ids, return_inverse=True, return_counts=True)
    filas = np.split(np.argsort(inv, kind="stable"), np.cumsum(cuantos)[:-1])
    out = []
    for _ in range(b):
        pick = rng.integers(0, len(unicos), len(unicos))
        out.append(estadistico(np.concatenate([filas[k] for k in pick])))
    return out


def corr(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    m = np.isfinite(a) & np.isfinite(b)
    return float(np.corrcoef(a[m], b[m])[0, 1]) if m.sum() > 3 else np.nan


def grupos(df: pd.DataFrame) -> np.ndarray:
    return models.group_ids(df.pitcher_anon_id)


def entrena_stuff(df: pd.DataFrame, feats: list[str], filas: np.ndarray) -> lgb.Booster:
    p, n = models.capa("stuff")
    prm = {**models.PARAMS, **p}
    d = df.iloc[np.flatnonzero(filas)]
    d = d[d.rv.notna()]
    return lgb.train(prm, lgb.Dataset(d[feats], d.rv.to_numpy()), num_boost_round=n)


def transferir(df: pd.DataFrame, feats: list[str], rho_destino: float) -> pd.DataFrame:
    """Las variables de Stuff+ de cada lanzamiento, voladas en el aire `rho_destino` (1.0 = nivel del mar)."""
    phys = json.loads((ART / "physics.json").read_text())
    aero = physics.decompose(df)
    kw = dict(rho_observed=df.rho_game.to_numpy(), aero=aero,
              magnus_gamma=phys["magnus_gamma_vertical"], magnus_gamma_h=phys["magnus_gamma_horizontal"])
    ref = physics.observed_shape(df)
    destino = physics.transfer_shape(df, rho_destino, **kw)
    return physics.transfer_features(df[feats], ref, destino)


# ================================================================================ A. holdout de parque
def parque(df: pd.DataFrame) -> dict:
    """Entrena sólo con nivel del mar y predice altitud extrema, con lanzadores separados por pliegue.

    Para cada lanzamiento de altura tenemos tres números. Las carreras que pasaron (obs). Lo que el modelo predice
    con la forma que la pelota tuvo de verdad en altura (alt). Y lo que predice si a esa misma pelota la volamos a
    nivel del mar (mar). obs − mar es un contraste contra el modelo, alt − mar
    es su cambio por forma y obs − alt su residual. No identifica una fracción causal
    porque también contiene error de calibración y diferencias no controladas.
    """
    feats = F.feature_sets()["stuff"]
    ext = (df.altitude_category == EXT).to_numpy()
    mar = (df.altitude_category == MAR).to_numpy()
    d_ext = df[ext]
    x_alt = d_ext[feats]
    x_mar = transferir(d_ext, feats, 1.0)
    g = grupos(df)
    p_alt = np.full(ext.sum(), np.nan)
    p_mar = np.full(ext.sum(), np.nan)
    pos_ext = np.flatnonzero(ext)
    for k, (tr, te) in enumerate(GroupKFold(PLIEGUES).split(df, groups=g)):
        filas = np.zeros(len(df), dtype=bool)
        filas[tr] = True
        bst = entrena_stuff(df, feats, filas & mar)
        en_prueba = np.isin(pos_ext, te)
        p_alt[en_prueba] = bst.predict(x_alt[en_prueba])
        p_mar[en_prueba] = bst.predict(x_mar[en_prueba])
        print(f"  pliegue {k + 1}/{PLIEGUES}", flush=True)

    y = d_ext.rv.to_numpy()
    ok = np.isfinite(y) & np.isfinite(p_alt) & np.isfinite(p_mar)
    y, p_alt, p_mar = y[ok], p_alt[ok], p_mar[ok]
    ids = grupos(d_ext)[ok]
    tipos = d_ext.pitch_type.astype(str).to_numpy()[ok]

    def partes(idx):
        o, a, m = y[idx].mean(), p_alt[idx].mean(), p_mar[idx].mean()
        total = o - m
        return {"obs": o, "alt": a, "mar": m, "total": total, "fisica": a - m, "resto": o - a,
                "fraccion": (a - m) / total if abs(total) > 1e-9 else np.nan}

    base = partes(np.arange(len(y)))
    bs = boot_lanzadores(ids, partes)
    sst = np.sum((y - y.mean()) ** 2)
    ajustado = p_alt - p_alt.mean() + y.mean()            # mismo orden, nivel corregido
    res = {
        "n": int(len(y)), "lanzadores": int(len(np.unique(ids))),
        "method": "Model-based decomposition with pitcher holdout and sea-only training.",
        "limits": "Not an identified causal share. Includes model calibration error and uncontrolled context; upstream references are global.",
        "por_100": {k: v * 100 if k != "fraccion" else v for k, v in base.items()},
        "ic95_por_100": {k: [x * 100 if k != "fraccion" else x for x in ic([b[k] for b in bs])] for k in base},
        "r2_forma_altura": 1 - np.sum((y - p_alt) ** 2) / sst,
        "r2_forma_mar": 1 - np.sum((y - p_mar) ** 2) / sst,
        "r2_nivel_corregido": 1 - np.sum((y - ajustado) ** 2) / sst,
        "corr": corr(p_alt, y),
        "corr_ic95": ic(boot_lanzadores(ids, lambda i: corr(p_alt[i], y[i]))),
    }

    # Por tipo, contra el exceso observado dentro del mismo lanzador (sus lanzamientos de ese tipo en altura contra
    # los mismos a nivel del mar). Si la física tiene razón, los tipos con más pérdida predicha sufren más.
    obs_mar = df[mar].groupby([df[mar].pitcher_anon_id.astype(str), df[mar].pitch_type.astype(str)]).rv.agg(["mean", "size"])
    filas = []
    for t in ES:
        sel = tipos == t
        if sel.sum() < 500:
            continue
        dd = pd.DataFrame({"p": ids[sel], "y": y[sel], "f": (p_alt - p_mar)[sel]})
        pe = dd.groupby("p").agg(y=("y", "mean"), f=("f", "mean"), n=("y", "size"))
        pe = pe.join(obs_mar.xs(t, level=1, drop_level=True) if t in obs_mar.index.get_level_values(1) else pd.DataFrame(),
                     how="inner")
        pe = pe[(pe.n >= 30) & (pe["size"] >= 30)]
        if len(pe) < 5:
            continue
        w = 2 / (1 / pe.n + 1 / pe["size"])
        filas.append({"tipo": ES[t], "lanzadores": int(len(pe)),
                      "fisica_100": float(np.average(pe.f, weights=w) * 100),
                      "observado_100": float(np.average(pe.y - pe["mean"], weights=w) * 100)})
    if len(filas) >= 4:
        from scipy.stats import spearmanr
        r = spearmanr([f["fisica_100"] for f in filas], [f["observado_100"] for f in filas])
        res["por_tipo"] = filas
        res["por_tipo_spearman"] = {"rho": float(r.correlation), "p": float(r.pvalue), "tipos": len(filas)}
    return limpio(res)


# ================================================================================ B. discriminación
def discriminacion(df: pd.DataFrame, oof: np.ndarray) -> dict:
    """Carreras por 100 lanzamientos del 10 % mejor contra el 10 % peor, con la predicción fuera de muestra."""
    res = {}
    y = df.rv.to_numpy()
    sw = df.y_whiff.to_numpy()
    ids = grupos(df)
    for k, nombre in enumerate(("stuff", "location", "pitching")):
        s = -oof[k]
        ok = np.isfinite(s) & np.isfinite(y)
        lo, hi = np.nanpercentile(s[ok], [10, 90])
        alto, bajo = ok & (s >= hi), ok & (s <= lo)

        def brecha(idx):
            a, b_ = alto[idx], bajo[idx]
            return (y[idx][b_].mean() - y[idx][a].mean()) * 100

        res[nombre] = {
            "carreras_100_mejor10": float(y[alto].mean() * 100), "carreras_100_peor10": float(y[bajo].mean() * 100),
            "brecha_100": float(brecha(np.arange(len(y)))),
            "brecha_ic95": ic(boot_lanzadores(ids, brecha, b=min(B, 400))),
            "whiff_mejor10": float(np.nanmean(sw[alto])), "whiff_peor10": float(np.nanmean(sw[bajo])),
        }
        print(f"  {nombre}: brecha {res[nombre]['brecha_100']:.2f} carreras por 100", flush=True)
    return limpio(res)


# ================================================================================ C. confiabilidad
def confiabilidad(df: pd.DataFrame, oof: np.ndarray) -> dict:
    """Estabilidad entre mitades, separando calidad de mezcla de lanzamientos."""
    d = pd.DataFrame({"p": grupos(df), "t": df.pitch_type.astype(str).to_numpy(), "s": -oof[0], "rv": df.rv.to_numpy()})
    d = d[np.isfinite(d.s) & np.isfinite(d.rv)]
    d["resid"] = d.s - d.groupby("t").s.transform("mean")             # calidad contra su propio tipo
    d["mezcla"] = d.groupby("t").s.transform("mean")                  # lo que da sólo la mezcla
    d["mitad"] = d.groupby("p").cumcount() % 2

    def mitades(dd: pd.DataFrame, col: str, minimo: int) -> tuple[float, int, list]:
        h = dd.groupby(["p", "mitad"]).agg(n=(col, "size"), v=(col, "mean")).unstack()
        h = h[(h["n"] >= minimo).all(axis=1)]
        if len(h) < 10:
            return np.nan, int(len(h)), [np.nan, np.nan]
        a, b_ = h["v"][0].to_numpy(), h["v"][1].to_numpy()
        bs = []
        for _ in range(min(B, 1000)):
            k = rng.integers(0, len(a), len(a))
            bs.append(np.corrcoef(a[k], b_[k])[0, 1])
        return float(np.corrcoef(a, b_)[0, 1]), int(len(h)), ic(bs)

    res = {}
    for clave, dd, col, mn in (("crudo", d, "s", 150), ("sin_mezcla", d, "resid", 150), ("solo_mezcla", d, "mezcla", 150),
                               ("solo_rectas", d[d.t == "Four-Seam"], "s", 100), ("carreras", d, "rv", 150)):
        r, n, i = mitades(dd, col, mn)
        res[clave] = {"r": r, "lanzadores": n, "ic95": i}
        print(f"  {clave}: {r:.3f} ({n} lanzadores)", flush=True)
    return limpio(res)


# ================================================================================ D. futuro
def futuro(df: pd.DataFrame, oof: np.ndarray) -> dict:
    """Asociación retrospectiva entre años; OLS agregado con holdout de pitcher."""
    d = pd.DataFrame({"p": grupos(df), "year": df.year.to_numpy(), "s": -oof[0], "rv": df.rv.to_numpy(),
                      "sw": df.y_whiff.to_numpy()})
    d = d[np.isfinite(d.s) & np.isfinite(d.rv)]
    a = d.groupby(["p", "year"]).agg(n=("rv", "size"), s=("s", "mean"), rv=("rv", "mean"), sw=("sw", "mean"))
    pares = []
    for y0 in sorted(d.year.unique())[:-1]:
        x0 = a.xs(y0, level="year")
        x1 = a.xs(y0 + 1, level="year") if (y0 + 1) in d.year.unique() else None
        if x1 is None:
            continue
        j = x0.join(x1, lsuffix="_0", rsuffix="_1", how="inner")
        j = j[(j.n_0 >= 200) & (j.n_1 >= 200)]
        j["par"] = f"{y0}→{y0 + 1}"
        pares.append(j.reset_index())
    pf = pd.concat(pares, ignore_index=True)
    ids = pf.p.to_numpy()
    preds = {"stuff": pf.s_0.to_numpy(), "carreras_pasadas": -pf.rv_0.to_numpy(), "whiff_pasado": pf.sw_0.to_numpy()}
    res = {"pares": int(len(pf)), "lanzadores": int(len(np.unique(ids))), "por_par": pf.par.value_counts().to_dict(),
           "method": "Retrospective year-pair association; aggregated OLS is cross-fitted by pitcher.",
           "limits": ["Input Stuff+ OOF models were trained across all calendar years, excluding the focal pitcher.",
                      "This is not prospective temporal validation.",
                      "Target/count references and physics in stored OOF artifacts were not nested."]}
    for objetivo, yv in (("carreras", -pf.rv_1.to_numpy()), ("whiff", pf.sw_1.to_numpy())):
        r = {}
        for k, x in preds.items():
            r[k] = {"r": corr(x, yv), "ic95": ic(boot_lanzadores(ids, lambda i, x=x: corr(x[i], yv[i])))}
        dif = boot_lanzadores(ids, lambda i: corr(preds["stuff"][i], yv[i]) - corr(preds["carreras_pasadas"][i], yv[i]))
        r["stuff_menos_carreras_pasadas"] = {"d": r["stuff"]["r"] - r["carreras_pasadas"]["r"], "ic95": ic(dif)}

        # Mejora de error sobre predicciones realmente fuera del ajuste agregado.
        p_base, p_extra = models.incremental_oof(yv, preds["carreras_pasadas"], preds["stuff"], ids)
        valid = np.isfinite(yv) & np.isfinite(p_base) & np.isfinite(p_extra)
        Y = yv[valid]
        loss_gain = (Y - p_base[valid]) ** 2 - (Y - p_extra[valid]) ** 2
        def r2_inc(i):
            variance = np.var(Y[i])
            return float(np.mean(loss_gain[i]) / variance) if variance > 0 else np.nan
        todos = np.arange(len(Y))
        r["r2_incremental_stuff"] = {
            "d": r2_inc(todos),
            "ic95": ic(boot_lanzadores(ids[valid], r2_inc)),
            "n": int(valid.sum()),
            "method": "Pitcher-grouped OOF OLS; bootstrap fixed paired squared-error differences by pitcher divided by outcome variance.",
            "limits": "Conditional interval for fixed OOF predictions; excludes retraining and upstream model uncertainty.",
            "baseline_oof": models.score(Y, p_base[valid]),
            "plus_stuff_oof": models.score(Y, p_extra[valid]),
        }
        res[objetivo] = r
        print(f"  {objetivo}: stuff {r['stuff']['r']:+.3f}, carreras pasadas {r['carreras_pasadas']['r']:+.3f}", flush=True)
    return limpio(res)


# ================================================================================ E. combinación ponderada
COMPONENTES = ["y_swing", "y_whiff", "y_called_strike", "y_chase", "y_groundball", "y_weak_contact",
               "y_hard_contact", "y_barrel", "y_out_pa"]


def out_en_turno(df: pd.DataFrame) -> np.ndarray:
    """1 si el turno de este lanzamiento termina en out (ponche u out en juego), con el mismo criterio que sequence.py."""
    ult = df.sort_values("file_order").groupby("pa_id", sort=False).tail(1)
    hit = sum(ult[c].fillna(0).to_numpy() for c in ("single", "double", "triple", "home_run"))
    out = (ult["strikeout"].fillna(0).to_numpy() == 1) | ((ult["is_ball_in_play"].fillna(0).to_numpy() == 1) & (hit == 0))
    return df["pa_id"].map(pd.Series(out.astype(float), index=ult["pa_id"].to_numpy())).to_numpy(dtype=float)


def combinacion(df: pd.DataFrame, oof: np.ndarray) -> dict:
    feats = F.feature_sets()["stuff"]
    entrena = json.loads((ART / "models.json").read_text()).get("stuff_entrena", "todo")
    puede = (df.altitude_category == MAR).to_numpy() if entrena == "mar" else np.ones(len(df), dtype=bool)
    d = df.copy()
    try:
        d["y_out_pa"] = out_en_turno(d)
    except Exception as e:                                  # si faltan columnas, sigue sin esa componente
        print(f"  sin y_out_pa ({e})", flush=True)
    comps = [c for c in COMPONENTES if c in d.columns]
    g = grupos(d)
    pliegues = list(GroupKFold(PLIEGUES).split(d, groups=g))
    P = {}
    for c in comps:
        t0 = time.time()
        prm = {**models.PARAMS, **(models.params_for(c) if c != "y_out_pa" else {"objective": "binary"})}
        definido = d[c].notna().to_numpy()
        pr = np.full(len(d), np.nan)
        # Entrena con las filas donde el objetivo existe y predice la probabilidad en todas las filas de prueba,
        # porque para combinar hace falta en cada lanzamiento.
        for tr, te in pliegues:
            tr = tr[definido[tr] & puede[tr]]
            bst = lgb.train(prm, lgb.Dataset(d.iloc[tr][feats], d.iloc[tr][c].to_numpy(dtype=float)), num_boost_round=250)
            pr[te] = bst.predict(d.iloc[te][feats])
        P[c] = pr
        print(f"  {c} listo en {time.time() - t0:.0f}s", flush=True)

    X = np.column_stack([P[c] for c in comps])
    y = d.rv.to_numpy()
    ok = np.isfinite(y) & np.isfinite(X).all(axis=1)
    comb = np.full(len(d), np.nan)
    pos = np.flatnonzero(ok)
    pesos = []
    for tr, te in GroupKFold(PLIEGUES).split(pos, groups=g[pos]):
        tri = pos[tr]
        tri = tri[puede[tri]]
        A = np.c_[np.ones(len(tri)), X[tri]]
        beta, *_ = np.linalg.lstsq(A, y[tri], rcond=None)
        comb[pos[te]] = np.c_[np.ones(len(te)), X[pos[te]]] @ beta
        pesos.append(beta[1:])
    directo = oof[0]
    m = ok & np.isfinite(directo)
    res = {"componentes": comps, "pesos": dict(zip(comps, np.mean(pesos, axis=0))),
           "combinado": models.score(y[m], comb[m]), "directo": models.score(y[m], directo[m]),
           "corr_entre_ellos": corr(comb[m], directo[m])}
    # Lo mismo en las dos pruebas que importan para un Stuff+: brecha 10 % y estabilidad entre mitades.
    for nombre, pred in (("combinado", comb), ("directo", directo)):
        s = -pred
        lo, hi = np.nanpercentile(s[m], [10, 90])
        res[nombre]["brecha_100"] = float((y[m & (s <= lo)].mean() - y[m & (s >= hi)].mean()) * 100)
        h = pd.DataFrame({"p": g[m], "s": s[m]})
        h["mitad"] = h.groupby("p").cumcount() % 2
        hh = h.groupby(["p", "mitad"]).agg(n=("s", "size"), v=("s", "mean")).unstack()
        hh = hh[(hh["n"] >= 150).all(axis=1)]
        res[nombre]["mitades"] = float(np.corrcoef(hh["v"][0], hh["v"][1])[0, 1])
    print(f"  combinado r2 {res['combinado']['r2']:.5f} contra directo {res['directo']['r2']:.5f}", flush=True)
    return limpio(res)


# ================================================================================ F. especificaciones
FRENADO = ["SpeedDrop", "ZoneSpeed", "ZoneTime"]


def especificaciones(df: pd.DataFrame) -> dict:
    """Pérdida por tipo al pasar a altitud extrema, con tres versiones de Stuff+."""
    phys = json.loads((ART / "physics.json").read_text())
    rho = phys["rho_altitud_extrema"]
    feats = F.feature_sets()["stuff"]
    mar = (df.altitude_category == MAR).to_numpy()
    todos = np.ones(len(df), dtype=bool)
    # Una muestra basta para estimar la pérdida promedio por tipo y ahorra mucho tiempo de integración.
    idx = rng.choice(len(df), size=min(len(df), 200_000), replace=False)
    d = df.iloc[np.sort(idx)]
    x_mar = transferir(d, feats, 1.0)
    x_alt = transferir(d, feats, rho)
    tipos = d.pitch_type.astype(str).to_numpy()
    # La versión de producción usa los juegos con que se entrenó Stuff+ (models.json). La tercera variante es la otra
    # muestra de entrenamiento, para ver si la conclusión depende de esa elección.
    entrena = json.loads((ART / "models.json").read_text()).get("stuff_entrena", "todo")
    prod = mar if entrena == "mar" else todos
    otra, filas_otra = ("todos_los_juegos", todos) if entrena == "mar" else ("solo_mar", mar)
    res = {"variantes": {}, "entrena": entrena, "otra": otra}
    for nombre, f_, filas in (("produccion", feats, prod), ("sin_frenado", [c for c in feats if c not in FRENADO], prod),
                              (otra, feats, filas_otra)):
        t0 = time.time()
        bst = entrena_stuff(df, f_, filas)
        s_ = -bst.predict(df.loc[df.rv.notna(), f_])
        cen, sd = float(s_.mean()), float(s_.std())
        pm = 100 + 10 * (-bst.predict(x_mar[f_]) - cen) / sd
        pa = 100 + 10 * (-bst.predict(x_alt[f_]) - cen) / sd
        por = {ES[t]: float(np.mean(pa[tipos == t] - pm[tipos == t])) for t in ES if (tipos == t).sum() > 200}
        res["variantes"][nombre] = {"variables": len(f_), "liga": float(np.mean(pa - pm)), "por_tipo": por,
                                    "por_tipo_carreras_100": {k: -v * sd / 10 * 100 for k, v in por.items()}}
        print(f"  {nombre}: liga {np.mean(pa - pm):+.2f} ({time.time() - t0:.0f}s)", flush=True)
    from scipy.stats import spearmanr
    v = res["variantes"]
    tt = list(v["produccion"]["por_tipo"])
    res["orden_igual"] = {
        k: float(spearmanr([v["produccion"]["por_tipo"][t] for t in tt], [v[k]["por_tipo"][t] for t in tt]).correlation)
        for k in ("sin_frenado", otra)}
    return limpio(res)


# ================================================================================ principal
def main() -> None:
    t0 = time.time()
    df = pd.read_pickle(ART / "scored.pkl")
    oof = np.load(ART / "oof_rv.npy")
    print(f"scored.pkl: {len(df):,} lanzamientos · bootstrap {B}", flush=True)
    partes = (("parque", lambda: parque(df)), ("discriminacion", lambda: discriminacion(df, oof)),
              ("confiabilidad", lambda: confiabilidad(df, oof)), ("futuro", lambda: futuro(df, oof)),
              ("especificaciones", lambda: especificaciones(df)), ("combinacion", lambda: combinacion(df, oof)))
    pedidas = set(sys.argv[1:]) or {n for n, _ in partes}
    previo = ART / "robustez.json"
    salida: dict = json.loads(previo.read_text()) if previo.exists() and set(sys.argv[1:]) else {}
    salida["stuff_entrena"] = json.loads((ART / "models.json").read_text()).get("stuff_entrena", "todo")
    for nombre, f in partes:
        if nombre not in pedidas:
            continue
        print(f"{nombre}…", flush=True)
        t1 = time.time()
        try:
            salida[nombre] = f()
        except Exception as e:                       # una parte que falla no tumba a las demás
            salida[nombre] = {"error": f"{type(e).__name__}: {e}"}
            traceback.print_exc()
        print(f"  {nombre} en {time.time() - t1:.0f}s", flush=True)
        guardar(salida)
    print(f"listo en {time.time() - t0:.0f}s → app/public/data/robustez.json")


if __name__ == "__main__":
    main()
