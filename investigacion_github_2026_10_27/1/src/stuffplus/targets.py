"""Objetivos del modelo: probabilidades de resultado y valor de carrera por lanzamiento.

El dataset no trae el estado de corredores, asi que no se puede construir la matriz
base-out de 24 estados. Se usa en su lugar la cadena de conteos (12 estados), que para un
modelo de calidad de lanzamiento es de hecho el marco correcto: Stuff+ pregunta que tan
bueno es el pitch, no que tan valioso fue dado quien estaba en base.

    RV(pitch) = valor(estado despues) - valor(estado antes)

donde el valor de un conteo es el run value esperado del turno que pasa por ahi, y el de
un evento terminal es su peso lineal.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Pesos lineales estandar (runs sobre out), re-centrados abajo con la frecuencia real
# de eventos de la LMB para que el turno promedio valga cero.
LINEAR_WEIGHTS = {
    "bb": 0.55, "hbp": 0.58, "1b": 0.70, "2b": 1.00, "3b": 1.27, "hr": 1.65,
    "k": -0.27, "out_bip": -0.25, "none": 0.0,
}

COUNTS = [f"{b}-{s}" for b in range(4) for s in range(3)]


def barrel(exit_speed: pd.Series, angle: pd.Series) -> np.ndarray:
    """Definicion de barril de MLB: a partir de 98 mph, el rango de angulo se abre con la
    velocidad de salida."""
    ev = exit_speed.to_numpy(dtype=float)
    la = angle.to_numpy(dtype=float)
    lo = 26.0 - (ev - 98.0)
    hi = 30.0 + (ev - 98.0)
    return ((ev >= 98.0) & (la >= np.maximum(lo, 8.0)) & (la <= np.minimum(hi, 50.0))).astype(float)


def run_values(
    df: pd.DataFrame, pa_events: pd.DataFrame,
    reference: tuple[float, pd.Series] | None = None,
) -> tuple[pd.DataFrame, pd.Series]:
    """Valor de carrera por lanzamiento y tabla de valor por conteo."""
    ev_by_pa = pa_events.set_index("pa_id")["pa_event"]
    pa_value = ev_by_pa.map(LINEAR_WEIGHTS).astype(float)
    pa_center = float(pa_value.mean()) if reference is None else reference[0]
    pa_value = pa_value - pa_center  # usa solo el centro del entrenamiento en validación

    df = df.copy()
    df["pa_value"] = df["pa_id"].map(pa_value)
    df["count"] = df["Balls"].astype(int).astype(str) + "-" + df["Strikes"].astype(int).astype(str)

    # Valor de cada conteo = valor medio de los turnos que pasan por el.
    if reference is None:
        count_value = df.groupby("count")["pa_value"].mean()
        count_value = count_value.reindex(COUNTS).fillna(0.0)
    else:
        count_value = reference[1].reindex(COUNTS).fillna(0.0)

    balls = df["Balls"].to_numpy(dtype=float)
    strikes = df["Strikes"].to_numpy(dtype=float)
    before = df["count"].map(count_value).to_numpy(dtype=float)

    # Estado despues del lanzamiento
    is_ball = (df["is_called_strike"].fillna(0).to_numpy() == 0) & df["PitchCall"].astype(str).isin(
        ["BallCalled", "BallinDirt", "BallIntentional"]
    ).to_numpy()
    is_strike = (
        (df["is_called_strike"].fillna(0).to_numpy() == 1)
        | (df["is_whiff"].fillna(0).to_numpy() == 1)
        | (df["PitchCall"].astype(str).str.startswith("Foul").to_numpy() & (strikes < 2))
    )
    terminal = df["is_ball_in_play"].fillna(0).to_numpy() == 1
    terminal |= df["is_hit_by_pitch"].fillna(0).to_numpy() == 1
    terminal |= is_ball & (balls >= 3)
    terminal |= is_strike & (strikes >= 2) & (df["is_whiff"].fillna(0).to_numpy() == 1)
    terminal |= is_strike & (strikes >= 2) & (df["is_called_strike"].fillna(0).to_numpy() == 1)

    nb = np.clip(balls + is_ball, 0, 3)
    ns = np.clip(strikes + is_strike, 0, 2)
    nxt = pd.Series([f"{int(b)}-{int(s)}" for b, s in zip(nb, ns)]).map(count_value).to_numpy()
    after = np.where(terminal, df["pa_value"].to_numpy(dtype=float), nxt)

    df["rv"] = after - before
    df["count_value"] = before
    return df, count_value


def build(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega todas las columnas objetivo. Las condicionales quedan NaN fuera de su
    subconjunto, para que el modelo entrene solo sobre las filas donde el evento pudo pasar.
    """
    df = df.copy()
    swing = df["is_swing"].fillna(0).to_numpy()
    bip = df["is_ball_in_play"].fillna(0).to_numpy()
    outside = df["in_strike_zone"].to_numpy() == 0

    df["y_swing"] = swing
    df["y_whiff"] = np.where(swing == 1, df["is_whiff"].fillna(0).to_numpy(), np.nan)
    df["y_called_strike"] = np.where(swing == 0, df["is_called_strike"].fillna(0).to_numpy(), np.nan)
    df["y_chase"] = np.where(outside, swing, np.nan)
    df["y_groundball"] = np.where(bip == 1, (df["hit_type"].astype(str) == "GroundBall").to_numpy(), np.nan)
    df["y_barrel"] = np.where(bip == 1, barrel(df["ExitSpeed"], df["Angle"]), np.nan)
    df["y_hard_contact"] = np.where(bip == 1, (df["ExitSpeed"].to_numpy(dtype=float) >= 95.0), np.nan)
    df["y_weak_contact"] = np.where(bip == 1, (df["ExitSpeed"].to_numpy(dtype=float) < 80.0), np.nan)
    return df


def fit_reference(df: pd.DataFrame, pa_events: pd.DataFrame) -> tuple[float, pd.Series]:
    """Ajusta únicamente con entrenamiento el centro de PA y el valor de cada conteo.

    Un conteo ausente usa cero, el valor neutro del entrenamiento. La tabla no se
    actualiza al puntuar pruebas, aunque cambien todos sus resultados.
    """
    center = float(pa_events.pa_event.map(LINEAR_WEIGHTS).mean())
    _, counts = run_values(df, pa_events)
    return center, counts
