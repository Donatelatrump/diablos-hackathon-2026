"""v7: calibracion separada y compuesto fisico aprendido con predicciones OOF.

Los modelos de componentes no ven los outcomes de su juego al generar OOF.
2026 ya se observo en versiones anteriores y es un benchmark reutilizado.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, CatBoostRegressor
from scipy.optimize import lsq_linear
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, mean_squared_error

import entrenar_stuff_plus_v5 as v5
import entrenar_stuff_plus_v6 as v6

SEED = 742
FOLDS = 3
CALIBRATION_TASKS = ["whiff", "whiff_given_swing"]
COMPONENTS = {
    "whiff": ("is_whiff", v6.PHYSICAL, None, "classification"),
    "whiff_given_swing": ("is_whiff", v6.PHYSICAL, "swing", "classification"),
    "ball_in_play": ("is_ball_in_play", v6.PHYSICAL, None, "classification"),
    "groundball_given_in_play": ("is_groundball", v6.PHYSICAL, "hit_type", "classification"),
    "home_run_per_pitch": ("home_run", v6.PHYSICAL, None, "classification"),
    "exit_speed_given_in_play": ("ExitSpeed", v6.PHYSICAL, "exit", "regression"),
    "physical_control": ("run_value_proxy", v5.PHYSICAL, None, "regression"),
}
STACK_COLUMNS = ["p_whiff", "p_whiff_given_swing", "p_ball_in_play", "p_groundball_per_pitch",
                 "p_home_run_per_pitch", "pred_exit_speed_given_in_play", "expected_exit_speed_per_pitch",
                 "pred_physical_control"]
# Restricciones en valor de carreras: whiff y rodado son favorables; HR, EV y
# prediccion de carreras directa son desfavorables, manteniendo otros inputs fijos.
LOWER_BOUNDS = [-np.inf, -np.inf, -np.inf, -np.inf, 0., 0., 0., 0.]
UPPER_BOUNDS = [0., 0., np.inf, 0., np.inf, np.inf, np.inf, np.inf]
ALPHAS = [10., 1000., 100000.]
MIX_WEIGHTS = [.25, .5, .75, 1.]


def partition_games(frame):
    """60% ajuste, 10% parada, 15% calibracion, 15% seleccion por temporada."""
    result = frame.copy().reset_index(drop=True)
    if result.year.ge(2026).any():
        raise ValueError("El desarrollo no puede incluir 2026")
    result["partition"] = ""
    result["oof_fold"] = -1
    for year in sorted(result.year.unique()):
        games = np.array(sorted(result.loc[result.year.eq(year), "game_anon_id"].astype(str).unique()))
        if len(games) < 20:
            raise ValueError("Se requieren al menos veinte juegos por temporada")
        shuffled = np.random.default_rng(SEED + int(year)).permutation(games)
        n_fit, n_stop, n_cal = int(len(games) * .60), int(len(games) * .10), int(len(games) * .15)
        parts = {"fit": shuffled[:n_fit], "early_stop": shuffled[n_fit:n_fit+n_stop],
                 "calibration": shuffled[n_fit+n_stop:n_fit+n_stop+n_cal],
                 "selection": shuffled[n_fit+n_stop+n_cal:]}
        for name, ids in parts.items():
            mask = result.year.eq(year) & result.game_anon_id.astype(str).isin(ids)
            result.loc[mask, "partition"] = name
        for fold in range(FOLDS):
            ids = shuffled[:n_fit][fold::FOLDS]
            mask = result.year.eq(year) & result.game_anon_id.astype(str).isin(ids)
            result.loc[mask, "oof_fold"] = fold
    if result.partition.eq("").any():
        raise ValueError("Filas sin particion")
    return result


def component_column(name):
    return v5.prediction_column(name, COMPONENTS[name])


def config_for(name, fold):
    if name in CALIBRATION_TASKS:
        return dict(iterations=400, depth=7, learning_rate=.05, l2_leaf_reg=20., random_seed=719+fold)
    if name == "physical_control":
        return dict(iterations=250, depth=6, learning_rate=.06, l2_leaf_reg=8., random_seed=42+fold)
    return dict(iterations=220, depth=5, learning_rate=.06, l2_leaf_reg=12., random_seed=719+fold)


def fit_component(fit, stop, name, fold, threads):
    spec = COMPONENTS[name]
    train = fit.loc[v5.eligible(fit, spec)]
    valid = stop.loc[v5.eligible(stop, spec)]
    cls = CatBoostClassifier if spec[3] == "classification" else CatBoostRegressor
    model = cls(loss_function="Logloss" if spec[3] == "classification" else "RMSE",
                **config_for(name, fold), thread_count=threads, allow_writing_files=False, verbose=False)
    model.fit(v6.features(train, spec[1]), train[spec[0]],
              cat_features=[c for c in spec[1] if c in v5.CATEGORICAL],
              eval_set=(v6.features(valid, spec[1]), valid[spec[0]]),
              early_stopping_rounds=30, use_best_model=True)
    return model


def predict_components(frame, models):
    result = pd.DataFrame(index=range(len(frame)))
    for name, model in models.items():
        result[component_column(name)] = v6.predict(model, COMPONENTS[name], frame)
    return result


def ece_quantile(y, probability, bins=10):
    y, probability = np.asarray(y), np.asarray(probability)
    edges = np.unique(np.quantile(probability, np.linspace(0, 1, bins+1)))
    ids = np.searchsorted(edges[1:-1], probability, side="right")
    return float(sum(np.mean(ids == b) * abs(probability[ids == b].mean() - y[ids == b].mean())
                     for b in np.unique(ids)))


def probability_metrics(y, probability, fit_y):
    row = v5.metrics(y, probability, fit_y, "classification")
    row["log_loss"] = float(log_loss(y, np.clip(probability, 1e-6, 1-1e-6), labels=[0, 1]))
    row["ece_quantile_10"] = ece_quantile(y, probability)
    return row


def apply_calibrator(probability, calibrator):
    p = np.clip(np.asarray(probability, dtype=float), 1e-6, 1-1e-6)
    if calibrator["method"] == "identity":
        return np.asarray(probability, dtype=float).copy()
    if calibrator["method"] == "sigmoid":
        z = calibrator["slope"] * np.log(p / (1-p)) + calibrator["intercept"]
        return np.clip(1 / (1 + np.exp(-np.clip(z, -40, 40))), 1e-6, 1-1e-6)
    if calibrator["method"] == "isotonic":
        return np.clip(np.interp(p, calibrator["x"], calibrator["y"]), 1e-6, 1-1e-6)
    raise ValueError("Calibrador desconocido")


def fit_calibrators(y, probability):
    y, p = np.asarray(y, dtype=float), np.clip(np.asarray(probability, dtype=float), 1e-6, 1-1e-6)
    if len(np.unique(y)) != 2:
        raise ValueError("La calibracion requiere ambas clases")
    sigmoid = LogisticRegression(C=1000., solver="lbfgs", max_iter=500)
    sigmoid.fit(np.log(p / (1-p)).reshape(-1, 1), y)
    slope = float(sigmoid.coef_[0, 0])
    # La calibracion no debe invertir el orden del clasificador.
    sig_meta = {"method": "sigmoid", "slope": slope, "intercept": float(sigmoid.intercept_[0])} if slope > 0 else {"method": "identity"}
    isotonic = IsotonicRegression(y_min=1e-6, y_max=1-1e-6, increasing=True, out_of_bounds="clip").fit(p, y)
    return {"identity": {"method": "identity"}, "sigmoid": sig_meta,
            "isotonic": {"method": "isotonic", "x": isotonic.X_thresholds_.tolist(), "y": isotonic.y_thresholds_.tolist()}}


def select_calibrator(y, probability, fit_y, candidates):
    raw = probability_metrics(y, probability, fit_y)
    records = {}
    selected = "identity"
    best = raw["brier"]
    for name, calibrator in candidates.items():
        metrics = probability_metrics(y, apply_calibrator(probability, calibrator), fit_y)
        required = max(.0005, raw["ece_10_bins"] * .10)
        eligible = (name != "identity" and metrics["brier"] <= raw["brier"] * 1.001
                    and metrics["log_loss"] <= raw["log_loss"] * 1.0015
                    and metrics["ece_10_bins"] <= raw["ece_10_bins"] - required
                    and metrics["ece_quantile_10"] <= raw["ece_quantile_10"] * 1.05 + .0005)
        records[name] = {"metrics": metrics, "eligible": eligible}
        if eligible and (selected == "identity" or metrics["brier"] < best):
            selected, best = name, metrics["brier"]
    return {"selected": selected, "calibrator": candidates[selected], "candidates": candidates, "selection_metrics": records}


def stack_features(predictions, calibrations, use_calibrated):
    x = predictions.copy()
    if use_calibrated:
        for name in CALIBRATION_TASKS:
            col = component_column(name)
            x[col] = apply_calibrator(x[col], calibrations[name]["calibrator"])
    x["p_groundball_per_pitch"] = x.p_ball_in_play * x.p_groundball_given_in_play
    x["expected_exit_speed_per_pitch"] = x.p_ball_in_play * x.pred_exit_speed_given_in_play
    result = x[STACK_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(result).all():
        raise ValueError("Componentes incompletos en el compuesto")
    return result


def fit_stack(x, y, alpha):
    """Ridge con restricciones de signo y estadisticas solo de las filas OOF."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale = np.where(scale > 1e-10, scale, 1.)
    z = (x - mean) / scale
    intercept = float(y.mean())
    gram = z.T @ z + alpha * np.eye(z.shape[1])
    rhs = z.T @ (y - intercept)
    cholesky = np.linalg.cholesky(gram)
    solution = lsq_linear(cholesky.T, np.linalg.solve(cholesky, rhs), bounds=(LOWER_BOUNDS, UPPER_BOUNDS), tol=1e-10, max_iter=1000)
    if not solution.success:
        raise RuntimeError("No convergio el compuesto regularizado")
    return {"columns": STACK_COLUMNS, "mean": mean.tolist(), "scale": scale.tolist(),
            "coef": solution.x.tolist(), "intercept": intercept, "alpha": float(alpha), "bounded": True}


