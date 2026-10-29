"""Audit the already frozen independent blend, without selecting another weight."""
import json
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import entrenar_stuff_plus_v9 as v9
from probar_modelo_conjunto_ensamble import BASE,SOURCE,write,prepare_history,fit_cb,fit_lgb,categorical_frames,gain


def run(folder='ensemble_screen_output_2026_10_28'):
    out=Path(folder)
    report=json.loads((out/'resultado.json').read_text())
    if not report['selection']['promoted']:
        print('No promoted blend to audit.',flush=True);return
    if report.get('audits'):
        raise FileExistsError('Audit already started; preserve it rather than rerun selection.')
    weight=float(report['selection']['candidate'].removeprefix('lgb_weight_'))
    raw=v9.v5.prepare_raw(v9.read_rows(SOURCE,2026,True))
    parts=pd.read_parquet(BASE/'particiones.parquet',columns=['PitchUID','partition'])
    raw=raw.merge(parts,on='PitchUID',validate='one_to_one')
    bundle=v9.load_bundle(BASE);columns=bundle[0]['tasks']['whiff_given_swing']['features']
    report['audits']={}
    report['audit_code_sha256']=v9.v6.file_hash(__file__)
    write(out/'resultado.json',report)
    for mode in ['temporal','pitcher','park']:
        if mode=='temporal':keep=raw.year.eq(2024);test=raw.year.eq(2025)
        elif mode=='pitcher':
            held=raw.pitcher_anon_id.map(v9.held_pitcher);keep=~held;test=held & raw.partition.eq('confirmation')
        else:
            held=raw.stadium_id.eq('mexico_ahh');keep=~held;test=held & raw.partition.eq('confirmation')
        local=prepare_history(raw,keep & raw.partition.eq('fit')).set_index('PitchUID').loc[raw.PitchUID].reset_index()
        valid=local.is_swing.eq(1) & local.is_whiff.notna()
        tr,va,ca=[local.loc[keep.to_numpy() & local.partition.eq(role) & valid].reset_index(drop=True)
            for role in ['fit','early_stop','calibration']]
        ev=local.loc[test.to_numpy() & valid].reset_index(drop=True)
        cb=fit_cb(tr,va,columns,'is_whiff','binary',400)
        lgb=fit_lgb(tr,va,columns,400)
        _,cx,ex=categorical_frames([tr,ca,ev],columns)
        pairs=[(cb.predict_proba(v9.model_features(ca,columns))[:,1],cb.predict_proba(v9.model_features(ev,columns))[:,1]),
            (lgb.predict_proba(cx)[:,1],lgb.predict_proba(ex)[:,1])]
        predictions=[]
        for pcal,ptest in pairs:
            prior=float(tr.is_whiff.mean())
            procs=v9.fit_postprocessors(ca.is_whiff,pcal,np.full(len(ca),prior),True)
            predictions.append(v9.postprocess(ptest,np.full(len(ev),prior),procs.get('sigmoid',procs['raw'])))
        blended=(1-weight)*predictions[0]+weight*predictions[1]
        report['audits'][mode]=gain(ev,ev.is_whiff,predictions[0],blended)
        write(out/'resultado.json',report)
        print(json.dumps({'audit':mode,**report['audits'][mode]}),flush=True)
    report['eligible_for_review']=all(x['passes'] for x in report['audits'].values())
    report['accepted']=False
    report['scope']='Fixed-weight retrospective audits completed. No production promotion.'
    write(out/'resultado.json',report)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='ensemble_screen_output_2026_10_28')
    run(parser.parse_args().output)
