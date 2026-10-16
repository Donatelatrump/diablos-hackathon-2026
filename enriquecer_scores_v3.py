"""Enriquece scores_pitch_v3.parquet con features físicas y regenera perfil ideal."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd


def main():
    scores_path = Path("stuff_plus_output_v3/scores_pitch_v3.parquet")
    parquet_path = Path("stuff_model_df.parquet")
    salida = Path("stuff_plus_output_v3")
    salida.mkdir(parents=True, exist_ok=True)

    if not scores_path.exists():
        print(f"No existe {scores_path}")
        return

    scores = pd.read_parquet(scores_path)
    print(f"Scores: {len(scores):,} filas")

    # Enriquecer con features físicas del parquet original
    con = duckdb.connect()
    try:
        enriched = con.execute(
            """
            SELECT s.*, d.RelSpeed, d.SpinRate, d.SpinAxis, d.InducedVertBreak,
                   d.HorzBreak, d.Extension, d.RelHeight, d.RelSide, d.PitcherThrows,
                   d.AutoPitchType as pitch_type_original
            FROM read_parquet(?) s
            JOIN read_parquet(?) d
              ON s.PitchUID = d.PitchUID
            """,
            [str(scores_path.resolve()), str(parquet_path.resolve())],
        ).fetchdf()
    finally:
        con.close()

    print(f"Enriquecido: {len(enriched):,} filas")
    enriched_path = salida / "scores_pitch_v3_enriquecido.parquet"
    con2 = duckdb.connect()
    try:
        con2.register("enriched_df", enriched)
        con2.execute(
            f"COPY enriched_df TO '{str(enriched_path.resolve()).replace(chr(39), chr(39)*2)}' "
            f"(FORMAT PARQUET, COMPRESSION ZSTD)"
        )
    finally:
        con2.close()

    # Perfil ideal con features físicas
    harp = enriched[enriched["altitude_category"] == "Extreme Altitude"].copy()
    if harp.empty:
        print("No hay datos Extreme Altitude.")
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
        "release_height_media_elite_ft": float(elite["RelHeight"].mean()) if "RelHeight" in elite.columns else None,
        "release_side_media_elite_ft": float(elite["RelSide"].mean()) if "RelSide" in elite.columns else None,
        "tipos_elite": elite["AutoPitchType"].value_counts().to_dict() if "AutoPitchType" in elite.columns else {},
        "mano_lanzadora_elite": elite["PitcherThrows"].value_counts().to_dict() if "PitcherThrows" in elite.columns else {},
        "stuff_plus_medio_elite": float(elite["stuff_plus_provisional"].mean()),
        "stuff_plus_medio_todos_harp": float(harp["stuff_plus_provisional"].mean()),
    }

    perfil_path = salida / "perfil_ideal_diablos.json"
    with open(perfil_path, "w", encoding="utf-8") as f:
        json.dump(perfil, f, indent=2, ensure_ascii=False)
    print(f"Perfil ideal actualizado: {perfil_path}")
    print(json.dumps(perfil, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
