import unittest
from pathlib import Path
from proyecto_io import bundle_ready
import numpy as np
import pandas as pd
from analisis_operativo_v8 import paired_environment,pitcher_summary
from validar_pitchers_v8 import pitcher_roles


class AnalysisTests(unittest.TestCase):
    def test_pitcher_roles_are_disjoint_reproducible(self):
        roles=pitcher_roles([f'p{i}' for i in range(100)])
        self.assertEqual(roles,pitcher_roles([f'p{i}' for i in range(100)]))
        self.assertEqual(sum(map(len,roles.values())),100)
        for i,a in enumerate(roles.values()):
            for b in list(roles.values())[i+1:]: self.assertFalse(a&b)
    def test_matching_recovers_known_difference(self):
        rows=[]
        for p in range(8):
            for category,value in [('No Altitude',2.),('Extreme Altitude',3.)]:
                for _ in range(5): rows.append(dict(pitcher_anon_id=str(p),year=2024,AutoPitchType='Slider',BatterSide='Right',Balls=0,Strikes=0,altitude_category=category,y=value+p))
        result=paired_environment(pd.DataFrame(rows),'y','Extreme Altitude')
        self.assertEqual(result['delta'],1.)
        self.assertEqual(result['ci_low'],1.)
        self.assertEqual(result['n_pitchers'],8)
    def test_no_overlap_does_not_invent_comparison(self):
        rows=pd.DataFrame([dict(pitcher_anon_id=str(i),year=2024,AutoPitchType='Slider',BatterSide='Right',Balls=0,Strikes=0,altitude_category='No Altitude',y=1.) for i in range(10)])
        self.assertIsNone(paired_environment(rows,'y','Extreme Altitude'))
    def test_one_game_has_no_between_game_interval(self):
        rows=pd.DataFrame(dict(year=[2026]*3,pitcher_anon_id=['p']*3,score_reference_id=['r']*3,PitchUID=['a','b','c'],game_anon_id=['g']*3,
             stuff_plus=[100.]*3,location_plus=[100.]*3,pitching_plus=[100.]*3,p_whiff=[.1]*3,p_whiff_given_swing=[.2]*3))
        result=pitcher_summary(rows)
        self.assertTrue(result.ci_low.isna().all())
        self.assertFalse(result.eligible.any())


@unittest.skipUnless(bundle_ready(Path(__file__).resolve().parents[1]/'stuff_plus_output_v8') and Path('entrega_v8/MANIFIESTO.json').exists(),'Requiere paquete y modelos v8 completos')
class DeliveryDashboardTests(unittest.TestCase):
    def test_operational_views(self):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'dashboard_stuff_plus_v8.py')).run(timeout=60)
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any(t.label=='Mapa y ficha' for t in app.tabs))
        app.checkbox[0].check().run(timeout=60)
        self.assertEqual(len(app.exception),0)
        pitcher=next(x for x in app.selectbox if x.label=='Pitcher de la ficha')
        pitcher.select('pitcher_00408').run(timeout=60)
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any('Muestra insuficiente' in x.value for x in app.warning))
        next(x for x in app.selectbox if x.label=='Resultado para comparar entornos').select('home_run').run(timeout=60)
        self.assertEqual(len(app.exception),0)
        self.assertTrue(any('Documento técnico PDF'==x.label for x in app.get('download_button')))


if __name__=='__main__': unittest.main()
