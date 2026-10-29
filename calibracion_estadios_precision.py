"""Regularized stadium calibration, fitted on calibration labels only."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import entrenar_stuff_plus_v9 as v9
from entrenar_precision_contextual import read_development, BASE, SOURCE, write


def sigmoid(value):
    return 1/(1+np.exp(-np.clip(value,-35,35)))


def solve_offset(probability, target, penalty):
    logit=np.log(np.clip(probability,1e-6,1-1e-6)/np.clip(1-probability,1e-6,1-1e-6))
    offset=0.
    for _ in range(40):
        p=sigmoid(logit+offset)
        step=(np.sum(p-target)+penalty*offset)/(np.sum(p*(1-p))+penalty)
        offset=float(np.clip(offset-step,-3,3))
        if abs(step)<1e-8:
            break
    return offset


def fit_offsets(probability,target,stadiums,penalty=50.):
    p,y=np.asarray(probability,dtype=float),np.asarray(target,dtype=float)
    groups=pd.Series(stadiums).reset_index(drop=True)
    global_offset=solve_offset(p,y,penalty)
    adjusted=sigmoid(np.log(np.clip(p,1e-6,1-1e-6)/np.clip(1-p,1e-6,1-1e-6))+global_offset)
    offsets={}
    for stadium in groups.dropna().unique():
        mask=groups.eq(stadium).to_numpy()
        offsets[str(stadium)]=solve_offset(adjusted[mask],y[mask],penalty)
    return {'global':global_offset,'stadiums':offsets,'penalty':penalty}


def apply_offsets(probability,stadiums,metadata):
    p=np.clip(np.asarray(probability,dtype=float),1e-6,1-1e-6)
    offsets=pd.Series(stadiums).map(metadata['stadiums']).fillna(0.).to_numpy()
    return sigmoid(np.log(p/(1-p))+metadata['global']+offsets)


def run(args):
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    raw=read_development()
    frame=v9.prepare_development(raw)
    bundle=v9.load_bundle(BASE)
    cal=frame.loc[frame.partition.eq('calibration')].reset_index(drop=True)
    selection=frame.loc[frame.partition.isin(['tune','confirmation'])].reset_index(drop=True)
    pc=v9.predict_prepared(cal,*bundle).p_home_run_per_pitch.to_numpy()
    ps=v9.predict_prepared(selection,*bundle).p_home_run_per_pitch.to_numpy()
    options={'baseline':ps};calibrators={}
    for penalty in [20.,100.]:
        key=f'shrink_{int(penalty)}'
        calibrators[key]=fit_offsets(pc,cal.home_run,cal.stadium_id,penalty)
        options[key]=apply_offsets(ps,selection.stadium_id,calibrators[key])
    choice=v9.choose_candidate(selection.home_run,options,selection.partition.eq('tune'),selection.year,
        selection.year.astype(str)+':'+selection.game_anon_id.astype(str),True)
    write(out/'resultado.json',{'selection':choice,'source_sha256':v9.v6.file_hash(SOURCE),
        'base_bundle_sha256':v9.v6.file_hash(BASE/'bundle.json'),'calibrators':calibrators,
        'n_calibration':len(cal),'n_selection':len(selection),'years':[2024,2025],
        'active':False,'scope':'Calibrator-only development screening; not a new temporal/pitcher/park audit of the complete model. Not activated without those audits.',
        'code_sha256':v9.v6.file_hash(__file__)})
    print(choice,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='precision_calibration_output_2026_10_28')
    run(p.parse_args())
