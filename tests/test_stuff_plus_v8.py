import unittest
import numpy as np
import pandas as pd
import entrenar_stuff_plus_v8 as v8


class V8Tests(unittest.TestCase):
    def test_selection_keeps_games_together(self):
        frame=pd.DataFrame({"year":np.repeat([2024,2025],40),"game_anon_id":list(np.repeat(np.arange(20),2))*2})
        mask=v8.selection_halves(frame)
        self.assertTrue(mask.any() and (~mask).any())
        self.assertEqual(frame.assign(role=mask).groupby(["year","game_anon_id"]).role.nunique().max(),1)
    def test_confirmation_rejects_overfit(self):
        y=np.tile([0.,1.],40); tune=np.arange(80)%4<2; years=np.repeat([2024,2025],40)
        p=np.where(tune,y,1-y)
        result=v8.choose(y,{"control":np.full(80,.5),"candidate":p},tune,years)
        self.assertEqual(result["candidate"],"candidate")
        self.assertFalse(result["promoted"])
    def test_consistent_gain_promotes(self):
        y=np.tile([0.,1.],40); tune=np.arange(80)%4<2; years=np.repeat([2024,2025],40)
        self.assertTrue(v8.choose(y,{"control":np.full(80,.5),"candidate":.1+.8*y},tune,years)["promoted"])
    def test_unknown_family_uses_global_group(self):
        self.assertEqual(v8.family(pd.DataFrame({"AutoPitchType":["Slider","Knuckleball"]})).tolist(),["breaking","other"])
    def test_missing_measurements_disable_new_model(self):
        frame=pd.DataFrame({"enhancement_available":[True,True],"ZoneSpeed":[85.,np.nan],"SpeedDrop":[5.,5.],"ZoneTime":[.4,.4]})
        self.assertEqual(v8.available(frame).tolist(),[True,False])
    def test_physics_features_exclude_context_and_outcomes(self):
        for task in v8.v7.COMPONENTS:
            self.assertFalse(set(v8.spec_for(task)[1]) & {"ExitSpeed","Angle","year","PlateLocHeight","PlateLocSide","Balls","Strikes","BatterSide","altitude_category"})


if __name__=="__main__": unittest.main()
