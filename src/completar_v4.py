"""Completa v4: entrena modelos restantes, genera scores, SHAP y entregables."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, CatBoostRegressor

try:
    import shap
except ImportError:
    shap = None

from entrenar_stuff_plus_v4 import (
    load_data, prepare_features, task_frame, TASKS, CATEGORICAL_FEATURES,
    ALTITUD_METROS, ALTITUD_ESTADIO_REPRESENTATIVO,
    add_provisional_scores, agregar_por_pitcher, perfil_ideal_diablos,
    compute_shap_values, shap_by_altitude, make_model,
)


def fit_remaining_models(frame, args):
    output = args.salida
    model_dir = output / "modelos"
    model_dir.mkdir(parents=True, exist_ok=True)
    for task_name, task in TASKS.items():
        model_path = model_dir / f"{task_name}.cbm"
        if model_path.exists():
            print(f"Ya existe: {task_name}")
            continue
        fit_rows = task_frame(frame, task)
        features = task["features"]
        x_fit = prepare_features(fit_rows, features)
        y_fit = fit_rows[task["target"]].astype(float)
        cat_feats = [c for c in features if c in CATEGORICAL_FEATURES]
        model = make_model(task, args)
        model.fit(x_fit, y_fit, cat_features=cat_feats)
        model.save_model(str(model_path))
        print(f"  Modelo final: {task_name} ({len(fit_rows):,} filas)")


def generate_oos_scores(frame, args):
    """Genera scores fuera de muestra usando splits ya definidos."""
    from entrenar_stuff_plus_v4 import make_splits, fit_and_measure, predict_task

    splits = list(
        make_splits(
            frame,
            include_pitcher=True,
            include_game=False,
            include_park=True,
            seed=args.semilla,
        )
    )
    oos_frames = {}
    for split_name, split_train, split_test in splits:
        split_test = split_test.reset_index(drop=True)
        print(f"Scores OOS {split_name}: train={len(split_train):,}, test={len(split_test):,}")
        for task_name, task in TASKS.items():
            model_path = args.salida / "modelos" / f"{task_name}.cbm"
            if not model_path.exists():
                continue
            if task["kind"] == "classification":
                model = CatBoostClassifier()
            else:
                model = CatBoostRegressor()
            model.load_model(str(model_path))
            test_rows = task_frame(split_test, task)
            if len(test_rows) == 0:
                continue
            preds = predict_task(model, task, test_rows)
            if split_name not in oos_frames:
                oos_frames[split_name] = split_test[
                    ["PitchUID", "year", "pitcher_anon_id", "altitude_category", "AutoPitchType"]
                ].copy()
            col = f"pred_{task_name}" if task["kind"] == "regression" else f"p_{task_name}"
            full_col = np.full(len(split_test), np.nan, dtype=float)
            full_col[test_rows.index] = preds
            oos_frames[split_name][col] = full_col

    if not oos_frames:
        print("No hay frames OOS.")
        return None

    predictions = pd.concat(oos_frames.values(), ignore_index=True)
    predictions = add_provisional_scores(predictions, frame)
    scores_path = args.salida / "scores_pitch_v4.parquet"
    con = duckdb.connect()
    try:
        con.register("scores_df", predictions)
        escaped = str(scores_path.resolve()).replace("'", "''")
        con.execute(f"COPY scores_df TO '{escaped}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    finally:
        con.close()
    print(f"Scores OOS guardados en {scores_path} ({len(predictions):,} filas)")
    return scores_path


def compute_all_shap(frame, args):
    if shap is None:
        print("SHAP no instalado.")
        return
    model_dir = args.salida / "modelos"
    shap_sample = frame.sample(min(3000, len(frame)), random_state=args.semilla)
    for task_name, task in TASKS.items():
        model_path = model_dir / f"{task_name}.cbm"
        if not model_path.exists():
            continue
        if task["kind"] == "classification":
            model = CatBoostClassifier()
        else:
            model = CatBoostRegressor()
        model.load_model(str(model_path))
        compute_shap_values(model, task, shap_sample, args, args.salida)
        shap_by_altitude(model, task, frame, args.salida)
    print("SHAP completado.")


def main():
    args = type("A", (), {
        "iteraciones": 40, "profundidad": 5, "semilla": 42,
        "salida": Path("stuff_plus_output_v4"),
        "omitir_shap": False,
    })()
    args.salida.mkdir(parents=True, exist_ok=True)

    print("Cargando datos ...")
    frame = load_data(Path("stuff_model_df.parquet"))
    print(f"{len(frame):,} lanzamientos")

    print("Entrenando modelos restantes ...")
    fit_remaining_models(frame, args)

    print("Generando scores OOS ...")
    scores_path = generate_oos_scores(frame, args)

    if scores_path:
        print("Generando entregables ...")
        agregar_por_pitcher(scores_path, args.salida)
        perfil_ideal_diablos(scores_path, args.salida)

    print("Computando SHAP ...")
    compute_all_shap(frame, args)

    print("Listo.")


if __name__ == "__main__":
    main()
