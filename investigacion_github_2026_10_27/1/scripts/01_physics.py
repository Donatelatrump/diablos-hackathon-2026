"""Etapa 1: densidad del aire, transferencia de forma y su validacion.

Produce:
  artifacts/pitches_rho.pkl        dataset + rho por juego (cache para etapas siguientes)
  artifacts/physics.json           constantes calibradas y metricas de validacion
  artifacts/altitude_deltas.json   delta de forma por tipo de pitch (entregable 1 y 3)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.stuffplus import io, physics  # noqa: E402
from src.stuffplus.constants import ALT_HARP_HELU  # noqa: E402

ART = Path(__file__).resolve().parents[1] / "artifacts"
SHAPE = ["ivb", "hb", "zone_speed", "vaa"]
RENAME = {
    "InducedVertBreak": "ivb",
    "HorzBreak": "hb",
    "ZoneSpeed": "zone_speed",
    "VertApprAngle": "vaa",
}
MIN_CELL = 40


def _cells(d: pd.DataFrame) -> pd.DataFrame:
    return (
        d[list(RENAME)]
        .rename(columns=RENAME)
        .assign(pitcher=d.pitcher_anon_id.values, pt=d.pitch_type.astype(str).values)
        .groupby(["pitcher", "pt"])[SHAPE]
        .agg(["mean", "size"])
    )


def main() -> None:
    df = io.load()
    aero = physics.decompose(df)
    rho = physics.air_density_index(df, aero)
    df["rho_game"] = rho["rho_game"]
    df["k_drag"] = rho["k_drag"]

    rho_by_bucket = df.groupby("altitude_category", observed=True)["rho_game"].median()
    rho_sea = float(rho_by_bucket["No Altitude"])
    rho_ext = float(rho_by_bucket["Extreme Altitude"])

    # --- validacion: llevar los pitches de nivel del mar al aire de altitud extrema ---
    sea = df[df.altitude_category == "No Altitude"]
    ext = df[df.altitude_category == "Extreme Altitude"]
    B, C = _cells(sea), _cells(ext)
    cells = B.index.intersection(C.index)
    cells = cells[(B.loc[cells, ("ivb", "size")] >= MIN_CELL) & (C.loc[cells, ("ivb", "size")] >= MIN_CELL)]

    # Split por PITCHER (no por celda): un pitcher nunca aparece en ambos lados.
    rng = np.random.default_rng(11)
    pitchers = cells.get_level_values(0).unique()
    fit = set(rng.choice(pitchers, size=len(pitchers) // 2, replace=False))
    is_fit = np.array([p in fit for p in cells.get_level_values(0)])

    aero_sea = physics.decompose(sea)

    def predict(gamma_v: float, gamma_h: float) -> pd.DataFrame:
        p = physics.transfer_shape(
            sea, rho_ext, rho_observed=sea.rho_game.to_numpy(), aero=aero_sea,
            magnus_gamma=gamma_v, magnus_gamma_h=gamma_h,
        )
        return p.assign(
            pitcher=sea.pitcher_anon_id.values, pt=sea.pitch_type.astype(str).values
        ).groupby(["pitcher", "pt"])[SHAPE].mean()

    def mae(A: pd.DataFrame, mask: np.ndarray) -> dict[str, float]:
        c = cells[mask]
        return {
            m: float(np.nanmean(np.abs(A.loc[c, m].to_numpy() - C.loc[c, (m, "mean")].to_numpy())))
            for m in SHAPE
        }

    grid = [(gv, gh) for gv in (1.4, 1.5, 1.6, 1.7) for gh in (1.8, 2.0, 2.2, 2.4)]
    scored = [(g, mae(predict(*g), is_fit)) for g in grid]
    gamma_v, gamma_h = min(scored, key=lambda t: t[1]["ivb"] + t[1]["hb"])[0]

    A_final = predict(gamma_v, gamma_h)
    A_density = predict(1.0, 1.0)
    holdout = {
        "calibrado": mae(A_final, ~is_fit),
        "solo_densidad": mae(A_density, ~is_fit),
        "sin_transferir": {
            m: float(np.nanmean(np.abs(
                B.loc[cells[~is_fit], (m, "mean")].to_numpy()
                - C.loc[cells[~is_fit], (m, "mean")].to_numpy())))
            for m in SHAPE
        },
    }

    # --- delta de forma por tipo de pitch, intra-pitcher (entregables 1 y 3) ---
    pt = cells.get_level_values(1)
    deltas = {}
    for m in ("ivb", "hb", "zone_speed"):
        obs = C.loc[cells, (m, "mean")].to_numpy() - B.loc[cells, (m, "mean")].to_numpy()
        pred = A_final.loc[cells, m].to_numpy() - B.loc[cells, (m, "mean")].to_numpy()
        t = pd.DataFrame({"pt": pt, "observado": obs, "predicho": pred}).groupby("pt").agg(
            observado=("observado", "mean"), predicho=("predicho", "mean"), n=("observado", "size")
        )
        deltas[m] = t.round(3).to_dict("index")

    ART.mkdir(exist_ok=True)
    df.to_pickle(ART / "pitches_rho.pkl")
    (ART / "physics.json").write_text(json.dumps({
        "n_pitches": int(len(df)),
        "rho_por_cubeta": {k: round(float(v), 4) for k, v in rho_by_bucket.items()},
        "rho_nivel_mar": round(rho_sea, 4),
        "rho_altitud_extrema": round(rho_ext, 4),
        "altitud_harp_helu_m": ALT_HARP_HELU,
        "magnus_gamma_vertical": gamma_v,
        "magnus_gamma_horizontal": gamma_h,
        "celdas_validacion": int(len(cells)),
        "celdas_holdout": int((~is_fit).sum()),
        "pitchers_cruce": int(len(pitchers)),
        "mae_holdout": {k: {m: round(v, 4) for m, v in d.items()} for k, d in holdout.items()},
    }, indent=2, ensure_ascii=False))
    (ART / "altitude_deltas.json").write_text(json.dumps(deltas, indent=2, ensure_ascii=False))

    print(f"rho: nivel del mar {rho_sea:.4f} | altitud extrema {rho_ext:.4f}")
    print(f"gamma calibrado: vertical {gamma_v}, horizontal {gamma_h}")
    print("\nMAE fuera de muestra (pulgadas / mph / grados):")
    print(pd.DataFrame(holdout).round(3).to_string())


if __name__ == "__main__":
    main()
