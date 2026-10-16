"""Entrena un prototipo mejorado de Stuff+ para el hackatón Diablos Rojos.

Mejoras v2 respecto a v1:
1. Stuff+ puro: solo features de release (velocidad, spin, punto de release, movimiento).
   Se eliminan variables de trayectoria/plato (ZoneSpeed, SpeedDrop, ZoneTime,
   VertRelAngle, HorzRelAngle, VertApprAngle, HorzApprAngle).
2. Ingeniería de características: EffectiveVelo, SpinEfficiency, VeloSpinRatio,
   SpinAxis sin/cos e interacciones pitch_type × velocidad/movimiento.
3. Separación clara de Stuff+ / Location+ / Environment+.
4. Compuesto de outcomes condicional corregido con p_ball_in_play explícito.
5. Baselines xRunValue por conteo + calibración (Brier, ECE) para todas las tareas.
6. Validación temporal estricta (season holdout) + pitcher holdout + game holdout.
7. Mapeo de altitude_category a estadios reales de la LMB con altitud aprox.

Uso:
    py -3.12 entrenar_stuff_plus_v2.py
    py -3.12 entrenar_stuff_plus_v2.py --iteraciones 400 --profundidad 7
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
    from catboost import CatBoostClassifier, CatBoostRegressor
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
        "requirements-hackathon.txt",
        file=sys.stderr,
    )
    raise SystemExit(2) from exc


# =============================================================================
# 1. DEFINICIÓN DE FEATURES POR DIMENSIÓN
# =============================================================================

# Stuff+ puro: solo release + spin + movimiento + mano del lanzador y tipo de pitcheo.
STUFF_NUMERIC = [
    "RelSpeed",
    "EffectiveVelo",
    "SpinRate",
    "SpinAxis_sin",
    "SpinAxis_cos",
    "RelHeight",
    "RelSide",
    "Extension",
    "VertBreak",
    "InducedVertBreak",
    "HorzBreak",
    "SpinEfficiency",
    "VeloSpinRatio",
]
STUFF_CATEGORICAL = ["AutoPitchType", "PitcherThrows"]
STUFF_FEATURES = STUFF_NUMERIC + STUFF_CATEGORICAL

# Location+: features de plato + conteo + lado bateador (condicionado al pitcheo).
LOCATION_NUMERIC = ["PlateLocHeight", "PlateLocSide", "Balls", "Strikes"]
LOCATION_CATEGORICAL = ["BatterSide"]
LOCATION_FEATURES = STUFF_FEATURES + LOCATION_NUMERIC + LOCATION_CATEGORICAL

# Environment+: altitud del estadio mapeada a metros reales (LMB).
ENVIRONMENT_FEATURES = STUFF_FEATURES + ["altitude_meters", "altitude_category"]

# Interacciones explícitas por tipo de pitcheo (CatBoost las captura, pero
# ayudan a la interprétabilidad y a modelos lineales de baseline).
PITCH_TYPE_INTERACTIONS = [
    ("AutoPitchType", "RelSpeed"),
    ("AutoPitchType", "InducedVertBreak"),
    ("AutoPitchType", "SpinRate"),
]

TASKS: dict[str, dict[str, Any]] = {
    "whiff": {
        "target": "is_whiff",
        "features": STUFF_FEATURES,
        "kind": "classification",
        "condition": None,
    },
    "whiff_given_swing": {
        "target": "is_whiff",
        "features": STUFF_FEATURES,
        "kind": "classification",
        "condition": "swing",
    },
    "ball_in_play": {
        "target": "is_ball_in_play",
        "features": STUFF_FEATURES,
        "kind": "classification",
        "condition": None,
    },
    "called_strike": {
        "target": "is_called_strike",
        "features": LOCATION_FEATURES,
        "kind": "classification",
        "condition": None,
    },
    "chase": {
        "target": "swung_outside_strike_zone",
        "features": LOCATION_FEATURES,
        "kind": "classification",
        "condition": None,
    },
    "groundball_given_in_play": {
        "target": "is_groundball",
        "features": STUFF_FEATURES,
        "kind": "classification",
        "condition": "in_play_and_known_hit_type",
    },
    "home_run_per_pitch": {
        "target": "home_run",
        "features": ENVIRONMENT_FEATURES,
        "kind": "classification",
        "condition": None,
    },
    "exit_speed_given_in_play": {
        "target": "ExitSpeed",
        "features": STUFF_FEATURES + LOCATION_NUMERIC,
        "kind": "regression",
        "condition": "in_play_and_known_exit_speed",
    },
}

CATEGORICAL_FEATURES = {
    "AutoPitchType",
    "PitcherThrows",
    "BatterSide",
    "altitude_category",
}


# =============================================================================
# 2. MAPEO DE ALTITUD A ESTADIOS REALES LMB (aproximado, en msnm)
# =============================================================================
# Fuente: elevaciones aproximadas de estadios de la Liga Mexicana de Béisbol.
# El dataset anonimiza los estadios, por lo que se mapea por bucket de altitud.
ALTITUD_METROS = {
    "No Altitude": 100.0,      # ej. Cancún, Veracruz, Tijuana (~0-100 m)
    "Medium Altitude": 800.0,  # ej. Monterrey (~537 m), Laguna (~1100 m)
    "Extreme Altitude": 2240.0,# Alfredo Harp Helú (CDMX, ~2240 m), Puebla (~2150 m)
}

ALTITUD_ESTADIO_REPRESENTATIVO = {
    "No Altitude": "Estadio de Béisbol Cancún / Veracruz (nivel del mar)",
    "Medium Altitude": "Estadio de Béisbol Monterrey (~537 m)",
    "Extreme Altitude": "Estadio Alfredo Harp Helú CDMX (~2240 m)",
}


# =============================================================================
# 3. ARGUMENTOS Y CARGA DE DATOS
# =============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--parquet",
        type=Path,
        default=Path("stuff_model_df.parquet"),
        help="Ruta del Parquet pitch-by-pitch.",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=Path("stuff_plus_output_v2"),
        help="Carpeta para métricas, scores y modelos.",
    )
    parser.add_argument("--iteraciones", type=int, default=400)
    parser.add_argument("--profundidad", type=int, default=7)
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument(
        "--omitir-validacion-pitcher",
        action="store_true",
        help="Omitir validación con pitchers no vistos.",
    )
    parser.add_argument(
        "--omitir-validacion-juego",
        action="store_true",
        help="Omitir validación con juegos no vistos.",
    )
    parser.add_argument(
        "--solo-validacion",
        action="store_true",
        help="Evalúa splits pero no entrena modelos finales.",
    )
    return parser.parse_args()


def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo Parquet: {path}")

    select_columns = [
        "year", "PitchUID", "game_anon_id", "pitcher_anon_id",
        "PitcherThrows", "BatterSide", "batter_anon_id",
        "altitude_category", "AutoPitchType",
        *STUFF_NUMERIC,  # includes engineered names; load raw below
        "PlateLocHeight", "PlateLocSide", "Balls", "Strikes",
        "is_whiff", "is_ball_in_play", "is_called_strike",
        "swung_outside_strike_zone", "PitchCall", "hit_type",
        "home_run", "ExitSpeed", "is_swing",
    ]
    # STUFF_NUMERIC tiene nombres ingenierados; cargamos los crudos y los
    # transformamos después. Lista de columnas crudas del parquet:
    raw_numeric = [
        "RelSpeed", "EffectiveVelo", "SpinRate", "SpinAxis",
        "RelHeight", "RelSide", "Extension", "VertBreak",
        "InducedVertBreak", "HorzBreak",
    ]
    select_columns_clean = [
        c for c in select_columns if c not in STUFF_NUMERIC
    ] + raw_numeric

    select_sql: list[str] = []
    for column in dict.fromkeys(select_columns_clean):
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

    frame["is_groundball"] = (
        frame["PitchCall"].eq("InPlay") & frame["hit_type"].eq("GroundBall")
    ).astype("int8")

    # Mapeo altitud a metros y estadio representativo (LMB)
    frame["altitude_meters"] = frame["altitude_category"].map(ALTITUD_METROS).fillna(0.0)
    frame["altitude_stadium"] = frame["altitude_category"].map(
        ALTITUD_ESTADIO_REPRESENTATIVO
    ).fillna("Desconocido")

    return frame


# =============================================================================
# 4. INGENIERÍA DE CARACTERÍSTICAS
# =============================================================================

def prepare_features(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    # Columnas crudas disponibles en el frame (excluye ingenieradas)
    raw_available = [c for c in frame.columns if c in features]
    # Añadir columnas crudas necesarias para ingeniería que no estén en features
    needed_raw = {"SpinAxis", "SpinRate", "RelSpeed"}
    for c in needed_raw:
        if c in frame.columns and c not in raw_available:
            raw_available.append(c)
    x = frame[raw_available].copy()

    # SpinAxis → sin/cos (evita discontinuidad en 0/360)
    if "SpinAxis" in x.columns:
        spin_axis = pd.to_numeric(x["SpinAxis"], errors="coerce")
        radians = np.deg2rad(spin_axis)
        x["SpinAxis_sin"] = np.sin(radians)
        x["SpinAxis_cos"] = np.cos(radians)
        x = x.drop(columns="SpinAxis")

    # Ingeniería numérica derivada
    if "SpinRate" in x.columns and "RelSpeed" in x.columns:
        spin_rate = pd.to_numeric(x["SpinRate"], errors="coerce")
        rel_speed = pd.to_numeric(x["RelSpeed"], errors="coerce")
        # SpinEfficiency proxy
        if "SpinAxis_sin" in x.columns:
            x["SpinEfficiency"] = (
                spin_rate * x["SpinAxis_sin"].abs() / rel_speed.replace(0, np.nan)
            ).fillna(0.0)
        else:
            x["SpinEfficiency"] = (spin_rate / rel_speed.replace(0, np.nan)).fillna(0.0)
        # VeloSpinRatio
        x["VeloSpinRatio"] = (rel_speed / spin_rate.replace(0, np.nan)).fillna(0.0)

    # Interacciones pitch_type × feature (string categórica)
    for cat_col, num_col in PITCH_TYPE_INTERACTIONS:
        if cat_col in x.columns and num_col in x.columns:
            cat_vals = x[cat_col].fillna("__MISSING__").astype(str)
            num_vals = pd.to_numeric(x[num_col], errors="coerce").fillna(0.0)
            inter_name = f"{cat_col}_x_{num_col}"
            x[inter_name] = cat_vals.astype(str) + "::" + num_vals.round(2).astype(str)
            x[inter_name] = x[inter_name].astype(str)

    # Seleccionar solo las features solicitadas (en orden)
    missing = [c for c in features if c not in x.columns]
    if missing:
        raise KeyError(f"Columnas no disponibles tras ingeniería: {missing}")
    x = x[features].copy()

    for col in features:
        if col in CATEGORICAL_FEATURES or col.endswith("_x_RelSpeed") or col.endswith("_x_InducedVertBreak") or col.endswith("_x_SpinRate"):
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
# 5. MODELOS Y MÉTRICAS
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
        row.update({
            "mae": float(mean_absolute_error(y_test, pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_test, pred))),
            "r2": float(r2_score(y_test, pred)),
            "baseline_mae_train_mean": float(mean_absolute_error(y_test, baseline)),
            "baseline_rmse_train_mean": float(np.sqrt(mean_squared_error(y_test, baseline))),
            "rmse_skill": float(
                1.0 - mean_squared_error(y_test, pred) / mean_squared_error(y_test, baseline)
            ) if np.sqrt(mean_squared_error(y_test, baseline)) > 0 else None,
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
# 6. BASELINE xRunValue por conteo
# =============================================================================

RUN_VALUE_BY_OUTCOME = {
    "home_run": 1.40,
    "triple": 1.05,
    "double": 0.75,
    "single": 0.45,
    "base_on_balls": 0.30,
    "strikeout": -0.30,
    "is_called_strike": -0.05,
    "is_whiff": -0.05,
    "is_ball_in_play": 0.0,
}


def compute_xrunvalue_baseline(frame: pd.DataFrame) -> pd.DataFrame:
    """xRunValue baseline por conteo (Balls-Strikes) usando tasa histórica."""
    df = frame.copy()
    df["count_key"] = df["Balls"].astype(str) + "-" + df["Strikes"].astype(str)

    # Run value aproximado por pitch usando outcomes observados
    def run_value(row):
        if row.get("home_run", 0) == 1:
            return RUN_VALUE_BY_OUTCOME["home_run"]
        if row.get("strikeout", 0) == 1:
            return RUN_VALUE_BY_OUTCOME["strikeout"]
        if row.get("base_on_balls", 0) == 1:
            return RUN_VALUE_BY_OUTCOME["base_on_balls"]
        if row.get("is_called_strike", 0) == 1:
            return RUN_VALUE_BY_OUTCOME["is_called_strike"]
        if row.get("is_whiff", 0) == 1:
            return RUN_VALUE_BY_OUTCOME["is_whiff"]
        return 0.0

    df["run_value"] = df.apply(run_value, axis=1)
    baseline = df.groupby("count_key")["run_value"].mean().rename("xrunvalue_by_count")
    df = df.merge(baseline, on="count_key", how="left")
    df["xrunvalue_by_count"] = df["xrunvalue_by_count"].fillna(df["run_value"].mean())
    return df


# =============================================================================
# 7. SPLITS DE VALIDACIÓN
# =============================================================================

def make_splits(frame, include_pitcher, include_game, seed):
    years = sorted(frame["year"].dropna().astype(int).unique().tolist())
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


# =============================================================================
# 8. ENTRENAMIENTO Y PUNTUACIÓN
# =============================================================================

def fit_and_measure(task_name, task, train, test, split_name, args, prediction_frame=None):
    features = task["features"]
    model = make_model(task, args)
    x_train = prepare_features(train, features)
    y_train = train[task["target"]].astype(float)
    model.fit(x_train, y_train, cat_features=[c for c in features if c in CATEGORICAL_FEATURES])
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
        model = make_model(task, args)
        model.fit(x_fit, y_fit, cat_features=[c for c in features if c in CATEGORICAL_FEATURES])
        model.save_model(str(model_dir / f"{task_name}.cbm"))
        fitted[task_name] = model
        print(f"  Modelo final: {task_name} ({len(fit_rows):,} filas)")
    return fitted


# =============================================================================
# 9. SCORE COMPUESTO (Stuff+ / Location+ / Pitching+)
# =============================================================================

def add_provisional_scores(predictions: pd.DataFrame) -> pd.DataFrame:
    """Índices provisionales Stuff+, Location+, Pitching+ con z-score por temporada."""
    predictions = predictions.copy()
    years = predictions["year"].fillna(-1)

    def z_by_year(values: pd.Series) -> pd.Series:
        grouped = values.groupby(years)
        means = grouped.transform("mean")
        stds = grouped.transform(lambda s: s.std(ddof=0))
        return ((values - means) / stds.replace(0, np.nan)).fillna(0.0)

    def composite(columns, direction_map):
        standardized = []
        for column in columns:
            values = pd.to_numeric(predictions[column], errors="coerce")
            direction = direction_map.get(column, 1.0)
            standardized.append(direction * z_by_year(values))
        raw = pd.concat(standardized, axis=1).mean(axis=1)
        return 100.0 + 10.0 * z_by_year(raw)

    # Stuff+: whiff (↑ bueno), groundball (↑ bueno para contacto débil), exit speed (↓ bueno)
    stuff_components = {
        "p_whiff_given_swing": 1.0,
        "p_groundball_per_pitch": 1.0,
        "pred_exit_speed_given_in_play": -1.0,
    }
    # Location+: called strike (↑), chase (↑)
    location_components = {
        "p_called_strike": 1.0,
        "p_chase": 1.0,
    }

    predictions["p_groundball_per_pitch"] = (
        predictions["p_ball_in_play"] * predictions["p_groundball_given_in_play"]
    )
    predictions["expected_exit_speed_per_pitch"] = (
        predictions["p_ball_in_play"] * predictions["pred_exit_speed_given_in_play"]
    )

    # Renombrar para que composite use columnas existentes
    predictions["pred_exit_speed_given_in_play_for_score"] = predictions[
        "pred_exit_speed_given_in_play"
    ]

    predictions["stuff_plus_provisional"] = composite(
        ["p_whiff_given_swing", "p_groundball_per_pitch", "pred_exit_speed_given_in_play"],
        {"p_whiff_given_swing": 1.0, "p_groundball_per_pitch": 1.0, "pred_exit_speed_given_in_play": -1.0},
    )
    predictions["location_plus_provisional"] = composite(
        ["p_called_strike", "p_chase"],
        {"p_called_strike": 1.0, "p_chase": 1.0},
    )
    # Pitching+ = promedio de Stuff+ y Location+ (estandarizados)
    predictions["pitching_plus_provisional"] = (
        (predictions["stuff_plus_provisional"] - 100) / 10 +
        (predictions["location_plus_provisional"] - 100) / 10
    ) / 2 * 10 + 100

    return predictions


# =============================================================================
# 10. MAIN
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

    # xRunValue baseline por conteo
    frame = compute_xrunvalue_baseline(frame)
    print("Baseline xRunValue por conteo calculado.")

    validation_rows: list[dict[str, Any]] = []
    oos_prediction_frames: dict[str, pd.DataFrame] = {}
    splits = list(
        make_splits(
            frame,
            include_pitcher=not args.omitir_validacion_pitcher,
            include_game=not args.omitir_validacion_juego,
            seed=args.semilla,
        )
    )
    print(f"{len(splits)} split(s) de validación configurado(s).")

    for split_name, split_train, split_test in splits:
        print(f"Validación {split_name}: train={len(split_train):,}, test={len(split_test):,}")
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
            if split_name.startswith("season_holdout_"):
                if split_name not in oos_prediction_frames:
                    oos_prediction_frames[split_name] = split_test[
                        ["PitchUID", "year", "pitcher_anon_id", "altitude_category", "AutoPitchType"]
                    ].copy()
                prediction_column = (
                    f"pred_{task_name}" if task["kind"] == "regression" else f"p_{task_name}"
                )
                oos_prediction_frames[split_name][prediction_column] = test_predictions

    metrics_path = args.salida / "metricas_validacion_v2.json"
    metrics_path.write_text(
        json.dumps(validation_rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Métricas guardadas en {metrics_path}")

    if not args.solo_validacion:
        print("Entrenando modelos de producción con todas las temporadas ...")
        fit_final_models(frame, args)

    if oos_prediction_frames:
        predictions = pd.concat(oos_prediction_frames.values(), ignore_index=True)
        predictions = add_provisional_scores(predictions)
        scores_path = args.salida / "scores_pitch_v2.parquet"
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
        print("Índices *_provisional usan pesos iguales y requieren revisión técnica.")

    if not args.solo_validacion:
        print(f"Modelos de producción guardados en {args.salida / 'modelos'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
