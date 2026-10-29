import unittest
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless((ROOT / "stuff_plus_output_v8/bundle.json").exists(), "Requiere artefactos v8")
class DashboardRevisionTests(unittest.TestCase):
    def test_views_probabilities_sources_and_score_filter(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(ROOT / "src/dashboard_stuff_plus_v8.py")).run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue({"Scores y descargas", "Estadios y altitudes"}.issubset({tab.label for tab in app.tabs}))
        probabilities = next(table.value for table in app.dataframe if "Probabilidad (%)" in table.value.columns)
        self.assertEqual(len(probabilities), 9)
        self.assertTrue(probabilities["Probabilidad (%)"].between(0, 100).all())
        self.assertTrue(any("0 de 2,127 juegos" in item.value for item in app.markdown))
        self.assertTrue(any("no supera" in item.value for item in app.warning))
        next(item for item in app.selectbox if item.label == "Pitcher para explorar lanzamientos").select("pitcher_00408").run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        exported = next(table.value for table in app.dataframe if "PitchUID" in table.value.columns)
        self.assertEqual(set(exported.pitcher_anon_id), {"pitcher_00408"})
        next(item for item in app.selectbox if item.label == "Estadio para comparar altitud").select("kanasin_cervera").run(timeout=60)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("carece de altitud verificada" in item.value for item in app.warning))

    def test_local_explanation_reconstructs_both_reference_modes(self):
        import entrenar_stuff_plus_v8 as v8
        from explicacion_simulador_v8 import explain_stuff
        bundle = v8.load_bundle(ROOT / "stuff_plus_output_v8")
        row = dict(PitchUID="sim", pitcher_anon_id="Sin historial", AutoPitchType="Four-Seam", PitcherThrows="Right", BatterSide="Right",
                   RelSpeed=92., EffectiveVelo=92., SpinRate=2200., SpinAxis=180., InducedVertBreak=14., HorzBreak=10.,
                   VertBreak=-15., Extension=6., RelHeight=5.8, RelSide=.5, PlateLocHeight=2.5, PlateLocSide=0., Balls=0, Strikes=0, altitude_category="No Altitude")
        for additional in [{}, dict(pfxx=-5., pfxz=8., vx0=4., vy0=-132., vz0=-4., ax0=-5., ay0=24., az0=-23., ZoneSpeed=85., SpeedDrop=7., ZoneTime=.4)]:
            frame = {**row, **additional}
            score = v8.infer(pd.DataFrame([frame]), bundle).iloc[0]
            base, table = explain_stuff(frame, bundle, score.stuff_plus, score.score_reference_id)
            np.testing.assert_allclose(base+table.iloc[:,1].sum(), score.stuff_plus, atol=1e-6)


if __name__ == "__main__":
    unittest.main()
