"""Pruebas de integridad estadistica e inferencia de Stuff+ v5."""
import unittest

import numpy as np
import pandas as pd

import entrenar_stuff_plus_v5 as v5


def sample():
    rows = []
    for year in [2024, 2025, 2026]:
        for i in range(10):
            rows.append(dict(PitchUID=f"{year}-{i}", year=year, game_anon_id=f"g{i}",
                             pitcher_anon_id="p1", AutoPitchType="Four-Seam" if i < 7 else "Sinker",
                             RelSpeed=90. + year - 2024, InducedVertBreak=12., HorzBreak=5.,
                             RelHeight=6., RelSide=1., Extension=6., SpinAxis=180.,
                             PitchCall="InPlay", play_result="Single", hit_type="GroundBall",
                             ExitSpeed=100., Balls=i % 4, Strikes=i % 3))
    return pd.DataFrame(rows)


class IntegrityTests(unittest.TestCase):
    def test_future_cannot_change_past_features(self):
        raw = v5.prepare_raw(sample())
        original = v5.historical_features(raw)
        raw.loc[raw.year.eq(2026), "RelSpeed"] += 50
        changed = v5.historical_features(raw)
        pd.testing.assert_frame_equal(original.loc[original.year.lt(2026)], changed.loc[changed.year.lt(2026)])

    def test_primary_fastball_is_not_mixed_with_sinker(self):
        raw = sample().query("year == 2024").copy()
        raw.loc[raw.AutoPitchType.eq("Sinker"), "RelSpeed"] = 70.
        self.assertEqual(v5.fit_profile(raw)["fastballs"][0]["RelSpeed"], 90.)

    def test_game_partitions_are_disjoint(self):
        fit, valid = v5.group_partition(sample(), 42)
        keys = lambda f: set(zip(f.year, f.game_anon_id))
        self.assertFalse(keys(fit) & keys(valid))
        self.assertFalse(set(fit.PitchUID) & set(valid.PitchUID))

    def test_run_value_is_row_local(self):
        frame = sample()
        before = v5.observed_run_value(frame)
        frame.loc[frame.year.eq(2026), "play_result"] = "HomeRun"
        after = v5.observed_run_value(frame)
        pd.testing.assert_series_equal(before.loc[frame.year.lt(2026)], after.loc[frame.year.lt(2026)])
        self.assertEqual(after.iloc[-1], 1.4)

    def test_count_baseline_never_reads_test_outcomes(self):
        frame = v5.prepare_raw(sample())
        fit, test = frame.query("year < 2026"), frame.query("year == 2026").copy()
        before = v5.count_baseline(fit, test)
        test["run_value_proxy"] = 999.
        np.testing.assert_array_equal(before, v5.count_baseline(fit, test))

    def test_terminal_walk_and_strikeout_override_pitch_call(self):
        frame = pd.DataFrame({"PitchCall": ["BallCalled", "StrikeSwinging", "StrikeSwinging"],
                              "play_result": ["Walk", "Strikeout", "StrikeSwinging"]})
        np.testing.assert_allclose(v5.observed_run_value(frame), [.30, -.27, -.05])

    def test_strong_groundball_is_not_weak_contact(self):
        self.assertEqual(v5.prepare_raw(sample()).is_weak_contact.iloc[0], 0.)

    def test_reject_duplicate_pitchuids(self):
        frame = sample()
        with self.assertRaises(ValueError):
            v5.prepare_raw(pd.concat([frame, frame.iloc[:1]]))

    def test_missing_components_rejected_and_reference_fixed(self):
        predictions = pd.DataFrame({"pred_stuff_run_value": [.1, .2], "pred_xrunvalue": [.05, .18],
                                    "pred_environment_run_value": [.04, .15]})
        ref = v5.fit_reference(predictions)
        full = v5.add_scores(predictions, ref)
        one = v5.add_scores(predictions.iloc[:1], ref)
        self.assertEqual(full.stuff_plus.iloc[0], one.stuff_plus.iloc[0])
        predictions.loc[0, "pred_stuff_run_value"] = np.nan
        with self.assertRaises(ValueError):
            v5.add_scores(predictions, ref)


if __name__ == "__main__":
    unittest.main()
