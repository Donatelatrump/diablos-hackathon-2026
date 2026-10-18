"""Integridad de variables fisicas, seleccion y bootstrap agrupado de v6."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import entrenar_stuff_plus_v5 as v5
import entrenar_stuff_plus_v6 as v6
from reportar_mejora_v6 import arsenal_ranking


def physical_sample():
    return pd.DataFrame([dict(PitcherThrows="Right", RelSpeed=90., EffectiveVelo=91., SpinRate=2200.,
                             SpinAxis=180., HorzBreak=10., InducedVertBreak=12., RelSide=1.,
                             Extension=6., RelHeight=6., pfxx=5., pfxz=7., vx0=0., vy0=-100.,
                             vz0=0., ax0=0., ay0=20., az0=-32.174)])


class PhysicsTests(unittest.TestCase):
    def test_projection_removes_gravity_and_separates_drag(self):
        result = v6.enhance(physical_sample())
        self.assertAlmostEqual(result.drag_proxy.iloc[0], 20.)
        self.assertAlmostEqual(result.lift_magnitude_proxy.iloc[0], 0.)
        raw = physical_sample()
        raw["ax0"] = 5.
        self.assertAlmostEqual(v6.enhance(raw).lift_magnitude_proxy.iloc[0], 5.)

    def test_physics_does_not_read_outcomes_location_or_altitude(self):
        raw = physical_sample()
        before = v6.enhance(raw)
        raw["PlateLocHeight"], raw["PlateLocSide"] = 99., 99.
        raw["Balls"], raw["Strikes"], raw["altitude_category"] = 3, 2, "Extreme Altitude"
        raw["ExitSpeed"], raw["is_whiff"], raw["play_result"] = 999., 1, "HomeRun"
        after = v6.enhance(raw)
        pd.testing.assert_frame_equal(before[v6.SHAPE_DERIVED + v6.AERO_DERIVED], after[v6.SHAPE_DERIVED + v6.AERO_DERIVED])

    def test_missing_measurements_trigger_fallback(self):
        raw = physical_sample().drop(columns="ax0")
        result = v6.enhance(raw)
        self.assertFalse(result.enhancement_available.iloc[0])
        self.assertTrue(np.isnan(result.drag_proxy.iloc[0]))

    def test_zero_speed_vector_is_not_valid_aerodynamics(self):
        raw = physical_sample()
        raw[["vx0", "vy0", "vz0"]] = 0.
        self.assertFalse(v6.enhance(raw).enhancement_available.iloc[0])

    def test_handedness_normalizes_horizontal_movement(self):
        raw = physical_sample()
        right = v6.enhance(raw)
        raw["PitcherThrows"], raw["HorzBreak"], raw["pfxx"], raw["RelSide"] = "Left", -10., -5., -1.
        left = v6.enhance(raw)
        for col in ["hb_arm_side", "pfxx_arm_side", "release_side_arm_side"]:
            self.assertEqual(right[col].iloc[0], left[col].iloc[0])

    def test_forbidden_inputs_not_in_stuff_features(self):
        forbidden = {"PlateLocHeight", "PlateLocSide", "Balls", "Strikes", "BatterSide", "altitude_category",
                     "Direction", "Angle", "ExitSpeed", "PitchCall", "vx0", "vy0", "vz0", "VertApprAngle", "HorzApprAngle"}
        self.assertFalse(set(v6.PHYSICAL) & forbidden)


class SelectionTests(unittest.TestCase):
    def test_worse_candidates_keep_v5(self):
        y = np.array([0., 1., 0., 1.])
        baseline = np.array([.1, .9, .1, .9])
        chosen, _ = v6.choose_mix(y, baseline, {"regularized": np.full(4, .5), "deep": np.full(4, .5)})
        self.assertEqual(chosen["members"], [])
        self.assertEqual(chosen["weight"], 0.)

    def test_strong_candidate_selected_by_proper_error(self):
        y = np.array([0., 1., 0., 1.])
        chosen, _ = v6.choose_mix(y, np.full(4, .5), {"regularized": y, "deep": 1-y})
        self.assertEqual(chosen["members"], ["regularized"])
        self.assertEqual(chosen["weight"], 1.)

    def test_tiny_development_gain_does_not_replace_v5(self):
        y = np.array([0., 1., 0., 1.])
        baseline = np.full(4, .5)
        tiny_change = baseline + np.array([-1., 1., -1., 1.]) * 1e-5
        chosen, _ = v6.choose_mix(y, baseline, {"regularized": tiny_change, "deep": tiny_change})
        self.assertEqual(chosen["weight"], 0.)

    def test_development_reader_excludes_2026(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.parquet"
            v5.write_parquet(pd.DataFrame({"year": [2024, 2025, 2026], "outcome": [0., 1., 999999.]}), path)
            development = v6.read_seasons(path, 2025)
            self.assertEqual(development.year.tolist(), [2024, 2025])
            self.assertNotIn(999999., development.outcome)

    def test_cluster_bootstrap_reproduces_known_paired_gain(self):
        frame = pd.DataFrame({"game_anon_id": ["a", "a", "b", "c"]})
        result = v6.game_bootstrap_comparison(frame, np.ones(4), np.zeros(4), np.full(4, .5), repetitions=100)
        self.assertAlmostEqual(result["relative_mse_reduction"], .75)
        self.assertAlmostEqual(result["ci95_low"], .75)
        self.assertAlmostEqual(result["ci95_high"], .75)
        self.assertEqual(result["n_games"], 3)


class RankingTests(unittest.TestCase):
    def test_small_sample_outlier_is_regularized_and_not_ranked_as_reliable(self):
        rows = []
        for i in range(102):
            mean = 140. if i < 2 else 100.
            rows.append({"PitchUID": str(i), "year": 2026, "pitcher_anon_id": "small" if i < 2 else "large",
                         "AutoPitchType": "Slider", "game_anon_id": "small_game" if i < 2 else f"g{i % 5}",
                         "stuff_plus": mean, "location_plus": 100., "pitching_plus": mean,
                         "score_reference_id": "v6_reference"})
        ranking = arsenal_ranking(pd.DataFrame(rows), repetitions=50).set_index("pitcher_anon_id")
        self.assertEqual(ranking.index[0], "large")
        self.assertFalse(ranking.loc["small", "ranking_eligible"])
        self.assertTrue(np.isnan(ranking.loc["small", "raw_mean_ci95_low"]))
        self.assertLess(ranking.loc["small", "stuff_plus_shrunk"], 110.)
        self.assertAlmostEqual(ranking.loc["large", "raw_mean_ci95_low"], 100.)


if __name__ == "__main__":
    unittest.main()
