import unittest
from pathlib import Path

from dashboard_decisiones import comparison_rows, game_variation
from pitch_altitude_lab import relative_density, transfer_movement


class AltitudeAndComparisonTests(unittest.TestCase):
    def test_constancy_uses_game_means_not_pitch_spread(self):
        import pandas as pd
        frame = pd.DataFrame({'year': [2026]*3, 'pitcher_anon_id': ['p']*3,
            'game_anon_id': ['a', 'a', 'b'], 'pitching_plus': [80., 120., 110.]})
        result = game_variation(frame).iloc[0]
        self.assertEqual(result.games_with_scores, 2)
        self.assertAlmostEqual(result.variation_between_games, 50 ** .5)

    def test_density_movement_invariants(self):
        measured = {'RelSpeed': 92., 'HorzBreak': -8., 'InducedVertBreak': 16.}
        self.assertEqual(relative_density(0), 1)
        self.assertAlmostEqual(relative_density(2240), .802, delta=.002)
        self.assertEqual(transfer_movement(measured, 2240, 2240), measured)
        high = transfer_movement(measured, 0, 2240)
        self.assertEqual(high['RelSpeed'], measured['RelSpeed'])
        self.assertLess(abs(high['HorzBreak']), abs(measured['HorzBreak']))
        self.assertLess(high['InducedVertBreak'], measured['InducedVertBreak'])
        back = transfer_movement(high, 2240, 0)
        for key in measured:
            self.assertAlmostEqual(back[key], measured[key])
        self.assertEqual(measured['HorzBreak'], -8.)
        for invalid in [float('nan'), float('inf'), -1, 3001]:
            with self.assertRaises(ValueError):
                relative_density(invalid)

    def test_comparison_preserves_units_and_direction(self):
        rows = comparison_rows({'stuff_plus': 110, 'p_whiff': .12}, {'stuff_plus': 100, 'p_whiff': .10})
        self.assertEqual(rows[0]['Diferencia'], 10)
        self.assertEqual(rows[0]['Unidad'], 'puntos')
        self.assertAlmostEqual(rows[1]['Diferencia'], 2)
        self.assertEqual(rows[1]['Unidad'], 'pp')
        self.assertEqual(comparison_rows({}, {}), [])


@unittest.skipUnless(Path('stuff_plus_output_v9_estadios/bundle.json').exists(), 'Requires local models')
class DecisionWorkflowTests(unittest.TestCase):
    def test_reference_lab_dossier_and_confidence(self):
        from streamlit.testing.v1 import AppTest
        from test_dashboard_navigation_helpers import navigate
        app = AppTest.from_file('dashboard_stuff_plus.py').run(timeout=60)
        next(w for w in app.button if w.label == 'Ver evaluación del lanzamiento').click().run(timeout=60)
        before = app.session_state['start_result']
        comparison = app.session_state['start_comparison']
        self.assertEqual(before[1]['stuff_plus'], comparison[1]['stuff_plus'])
        next(w for w in app.toggle if w.key == 'altitude-lab-enabled').set_value(True).run(timeout=60)
        next(w for w in app.slider if w.key == 'lab-destination').set_value(1500).run(timeout=60)
        self.assertEqual(app.session_state['start_result'], before)
        self.assertFalse(app.exception)
        next(w for w in app.selectbox if w.label == 'Comparar con').select('mexico_ahh')
        next(w for w in app.button if w.label == 'Ver evaluación del lanzamiento').click().run(timeout=60)
        for key in ['stuff_plus', 'location_plus', 'pitching_plus', 'p_whiff', 'p_home_run_per_pitch']:
            self.assertEqual(app.session_state['start_result'][1][key], app.session_state['start_comparison'][1][key])
        navigate(app, 'Lanzadores').run(timeout=60)
        self.assertFalse(app.exception)
        choice = next(w for w in app.selectbox if w.key == 'movement_pitcher')
        choice.select_index(len(choice.options)-1).run(timeout=60)
        next(w for w in app.selectbox if w.key == 'pitcher-decision-order').select('Mayor muestra de lanzamientos').run(timeout=60)
        self.assertFalse(app.exception)
        self.assertTrue(any('Su repertorio' in w.value for w in app.markdown))
        navigate(app, 'Confianza').run(timeout=60)
        self.assertFalse(app.exception)
        self.assertTrue(any('confiable' in w.value for w in app.title))


if __name__ == '__main__':
    unittest.main()
