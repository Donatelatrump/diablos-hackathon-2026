"""Pruebas de independencia, calibracion serializable y compuesto OOF v7."""
import unittest
from pathlib import Path
from unittest.mock import patch

import duckdb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

import entrenar_stuff_plus_v5 as v5
import entrenar_stuff_plus_v6 as v6
import entrenar_stuff_plus_v7 as v7
from proyecto_io import bundle_ready, data_path

ROOT = Path(__file__).resolve().parents[1]


def toy_predictions(n=600, seed=19):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({"p_whiff": rng.uniform(.05, .20, n), "p_whiff_given_swing": rng.uniform(.10, .50, n),
                         "p_ball_in_play": rng.uniform(.10, .35, n), "p_groundball_given_in_play": rng.uniform(.2, .7, n),
                         "p_home_run_per_pitch": rng.uniform(.002, .015, n), "pred_exit_speed_given_in_play": rng.uniform(80, 95, n),
                         "pred_physical_control": rng.normal(0, .01, n)})


def identity_calibrations():
    return {name: {"calibrator": {"method": "identity"}} for name in v7.CALIBRATION_TASKS}


class PartitionTests(unittest.TestCase):
    def test_four_partitions_and_oof_folds_keep_games_together(self):
        rows = pd.DataFrame([{"year": y, "game_anon_id": f"g{g}", "PitchUID": f"{y}-{g}-{p}"}
                             for y in [2024, 2025] for g in range(100) for p in range(3)])
        result = v7.partition_games(rows)
        self.assertEqual(result.groupby(["year", "game_anon_id"]).partition.nunique().max(), 1)
        self.assertEqual(result.groupby(["year", "game_anon_id"]).oof_fold.nunique().max(), 1)
        self.assertEqual(set(result.partition), {"fit", "early_stop", "calibration", "selection"})
        fit = result.loc[result.partition.eq("fit")]
        self.assertEqual(set(fit.oof_fold), {0, 1, 2})
        for fold in range(3):
            train = set(fit.loc[fit.oof_fold.ne(fold), "PitchUID"])
            held = set(fit.loc[fit.oof_fold.eq(fold), "PitchUID"])
            self.assertFalse(train & held)

    def test_future_data_rejected(self):
        with self.assertRaises(ValueError):
            v7.partition_games(pd.DataFrame({"year": [2026], "game_anon_id": ["future"]}))


class CalibrationTests(unittest.TestCase):
    def test_serialized_isotonic_reproduces_model_and_clips(self):
        p = np.linspace(.01, .99, 200)
        y = np.tile([0, 0, 1, 1], 50)
        model = IsotonicRegression(y_min=1e-6, y_max=1-1e-6, increasing=True, out_of_bounds="clip").fit(p, y)
        metadata = {"method": "isotonic", "x": model.X_thresholds_.tolist(), "y": model.y_thresholds_.tolist()}
        grid = np.linspace(-.1, 1.1, 500)
        np.testing.assert_allclose(v7.apply_calibrator(grid, metadata), model.predict(np.clip(grid, 1e-6, 1-1e-6)), atol=1e-12)

    def test_sigmoid_identity_mapping_is_finite_at_endpoints(self):
        values = v7.apply_calibrator([0., .2, .5, .8, 1.], {"method": "sigmoid", "slope": 1., "intercept": 0.})
        self.assertTrue(np.isfinite(values).all())
        np.testing.assert_allclose(values[1:4], [.2, .5, .8])

    def test_sigmoid_fit_does_not_reverse_ranking(self):
        rng = np.random.default_rng(27)
        p = rng.uniform(.02, .98, 4000)
        y = rng.binomial(1, p)
        candidates = v7.fit_calibrators(y, p)
        if candidates["sigmoid"]["method"] == "sigmoid":
            self.assertGreater(candidates["sigmoid"]["slope"], 0)

    def test_bad_calibration_keeps_identity(self):
        p = np.tile([.01, .99], 1000)
        y = np.tile([0, 1], 1000)
        bad = {"identity": {"method": "identity"},
               "sigmoid": {"method": "sigmoid", "slope": .001, "intercept": 0.},
               "isotonic": {"method": "isotonic", "x": [0., 1.], "y": [.5, .5]}}
        selected = v7.select_calibrator(y, p, y, bad)
        self.assertEqual(selected["selected"], "identity")


