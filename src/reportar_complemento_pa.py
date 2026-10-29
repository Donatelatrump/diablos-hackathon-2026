"""Per-park PA calibration from frozen predictions; never refits on benchmark."""
import json
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score
from completar_targets_pa import ROOT, OUT, reconstruct_pa


def main():
    raw=pd.read_parquet(ROOT/'stuff_model_df_con_estadios.parquet')
    labels,_=reconstruct_pa(raw)
    for mode in ['season','pitcher','park']:
        folder=OUT/mode
        p=pd.read_parquet(folder/'predicciones_pa.parquet').merge(
            labels[['PitchUID','out_within_pa']],on='PitchUID',validate='one_to_one')
        assert p.out_within_pa.notna().all()
        metrics=[]; calibration=[]
        for stadium,rows in p.groupby('stadium_id',dropna=False):
            y=rows.out_within_pa; prob=rows.p_out_within_pa
            metrics.append(dict(stadium_id=stadium,n=len(rows),games=rows.game_anon_id.nunique(),
                observed=y.mean(),predicted=prob.mean(),brier=brier_score_loss(y,prob),
                auc=roc_auc_score(y,prob) if y.nunique()==2 else np.nan))
            bins=np.minimum((prob*10).astype(int),9)
            for number,group in rows.groupby(bins):
                calibration.append(dict(stadium_id=stadium,bin=int(number),n=len(group),
                    predicted=group.p_out_within_pa.mean(),observed=group.out_within_pa.mean(),
                    sufficient_for_display=len(group)>=30))
        pd.DataFrame(metrics).to_csv(folder/'metricas_pa_por_estadio.csv',index=False)
        pd.DataFrame(calibration).to_csv(folder/'calibracion_pa_por_estadio.csv',index=False)
        print(mode+': calibracion por estadio registrada',flush=True)


if __name__=='__main__':
    main()
