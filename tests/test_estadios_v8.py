import unittest
import pandas as pd
from estadios_v8 import attach_stadiums, audit


class StadiumLinkTests(unittest.TestCase):
    def setUp(self):
        self.games = pd.DataFrame({"year": [2024, 2024, 2025], "game_anon_id": ["g1", "g1", "g2"],
                                   "PitchUID": ["p1", "p2", "p3"], "altitude_category": ["Extreme Altitude", "Extreme Altitude", None]})
        self.catalog = pd.DataFrame({"stadium_id": ["ahh", "puebla"], "stadium": ["AHH", "Puebla"],
                                     "altitude_m": [2232, 2192], "altitude_source": ["https://example.org/a", "https://example.org/b"]})
        self.mapping = pd.DataFrame({"year": [2024], "game_anon_id": ["g1"], "stadium_id": ["puebla"], "source_url": ["https://example.org/juego"]})

    def test_same_category_does_not_assign_any_stadium_without_mapping(self):
        empty = self.mapping.iloc[:0]
        linked = attach_stadiums(self.games, empty, self.catalog)
        self.assertTrue(linked.stadium_id.isna().all())
        self.assertEqual(len(linked), 3)

    def test_exact_mapping_reaches_every_pitch_and_leaves_others_unknown(self):
        linked = attach_stadiums(self.games, self.mapping, self.catalog)
        self.assertEqual(linked.loc[linked.game_anon_id.eq("g1"), "stadium_id"].tolist(), ["puebla", "puebla"])
        self.assertTrue(linked.loc[linked.game_anon_id.eq("g2"), "stadium_id"].isna().all())

    def test_conflicting_duplicate_unknown_game_or_missing_evidence_rejected(self):
        variants = [pd.concat([self.mapping, self.mapping]),
                    self.mapping.assign(year=2025),
                    self.mapping.assign(source_url=""),
                    self.mapping.assign(stadium_id="inventado")]
        for mapping in variants:
            with self.subTest(mapping=mapping.to_dict("records")):
                with self.assertRaises(ValueError):
                    attach_stadiums(self.games, mapping, self.catalog)

    def test_missing_altitude_is_retained_in_audit(self):
        result = audit(self.games)
        self.assertEqual(result["missing_altitude_pitches"], 1)
        self.assertEqual(sum(row["pitches"] for row in result["categories"]), 3)
        self.assertFalse(result["stadium_identifiable_from_altitude_alone"])


if __name__ == "__main__":
    unittest.main()
