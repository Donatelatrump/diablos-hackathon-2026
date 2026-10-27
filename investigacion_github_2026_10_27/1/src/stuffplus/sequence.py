"""Reconstruccion del orden de los lanzamientos y de los turnos al bate.

El dataset no trae fecha, numero de pitch ni identificador de turno. Pero las filas vienen
en orden cronologico y contiguas por juego (verificado: dentro de un juego las entradas son
monotonas y el conteo progresa 0-0, 1-0, 1-1...). Sobre esa base se reconstruye la secuencia,
que es lo que habilita `prev_pitch_type`, el efecto de tunel y la vuelta al orden.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def add_sequence(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega identificador de turno, numero de pitch dentro del turno y pitch previo.

    Un turno nuevo empieza en todo lanzamiento con conteo 0-0: dentro de un turno el conteo
    solo sube, asi que 0-0 aparece exactamente una vez. El cambio de bateador, pitcher o
    media entrada se usa ademas como respaldo, para cerrar turnos cuyo primer lanzamiento
    falta en los datos.
    """
    df = df.sort_values("file_order").copy()

    key = ["game_anon_id", "Inning", "Top/Bottom", "pitcher_anon_id", "batter_anon_id"]
    changed = np.zeros(len(df), dtype=bool)
    for c in key:
        v = df[c].astype(str).to_numpy()
        changed |= np.r_[True, v[1:] != v[:-1]]

    fresh = (df["Balls"].to_numpy() == 0) & (df["Strikes"].to_numpy() == 0)
    changed |= fresh

    df["pa_id"] = np.cumsum(changed)
    df["pitch_in_pa"] = df.groupby("pa_id").cumcount() + 1

    # Pitch previo del mismo pitcher dentro del turno (para secuencia y tunel).
    g = df.groupby("pa_id", sort=False)
    df["prev_pitch_type"] = g["pitch_type"].shift(1).astype("object").fillna("None")
    for col, out in [
        ("RelSpeed", "prev_rel_speed"),
        ("InducedVertBreak", "prev_ivb"),
        ("HorzBreak", "prev_hb"),
        ("PlateLocHeight", "prev_plate_z"),
        ("PlateLocSide", "prev_plate_x"),
    ]:
        df[out] = g[col].shift(1)

    # Vuelta al orden: cuantas veces este pitcher ya enfrento a este bateador en el juego.
    pa_first = df.groupby("pa_id", sort=False).head(1)
    order = (
        pa_first.groupby(["game_anon_id", "pitcher_anon_id", "batter_anon_id"], sort=False)
        .cumcount()
        + 1
    )
    df["times_through"] = df["pa_id"].map(pd.Series(order.to_numpy(), index=pa_first["pa_id"]))

    return df.sort_index()


def pa_outcome(df: pd.DataFrame) -> pd.DataFrame:
    """Resultado terminal de cada turno, tomado del ultimo lanzamiento."""
    last = df.sort_values("file_order").groupby("pa_id", sort=False).tail(1)
    ev = pd.Series("none", index=last.index, dtype=object)
    for flag, name in [
        ("is_hit_by_pitch", "hbp"), ("base_on_balls", "bb"), ("strikeout", "k"),
        ("single", "1b"), ("double", "2b"), ("triple", "3b"), ("home_run", "hr"),
    ]:
        ev[last[flag].fillna(0).to_numpy() == 1] = name
    in_play_out = (last["is_ball_in_play"].fillna(0).to_numpy() == 1) & (ev.to_numpy() == "none")
    ev[in_play_out] = "out_bip"
    return pd.DataFrame({"pa_id": last["pa_id"].to_numpy(), "pa_event": ev.to_numpy()})