def predict_stack(x, metadata):
    z = (np.asarray(x) - np.asarray(metadata["mean"])) / np.asarray(metadata["scale"])
    return z @ np.asarray(metadata["coef"]) + metadata["intercept"]


def select_stack(oof, fit_y, selection_predictions, selection_y, calibrations, calibrated_oof=None):
    control = selection_predictions.pred_physical_control.to_numpy()
    baseline_error = float(mean_squared_error(selection_y, control))
    records, best, best_error = [], None, np.inf
    for calibrated in [False, True]:
        train_x = (stack_features(calibrated_oof, calibrations, False) if calibrated and calibrated_oof is not None
                   else stack_features(oof, calibrations, calibrated))
        valid_x = stack_features(selection_predictions, calibrations, calibrated)
        for alpha in ALPHAS:
            model = fit_stack(train_x, fit_y, alpha)
            prediction = predict_stack(valid_x, model)
            for weight in MIX_WEIGHTS:
                blended = weight * prediction + (1-weight) * control
                error = float(mean_squared_error(selection_y, blended))
                row = {"use_calibrated": calibrated, "alpha": alpha, "weight": weight,
                       "mse": error, "relative_gain": 1-error/baseline_error}
                records.append(row)
                if error < best_error:
                    best_error = error
                    best = {**row, "model": model}
    best["promoted"] = bool(best["relative_gain"] >= .001)
    best["deployment_weight"] = best["weight"] if best["promoted"] else 0.
    return {"chosen": best, "control_mse": baseline_error, "trials": records}


