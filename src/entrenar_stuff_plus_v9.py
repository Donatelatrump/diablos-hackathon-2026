"""Standalone, grouped and calibrated Stuff+ experiment. See docs/guias/GUIA_PROYECTO.md.

Training freezes decisions before evaluation. 2026 is a reused benchmark.
The physical index excludes arsenal, location, environment and outcomes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, CatBoostRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss

import entrenar_stuff_plus_v5 as v5
import entrenar_stuff_plus_v6 as v6
from proyecto_io import data_path, require_local_file

SEED = 904


class TrainingProgress:
    """CatBoost callback with throttled terminal and redirected-log output."""

    def __init__(self, task, iterations):
        self.task = task
        self.total = iterations
        self.started = time.monotonic()
        self.last_update = 0.
        self.iteration = 0
        self.terminal = sys.stderr.isatty()

    def render(self, final=False):
        now = time.monotonic()
        if not final and self.iteration != 1 and now - self.last_update < 5:
            return
        self.last_update = now
        fraction = min(self.iteration / max(self.total, 1), 1.)
        filled = int(25 * fraction)
        elapsed = now - self.started
        message = (f"{self.task} [{'#' * filled}{'-' * (25 - filled)}] "
                   f"{self.iteration}/{self.total} iterations · {elapsed:.0f}s"
                   + (" · training finished" if final else ""))
        print(("\r" if self.terminal else "") + message,
              end="\n" if final or not self.terminal else "", file=sys.stderr, flush=True)

    def after_iteration(self, info):
        self.iteration = info.iteration
        self.render()
        return True

ARSENAL = ["velo_diff_vs_fb", "ivb_diff_vs_fb", "hb_diff_vs_fb", "release_distance_vs_fb",
           "pitch_usage_pct", "arsenal_history_available", "arsenal_reliability"]
PHYSICAL = [c for c in v5.PHYSICAL if c not in ARSENAL] + v6.SHAPE_DERIVED
LOCATION = PHYSICAL + ["PlateLocHeight", "PlateLocSide", "Balls", "Strikes", "BatterSide"]
WITH_ARSENAL = LOCATION + ARSENAL
ENVIRONMENT = WITH_ARSENAL + ["altitude_category"]
# Probabilities describe the complete pitch scenario; their scope is explicit.
TASKS = {
    "stuff_run_value": ("run_value_proxy", PHYSICAL, None, "regression"),
    "xrunvalue": ("run_value_proxy", LOCATION, None, "regression"),
    "arsenal_run_value": ("run_value_proxy", WITH_ARSENAL, None, "regression"),
    "environment_run_value": ("run_value_proxy", ENVIRONMENT, None, "regression"),
    "whiff": ("is_whiff", ENVIRONMENT, None, "classification"),
    "whiff_given_swing": ("is_whiff", ENVIRONMENT, "swing", "classification"),
    "ball_in_play": ("is_ball_in_play", ENVIRONMENT, None, "classification"),
    "groundball_given_in_play": ("is_groundball", ENVIRONMENT, "hit_type", "classification"),
    "weak_contact": ("is_weak_contact", ENVIRONMENT, "exit", "classification"),
    "hard_contact": ("is_hard_contact", ENVIRONMENT, "exit", "classification"),
    "home_run_per_pitch": ("home_run", ENVIRONMENT, None, "classification"),
    "called_strike": ("is_called_strike", LOCATION, None, "classification"),
    "chase": ("swung_outside_strike_zone", LOCATION, None, "classification"),
}
CORE_TASKS = list(TASKS)[:4]
PARENTS = {"arsenal_run_value": "xrunvalue", "environment_run_value": "arsenal_run_value"}
ROLES = ["fit", "early_stop", "calibration", "tune", "confirmation"]
IDENTITY = v6.IDENTITY
RAW_PHYSICAL = [c for c in v5.PHYSICAL if c not in ARSENAL and not c.startswith("SpinAxis_")] + ["SpinAxis"]
RAW_REQUIRED = list(dict.fromkeys(RAW_PHYSICAL + ["pitcher_anon_id", "PlateLocHeight", "PlateLocSide",
                                                "Balls", "Strikes", "BatterSide", "altitude_category"]))
LABEL_REQUIRED = ["PitchUID", "year", "game_anon_id", "PitchCall", "play_result", "hit_type", "ExitSpeed",
                  "is_whiff", "is_swing", "is_ball_in_play", "home_run", "is_called_strike",
                  "swung_outside_strike_zone"]


def validate_frame(frame, training=False):
    required = RAW_REQUIRED + (LABEL_REQUIRED if training else [])
    missing = sorted(set(required) - set(frame))
    if missing:
        raise ValueError("Faltan columnas: " + ", ".join(missing))
    if frame.empty:
        raise ValueError("La muestra está vacía")
    if training:
        for column in ["PitchUID", "year", "game_anon_id"]:
            if frame[column].isna().any():
                raise ValueError(f"{column} contiene valores ausentes")
        if frame.PitchUID.duplicated().any():
            raise ValueError("PitchUID debe ser único")
        years = pd.to_numeric(frame.year, errors="coerce")
        if not np.isfinite(years).all() or (years % 1 != 0).any():
            raise ValueError("year debe contener años enteros")
        for column in ["is_whiff", "is_swing", "is_ball_in_play", "home_run", "is_called_strike", "swung_outside_strike_zone"]:
            if not frame[column].dropna().isin([0, 1, False, True]).all():
                raise ValueError(f"{column} debe ser binaria (0/1) o ausente")
    for column, high in [("Balls", 3), ("Strikes", 2)]:
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.isna().any() or not values.between(0, high).all() or (values % 1 != 0).any():
            raise ValueError(f"{column} debe contener enteros entre 0 y {high}")


def partition_games(frame, seed=SEED):
    """50/15/15/10/10, whole games; reproducible under row reordering."""
    result = frame.copy().reset_index(drop=True)
    result["partition"] = ""
    for year in sorted(result.year.unique()):
        games = np.array(sorted(result.loc[result.year.eq(year), "game_anon_id"].astype(str).unique()))
        if len(games) < 30:
            raise ValueError(f"Se requieren al menos 30 juegos de desarrollo en {year}")
        games = np.random.default_rng(seed + int(year)).permutation(games)
        cuts = [0, int(len(games)*.5), int(len(games)*.65), int(len(games)*.8), int(len(games)*.9), len(games)]
        for i, role in enumerate(ROLES):
            mask = result.year.eq(year) & result.game_anon_id.astype(str).isin(games[cuts[i]:cuts[i+1]])
            result.loc[mask, "partition"] = role
    return result


def held_pitcher(identifier):
    digest = hashlib.sha256(f"{SEED}:{identifier}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % 5 == 0


def holdout_mask(frame, holdout, value=None):
    if holdout == "season":
        return pd.Series(True, index=frame.index)
    if holdout == "pitcher":
        return frame.pitcher_anon_id.notna() & frame.pitcher_anon_id.map(held_pitcher)
    column = "altitude_category" if holdout == "environment" else "stadium"
    if column not in frame or not value:
        raise ValueError(f"El holdout {holdout} requiere {column} y --grupo-excluido")
    return frame[column].eq(value)


def fit_profile(history):
    """Shrink primary fastball means using historical type/hand peers only."""
    profile = v5.fit_profile(history)
    if history.empty:
        return profile
    fb = history.loc[history.AutoPitchType.isin(["Four-Seam", "Sinker"])]
    counts = fb.groupby(["pitcher_anon_id", "AutoPitchType"]).size().rename("n").reset_index()
    primary = counts.sort_values(["n", "AutoPitchType"], ascending=[False, True]).drop_duplicates("pitcher_anon_id")
    selected = fb.merge(primary[["pitcher_anon_id", "AutoPitchType"]], on=["pitcher_anon_id", "AutoPitchType"])
    priors = fb.groupby(["AutoPitchType", "PitcherThrows"])[v5.PROFILE_NUMERIC].mean()
    reliability = {}
    by_pitcher = selected.groupby("pitcher_anon_id")
    for record in profile["fastballs"]:
        pitches = by_pitcher.get_group(record["pitcher_anon_id"])
        peer_key = (pitches.AutoPitchType.iloc[0], pitches.PitcherThrows.iloc[0])
        if peer_key not in priors.index:
            continue
        peer = priors.loc[peer_key]
        count = len(pitches)
        reliability[record["pitcher_anon_id"]] = count / (count + 30.)
        for col in v5.PROFILE_NUMERIC:
            observed = pd.to_numeric(pitches[col], errors="coerce").dropna()
            if len(observed) and np.isfinite(peer[col]):
                weight = len(observed) / (len(observed) + 30.)
                record[col] = float(weight * observed.mean() + (1-weight)*peer[col])
    profile["reliability"] = reliability
    return profile


def apply_profile(frame, profile):
    prepared = v5.apply_profile(frame, profile)
    prepared["arsenal_reliability"] = prepared.pitcher_anon_id.map(profile.get("reliability", {})).fillna(0.)
    return v6.enhance(prepared)


def prepare_development(partitioned):
    """All histories come from FIT games in strictly earlier seasons."""
    chunks = []
    for year in sorted(partitioned.year.unique()):
        history = partitioned.loc[partitioned.partition.eq("fit") & partitioned.year.lt(year)]
        rows = partitioned.loc[partitioned.year.eq(year)]
        chunks.append(apply_profile(rows, fit_profile(history)))
    return pd.concat(chunks, ignore_index=True)


def fit_baseline(frame, spec):
    target, columns, _, kind = spec
    eligible = frame.loc[v5.eligible(frame, spec)]
    prior = float(eligible[target].mean())
    meta = {"prior": prior, "counts": {}}
    if target == "run_value_proxy" and "Balls" in columns:
        table = eligible.groupby(["Balls", "Strikes"])[target].agg(["sum", "count"])
        meta["counts"] = {f"{int(b)}-{int(s)}": float((r["sum"] + 50*prior)/(r["count"]+50))
                          for (b, s), r in table.iterrows()}
    return meta


def baseline_predict(frame, metadata):
    if not metadata["counts"]:
        return np.full(len(frame), metadata["prior"])
    keys = frame.Balls.astype(int).astype(str) + "-" + frame.Strikes.astype(int).astype(str)
    return keys.map(metadata["counts"]).fillna(metadata["prior"]).to_numpy(dtype=float)


def fit_postprocessors(y, probability, baseline, classification):
    """Fit only on calibration games. Continuous shrinkage minimizes MSE."""
    y, p, b = map(lambda x: np.asarray(x, dtype=float), (y, probability, baseline))
    delta = p-b
    denominator = float(delta @ delta)
    weight = float(np.clip(delta @ (y-b)/denominator, 0., 1.)) if denominator > 1e-12 else 0.
    result = {"raw": {"method": "identity"}, "shrink": {"method": "shrink", "weight": weight}}
    if classification and len(np.unique(y)) == 2 and min(np.bincount(y.astype(int))) >= 20:
        p = np.clip(p, 1e-6, 1-1e-6)
        model = LogisticRegression(C=10., max_iter=1000).fit(np.log(p/(1-p)).reshape(-1, 1), y)
        slope = float(model.coef_[0, 0])
        if slope > 0:
            result["sigmoid"] = {"method": "sigmoid", "slope": slope, "intercept": float(model.intercept_[0])}
    return result


def postprocess(prediction, baseline, meta):
    p = np.asarray(prediction, dtype=float)
    if meta["method"] == "identity":
        return p.copy()
    if meta["method"] == "baseline":
        return np.asarray(baseline, dtype=float).copy()
    if meta["method"] == "shrink":
        return meta["weight"]*p + (1-meta["weight"])*baseline
    if meta["method"] == "sigmoid":
        p = np.clip(p, 1e-6, 1-1e-6)
        z = meta["slope"]*np.log(p/(1-p)) + meta["intercept"]
        return 1/(1+np.exp(-np.clip(z, -40, 40)))
    raise ValueError("Postprocesador desconocido")


def grouped_gain(y, control, candidate, groups, repetitions=500):
    """Paired pitch-weighted error, resampling complete groups."""
    y, control, candidate = map(lambda x: np.asarray(x, dtype=float), (y, control, candidate))
    if not len(y) or not np.isfinite(np.column_stack([y, control, candidate])).all():
        return {"gain": None, "ci_low": None, "ci_high": None, "groups": 0}
    errors = pd.DataFrame({"group": np.asarray(groups), "control": (y-control)**2, "candidate": (y-candidate)**2})
    sums = errors.groupby("group")[["control", "candidate"]].sum().to_numpy()
    denominator = sums[:, 0].sum()
    gain = float(1-sums[:, 1].sum()/denominator) if denominator > 1e-15 else None
    result = {"gain": gain, "ci_low": None, "ci_high": None, "groups": len(sums)}
    if len(sums) < 5 or gain is None:
        return result
    rng = np.random.default_rng(SEED)
    gains = []
    for _ in range(repetitions):
        resampled = sums[rng.integers(0, len(sums), len(sums))].sum(axis=0)
        if resampled[0] > 1e-15:
            gains.append(1-resampled[1]/resampled[0])
    if gains:
        result.update(ci_low=float(np.quantile(gains, .025)), ci_high=float(np.quantile(gains, .975)))
    return result


def choose_candidate(y, options, tune, years, groups, classification):
    """Choose ONCE on tune; confirmation may reject, never pick a runner-up."""
    y, tune, years, groups = np.asarray(y), np.asarray(tune, dtype=bool), np.asarray(years), np.asarray(groups)
    fallback = {"candidate": "baseline", "selected": "baseline", "promoted": False, "reason": "insufficient_support"}
    if tune.sum() < 30 or (~tune).sum() < 30:
        return fallback
    if not all(np.isfinite(p).all() for p in options.values()):
        raise ValueError("Predicciones no finitas durante selección")
    mse = lambda p, mask: float(np.mean((y[mask]-p[mask])**2))
    best = min(options, key=lambda name: mse(options[name], tune))
    control, prediction = options["baseline"], options[best]
    check = ~tune
    confirmation = grouped_gain(y[check], control[check], prediction[check], groups[check])
    base_tune = mse(control, tune)
    tune_gain = 1-mse(prediction, tune)/base_tune if base_tune > 1e-15 else None
    year_gains = {}
    for year in np.unique(years[check]):
        mask = check & (years == year)
        denominator = mse(control, mask)
        year_gains[str(year)] = 1-mse(prediction, mask)/denominator if denominator > 1e-15 else None
    logloss_ok = True
    if classification:
        loss = lambda p: float(log_loss(y[check], np.clip(p[check], 1e-6, 1-1e-6), labels=[0, 1]))
        logloss_ok = loss(prediction) <= loss(control)*1.0015
    promoted = (best != "baseline" and tune_gain is not None and tune_gain >= .001
                and confirmation["gain"] is not None and confirmation["gain"] >= .001
                and confirmation["ci_low"] is not None and confirmation["ci_low"] > 0
                and all(g is not None and g >= -.001 for g in year_gains.values()) and logloss_ok)
    return {"candidate": best, "selected": best if promoted else "baseline", "promoted": bool(promoted),
            "reason": "confirmed" if promoted else "gate_not_met", "tune_gain": tune_gain,
            "confirmation": confirmation, "year_gains": year_gains, "logloss_noninferior": logloss_ok,
            "tune_mse": {key: mse(p, tune) for key, p in options.items()}}


def model_features(frame, columns):
    result = v6.features(frame, [c for c in columns if c != "stadium_id"])
    if "stadium_id" in columns:
        if "stadium_id" not in frame:
            raise ValueError("Falta caracteristica requerida: stadium_id")
        result["stadium_id"] = frame.stadium_id.fillna("__MISSING__").astype(str)
    return result[columns]


def task_spec(task, stadium_context=False):
    target, columns, condition, kind = TASKS[task]
    if stadium_context and "altitude_category" in columns:
        columns = columns + ["stadium_id"]
    return target, columns, condition, kind


def predict_raw(model, frame, task, baseline, columns=None):
    spec = TASKS[task]
    x = model_features(frame, columns if columns is not None else spec[1])
    if spec[3] == "classification":
        return model.predict_proba(x)[:, list(model.classes_).index(1)]
    # Residual regression around a fitted constant or smoothed count baseline.
    return np.asarray(model.predict(x)) + baseline_predict(frame, baseline)


def predict_prepared(frame, metadata, models):
    result = frame[[c for c in IDENTITY + ["stadium", "stadium_id"] if c in frame]].copy().reset_index(drop=True)
    # JSON writers may sort keys; dependencies must not rely on serialization order.
    ordered = [task for task in TASKS if task in metadata["tasks"]]
    for task in ordered:
        meta = metadata["tasks"][task]
        if meta["postprocessor"]["method"] == "parent":
            parent = meta["postprocessor"]["task"]
            if PARENTS.get(task) != parent:
                raise ValueError(f"Dependencia de capa inválida: {task} -> {parent}")
            result[v5.prediction_column(task, TASKS[task])] = result[v5.prediction_column(parent, TASKS[parent])]
            continue
        baseline = baseline_predict(frame, meta["baseline"])
        raw = predict_raw(models[task], frame, task, meta["baseline"], meta["features"]) if task in models else baseline
        result[v5.prediction_column(task, TASKS[task])] = postprocess(raw, baseline, meta["postprocessor"])
    return result


def fit_reference(predictions):
    result = {}
    for name, values in v5.raw_scores(predictions).items():
        std = float(np.std(values))
        result[name] = {"mean": float(np.mean(values)), "std": std, "informative": std > 1e-8}
    return result


def add_scores(predictions, reference):
    result = predictions.copy()
    for name, values in v5.raw_scores(result).items():
        ref = reference[name]
        result[name] = 100+10*(values-ref["mean"])/ref["std"] if ref["informative"] else np.full(len(values), 100.)
    result["score_reference_id"] = "v9_calibration_fixed"
    return result


def input_profiles(frame):
    numeric = [c for c in RAW_PHYSICAL if c not in v5.CATEGORICAL]
    records = []
    for (pitch_type, hand), rows in frame.groupby(["AutoPitchType", "PitcherThrows"]):
        values = rows[numeric].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
        clean = lambda series: {key: float(val) if pd.notna(val) else None for key, val in series.items()}
        records.append({"type": str(pitch_type), "hand": str(hand), "n": len(rows),
                        "median": clean(values.median()), "p01": clean(values.quantile(.01)), "p99": clean(values.quantile(.99))})
    return records


def load_bundle(path):
    path = Path(path)
    meta = json.loads(require_local_file(path / "bundle.json").read_text())
    models = {}
    for task, item in meta["tasks"].items():
        if not item["model"]:
            continue
        model_path = require_local_file(path / item["model"])
        if v6.file_hash(model_path) != item["sha256"]:
            raise ValueError(f"Hash de modelo incorrecto: {task}")
        cls = CatBoostClassifier if TASKS[task][3] == "classification" else CatBoostRegressor
        models[task] = cls().load_model(str(model_path))
    return meta, models


def infer(frame, bundle):
    validate_frame(frame)
    meta, models = bundle
    prepared = apply_profile(frame, meta["profile"])
    result = add_scores(predict_prepared(prepared, meta, models), meta["reference"])
    result["arsenal_history_available"] = prepared.arsenal_history_available.to_numpy()
    return result


def read_rows(path, year, development):
    operator = "<" if development else "="
    with duckdb.connect() as con:
        available = {r[0] for r in con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(path)]).fetchall()}
        needed = [c for c in dict.fromkeys(RAW_REQUIRED + LABEL_REQUIRED + ["stadium", "stadium_id", "estadio"]) if c in available]
        columns = ", ".join('"' + c + '"' for c in needed)
        frame = con.execute(f"SELECT {columns} FROM read_parquet(?) WHERE year {operator} ?", [str(path), year]).fetchdf()
        if "estadio" in frame:
            frame["stadium"] = frame.pop("estadio")
        return frame


def train(args):
    source = data_path(args.parquet)
    if args.salida.exists() and any(args.salida.iterdir()):
        raise FileExistsError("La salida ya existe; usa una carpeta nueva para conservar el experimento")
    print("Loading and preparing training data…", flush=True)
    raw = read_rows(source, args.test_year, True)
    validate_frame(raw, training=True)
    stadium_context = getattr(args, "stadium_context", False)
    if stadium_context and ("stadium_id" not in raw or raw.stadium_id.notna().sum() == 0):
        raise ValueError("--stadium-context requiere stadium_id con estadios clasificados")
    source_rows = len(raw)
    if args.holdout != "season":
        grouping = {"pitcher": "pitcher_anon_id", "environment": "altitude_category", "park": "stadium"}[args.holdout]
        if grouping not in raw:
            raise ValueError(f"El holdout {args.holdout} requiere la columna {grouping}")
        raw = raw.loc[raw[grouping].notna()].copy()
        raw = raw.loc[~holdout_mask(raw, args.holdout, args.grupo_excluido)].copy()
    raw = v5.prepare_raw(raw)
    partitioned = partition_games(raw)
    args.salida.mkdir(parents=True, exist_ok=True)
    protocol = {"version": 9, "seed": SEED, "source_sha256": v6.file_hash(source),
                "source_development_rows": source_rows, "included_development_rows": len(raw),
                "missing_pitcher_development_rows": int(raw.pitcher_anon_id.isna().sum()),
                "test_year": args.test_year, "holdout": args.holdout, "held_group": args.grupo_excluido,
                "benchmark_reused": args.test_year <= 2026, "iterations": args.iteraciones, "threads": args.hilos,
                "tasks": list(args.tasks), "incremental_gate": getattr(args, "incremental_gate", False),
                "stadium_context": stadium_context,
                "stadiums_development": sorted(raw.stadium_id.dropna().unique().tolist()) if stadium_context else [],
                "depth": 6, "learning_rate": .045, "l2_leaf_reg": 20.,
                "partitions": dict(zip(ROLES, [.5, .15, .15, .1, .1])),
                "gate": {"min_gain": .001, "min_ci_low": 0., "max_year_degradation": .001,
                         "max_logloss_ratio": 1.0015, "bootstrap_repetitions": 500},
                "code_hashes": {Path(p).name: v6.file_hash(p) for p in [__file__, v5.__file__, v6.__file__]}}
    v6.json_write(args.salida / "protocolo.json", protocol)
    v5.write_parquet(partitioned[IDENTITY+["partition"]], args.salida / "particiones.parquet")
    frame = prepare_development(partitioned)
    fit, stop, cal = [frame.loc[frame.partition.eq(part)].reset_index(drop=True) for part in ROLES[:3]]
    selection = frame.loc[frame.partition.isin(ROLES[3:])].reset_index(drop=True)
    models, tasks = {}, {}
    (args.salida / "modelos").mkdir()
    selected_tasks = [name for name in TASKS if name in args.tasks]
    for task_number, task in enumerate(selected_tasks, 1):
        print(f"Task {task_number}/{len(selected_tasks)}: {task}", flush=True)
        spec = task_spec(task, stadium_context)
        tr, va, ca, se = [rows.loc[v5.eligible(rows, spec)].reset_index(drop=True) for rows in [fit, stop, cal, selection]]
        if tr.empty:
            raise ValueError(f"Sin etiquetas de ajuste para {task}")
        baseline = fit_baseline(fit, spec)
        item = {"baseline": baseline, "model": None, "features": spec[1], "kind": spec[3],
                "target": spec[0], "condition": spec[2], "n_fit": len(tr), "n_calibration": len(ca),
                "postprocessor": {"method": "baseline"}, "selection": {"promoted": False, "reason": "insufficient_labels"}}
        parent = PARENTS.get(task) if getattr(args, "incremental_gate", False) else None
        if parent:
            item["postprocessor"] = {"method": "parent", "task": parent}
            item["selection"].update(selected="parent", control_task=parent)
        classification = spec[3] == "classification"
        enough = len(tr) >= 100 and len(va) >= 30 and len(ca) >= 30 and len(se) >= 60
        if classification:
            enough &= all(rows[spec[0]].nunique() == 2 for rows in [tr, va])
        if enough:
            cls = CatBoostClassifier if classification else CatBoostRegressor
            model = cls(iterations=args.iteraciones, depth=6, learning_rate=.045, l2_leaf_reg=20.,
                        random_seed=SEED, thread_count=args.hilos, loss_function="Logloss" if classification else "RMSE",
                        allow_writing_files=False, verbose=False)
            target = lambda rows: rows[spec[0]].to_numpy() if classification else rows[spec[0]].to_numpy()-baseline_predict(rows, baseline)
            progress = TrainingProgress(task, args.iteraciones)
            try:
                model.fit(model_features(tr, spec[1]), target(tr), cat_features=[c for c in spec[1] if c in v5.CATEGORICAL or c == "stadium_id"],
                          eval_set=(model_features(va, spec[1]), target(va)), early_stopping_rounds=35,
                          use_best_model=True, callbacks=[progress])
            finally:
                progress.render(final=True)
            print(f"{task}: calibrating and selecting candidates…", flush=True)
            pcal, psel = [predict_raw(model, rows, task, baseline, spec[1]) for rows in [ca, se]]
            processors = fit_postprocessors(ca[spec[0]], pcal, baseline_predict(ca, baseline), classification)
            base = baseline_predict(se, baseline)
            options = {"baseline": base, **{name: postprocess(psel, base, post) for name, post in processors.items()}}
            if parent:
                # The simpler selected layer is the control, not a weak count mean.
                parent_predictions = predict_prepared(se, {"tasks": tasks}, models)
                options["baseline"] = parent_predictions[v5.prediction_column(parent, TASKS[parent])].to_numpy()
            groups = se.year.astype(str) + ":" + se.game_anon_id.astype(str)
            chosen = choose_candidate(se[spec[0]], options, se.partition.eq("tune"), se.year, groups, classification)
            if parent:
                chosen["control_task"] = parent
                if not chosen["promoted"]:
                    chosen["selected"] = "parent"
            item["selection"] = chosen
            item["trees"] = model.tree_count_
            # Persist all fitted models for audit; inference uses the frozen processor.
            path = args.salida / "modelos" / f"{task}.cbm"
            model.save_model(str(path))
            item.update(model=str(path.relative_to(args.salida)), sha256=v6.file_hash(path))
            models[task] = model
            if chosen["promoted"]:
                item["postprocessor"] = processors[chosen["selected"]]
            audit = se[IDENTITY+["partition", spec[0]]].copy()
            for key, values in options.items():
                audit[key] = values
            v5.write_parquet(audit, args.salida / f"seleccion_{task}.parquet")
        tasks[task] = item
        print(json.dumps({"task": task, "n_fit": len(tr), "selection": item["selection"]}), flush=True)
    meta = {"version": 9, "protocol_sha256": v6.file_hash(args.salida / "protocolo.json"), "tasks": tasks,
            "profile": fit_profile(partitioned.loc[partitioned.partition.eq("fit")]),
            "input_profiles": input_profiles(fit),
            "probability_scope": "physical_location_arsenal_environment_except_called_strike_and_chase",
            "benchmark_reused": protocol["benchmark_reused"], "test_year": args.test_year,
            "holdout": args.holdout, "held_group": args.grupo_excluido}
    meta["reference"] = fit_reference(predict_prepared(cal, meta, models))
    v6.json_write(args.salida / "bundle.json", meta)
    v6.json_write(args.salida / "seleccion_congelada.json", meta)
    print("Selección y escala congeladas antes de leer el benchmark.", flush=True)


def evaluate(args):
    out = args.salida
    if (out / "metricas.json").exists():
        raise FileExistsError("Benchmark ya evaluado; conserva esta ejecución")
    protocol = json.loads((out / "protocolo.json").read_text())
    source = data_path(args.parquet)
    if v6.file_hash(source) != protocol["source_sha256"]:
        raise ValueError("El dataset cambió desde entrenamiento")
    for name, digest in protocol["code_hashes"].items():
        if v6.file_hash(Path(__file__).parent / name) != digest:
            raise ValueError(f"El código cambió desde entrenamiento: {name}")
    if (out / "bundle.json").read_bytes() != (out / "seleccion_congelada.json").read_bytes():
        raise ValueError("La selección congelada fue modificada")
    bundle = load_bundle(out)
    test = read_rows(source, protocol["test_year"], False)
    test = test.loc[holdout_mask(test, protocol["holdout"], protocol["held_group"])].reset_index(drop=True)
    validate_frame(test, training=True)
    test = v5.prepare_raw(test)
    predicted = infer(test, bundle)
    v5.write_parquet(predicted, out / "scores_pitch_v9.parquet")
    records = []
    for task, item in bundle[0]["tasks"].items():
        spec = TASKS[task]
        mask = v5.eligible(test, spec).to_numpy()
        rows = test.loc[mask]
        if rows.empty:
            records.append({"task": task, "n": 0, "status": "no_eligible_labels"})
            continue
        y, p = rows[spec[0]].to_numpy(), predicted.loc[mask, v5.prediction_column(task, spec)].to_numpy()
        baseline = baseline_predict(rows, item["baseline"])
        groups = rows.pitcher_anon_id if protocol["holdout"] == "pitcher" else rows.year.astype(str)+":"+rows.game_anon_id.astype(str)
        metrics = v5.metrics(y, p, [item["baseline"]["prior"]], spec[3])
        if spec[3] == "classification":
            metrics["log_loss"] = float(log_loss(y, np.clip(p, 1e-6, 1-1e-6), labels=[0, 1]))
        if spec[0] == "run_value_proxy":
            count_base = baseline_predict(rows, bundle[0]["tasks"]["xrunvalue"]["baseline"])
            count_mse = float(np.mean((y-count_base)**2))
            metrics.update(count_baseline_rmse=float(np.sqrt(count_mse)),
                           mse_skill_vs_count=float(1-np.mean((y-p)**2)/count_mse) if count_mse else None)
        records.append({"task": task, "n": len(rows), "selected": item["selection"].get("selected", "baseline"),
                        "metrics": metrics, "vs_baseline": grouped_gain(y, baseline, p, groups)})
    v6.json_write(out / "metricas.json", records)
    # Paired comparisons quantify incremental predictive value, never causality.
    y = test.run_value_proxy.to_numpy()
    groups = test.pitcher_anon_id if protocol["holdout"] == "pitcher" else test.year.astype(str)+":"+test.game_anon_id.astype(str)
    ablations = []
    for old, new in zip(CORE_TASKS[:-1], CORE_TASKS[1:]):
        ablations.append({"from": old, "to": new, **grouped_gain(y, predicted[f"pred_{old}"], predicted[f"pred_{new}"], groups)})
    v6.json_write(out / "ablaciones.json", ablations)
    for keys, filename in [(["year", "pitcher_anon_id"], "pitchers.csv"),
                           (["year", "pitcher_anon_id", "AutoPitchType", "altitude_category"], "arsenal.csv")]:
        summary = predicted.groupby(keys).agg(n_pitches=("PitchUID", "size"), n_games=("game_anon_id", "nunique"),
                    stuff_plus=("stuff_plus", "mean"), location_plus=("location_plus", "mean"), pitching_plus=("pitching_plus", "mean"))
        summary.to_csv(out / filename)
    movement = test[["pitcher_anon_id", "AutoPitchType", "PitcherThrows", "altitude_category", "RelSpeed", "HorzBreak", "InducedVertBreak"]].copy()
    movement["HB"] = movement.HorzBreak * movement.PitcherThrows.map({"Right": 1., "Left": -1.})
    movement["stuff_plus"] = predicted.stuff_plus.to_numpy()
    movement["pitching_plus"] = predicted.pitching_plus.to_numpy()
    movement.groupby(["pitcher_anon_id", "AutoPitchType", "PitcherThrows", "altitude_category"]).agg(
        n=("RelSpeed", "size"), velocity=("RelSpeed", "mean"), HB=("HB", "mean"), IVB=("InducedVertBreak", "mean"),
        stuff_plus=("stuff_plus", "mean"), pitching_plus=("pitching_plus", "mean")).to_csv(out / "mapa_movimiento.csv")
    report = ["# Experimento v9", "", f"Holdout: {protocol['holdout']}; año: {protocol['test_year']}; pitches: {len(test):,}.",
              "Benchmark 2026 reutilizado. Probabilidades v9 conocen contexto; no comparar sus AUC con probabilidades físicas v8 como si usaran la misma información.", "",
              "| Tarea | n | RMSE / Brier | Mejora MSE/Brier vs baseline |", "|---|---:|---:|---:|"]
    for record in records:
        if "metrics" in record:
            m = record["metrics"]
            gain = record["vs_baseline"]["gain"]
            gain_text = f"{gain:.2%}" if gain is not None else "no estimable"
            report.append(f"| {record['task']} | {record['n']} | {m.get('rmse', m.get('brier')):.6f} | {gain_text} |")
    (out / "RESULTADOS.md").write_text("\n".join(report)+"\n", encoding="utf-8")
    print(f"Evaluación guardada: {out / 'RESULTADOS.md'}", flush=True)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--parquet", type=Path)
    p.add_argument("--stadium-context", action="store_true", help="Incorpora stadium_id en modelos de entorno y probabilidades contextuales")
    p.add_argument("--salida", type=Path, default=Path("stuff_plus_output_v9"))
    p.add_argument("--test-year", type=int, default=2026)
    p.add_argument("--holdout", choices=["season", "pitcher", "environment", "park"], default="season")
    p.add_argument("--grupo-excluido")
    p.add_argument("--iteraciones", type=int, default=400)
    p.add_argument("--hilos", type=int, default=6)
    p.add_argument("--incremental-gate", action="store_true",
                   help="Arsenal y entorno deben superar la capa anterior; si no, heredan su predicción")
    p.add_argument("--tasks", nargs="+", choices=list(TASKS), default=list(TASKS))
    p.add_argument("--fase", choices=["entrenar", "evaluar", "todo"], default="todo")
    return p


if __name__ == "__main__":
    args = parser().parse_args()
    if not set(CORE_TASKS) <= set(args.tasks):
        raise SystemExit("--tasks debe incluir las cuatro tareas de carreras para construir índices y ablaciones")
    try:
        if args.fase in ["entrenar", "todo"]:
            train(args)
        if args.fase in ["evaluar", "todo"]:
            evaluate(args)
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        raise SystemExit(str(exc)) from exc
