import unittest
from pathlib import Path
from proyecto_io import bundle_ready
ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(bundle_ready(ROOT/"stuff_plus_output_v8") and (ROOT/"stuff_plus_output_v8/verificacion.json").exists(),"Requiere modelos v8 completos y verificados")
class DashboardV8Tests(unittest.TestCase):
    def test_simulation_velocity_and_ranking(self):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_file(str(ROOT/"dashboard_stuff_plus_v8.py")).run(timeout=60)
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any("Faltan mediciones" in i.value for i in app.info))
        app.checkbox[0].check().run(timeout=60)
        self.assertEqual(len(app.exception),0)
        self.assertFalse(any("Faltan mediciones" in i.value for i in app.info))
        score=app.metric[0].value
        next(i for i in app.number_input if i.label=="Altura en plato (pies)").set_value(4.5).run(timeout=60)
        self.assertEqual(app.metric[0].value,score)
        next(i for i in app.number_input if i.label=="Velocidad en plato (mph)").set_value(86.).run(timeout=60)
        self.assertEqual(len(app.exception),0)
        next(i for i in app.selectbox if i.label=="Ordenar arsenal por").select("Whiff dado swing").run(timeout=60)
        self.assertEqual(len(app.exception),0)
        self.assertGreater(len(app.dataframe[-1].value),0)


if __name__=="__main__": unittest.main()
