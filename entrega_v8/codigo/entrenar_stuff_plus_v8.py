"""v8: comparación con igual muestra, velocidad y especialistas por familia.

2026 es un benchmark reutilizado. Selección exclusivamente anterior a 2026.
"""
from pathlib import Path
import argparse
import json
import shutil
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, CatBoostRegressor
import entrenar_stuff_plus_v5 as v5
import entrenar_stuff_plus_v6 as v6
import entrenar_stuff_plus_v7 as v7

EXTRA = ["ZoneSpeed", "SpeedDrop", "ZoneTime"]
FAMILIES = {"Four-Seam": "fast", "Sinker": "fast", "Cutter": "fast",
            "Slider": "breaking", "Curveball": "breaking", "Sweeper": "breaking",
            "Changeup": "offspeed", "Splitter": "offspeed"}
SPECIALISTS = ["whiff", "whiff_given_swing", "ball_in_play"]
MIN_GAIN = .001


def family(frame):
    return frame.AutoPitchType.map(FAMILIES).fillna("other")


def available(frame):
    numeric = frame.reindex(columns=EXTRA).apply(pd.to_numeric, errors="coerce")
    return frame.enhancement_available.to_numpy() & np.isfinite(numeric.to_numpy()).all(axis=1)


def spec_for(task):
    target, columns, condition, kind = v7.COMPONENTS[task]
    return target, list(columns) + EXTRA, condition, kind


def fit_model(train, stop, task, threads):
    spec = spec_for(task)
    train, stop = train.loc[v5.eligible(train, spec)], stop.loc[v5.eligible(stop, spec)]
    cls = CatBoostClassifier if spec[3] == "classification" else CatBoostRegressor
    model = cls(**v7.config_for(task, 0), loss_function="Logloss" if spec[3] == "classification" else "RMSE",
                thread_count=threads, allow_writing_files=False, verbose=False)
    model.fit(v6.features(train, spec[1]), train[spec[0]],
              cat_features=[c for c in spec[1] if c in v5.CATEGORICAL],
              eval_set=(v6.features(stop, spec[1]), stop[spec[0]]), early_stopping_rounds=30, use_best_model=True)
    return model


def candidates(frame, task, models, control):
    global_pred = v6.predict(models[f"{task}__global"], spec_for(task), frame)
    result = {"control": np.asarray(control), "velocity": global_pred}
    specialized = global_pred.copy()
    groups = family(frame).to_numpy()
    any_specialist = False
    for group in ["fast", "breaking", "offspeed"]:
        key = f"{task}__{group}"
        mask = groups == group
        if key in models and mask.any():
            specialized[mask] = v6.predict(models[key], spec_for(task), frame.loc[mask])
            any_specialist = True
    if any_specialist:
        for weight in [.25, .5, .75]:
            result[f"family_{weight}"] = (1-weight)*global_pred + weight*specialized
    return result


def selection_halves(frame):
    tune = np.zeros(len(frame), dtype=bool)
    for year in sorted(frame.year.unique()):
        games = np.array(sorted(frame.loc[frame.year.eq(year), "game_anon_id"].unique()))
        chosen = np.random.default_rng(808+int(year)).permutation(games)[::2]
        tune |= (frame.year.eq(year) & frame.game_anon_id.isin(chosen)).to_numpy()
    return tune


def loss(y, p):
    return float(np.mean((np.asarray(y)-np.asarray(p))**2))


