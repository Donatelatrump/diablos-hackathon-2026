"""Mejoras selectivas v6 elegidas con 2025 y evaluadas una vez en 2026.

2026 es un benchmark reutilizado despues de v5, no un test nunca observado.
No se modifica el target ni los artefactos de v5. Ver docs/archivo/README_MODELO_V6.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, CatBoostRegressor
from sklearn.metrics import mean_squared_error

import entrenar_stuff_plus_v5 as base

EXTRA_RAW = ["pfxx", "pfxz", "vx0", "vy0", "vz0", "ax0", "ay0", "az0"]
SHAPE_DERIVED = [
    "hb_arm_side", "release_side_arm_side", "movement_magnitude", "movement_angle_sin",
    "movement_angle_cos", "spin_per_mph", "effective_speed_delta", "extension_per_height",
    "spin_axis_sin2", "spin_axis_cos2",
]
AERO_DERIVED = ["pfxx_arm_side", "pfxz", "drag_proxy", "lift_vertical_proxy",
                "lift_horizontal_arm_side_proxy", "lift_magnitude_proxy", "movement_per_spin"]
PHYSICAL = base.PHYSICAL + SHAPE_DERIVED + AERO_DERIVED
TASKS = {
    "whiff": ("is_whiff", PHYSICAL, None, "classification"),
    "whiff_given_swing": ("is_whiff", PHYSICAL, "swing", "classification"),
    "exit_speed_given_in_play": ("ExitSpeed", PHYSICAL, "exit", "regression"),
    "stuff_run_value": ("run_value_proxy", PHYSICAL, None, "regression"),
    "environment_run_value": ("run_value_proxy", PHYSICAL + ["PlateLocHeight", "PlateLocSide", "Balls", "Strikes", "BatterSide", "altitude_category"], None, "regression"),
    "exit_speed_contextual": ("ExitSpeed", base.LOCATION + SHAPE_DERIVED, "exit", "regression"),
}
CONFIGS = {
    "regularized": {"depth": 5, "iterations": 400, "l2_leaf_reg": 15., "learning_rate": .05, "random_seed": 91},
    "deep": {"depth": 7, "iterations": 500, "l2_leaf_reg": 20., "learning_rate": .045, "random_seed": 137},
}
MIN_DEVELOPMENT_GAIN = .001
SCORE_COLUMNS = ["stuff_plus", "location_plus", "pitching_plus"]
IDENTITY = ["PitchUID", "year", "game_anon_id", "pitcher_anon_id", "AutoPitchType", "altitude_category"]


def json_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def numeric(frame, column):
    if column not in frame:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan)


def enhance(frame):
    """Solo mediciones fisicas. No utiliza outcomes, plato, conteo ni altitud.

    Las fuerzas son proxies calculados con el ajuste de trayectoria, no medidas
    de Magnus ni de eficiencia real del spin. z positivo hacia arriba; ft/s^2.
    """
    x = frame.copy()
    hand = x["PitcherThrows"].map({"Right": 1., "Left": -1.})
    hb, ivb = numeric(x, "HorzBreak"), numeric(x, "InducedVertBreak")
    magnitude = np.hypot(hb, ivb)
    spin, velo = numeric(x, "SpinRate"), numeric(x, "RelSpeed")
    axis = np.deg2rad(numeric(x, "SpinAxis"))
    x["hb_arm_side"] = hb * hand
    x["release_side_arm_side"] = numeric(x, "RelSide") * hand
    x["movement_magnitude"] = magnitude
    x["movement_angle_sin"] = hb / magnitude.replace(0, np.nan)
    x["movement_angle_cos"] = ivb / magnitude.replace(0, np.nan)
    x["spin_per_mph"] = spin / velo.replace(0, np.nan)
    x["effective_speed_delta"] = numeric(x, "EffectiveVelo") - velo
    x["extension_per_height"] = numeric(x, "Extension") / numeric(x, "RelHeight").replace(0, np.nan)
    x["spin_axis_sin2"], x["spin_axis_cos2"] = np.sin(2 * axis), np.cos(2 * axis)
    x["pfxx_arm_side"] = numeric(x, "pfxx") * hand
    # Restar gravedad de la aceleracion observada, despues separar proyeccion
    # paralela a velocidad y componente perpendicular. Sin reconstruir plato.
    velocity = np.column_stack([numeric(x, c) for c in ["vx0", "vy0", "vz0"]])
    acceleration = np.column_stack([numeric(x, c) for c in ["ax0", "ay0", "az0"]])
    acceleration[:, 2] += 32.174
    norm = np.linalg.norm(velocity, axis=1)
    norm = np.where(norm > 1e-8, norm, np.nan)
    unit = velocity / norm[:, None]
    parallel = np.sum(acceleration * unit, axis=1)
    transverse = acceleration - parallel[:, None] * unit
    x["drag_proxy"] = -parallel
    x["lift_vertical_proxy"] = transverse[:, 2]
    x["lift_horizontal_arm_side_proxy"] = transverse[:, 0] * hand.to_numpy()
    x["lift_magnitude_proxy"] = np.linalg.norm(transverse, axis=1)
    x["movement_per_spin"] = np.hypot(numeric(x, "pfxx"), numeric(x, "pfxz")) / spin.replace(0, np.nan) * 1000.
    extra = np.column_stack([numeric(x, c) for c in EXTRA_RAW])
    x["enhancement_available"] = np.isfinite(extra).all(axis=1) & np.isfinite(norm)
    return x


def features(frame, columns):
    # Seleccionar antes de copiar evita duplicar el dataset completo por modelo.
    needed = list(dict.fromkeys([*columns, "SpinAxis"]))
    x = frame[[c for c in needed if c in frame]].copy()
    return base.features(x, columns)


def available(frame, name):
    if name == "exit_speed_contextual":
        return pd.Series(True, index=frame.index)
    return frame["enhancement_available"].astype(bool)


def task_mask(frame, name):
    return base.eligible(frame, TASKS[name]) & available(frame, name)


def base_column(name):
    if name == "exit_speed_contextual":
        return "pred_exit_speed_given_in_play"
    return base.prediction_column(name, TASKS[name])


def predict(model, spec, frame):
    x = features(frame, spec[1])
    if spec[3] == "classification":
        return model.predict_proba(x)[:, list(model.classes_).index(1)]
    return np.asarray(model.predict(x), dtype=float)


def base_predictions(prepared, bundle):
    metadata, models = bundle
    result = prepared[[c for c in IDENTITY if c in prepared]].copy().reset_index(drop=True)
    for name, model in models.items():
        task = metadata["tasks"][name]
        spec = (task["target"], task["features"], None, task["kind"])
        result[base.prediction_column(name, spec)] = task["alpha"] * base.predict(model, spec, prepared) + (1 - task["alpha"]) * task["prior"]
    return result


def choose_mix(y, baseline, predictions, min_gain=MIN_DEVELOPMENT_GAIN):
    """Seleccion por error propio sobre 2025; nunca recibe 2026."""
    y = np.asarray(y, dtype=float)
    baseline = np.asarray(baseline, dtype=float)
    baseline_error = float(mean_squared_error(y, baseline))
    options = {"regularized": ["regularized"], "deep": ["deep"], "ensemble": ["regularized", "deep"]}
    best = {"members": [], "weight": 0., "mse": baseline_error, "relative_gain": 0.}
    trials = []
    for label, members in options.items():
        candidate = np.mean([predictions[m] for m in members], axis=0)
        for weight in [.25, .5, .75, 1.]:
            error = float(mean_squared_error(y, weight * candidate + (1 - weight) * baseline))
            gain = 1 - error / baseline_error if baseline_error else 0.
            row = {"candidate": label, "members": members, "weight": weight, "mse": error, "relative_gain": gain}
            trials.append(row)
            if gain >= min_gain and error < best["mse"]:
                best = dict(row)
    return best, trials


def fit_candidate(fit, valid, name, config, args):
    spec = TASKS[name]
    train = fit.loc[task_mask(fit, name)]
    calibration = valid.loc[task_mask(valid, name)]
    cls = CatBoostClassifier if spec[3] == "classification" else CatBoostRegressor
    model = cls(loss_function="Logloss" if spec[3] == "classification" else "RMSE",
                **CONFIGS[config], thread_count=args.hilos, verbose=False, allow_writing_files=False)
    model.fit(features(train, spec[1]), train[spec[0]],
              cat_features=[c for c in spec[1] if c in base.CATEGORICAL],
              eval_set=(features(calibration, spec[1]), calibration[spec[0]]),
              early_stopping_rounds=35, use_best_model=True)
    return model


def read_seasons(path, maximum):
    with duckdb.connect() as con:
        return con.execute("SELECT * FROM read_parquet(?) WHERE year <= ?", [str(path), int(maximum)]).fetchdf()


def select(args):
    protocol_path = args.salida / "protocolo_congelado.json"
    if protocol_path.exists():
        raise FileExistsError("La seleccion ya esta congelada. Usar --fase evaluar o una salida nueva.")
    source_hash = file_hash(args.parquet)
    old_manifest = json.loads((args.base / "manifest.json").read_text(encoding="utf-8"))
    if source_hash != old_manifest["source_sha256"] or file_hash(base.__file__) != old_manifest["script_sha256"]:
        raise ValueError("El origen o el codigo de v5 no coincide con sus artefactos")
    print("Seleccion: leyendo exclusivamente 2024 y 2025", flush=True)
    raw = base.prepare_raw(read_seasons(args.parquet, 2025))
    frame = enhance(base.historical_features(raw))
    fit, valid = base.group_partition(frame.loc[frame.year.eq(2024)], 42)
    development = frame.loc[frame.year.eq(2025)].copy().reset_index(drop=True)
    baseline = base_predictions(development, base.load_bundle(args.base / "holdout_2025"))
    selections = {}
    for name, spec in TASKS.items():
        mask = task_mask(development, name).to_numpy()
        rows = development.loc[mask]
        candidate_predictions = {}
        diagnostics = {}
        for config in CONFIGS:
            print(f"Seleccion {name}/{config}", flush=True)
            model = fit_candidate(fit, valid, name, config, args)
            candidate_predictions[config] = predict(model, spec, rows)
            path = args.salida / "desarrollo_2025" / "modelos" / f"{name}_{config}.cbm"
            path.parent.mkdir(parents=True, exist_ok=True)
            model.save_model(str(path))
            diagnostics[config] = {"trees": model.tree_count_, "config": CONFIGS[config]}
        chosen, trials = choose_mix(rows[spec[0]], baseline.loc[mask, base_column(name)], candidate_predictions)
        selections[name] = {"chosen": chosen, "trials": trials, "candidates": diagnostics,
                            "n_development": len(rows), "target": spec[0], "features": spec[1], "kind": spec[3]}
        json_write(args.salida / "desarrollo_2025" / f"seleccion_{name}.json", selections[name])
        print(json.dumps({"task": name, "selection": chosen}), flush=True)
    protocol = {"version": 6, "selection_year": 2025, "benchmark_year": 2026,
                "benchmark_previously_seen_in_v5": True, "development_reads_years_at_most": 2025,
                "script_sha256": file_hash(__file__), "v5_script_sha256": file_hash(base.__file__),
                "source_sha256": source_hash, "base_manifest_sha256": file_hash(args.base / "manifest.json"),
                "threads": args.hilos,
                "partition_seed": 42, "configs": CONFIGS, "minimum_relative_development_gain": MIN_DEVELOPMENT_GAIN,
                "tasks": selections}
    json_write(protocol_path, protocol)
    print("Protocolo congelado. 2026 no participo en la seleccion.", flush=True)


def apply_overlays(prepared, baseline, selections, models):
    result = baseline.copy()
    for name, task in selections.items():
        chosen = task["chosen"]
        col = base.prediction_column(name, TASKS[name])
        result[col] = baseline[base_column(name)].to_numpy()
        if chosen["weight"] > 0:
            mask = available(prepared, name).to_numpy()
            if mask.any():
                candidate = np.mean([predict(models[(name, member)], TASKS[name], prepared.loc[mask]) for member in chosen["members"]], axis=0)
                result.loc[mask, col] = chosen["weight"] * candidate + (1 - chosen["weight"]) * result.loc[mask, col].to_numpy()
    return result


def load_bundle(path):
    path = Path(path)
    metadata = json.loads((path / "bundle.json").read_text(encoding="utf-8"))
    baseline = base.load_bundle(path / "base_v5")
    models = {}
    for name, task in metadata["tasks"].items():
        cls = CatBoostClassifier if TASKS[name][3] == "classification" else CatBoostRegressor
        for member in task["chosen"]["members"]:
            model = cls()
            model.load_model(str(path / "modelos" / f"{name}_{member}.cbm"))
            models[(name, member)] = model
    return metadata, baseline, models


def infer(frame, bundle):
    metadata, baseline_bundle, models = bundle
    prepared = enhance(base.apply_profile(frame, baseline_bundle[0]["profile"]))
    baseline = base_predictions(prepared, baseline_bundle)
    result = base.add_scores(apply_overlays(prepared, baseline, metadata["tasks"], models), metadata["reference"])
    result["enhancement_available"] = prepared["enhancement_available"].to_numpy()
    result["score_reference_id"] = "v6_reference"
    missing = ~result.enhancement_available
    if missing.any():
        original = base.add_scores(baseline, baseline_bundle[0]["reference"])
        result.loc[missing, SCORE_COLUMNS] = original.loc[missing, SCORE_COLUMNS]
        result.loc[missing, "score_reference_id"] = "v5_fallback"
    return result


def game_bootstrap_comparison(frame, y, old, new, repetitions=1000, seed=6026):
    """IC pareado por juegos para reduccion de MSE/Brier, no por pitches iid."""
    table = pd.DataFrame({"game": frame["game_anon_id"].astype(str).to_numpy(),
                          "old_error": (np.asarray(y) - np.asarray(old)) ** 2,
                          "new_error": (np.asarray(y) - np.asarray(new)) ** 2})
    grouped = table.groupby("game")[["old_error", "new_error"]].sum()
    n = len(grouped)
    counts = np.random.default_rng(seed).multinomial(n, np.full(n, 1 / n), size=repetitions)
    old_sum = counts @ grouped.old_error.to_numpy()
    new_sum = counts @ grouped.new_error.to_numpy()
    gain = 1 - new_sum / old_sum
    low, high = np.quantile(gain, [.025, .975])
    return {"relative_mse_reduction": float(1 - table.new_error.sum() / table.old_error.sum()),
            "ci95_low": float(low), "ci95_high": float(high), "n_games": n, "bootstrap_repetitions": repetitions}


def evaluate(args):
    protocol_path = args.salida / "protocolo_congelado.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    for actual, expected, label in [(file_hash(__file__), protocol["script_sha256"], "script"),
                                     (file_hash(base.__file__), protocol["v5_script_sha256"], "v5"),
                                     (file_hash(args.parquet), protocol["source_sha256"], "origen"),
                                     (file_hash(args.base / "manifest.json"), protocol["base_manifest_sha256"], "manifest v5")]:
        if actual != expected:
            raise ValueError(f"Cambio {label} despues de congelar la seleccion")
    if (args.salida / "metricas_benchmark_2026.json").exists():
        raise FileExistsError("Benchmark ya evaluado; no se permite reoptimizar contra 2026.")
    raw = base.prepare_raw(read_seasons(args.parquet, 2026))
    prepared = enhance(base.historical_features(raw))
    history = prepared.loc[prepared.year.lt(2026)]
    fit, valid = base.group_partition(history, 42)
    test = prepared.loc[prepared.year.eq(2026)].copy().reset_index(drop=True)
    baseline_bundle = base.load_bundle(args.base / "holdout_2026")
    # Misma particion que v5 para que la comparacion no dependa de nuevos juegos.
    for name, rows in [("fit", fit), ("validacion", valid)]:
        old_ids = base.read_parquet(args.base / "holdout_2026" / f"filas_{name}.parquet")
        if set(old_ids.PitchUID) != set(rows.PitchUID):
            raise ValueError("La particion de v5 y v6 no coincide")
    baseline_test = base_predictions(test, baseline_bundle)
    baseline_valid = base_predictions(valid, baseline_bundle)
    model_dir = args.salida / "modelos"
    model_dir.mkdir(parents=True, exist_ok=True)
    models = {}
    for name, task in protocol["tasks"].items():
        for member in task["chosen"]["members"]:
            print(f"Entrenamiento final {name}/{member}", flush=True)
            model = fit_candidate(fit, valid, name, member, args)
            model.save_model(str(model_dir / f"{name}_{member}.cbm"))
            models[(name, member)] = model
    predictions = apply_overlays(test, baseline_test, protocol["tasks"], models)
    reference_predictions = apply_overlays(valid.reset_index(drop=True), baseline_valid, protocol["tasks"], models)
    reference = base.fit_reference(reference_predictions)
    scores = base.add_scores(predictions, reference)
    scores["enhancement_available"] = test.enhancement_available.to_numpy()
    scores["score_reference_id"] = "v6_reference"
    missing = ~scores.enhancement_available
    if missing.any():
        fallback = base.add_scores(baseline_test, baseline_bundle[0]["reference"])
        scores.loc[missing, SCORE_COLUMNS] = fallback.loc[missing, SCORE_COLUMNS]
        scores.loc[missing, "score_reference_id"] = "v5_fallback"
    scores["model_id"] = "v6_frozen_on_2025"
    scores["prediction_kind"] = "reused_temporal_benchmark_2026"
    scores["training_max_year"] = 2025
    for name in TASKS:
        scores[f"base_{base.prediction_column(name, TASKS[name])}"] = baseline_test[base_column(name)].to_numpy()
    if scores.PitchUID.duplicated().any() or not np.isfinite(scores[SCORE_COLUMNS].to_numpy()).all():
        raise ValueError("Scores duplicados o incompletos")
    base.write_parquet(scores, args.salida / "scores_pitch_v6.parquet")
    snapshots = args.salida / "base_v5"
    snapshots.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.base / "holdout_2026" / "bundle.json", snapshots / "bundle.json")
    shutil.copytree(args.base / "holdout_2026" / "modelos", snapshots / "modelos", dirs_exist_ok=True)
    model_hashes = {str(p.relative_to(args.salida)).replace('\\', '/'): file_hash(p) for p in args.salida.glob("modelos/*.cbm")}
    model_hashes.update({str(p.relative_to(args.salida)).replace('\\', '/'): file_hash(p) for p in snapshots.glob("modelos/*.cbm")})
    metadata = {"version": 6, "training_max_year": 2025, "benchmark_year": 2026,
                "benchmark_previously_seen_in_v5": True, "tasks": protocol["tasks"], "reference": reference,
                "protocol_sha256": file_hash(protocol_path), "script_sha256": file_hash(__file__),
                "base_bundle_sha256": file_hash(snapshots / "bundle.json"), "model_hashes": model_hashes,
                "source_sha256": protocol["source_sha256"], "extra_measurements": EXTRA_RAW}
    json_write(args.salida / "bundle.json", metadata)
    records = []
    for name, spec in TASKS.items():
        # Evaluar todos los targets observados, incluyendo fallback si falta fisica.
        mask = base.eligible(test, spec).to_numpy()
        rows = test.loc[mask]
        old = baseline_test.loc[mask, base_column(name)].to_numpy()
        new = predictions.loc[mask, base.prediction_column(name, spec)].to_numpy()
        train_y = fit.loc[base.eligible(fit, spec), spec[0]]
        record = {"task": name, "n_test": len(rows), "selection": protocol["tasks"][name]["chosen"],
                  "v5": base.metrics(rows[spec[0]], old, train_y, spec[3]),
                  "v6": base.metrics(rows[spec[0]], new, train_y, spec[3]),
                  "paired_game_bootstrap": game_bootstrap_comparison(rows, rows[spec[0]], old, new)}
        if spec[0] == "run_value_proxy":
            by_count = base.count_baseline(fit, rows)
            record["v6"].update(base.metrics(rows[spec[0]], new, train_y, spec[3], by_count))
        records.append(record)
        print(json.dumps(record), flush=True)
    base.write_parquet(fit[["PitchUID", "year", "game_anon_id"]], args.salida / "filas_fit.parquet")
    base.write_parquet(valid[["PitchUID", "year", "game_anon_id"]], args.salida / "filas_validacion.parquet")
    # Este archivo es el cierre de evaluacion y bloquea otra optimizacion del benchmark.
    json_write(args.salida / "metricas_benchmark_2026.json", records)
    print(f"v6 completa: {len(scores):,} scores y comparacion pareada por juegos", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fase", choices=["seleccionar", "evaluar", "todo"], default="todo")
    parser.add_argument("--parquet", type=Path, default=Path("stuff_model_df.parquet"))
    parser.add_argument("--base", type=Path, default=Path("stuff_plus_output_v5"))
    parser.add_argument("--salida", type=Path, default=Path("stuff_plus_output_v6"))
    parser.add_argument("--hilos", type=int, default=6)
    args = parser.parse_args()
    if args.hilos < 1:
        parser.error("--hilos debe ser positivo")
    args.salida.mkdir(parents=True, exist_ok=True)
    if args.fase in ["seleccionar", "todo"]:
        select(args)
    if args.fase in ["evaluar", "todo"]:
        evaluate(args)


if __name__ == "__main__":
    main()
