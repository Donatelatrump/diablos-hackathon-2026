import copy
import unittest
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

from precision_features import past_context, fit_count_values, count_transition_target, FLIGHT
from precision_model import apply_precision, eligible_inputs, model_features


def identifier(t):
    return str(uuid.UUID(fields=(t,0,0x1000,0x80,0,1)))


class PrecisionFeatureTests(unittest.TestCase):
    def test_calibration_shrinks_sparse_stadium_and_handles_unseen(self):
        from calibracion_estadios_precision import fit_offsets,apply_offsets
        p=np.full(200,.1);y=np.tile([1.,0.],100);g=pd.Series(['a']*198+['b']*2)
        meta=fit_offsets(p,y,g,penalty=100.)
        self.assertLess(abs(meta['stadiums']['b']),.02)
        out=apply_offsets([.1,.1],pd.Series(['new',None]),meta)
        self.assertAlmostEqual(out[0],out[1])
        self.assertTrue(((out>0)&(out<1)).all())

    def raw(self):
        rows=[]
        for game,time,speed in [('a',100,90.),('b',200,92.),('c',300,96.)]:
            for i in range(12):
                rows.append(dict(year=2024,game_anon_id=game,PitchUID=identifier(time+i),pitcher_anon_id='p',
                    AutoPitchType='Four-Seam',RelSpeed=speed+i/10,HorzBreak=8.,InducedVertBreak=15.))
        return pd.DataFrame(rows)

    def test_sequence_and_recent_only_use_past(self):
        raw=self.raw()
        mask=raw.game_anon_id.isin(['a','c'])
        before=past_context(raw,mask)
        self.assertTrue(np.isnan(before.loc[0,'previous_velocity']))
        self.assertEqual(before.loc[1,'previous_velocity'],90.)
        self.assertEqual(before.loc[12,'observed_workload'],0.)
        self.assertEqual(before.loc[12,'recent_pitches'],12.)
        self.assertAlmostEqual(before.loc[24,'recent_velocity'],90.55)
        changed=raw.copy()
        changed.loc[changed.game_anon_id.eq('c'),'RelSpeed']=200.
        after=past_context(changed,mask)
        pd.testing.assert_frame_equal(before.iloc[:24],after.iloc[:24])
        shuffled=raw.sample(frac=1,random_state=3).reset_index(drop=True)
        reordered=past_context(shuffled,shuffled.game_anon_id.isin(['a','c']))
        a=before.assign(id=raw.PitchUID).set_index('id').sort_index()
        b=reordered.assign(id=shuffled.PitchUID).set_index('id').sort_index()
        pd.testing.assert_frame_equal(a,b)

    def test_ambiguous_order_disables_context(self):
        raw=self.raw()
        raw.loc[1,'PitchUID']=raw.loc[0,'PitchUID']
        context=past_context(raw,raw.game_anon_id.eq('a'))
        self.assertTrue(context.loc[:11,'observed_workload'].isna().all())
        self.assertEqual(context.loc[12,'recent_available'],0.)

    def test_count_target_is_training_only_and_foul_at_two_is_zero(self):
        raw=pd.DataFrame([
            {'PitchUID':'a','Balls':0,'Strikes':0,'PitchCall':'BallCalled','play_result':'BallCalled'},
            {'PitchUID':'b','Balls':1,'Strikes':0,'PitchCall':'InPlay','play_result':'Single'},
            {'PitchUID':'c','Balls':0,'Strikes':0,'PitchCall':'StrikeCalled','play_result':'NeutralPlay'},
            {'PitchUID':'d','Balls':0,'Strikes':1,'PitchCall':'InPlay','play_result':'Out'},
        ])
        pa=pd.DataFrame({'PitchUID':['a','b','c','d'],'pa_id':['1','1','2','2'],'out_within_pa':[0.,0.,1.,1.]})
        fit=raw.iloc[:2]
        values=fit_count_values(fit,pa,smoothing=0.)
        float_fit=fit.astype({'Balls':float,'Strikes':float})
        self.assertEqual(values,fit_count_values(float_fit,pa,smoothing=0.))
        self.assertEqual(values['training_pa'],1)
        self.assertAlmostEqual(values['values']['0-0'],.47)
        altered=raw.copy();altered.loc[3,'play_result']='HomeRun'
        self.assertEqual(values,fit_count_values(altered.iloc[:2],pa,smoothing=0.))
        foul=pd.DataFrame([{'Balls':1,'Strikes':2,'PitchCall':'FoulBall','play_result':'NeutralPlay'}])
        self.assertEqual(count_transition_target(foul,values).iloc[0],0.)
        with self.assertRaises(ValueError):
            fit_count_values(raw.iloc[:1],pa)

    def test_missing_or_bad_inputs_fall_back_and_never_change_scores(self):
        frame=pd.DataFrame({'RelSpeed':[90.]})
        meta={'required_inputs':FLIGHT,'bounds':{}}
        self.assertFalse(eligible_inputs(frame,meta).iloc[0])
        result=pd.DataFrame({'stuff_plus':[110.],'pitching_plus':[100.],'p_whiff_given_swing':[.2]})
        result_copy=copy.deepcopy(result)
        output=apply_precision(frame,result,({},{}),None)
        pd.testing.assert_frame_equal(output[result.columns],result_copy)
        self.assertFalse(output.precision_whiff_available.any())
        with self.assertRaises(ValueError):
            model_features(frame,['ExitSpeed'])

    def test_overlay_updates_only_conditional_whiff_with_valid_inputs(self):
        import entrenar_stuff_plus_v9 as v9
        from test_stuff_plus_v9 import synthetic_data
        frame=synthetic_data().iloc[:2].copy()
        for key,value in zip(FLIGHT,[82.,.43,7.,-1.,-2.,-6.,-1.]):
            frame[key]=value
        frame['RelSpeed']=90.
        frame.loc[frame.index[1],'ZoneTime']=np.nan
        result=pd.DataFrame({'stuff_plus':[105.,106.],'location_plus':[100.,101.],
            'pitching_plus':[102.,103.],'p_whiff_given_swing':[.2,.25],'p_whiff':[.1,.12]})
        class FixedModel:
            def predict_proba(self,x):
                return np.tile([.6,.4],(len(x),1))
        profile=v9.fit_profile(frame)
        bundle=({'profile':profile,'precision_base_bundle_sha256':'same'}, {})
        meta={'base_bundle_sha256':'same','required_inputs':FLIGHT,'bounds':{},'features':v9.LOCATION+FLIGHT,
            'baseline':{'prior':.2,'counts':{}},'postprocessor':{'method':'identity'}}
        out=apply_precision(frame,result,bundle,(meta,FixedModel()))
        self.assertEqual(out.p_whiff_given_swing.tolist(),[.4,.25])
        self.assertEqual(out.precision_whiff_available.tolist(),[True,False])
        pd.testing.assert_frame_equal(out.drop(columns=['p_whiff_given_swing','precision_whiff_available']),
                                      result.drop(columns=['p_whiff_given_swing']))
        wrong=copy.deepcopy(meta);wrong['base_bundle_sha256']='different'
        self.assertFalse(apply_precision(frame,result,bundle,(wrong,FixedModel())).precision_whiff_available.any())