def choose(y, options, tune, years):
    """Elegir en búsqueda y exigir ganancia separada; no reintentar si falla."""
    baseline = options["control"]
    best = min(options, key=lambda key: loss(y[tune], options[key][tune]))
    prediction = options[best]
    gains = {name: 1-loss(y[mask], prediction[mask])/loss(y[mask], baseline[mask])
             for name, mask in [("tune", tune), ("confirmation", ~tune)]}
    year_gains = {str(year): 1-loss(y[(years == year)&~tune], prediction[(years == year)&~tune]) /
                  loss(y[(years == year)&~tune], baseline[(years == year)&~tune]) for year in np.unique(years)}
    promoted = best != "control" and min(gains.values()) >= MIN_GAIN and min(year_gains.values()) >= -.001
    return {"candidate": best, "promoted": bool(promoted), "gains": gains, "year_gains": year_gains,
            "trials": {key: {"tune_mse": loss(y[tune], p[tune]), "confirmation_mse": loss(y[~tune], p[~tune])}
                       for key, p in options.items()}}


def load_bundle(path):
    path = Path(path)
    meta = json.loads((path / "bundle.json").read_text(encoding="utf-8"))
    models = {}
    for key in meta["models"]:
        task = key.split("__")[0]
        cls = CatBoostClassifier if spec_for(task)[3] == "classification" else CatBoostRegressor
        models[key] = cls().load_model(str(path / "modelos" / f"{key}.cbm"))
    return meta, models, v7.load_bundle(path / "parent_v7")


def infer(raw, bundle):
    meta, models, parent_bundle = bundle
    output = v7.infer(raw, parent_bundle)
    prepared = v6.enhance(v5.apply_profile(raw, parent_bundle[2][1][0]["profile"])).reset_index(drop=True)
    usable = available(prepared)
    output["v8_available"] = usable
    if not usable.any():
        return output
    rows = prepared.loc[usable]
    for task, selection in meta["selection"].items():
        if not selection["promoted"]:
            continue
        control = v6.predict(parent_bundle[1][task], v7.COMPONENTS[task], rows)
        options = candidates(rows, task, models, control)
        key, method = selection["candidate"].split("|", 1)
        pred = v7.apply_calibrator(options[key], selection["calibrator"]) if method != "raw" else options[key]
        col = "pred_stuff_run_value" if task == "physical_control" else v7.component_column(task)
        output.loc[usable, col] = pred
        if task in v7.CALIBRATION_TASKS:
            output.loc[usable, f"{col}_uncalibrated"] = options[key]
        if task == "physical_control":
            for score, values in {"stuff_plus": -pred, "location_plus": pred-output.loc[usable, "pred_xrunvalue"].to_numpy()}.items():
                ref = meta["reference"][score]
                output.loc[usable, score] = 100+10*(values-ref["mean"])/ref["std"]
            output.loc[usable, "score_reference_id"] = "v8_calibration_reference"
            output.loc[usable, "compound_status"] = "v8_direct_selected"
    return output