def copy_parent(source, target):
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "bundle.json", target / "bundle.json")
    shutil.copytree(source / "modelos", target / "modelos", dirs_exist_ok=True)
    shutil.copytree(source / "base_v5", target / "base_v5", dirs_exist_ok=True)


def load_bundle(path):
    path = Path(path)
    metadata = json.loads((path / "bundle.json").read_text(encoding="utf-8"))
    models = {}
    for name, spec in COMPONENTS.items():
        cls = CatBoostClassifier if spec[3] == "classification" else CatBoostRegressor
        models[name] = cls()
        models[name].load_model(str(path / "modelos" / f"{name}.cbm"))
    return metadata, models, v6.load_bundle(path / "parent_v6")


def assemble(prepared, parent, components, metadata):
    """Actualizar outputs fisicos y, solo si fue seleccionado, el compuesto."""
    result = parent.copy().reset_index(drop=True)
    usable = prepared.enhancement_available.to_numpy()
    for name in COMPONENTS:
        col = component_column(name)
        parent_col = "pred_stuff_run_value" if name == "physical_control" else col
        value = parent[parent_col].to_numpy().copy()
        value[usable] = components.loc[usable, col].to_numpy()
        result[f"component_{col}"] = value
        if name != "physical_control":
            result.loc[usable, col] = value[usable]
    for name in CALIBRATION_TASKS:
        col = component_column(name)
        result[f"{col}_uncalibrated"] = result[col].to_numpy()
        if usable.any():
            result.loc[usable, col] = apply_calibrator(result.loc[usable, col], metadata["calibrations"][name]["calibrator"])
    comp = pd.DataFrame({component_column(name): result[f"component_{component_column(name)}"].to_numpy() for name in COMPONENTS})
    selection = metadata["stack"]["chosen"]
    x = stack_features(comp, metadata["calibrations"], selection["use_calibrated"])
    result["pred_stack_candidate"] = predict_stack(x, selection["model"])
    result["pred_physical_control"] = comp.pred_physical_control.to_numpy()
    result["compound_status"] = "parent_retained"
    if selection["promoted"] and usable.any():
        weight = selection["deployment_weight"]
        core = weight * result.pred_stack_candidate + (1-weight) * comp.pred_physical_control
        result.loc[usable, "pred_stuff_run_value"] = core[usable].to_numpy()
        raw = {"stuff_plus": -core.to_numpy(), "location_plus": (core-result.pred_xrunvalue).to_numpy()}
        for name, values in raw.items():
            ref = metadata["reference"][name]
            result.loc[usable, name] = 100 + 10 * (values[usable]-ref["mean"]) / ref["std"]
        result.loc[usable, "compound_status"] = "oof_stack_selected"
        result.loc[usable, "score_reference_id"] = "v7_calibration_reference"
    result["v7_available"] = usable
    return result


