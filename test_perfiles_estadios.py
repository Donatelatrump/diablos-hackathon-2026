import unittest
import numpy as np
import pandas as pd
from analizar_perfiles_estadios import cluster_mean_interval, common_support


class ProfileEvidenceTests(unittest.TestCase):
    def test_constant_cluster_delta_has_exact_interval(self):
        result=cluster_mean_interval(np.repeat(.02,101), ['a']*100+['b'])
        np.testing.assert_allclose(result,[.02,.02,.02])

    def test_single_game_does_not_claim_confidence_interval(self):
        mean,low,high=cluster_mean_interval([1.,3.],['a','a'])
        self.assertEqual(mean,2.)
        self.assertIsNone(low)
        self.assertIsNone(high)

    def test_support_rejects_small_samples_and_extreme_physics(self):
        data=pd.DataFrame({'AutoPitchType':['Slider']*800,'PitcherThrows':['Right']*800,
            'year':[2024]*800,'game_anon_id':[f'g{i//20}' for i in range(800)],
            'stadium_id':['mexico_ahh']*400+['veracruz_avila']*400,
            'RelSpeed':[90.]*800,'InducedVertBreak':[10.]*800,'HorzBreak':[5.]*800,'SpinRate':[2000.]*800})
        test=data.iloc[:2].copy()
        test.loc[1,'RelSpeed']=150.
        valid,coverage=common_support(data,test)
        self.assertEqual(valid.tolist(),[True,False])
        self.assertEqual(coverage.n_supported.iloc[0],1)
        valid,_=common_support(data.iloc[:30],test)
        self.assertFalse(valid.any())


if __name__=='__main__':
    unittest.main()
