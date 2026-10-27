"""Modelos Stuff+, Location+ y Pitching+.

Tres capas sobre el mismo objetivo (el valor de carrera esperado del lanzamiento), que se
distinguen solo por que features ven:

  Stuff+     fisica del release. No ve ubicacion, conteo, bateador ni parque. Por eso es
             transferible: para saber cuanto vale el mismo pitch en otro aire, se le pasa
             la forma transferida y se vuelve a puntuar.
  Location+  agrega ubicacion, conteo y lado del bateador.
  Pitching+  agrega arsenal, secuencia y vuelta al orden.

La escala sigue la convencion sabermetrica: 100 es el promedio de la LMB de esa temporada,
y cada 10 puntos es una desviacion estandar. Se invierte el signo del run value porque un
run value bajo es bueno para el pitcher.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import GroupKFold

PARAMS = {
    "objective": "regression",
    "learning_rate": 0.05,
    "num_leaves": 96,
    "min_data_in_leaf": 400,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 5.0,
    "verbose": -1,
    "num_threads": 0,
}
N_ROUNDS = 500

# Objetivos raros (barril: 2.5% de tasa base, ~2,900 positivos) necesitan arboles mucho mas
# chicos y mas regularizacion. Con los parametros generales el modelo queda por debajo de
# predecir la tasa base.
RARE_PARAMS = {
    "objective": "binary",
    "num_leaves": 16,
    "min_data_in_leaf": 150,
    "learning_rate": 0.03,
    "feature_fraction": 0.7,
    "lambda_l2": 20.0,
}
RARE_TARGETS = {"y_barrel"}


# Stuff+ va mucho mas regularizado que las otras capas. Sin ubicacion, lo unico que le queda para
# separar lanzamientos es la fisica, y el punto de salida (RelSide, RelHeight, Extension) es casi una
# firma de cada lanzador: con hojas chicas el modelo memoriza lanzadores y, con lanzadores nuevos,
# queda peor que el promedio (R² −0.004 fuera de muestra). Con hojas grandes y L2 alto le gana al
# modelo nulo y su calificacion por lanzador es estable (0.99 entre mitades de sus lanzamientos).
CAPA_PARAMS: dict[str, tuple[dict, int]] = {
    "stuff": ({"num_leaves": 31, "min_data_in_leaf": 4000, "lambda_l2": 50.0, "learning_rate": 0.03}, 400),
}


def reescalar(fit: "Fitted", df: pd.DataFrame) -> "Fitted":
    """Recalcula centro y escala sobre todas las filas de `df`.

    Cuando un modelo se entrena con un subconjunto (Stuff+ solo con juegos a nivel del mar), su
    escala tiene que seguir midiendo contra la liga completa: 100 es el promedio de todos los
    lanzamientos de la LMB, no solo de los de nivel del mar.
    """
    s = -fit.raw(df)
    fit.center, fit.scale = float(np.nanmean(s)), float(np.nanstd(s))
    return fit


def capa(nombre: str) -> tuple[dict, int]:
    """Parametros y numero de arboles de una capa (stuff, location, pitching)."""
    extra, n = CAPA_PARAMS.get(nombre, ({}, N_ROUNDS))
    return extra, n


def params_for(target: str) -> dict:
    """Parametros segun el objetivo: los raros piden arboles chicos."""
    return dict(RARE_PARAMS) if target in RARE_TARGETS else {"objective": "binary"}


@dataclass
class Fitted:
    """Un modelo entrenado y la escala que lo lleva a la convencion 'plus'."""

    booster: lgb.Booster
    features: list[str]
    center: float = 0.0
    scale: float = 1.0
    calibrator: IsotonicRegression | None = None
    metrics: dict = field(default_factory=dict)

    def raw(self, X: pd.DataFrame) -> np.ndarray:
        return self.booster.predict(X[self.features], num_iteration=self.booster.best_iteration)

    def plus(self, X: pd.DataFrame) -> np.ndarray:
        """Escala plus: 100 + 10 z(-xRV). Mayor a 100 es mejor que el promedio de la liga."""
        return 100.0 + 10.0 * (-(self.raw(X)) - self.center) / self.scale


def train(
    df: pd.DataFrame,
    features: list[str],
    target: str = "rv",
    params: dict | None = None,
    n_rounds: int = N_ROUNDS,
    weight: np.ndarray | None = None,
) -> Fitted:
    """Entrena un modelo sobre todas las filas con objetivo definido."""
    p = {**PARAMS, **(params or {})}
    m = df[target].notna()
    X, y = df.loc[m, features], df.loc[m, target]
    ds = lgb.Dataset(X, y, weight=None if weight is None else weight[m.to_numpy()])
    booster = lgb.train(p, ds, num_boost_round=n_rounds)
    booster.best_iteration = n_rounds

    fit = Fitted(booster=booster, features=features)
    s = -booster.predict(X)
    fit.center, fit.scale = float(s.mean()), float(s.std())
    return fit


def group_ids(values: pd.Series) -> np.ndarray:
    """Preserva un único grupo desconocido también con StringDtype de pandas 3."""
    return values.astype("string").fillna("__desconocido__").to_numpy(dtype=str)


def fold_run_values(train_df: pd.DataFrame, test_df: pd.DataFrame):
    """Targets y baseline por conteo ajustados solo con filas de entrenamiento."""
    from . import sequence, targets
    train_events = sequence.pa_outcome(train_df)
    reference = targets.fit_reference(train_df, train_events)
    tr, _ = targets.run_values(train_df, train_events, reference=reference)
    te, _ = targets.run_values(test_df, sequence.pa_outcome(test_df), reference=reference)
    means = tr.groupby("count").rv.mean()
    baseline = te["count"].map(means).fillna(tr.rv.mean()).to_numpy(float)
    return tr, te, baseline


def cross_val(
    df: pd.DataFrame,
    features: list[str],
    target: str = "rv",
    groups: str = "pitcher_anon_id",
    n_splits: int = 5,
    params: dict | None = None,
    n_rounds: int = N_ROUNDS,
    train_mask: np.ndarray | None = None,
    rebuild_rv: bool = False,
) -> tuple[np.ndarray, dict]:
    """Validacion cruzada agrupada: ningun pitcher aparece en entrenamiento y prueba a la vez.

    `train_mask` limita las filas que pueden entrenar (por ejemplo, solo juegos a nivel del mar).
    La prediccion fuera de muestra se hace igual sobre todas las filas de los lanzadores de prueba.

    Es la prueba que importa para Stuff+. Sin agrupar por pitcher, el modelo puede memorizar
    firmas de release y reportar metricas que no sobreviven a un lanzador nuevo, que es
    justo el caso de uso: evaluar a un prospecto que el club no ha visto.
    """
    p = {**PARAMS, **(params or {})}
    m = df[target].notna().to_numpy()
    X, y = df.loc[m, features], df.loc[m, target].to_numpy()
    # Los pitches sin pitcher identificado (0.2% del dataset) forman su propio grupo, para
    # que no se repartan entre pliegues y contaminen el holdout.
    g = group_ids(df.loc[m, groups])

    oof = np.full(len(df), np.nan)
    eval_y, baseline = y.copy(), np.full(len(y), np.nan)
    idx = np.flatnonzero(m)
    puede = np.ones(len(idx), dtype=bool) if train_mask is None else np.asarray(train_mask)[idx]
    for tr, te in GroupKFold(n_splits=n_splits).split(X, y, g):
        tr = tr[puede[tr]]
        if rebuild_rv:
            if target != "rv":
                raise ValueError("rebuild_rv only applies to rv")
            dtr, dte, base = fold_run_values(df.iloc[idx[tr]], df.iloc[idx[te]])
            train_y = dtr.rv.to_numpy()
            eval_y[te], baseline[te] = dte.rv.to_numpy(), base
        else:
            train_y = y[tr]
        b = lgb.train(p, lgb.Dataset(X.iloc[tr], train_y), num_boost_round=n_rounds)
        oof[idx[te]] = b.predict(X.iloc[te])

    metrics = score(eval_y, oof[idx])
    if rebuild_rv:
        metrics["baseline_nulo_por_conteo"] = score(eval_y, baseline)
        metrics["target_reference"] = "training_fold_only"
        metrics["limits"] = "Arsenal features and physics calibration remain global; not fully nested preprocessing."
    return oof, metrics


def score(y: np.ndarray, pred: np.ndarray) -> dict:
    """Metricas contra el modelo nulo, que aqui es simplemente la media del objetivo."""
    m = np.isfinite(pred) & np.isfinite(y)
    y, pred = y[m], pred[m]
    sse = float(np.sum((y - pred) ** 2))
    sst = float(np.sum((y - y.mean()) ** 2))
    return {
        "n": int(m.sum()),
        "rmse": float(np.sqrt(sse / len(y))),
        "r2": 1.0 - sse / sst,
        "corr": float(np.corrcoef(y, pred)[0, 1]),
    }


def brier(y: np.ndarray, p: np.ndarray) -> dict:
    """Brier score y su mejora relativa contra predecir siempre la tasa base."""
    m = np.isfinite(y) & np.isfinite(p)
    y, p = y[m], p[m]
    bs = float(np.mean((y - p) ** 2))
    base = float(np.mean((y - y.mean()) ** 2))
    return {"n": int(m.sum()), "brier": bs, "brier_base": base, "skill": 1.0 - bs / base}


def calibration_table(y: np.ndarray, p: np.ndarray, bins: int = 10) -> pd.DataFrame:
    """Curva de calibracion: probabilidad predicha contra frecuencia observada."""
    m = np.isfinite(y) & np.isfinite(p)
    d = pd.DataFrame({"y": y[m], "p": p[m]})
    d["bin"] = pd.qcut(d.p, bins, duplicates="drop")
    return d.groupby("bin", observed=True).agg(
        predicha=("p", "mean"), observada=("y", "mean"), n=("y", "size")
    ).reset_index(drop=True)


def incremental_oof(
    y: np.ndarray, baseline_x: np.ndarray, extra_x: np.ndarray,
    groups: np.ndarray, n_splits: int = 4,
) -> tuple[np.ndarray, np.ndarray]:
    """Predicciones OLS anidadas, con cada pitcher fuera de ambos ajustes.

    Las filas incompletas conservan NaN. Es validación de la regresión agregada,
    no vuelve prospectivo un score de entrada entrenado retrospectivamente.
    """
    y, base, extra = (np.asarray(a, dtype=float) for a in (y, baseline_x, extra_x))
    groups = group_ids(pd.Series(groups))
    ok = np.isfinite(y) & np.isfinite(base) & np.isfinite(extra)
    pos = np.flatnonzero(ok)
    p1, p2 = np.full(len(y), np.nan), np.full(len(y), np.nan)
    folds = min(n_splits, len(np.unique(groups[ok])))
    if folds < 2:
        raise ValueError("At least two independent pitcher groups are required")
    X1 = np.c_[np.ones(len(y)), base]
    X2 = np.c_[X1, extra]
    for tr, te in GroupKFold(folds).split(pos, groups=groups[ok]):
        tri, tei = pos[tr], pos[te]
        p1[tei] = X1[tei] @ np.linalg.lstsq(X1[tri], y[tri], rcond=None)[0]
        p2[tei] = X2[tei] @ np.linalg.lstsq(X2[tri], y[tri], rcond=None)[0]
    return p1, p2
