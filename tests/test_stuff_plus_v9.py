"""Behavioral checks for leakage, selection and saved-model inference."""
import argparse
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

import entrenar_stuff_plus_v9 as v9
from proyecto_io import is_lfs_pointer, require_local_file


def synthetic_data():
    rng = np.random.default_rng(73)
    rows = []
    for year, games in [(2024, 60), (2025, 60), (2026, 20)]:
        for game in range(games):
            for pitch in range(12):
                speed = rng.uniform(80, 98)
                good = speed > 89
                in_play = not good
                rows.append(dict(PitchUID=f"{year}-{game}-{pitch}", year=year, game_anon_id=f"g{game}",
                    pitcher_anon_id=f"p{game%10}", AutoPitchType="Four-Seam" if pitch%2 else "Slider",
                    PitcherThrows="Right", BatterSide="Left", altitude_category="No Altitude" if game%2 else "Extreme Altitude",
                    RelSpeed=speed, EffectiveVelo=speed, SpinRate=2200., SpinAxis=180., RelHeight=6., RelSide=1.,
                    Extension=6., VertBreak=-15., InducedVertBreak=14., HorzBreak=8.,
                    PlateLocHeight=rng.uniform(1., 4.), PlateLocSide=rng.uniform(-1., 1.), Balls=pitch%4, Strikes=pitch%3,
                    PitchCall="StrikeSwinging" if good else "InPlay", play_result="Strikeout" if good else "HomeRun",
                    hit_type="FlyBall" if in_play else None, ExitSpeed=100. if in_play else np.nan,
                    is_whiff=int(good), is_swing=1, is_ball_in_play=int(in_play), home_run=int(in_play),
                    is_called_strike=0, swung_outside_strike_zone=int(good)))
    return pd.DataFrame(rows)


