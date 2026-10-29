import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest
from test_dashboard_navigation_helpers import navigate
from proyecto_io import bundle_ready

ROOT = Path(__file__).resolve().parent


@unittest.skipUnless(bundle_ready(ROOT / "stuff_plus_output_v9_estadios"), "Requiere modelos locales")
class GuidedStartTests(unittest.TestCase):
    def test_example_submit_change_and_advanced_navigation(self):
        app = AppTest.from_file(str(ROOT / "dashboard_stuff_plus.py")).run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state["main_navigation"], "Inicio")
        self.assertEqual(len(app.tabs), 0)
        self.assertEqual(len(app.metric), 0)
        next(w for w in app.button if w.label == "Ver evaluación del lanzamiento").click().run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(next(w for w in app.metric if w.label == "Evaluación general").value.endswith("puntos"))
        self.assertTrue(any("No son un porcentaje" in w.value for w in app.markdown))
        next(w for w in app.selectbox if w.label == "Estadio").select("veracruz_avila")
        next(w for w in app.button if w.label == "Ver evaluación del lanzamiento").click().run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state["start_result"][2], "Estadio Universitario Beto Avila")
        next(w for w in app.selectbox if w.key == "start_pitch").select("Slider").run(timeout=60)
        self.assertEqual(len(app.metric), 0)  # Never label an old result as a new pitch.
        next(w for w in app.button if w.key == 'start-hand-Right').click().run(timeout=60)
        self.assertEqual(app.session_state['start_hand'], 'Right')
        self.assertEqual(len(app.exception), 0)
        next(w for w in app.button if w.label == 'Ver evaluación del lanzamiento').click().run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        navigate(app, "Simular y comparar v9").run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any(w.label == "Estadios para comparar" for w in app.multiselect))
        navigate(app, 'Lanzadores').run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any(t.value == 'Lanzadores y repertorios' for t in app.title))
        self.assertFalse(any(r.key == 'main_navigation' for r in app.radio))
        navigate(app, "Inicio").run(timeout=60)
        next(w for w in app.button if w.key == 'preset-Curveball').click().run(timeout=60)
        self.assertEqual(next(w for w in app.selectbox if w.key == 'start_pitch').value, 'Curveball')
        self.assertEqual(len(app.exception), 0)
        next(w for w in app.button if w.label == 'Ver la guía de resultados →').click().run(timeout=60)
        self.assertEqual(app.session_state["main_navigation"], 'Entender el proyecto')
        self.assertEqual(len(app.exception), 0)


if __name__ == "__main__":
    unittest.main()
