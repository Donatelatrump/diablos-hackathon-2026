"""Flujo real v7, incluidos fallback y física adicional."""
import importlib.util
import unittest
from pathlib import Path
from proyecto_io import bundle_ready

ROOT = Path(__file__).resolve().parents[1]
AVAILABLE = importlib.util.find_spec("streamlit") is not None and bundle_ready(ROOT / "stuff_plus_output_v7") and (ROOT / "stuff_plus_output_v7" / "verificacion.json").exists()


@unittest.skipUnless(AVAILABLE, "Requiere Streamlit y artefactos v7 verificados")
class DashboardV7Tests(unittest.TestCase):
    def test_simulation_and_calibration_report(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(ROOT / "dashboard_stuff_plus_v7.py")).run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 5)
        self.assertTrue(any("Faltan mediciones" in item.value for item in app.info))
        app.checkbox[0].check().run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertFalse(any("Faltan mediciones" in item.value for item in app.info))
        score = app.metric[0].value
        next(item for item in app.number_input if item.label == "Altura en plato (pies)").set_value(4.5).run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.metric[0].value, score)
        next(item for item in app.selectbox if item.label == "Ordenar arsenal por").select("Whiff dado swing").run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertGreater(len(app.dataframe[-1].value), 0)
        self.assertTrue((ROOT / "stuff_plus_output_v7" / "calibracion_whiff.png").exists())


if __name__ == "__main__":
    unittest.main()