def infer(frame, bundle):
    metadata, models, parent_bundle = bundle
    parent = v6.infer(frame, parent_bundle)
    profile = parent_bundle[1][0]["profile"]
    prepared = v6.enhance(v5.apply_profile(frame, profile))
    # Los valores de componentes para filas sin mediciones se sustituyen por el
    # padre en assemble; no se emiten scores nuevos para esas filas.
    if prepared.enhancement_available.all():
        components = predict_components(prepared, models)
    else:
        components = pd.DataFrame(index=range(len(prepared)), columns=[component_column(n) for n in COMPONENTS], dtype=float)
        mask = prepared.enhancement_available.to_numpy()
        if mask.any():
            components.loc[mask] = predict_components(prepared.loc[mask], models).to_numpy()
    return assemble(prepared, parent, components, metadata)


def prepare(args):
    if (args.salida / "protocolo.json").exists():
        raise FileExistsError("La preparacion ya existe; usar --fase seleccionar o una salida nueva")
    parent_meta = json.loads((args.parent / "bundle.json").read_text(encoding="utf-8"))
    if parent_meta["source_sha256"] != v6.file_hash(args.parquet):
        raise ValueError("El origen difiere del utilizado en v6")
    if parent_meta["script_sha256"] != v6.file_hash(v6.__file__):
        raise ValueError("El codigo padre no coincide con los artefactos v6")
    for name, digest in parent_meta["model_hashes"].items():
        if v6.file_hash(args.parent / name) != digest:
            raise ValueError(f"Modelo padre alterado: {name}")
    protocol = {"version": 7, "seed": SEED, "folds": FOLDS,
                "partitions": {"fit": .60, "early_stop": .10, "calibration": .15, "selection": .15},
                "component_configs": {name: config_for(name, 0) for name in COMPONENTS},
                "components": {name: {"target": spec[0], "features": spec[1], "kind": spec[3], "condition": spec[2]} for name, spec in COMPONENTS.items()},
                "stack_columns": STACK_COLUMNS, "alphas": ALPHAS, "mix_weights": MIX_WEIGHTS,
                "source_sha256": v6.file_hash(args.parquet), "script_sha256": v6.file_hash(__file__),
                "v5_script_sha256": v6.file_hash(v5.__file__), "v6_script_sha256": v6.file_hash(v6.__file__),
                "parent_bundle_sha256": v6.file_hash(args.parent / "bundle.json"),
                "benchmark_year": 2026, "benchmark_previously_seen": True, "development_max_year": 2025,
                "calibration_gate": {"max_brier_ratio": 1.001, "max_logloss_ratio": 1.0015,
                    "min_absolute_ece_gain": .0005, "min_relative_ece_gain": .10,
                    "max_quantile_ece_ratio": 1.05, "quantile_ece_tolerance": .0005},
                "minimum_stack_selection_gain": .001}
    v6.json_write(args.salida / "protocolo.json", protocol)
    raw = v5.prepare_raw(v6.read_seasons(args.parquet, 2025))
    frame = partition_games(v6.enhance(v5.historical_features(raw)))
    if not frame.enhancement_available.all():
        raise ValueError("La preparacion OOF requiere mediciones adicionales completas en desarrollo")
    v5.write_parquet(frame[v6.IDENTITY + ["partition", "oof_fold"]], args.salida / "particiones_pre2026.parquet")
    fit = frame.loc[frame.partition.eq("fit")].copy().reset_index(drop=True)
    stop = frame.loc[frame.partition.eq("early_stop")].copy()
    observed = ["PitchCall", "is_swing", "is_whiff", "is_ball_in_play", "is_groundball", "hit_type", "home_run", "ExitSpeed", "run_value_proxy"]
    oof = fit[v6.IDENTITY + ["oof_fold", *observed]].copy()
    cal_rows = frame.loc[frame.partition.eq("calibration")].copy().reset_index(drop=True)
    for name in COMPONENTS:
        oof[component_column(name)] = np.nan
    for fold in range(FOLDS):
        train = fit.loc[fit.oof_fold.ne(fold)]
        held = fit.loc[fit.oof_fold.eq(fold)]
        folder = args.salida / "oof" / f"fold_{fold}"
        (folder / "modelos").mkdir(parents=True, exist_ok=True)
        v5.write_parquet(train[v6.IDENTITY], folder / "train_ids.parquet")
        fold_cal = cal_rows[v6.IDENTITY + ["is_swing", "is_whiff"]].copy()
        for name, spec in COMPONENTS.items():
            print(f"OOF {fold+1}/{FOLDS}: {name} ({len(train):,} train, {len(held):,} predicciones)", flush=True)
            model = fit_component(train, stop, name, fold, args.hilos)
            model.save_model(str(folder / "modelos" / f"{name}.cbm"))
            oof.loc[held.index, component_column(name)] = v6.predict(model, spec, held)
            if name in CALIBRATION_TASKS:
                fold_cal[component_column(name)] = v6.predict(model, spec, cal_rows)
        v5.write_parquet(oof.loc[held.index], folder / "predicciones.parquet")
        v5.write_parquet(fold_cal, folder / "calibration_scores.parquet")
    if oof.PitchUID.duplicated().any() or not np.isfinite(oof[[component_column(n) for n in COMPONENTS]].to_numpy()).all():
        raise ValueError("Predicciones OOF duplicadas o incompletas")
    v5.write_parquet(oof, args.salida / "oof_fit.parquet")
    models = {}
    (args.salida / "modelos").mkdir(exist_ok=True)
    for name in COMPONENTS:
        print(f"Componente final: {name}", flush=True)
        model = fit_component(fit, stop, name, 0, args.hilos)
        model.save_model(str(args.salida / "modelos" / f"{name}.cbm"))
        models[name] = model
    for part in ["calibration", "selection"]:
        rows = frame.loc[frame.partition.eq(part)].copy().reset_index(drop=True)
        predictions = predict_components(rows, models)
        table = rows[v6.IDENTITY + ["PitchCall", "is_swing", "is_whiff", "is_groundball", "home_run", "ExitSpeed", "hit_type", "is_ball_in_play", "run_value_proxy"]].copy()
        for col in predictions:
            table[col] = predictions[col].to_numpy()
        v5.write_parquet(table, args.salida / f"predicciones_{part}.parquet")
    copy_parent(args.parent, args.salida / "parent_v6")
    artifacts = {str(p.relative_to(args.salida)).replace('\\', '/'): v6.file_hash(p) for p in args.salida.rglob("*.cbm")}
    artifacts.update({"oof_fit.parquet": v6.file_hash(args.salida / "oof_fit.parquet"),
                      "particiones_pre2026.parquet": v6.file_hash(args.salida / "particiones_pre2026.parquet")})
    v6.json_write(args.salida / "preparacion.json", {"model_and_oof_hashes": artifacts, "source_rows": len(frame), "fit_rows": len(fit), "threads": args.hilos})
    print("OOF y componentes completos. Solo se leyeron temporadas hasta 2025.", flush=True)


