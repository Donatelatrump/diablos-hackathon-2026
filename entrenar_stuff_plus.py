"""Entrena un prototipo interpretable de Stuff+ para el hackatón Diablos Rojos.

Lee stuff_model_df.parquet, valida por temporada y por pitcher, y genera
modelos CatBoost, métricas y scores por lanzamiento. Los scores compuestos son
un punto de partida con pesos iguales; deben revisarse con el staff técnico.

Uso:
    py -3.14 entrenar_stuff_plus.py
    py -3.14 entrenar_stuff_plus.py --parquet ruta/datos.parquet --iteraciones 300
    py -3.14 entrenar_stuff_plus.py --omitir-validacion-pitcher
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
        r2_score,
        roc_auc_score,
    )
except ImportError as exc:
    missing = getattr(exc, "name", "una dependencia")
    print(
        f"Falta instalar {missing}. Ejecuta: py -3.14 -m pip install -r "
        "requirements-hackathon.txt",
        file=sys.stderr,
    )
    raise SystemExit(2) from exc


PHYSICAL_NUMERIC = [
    "RelSpeed",
    "EffectiveVelo",
    "ZoneSpeed",
    "SpinRate",
    "SpinAxis",
    "RelHeight",
    "RelSide",
    "Extension",
    "VertBreak",
    "InducedVertBreak",
    "HorzBreak",
    "VertRelAngle",
    "HorzRelAngle",
    "VertApprAngle",
    "HorzApprAngle",
    "SpeedDrop",
    "ZoneTime",
]
PHYSICAL_CATEGORICAL = ["AutoPitchType", "PitcherThrows"]
PHYSICAL_FEATURES = PHYSICAL_NUMERIC + PHYSICAL_CATEGORICAL

LOCATION_FEATURES = PHYSICAL_FEATURES + [
    "PlateLocHeight",
    "PlateLocSide",
    "Balls",
    "Strikes",
    "BatterSide",
]
ENVIRONMENT_FEATURES = PHYSICAL_FEATURES + ["altitude_category"]

# Cada especificación entrena una tarea distinta. Los modelos condicionales de
# groundball y exit speed se entrenan solo en lanzamientos que llegaron a InPlay.
TASKS: dict[str, dict[str, Any]] = {
    "whiff": {
        "target": "is_whiff",
        "features": PHYSICAL_FEATURES,
        "kind": "classification",
        "condition": None,
    },
    "ball_in_play": {
        "target": "is_ball_in_play",
        "features": ENVIRONMENT_FEATURES,
        "kind": "classification",
        "condition": None,
    },
    "called_strike": {
        "target": "is_called_strike",
        "features": LOCATION_FEATURES + ["altitude_category"],
        "kind": "classification",
        "condition": None,
    },
    "chase": {
        "target": "swung_outside_strike_zone",
        "features": LOCATION_FEATURES + ["altitude_category"],
        "kind": "classification",
        "condition": None,
    },
    "groundball_given_in_play": {
        "target": "is_groundball",
        "features": ENVIRONMENT_FEATURES,
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
        "features": ENVIRONMENT_FEATURES,
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
        default=Path("stuff_plus_output"),
        help="Carpeta para métricas, scores y modelos.",
    )
    parser.add_argument("--iteraciones", type=int, default=400)
    parser.add_argument("--profundidad", type=int, default=7)
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument(
        "--omitir-validacion-pitcher",
        action="store_true",
        help="Ahorra tiempo; por defecto también se valida con pitchers no vistos.",
    )
    parser.add_argument(
        "--solo-validacion",
        action="store_true",
        help="Evalúa los splits pero no vuelve a entrenar modelos finales.",
    )
    return parser.parse_args()


def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo Parquet: {path}")

    # EffectiveVelo está almacenada como texto en este Parquet; convertirla
    # explícitamente a número evita que CatBoost la trate como categoría.
    select_columns = [
        "year",
        "PitchUID",
        "game_anon_id",
        "pitcher_anon_id",
        "PitcherThrows",
        "BatterSide",
        "altitude_category",
        "AutoPitchType",
        *PHYSICAL_NUMERIC,
        "PlateLocHeight",
        "PlateLocSide",
        "Balls",
        "Strikes",
        "is_whiff",
        "is_ball_in_play",
        "is_called_strike",
        "swung_outside_strike_zone",
        "PitchCall",
        "hit_type",
        "home_run",
        "ExitSpeed",
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
            f"SELECT {', '.join(select_sql)} FROM read_parquet(?)", [str(path.resolve())]
        ).fetchdf()
    finally:
        con.close()

    frame["is_groundball"] = (
        frame["PitchCall"].eq("InPlay") & frame["hit_type"].eq("GroundBall")
    ).astype("int8")
    return frame


def prepare_features(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    x = frame[features].copy()
    for col in features:
        if col in CATEGORICAL_FEATURES:
            x[col] = x[col].fillna("__MISSING__").astype(str)
        else:
            x[col] = pd.to_numeric(x[col], errors="coerce")
    return x


def task_frame(frame: pd.DataFrame, task: dict[str, Any]) -> pd.DataFrame:
    result = frame
    if task["condition"] == "in_play_and_known_hit_type":
        result = result.loc[result["PitchCall"].eq("InPlay") & frame["hit_type"].notna()]
    elif task["condition"] == "in_play_and_known_exit_speed":
        result = result.loc[result["PitchCall"].eq("InPlay") & frame["ExitSpeed"].notna()]

    return result.loc[result[task["target"]].notna()].copy()


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


def metrics_for(
    model: Any,
    task: dict[str, Any],
    train: pd.DataFrame,
    test: pd.DataFrame,
) -> dict[str, Any]:
    features = task["features"]
    x_test = prepare_features(test, features)
    y_test = test[task["target"]].astype(float).to_numpy()
    pred = model.predict(x_test).reshape(-1).astype(float)

    row: dict[str, Any] = {
        "n_train": int(len(train)),
        "n_test": int(len(test)),
    }
    if task["kind"] == "regression":
        row.update(
            {
                "mae": float(mean_absolute_error(y_test, pred)),
                "rmse": float(np.sqrt(mean_squared_error(y_test, pred))),
                "r2": float(r2_score(y_test, pred)),
            }
        )
        return row

    proba_all = model.predict_proba(x_test)
    classes = list(model.classes_)
    positive_index = classes.index(1) if 1 in classes else classes.index(1.0)
    proba = proba_all[:, positive_index]
    y_binary = y_test.astype(int)
    row["positive_rate_test"] = float(np.mean(y_binary))
    row["brier"] = float(brier_score_loss(y_binary, proba))
    row["roc_auc"] = (
        float(roc_auc_score(y_binary, proba)) if len(np.unique(y_binary)) == 2 else None
    )
    row["average_precision"] = (
        float(average_precision_score(y_binary, proba))
        if len(np.unique(y_binary)) == 2
        else None
    )
    return row


def make_splits(frame: pd.DataFrame, include_pitcher: bool, seed: int):
    max_year = int(frame["year"].max())
    temporal_train = frame.loc[frame["year"] < max_year]
    temporal_test = frame.loc[frame["year"] == max_year]
    if not temporal_train.empty and not temporal_test.empty:
        yield f"season_holdout_{max_year}", temporal_train, temporal_test

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


def fit_and_measure(
    task_name: str,
    task: dict[str, Any],
    train: pd.DataFrame,
    test: pd.DataFrame,
    split_name: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
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
    return result


def fit_final_models(frame: pd.DataFrame, args: argparse.Namespace) -> tuple[dict[str, Any], pd.DataFrame]:
    output = args.salida
    model_dir = output / "modelos"
    model_dir.mkdir(parents=True, exist_ok=True)
    fitted: dict[str, Any] = {}
    predictions = pd.DataFrame(
        {
            "PitchUID": frame["PitchUID"],
            "year": frame["year"],
            "pitcher_anon_id": frame["pitcher_anon_id"],
            "altitude_category": frame["altitude_category"],
            "AutoPitchType": frame["AutoPitchType"],
        }
    )

    for task_name, task in TASKS.items():
        fit_rows = task_frame(frame, task)
        features = task["features"]
        x_fit = prepare_features(fit_rows, features)
        y_fit = fit_rows[task["target"]].astype(float)
        model = make_model(task, args)
        model.fit(x_fit, y_fit, cat_features=[c for c in features if c in CATEGORICAL_FEATURES])
        model.save_model(str(model_dir / f"{task_name}.cbm"))
        fitted[task_name] = model

        x_all = prepare_features(frame, features)
        if task["kind"] == "regression":
            predictions[f"pred_{task_name}"] = model.predict(x_all).reshape(-1)
        else:
            classes = list(model.classes_)
            positive_index = classes.index(1) if 1 in classes else classes.index(1.0)
            predictions[f"p_{task_name}"] = model.predict_proba(x_all)[:, positive_index]
        print(f"  Modelo final: {task_name} ({len(fit_rows):,} filas)")

    return fitted, predictions


def add_provisional_scores(predictions: pd.DataFrame) -> pd.DataFrame:
    """Agrega índices 100/10 con componentes estandarizados y pesos iguales."""
    stuff_components = {
        "p_whiff": 1.0,
        "p_groundball_given_in_play": 1.0,
        "pred_exit_speed_given_in_play": -1.0,
    }
    location_components = {
        "p_called_strike": 1.0,
        "p_chase": 1.0,
    }

    def composite(components: dict[str, float]) -> pd.Series:
        standardized = []
        for column, direction in components.items():
            values = pd.to_numeric(predictions[column], errors="coerce")
            std = values.std(ddof=0)
            if pd.isna(std) or std == 0:
                z = pd.Series(0.0, index=values.index)
            else:
                z = (values - values.mean()) / std
            standardized.append(direction * z)
        raw = sum(standardized) / len(standardized)
        raw_std = raw.std(ddof=0)
        if pd.isna(raw_std) or raw_std == 0:
            return pd.Series(100.0, index=raw.index)
        return 100.0 + 10.0 * (raw - raw.mean()) / raw_std

    predictions["stuff_plus_provisional"] = composite(stuff_components)
    predictions["location_plus_provisional"] = composite(location_components)
    return predictions


def main() -> int:
    args = parse_args()
    if args.iteraciones < 1:
        raise SystemExit("--iteraciones debe ser mayor que cero")
    args.salida.mkdir(parents=True, exist_ok=True)

    print(f"Leyendo {args.parquet} ...")
    frame = load_data(args.parquet)
    print(f"{len(frame):,} lanzamientos; años: {sorted(frame['year'].dropna().unique().tolist())}")

    validation_rows: list[dict[str, Any]] = []
    splits = list(
        make_splits(
            frame,
            include_pitcher=not args.omitir_validacion_pitcher,
            seed=args.semilla,
        )
    )
    for split_name, split_train, split_test in splits:
        print(f"Validación {split_name}: train={len(split_train):,}, test={len(split_test):,}")
        for task_name, task in TASKS.items():
            train_rows = task_frame(split_train, task)
            test_rows = task_frame(split_test, task)
            if len(train_rows) == 0 or len(test_rows) == 0:
                print(f"  Se omite {task_name}: faltan filas de entrenamiento o prueba.")
                continue
            if task["kind"] == "classification" and train_rows[task["target"]].nunique() < 2:
                print(f"  Se omite {task_name}: el entrenamiento tiene una sola clase.")
                continue
            validation_rows.append(
                fit_and_measure(
                    task_name,
                    task,
                    train_rows,
                    test_rows,
                    split_name,
                    args,
                )
            )

    metrics_path = args.salida / "metricas_validacion.json"
    metrics_path.write_text(json.dumps(validation_rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Métricas guardadas en {metrics_path}")

    if not args.solo_validacion:
        print("Entrenando modelos finales con todas las temporadas ...")
        _, predictions = fit_final_models(frame, args)
        predictions = add_provisional_scores(predictions)
        scores_path = args.salida / "scores_pitch.parquet"
        con = duckdb.connect()
        try:
            con.register("scores_df", predictions)
            escaped_path = str(scores_path.resolve()).replace("'", "''")
            con.execute(
                f"COPY scores_df TO '{escaped_path}' (FORMAT PARQUET, COMPRESSION ZSTD)"
            )
        finally:
            con.close()
        print(f"Scores por pitch guardados en {scores_path}")
        print(f"Modelos guardados en {args.salida / 'modelos'}")
        print("Los índices *_provisional usan pesos iguales y requieren revisión antes de entrega.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