class IntegrityTests(unittest.TestCase):
    def test_feature_boundaries(self):
        forbidden = set(v9.ARSENAL + ["Balls", "Strikes", "PlateLocHeight", "PlateLocSide", "BatterSide",
                                      "altitude_category", "year", "pitcher_anon_id", "ExitSpeed", "PitchCall", "ZoneSpeed"])
        self.assertFalse(forbidden & set(v9.PHYSICAL))
        self.assertFalse(set(v9.ARSENAL) & set(v9.LOCATION))
        for spec in v9.TASKS.values():
            self.assertFalse(set(v9.LABEL_REQUIRED) & set(spec[1]))

    def test_whole_games_and_order_invariance(self):
        raw = synthetic_data().query("year < 2026")
        first = v9.partition_games(raw).set_index("PitchUID")
        second = v9.partition_games(raw.sample(frac=1, random_state=3)).set_index("PitchUID")
        pd.testing.assert_series_equal(first.partition.sort_index(), second.partition.sort_index())
        self.assertEqual(first.groupby(["year", "game_anon_id"]).partition.nunique().max(), 1)

    def test_held_games_cannot_change_training_arsenal(self):
        data = v9.partition_games(v9.v5.prepare_raw(synthetic_data().query("year < 2026")))
        before = v9.prepare_development(data).set_index("PitchUID")
        data.loc[data.partition.ne("fit"), "RelSpeed"] = 1000.
        after = v9.prepare_development(data).set_index("PitchUID")
        ids = data.loc[data.partition.eq("fit"), "PitchUID"]
        pd.testing.assert_frame_equal(before.loc[ids, v9.ARSENAL], after.loc[ids, v9.ARSENAL])

    def test_pitcher_holdout_excludes_all_history(self):
        raw = synthetic_data()
        held = v9.holdout_mask(raw, "pitcher")
        self.assertTrue(held.any() and (~held).any())
        self.assertFalse(set(raw.loc[held, "pitcher_anon_id"]) & set(raw.loc[~held, "pitcher_anon_id"]))
        with self.assertRaisesRegex(ValueError, "stadium"):
            v9.holdout_mask(raw, "park", "Harp Helú")

    def test_reject_overfit_without_trying_runner_up(self):
        y = np.tile([0., 1.], 200)
        tune = np.arange(len(y)) < 200
        options = {"baseline": np.full(len(y), .5), "overfit": np.where(tune, y, 1-y), "runner_up": .1+.8*y}
        result = v9.choose_candidate(y, options, tune, np.full(len(y), 2025), np.repeat(np.arange(40), 10), True)
        self.assertEqual(result["candidate"], "overfit")
        self.assertEqual(result["selected"], "baseline")

    def test_confirmation_and_zero_error(self):
        y = np.tile([0., 1.], 200)
        args = [np.arange(len(y)) < 200, np.full(len(y), 2025), np.repeat(np.arange(40), 10), True]
        self.assertTrue(v9.choose_candidate(y, {"baseline": np.full(len(y), .5), "good": .1+.8*y}, *args)["promoted"])
        result = v9.choose_candidate(y, {"baseline": y.copy(), "good": y.copy()}, *args)
        self.assertFalse(result["promoted"])
        json.dumps(result, allow_nan=False)

    def test_shrinkage_and_calibration_are_bounded(self):
        y = np.tile([0., 1.], 100)
        p = .2+.6*y
        b = np.full(len(y), .5)
        maps = v9.fit_postprocessors(y, p, b, True)
        self.assertLessEqual(maps["shrink"]["weight"], 1.)
        for meta in maps.values():
            actual = v9.postprocess(p, b, meta)
            self.assertTrue(((actual >= 0) & (actual <= 1)).all())
        single = v9.fit_postprocessors(np.zeros(10), np.zeros(10), np.zeros(10), True)
        self.assertNotIn("sigmoid", single)

    def test_lfs_diagnostic(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"data.parquet"
            path.write_text("version https://git-lfs.github.com/spec/v1\noid sha256:123\nsize 100\n")
            self.assertTrue(is_lfs_pointer(path))
            with self.assertRaisesRegex(ValueError, "Git LFS"):
                require_local_file(path)


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.data = synthetic_data()
        source = cls.root/"source.parquet"
        v9.v5.write_parquet(cls.data, source)
        cls.args = argparse.Namespace(parquet=source, salida=cls.root/"run", test_year=2026, holdout="season",
                                      grupo_excluido=None, iteraciones=30, hilos=2, tasks=v9.CORE_TASKS+["whiff"],
                                      incremental_gate=getattr(cls, "incremental_gate", False))
        with contextlib.redirect_stdout(io.StringIO()):
            v9.train(cls.args)
            v9.evaluate(cls.args)
        cls.bundle = v9.load_bundle(cls.args.salida)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_saved_inference_needs_no_outcomes_and_is_batch_invariant(self):
        rows = self.data.query("year == 2026").head(6)[v9.RAW_REQUIRED].reset_index(drop=True)
        whole = v9.infer(rows, self.bundle)
        one = v9.infer(rows.iloc[:1], self.bundle)
        np.testing.assert_allclose(whole.iloc[0][["stuff_plus", "location_plus", "pitching_plus"]].astype(float),
                                   one.iloc[0][["stuff_plus", "location_plus", "pitching_plus"]].astype(float))
        self.assertTrue(np.isfinite(whole.select_dtypes(include="number")).all().all())

    def test_physical_score_is_invariant_to_context_and_pitcher(self):
        rows = self.data.query("year == 2026").head(5).copy()
        before = v9.infer(rows, self.bundle)
        rows["pitcher_anon_id"] = "never_seen"
        rows["PlateLocSide"] = 2.
        rows["Balls"] = 3
        rows["altitude_category"] = "Medium Altitude"
        rows["ExitSpeed"] = 9999.
        after = v9.infer(rows, self.bundle)
        np.testing.assert_array_equal(before.stuff_plus, after.stuff_plus)
        self.assertTrue(after.arsenal_history_available.eq(0).all())

    def test_artifacts_and_no_overwrite(self):
        metrics = json.loads((self.args.salida/"metricas.json").read_text())
        self.assertEqual(len(metrics), 5)
        self.assertTrue((self.args.salida/"mapa_movimiento.csv").exists())
        with self.assertRaises(FileExistsError):
            v9.train(self.args)
        with self.assertRaises(FileExistsError):
            v9.evaluate(self.args)

    def test_shap_reconstructs_score_including_shrinkage(self):
        from explicar_v9 import explain_physical
        rows = self.data.query("year == 2026").head(4).copy()
        for processor in [{"method": "identity"}, {"method": "shrink", "weight": .35}]:
            meta = copy.deepcopy(self.bundle[0])
            meta["tasks"]["stuff_run_value"]["postprocessor"] = processor
            bundle = meta, self.bundle[1]
            explanation = explain_physical(rows, bundle)
            np.testing.assert_allclose(explanation["score"], v9.infer(rows, bundle).stuff_plus, atol=1e-8)


class IncrementalPipelineTests(PipelineTests):
    incremental_gate = True

    def test_parent_fallback_survives_serialization_and_has_zero_environment_delta(self):
        meta = copy.deepcopy(self.bundle[0])
        for task, parent in v9.PARENTS.items():
            meta["tasks"][task]["postprocessor"] = {"method": "parent", "task": parent}
        # Deliberately scramble keys as sorted JSON does.
        meta = json.loads(json.dumps(meta, sort_keys=True))
        rows = self.data.query("year == 2026").head(5).copy()
        predicted = v9.infer(rows, (meta, self.bundle[1]))
        np.testing.assert_array_equal(predicted.pred_xrunvalue, predicted.pred_environment_run_value)
        rows["altitude_category"] = "unseen_environment"
        after = v9.infer(rows, (meta, self.bundle[1]))
        np.testing.assert_array_equal(predicted.pitching_plus, after.pitching_plus)

    def test_incremental_decisions_name_their_control(self):
        for task, parent in v9.PARENTS.items():
            item = self.bundle[0]["tasks"][task]
            self.assertEqual(item["selection"]["control_task"], parent)
            if not item["selection"]["promoted"]:
                self.assertEqual(item["postprocessor"], {"method": "parent", "task": parent})


if __name__ == "__main__":
    unittest.main()