def assert_protocol(args):
    protocol = json.loads((args.salida / "protocolo.json").read_text(encoding="utf-8"))
    for actual, expected in [(v6.file_hash(__file__), protocol["script_sha256"]),
                             (v6.file_hash(v5.__file__), protocol["v5_script_sha256"]),
                             (v6.file_hash(v6.__file__), protocol["v6_script_sha256"]),
                             (v6.file_hash(args.parquet), protocol["source_sha256"])]:
        if actual != expected:
            raise ValueError("Cambio codigo u origen respecto del protocolo")
    return protocol


def select(args):
    protocol = assert_protocol(args)
    if (args.salida / "seleccion_congelada.json").exists():
        raise FileExistsError("Seleccion ya congelada; usar --fase evaluar")
    oof = v5.read_parquet(args.salida / "oof_fit.parquet")
    calibration = v5.read_parquet(args.salida / "predicciones_calibration.parquet")
    selection = v5.read_parquet(args.salida / "predicciones_selection.parquet")
    calibrations = {}
    for name in CALIBRATION_TASKS:
        spec = COMPONENTS[name]
        cal_mask, sel_mask = v5.eligible(calibration, spec), v5.eligible(selection, spec)
        col = component_column(name)
        candidates = fit_calibrators(calibration.loc[cal_mask, spec[0]], calibration.loc[cal_mask, col])
        fit_y = oof.loc[v5.eligible(oof, spec), spec[0]]
        chosen = select_calibrator(selection.loc[sel_mask, spec[0]], selection.loc[sel_mask, col], fit_y, candidates)
        calibrations[name] = chosen
        print(json.dumps({"task": name, "selected_calibration": chosen["selected"], "selection_metrics": chosen["selection_metrics"]}), flush=True)
    # Cada bloque OOF recibe un calibrador aprendido con las predicciones de SU
    # modelo sobre los juegos de calibracion, nunca con sus propios outcomes.
    calibrated_oof = oof.copy()
    for fold in range(FOLDS):
        fold_cal = v5.read_parquet(args.salida / "oof" / f"fold_{fold}" / "calibration_scores.parquet")
        for name in CALIBRATION_TASKS:
            col = component_column(name)
            mask = fold_cal.is_whiff.notna()
            if name == "whiff_given_swing":
                mask &= fold_cal.is_swing.eq(1)
            variants = fit_calibrators(fold_cal.loc[mask, "is_whiff"], fold_cal.loc[mask, col])
            chosen = variants[calibrations[name]["selected"]]
            calibrations[name].setdefault("oof_calibrators", {})[str(fold)] = chosen
            held = calibrated_oof.oof_fold.eq(fold)
            calibrated_oof.loc[held, col] = apply_calibrator(oof.loc[held, col], chosen)
    v5.write_parquet(calibrated_oof, args.salida / "oof_calibrado.parquet")
    stack = select_stack(oof, oof.run_value_proxy, selection, selection.run_value_proxy, calibrations, calibrated_oof)
    core = stack["chosen"]
    raw_cal = predict_stack(stack_features(calibration, calibrations, core["use_calibrated"]), core["model"])
    core_cal = core["deployment_weight"] * raw_cal + (1-core["deployment_weight"]) * calibration.pred_physical_control.to_numpy()
    raw = v5.prepare_raw(v6.read_seasons(args.parquet, 2025))
    ids = calibration.PitchUID.tolist()
    raw_calibration = raw.set_index("PitchUID").loc[ids].reset_index()
    parent = v6.infer(raw_calibration, v6.load_bundle(args.salida / "parent_v6"))
    values = {"stuff_plus": -core_cal, "location_plus": core_cal-parent.pred_xrunvalue.to_numpy()}
    reference = {name: {"mean": float(x.mean()), "std": max(float(x.std()), 1e-8)} for name, x in values.items()}
    selection_meta = {"version": 7, "calibrations": calibrations, "stack": stack, "reference": reference,
                      "protocol_sha256": v6.file_hash(args.salida / "protocolo.json"),
                      "preparation_sha256": v6.file_hash(args.salida / "preparacion.json"),
                      "source_sha256": protocol["source_sha256"], "script_sha256": protocol["script_sha256"],
                      "training_max_year": 2025, "benchmark_previously_seen": True,
                      "reference_population": "calibration_games_before_2026", "pitching_plus_policy": "parent_unchanged"}
    v6.json_write(args.salida / "seleccion_congelada.json", selection_meta)
    v6.json_write(args.salida / "bundle.json", selection_meta)
    print(json.dumps({"stack_selection": {k: v for k, v in core.items() if k != "model"}}), flush=True)
    print("Calibracion y compuesto congelados antes de leer 2026.", flush=True)


