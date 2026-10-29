"""Separate count-transition proxy experiment; never replaces the v9 target."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

import entrenar_stuff_plus_v9 as v9
from completar_targets_pa import reconstruct_pa
from entrenar_precision_contextual import read_development, BASE, SOURCE, write
from precision_features import fit_count_values, count_transition_target


def run(args):
    out=Path(args.output)
    out.mkdir(parents=True,exist_ok=False)
    raw=read_development()
    pa,coverage=reconstruct_pa(raw)
    values=fit_count_values(raw.loc[raw.partition.eq('fit')],pa)
    write(out/'count_values.json',values)
    write(out/'protocolo.json',{'source_sha256':v9.v6.file_hash(SOURCE),'years':[2024,2025],
        'target':'Change in smoothed expected terminal fixed run-value proxy by count; NOT RE24.',
        'coverage':coverage,'table_fitted_on':'fit complete PA only','iterations':args.iterations,
        'claim':'Different target from v9; RMSE cannot rank against legacy RV RMSE.',
        'code_sha256':v9.v6.file_hash(__file__)})
    frame=v9.prepare_development(raw)
    frame['count_transition_value']=count_transition_target(frame,values)
    valid_ids=set(pa.loc[pa.out_within_pa.notna(),'PitchUID'])
    frame=frame.loc[frame.PitchUID.isin(valid_ids) & frame.count_transition_value.notna()].reset_index(drop=True)
    fit,stop,cal,selection=[frame.loc[frame.partition.eq(role)].reset_index(drop=True)
                          for role in ['fit','early_stop','calibration','unused']]
    selection=frame.loc[frame.partition.isin(['tune','confirmation'])].reset_index(drop=True)
    # Fit the reference on the NEW target, never compare errors across targets.
    proxy_fit=fit.copy();proxy_fit['run_value_proxy']=proxy_fit.count_transition_value
    spec=('run_value_proxy',v9.LOCATION,None,'regression')
    baseline=v9.fit_baseline(proxy_fit,spec)
    model=CatBoostRegressor(iterations=args.iterations,depth=6,learning_rate=.045,l2_leaf_reg=20.,
        random_seed=v9.SEED,thread_count=3,loss_function='RMSE',allow_writing_files=False,verbose=False)
    model.fit(v9.model_features(fit,v9.LOCATION),fit.count_transition_value-v9.baseline_predict(fit,baseline),
        cat_features=[c for c in v9.LOCATION if c in v9.v5.CATEGORICAL],
        eval_set=(v9.model_features(stop,v9.LOCATION),stop.count_transition_value-v9.baseline_predict(stop,baseline)),
        early_stopping_rounds=35,use_best_model=True)
    predict=lambda data: model.predict(v9.model_features(data,v9.LOCATION))+v9.baseline_predict(data,baseline)
    pcal,psel=predict(cal),predict(selection)
    processors=v9.fit_postprocessors(cal.count_transition_value,pcal,v9.baseline_predict(cal,baseline),False)
    ref=v9.baseline_predict(selection,baseline)
    options={'baseline':ref,**{k:v9.postprocess(psel,ref,p) for k,p in processors.items()}}
    choice=v9.choose_candidate(selection.count_transition_value,options,selection.partition.eq('tune'),selection.year,
        selection.year.astype(str)+':'+selection.game_anon_id.astype(str),False)
    chosen=options[choice['selected']]
    check=selection.partition.eq('confirmation').to_numpy()
    report={'selection':choice,'n_comparison':int(check.sum()),'trees':model.tree_count_,
        'new_target_rmse':float(np.sqrt(np.mean((selection.loc[check,'count_transition_value']-chosen[check])**2))),
        'new_target_count_reference_rmse':float(np.sqrt(np.mean((selection.loc[check,'count_transition_value']-ref[check])**2))),
        'production_replaced':False,'status':'Experimental different target; requires temporal/grouped audits and real sporting validation.'}
    model.save_model(str(out/'count_transition.cbm'))
    write(out/'modelo.json',{'features':v9.LOCATION,'baseline':baseline,'model':'count_transition.cbm',
        'model_sha256':v9.v6.file_hash(out/'count_transition.cbm'),'postprocessor':processors.get(choice['selected'],{'method':'baseline'}),
        'history':v9.fit_profile(raw.loc[raw.partition.eq('fit')])})
    write(out/'resultados.json',report)
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--output',default='precision_count_output_2026_10_28')
    p.add_argument('--iterations',type=int,default=400)
    run(p.parse_args())
