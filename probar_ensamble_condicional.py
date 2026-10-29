"""Independent screening of the blend while the joint event trial runs."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import entrenar_stuff_plus_v9 as v9
from probar_modelo_conjunto_ensamble import BASE,SOURCE,write,categorical_frames,fit_lgb,gain


def run(folder):
    out=Path(folder);out.mkdir(parents=True,exist_ok=False)
    raw=v9.v5.prepare_raw(v9.read_rows(SOURCE,2026,True))
    parts=pd.read_parquet(BASE/'particiones.parquet',columns=['PitchUID','partition'])
    frame=v9.prepare_development(raw.merge(parts,on='PitchUID',validate='one_to_one'))
    rows=frame.loc[frame.is_swing.eq(1) & frame.is_whiff.notna()].reset_index(drop=True)
    fit,stop,cal=[rows.loc[rows.partition.eq(p)].reset_index(drop=True) for p in ['fit','early_stop','calibration']]
    selection=rows.loc[rows.partition.isin(['tune','confirmation'])].reset_index(drop=True)
    bundle=v9.load_bundle(BASE);columns=bundle[0]['tasks']['whiff_given_swing']['features']
    write(out/'protocolo.json',{'source_sha256':v9.v6.file_hash(SOURCE),'bundle_sha256':v9.v6.file_hash(BASE/'bundle.json'),
        'code_sha256':v9.v6.file_hash(__file__),'helper_sha256':v9.v6.file_hash('probar_modelo_conjunto_ensamble.py'),
        'features':columns,'iterations':400,'years':[2024,2025],'weights':[.25,.5,.75,1.],
        'scope':'Same fixed blend configuration as the full joint/ensemble run; independent execution, not a fresh data validation.'})
    model=fit_lgb(fit,stop,columns,400)
    _,cx,sx=categorical_frames([fit,cal,selection],columns)
    prior=float(fit.is_whiff.mean())
    processors=v9.fit_postprocessors(cal.is_whiff,model.predict_proba(cx)[:,1],np.full(len(cal),prior),True)
    post=processors.get('sigmoid',processors['raw'])
    plgb=v9.postprocess(model.predict_proba(sx)[:,1],np.full(len(selection),prior),post)
    pcb=v9.predict_prepared(selection,*bundle).p_whiff_given_swing.to_numpy()
    options={'baseline':pcb,**{f'lgb_weight_{w}':(1-w)*pcb+w*plgb for w in [.25,.5,.75,1.]}}
    choice=v9.choose_candidate(selection.is_whiff,options,selection.partition.eq('tune'),selection.year,
        selection.year.astype(str)+':'+selection.game_anon_id.astype(str),True)
    check=selection.partition.eq('confirmation').to_numpy()
    report={'selection':choice,'comparison':gain(selection.loc[check],selection.loc[check,'is_whiff'],pcb[check],options[choice['candidate']][check]),
        'trees':model.best_iteration_,'accepted':False,'scope':'Screen only; the full run performs robustness audits if selected.'}
    model.booster_.save_model(str(out/'lightgbm.txt'))
    write(out/'resultado.json',report)
    print(report,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='ensemble_screen_output_2026_10_28')
    run(p.parse_args().output)
