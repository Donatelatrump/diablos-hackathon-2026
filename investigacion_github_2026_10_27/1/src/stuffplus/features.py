"""Features del modelo.

Tres bloques, que corresponden a las tres capas del sistema:

  SHAPE     fisica pura del lanzamiento en el momento del release. Es lo unico que ve
            Stuff+, y por eso Stuff+ es transferible entre estadios.
  LOCATION  ubicacion, conteo y lado del bateador. Entra en Location+.
  ARSENAL   relacion del pitch con el repertorio completo del pitcher. Entra en Pitching+.

El diccionario de datos marca explicitamente que los identificadores anonimos no se usen
como feature (memorizacion de jugador); aqui solo sirven para agregar y agrupar.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .constants import FASTBALL_TYPES

# Los angulos de salida y de llegada (VertRelAngle, HorzRelAngle, VertApprAngle, HorzApprAngle)
# NO van en Stuff+, aunque se midan en el release. El angulo con que sale la pelota tambien dice a
# donde va, asi que con ellos el modelo aprende puntería: un Stuff+ que los usaba correlacionaba
# −0.70 con la distancia al centro de la zona (mas que Location+, −0.53), y el 58 % de su varianza
# se predecia solo con la ubicacion en el plato. Sin ellos: −0.03 y ~0 %. El reto define Stuff+
# como fisica pura; la ubicacion entra en Location+.
SHAPE = [
    "RelSpeed", "EffectiveVelo", "SpinRate", "SpinAxis",
    "InducedVertBreak", "HorzBreak", "VertBreak",
    "RelHeight", "RelSide", "Extension",
    "SpeedDrop", "ZoneTime", "ZoneSpeed",
    "spin_efficiency", "movement_total", "is_rhp",
]

LOCATION = ["PlateLocHeight", "PlateLocSide", "plate_dist", "balls", "strikes", "is_rhb", "platoon_same"]

ARSENAL = [
    "velo_diff_vs_fb", "ivb_diff_vs_fb", "hb_diff_vs_fb", "movement_diff_vs_fb",
    "tunnel_similarity", "pitch_usage_pct", "arsenal_size",
    "prev_is_fastball", "prev_velo_diff", "times_through",
]


def add_shape(df: pd.DataFrame, aero: pd.DataFrame) -> pd.DataFrame:
    """Features fisicas derivadas.

    `spin_efficiency` es la fraccion del giro que efectivamente produce movimiento: la
    aceleracion de Magnus observada contra la que produciria ese spin si todo el eje fuera
    perpendicular a la trayectoria. Es la respuesta directa a H4 ("shape over label"): dos
    pitches con el mismo rpm pueden moverse muy distinto.
    """
    df = df.copy()
    v = aero["v_rel"].to_numpy()
    omega = df["SpinRate"].to_numpy(dtype=float) * 2 * np.pi / 60.0
    # Magnus maximo alcanzable con ese spin, a spin factor equivalente
    ref = np.where(omega > 0, omega * v * 0.1208 / v, np.nan)
    df["spin_efficiency"] = np.clip(aero["a_magnus"].to_numpy() / (ref * v * 0.0045 + 1e-9), 0, 2)
    df["movement_total"] = np.hypot(df["InducedVertBreak"], df["HorzBreak"])
    df["is_rhp"] = (df["PitcherThrows"] == "Right").astype(float)
    df["is_rhb"] = (df["BatterSide"] == "Right").astype(float)
    df["platoon_same"] = (df["PitcherThrows"] == df["BatterSide"]).astype(float)
    df["balls"] = df["Balls"].astype(float)
    df["strikes"] = df["Strikes"].astype(float)
    # Distancia al centro de la zona, en pies
    df["plate_dist"] = np.hypot(df["PlateLocSide"], df["PlateLocHeight"] - 2.55)
    return df


def add_arsenal(df: pd.DataFrame) -> pd.DataFrame:
    """Features relacionales: cada pitch se juzga contra la recta primaria del pitcher.

    La referencia se calcula por pitcher y temporada, no global, porque un arsenal cambia
    de un ano a otro. Si el pitcher no tiene recta registrada, los diferenciales quedan en
    NaN y LightGBM los maneja como categoria propia.
    """
    df = df.copy()
    pt = df["pitch_type"].astype(str)
    key = ["pitcher_anon_id", "year"]

    # Recta primaria = el tipo de recta mas usado por ese pitcher esa temporada.
    fb = df[pt.isin(FASTBALL_TYPES)]
    fb_ref = fb.groupby(key).agg(
        fb_velo=("RelSpeed", "mean"),
        fb_ivb=("InducedVertBreak", "mean"),
        fb_hb=("HorzBreak", "mean"),
        fb_relx=("RelSide", "mean"),
        fb_relz=("RelHeight", "mean"),
    )
    df = df.join(fb_ref, on=key)

    df["velo_diff_vs_fb"] = df["RelSpeed"] - df["fb_velo"]
    df["ivb_diff_vs_fb"] = df["InducedVertBreak"] - df["fb_ivb"]
    df["hb_diff_vs_fb"] = df["HorzBreak"] - df["fb_hb"]
    df["movement_diff_vs_fb"] = np.hypot(df["ivb_diff_vs_fb"], df["hb_diff_vs_fb"])

    # Tunel: que tan parecido sale de la mano respecto a la recta. Mismo punto de salida
    # con distinto destino es justo lo que hace indistinguible un secundario.
    df["tunnel_similarity"] = 1.0 / (
        1.0 + np.hypot(df["RelSide"] - df["fb_relx"], df["RelHeight"] - df["fb_relz"]) * 12.0
    )

    usage = df.groupby(key + ["pitch_type"], observed=True).size().rename("n_pt")
    total = df.groupby(key).size().rename("n_total")
    df = df.join(usage, on=key + ["pitch_type"]).join(total, on=key)
    df["pitch_usage_pct"] = df["n_pt"] / df["n_total"]
    df["arsenal_size"] = df.join(
        df.groupby(key)["pitch_type"].nunique().rename("n_types"), on=key
    )["n_types"].astype(float)

    prev = df["prev_pitch_type"].astype(str)
    df["prev_is_fastball"] = prev.isin(FASTBALL_TYPES).astype(float)
    df["prev_velo_diff"] = df["RelSpeed"] - df["prev_rel_speed"]
    df["times_through"] = df["times_through"].astype(float)

    return df.drop(columns=["n_pt", "n_total"])


def feature_sets() -> dict[str, list[str]]:
    """Los tres conjuntos de features. Stuff+ nunca ve ubicacion ni parque."""
    return {
        "stuff": SHAPE,
        "location": SHAPE + LOCATION,
        "pitching": SHAPE + LOCATION + ARSENAL,
    }
