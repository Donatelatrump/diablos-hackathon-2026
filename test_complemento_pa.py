import unittest
import uuid
import numpy as np
import pandas as pd
from completar_targets_pa import reconstruct_pa, normalized_by_cohort
from indice_integral import fit_reference, score, COMPONENTS


def uid(time):
    return str(uuid.UUID(fields=(time,0,0x1000,0x80,0,0)))


class ReconstructionTests(unittest.TestCase):
    def rows(self):
        return pd.DataFrame(dict(PitchUID=[uid(i) for i in range(1,5)],year=[2025]*4,
            game_anon_id=['g']*4,batter_anon_id=['b']*4,Inning=[1]*4,
            **{'Top/Bottom':['Top']*4},Balls=[0,0,0,0],Strikes=[0,1,2,2],
            PitchCall=['StrikeCalled','StrikeSwinging','FoulBallNotFieldable','StrikeSwinging'],
            play_result=['NeutralPlay']*3+['Strikeout'],OutsOnPlay=[0,0,0,1]))

    def test_complete_pa_and_shuffled_order(self):
        rows=self.rows()
        labeled,audit=reconstruct_pa(rows.sample(frac=1,random_state=1))
        self.assertTrue(labeled.out_within_pa.eq(1).all())
        self.assertEqual(audit['valid_pa'],1)

    def test_missing_pitch_and_censoring_excluded(self):
        rows=self.rows()
        for incomplete in [rows.drop(index=1),rows.iloc[:-1],rows.iloc[1:]]:
            labeled,_=reconstruct_pa(incomplete)
            self.assertTrue(labeled.out_within_pa.isna().all())

    def test_dropped_third_strike_does_not_invent_out(self):
        rows=self.rows(); rows.loc[3,'OutsOnPlay']=0
        labeled,_=reconstruct_pa(rows)
        self.assertTrue(labeled.out_within_pa.eq(0).all())

    def test_runner_out_mid_pa_excluded(self):
        rows=self.rows(); rows.loc[1,'OutsOnPlay']=1
        labeled,_=reconstruct_pa(rows)
        self.assertTrue(labeled.out_within_pa.isna().all())

    def test_inning_boundary_not_joined(self):
        rows=self.rows(); rows.loc[3,'Inning']=2
        labeled,_=reconstruct_pa(rows)
        self.assertTrue(labeled.out_within_pa.isna().all())

    def test_adjacent_pas_same_batter_are_separate(self):
        rows=self.rows(); second=rows.copy(); second.PitchUID=[uid(i) for i in range(5,9)]
        labels,audit=reconstruct_pa(pd.concat([rows,second]))
        self.assertEqual(audit['valid_pa'],2)
        self.assertEqual(labels.pa_id.nunique(),2)


class ReferenceTests(unittest.TestCase):
    def test_normalization_and_fallback(self):
        d=pd.DataFrame({'year':[2026]*8,'stadium_id':['a']*4+['b']*3+[None], 's':[1,2,3,4,8,9,10,50]})
        output,refs=normalized_by_cohort(d,['s'],minimum=4)
        self.assertAlmostEqual(output.iloc[:4].s_temporada_estadio.mean(),100)
        self.assertAlmostEqual(output.iloc[:4].s_temporada_estadio.std(ddof=0),10)
        self.assertTrue(any(r['reference']=='season_fallback' for r in refs))

    def test_index_scale_direction_and_constant(self):
        p=pd.DataFrame({c:np.arange(10)*direction for c,direction in COMPONENTS.items()})
        ref=fit_reference(p); values=score(p,ref)
        self.assertAlmostEqual(values.mean(),100)
        self.assertAlmostEqual(values.std(),10)
        better=p.copy(); better['p_out_within_pa']+=1
        self.assertTrue((score(better,ref)>values).all())
        constant=p*0; self.assertTrue((score(constant,fit_reference(constant))==100).all())


if __name__=='__main__':
    unittest.main()
