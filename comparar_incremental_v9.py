"""Compare frozen run-value predictions on identical pitches; export aggregates only."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import entrenar_stuff_plus_v9 as v9


def compare(original, incremental, output, parquet=None):
    protocols = [json.loads((directory / "protocolo.json").read_text()) for directory in [original, incremental]]
    for key in ["source_sha256", "test_year", "holdout", "held_group", "seed", "iterations", "partitions",
                "depth", "learning_rate", "l2_leaf_reg", "tasks"]:
        if protocols[0][key] != protocols[1][key]:
            raise ValueError(f"Experimentos no comparables: {key}")
    if protocols[0]["holdout"] != "season":
        raise ValueError("Esta comparación requiere el holdout temporal")
    if not protocols[1].get("incremental_gate"):
        raise ValueError("La segunda ejecución no activó el gate incremental")
    source = v9.data_path(parquet)
    if v9.v6.file_hash(source) != protocols[0]["source_sha256"]:
        raise ValueError("El dataset no coincide con los experimentos")
    test = v9.v5.prepare_raw(v9.read_rows(source, protocols[0]["test_year"], False))
    v9.validate_frame(test, training=True)
    scores = []
    for directory in [original, incremental]:
        if not (directory / "metricas.json").exists():
            raise ValueError(f"Evaluación incompleta: {directory}")
        frame = v9.v5.read_parquet(directory / "scores_pitch_v9.parquet")
        if frame.PitchUID.duplicated().any() or set(frame.PitchUID) != set(test.PitchUID):
            raise ValueError("Los pitches evaluados no coinciden")
        scores.append(frame.set_index("PitchUID").loc[test.PitchUID])
    y = test.run_value_proxy.to_numpy()
    groups = test.year.astype(str) + ":" + test.game_anon_id.astype(str)
    metadata, _ = v9.load_bundle(incremental)
    records = []
    for task in v9.CORE_TASKS:
        before, after = [frame[f"pred_{task}"].to_numpy() for frame in scores]
        records.append({"task": task, "n": len(y),
                        "rmse_original": float(np.sqrt(np.mean((y-before)**2))),
                        "rmse_incremental": float(np.sqrt(np.mean((y-after)**2))),
                        "processor": metadata["tasks"][task]["postprocessor"],
                        **v9.grouped_gain(y, before, after, groups, repetitions=1000)})
    output.mkdir(parents=True, exist_ok=True)
    v9.v6.json_write(output / "comparacion.json", records)
    lines = ["# Validación incremental de arsenal y entorno", "",
             f"Mismos {len(y):,} pitches, target y presupuesto de {protocols[0]['iterations']} iteraciones. "
             "2026 es un benchmark reutilizado; esto no es una evaluación nueva e independiente.", "",
             "| Capa | RMSE original | RMSE incremental | Reducción MSE | IC 95% por juegos |",
             "|---|---:|---:|---:|---:|"]
    for row in records:
        lines.append(f"| {row['task']} | {row['rmse_original']:.6f} | {row['rmse_incremental']:.6f} | "
                     f"{row['gain']:.3%} | [{row['ci_low']:.3%}, {row['ci_high']:.3%}] |")
    lines += ["", "Las diferencias se calculan sobre predicciones de carreras, no sobre índices con referencias distintas. "
              "Una reducción positiva favorece el nuevo método. Los intervalos describen este benchmark y no corrigen su reutilización.", "",
              "## Decisiones congeladas en desarrollo", ""]
    for task in v9.PARENTS:
        item = metadata["tasks"][task]
        lines.append(f"- `{task}`: `{item['postprocessor']}`; control: `{item['selection']['control_task']}`.")
    lines += ["", "Si entorno hereda la capa anterior, su delta de carreras es cero por construcción. "
              "No equivale a demostrar que no existe un efecto físico de altitud. Los clasificadores contextuales "
              "siguen siendo independientes. Esta ejecución no incorpora una nueva auditoría por pitcher o parque.", "",
              "[Explicación completa](../../docs/guias/PROJECT_APPROACH.md)"]
    (output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output / "README.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, default=Path("stuff_plus_output_v9"))
    parser.add_argument("--incremental", type=Path, default=Path("stuff_plus_output_v9_incremental"))
    parser.add_argument("--output", type=Path, default=Path("reports/v9_incremental"))
    parser.add_argument("--parquet", type=Path)
    args = parser.parse_args()
    compare(args.original, args.incremental, args.output, args.parquet)
