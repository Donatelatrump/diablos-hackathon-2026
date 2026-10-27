"""Exportacion del modelo y de las tablas al front.

El simulador corre entero en el navegador: los arboles de LightGBM se serializan a JSON
plano y un evaluador de unas cuantas lineas los recorre. Sin servidor, sin wasm, sin
latencia. Importa para la entrevista de 10 minutos con el jurado: el tablero funciona
aunque no haya red en la sala.
"""
from __future__ import annotations

import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd


def _flatten(tree: dict) -> dict:
    """Aplana un arbol de LightGBM a arreglos paralelos.

    Los hijos se guardan como indices; un indice negativo apunta a una hoja:
    `-k - 1` es la hoja `k`. Asi el evaluador es un solo bucle sin recursion.
    """
    feat: list[int] = []
    thr: list[float] = []
    left: list[int] = []
    right: list[int] = []
    miss: list[int] = []   # 1 si los faltantes van al hijo izquierdo
    leaves: list[float] = []

    def walk(node: dict) -> int:
        if "leaf_value" in node:
            leaves.append(float(node["leaf_value"]))
            return -len(leaves)          # -1, -2, ... -> hoja 0, 1, ...
        idx = len(feat)
        feat.append(int(node["split_feature"]))
        thr.append(float(node["threshold"]))
        miss.append(1 if node.get("default_left", True) else 0)
        left.append(0)
        right.append(0)
        left[idx] = walk(node["left_child"])
        right[idx] = walk(node["right_child"])
        return idx

    walk(tree["tree_structure"])
    return {"f": feat, "t": thr, "l": left, "r": right, "d": miss, "v": leaves}


def export_booster(booster: lgb.Booster, objective: str = "regression") -> dict:
    dumped = booster.dump_model()
    return {
        "features": list(dumped["feature_names"]),
        "objective": objective,
        "trees": [_flatten(t) for t in dumped["tree_info"]],
    }


def fit_helpers(df: pd.DataFrame) -> dict:
    """Relaciones auxiliares que el simulador necesita y no salen de la integracion.

    EffectiveVelo (velocidad percibida) y SpinAxis no los produce el integrador, pero
    ambos son casi deterministas dadas las magnitudes que si produce. Se ajusta una
    regresion lineal chica de cada uno y se exportan los coeficientes, en vez de pedirle
    al coach que los invente.
    """
    out: dict = {}

    # Velocidad percibida ~ velocidad de release + extension
    m = df[["RelSpeed", "Extension", "EffectiveVelo"]].dropna()
    X = np.c_[np.ones(len(m)), m.RelSpeed, m.Extension]
    coef, *_ = np.linalg.lstsq(X, m.EffectiveVelo.to_numpy(), rcond=None)
    pred = X @ coef
    out["effective_velo"] = {
        "coef": [float(c) for c in coef],
        "terms": ["1", "RelSpeed", "Extension"],
        "r2": float(1 - ((m.EffectiveVelo - pred) ** 2).sum() / ((m.EffectiveVelo - m.EffectiveVelo.mean()) ** 2).sum()),
    }

    # Eje de giro: es la direccion del movimiento, medida como angulo de reloj.
    # Se guarda el offset empirico entre atan2(hb, ivb) y el SpinAxis reportado.
    m = df[["HorzBreak", "InducedVertBreak", "SpinAxis", "PitcherThrows"]].dropna()
    ang = np.degrees(np.arctan2(m.HorzBreak.to_numpy(), m.InducedVertBreak.to_numpy()))
    resid = (m.SpinAxis.to_numpy() - ang + 180) % 360 - 180
    out["spin_axis"] = {"offset_deg": float(np.median(resid)), "mad_deg": float(np.median(np.abs(resid - np.median(resid))))}

    # Eficiencia de spin ~ movimiento total / spin rate (para reconstruirla en el navegador)
    m = df[["movement_total", "SpinRate", "RelSpeed", "spin_efficiency"]].dropna()
    m = m[np.isfinite(m).all(axis=1)]
    X = np.c_[np.ones(len(m)), m.movement_total, m.SpinRate, m.RelSpeed]
    coef, *_ = np.linalg.lstsq(X, m.spin_efficiency.to_numpy(), rcond=None)
    pred = X @ coef
    out["spin_efficiency"] = {
        "coef": [float(c) for c in coef],
        "terms": ["1", "movement_total", "SpinRate", "RelSpeed"],
        "r2": float(1 - ((m.spin_efficiency - pred) ** 2).sum() / ((m.spin_efficiency - m.spin_efficiency.mean()) ** 2).sum()),
    }

    # Dispersion del arrastre entre pelotas. Dentro de un mismo juego el aire es uno, asi que lo que
    # varia de un lanzamiento a otro es la pelota (costuras, desgaste) mas el ruido de Trackman. El
    # pipeline vuela cada lanzamiento con su propio arrastre; el simulador promedia sobre esta
    # dispersion para que su Stuff+ por forma sea comparable. Escala robusta (MAD) del log.
    if {"k_drag", "game_anon_id"}.issubset(df.columns):
        k = df["k_drag"].where(df["k_drag"] > 0)
        lk = np.log(k)
        r = (lk - lk.groupby(df["game_anon_id"]).transform("median")).dropna().to_numpy()
        out["arrastre"] = {
            "log_sd": float(1.4826 * np.median(np.abs(r - np.median(r)))),
            "n": int(len(r)),
        }
    return out


def write_json(path: Path, obj: dict, compact: bool = True) -> int:
    """Escribe JSON y devuelve el tamano en bytes."""
    text = json.dumps(obj, separators=(",", ":") if compact else None,
                      indent=None if compact else 2, ensure_ascii=False)
    path.write_text(text)
    return len(text.encode())
