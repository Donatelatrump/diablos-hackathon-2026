"""Stuff+ v5: validacion temporal, inferencia completa y referencias persistentes.

Ejecutar con .venv/Scripts/python.exe entrenar_stuff_plus_v5.py.
El run value es un proxy de pesos lineales; no es RE24 ni efecto causal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

import catboost
import duckdb
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, CatBoostRegressor
from sklearn.metrics import average_precision_score, brier_score_loss, mean_squared_error, r2_score, roc_auc_score

PHYSICAL = [
    "RelSpeed", "EffectiveVelo", "SpinRate", "SpinAxis_sin", "SpinAxis_cos",
    "RelHeight", "RelSide", "Extension", "VertBreak", "InducedVertBreak", "HorzBreak",
    "velo_diff_vs_fb", "ivb_diff_vs_fb", "hb_diff_vs_fb", "release_distance_vs_fb",
    "pitch_usage_pct", "arsenal_history_available", "AutoPitchType", "PitcherThrows",
]
LOCATION = PHYSICAL + ["PlateLocHeight", "PlateLocSide", "Balls", "Strikes", "BatterSide"]
ENVIRONMENT = LOCATION + ["altitude_category"]
CATEGORICAL = {"AutoPitchType", "PitcherThrows", "BatterSide", "altitude_category"}
BASELINE_KEYS = ["Balls", "Strikes"]
TASKS = {
    "whiff": ("is_whiff", PHYSICAL, None, "classification"),
    "whiff_given_swing": ("is_whiff", PHYSICAL, "swing", "classification"),
    "ball_in_play": ("is_ball_in_play", PHYSICAL, None, "classification"),
    "weak_contact": ("is_weak_contact", PHYSICAL, "exit", "classification"),
    "barrel_or_hard_contact": ("is_hard_contact", PHYSICAL, "exit", "classification"),
    "called_strike": ("is_called_strike", LOCATION, None, "classification"),
    "chase": ("swung_outside_strike_zone", LOCATION, None, "classification"),
    "groundball_given_in_play": ("is_groundball", PHYSICAL, "hit_type", "classification"),
    "home_run_per_pitch": ("home_run", PHYSICAL + ["altitude_category"], None, "classification"),
    "exit_speed_given_in_play": ("ExitSpeed", PHYSICAL, "exit", "regression"),
    "stuff_run_value": ("run_value_proxy", PHYSICAL, None, "regression"),
    "xrunvalue": ("run_value_proxy", LOCATION, None, "regression"),
    "environment_run_value": ("run_value_proxy", ENVIRONMENT, None, "regression"),
}
PROFILE_NUMERIC = ["RelSpeed", "InducedVertBreak", "HorzBreak", "RelHeight", "RelSide", "Extension"]


def read_parquet(path):
    with duckdb.connect() as con:
        return con.execute("SELECT * FROM read_parquet(?)", [str(path)]).fetchdf()


def write_parquet(frame, path):
    with duckdb.connect() as con:
        con.register("export_frame", frame)
        escaped = str(Path(path).resolve()).replace("'", "''")
        con.execute(f"COPY export_frame TO '{escaped}' (FORMAT PARQUET, COMPRESSION ZSTD)")


def observed_run_value(frame):
    """Pesos fijos por resultado observado; ninguna media estimada con test."""
    rv = pd.Series(0.0, index=frame.index)
    rv.loc[frame["PitchCall"].isin(["StrikeCalled", "StrikeSwinging"])] = -0.05
    rv.loc[frame["PitchCall"].isin(["BallCalled", "BallinDirt"])] = 0.03
    weights = {"Out": -0.27, "FieldersChoice": -0.27, "Sacrifice": -0.27,
               "Strikeout": -0.27, "Walk": 0.30, "HitByPitch": 0.33,
               "Single": 0.47, "Double": 0.78, "Triple": 1.09, "HomeRun": 1.40}
    result = frame["play_result"].map(weights)
    return result.fillna(rv).astype(float)


def prepare_raw(frame):
    frame = frame.copy()
    if frame["PitchUID"].isna().any() or frame["PitchUID"].duplicated().any():
        raise ValueError("El origen requiere PitchUID no nulos y unicos")
    frame["run_value_proxy"] = observed_run_value(frame)
    in_play = frame["PitchCall"].eq("InPlay")
    frame["is_groundball"] = frame["hit_type"].eq("GroundBall").astype(float).where(in_play & frame["hit_type"].notna())
    frame["is_weak_contact"] = frame["ExitSpeed"].lt(85).astype(float).where(in_play & frame["ExitSpeed"].notna())
    # Hard hit: velocidad >=95 mph, independiente del angulo. No se denomina barrel.
    frame["is_hard_contact"] = frame["ExitSpeed"].ge(95).astype(float).where(in_play & frame["ExitSpeed"].notna())
    return frame


def fit_profile(history):
    """Solo historia disponible. Fastball primaria = Four-Seam/Sinker mas usado."""
    fb = history.loc[history["AutoPitchType"].isin(["Four-Seam", "Sinker"])]
    counts = fb.groupby(["pitcher_anon_id", "AutoPitchType"]).size().rename("n").reset_index()
    primary = counts.sort_values(["n", "AutoPitchType"], ascending=[False, True]).drop_duplicates("pitcher_anon_id")
    selected = fb.merge(primary[["pitcher_anon_id", "AutoPitchType"]], on=["pitcher_anon_id", "AutoPitchType"])
    means = selected.groupby("pitcher_anon_id")[PROFILE_NUMERIC].mean().reset_index()
    usage = history.groupby(["pitcher_anon_id", "AutoPitchType"]).size().rename("n").reset_index()
    usage["pitch_usage_pct"] = usage["n"] / usage.groupby("pitcher_anon_id")["n"].transform("sum")
    return {"fastballs": json.loads(means.to_json(orient="records")),
            "usage": json.loads(usage.drop(columns="n").to_json(orient="records"))}


def apply_profile(frame, profile):
    result = frame.copy().reset_index(drop=True)
    fb = pd.DataFrame(profile["fastballs"], columns=["pitcher_anon_id", *PROFILE_NUMERIC])
    for col in PROFILE_NUMERIC:
        fb[col] = pd.to_numeric(fb[col], errors="coerce").astype(float)
    fb = fb.rename(columns={c: f"fb_{c}" for c in PROFILE_NUMERIC})
    usage = pd.DataFrame(profile["usage"], columns=["pitcher_anon_id", "AutoPitchType", "pitch_usage_pct"])
    usage["pitch_usage_pct"] = pd.to_numeric(usage["pitch_usage_pct"], errors="coerce").astype(float)
    result = result.merge(fb, on="pitcher_anon_id", how="left", validate="many_to_one")
    result = result.merge(usage, on=["pitcher_anon_id", "AutoPitchType"], how="left", validate="many_to_one")
    result["arsenal_history_available"] = result["fb_RelSpeed"].notna().astype(float)
    for dest, raw in [("velo_diff_vs_fb", "RelSpeed"), ("ivb_diff_vs_fb", "InducedVertBreak"), ("hb_diff_vs_fb", "HorzBreak")]:
        result[dest] = result[raw] - result[f"fb_{raw}"]
    result["release_distance_vs_fb"] = np.sqrt(sum((result[c] - result[f"fb_{c}"]) ** 2 for c in ["RelHeight", "RelSide", "Extension"]))
    return result.drop(columns=[f"fb_{c}" for c in PROFILE_NUMERIC])


def historical_features(raw):
    """Cada temporada usa exclusivamente temporadas anteriores, nunca su futuro."""
    chunks = []
    for year in sorted(raw["year"].unique()):
        chunks.append(apply_profile(raw.loc[raw["year"].eq(year)], fit_profile(raw.loc[raw["year"].lt(year)])))
    return pd.concat(chunks, ignore_index=True)


def features(frame, columns):
    x = frame.copy()
    radians = np.deg2rad(pd.to_numeric(x["SpinAxis"], errors="coerce"))
    x["SpinAxis_sin"], x["SpinAxis_cos"] = np.sin(radians), np.cos(radians)
    for col in columns:
        if col not in x:
            raise ValueError(f"Falta caracteristica requerida: {col}")
        if col in CATEGORICAL:
            x[col] = x[col].fillna("__MISSING__").astype(str)
        else:
            x[col] = pd.to_numeric(x[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
    return x[columns]


def eligible(frame, spec):
    target, _, condition, _ = spec
    mask = frame[target].notna()
    if condition == "swing":
        mask &= frame["is_swing"].eq(1)
    elif condition == "exit":
        mask &= frame["PitchCall"].eq("InPlay") & frame["ExitSpeed"].notna()
    elif condition == "hit_type":
        mask &= frame["PitchCall"].eq("InPlay") & frame["hit_type"].notna()
    return mask


def group_partition(frame, seed):
    # Un juego completo pertenece a fit o a validacion, incluso si contiene varios pitchers.
    groups = frame["year"].astype(str) + ":" + frame["game_anon_id"].astype(str)
    unique = np.array(sorted(groups.unique()))
    if len(unique) < 5:
        raise ValueError("Se requieren al menos cinco juegos para validacion interna")
    held = set(np.random.default_rng(seed).permutation(unique)[:max(1, round(len(unique) * .2))])
    valid = groups.isin(held)
    return frame.loc[~valid].copy(), frame.loc[valid].copy()


def prediction_column(name, spec):
    return ("p_" if spec[3] == "classification" else "pred_") + name


def predict(model, spec, frame):
    x = features(frame, spec[1])
    if spec[3] == "classification":
        return model.predict_proba(x)[:, list(model.classes_).index(1)]
    return np.asarray(model.predict(x), dtype=float)


def metrics(y, pred, train_y, kind, count_baseline=None):
    y, pred = np.asarray(y, dtype=float), np.asarray(pred, dtype=float)
    constant = np.full(len(y), float(np.mean(train_y)))
    if kind == "classification":
        brier = float(brier_score_loss(y, pred))
        base = float(brier_score_loss(y, constant))
        bin_id = np.minimum((pred * 10).astype(int), 9)
        ece = sum(float((bin_id == b).mean()) * abs(float(pred[bin_id == b].mean() - y[bin_id == b].mean())) for b in range(10) if (bin_id == b).any())
        return {"roc_auc": float(roc_auc_score(y, pred)) if len(np.unique(y)) == 2 else None,
                "average_precision": float(average_precision_score(y, pred)) if y.sum() else None,
                "brier": brier, "brier_baseline": base, "brier_skill": 1 - brier / base if base else None,
                "ece_10_bins": ece, "positive_rate_test": float(y.mean()), "mean_probability": float(pred.mean())}
    mse, base = float(mean_squared_error(y, pred)), float(mean_squared_error(y, constant))
    row = {"rmse": float(np.sqrt(mse)), "r2": float(r2_score(y, pred)),
           "mse_skill": 1 - mse / base if base else None, "baseline_rmse": float(np.sqrt(base))}
    if count_baseline is not None:
        count_mse = float(mean_squared_error(y, count_baseline))
        row.update(count_baseline_rmse=float(np.sqrt(count_mse)), mse_skill_vs_count=1 - mse / count_mse if count_mse else None)
    return row


def count_baseline(train, test):
    table = train.groupby(BASELINE_KEYS)["run_value_proxy"].mean().rename("baseline")
    values = test[BASELINE_KEYS].merge(table.reset_index(), on=BASELINE_KEYS, how="left", validate="many_to_one")
    return values["baseline"].fillna(train["run_value_proxy"].mean()).to_numpy()


def raw_scores(predictions):
    return {
        "stuff_plus": -predictions["pred_stuff_run_value"].to_numpy(),
        "location_plus": (predictions["pred_stuff_run_value"] - predictions["pred_xrunvalue"]).to_numpy(),
        "pitching_plus": -predictions["pred_environment_run_value"].to_numpy(),
    }


def fit_reference(predictions):
    return {name: {"mean": float(values.mean()), "std": max(float(values.std()), 1e-8)} for name, values in raw_scores(predictions).items()}


def add_scores(predictions, reference):
    result = predictions.copy()
    for name, values in raw_scores(result).items():
        if not np.isfinite(values).all():
            raise ValueError(f"Componentes incompletos: {name}")
        result[name] = 100 + 10 * (values - reference[name]["mean"]) / reference[name]["std"]
    return result


def train_fold(frame, test_year, args):
    history = frame.loc[frame["year"].lt(test_year)]
    test = frame.loc[frame["year"].eq(test_year)].copy()
    fit, valid = group_partition(history, args.semilla)
    fold_dir = args.salida / f"holdout_{test_year}"
    model_dir = fold_dir / "modelos"
    model_dir.mkdir(parents=True, exist_ok=True)
    identity = ["PitchUID", "year", "pitcher_anon_id", "game_anon_id", "AutoPitchType", "altitude_category"]
    predictions, reference_predictions = test[identity].copy(), valid[identity].copy()
    records, tasks_meta = [], {}
    for name, spec in TASKS.items():
        target, columns, _, kind = spec
        fit_rows, valid_rows, test_rows = fit.loc[eligible(fit, spec)], valid.loc[eligible(valid, spec)], test.loc[eligible(test, spec)]
        common = dict(iterations=args.iteraciones, depth=args.profundidad, learning_rate=.06,
                      l2_leaf_reg=8, random_seed=args.semilla, thread_count=args.hilos,
                      allow_writing_files=False, verbose=False)
        model = CatBoostClassifier(loss_function="Logloss", **common) if kind == "classification" else CatBoostRegressor(loss_function="RMSE", **common)
        model.fit(features(fit_rows, columns), fit_rows[target],
                  cat_features=[c for c in columns if c in CATEGORICAL],
                  eval_set=(features(valid_rows, columns), valid_rows[target]),
                  early_stopping_rounds=30, use_best_model=True)
        # Mezcla con baseline elegida SOLO en validacion interna. Sin pesos de clase.
        valid_pred = predict(model, spec, valid_rows)
        prior = float(fit_rows[target].mean())
        candidates = [0., .25, .5, .75, 1.]
        errors = [mean_squared_error(valid_rows[target], a * valid_pred + (1 - a) * prior) for a in candidates]
        alpha = candidates[int(np.argmin(errors))]
        model.save_model(str(model_dir / f"{name}.cbm"))
        for rows, dest in [(test, predictions), (valid, reference_predictions)]:
            dest[prediction_column(name, spec)] = alpha * predict(model, spec, rows) + (1 - alpha) * prior
        mask = eligible(test, spec).to_numpy()
        score_pred = predictions[prediction_column(name, spec)].to_numpy()[mask]
        row = {"split": f"season_holdout_{test_year}", "task": name, "n_train": len(fit_rows),
               "n_validation": len(valid_rows), "n_test": len(test_rows), "trees": model.tree_count_, "alpha": alpha,
               **metrics(test_rows[target], score_pred, fit_rows[target], kind,
                         count_baseline(fit, test_rows) if target == "run_value_proxy" else None)}
        records.append(row)
        tasks_meta[name] = {"alpha": alpha, "prior": prior, "features": columns, "kind": kind,
                            "target": target, "trees": model.tree_count_}
        print(json.dumps(row), flush=True)
    reference = fit_reference(reference_predictions)
    predictions = add_scores(predictions, reference)
    predictions["split"] = f"season_holdout_{test_year}"
    predictions["model_id"] = f"v5_holdout_{test_year}"
    predictions["training_max_year"] = int(history["year"].max())
    predictions["prediction_kind"] = "temporal_out_of_sample"
    predictions["observed_run_value_proxy"] = test["run_value_proxy"].to_numpy()
    physical_columns = ["RelSpeed", "SpinRate", "InducedVertBreak", "HorzBreak", "PitcherThrows"]
    for col in physical_columns:
        predictions[col] = test[col].to_numpy()
    write_parquet(predictions, fold_dir / "scores_oos.parquet")
    # No se reentrena con test: este bundle coincide exactamente con lo evaluado.
    metadata = {"version": 5, "test_year": test_year, "training_max_year": int(history["year"].max()),
                "reference_population": "internal_game_holdout_of_training_seasons",
                "tasks": tasks_meta, "reference": reference,
                "profile": fit_profile(frame.loc[frame["year"].lt(test_year)]),
                "run_value_definition": "fixed_linear_weights_proxy_not_RE24",
                "altitude_policy": "dataset_buckets_no_stadium_mapping_no_causal_claim"}
    (fold_dir / "bundle.json").write_text(json.dumps(metadata, indent=2, allow_nan=False), encoding="utf-8")
    (fold_dir / "metricas.json").write_text(json.dumps(records, indent=2, allow_nan=False), encoding="utf-8")
    write_parquet(fit[["PitchUID", "year", "game_anon_id"]].assign(partition="fit"), fold_dir / "filas_fit.parquet")
    write_parquet(valid[["PitchUID", "year", "game_anon_id"]].assign(partition="validation"), fold_dir / "filas_validacion.parquet")
    return predictions, records


def load_bundle(path):
    path = Path(path)
    metadata = json.loads((path / "bundle.json").read_text(encoding="utf-8"))
    models = {}
    for name, task in metadata["tasks"].items():
        model = CatBoostClassifier() if task["kind"] == "classification" else CatBoostRegressor()
        model.load_model(str(path / "modelos" / f"{name}.cbm"))
        models[name] = model
    return metadata, models


def infer(frame, bundle):
    metadata, models = bundle
    prepared = apply_profile(frame, metadata["profile"])
    result = frame[[c for c in ["PitchUID", "pitcher_anon_id", "AutoPitchType", "altitude_category"] if c in frame]].copy().reset_index(drop=True)
    for name, model in models.items():
        task = metadata["tasks"][name]
        spec = (task["target"], task["features"], None, task["kind"])
        result[prediction_column(name, spec)] = task["alpha"] * predict(model, spec, prepared) + (1 - task["alpha"]) * task["prior"]
    return add_scores(result, metadata["reference"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, default=Path("stuff_model_df.parquet"))
    parser.add_argument("--salida", type=Path, default=Path("stuff_plus_output_v5"))
    parser.add_argument("--iteraciones", type=int, default=250)
    parser.add_argument("--profundidad", type=int, default=6)
    parser.add_argument("--hilos", type=int, default=6)
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--temporadas", type=int, nargs="+", default=[2025, 2026])
    args = parser.parse_args()
    if args.iteraciones < 1 or args.hilos < 1 or not 1 <= args.profundidad <= 10:
        parser.error("Iteraciones/hilos deben ser positivos y profundidad entre 1 y 10")
    args.salida.mkdir(parents=True, exist_ok=True)
    print("Cargando datos y perfiles historicos...", flush=True)
    raw = prepare_raw(read_parquet(args.parquet))
    frame = historical_features(raw)
    frames, all_metrics = [], []
    for year in sorted(set(args.temporadas)):
        if not (frame["year"].eq(year).any() and frame["year"].lt(year).any()):
            raise ValueError(f"Temporada sin train/test: {year}")
        predictions, records = train_fold(frame, year, args)
        frames.append(predictions)
        all_metrics.extend(records)
    scores = pd.concat(frames, ignore_index=True)
    if scores["PitchUID"].duplicated().any() or scores[["stuff_plus", "location_plus", "pitching_plus"]].isna().any().any():
        raise ValueError("Scores duplicados o incompletos")
    write_parquet(scores, args.salida / "scores_pitch_v5.parquet")
    # No mezclar temporadas con referencias diferentes en un ranking unico.
    ranking = scores.groupby(["year", "pitcher_anon_id", "AutoPitchType"]).agg(
        n_pitches=("PitchUID", "size"), stuff_plus=("stuff_plus", "mean"),
        location_plus=("location_plus", "mean"), pitching_plus=("pitching_plus", "mean")).reset_index()
    ranking["sample_sufficient"] = ranking["n_pitches"].ge(100)
    ranking.to_csv(args.salida / "arsenal_por_temporada.csv", index=False)
    pitcher = scores.groupby(["year", "pitcher_anon_id"]).agg(n_pitches=("PitchUID", "size"),
        stuff_plus=("stuff_plus", "mean"), location_plus=("location_plus", "mean"), pitching_plus=("pitching_plus", "mean")).reset_index()
    pitcher["sample_sufficient"] = pitcher["n_pitches"].ge(100)
    pitcher.to_csv(args.salida / "pitchers_por_temporada.csv", index=False)
    (args.salida / "metricas_validacion_v5.json").write_text(json.dumps(all_metrics, indent=2, allow_nan=False), encoding="utf-8")
    manifest = {"version": 5, "source_sha256": hashlib.file_digest(args.parquet.open("rb"), "sha256").hexdigest(),
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "python": platform.python_version(), "catboost": catboost.__version__, "pandas": pd.__version__,
                "numpy": np.__version__, "duckdb": duckdb.__version__,
                "args": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
                "source_rows": len(raw), "oos_rows": len(scores), "unique_pitchuids": int(scores["PitchUID"].nunique()),
                "heldout_years": sorted(set(args.temporadas)), "production_refit_including_test": False}
    (args.salida / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Listo: {len(scores):,} scores OOS unicos en {args.salida}", flush=True)


if __name__ == "__main__":
    main()
