import unittest
import importlib.util
import numpy as np
import pandas as pd

from coherent_events import event_labels,joint_predictions,fit_temperature,temperature_probabilities,fit_event_values,expected_legacy_value


class JointEventTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('lightgbm'),'Optional LightGBM experiment dependency')
    def test_report_compares_brier_and_calibration_on_the_same_rows(self):
        from probar_modelo_conjunto_ensamble import gain
        rows=pd.DataFrame({'year':[2024]*40,'game_anon_id':np.repeat(np.arange(10).astype(str),4)})
        y=np.tile([0,0,0,1],10)
        r=gain(rows,y,np.full(40,.5),np.full(40,.25))
        self.assertAlmostEqual(r['control_mse'],.25)
        self.assertAlmostEqual(r['candidate_mse'],.1875)
        self.assertAlmostEqual(r['control_ece'],.25)
        self.assertAlmostEqual(r['candidate_ece'],0.)

    @unittest.skipUnless(importlib.util.find_spec('lightgbm'),'Optional LightGBM experiment dependency')
    def test_ensemble_categories_are_fitted_on_training_only(self):
        from probar_modelo_conjunto_ensamble import categorical_frames
        from tests.test_stuff_plus_v9 import synthetic_data
        train=synthetic_data().iloc[:2].copy()
        test=train.copy();test['AutoPitchType']='unseen_type'
        a,b=categorical_frames([train,test],['AutoPitchType','RelSpeed'])
        self.assertNotIn('unseen_type',a.AutoPitchType.cat.categories)
        self.assertTrue(b.AutoPitchType.isna().all())
        self.assertEqual(len(b),len(test))

    def test_hbp_is_separate_and_unknown_not_imputed(self):
        labels=event_labels(pd.DataFrame({'PitchCall':['BallCalled','HitByPitch','Undefined']}))
        self.assertEqual(labels.iloc[:2].tolist(),[0.,5.])
        self.assertTrue(np.isnan(labels.iloc[2]))

    def test_joint_and_conditional_probabilities_obey_inclusion_rules(self):
        rng=np.random.default_rng(7)
        events=rng.dirichlet(np.ones(6),size=1000)
        contact=rng.dirichlet(np.ones(3),size=1000)
        p=joint_predictions(events,rng.uniform(0,1,size=1000),contact)
        self.assertTrue((p.p_whiff<=p.p_whiff_given_swing+1e-12).all())
        self.assertTrue((p.p_home_run_per_pitch<=p.p_ball_in_play+1e-12).all())
        self.assertTrue((p.p_weak_contact+p.p_hard_contact<=1+1e-12).all())
        self.assertTrue((p.p_called_strike+p.p_whiff+p.p_ball_in_play<=1+1e-12).all())
        self.assertTrue(((p>=0)&(p<=1)).all().all())
        # No swings: defined zero conditional, never a nonfinite ratio.
        zero=joint_predictions([[1,0,0,0,0,0]],[.2],[[0,1,0]])
        self.assertEqual(zero.p_whiff_given_swing.iloc[0],0.)

    def test_bad_distributions_are_rejected(self):
        with self.assertRaises(ValueError):
            joint_predictions([[1,1,0,0,0,0]],[.1],[[0,1,0]])
        with self.assertRaises(ValueError):
            joint_predictions([[1,0,0,0,0,0]],[np.nan],[[0,1,0]])

    def test_calibration_preserves_distribution_and_does_not_change_inputs(self):
        p=np.array([[.9,.1],[.9,.1],[.2,.8],[.2,.8]])
        before=p.copy()
        temperature=fit_temperature(p,[0,1,1,0])
        calibrated=temperature_probabilities(p,temperature)
        np.testing.assert_allclose(calibrated.sum(axis=1),1.)
        np.testing.assert_array_equal(p,before)
        self.assertTrue(np.isfinite(calibrated).all())

    def test_same_run_value_target_uses_fit_table_and_conditional_contact(self):
        fit=pd.DataFrame({'PitchCall':['BallCalled','HitByPitch','InPlay'],'Balls':[0.,0.,0.],
                          'Strikes':[0.,0.,0.],'run_value_proxy':[.03,.33,.47]})
        table=fit_event_values(fit)
        rows=fit.iloc[:1]
        # Entire mass on contact uses the conditional regressor, not fit mean.
        value=expected_legacy_value([[0,0,0,0,1,0]],rows,[-.27],table)
        self.assertAlmostEqual(value[0],-.27)
        hbp=expected_legacy_value([[0,0,0,0,0,1]],rows,[10.],table)
        self.assertAlmostEqual(hbp[0],.33)


if __name__=='__main__':
    unittest.main()
