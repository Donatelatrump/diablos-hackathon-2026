"""Verifica artefactos, independencia e igualdad entre exportacion e inferencia."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from entrenar_stuff_plus_v5 import PHYSICAL, infer, load_bundle, read_parquet


def verify(output, source):
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    with source.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == manifest["source_sha256"], "Origen distinto del entrenado"
    script = Path(__file__).with_name("entrenar_stuff_plus_v5.py")
    assert hashlib.sha256(script.read_bytes()).hexdigest() == manifest["script_sha256"], "Codigo distinto del entrenado"
    scores = read_parquet(output / "scores_pitch_v5.parquet")
    assert not scores.PitchUID.duplicated().any(), "PitchUID repetidos"
    prediction_cols = [c for c in scores if c.startswith(("p_", "pred_"))]
    score_cols = ["stuff_plus", "location_plus", "pitching_plus"]
    assert np.isfinite(scores[prediction_cols + score_cols].to_numpy()).all(), "Predicciones incompletas"
    raw = read_parquet(source)
    expected = set(raw.loc[raw.year.isin(scores.year.unique()), "PitchUID"])
    assert set(scores.PitchUID) == expected, "Cobertura temporal incompleta"
    checks = {"rows": len(scores), "unique_pitchuids": scores.PitchUID.nunique(), "source_and_code_hashes_match": True, "folds": []}
    for folder in sorted(output.glob("holdout_*")):
        if not (folder / "bundle.json").exists():
            continue
        bundle = load_bundle(folder)
        year = bundle[0]["test_year"]
        fit = read_parquet(folder / "filas_fit.parquet")
        valid = read_parquet(folder / "filas_validacion.parquet")
        test = scores.loc[scores.year.eq(year)]
        fit_ids, valid_ids, test_ids = set(fit.PitchUID), set(valid.PitchUID), set(test.PitchUID)
        assert not fit_ids & valid_ids and not (fit_ids | valid_ids) & test_ids, "Filas compartidas entre particiones"
        keys = lambda f: set(zip(f.year, f.game_anon_id))
        assert not keys(fit) & keys(valid), "Juegos compartidos en validacion interna"
        assert fit.year.max() < year and valid.year.max() < year, "Datos futuros en entrenamiento"
        sample_ids = test.PitchUID.sample(min(200, len(test)), random_state=42).tolist()
        sample = raw.set_index("PitchUID").loc[sample_ids].reset_index()
        live = infer(sample, bundle)
        exported = test.set_index("PitchUID").loc[sample_ids].reset_index()
        np.testing.assert_allclose(live[prediction_cols + score_cols], exported[prediction_cols + score_cols], rtol=1e-9, atol=1e-9)
        # El score fisico debe ser invariante a ubicacion, conteo y altitud.
        changed = sample.copy()
        changed["PlateLocHeight"], changed["PlateLocSide"] = 5., 2.
        changed["Balls"], changed["Strikes"] = 3, 2
        changed["altitude_category"] = "Extreme Altitude"
        changed_pred = infer(changed, bundle)
        np.testing.assert_allclose(live.stuff_plus, changed_pred.stuff_plus, rtol=0, atol=1e-10)
        # No es necesario conocer el resultado para simular un lanzamiento.
        inputs = [c for c in PHYSICAL if c in sample] + ["PitchUID", "pitcher_anon_id", "SpinAxis",
                  "PlateLocHeight", "PlateLocSide", "Balls", "Strikes", "BatterSide", "altitude_category"]
        # El arsenal se calcula del bundle; no se pasa como entrada observada.
        inputs = list(dict.fromkeys(c for c in inputs if c in sample))
        outcome_free = infer(sample[inputs], bundle)
        np.testing.assert_allclose(live[score_cols], outcome_free[score_cols], rtol=0, atol=1e-10)
        checks["folds"].append({"year": year, "fit_rows": len(fit), "validation_rows": len(valid),
                                "test_rows": len(test), "inference_matches_export": True,
                                "stuff_invariant_to_location_and_altitude": True})
    print(json.dumps(checks, indent=2, default=int))
    (output / "verificacion.json").write_text(json.dumps(checks, indent=2, default=int), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, default=Path("stuff_plus_output_v5"))
    parser.add_argument("--parquet", type=Path, default=Path("stuff_model_df.parquet"))
    args = parser.parse_args()
    verify(args.salida, args.parquet)
