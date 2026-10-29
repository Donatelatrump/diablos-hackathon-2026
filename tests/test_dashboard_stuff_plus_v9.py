import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from tests.test_dashboard_navigation_helpers import navigate
from proyecto_io import bundle_ready

ROOT = Path(__file__).resolve().parents[1]


class WalkthroughTests(unittest.TestCase):
    def test_guide_explains_scale_and_archive_handles_lfs(self):
        app = AppTest.from_file(str(ROOT/"app.py")).run(timeout=60)
        navigate(app, "Entender el proyecto").run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any(t.label == "El reto y su alcance" for t in app.tabs))
        app.slider[0].set_value(90).run(timeout=60)
        self.assertEqual(app.metric[0].value, "90")
        navigate(app, "Entrega histórica v8").run(timeout=60)
        self.assertEqual(len(app.exception), 0)


@unittest.skipUnless(bundle_ready(ROOT/"stuff_plus_output_v9"), "Requiere modelos v9 entrenados")
class SimulatorTests(unittest.TestCase):
    def test_context_changes_preserve_physical_score(self):
        app = AppTest.from_file(str(ROOT/"app.py")).run(timeout=60)
        navigate(app, "Simular y comparar v9").run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        physical = [metric.value for metric in app.metric if metric.label == "Stuff+ · física"]
        self.assertEqual(len(physical), 3)
        self.assertEqual(len(set(physical)), 1)
        next(w for w in app.number_input if w.label == "Altura en plato (pies)").set_value(4.).run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual([m.value for m in app.metric if m.label == "Stuff+ · física"], physical)
        next(w for w in app.selectbox if w.label == "Tipo de lanzamiento").select("Four-Seam").run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any(tab.label == "Cómo se validó" for tab in app.tabs))
        next(w for w in app.button if w.label == "Explicar este pitch").click().run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("Atribuciones SHAP" in item.value for item in app.caption))

    @unittest.skipUnless((ROOT/"stuff_plus_output_v9_incremental/metricas.json").exists(), "Requiere evaluación incremental")
    def test_incremental_run_explains_fallback_and_can_switch_to_original(self):
        app = AppTest.from_file(str(ROOT/"app.py")).run(timeout=60)
        navigate(app, "Simular y comparar v9").run(timeout=60)
        chooser = next(w for w in app.selectbox if w.label == "Experimento")
        self.assertEqual(chooser.value, "v9 con validación incremental")
        self.assertTrue(any("no demuestra ausencia" in item.value for item in app.info))
        combined = [m.value for m in app.metric if m.label == "Pitching+ · combinado"]
        self.assertEqual(len(combined), 3)
        self.assertEqual(len(set(combined)), 1)
        chooser.select("v9 original").run(timeout=60)
        self.assertEqual(len(app.exception), 0)


if __name__ == "__main__":
    unittest.main()
