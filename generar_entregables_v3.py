"""Genera entregables obligatorios desde scores_pitch_v3.parquet:
1. stuff_plus_por_pitcher.csv - ranking de pitchers con delta altitud
2. stuff_plus_por_altitud.csv - efecto Harp Helu por altitud
3. perfil_ideal_diablos.json - perfil fisico ideal bajo altitud
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    scores_path = Path("stuff_plus_output_v3/scores_pitch_v3.parquet")
    salida = Path("stuff_plus_output_v3")
    salida.mkdir(parents=True, exist_ok=True)

    if not scores_path.exists():
        print(f"No existe {scores_path}")
        return

    df = pd.read_parquet(scores_path)
    print(f"Leyendo {scores_path}: {len(df):,} filas")

    # ===== 1. AGREGACION POR PITCHER =====
    agg = (
        df.groupby(["pitcher_anon_id", "altitude_category"])
        .agg(
            n_pitches=("PitchUID", "count"),
            stuff_plus_mean=("stuff_plus_provisional", "mean"),
            location_plus_mean=("location_plus_provisional", "mean"),
            pitching_plus_mean=("pitching_plus_provisional", "mean"),
        )
        .reset_index()
    )

    pivot = agg.pivot_table(
        index="pitcher_anon_id",
        columns="altitude_category",
        values="stuff_plus_mean",
        aggfunc="mean",
    ).reset_index()

    if "Extreme Altitude" in pivot.columns and "No Altitude" in pivot.columns:
        pivot["delta_stuff_plus_extreme_vs_no_altitude"] = (
            pivot["Extreme Altitude"] - pivot["No Altitude"]
        )
    elif "Extreme Altitude" in pivot.columns:
        pivot["delta_stuff_plus_extreme_vs_no_altitude"] = pivot["Extreme Altitude"]
    else:
        pivot["delta_stuff_plus_extreme_vs_no_altitude"] = np.nan

    total = (
        df.groupby("pitcher_anon_id")
        .agg(
            total_pitches=("PitchUID", "count"),
            stuff_plus_overall=("stuff_plus_provisional", "mean"),
            location_plus_overall=("location_plus_provisional", "mean"),
            pitching_plus_overall=("pitching_plus_provisional", "mean"),
            n_altitudes=("altitude_category", "nunique"),
        )
        .reset_index()
    )

    pitcher_summary = total.merge(pivot, on="pitcher_anon_id", how="left")

    arsenal = (
        df.groupby("pitcher_anon_id")["AutoPitchType"]
        .apply(lambda s: ", ".join(sorted(s.unique())))
        .reset_index()
        .rename(columns={"AutoPitchType": "arsenal_tipos"})
    )
    pitcher_summary = pitcher_summary.merge(arsenal, on="pitcher_anon_id", how="left")

    pitcher_summary = pitcher_summary.sort_values("stuff_plus_overall", ascending=False)
    out_path = salida / "stuff_plus_por_pitcher.csv"
    pitcher_summary.to_csv(out_path, index=False, encoding="utf-8")
    print(f"[1/3] Guardado: {out_path} ({len(pitcher_summary)} pitchers)")

    # ===== 2. RESUMEN POR ALTITUD =====
    altitud_resumen = (
        df.groupby("altitude_category")
        .agg(
            n_pitches=("PitchUID", "count"),
            n_pitchers=("pitcher_anon_id", "nunique"),
            stuff_plus_mean=("stuff_plus_provisional", "mean"),
            location_plus_mean=("location_plus_provisional", "mean"),
            pitching_plus_mean=("pitching_plus_provisional", "mean"),
        )
        .reset_index()
    )
    alt_path = salida / "stuff_plus_por_altitud.csv"
    altitud_resumen.to_csv(alt_path, index=False, encoding="utf-8")
    print(f"[2/3] Guardado: {alt_path}")
    print(altitud_resumen.to_string(index=False))

    # ===== 3. PERFIL IDEAL DIABLOS (Harp Helu / Extreme Altitude) =====
    harp = df[df["altitude_category"] == "Extreme Altitude"].copy()
    if harp.empty:
        print("No hay datos Extreme Altitude; se omite perfil ideal.")
        return

    umbral = harp["stuff_plus_provisional"].quantile(0.90)
    elite = harp[harp["stuff_plus_provisional"] >= umbral]

    perfil = {
        "n_pitches_elite": int(len(elite)),
        "umbral_stuff_plus_top10": float(umbral),
        "velocidad_media_elite_mph": float(elite["RelSpeed"].mean()) if "RelSpeed" in elite.columns else None,
        "spin_rate_media_elite_rpm": float(elite["SpinRate"].mean()) if "SpinRate" in elite.columns else None,
        "ivb_media_elite_pulg": float(elite["InducedVertBreak"].mean()) if "InducedVertBreak" in elite.columns else None,
        "hb_media_elite_pulg": float(elite["HorzBreak"].mean()) if "HorzBreak" in elite.columns else None,
        "extension_media_elite_ft": float(elite["Extension"].mean()) if "Extension" in elite.columns else None,
        "tipos_elite": elite["AutoPitchType"].value_counts().to_dict() if "AutoPitchType" in elite.columns else {},
        "mano_lanzadora_elite": elite["PitcherThrows"].value_counts().to_dict() if "PitcherThrows" in elite.columns else {},
        "stuff_plus_medio_elite": float(elite["stuff_plus_provisional"].mean()),
        "stuff_plus_medio_todos_harp": float(harp["stuff_plus_provisional"].mean()),
    }

    perfil_path = salida / "perfil_ideal_diablos.json"
    with open(perfil_path, "w", encoding="utf-8") as f:
        json.dump(perfil, f, indent=2, ensure_ascii=False)
    print(f"[3/3] Guardado: {perfil_path}")
    print(json.dumps(perfil, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
