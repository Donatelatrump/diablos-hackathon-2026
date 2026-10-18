"""Prueba del flujo real de la interfaz; necesita bundle v6 verificado y Streamlit."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AVAILABLE = importlib.util.find_spec("streamlit") is not None and (ROOT / "stuff_plus_output_v6" / "verificacion.json").exists()


@unittest.skipUnless(AVAILABLE, "Requiere Streamlit y artefactos v6 verificados")
class DashboardTests(unittest.TestCase):
    def test_real_inference_fallback_physics_and_ranking(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(ROOT / "dashboard_stuff_plus.py")).run(timeout=45)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 5)
        self.assertTrue(any("Faltan mediciones" in element.value for element in app.info))
        app.checkbox[0].check().run(timeout=45)
        self.assertEqual(len(app.exception), 0)
        self.assertFalse(any("Faltan mediciones" in element.value for element in app.info))
        score = app.metric[0].value
        plate = next(item for item in app.number_input if item.label == "Altura en plato (pies)")
        plate.set_value(4.5).run(timeout=45)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.metric[0].value, score)
        order = next(item for item in app.selectbox if item.label == "Ordenar arsenal por")
        order.select("Whiff dado swing").run(timeout=45)
        self.assertEqual(len(app.exception), 0)
        self.assertGreater(len(app.dataframe), 0)


if __name__ == "__main__":
    unittest.main()