def train(args):
    out = args.salida
    if (out / "protocolo.json").exists():
        raise FileExistsError("La salida ya contiene un protocolo; conserva la ejecución original")
    out.mkdir(parents=True, exist_ok=True)
    parent_meta = json.loads((args.parent / "bundle.json").read_text(encoding="utf-8"))
    assert parent_meta["source_sha256"] == v6.file_hash(args.parquet)
    assert parent_meta["script_sha256"] == v6.file_hash(v7.__file__)
    protocol = {"version": 8, "source_sha256": v6.file_hash(args.parquet), "code_hashes":
                {Path(p).name: v6.file_hash(p) for p in [__file__, v5.__file__, v6.__file__, v7.__file__]},
                "minimum_gain": MIN_GAIN, "confirmation_year_max_degradation": .001,
                "extra_features": EXTRA, "families": FAMILIES, "family_weights": [.25,.5,.75],
                "selection_seed": 808, "benchmark_reused": True, "threads": args.hilos}
    v6.json_write(out / "protocolo.json", protocol)
    parent_dir = out / "parent_v7"
    parent_dir.mkdir()
    shutil.copy2(args.parent / "bundle.json", parent_dir / "bundle.json")
    for directory in ["modelos", "parent_v6"]:
        shutil.copytree(args.parent / directory, parent_dir / directory)
    parent = v7.load_bundle(parent_dir)
    raw = v5.prepare_raw(v6.read_seasons(args.parquet, 2025))
    frame = v7.partition_games(v6.enhance(v5.historical_features(raw)))
    assert available(frame).all(), "Mediciones adicionales incompletas en desarrollo"
    old_parts = v5.read_parquet(args.parent / "particiones_pre2026.parquet").set_index("PitchUID")
    assert frame.partition.tolist() == old_parts.loc[frame.PitchUID, "partition"].tolist()
    v5.write_parquet(frame[v6.IDENTITY+["partition"]], out / "particiones.parquet")
    fit = frame.loc[frame.partition.eq("fit")]
    stop = frame.loc[frame.partition.eq("early_stop")]
    cal = frame.loc[frame.partition.eq("calibration")].reset_index(drop=True)
    sel = frame.loc[frame.partition.eq("selection")].reset_index(drop=True)
    tune = selection_halves(sel)
    audit = sel[v6.IDENTITY].copy()
    audit["role"] = np.where(tune, "tune", "confirmation")
    v5.write_parquet(audit, out / "seleccion_roles.parquet")
    models, selections, references = {}, {}, {}
    (out / "modelos").mkdir()
    for task, spec in v7.COMPONENTS.items():
        print(f"Global + velocidad: {task}", flush=True)
        models[f"{task}__global"] = fit_model(fit, stop, task, args.hilos)
        if task in SPECIALISTS:
            for group in ["fast", "breaking", "offspeed"]:
                tr, va = fit.loc[family(fit).eq(group)], stop.loc[family(stop).eq(group)]
                if v5.eligible(tr, spec).sum() >= 3000 and v5.eligible(va, spec).sum() >= 500:
                    print(f"Especialista: {task}/{group}", flush=True)
                    models[f"{task}__{group}"] = fit_model(tr, va, task, args.hilos)
        for key, model in models.items():
            if key.startswith(task+"__"):
                model.save_model(str(out / "modelos" / f"{key}.cbm"))
        control_cal = v6.predict(parent[1][task], spec, cal)
        control_sel = v6.predict(parent[1][task], spec, sel)
        # Verifica que el control coincide exactamente con el exportado por v7.
        stored = v5.read_parquet(args.parent / "predicciones_selection.parquet").set_index("PitchUID")
        np.testing.assert_allclose(control_sel, stored.loc[sel.PitchUID, v7.component_column(task)], atol=1e-10)
        cp, sp = candidates(cal, task, models, control_cal), candidates(sel, task, models, control_sel)
        cm, sm = v5.eligible(cal, spec).to_numpy(), v5.eligible(sel, spec).to_numpy()
        options, mappings = {"control": control_sel}, {}
        for key in sp:
            options[key+"|raw"] = sp[key]
            if task in v7.CALIBRATION_TASKS:
                maps = v7.fit_calibrators(cal.loc[cm, spec[0]], cp[key][cm])
                # Sigmoide: pocos parámetros; isotónica permanece solo en el padre.
                mapping = maps["sigmoid"]
                options[key+"|sigmoid"] = v7.apply_calibrator(sp[key], mapping)
                mappings[key+"|sigmoid"] = mapping
        choice = choose(sel.loc[sm, spec[0]].to_numpy(), {k:v[sm] for k,v in options.items()}, tune[sm], sel.loc[sm,"year"].to_numpy())
        if spec[3] == "classification":
            check = sm & ~tune
            baseline_logloss = v7.log_loss(sel.loc[check,spec[0]], control_sel[check])
            candidate_logloss = v7.log_loss(sel.loc[check,spec[0]], options[choice["candidate"]][check])
            choice["logloss_noninferior"] = bool(candidate_logloss <= baseline_logloss*1.0015)
            choice["promoted"] = choice["promoted"] and choice["logloss_noninferior"]
        choice["calibrator"] = mappings.get(choice["candidate"], {"method": "identity"})
        selections[task] = choice
        table = sel[v6.IDENTITY+[spec[0]]].copy()
        for key, values in options.items():
            table[key] = values
        v5.write_parquet(table, out / f"seleccion_{task}.parquet")
        if task == "physical_control" and choice["promoted"]:
            key = choice["candidate"].split("|")[0]
            p = cp[key]
            original = raw.set_index("PitchUID").loc[cal.PitchUID].reset_index()
            contextual = v7.infer(original, parent).pred_xrunvalue.to_numpy()
            references = {name: {"mean": float(x.mean()), "std": max(float(x.std()), 1e-8)}
                          for name,x in {"stuff_plus": -p, "location_plus": p-contextual}.items()}
        print(json.dumps({"task":task, "chosen":choice["candidate"], "promoted":choice["promoted"], "gains":choice["gains"]}), flush=True)
    assert v6.file_hash(__file__) == protocol["code_hashes"][Path(__file__).name]
    hashes = {str(p.relative_to(out)):v6.file_hash(p) for p in out.rglob("*.cbm")}
    metadata = {"version":8, "selection":selections, "reference":references, "models":list(models),
                "model_hashes":hashes, "parent_hash":v6.file_hash(parent_dir / "bundle.json"),
                "protocol_hash":v6.file_hash(out / "protocolo.json"), "benchmark_reused":True}
    v6.json_write(out / "seleccion_congelada.json", metadata)
    v6.json_write(out / "bundle.json", metadata)
    print("Selección congelada antes de leer 2026", flush=True)