class StackTests(unittest.TestCase):
    def test_conditional_probabilities_are_marginalized(self):
        pred = toy_predictions(10)
        x = v7.stack_features(pred, identity_calibrations(), False)
        np.testing.assert_allclose(x[:, v7.STACK_COLUMNS.index("p_groundball_per_pitch")], pred.p_ball_in_play * pred.p_groundball_given_in_play)
        np.testing.assert_allclose(x[:, v7.STACK_COLUMNS.index("expected_exit_speed_per_pitch")], pred.p_ball_in_play * pred.pred_exit_speed_given_in_play)

    def test_no_observed_outcome_enters_stack(self):
        pred = toy_predictions(100)
        before = v7.stack_features(pred, identity_calibrations(), False)
        pred["home_run"], pred["ExitSpeed"], pred["run_value_proxy"] = 1, 999., 999.
        after = v7.stack_features(pred, identity_calibrations(), False)
        np.testing.assert_array_equal(before, after)

    def test_missing_component_rejected(self):
        pred = toy_predictions(20)
        pred.loc[0, "p_ball_in_play"] = np.nan
        with self.assertRaises(ValueError):
            v7.stack_features(pred, identity_calibrations(), False)

    def test_learned_coefficients_obey_physical_sign_constraints(self):
        pred = toy_predictions()
        x = v7.stack_features(pred, identity_calibrations(), False)
        y = 1.4 * pred.p_home_run_per_pitch - .1 * pred.p_whiff
        model = v7.fit_stack(x, y, 10.)
        coef = np.asarray(model["coef"])
        self.assertTrue(np.all(coef >= np.asarray(v7.LOWER_BOUNDS) - 1e-10))
        self.assertTrue(np.all(coef <= np.asarray(v7.UPPER_BOUNDS) + 1e-10))
        self.assertLess(np.mean((v7.predict_stack(x, model)-y)**2), np.var(y))

    def test_prediction_independent_of_batch_composition(self):
        pred = toy_predictions()
        x = v7.stack_features(pred, identity_calibrations(), False)
        model = v7.fit_stack(x, pred.pred_physical_control, 1000.)
        np.testing.assert_allclose(v7.predict_stack(x[:1], model), v7.predict_stack(x, model)[:1], atol=1e-12)


@unittest.skipUnless(bundle_ready(ROOT / "stuff_plus_output_v6"), "Requiere modelos padre completos, no punteros LFS")
class InferenceSmokeTests(unittest.TestCase):
    def test_small_models_exercise_complete_and_fallback_inference(self):
        with duckdb.connect() as con:
            raw = con.execute("SELECT * FROM read_parquet(?) WHERE year=2024 LIMIT 10000", [str(data_path())]).fetchdf()
        raw = v5.prepare_raw(raw)
        frame = v6.enhance(v5.historical_features(raw))
        train, stop = frame.iloc[:8000], frame.iloc[8000:]
        models = {}
        with patch.object(v7, "config_for", return_value=dict(iterations=5, depth=3, learning_rate=.1, l2_leaf_reg=5., random_seed=1)):
            for name in v7.COMPONENTS:
                models[name] = v7.fit_component(train, stop, name, 0, 2)
        parent = v6.load_bundle(ROOT / "stuff_plus_output_v6")
        predictions = v7.predict_components(stop, models)
        cal = identity_calibrations()
        model = v7.fit_stack(v7.stack_features(predictions, cal, False), stop.run_value_proxy, 1000.)
        metadata = {"calibrations": cal, "stack": {"chosen": {"model": model, "use_calibrated": False,
                    "promoted": True, "deployment_weight": .5}},
                    "reference": {"stuff_plus": {"mean": 0., "std": 1.}, "location_plus": {"mean": 0., "std": 1.}}}
        bundle = metadata, models, parent
        sample = raw.iloc[8000:8020].copy()
        live = v7.infer(sample, bundle)
        self.assertTrue(np.isfinite(live[v6.SCORE_COLUMNS].to_numpy()).all())
        no_extra = sample.drop(columns=v6.EXTRA_RAW)
        fallback = v7.infer(no_extra, bundle)
        old = v6.infer(no_extra, parent)
        np.testing.assert_allclose(fallback[v6.SCORE_COLUMNS], old[v6.SCORE_COLUMNS], atol=1e-10)
        self.assertFalse(fallback.v7_available.any())
        self.assertTrue(fallback.compound_status.eq("parent_retained").all())


if __name__ == "__main__":
    unittest.main()
