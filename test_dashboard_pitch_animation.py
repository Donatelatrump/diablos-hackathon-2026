import json
import re
import unittest

from dashboard_pitch_animation import animation_document


class PitchAnimationTests(unittest.TestCase):
    def test_lab_supplies_the_actual_origin_as_second_trajectory(self):
        origin = {'RelSpeed': 90, 'HorzBreak': -10, 'InducedVertBreak': 15}
        destination = {'RelSpeed': 90, 'HorzBreak': -8, 'InducedVertBreak': 12}
        document = animation_document('Four-Seam', 'Left', destination, reference=origin)
        payload = json.loads(re.search(r'const data=(.*?);', document).group(1))
        self.assertEqual(payload['comparison'], origin)
        self.assertEqual(payload['HorzBreak'], -8)
        self.assertIn('destino exploratorio', document)
        self.assertIsNone(animation_document('Four-Seam', 'Left', destination, reference={}))

    def test_uses_signed_measurements_for_each_hand(self):
        for hand, horizontal in [("Right", -12.5), ("Left", 13.2)]:
            document = animation_document("Slider", hand,
                {"RelSpeed": 86, "HorzBreak": horizontal, "InducedVertBreak": 4.5})
            payload = json.loads(re.search(r"const data=(.*?);", document).group(1))
            self.assertEqual(payload["HorzBreak"], horizontal)
            self.assertEqual(payload["RelSpeed"], 86)
            self.assertEqual(payload["hand"], hand)
            self.assertIn("prefers-reduced-motion", document)
            self.assertNotIn("__MEASUREMENTS__", document)
            self.assertNotIn("__THREE_SCENE__", document)
            self.assertIn('id="scene"', document)
            self.assertNotIn('<script src=', document)

    def test_missing_invalid_and_nonfinite_measurements_hide_animation(self):
        for speed in [None, float("nan"), float("inf"), 0, -1, "bad"]:
            self.assertIsNone(animation_document("Slider", "Right",
                {"RelSpeed": speed, "HorzBreak": 12, "InducedVertBreak": 3}))


if __name__ == "__main__":
    unittest.main()