def evaluate(args):
    out = args.salida
    if (out / "metricas.json").exists():
        raise FileExistsError("Benchmark ya evaluado")
    protocol = json.loads((out / "protocolo.json").read_text(encoding="utf-8"))
    assert v6.file_hash(args.parquet) == protocol["source_sha256"]
    for name, digest in protocol["code_hashes"].items():
        assert v6.file_hash(Path(__file__).parent / name) == digest
    bundle = load_bundle(out)
    data = v5.prepare_raw(v6.read_seasons(args.parquet, 2026))
    test = data.loc[data.year.eq(2026)].reset_index(drop=True)
    fit_ids = v5.read_parquet(out / "particiones.parquet")
    fit = data.loc[data.PitchUID.isin(fit_ids.loc[fit_ids.partition.eq("fit"),"PitchUID"])]
    parent = v7.infer(test, bundle[2])
    predicted = infer(test, bundle)
    v5.write_parquet(predicted, out / "scores_pitch_v8.parquet")
    records = []
    for task, spec in v7.COMPONENTS.items():
        mask = v5.eligible(test,spec)
        col = "pred_stuff_run_value" if task == "physical_control" else v7.component_column(task)
        y, old, new = test.loc[mask,spec[0]],parent.loc[mask,col],predicted.loc[mask,col]
        records.append({"task":task,"n":int(mask.sum()), "v7":v5.metrics(y,old,fit.loc[v5.eligible(fit,spec),spec[0]],spec[3]),
                        "v8":v5.metrics(y,new,fit.loc[v5.eligible(fit,spec),spec[0]],spec[3]),
                        "bootstrap":v6.game_bootstrap_comparison(test.loc[mask],y,old,new)})
    v6.json_write(out / "metricas.json",records)
    print(f"v8 completa: {len(predicted):,} predicciones",flush=True)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet",type=Path,default=Path("stuff_model_df.parquet"))
    parser.add_argument("--parent",type=Path,default=Path("stuff_plus_output_v7"))
    parser.add_argument("--salida",type=Path,default=Path("stuff_plus_output_v8"))
    parser.add_argument("--hilos",type=int,default=6)
    parser.add_argument("--fase",choices=["entrenar","evaluar","todo"],default="todo")
    args=parser.parse_args()
    if args.fase in ["entrenar","todo"]: train(args)
    if args.fase in ["evaluar","todo"]: evaluate(args)