def evaluate(args):
    assert_protocol(args)
    if (args.salida / "metricas_benchmark_2026.json").exists():
        raise FileExistsError("Benchmark ya evaluado; no se permite reoptimizarlo")
    bundle = load_bundle(args.salida)
    raw = v5.prepare_raw(v6.read_seasons(args.parquet, 2026))
    test = raw.loc[raw.year.eq(2026)].copy().reset_index(drop=True)
    predictions = infer(test, bundle)
    parent = v6.infer(test, bundle[2])
    scores = test[v6.IDENTITY].copy()
    for col in predictions:
        if col not in scores:
            scores[col] = predictions[col].to_numpy()
    scores["model_id"] = "v7_oof_and_calibration_frozen_pre2026"
    scores["prediction_kind"] = "reused_temporal_benchmark_2026"
    scores["training_max_year"] = 2025
    if scores.PitchUID.duplicated().any() or not np.isfinite(scores[v6.SCORE_COLUMNS].to_numpy()).all():
        raise ValueError("Scores duplicados o incompletos")
    v5.write_parquet(scores, args.salida / "scores_pitch_v7.parquet")
    fit_rows = v5.read_parquet(args.salida / "oof_fit.parquet")
    records = []
    for name in COMPONENTS:
        if name == "physical_control":
            continue
        spec, col = COMPONENTS[name], component_column(name)
        mask = v5.eligible(test, spec).to_numpy()
        y = test.loc[mask, spec[0]]
        new, old = predictions.loc[mask, col].to_numpy(), parent.loc[mask, col].to_numpy()
        fit_y = fit_rows.loc[v5.eligible(fit_rows, spec), spec[0]]
        row = {"task": name, "n_test": int(mask.sum()),
               "v6": v5.metrics(y, old, fit_y, spec[3]), "v7": v5.metrics(y, new, fit_y, spec[3]),
               "paired_game_bootstrap_vs_v6": v6.game_bootstrap_comparison(test.loc[mask], y, old, new)}
        if name in CALIBRATION_TASKS:
            raw_pred = predictions.loc[mask, f"{col}_uncalibrated"].to_numpy()
            row["v7_uncalibrated"] = probability_metrics(y, raw_pred, fit_y)
            row["v7"] = probability_metrics(y, new, fit_y)
            row["calibration_effect"] = v6.game_bootstrap_comparison(test.loc[mask], y, raw_pred, new)
            row["chosen_calibration"] = bundle[0]["calibrations"][name]["selected"]
        records.append(row)
        print(json.dumps(row), flush=True)
    y = test.run_value_proxy
    current = predictions.pred_stuff_run_value.to_numpy()
    parent_core = parent.pred_stuff_run_value.to_numpy()
    control = predictions.pred_physical_control.to_numpy()
    chosen = bundle[0]["stack"]["chosen"]
    candidate = chosen["weight"] * predictions.pred_stack_candidate.to_numpy() + (1-chosen["weight"]) * control
    fit_y = fit_rows.run_value_proxy
    rv_row = {"task": "stuff_run_value", "n_test": len(test), "promoted": chosen["promoted"],
              "v6": v5.metrics(y, parent_core, fit_y, "regression"),
              "v7": v5.metrics(y, current, fit_y, "regression"),
              "same_cohort_control": v5.metrics(y, control, fit_y, "regression"),
              "stack_candidate": v5.metrics(y, candidate, fit_y, "regression"),
              "paired_game_bootstrap_vs_v6": v6.game_bootstrap_comparison(test, y, parent_core, current),
              "stack_effect_same_cohort": v6.game_bootstrap_comparison(test, y, control, candidate)}
    records.append(rv_row)
    print(json.dumps(rv_row), flush=True)
    v6.json_write(args.salida / "metricas_benchmark_2026.json", records)
    print(f"v7 completa: {len(scores):,} scores, calibracion independiente y compuesto OOF", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fase", choices=["preparar", "seleccionar", "evaluar", "todo"], default="todo")
    parser.add_argument("--parquet", type=Path, default=Path("stuff_model_df.parquet"))
    parser.add_argument("--parent", type=Path, default=Path("stuff_plus_output_v6"))
    parser.add_argument("--salida", type=Path, default=Path("stuff_plus_output_v7"))
    parser.add_argument("--hilos", type=int, default=6)
    args = parser.parse_args()
    if args.hilos < 1:
        parser.error("--hilos debe ser positivo")
    args.salida.mkdir(parents=True, exist_ok=True)
    if args.fase in ["preparar", "todo"]:
        prepare(args)
    if args.fase in ["seleccionar", "todo"]:
        select(args)
    if args.fase in ["evaluar", "todo"]:
        evaluate(args)


if __name__ == "__main__":
    main()
