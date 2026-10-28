"""Ingesta y limpieza del dataset pitch-by-pitch de la LMB.

El dataset viene en tres formatos equivalentes (.pkl, .parquet, .rds). Usamos el
parquet por velocidad de carga; el pickle queda como respaldo.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .constants import PITCH_TYPE_MAP

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = REPO_ROOT / "artifacts"

# Columnas que el diccionario marca como no utilizables como feature del modelo.
ID_COLS = ["PitchUID", "game_anon_id", "pitcher_anon_id", "batter_anon_id", "catcher_anon_id"]


def _resolve(path: str | Path | None) -> Path:
    if path is not None:
        return Path(path)
    for name in ("stuff_model_df.parquet", "stuff_model_df.pkl"):
        candidate = REPO_ROOT / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No se encontro stuff_model_df.{parquet,pkl} en la raiz del repo")


def load_raw(path: str | Path | None = None) -> pd.DataFrame:
    """Carga el dataset crudo sin transformaciones."""
    p = _resolve(path)
    if p.suffix == ".parquet":
        return pd.read_parquet(p)
    return pd.read_pickle(p)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Limpieza minima y documentada. No imputa ni filtra outliers fisicos todavia."""
    df = df.copy()

    # EffectiveVelo llega como string en el dataset original (dtype 'str' en pandas 3,
    # 'object' en pandas 2). Se normaliza a float en ambos casos.
    if not pd.api.types.is_numeric_dtype(df["EffectiveVelo"]):
        df["EffectiveVelo"] = pd.to_numeric(df["EffectiveVelo"], errors="coerce")

    # AutoPitchType trae clases residuales (Sweeper=588, Knuckleball=1, OneSeam=1).
    # Se colapsan a un vocabulario estable; la re-clasificacion por forma vive en cluster.py.
    df["pitch_type"] = (
        df["AutoPitchType"].astype(str).map(PITCH_TYPE_MAP).fillna("Other").astype("category")
    )

    # Handedness: 'Undefined'/'None' -> NaN explicito en vez de categoria fantasma.
    for col in ("PitcherThrows", "BatterSide"):
        df[col] = df[col].replace({"Undefined": np.nan, "None": np.nan, None: np.nan})

    # Switch hitters (54 filas) no declaran el lado real del turno; se descartan del lado.
    df["BatterSide"] = df["BatterSide"].replace({"Switch": np.nan})

    df["altitude_category"] = df["altitude_category"].replace({None: np.nan})

    # `is_hit_by_pitch` viene en cero en las 635,002 filas, aunque PitchCall registra 2,280
    # golpes y play_result 2,258. Es el unico flag derivado roto del dataset: los otros
    # trece coinciden con PitchCall/play_result en 99.7% o mas. Se reconstruye del call.
    df["is_hit_by_pitch"] = (df["PitchCall"].astype(str) == "HitByPitch").astype(float)

    # Orden cronologico: las filas vienen contiguas y ordenadas por juego en el archivo.
    # Se conserva explicitamente para poder reconstruir secuencias (ver sequence.py).
    df = df.reset_index(drop=True)
    df["file_order"] = np.arange(len(df), dtype=np.int64)

    return df


def load(path: str | Path | None = None) -> pd.DataFrame:
    """Carga + limpieza. Punto de entrada normal del pipeline."""
    return clean(load_raw(path))