@unittest.skipUnless(Path('stuff_plus_output_v9_estadios/bundle.json').exists(),'Requires local artifacts')
class PrecisionDashboardTests(unittest.TestCase):
    @unittest.skipUnless(Path('precision_count_output_2026_10_28/modelo.json').exists(),'Requires count model')
    def test_trained_count_model_accepts_scenarios_without_outcomes(self):
        import entrenar_stuff_plus_v9 as v9
        from precision_count_model import predict_count_transition
        bundle=v9.load_bundle('stuff_plus_output_v9_estadios')
        profile=bundle[0]['input_profiles'][0]
        row={**profile['median'],'AutoPitchType':profile['type'],'PitcherThrows':profile['hand'],
             'pitcher_anon_id':'unknown','PlateLocHeight':2.5,'PlateLocSide':0.,'Balls':0,'Strikes':0,
             'BatterSide':'Right','altitude_category':'No Altitude'}
        frame=pd.DataFrame([row])
        before=frame.copy(deep=True)
        result=predict_count_transition(frame)
        self.assertTrue(result.experimental.all())
        self.assertTrue(np.isfinite(result.expected_count_transition_proxy).all())
        pd.testing.assert_frame_equal(frame,before)

    def test_advanced_measurements_do_not_change_physical_score(self):
        from streamlit.testing.v1 import AppTest
        from test_dashboard_navigation_helpers import navigate
        app=AppTest.from_file('dashboard_stuff_plus.py').run(timeout=60)
        navigate(app,'Simular y comparar v9').run(timeout=60)
        next(w for w in app.selectbox if w.key=='sim_pitch_type').select('Four-Seam').run(timeout=60)
        before=[w.value for w in app.metric if w.label=='Stuff+ · física']
        for key,value in zip(FLIGHT,[82.,.43,7.,-1.,-2.,-6.,-1.]):
            next(w for w in app.number_input if str(w.key).endswith('-precision-'+key)).set_value(value)
        next(w for w in app.number_input if str(w.key).endswith('-workload')).set_value(0).run(timeout=60)
        next(w for w in app.checkbox if w.key=='preview-precision').set_value(True).run(timeout=60)
        self.assertFalse(app.exception)
        self.assertEqual(before,[w.value for w in app.metric if w.label=='Stuff+ · física'])


if __name__=='__main__':
    unittest.main()
