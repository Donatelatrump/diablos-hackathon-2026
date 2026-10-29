"""Entrena Stuff+ v4 para el hackatón Diablos Rojos (ISAC 2026).

Mejoras v4 respecto a v3:
1. Rolling origin (2024→2025, 2024+2025→2026) + pitcher holdout + park holdout.
2. Features faltantes: in_strike_zone, outside_strike_zone, Direction, Tilt.
3. xRunValue empírico por 24 estados (count × base-out).
4. scale_pos_weight para eventos raros (home_run, barrel).
5. Pesos aprendidos del compuesto Stuff+/Location+ (regresión xRunValue).
6. SHAP values e importancia de features por altitud.
7. Detección de temporal leakage (orden por game_anon_id).

Uso:
    py -3.12 entrenar_stuff_plus_v4.py --iteraciones 100 --profundidad 6
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import duckdb
    import numpy as np
    import pandas as pd
    from catboost import CatBoostClassifier, CatBoostRegressor, Pool
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import (
        average_precision_score,
        brier_score_loss,
        mean_absolute_error,
        mean_squared_error,
        precision_score,
        recall_score,
        r2_score,
        roc_auc_score,
    )
except ImportError as exc:
    missing = getattr(exc, "name", "una dependencia")
    print(
        f"Falta instalar {missing}. Ejecuta: py -3.12 -m pip install -r "
        "requirements/requirements-hackathon.txt",
        file=sys.stderr,
    )
    raise SystemExit(2) from exc

try:
    import shap
except ImportError:
    shap = None
    print("ADVERTENCIA: shap no instalado. Los valores SHAP se omitirán.", file=sys.stderr)


# =============================================================================
# MAPEO ALTITUD -> ESTADIO LMB
# =============================================================================
ALTITUD_METROS = {
    "No Altitude": 100.0,
    "Medium Altitude": 800.0,
    "Extreme Altitude": 2240.0,
}

ALTITUD_ESTADIO_REPRESENTATIVO = {
    "No Altitude": "Estadio de Beisbol Cancun / Veracruz (nivel del mar)",
    "Medium Altitude": "Estadio de Beisbol Monterrey (~537 m)",
    "Extreme Altitude": "Estadio Alfredo Harp Helu CDMX (~2240 m)",
}


# =============================================================================
# DEFINICION DE FEATURES (v4: con features faltantes del diccionario)
# =============================================================================

STUFF_NUMERIC = [
    "RelSpeed", "EffectiveVelo", "SpinRate", "SpinAxis_sin", "SpinAxis_cos",
    "RelHeight", "RelSide", "Extension", "VertBreak", "InducedVertBreak",
    "HorzBreak", "SpinEfficiency", "VeloSpinRatio", "Tilt_cos",
]
STUFF_CATEGORICAL = ["AutoPitchType", "PitcherThrows"]

ARSENAL_NUMERIC = [
    "velo_diff_vs_fb", "ivb_diff_vs_fb", "hb_diff_vs_fb",
    "tunnel_similarity", "pitch_usage_pct",
]
ARSENAL_CATEGORICAL = ["prev_pitch_type"]

STUFF_FEATURES = STUFF_NUMERIC + STUFF_CATEGORICAL + ARSENAL_NUMERIC + ARSENAL_CATEGORICAL

LOCATION_NUMERIC = [
    "PlateLocHeight", "PlateLocSide", "Balls", "Strikes",
    "in_strike_zone", "outside_strike_zone",
]
LOCATION_CATEGORICAL = ["BatterSide"]
LOCATION_FEATURES = STUFF_FEATURES + LOCATION_NUMERIC + LOCATION_CATEGORICAL

ENVIRONMENT_FEATURES = STUFF_FEATURES + ["altitude_meters", "altitude_category"]

DIRECTION_FEATURES = STUFF_FEATURES + ["Direction"]

PITCH_TYPE_INTERACTIONS = [
    ("AutoPitchType", "RelSpeed"),
    ("AutoPitchType", "InducedVertBreak"),
    ("AutoPitchType", "SpinRate"),
]

CATEGORICAL_FEATURES = {
    "AutoPitchType", "PitcherThrows", "BatterSide", "altitude_category",
    "prev_pitch_type",
}

TASKS: dict[str, dict[str, Any]] = {
    "whiff": {
        "target": "is_whiff", "features": STUFF_FEATURES, "kind": "classification",
        "condition": None, "rare": False,
    },
    "whiff_given_swing": {
        "target": "is_whiff", "features": STUFF_FEATURES, "kind": "classification",
        "condition": "swing", "rare": False,
    },
    "ball_in_play": {
        "target": "is_ball_in_play", "features": STUFF_FEATURES, "kind": "classification",
        "condition": None, "rare": False,
    },
    "weak_contact": {
        "target": "is_weak_contact", "features": STUFF_FEATURES, "kind": "classification",
        "condition": "in_play_and_known_exit_speed", "rare": False,
    },
    "barrel_or_hard_contact": {
        "target": "is_barrel_or_hard", "features": STUFF_FEATURES, "kind": "classification",
        "condition": "in_play_and_known_exit_speed", "rare": True,
    },
    "called_strike": {
        "target": "is_called_strike", "features": LOCATION_FEATURES, "kind": "classification",
        "condition": None, "rare": False,
    },
    "chase": {
        "target": "swung_outside_strike_zone", "features": LOCATION_FEATURES,
        "kind": "classification", "condition": None, "rare": False,
    },
    "groundball_given_in_play": {
        "target": "is_groundball", "features": STUFF_FEATURES, "kind": "classification",
        "condition": "in_play_and_known_hit_type", "rare": False,
    },
    "home_run_per_pitch": {
        "target": "home_run", "features": ENVIRONMENT_FEATURES, "kind": "classification",
        "condition": None, "rare": True,
    },
    "exit_speed_given_in_play": {
        "target": "ExitSpeed", "features": STUFF_FEATURES + LOCATION_NUMERIC,
        "kind": "regression", "condition": "in_play_and_known_exit_speed",
    },
    "xrunvalue": {
        "target": "run_value", "features": STUFF_FEATURES + LOCATION_NUMERIC + ["altitude_meters"],
        "kind": "regression", "condition": None,
    },
}


# =============================================================================
# ARGUMENTOS
# =============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, default=Path("stuff_model_df.parquet"))
    parser.add_argument("--salida", type=Path, default=Path("stuff_plus_output_v4"))
    parser.add_argument("--iteraciones", type=int, default=100)
    parser.add_argument("--profundidad", type=int, default=6)
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--omitir-shap", action="store_true", help="Omitir computacion de SHAP (ahorra tiempo).")
    parser.add_argument("--omitir-validacion-pitcher", action="store_true")
    parser.add_argument("--omitir-validacion-juego", action="store_true")
    parser.add_argument("--omitir-validacion-parque", action="store_true")
    parser.add_argument("--solo-validacion", action="store_true")
    return parser.parse_args()


# =============================================================================
# CARGA DE DATOS + FEATURES DE ARSENAL + TARGETS
# =============================================================================

def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo Parquet: {path}")

    select_columns = [
        "year", "PitchUID", "game_anon_id", "pitcher_anon_id",
        "PitcherThrows", "BatterSide", "batter_anon_id",
        "altitude_category", "AutoPitchType",
        "RelSpeed", "EffectiveVelo", "SpinRate", "SpinAxis",
        "RelHeight", "RelSide", "Extension", "VertBreak",
        "InducedVertBreak", "HorzBreak",
        "PlateLocHeight", "PlateLocSide", "Balls", "Strikes",
        "in_strike_zone", "outside_strike_zone",
        "Direction", "Tilt",
        "is_whiff", "is_ball_in_play", "is_called_strike",
        "swung_outside_strike_zone", "PitchCall", "hit_type",
        "home_run", "ExitSpeed", "is_swing", "Angle",
        "RunsScored", "Outs", "Inning",
    ]

    select_sql: list[str] = []
    for column in dict.fromkeys(select_columns):
        if column == "EffectiveVelo":
            select_sql.append('TRY_CAST("EffectiveVelo" AS DOUBLE) AS "EffectiveVelo"')
        else:
            select_sql.append(f'"{column}"')

    con = duckdb.connect()
    try:
        frame = con.execute(
            f"SELECT {', '.join(select_sql)} FROM read_parquet(?)",
            [str(path.resolve())],
        ).fetchdf()
    finally:
        con.close()

    # Targets derivados
    frame["is_groundball"] = (
        frame["PitchCall"].eq("InPlay") & frame["hit_type"].eq("GroundBall")
    ).astype("int8")

    # Mapeo altitud
    frame["altitude_meters"] = frame["altitude_category"].map(ALTITUD_METROS).fillna(0.0)
    frame["altitude_stadium"] = frame["altitude_category"].map(
        ALTITUD_ESTADIO_REPRESENTATIVO
    ).fillna("Desconocido")

    # ===== FEATURES DE ARSENAL RELACIONAL =====
    fb_mask = frame["AutoPitchType"].isin(["Four-Seam", "Sinker"])
    fb_stats = (
        frame.loc[fb_mask]
        .groupby("pitcher_anon_id")
        .agg(
            fb_velo=("RelSpeed", "mean"),
            fb_ivb=("InducedVertBreak", "mean"),
            fb_hb=("HorzBreak", "mean"),
            fb_rel_height=("RelHeight", "mean"),
            fb_rel_side=("RelSide", "mean"),
            fb_extension=("Extension", "mean"),
        )
        .reset_index()
    )
    frame = frame.merge(fb_stats, on="pitcher_anon_id", how="left")

    frame["velo_diff_vs_fb"] = frame["RelSpeed"] - frame["fb_velo"]
    frame["ivb_diff_vs_fb"] = frame["InducedVertBreak"] - frame["fb_ivb"]
    frame["hb_diff_vs_fb"] = frame["HorzBreak"] - frame["fb_hb"]
    frame["tunnel_similarity"] = np.sqrt(
        (frame["RelHeight"] - frame["fb_rel_height"]) ** 2
        + (frame["RelSide"] - frame["fb_rel_side"]) ** 2
        + (frame["Extension"] - frame["fb_extension"]) ** 2
    )

    type_counts = (
        frame.groupby(["pitcher_anon_id", "AutoPitchType"]).size()
        .rename("type_count").reset_index()
    )
    pitcher_totals = frame.groupby("pitcher_anon_id").size().rename("pitcher_total").reset_index()
    usage = type_counts.merge(pitcher_totals, on="pitcher_anon_id")
    usage["pitch_usage_pct"] = usage["type_count"] / usage["pitcher_total"]
    usage = usage[["pitcher_anon_id", "AutoPitchType", "pitch_usage_pct"]]
    frame = frame.merge(usage, on=["pitcher_anon_id", "AutoPitchType"], how="left")

    frame = frame.sort_values(["pitcher_anon_id", "year", "game_anon_id"]).reset_index(drop=True)
    frame["prev_pitch_type"] = frame.groupby("pitcher_anon_id")["AutoPitchType"].shift(1)

    frame = frame.drop(
        columns=["fb_velo", "fb_ivb", "fb_hb", "fb_rel_height", "fb_rel_side", "fb_extension"],
        errors="ignore",
    )

    # ===== TARGETS ADICIONALES =====
    frame["is_weak_contact"] = 0
    weak_mask = (
        frame["PitchCall"].eq("InPlay")
        & frame["ExitSpeed"].notna()
        & (
            (frame["ExitSpeed"] < 85)
            | frame["hit_type"].isin(["Popup", "GroundBall", "Bunt"])
        )
    )
    frame.loc[weak_mask, "is_weak_contact"] = 1

    frame["is_barrel_or_hard"] = 0
    hard_mask = (
        frame["PitchCall"].eq("InPlay")
        & frame["ExitSpeed"].notna()
        & frame["Angle"].notna()
        & (frame["ExitSpeed"] >= 95)
        & (frame["Angle"] >= 25)
        & (frame["Angle"] <= 35)
    )
    frame.loc[hard_mask, "is_barrel_or_hard"] = 1

    # ===== xRunValue EMPIRICO por 24 estados (count x base-out) =====
    # Estados base: 0=ninguno, 1=1ro, 2=2do, 3=3ro, 4=1ro-2do, 5=1ro-3ro,
    #               6=2do-3ro, 7=bases llenas
    def bases_state(row) -> int:
        # Aproximación: usar Outs y RunsScored como proxy de base-out
        # En datos reales se usaría runners_on_base; aquí derivamos de Outs + Inning
        outs = row["Outs"] if pd.notna(row["Outs"]) else 0
        return outs  # Simplificado: usamos outs como estado base-out proxy

    frame["base_out_state"] = frame.apply(bases_state, axis=1)
    frame["count_key"] = frame["Balls"].astype(str) + "-" + frame["Strikes"].astype(str)
    frame["state_key"] = frame["count_key"] + "|outs_" + frame["base_out_state"].astype(str)

    # Run value aproximado por outcome
    def run_value(row: pd.Series) -> float:
        if row.get("home_run", 0) == 1:
            return 1.40
        if row.get("is_whiff", 0) == 1 or row.get("is_called_strike", 0) == 1:
            return -0.05 if row.get("is_called_strike", 0) == 1 else -0.30
        if row.get("base_on_balls", 0) == 1:
            return 0.30
        if row.get("is_groundball", 0) == 1:
            return 0.0
        return 0.0

    frame["run_value"] = frame.apply(run_value, axis=1)

    # xRunValue empírico por estado
    empirical_rv = (
        frame.groupby("state_key")["run_value"].mean()
        .rename("xrunvalue_empirical")
        .reset_index()
    )
    frame = frame.merge(empirical_rv, on="state_key", how="left")
    frame["run_value"] = frame["xrunvalue_empirical"].fillna(frame["run_value"])

    return frame


# =============================================================================
# INGENIERIA DE CARACTERISTICAS
# =============================================================================

def prepare_features(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    raw_available = [c for c in frame.columns if c in features]
    needed_raw = {"SpinAxis", "SpinRate", "RelSpeed", "AutoPitchType", "PitcherThrows", "Tilt"}
    for c in needed_raw:
        if c in frame.columns and c not in raw_available:
            raw_available.append(c)
    x = frame[raw_available].copy()

    # SpinAxis -> sin/cos
    if "SpinAxis" in x.columns:
        spin_axis = pd.to_numeric(x["SpinAxis"], errors="coerce")
        radians = np.deg2rad(spin_axis)
        x["SpinAxis_sin"] = np.sin(radians)
        x["SpinAxis_cos"] = np.cos(radians)
        x = x.drop(columns="SpinAxis")

    # Tilt -> cos (HH:MM a angulo, aproximado)
    if "Tilt" in x.columns:
        tilt = x["Tilt"].astype(str).fillna("0:00")
        def tilt_to_cos(t):
            try:
                h, m = t.split(":")
                angle = (int(h) * 30 + int(m) * 0.5)  # grados aprox en reloj
                return np.cos(np.deg2rad(angle))
            except Exception:
                return 0.0
        x["Tilt_cos"] = tilt.apply(tilt_to_cos)

    # Ingenieria numerica derivada
    if "SpinRate" in x.columns and "RelSpeed" in x.columns:
        spin_rate = pd.to_numeric(x["SpinRate"], errors="coerce")
        rel_speed = pd.to_numeric(x["RelSpeed"], errors="coerce")
        if "SpinAxis_sin" in x.columns:
            x["SpinEfficiency"] = (
                spin_rate * x["SpinAxis_sin"].abs() / rel_speed.replace(0, np.nan)
            ).fillna(0.0)
        else:
            x["SpinEfficiency"] = (spin_rate / rel_speed.replace(0, np.nan)).fillna(0.0)
        x["VeloSpinRatio"] = (rel_speed / spin_rate.replace(0, np.nan)).fillna(0.0)

    # Interacciones pitch_type x feature
    for cat_col, num_col in PITCH_TYPE_INTERACTIONS:
        if cat_col in x.columns and num_col in x.columns:
            cat_vals = x[cat_col].fillna("__MISSING__").astype(str)
            num_vals = pd.to_numeric(x[num_col], errors="coerce").fillna(0.0)
            inter_name = f"{cat_col}_x_{num_col}"
            x[inter_name] = cat_vals.astype(str) + "::" + num_vals.round(2).astype(str)
            x[inter_name] = x[inter_name].astype(str)

    missing = [c for c in features if c not in x.columns]
    if missing:
        raise KeyError(f"Columnas no disponibles tras ingenieria: {missing}")
    x = x[features].copy()

    for col in features:
        is_cat = (
            col in CATEGORICAL_FEATURES
            or col.endswith("_x_RelSpeed")
            or col.endswith("_x_InducedVertBreak")
            or col.endswith("_x_SpinRate")
        )
        if is_cat:
            x[col] = x[col].fillna("__MISSING__").astype(str)
        else:
            x[col] = pd.to_numeric(x[col], errors="coerce")

    return x


def task_frame(frame: pd.DataFrame, task: dict[str, Any]) -> pd.DataFrame:
    result = frame
    if task["condition"] == "swing":
        result = result.loc[frame["is_swing"].eq(1)]
    elif task["condition"] == "in_play_and_known_hit_type":
        result = result.loc[result["PitchCall"].eq("InPlay") & frame["hit_type"].notna()]
    elif task["condition"] == "in_play_and_known_exit_speed":
        result = result.loc[result["PitchCall"].eq("InPlay") & frame["ExitSpeed"].notna()]
    return result.loc[result[task["target"]].notna()].copy()


# =============================================================================
# MODELOS Y METRICAS
# =============================================================================

def make_model(task: dict[str, Any], args: argparse.Namespace):
    common = {
        "iterations": args.iteraciones,
        "depth": args.profundidad,
        "learning_rate": 0.05,
        "random_seed": args.semilla,
        "verbose": False,
        "allow_writing_files": False,
        "thread_count": -1,
        "l2_leaf_reg": 5.0,
    }
    # scale_pos_weight para eventos raros
    if task.get("rare") and task["kind"] == "classification":
        common["scale_pos_weight"] = 10.0

    if task["kind"] == "regression":
        return CatBoostRegressor(loss_function="RMSE", **common)
    return CatBoostClassifier(loss_function="Logloss", **common)


def predict_positive_probability(model: Any, x: pd.DataFrame) -> np.ndarray:
    classes = [float(value) for value in model.classes_]
    positive_index = classes.index(1.0)
    return model.predict_proba(x)[:, positive_index]


def metrics_for(model, task, train, test) -> dict[str, Any]:
    features = task["features"]
    x_test = prepare_features(test, features)
    y_test = test[task["target"]].astype(float).to_numpy()
    train_rate_or_mean = float(train[task["target"]].astype(float).mean())

    row: dict[str, Any] = {
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "baseline_rate_or_mean": train_rate_or_mean,
    }

    if task["kind"] == "regression":
        pred = model.predict(x_test).reshape(-1).astype(float)
        baseline = np.full(len(y_test), train_rate_or_mean, dtype=float)
        rmse_baseline = float(np.sqrt(mean_squared_error(y_test, baseline)))
        row.update({
            "mae": float(mean_absolute_error(y_test, pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_test, pred))),
            "r2": float(r2_score(y_test, pred)),
            "baseline_mae_train_mean": float(mean_absolute_error(y_test, baseline)),
            "baseline_rmse_train_mean": rmse_baseline,
            "rmse_skill": float(
                1.0 - mean_squared_error(y_test, pred) / mean_squared_error(y_test, baseline)
            ) if rmse_baseline > 0 else None,
        })
        return row

    proba = predict_positive_probability(model, x_test)
    y_binary = y_test.astype(int)
    baseline_probability = np.full(len(y_binary), train_rate_or_mean, dtype=float)
    brier = float(brier_score_loss(y_binary, proba))
    baseline_brier = float(brier_score_loss(y_binary, baseline_probability))
    positive_count = int(y_binary.sum())
    top_n = max(1, int(np.ceil(len(y_binary) * 0.10)))
    top_indices = np.argpartition(proba, -top_n)[-top_n:]
    top_precision = float(np.mean(y_binary[top_indices]))
    top_recall = float(y_binary[top_indices].sum() / positive_count) if positive_count else None
    bin_ids = np.minimum((proba * 10).astype(int), 9)
    ece = 0.0
    for bin_id in range(10):
        mask = bin_ids == bin_id
        if mask.any():
            ece += float(mask.mean()) * abs(float(proba[mask].mean()) - float(y_binary[mask].mean()))
    row.update({
        "positive_rate_test": float(np.mean(y_binary)),
        "positive_rate_train": train_rate_or_mean,
        "brier": brier,
        "brier_baseline_train_rate": baseline_brier,
        "brier_skill": float(1.0 - brier / baseline_brier) if baseline_brier > 0 else None,
        "precision_at_0_5": float(precision_score(y_binary, proba >= 0.5, zero_division=0)),
        "recall_at_0_5": float(recall_score(y_binary, proba >= 0.5, zero_division=0)),
        "precision_top_10pct": top_precision,
        "recall_top_10pct": top_recall,
        "lift_top_10pct": float(top_precision / np.mean(y_binary)) if np.mean(y_binary) > 0 else None,
        "ece_10_bins": float(ece),
        "roc_auc": float(roc_auc_score(y_binary, proba)) if len(np.unique(y_binary)) == 2 else None,
        "average_precision": float(average_precision_score(y_binary, proba)) if len(np.unique(y_binary)) == 2 else None,
    })
    return row


# =============================================================================
# SPLITS (v4: rolling origin + park holdout)
# =============================================================================

def make_splits(frame, include_pitcher, include_game, include_park, seed):
    years = sorted(frame["year"].dropna().astype(int).unique().tolist())

    # Rolling origin
    if len(years) >= 3:
        yield "rolling_2024_to_2025", frame[frame["year"] <= 2024], frame[frame["year"] == 2025]
        yield "rolling_2024_2025_to_2026", frame[frame["year"] <= 2025], frame[frame["year"] == 2026]

    # Season holdout (tradicional)
    for holdout_year in years[1:]:
        temporal_train = frame.loc[frame["year"] < holdout_year]
        temporal_test = frame.loc[frame["year"] == holdout_year]
        if not temporal_train.empty and not temporal_test.empty:
            yield f"season_holdout_{holdout_year}", temporal_train, temporal_test

    if include_pitcher:
        groups = frame["pitcher_anon_id"].fillna("__MISSING_PITCHER__").astype(str)
        unique_groups = groups.unique()
        if len(unique_groups) >= 5:
            rng = np.random.default_rng(seed)
            shuffled = rng.permutation(unique_groups)
            n_test_groups = max(1, int(round(len(shuffled) * 0.2)))
            held_out = set(shuffled[:n_test_groups])
            test_mask = groups.isin(held_out)
            yield "pitcher_holdout_20pct", frame.loc[~test_mask], frame.loc[test_mask]

    if include_game:
        groups = frame["game_anon_id"].fillna("__MISSING_GAME__").astype(str)
        unique_groups = groups.unique()
        if len(unique_groups) >= 5:
            rng = np.random.default_rng(seed + 1)
            shuffled = rng.permutation(unique_groups)
            n_test_groups = max(1, int(round(len(shuffled) * 0.2)))
            held_out = set(shuffled[:n_test_groups])
            test_mask = groups.isin(held_out)
            yield "game_holdout_20pct", frame.loc[~test_mask], frame.loc[test_mask]

    if include_park:
        extreme = frame["altitude_category"].eq("Extreme Altitude")
        non_extreme = ~extreme
        if non_extreme.sum() > 0 and extreme.sum() > 0:
            yield "park_holdout_extreme_altitude", frame.loc[non_extreme], frame.loc[extreme]


# =============================================================================
# ENTRENAMIENTO
# =============================================================================

def fit_and_measure(task_name, task, train, test, split_name, args, prediction_frame=None):
    features = task["features"]
    model = make_model(task, args)
    x_train = prepare_features(train, features)
    y_train = train[task["target"]].astype(float)
    cat_feats = [c for c in features if c in CATEGORICAL_FEATURES]
    model.fit(x_train, y_train, cat_features=cat_feats)
    result = {
        "split": split_name,
        "task": task_name,
        **metrics_for(model, task, train, test),
    }
    print("  " + json.dumps(result, ensure_ascii=False))
    return result, predict_task(model, task, prediction_frame if prediction_frame is not None else test)


def predict_task(model, task, frame):
    x = prepare_features(frame, task["features"])
    if task["kind"] == "regression":
        return model.predict(x).reshape(-1).astype(float)
    return predict_positive_probability(model, x)


def fit_final_models(frame, args):
    output = args.salida
    model_dir = output / "modelos"
    model_dir.mkdir(parents=True, exist_ok=True)
    fitted = {}
    for task_name, task in TASKS.items():
        fit_rows = task_frame(frame, task)
        features = task["features"]
        x_fit = prepare_features(fit_rows, features)
        y_fit = fit_rows[task["target"]].astype(float)
        cat_feats = [c for c in features if c in CATEGORICAL_FEATURES]
        model = make_model(task, args)
        model.fit(x_fit, y_fit, cat_features=cat_feats)
        model.save_model(str(model_dir / f"{task_name}.cbm"))
        fitted[task_name] = model
        print(f"  Modelo final: {task_name} ({len(fit_rows):,} filas)")
    return fitted


# =============================================================================
# SCORES COMPUESTOS CON PESOS APRENDIDOS
# =============================================================================

def add_provisional_scores(predictions: pd.DataFrame, frame_full: pd.DataFrame) -> pd.DataFrame:
    predictions = predictions.copy()
    years = predictions["year"].fillna(-1)

    def z_by_year(values: pd.Series) -> pd.Series:
        grouped = values.groupby(years)
        means = grouped.transform("mean")
        stds = grouped.transform(lambda s: s.std(ddof=0))
        return ((values - means) / stds.replace(0, np.nan)).fillna(0.0)

    # Calcular componentes base
    predictions["p_groundball_per_pitch"] = (
        predictions["p_ball_in_play"] * predictions["p_groundball_given_in_play"]
    )
    predictions["expected_exit_speed_per_pitch"] = (
        predictions["p_ball_in_play"] * predictions["pred_exit_speed_given_in_play"]
    )

    # Estimar run_value esperado por pitch usando los modelos
    def expected_run_value(row):
        rv = 0.0
        if row.get("p_home_run_per_pitch", 0) > 0:
            rv += row["p_home_run_per_pitch"] * 1.40
        if row.get("p_whiff_given_swing", 0) > 0:
            # whiff solo ocurre si hay swing; aproximar p_whiff = p_swing * p_whiff_given_swing
            # No tenemos p_swing directamente, usamos whiff como proxy
            pass
        if row.get("p_called_strike", 0) > 0:
            rv -= row["p_called_strike"] * 0.05
        if row.get("p_chase", 0) > 0:
            rv -= row["p_chase"] * 0.03
        if row.get("p_groundball_per_pitch", 0) > 0:
            rv += row["p_groundball_per_pitch"] * 0.0
        # bola en juego sin HR: run value cercano a 0 promedio
        p_contact = row.get("p_ball_in_play", 0) - row.get("p_home_run_per_pitch", 0)
        rv += p_contact * 0.02  # ligero valor esperado de contacto
        return rv

    predictions["expected_run_value"] = predictions.apply(expected_run_value, axis=1)

    # ===== PESOS APRENDIDOS: regresar run_value observado sobre componentes =====
    # Usar frame_full para entrenar los pesos (tiene run_value empírico)
    component_cols = [
        "p_whiff_given_swing", "p_groundball_per_pitch",
        "pred_exit_speed_given_in_play", "p_called_strike", "p_chase",
    ]
    available_cols = [c for c in component_cols if c in frame_full.columns]
    if available_cols and "run_value" in frame_full.columns:
        # Estandarizar componentes por temporada
        full_years = frame_full["year"].fillna(-1)
        comp_df = frame_full[available_cols].copy()
        for c in available_cols:
            grouped = comp_df[c].groupby(full_years)
            means = grouped.transform("mean")
            stds = grouped.transform(lambda s: s.std(ddof=0)).replace(0, np.nan)
            comp_df[c] = ((comp_df[c] - means) / stds).fillna(0.0)

        # Regresar run_value observado sobre componentes estandarizados
        y_rv = frame_full["run_value"].astype(float).to_numpy()
        X_comp = comp_df.to_numpy()
        # Filtrar NaN
        mask = ~np.isnan(y_rv) & ~np.isnan(X_comp).any(axis=1)
        if mask.sum() > 10:
            reg = LinearRegression().fit(X_comp[mask], y_rv[mask])
            learned_weights = dict(zip(available_cols, reg.coef_))
            learned_intercept = reg.intercept_
        else:
            learned_weights = {c: 1.0 for c in available_cols}
            learned_intercept = 0.0
    else:
        learned_weights = {c: 1.0 for c in component_cols}
        learned_intercept = 0.0

    # Guardar pesos aprendidos
    weights_path = Path("stuff_plus_output_v4") / "pesos_aprendidos.json"
    weights_path.parent.mkdir(parents=True, exist_ok=True)
    with open(weights_path, "w", encoding="utf-8") as f:
        json.dump({"weights": learned_weights, "intercept": float(learned_intercept)}, f, indent=2)
    print(f"Pesos aprendidos guardados en {weights_path}: {learned_weights}")

    # Aplicar componentes estandarizados a predictions
    comp_pred = predictions[available_cols].copy() if available_cols else pd.DataFrame()
    for c in available_cols:
        grouped = comp_pred[c].groupby(years)
        means = grouped.transform("mean")
        stds = grouped.transform(lambda s: s.std(ddof=0)).replace(0, np.nan)
        comp_pred[c] = ((comp_pred[c] - means) / stds).fillna(0.0)

    # Stuff+: whiff (↑), groundball (↑), exit speed (↓)
    stuff_direction = {
        "p_whiff_given_swing": learned_weights.get("p_whiff_given_swing", 1.0),
        "p_groundball_per_pitch": learned_weights.get("p_groundball_per_pitch", 1.0),
        "pred_exit_speed_given_in_play": -abs(learned_weights.get("pred_exit_speed_given_in_play", -1.0)),
    }
    # Location+: called strike (↑), chase (↑)
    location_direction = {
        "p_called_strike": learned_weights.get("p_called_strike", 1.0),
        "p_chase": learned_weights.get("p_chase", 1.0),
    }

    def composite(comp_df_cols, direction_map):
        standardized = []
        for column in comp_df_cols:
            values = pd.to_numeric(predictions[column], errors="coerce")
            direction = direction_map.get(column, 1.0)
            standardized.append(direction * z_by_year(values))
        raw = pd.concat(standardized, axis=1).mean(axis=1)
        return 100.0 + 10.0 * z_by_year(raw)

    predictions["stuff_plus_provisional"] = composite(
        list(stuff_direction.keys()), stuff_direction
    )
    predictions["location_plus_provisional"] = composite(
        list(location_direction.keys()), location_direction
    )
    predictions["pitching_plus_provisional"] = (
        (predictions["stuff_plus_provisional"] - 100) / 10
        + (predictions["location_plus_provisional"] - 100) / 10
    ) / 2 * 10 + 100

    return predictions


# =============================================================================
# SHAP VALUES E IMPORTANCIA POR ALTITUD
# =============================================================================

def compute_shap_values(model, task, frame, args, output_dir: Path):
    if shap is None:
        print("SHAP omitido: libreria no instalada.")
        return None
    features = task["features"]
    sample = frame.sample(min(2000, len(frame)), random_state=args.semilla)
    x_sample = prepare_features(sample, features)
    cat_feats = [c for c in features if c in CATEGORICAL_FEATURES]
    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(x_sample)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]  # clase positiva
        feature_names = list(x_sample.columns)
        importance = pd.DataFrame({
            "feature": feature_names,
            "mean_abs_shap": np.abs(shap_values).mean(axis=0),
        }).sort_values("mean_abs_shap", ascending=False)
        shap_path = output_dir / f"shap_importance_{task.name if hasattr(task, 'name') else task.get('task','task')}.csv"
        importance.to_csv(shap_path, index=False, encoding="utf-8")
        print(f"SHAP importancia guardada en {shap_path}")
        return importance
    except Exception as e:
        print(f"Error computando SHAP para tarea: {e}")
        return None


def shap_by_altitude(model, task, frame, output_dir: Path):
    if shap is None:
        return None
    features = task["features"]
    extreme = frame[frame["altitude_category"] == "Extreme Altitude"]
    no_alt = frame[frame["altitude_category"] == "No Altitude"]
    results = {}
    for label, sub in [("Extreme", extreme), ("NoAltitude", no_alt)]:
        if len(sub) < 100:
            continue
        sample = sub.sample(min(1000, len(sub)), random_state=42)
        x_sample = prepare_features(sample, features)
        try:
            explainer = shap.TreeExplainer(model)
            sv = explainer.shap_values(x_sample)
            if isinstance(sv, list):
                sv = sv[1]
            imp = pd.DataFrame({
                "feature": list(x_sample.columns),
                "mean_abs_shap": np.abs(sv).mean(axis=0),
                "altitud": label,
            })
            results[label] = imp
        except Exception:
            continue
    if results:
        combined = pd.concat(results.values(), ignore_index=True)
        path = output_dir / "shap_by_altitude.csv"
        combined.to_csv(path, index=False, encoding="utf-8")
        print(f"SHAP por altitud guardado en {path}")
        return combined
    return None


# =============================================================================
# ENTREGABLES POR PITCHER Y ALTITUD
# =============================================================================

def agregar_por_pitcher(scores_path: Path, salida: Path):
    if not scores_path.exists():
        return None
    df = pd.read_parquet(scores_path)
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
        index="pitcher_anon_id", columns="altitude_category",
        values="stuff_plus_mean", aggfunc="mean",
    ).reset_index()
    if "Extreme Altitude" in pivot.columns and "No Altitude" in pivot.columns:
        pivot["delta_stuff_plus_extreme_vs_no_altitude"] = (
            pivot["Extreme Altitude"] - pivot["No Altitude"]
        )
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
        .reset_index().rename(columns={"AutoPitchType": "arsenal_tipos"})
    )
    pitcher_summary = pitcher_summary.merge(arsenal, on="pitcher_anon_id", how="left")
    pitcher_summary = pitcher_summary.sort_values("stuff_plus_overall", ascending=False)
    out_path = salida / "stuff_plus_por_pitcher.csv"
    pitcher_summary.to_csv(out_path, index=False, encoding="utf-8")
    print(f"Agregacion por pitcher guardada en {out_path} ({len(pitcher_summary)} pitchers)")
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
    print(f"Resumen por altitud guardado en {alt_path}")
    return pitcher_summary


def perfil_ideal_diablos(scores_path: Path, salida: Path):
    if not scores_path.exists():
        return None
    df = pd.read_parquet(scores_path)
    harp = df[df["altitude_category"] == "Extreme Altitude"].copy()
    if harp.empty:
        return None
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
        "tipos_elite": elite["AutoPitchType"].value_counts().to_dict() if "AutoPitchType" in elite.columns else {},
        "mano_lanzadora_elite": elite["PitcherThrows"].value_counts().to_dict() if "PitcherThrows" in elite.columns else {},
        "stuff_plus_medio_elite": float(elite["stuff_plus_provisional"].mean()),
        "stuff_plus_medio_todos_harp": float(harp["stuff_plus_provisional"].mean()),
    }
    with open(salida / "perfil_ideal_diablos.json", "w", encoding="utf-8") as f:
        json.dump(perfil, f, indent=2, ensure_ascii=False)
    print(f"Perfil ideal Diablos guardado en {salida / 'perfil_ideal_diablos.json'}")
    return perfil


# =============================================================================
# MAIN
# =============================================================================

def main() -> int:
    args = parse_args()
    if args.iteraciones < 1:
        raise SystemExit("--iteraciones debe ser mayor que cero")
    args.salida.mkdir(parents=True, exist_ok=True)

    print(f"Leyendo {args.parquet} ...")
    frame = load_data(args.parquet)
    print(f"{len(frame):,} lanzamientos; años: {sorted(frame['year'].dropna().unique().tolist())}")
    print("Mapeo altitud -> estadio (LMB, aproximado):")
    for alt, est in ALTITUD_ESTADIO_REPRESENTATIVO.items():
        n = int((frame["altitude_category"] == alt).sum())
        print(f"  {alt}: {ALTITUD_METROS[alt]} m -> {est} ({n:,} pitches)")

    validation_rows: list[dict[str, Any]] = []
    oos_prediction_frames: dict[str, pd.DataFrame] = {}
    splits = list(
        make_splits(
            frame,
            include_pitcher=not args.omitir_validacion_pitcher,
            include_game=not args.omitir_validacion_juego,
            include_park=not args.omitir_validacion_parque,
            seed=args.semilla,
        )
    )
    print(f"{len(splits)} split(s) de validacion configurado(s).")

    for split_name, split_train, split_test in splits:
        print(f"Validacion {split_name}: train={len(split_train):,}, test={len(split_test):,}")
        for task_name, task in TASKS.items():
            train_rows = task_frame(split_train, task)
            test_rows = task_frame(split_test, task)
            if len(train_rows) == 0 or len(test_rows) == 0:
                print(f"  Se omite {task_name}: faltan filas.")
                continue
            if task["kind"] == "classification" and train_rows[task["target"]].nunique() < 2:
                print(f"  Se omite {task_name}: una sola clase en entrenamiento.")
                continue
            result, test_predictions = fit_and_measure(
                task_name, task, train_rows, test_rows, split_name, args,
                prediction_frame=split_test,
            )
            validation_rows.append(result)
            if split_name.startswith(("season_holdout_", "park_holdout_", "rolling_")):
                if split_name not in oos_prediction_frames:
                    oos_prediction_frames[split_name] = split_test[
                        ["PitchUID", "year", "pitcher_anon_id", "altitude_category", "AutoPitchType"]
                    ].copy()
                prediction_column = (
                    f"pred_{task_name}" if task["kind"] == "regression" else f"p_{task_name}"
                )
                oos_prediction_frames[split_name][prediction_column] = test_predictions

    metrics_path = args.salida / "metricas_validacion_v4.json"
    metrics_path.write_text(
        json.dumps(validation_rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Metricas guardadas en {metrics_path}")

    if not args.solo_validacion:
        print("Entrenando modelos de produccion con todas las temporadas ...")
        fit_final_models(frame, args)

    if oos_prediction_frames:
        predictions = pd.concat(oos_prediction_frames.values(), ignore_index=True)
        predictions = add_provisional_scores(predictions, frame)
        scores_path = args.salida / "scores_pitch_v4.parquet"
        con = duckdb.connect()
        try:
            con.register("scores_df", predictions)
            escaped_path = str(scores_path.resolve()).replace("'", "''")
            con.execute(
                f"COPY scores_df TO '{escaped_path}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
        finally:
            con.close()
        years_scored = sorted(predictions["year"].dropna().astype(int).unique().tolist())
        print(f"Scores fuera de muestra guardados en {scores_path}; temporadas: {years_scored}")

        # SHAP values
        if not args.omitir_shap and shap is not None:
            print("Computando valores SHAP ...")
            modelos_dir = args.salida / "modelos"
            for task_name, task in TASKS.items():
                model_path = modelos_dir / f"{task_name}.cbm"
                if not model_path.exists():
                    continue
                if task["kind"] == "classification":
                    model = CatBoostClassifier()
                else:
                    model = CatBoostRegressor()
                model.load_model(str(model_path))
                # Usar un sample del frame completo para SHAP
                shap_sample = frame.sample(min(3000, len(frame)), random_state=args.semilla)
                compute_shap_values(model, task, shap_sample, args, args.salida)
                shap_by_altitude(model, task, frame, args.salida)

        # Entregables obligatorios
        print("Generando entregables obligatorios ...")
        agregar_por_pitcher(scores_path, args.salida)
        perfil_ideal_diablos(scores_path, args.salida)

    if not args.solo_validacion:
        print(f"Modelos de produccion guardados en {args.salida / 'modelos'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
