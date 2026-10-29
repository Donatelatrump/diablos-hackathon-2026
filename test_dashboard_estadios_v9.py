import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest
from test_dashboard_navigation_helpers import navigate

ROOT = Path(__file__).resolve().parent
READY = (ROOT / 'stuff_plus_output_v9_estadios/estadios.csv').is_file()


@unittest.skipUnless(READY, 'Requiere entrenamiento y reporte por estadios completos')
class StadiumDashboardTests(unittest.TestCase):
    def test_compare_stadiums_and_preserve_physical_score(self):
        app = AppTest.from_file(str(ROOT / 'dashboard_stuff_plus.py')).run(timeout=60)
        navigate(app, 'Simular y comparar v9').run(timeout=60)
        self.assertEqual(len(app.exception), 0)

        chooser = next(w for w in app.selectbox if w.label == 'Experimento')
        self.assertEqual(chooser.value, 'v9 por estadios · Harp Helú')
        selection = next(w for w in app.multiselect if w.label == 'Estadios para comparar')
        self.assertIn('mexico_ahh', selection.value)
        physical = [m.value for m in app.metric if m.label == 'Stuff+ · física']
        self.assertEqual(len(physical), 3)
        self.assertEqual(len(set(physical)), 1)
        if (ROOT / 'reports/v9_estadios/complemento/season/indice_integral.json').exists():
            self.assertEqual(len([m for m in app.metric if m.label == 'Índice integral']), 3)
            outs = [float(m.value.rstrip('%')) for m in app.metric if m.label == 'Out al terminar el turno']
            self.assertEqual(len(outs), 3)
            self.assertTrue(all(0 <= p <= 100 for p in outs))
        selection.set_value(['mexico_ahh']).run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual([m.value for m in app.metric if m.label == 'Stuff+ · física'], physical[:1])
        next(w for w in app.button if w.label == 'Explicar este pitch').click().run(timeout=60)
        self.assertEqual(len(app.exception), 0)

    def test_profile_support_and_empty_comparison_are_explained(self):
        app = AppTest.from_file(str(ROOT / 'dashboard_stuff_plus.py')).run(timeout=60)
        navigate(app, 'Simular y comparar v9').run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        next(w for w in app.selectbox if w.key == 'coach_profile_type').select('Knuckleball').run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any('Muestra insuficiente' in w.value for w in app.warning))
        next(w for w in app.multiselect if w.label == 'Estadios para comparar').set_value([]).run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any('Selecciona al menos' in w.value for w in app.info))
        navigate(app, 'Lanzadores').run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any(w.key == 'movement_pitcher' for w in app.selectbox))


if __name__ == '__main__':
    unittest.main()
