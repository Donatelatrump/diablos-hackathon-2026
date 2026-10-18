"""Audita seleccion congelada, separacion de juegos, inferencia y respaldo v5."""
import argparse
import json
from pathlib import Path

import numpy as np

import entrenar_stuff_plus_v5 as v5
import entrenar_stuff_plus_v6 as v6


def verify(output, source):
    bundle = v6.load_bundle(output)
    metadata, baseline, _ = bundle
    protocol = json.loads((output / "protocolo_congelado.json").read_text(encoding="utf-8"))
    assert v6.file_hash(output / "protocolo_congelado.json") == metadata["protocol_sha256"]
    assert metadata["tasks"] == protocol["tasks"], "Seleccion alterada despues del desarrollo"
    assert protocol["selection_year"] == 2025 and protocol["development_reads_years_at_most"] == 2025
    assert v6.file_hash(v6.__file__) == metadata["script_sha256"] == protocol["script_sha256"]
    assert v6.file_hash(v5.__file__) == protocol["v5_script_sha256"]
    assert v6.file_hash(source) == metadata["source_sha256"]
    assert v6.file_hash(output / "base_v5" / "bundle.json") == metadata["base_bundle_sha256"]
    for name, digest in metadata["model_hashes"].items():
        assert v6.file_hash(output / name) == digest, f"Modelo alterado: {name}"
    scores = v5.read_parquet(output / "scores_pitch_v6.parquet")
    assert not scores.PitchUID.duplicated().any()
    assert scores.year.eq(2026).all()
    pred_cols = [c for c in scores if c.startswith(("p_", "pred_", "base_p_", "base_pred_"))]
    assert np.isfinite(scores[pred_cols + v6.SCORE_COLUMNS].to_numpy()).all()
    raw = v6.read_seasons(source, 2026)
    expected = set(raw.loc[raw.year.eq(2026), "PitchUID"])
    assert set(scores.PitchUID) == expected
    fit = v5.read_parquet(output / "filas_fit.parquet")
    valid = v5.read_parquet(output / "filas_validacion.parquet")
    assert fit.year.max() < 2026 and valid.year.max() < 2026
    assert not set(fit.PitchUID) & set(valid.PitchUID)
    assert not (set(fit.PitchUID) | set(valid.PitchUID)) & expected
    keys = lambda f: set(zip(f.year, f.game_anon_id))
    assert not keys(fit) & keys(valid)
    sample_ids = scores.PitchUID.sample(min(300, len(scores)), random_state=606).tolist()
    inputs = raw.set_index("PitchUID").loc[sample_ids].reset_index()
    live = v6.infer(inputs, bundle)
    exported = scores.set_index("PitchUID").loc[sample_ids].reset_index()
    predictions = [c for c in pred_cols if not c.startswith("base_")]
    np.testing.assert_allclose(live[predictions + v6.SCORE_COLUMNS], exported[predictions + v6.SCORE_COLUMNS], rtol=1e-9, atol=1e-9)
    changed = inputs.copy()
    changed["PlateLocHeight"], changed["PlateLocSide"], changed["Balls"], changed["Strikes"] = 5., -2., 3, 2
    changed["BatterSide"], changed["altitude_category"] = "Left", "Extreme Altitude"
    changed_pred = v6.infer(changed, bundle)
    np.testing.assert_allclose(live.stuff_plus, changed_pred.stuff_plus, rtol=0, atol=1e-10)
    physical_predictions = ["p_whiff", "p_whiff_given_swing", "pred_exit_speed_given_in_play", "pred_stuff_run_value"]
    np.testing.assert_allclose(live[physical_predictions], changed_pred[physical_predictions], rtol=0, atol=1e-10)
    input_columns = list(dict.fromkeys([*[c for c in v5.PHYSICAL if c in inputs], *v6.EXTRA_RAW,
        "PitchUID", "pitcher_anon_id", "SpinAxis", "PlateLocHeight", "PlateLocSide", "Balls", "Strikes", "BatterSide", "altitude_category"]))
    no_outcomes = v6.infer(inputs[input_columns], bundle)
    np.testing.assert_allclose(live[predictions + v6.SCORE_COLUMNS], no_outcomes[predictions + v6.SCORE_COLUMNS], rtol=0, atol=1e-10)
    missing_extra = inputs.drop(columns=v6.EXTRA_RAW)
    fallback = v6.infer(missing_extra, bundle)
    original = v5.infer(missing_extra, baseline)
    assert fallback.score_reference_id.eq("v5_fallback").all()
    for name in baseline[0]["tasks"]:
        col = ("p_" if baseline[0]["tasks"][name]["kind"] == "classification" else "pred_") + name
        np.testing.assert_allclose(fallback[col], original[col], rtol=0, atol=1e-10)
    np.testing.assert_allclose(fallback[v6.SCORE_COLUMNS], original[v6.SCORE_COLUMNS], rtol=0, atol=1e-10)
    # Puntuar una sola fila no debe cambiar la referencia ni los outputs.
    single = v6.infer(inputs.iloc[:1], bundle)
    np.testing.assert_allclose(single[predictions + v6.SCORE_COLUMNS], live.iloc[:1][predictions + v6.SCORE_COLUMNS], rtol=0, atol=1e-10)
    checks = {"rows": len(scores), "unique_pitchuids": int(scores.PitchUID.nunique()),
              "selection_frozen_on_2025": True, "code_source_and_models_hashes_match": True,
              "fit_validation_and_benchmark_disjoint": True, "inference_matches_export": True,
              "stuff_invariant_to_location_count_batter_and_altitude": True,
              "physical_probabilities_invariant_to_location_count_batter_and_altitude": True,
              "outcomes_not_needed_for_inference": True, "missing_extra_measurements_match_v5": True,
              "batch_size_invariant": True, "benchmark_is_reused": True}
    v6.json_write(output / "verificacion.json", checks)
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, default=Path("stuff_plus_output_v6"))
    parser.add_argument("--parquet", type=Path, default=Path("stuff_model_df.parquet"))
    args = parser.parse_args()
    verify(args.salida, args.parquet)
