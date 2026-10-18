"""Audita la separacion real de juegos, predicciones OOF y calibracion v7."""
import argparse
import json
from pathlib import Path

import numpy as np
from catboost import CatBoostClassifier, CatBoostRegressor

import entrenar_stuff_plus_v5 as v5
import entrenar_stuff_plus_v6 as v6
import entrenar_stuff_plus_v7 as v7


def keyset(frame):
    return set(zip(frame.year, frame.game_anon_id.astype(str)))


def verify(output, source):
    protocol = json.loads((output / "protocolo.json").read_text(encoding="utf-8"))
    metadata = json.loads((output / "bundle.json").read_text(encoding="utf-8"))
    selection = json.loads((output / "seleccion_congelada.json").read_text(encoding="utf-8"))
    preparation = json.loads((output / "preparacion.json").read_text(encoding="utf-8"))
    assert metadata == selection, "El bundle difiere de la seleccion congelada"
    assert v6.file_hash(output / "protocolo.json") == metadata["protocol_sha256"]
    assert v6.file_hash(output / "preparacion.json") == metadata["preparation_sha256"]
    assert v6.file_hash(source) == protocol["source_sha256"]
    assert v6.file_hash(v7.__file__) == protocol["script_sha256"]
    assert v6.file_hash(v6.__file__) == protocol["v6_script_sha256"]
    assert v6.file_hash(v5.__file__) == protocol["v5_script_sha256"]
    assert v6.file_hash(output / "parent_v6/bundle.json") == protocol["parent_bundle_sha256"]
    parent_meta = json.loads((output / "parent_v6/bundle.json").read_text(encoding="utf-8"))
    assert v6.file_hash(output / "parent_v6/base_v5/bundle.json") == parent_meta["base_bundle_sha256"]
    for path, digest in preparation["model_and_oof_hashes"].items():
        assert v6.file_hash(output / path) == digest, f"Artefacto alterado: {path}"
    partitions = v5.read_parquet(output / "particiones_pre2026.parquet")
    assert partitions.year.max() <= 2025
    assert not partitions.PitchUID.duplicated().any()
    pieces = {name: partitions.loc[partitions.partition.eq(name)] for name in ["fit", "early_stop", "calibration", "selection"]}
    names = list(pieces)
    for i, name in enumerate(names):
        for other in names[i+1:]:
            assert not keyset(pieces[name]) & keyset(pieces[other]), f"Juegos compartidos entre {name} y {other}"
            assert not set(pieces[name].PitchUID) & set(pieces[other].PitchUID)
    oof = v5.read_parquet(output / "oof_fit.parquet")
    cal_oof = v5.read_parquet(output / "oof_calibrado.parquet")
    assert not oof.PitchUID.duplicated().any()
    assert set(oof.PitchUID) == set(pieces["fit"].PitchUID)
    assert oof.PitchUID.tolist() == cal_oof.PitchUID.tolist()
    component_columns = [v7.component_column(n) for n in v7.COMPONENTS]
    assert np.isfinite(oof[component_columns].to_numpy()).all()
    raw = v5.prepare_raw(v6.read_seasons(source, 2025))
    assert set(raw.PitchUID) == set(partitions.PitchUID)
    prepared = v6.enhance(v5.historical_features(raw)).set_index("PitchUID", drop=False)
    calibration = v5.read_parquet(output / "predicciones_calibration.parquet")
    select_rows = v5.read_parquet(output / "predicciones_selection.parquet")
    for name, table in [("calibration", calibration), ("selection", select_rows)]:
        assert set(table.PitchUID) == set(pieces[name].PitchUID)
        actual = prepared.loc[table.PitchUID]
        for col in ["run_value_proxy", "is_whiff", "is_swing", "home_run", "ExitSpeed"]:
            np.testing.assert_allclose(table[col].to_numpy(dtype=float, na_value=np.nan), actual[col].to_numpy(dtype=float, na_value=np.nan), equal_nan=True)
    folds_verified = []
    for fold in range(v7.FOLDS):
        held = oof.loc[oof.oof_fold.eq(fold)]
        train = v5.read_parquet(output / "oof" / f"fold_{fold}" / "train_ids.parquet")
        expected_train = pieces["fit"].loc[pieces["fit"].oof_fold.ne(fold)]
        assert set(train.PitchUID) == set(expected_train.PitchUID)
        assert not keyset(train) & keyset(held)
        for name in ["early_stop", "calibration", "selection"]:
            assert not keyset(train) & keyset(pieces[name])
        sample = held.sample(min(50, len(held)), random_state=fold)
        inputs = prepared.loc[sample.PitchUID].reset_index(drop=True)
        fold_cal = v5.read_parquet(output / "oof" / f"fold_{fold}" / "calibration_scores.parquet")
        assert set(fold_cal.PitchUID) == set(pieces["calibration"].PitchUID)
        for task, spec in v7.COMPONENTS.items():
            cls = CatBoostClassifier if spec[3] == "classification" else CatBoostRegressor
            model = cls()
            model.load_model(str(output / "oof" / f"fold_{fold}" / "modelos" / f"{task}.cbm"))
            prediction = v6.predict(model, spec, inputs)
            np.testing.assert_allclose(prediction, sample[v7.component_column(task)], rtol=1e-9, atol=1e-10)
            if task in v7.CALIBRATION_TASKS:
                col = v7.component_column(task)
                mask = oof.oof_fold.eq(fold)
                mapped = v7.apply_calibrator(oof.loc[mask, col], metadata["calibrations"][task]["oof_calibrators"][str(fold)])
                np.testing.assert_allclose(mapped, cal_oof.loc[mask, col], rtol=1e-9, atol=1e-10)
                mask_cal = fold_cal.is_whiff.notna()
                if task == "whiff_given_swing":
                    mask_cal &= fold_cal.is_swing.eq(1)
                variants = v7.fit_calibrators(fold_cal.loc[mask_cal, "is_whiff"], fold_cal.loc[mask_cal, col])
                expected_map = variants[metadata["calibrations"][task]["selected"]]
                np.testing.assert_allclose(v7.apply_calibrator(oof.loc[mask, col], expected_map), mapped, rtol=1e-8, atol=1e-9)
        folds_verified.append({"fold": fold, "train_rows": len(train), "oof_rows": len(held), "games_disjoint": True})
    bundle = v7.load_bundle(output)
    for name, table in [("calibration", calibration), ("selection", select_rows)]:
        sample = table.sample(min(100, len(table)), random_state=7)
        pred = v7.predict_components(prepared.loc[sample.PitchUID].reset_index(drop=True), bundle[1])
        np.testing.assert_allclose(pred[component_columns], sample[component_columns], rtol=1e-9, atol=1e-10)
    for task in v7.CALIBRATION_TASKS:
        spec, col = v7.COMPONENTS[task], v7.component_column(task)
        cal_mask, sel_mask, fit_mask = v5.eligible(calibration, spec), v5.eligible(select_rows, spec), v5.eligible(oof, spec)
        variants = v7.fit_calibrators(calibration.loc[cal_mask, spec[0]], calibration.loc[cal_mask, col])
        selected = v7.select_calibrator(select_rows.loc[sel_mask, spec[0]], select_rows.loc[sel_mask, col], oof.loc[fit_mask, spec[0]], variants)
        assert selected["selected"] == metadata["calibrations"][task]["selected"]
    chosen = metadata["stack"]["chosen"]
    x = v7.stack_features(cal_oof if chosen["use_calibrated"] else oof, metadata["calibrations"], False)
    recomputed = v7.fit_stack(x, oof.run_value_proxy, chosen["alpha"])
    for key in ["mean", "scale", "coef", "intercept"]:
        np.testing.assert_allclose(recomputed[key], chosen["model"][key], rtol=1e-7, atol=1e-9)
    trial = min(metadata["stack"]["trials"], key=lambda item: item["mse"])
    assert chosen["mse"] == trial["mse"]
    assert chosen["promoted"] == (chosen["relative_gain"] >= protocol["minimum_stack_selection_gain"])
    scores = v5.read_parquet(output / "scores_pitch_v7.parquet")
    assert scores.year.eq(2026).all() and not scores.PitchUID.duplicated().any()
    pred_columns = [c for c in scores if c.startswith(("p_", "pred_", "component_")) and c != "compound_status"]
    assert np.isfinite(scores[pred_columns+v6.SCORE_COLUMNS].to_numpy()).all()
    benchmark = v6.read_seasons(source, 2026)
    benchmark = benchmark.loc[benchmark.year.eq(2026)]
    assert set(scores.PitchUID) == set(benchmark.PitchUID)
    ids = scores.PitchUID.sample(min(200, len(scores)), random_state=77).tolist()
    inputs = benchmark.set_index("PitchUID").loc[ids].reset_index()
    live = v7.infer(inputs, bundle)
    exported = scores.set_index("PitchUID").loc[ids].reset_index()
    np.testing.assert_allclose(live[pred_columns+v6.SCORE_COLUMNS], exported[pred_columns+v6.SCORE_COLUMNS], rtol=1e-9, atol=1e-9)
    changed = inputs.copy()
    changed["PlateLocHeight"], changed["PlateLocSide"], changed["Balls"], changed["Strikes"] = 5., 2., 3, 2
    changed["BatterSide"], changed["altitude_category"] = "Left", "Extreme Altitude"
    changed_predictions = v7.infer(changed, bundle)
    physics = ["stuff_plus", "pred_stuff_run_value", "p_whiff", "p_whiff_given_swing", "p_ball_in_play", "p_home_run_per_pitch"]
    np.testing.assert_allclose(live[physics], changed_predictions[physics], rtol=0, atol=1e-9)
    needed = list(dict.fromkeys([*[c for c in v5.PHYSICAL if c in inputs], *v6.EXTRA_RAW, "SpinAxis",
        "PitchUID", "pitcher_anon_id", "PlateLocHeight", "PlateLocSide", "Balls", "Strikes", "BatterSide", "altitude_category"]))
    no_outcomes = v7.infer(inputs[needed], bundle)
    np.testing.assert_allclose(live[pred_columns+v6.SCORE_COLUMNS], no_outcomes[pred_columns+v6.SCORE_COLUMNS], rtol=0, atol=1e-9)
    missing = inputs.drop(columns=v6.EXTRA_RAW)
    fallback = v7.infer(missing, bundle)
    parent = v6.infer(missing, bundle[2])
    parent_columns = [c for c in parent if c.startswith(("p_", "pred_"))] + v6.SCORE_COLUMNS
    np.testing.assert_allclose(fallback[parent_columns], parent[parent_columns], rtol=0, atol=1e-9)
    single = v7.infer(inputs.iloc[:1], bundle)
    np.testing.assert_allclose(single[pred_columns+v6.SCORE_COLUMNS], live.iloc[:1][pred_columns+v6.SCORE_COLUMNS], rtol=0, atol=1e-9)
    checks = {"benchmark_rows": len(scores), "fit_rows": len(oof), "partitions": {n: len(p) for n, p in pieces.items()},
              "four_roles_have_disjoint_games": True, "oof_excludes_own_game": True, "folds": folds_verified,
              "calibrators_use_only_calibration_games": True, "stack_fit_uses_only_oof_predictions": True,
              "selection_reproduced_without_2026": True, "code_data_and_models_hashes_match": True,
              "inference_matches_export": True, "outcomes_not_required": True, "physical_invariance": True,
              "fallback_matches_v6": True, "batch_size_invariant": True, "benchmark_is_reused": True}
    v6.json_write(output / "verificacion.json", checks)
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, default=Path("stuff_plus_output_v7"))
    parser.add_argument("--parquet", type=Path, default=Path("stuff_model_df.parquet"))
    args = parser.parse_args()
    verify(args.salida, args.parquet)
