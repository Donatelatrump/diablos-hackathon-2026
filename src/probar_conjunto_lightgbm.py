"""Efficient joint-event trial. Backend chosen for runtime before held-out results."""
import argparse
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import log_loss

import entrenar_stuff_plus_v9 as v9
from coherent_events import EVENTS,event_labels,fit_temperature,temperature_probabilities,joint_predictions,fit_event_values,expected_legacy_value
from probar_modelo_conjunto_ensamble import SOURCE,BASE,write,gain,coherence


def features(rows,columns,categories):
    x=v9.model_features(rows,columns)
    for name,levels in categories.items():
        x[name]=pd.Categorical(x[name].where(x[name].isin(levels)),categories=levels)
    return x


def run(folder,iterations):
    out=Path(folder);out.mkdir(parents=True,exist_ok=False)
    raw=v9.v5.prepare_raw(v9.read_rows(SOURCE,2026,True))
    parts=pd.read_parquet(BASE/'particiones.parquet',columns=['PitchUID','partition'])
    frame=v9.prepare_development(raw.merge(parts,on='PitchUID',validate='one_to_one'))
    frame['_event']=event_labels(frame)
    unknown=int(frame._event.isna().sum());frame=frame.loc[frame._event.notna()].reset_index(drop=True)
    frame['_event']=frame._event.astype(int)
    frame['_contact']=np.select([frame.ExitSpeed.lt(85),frame.ExitSpeed.ge(95)],[0,2],default=1)
    bundle=v9.load_bundle(BASE);columns=bundle[0]['tasks']['whiff']['features']
    protocol={'source_sha256':v9.v6.file_hash(SOURCE),'bundle_sha256':v9.v6.file_hash(BASE/'bundle.json'),
        'code_sha256':v9.v6.file_hash(__file__),'helper_sha256':v9.v6.file_hash('src/probar_modelo_conjunto_ensamble.py'),
        'event_code_sha256':v9.v6.file_hash('src/coherent_events.py'),'years':[2024,2025],'features':columns,
        'iterations':iterations,'backend':'lightgbm','version':lgb.__version__,
        'backend_reason':'Initial CatBoost multiclass fit stopped for runtime before any held-out candidate results. Architecture and family both differ from frozen control.',
        'scope':'Reused development data. No production changes; no 2026 selection.'}
    write(out/'protocolo.json',protocol)
    report={'heads':{},'excluded_unknown_events':unknown,'accepted':False}
    heads={}
    for name,label,kind in [('events','_event','multi'),('hr','home_run','binary'),('contact','_contact','multi'),('rv','run_value_proxy','regression')]:
        rows=frame
        if name!='events':rows=rows.loc[rows.PitchCall.eq('InPlay')]
        if name=='contact':rows=rows.loc[rows.ExitSpeed.notna()]
        tr,va,ca=[rows.loc[rows.partition.eq(p)].reset_index(drop=True) for p in ['fit','early_stop','calibration']]
        tx=v9.model_features(tr,columns)
        categories={c:sorted(tx[c].astype(str).unique()) for c in columns if c in v9.v5.CATEGORICAL or c=='stadium_id'}
        klass=lgb.LGBMRegressor if kind=='regression' else lgb.LGBMClassifier
        model=klass(objective={'multi':'multiclass','binary':'binary','regression':'regression'}[kind],
            n_estimators=iterations,learning_rate=.045,max_depth=6,num_leaves=31,min_child_samples=300,
            reg_lambda=20.,subsample=.8,subsample_freq=1,colsample_bytree=.85,
            random_state=v9.SEED,n_jobs=3,verbosity=-1)
        begin=time.monotonic()
        model.fit(features(tr,columns,categories),tr[label],
            eval_X=features(va,columns,categories),eval_y=va[label],
            eval_metric={'multi':'multi_logloss','binary':'binary_logloss','regression':'l2'}[kind],
            callbacks=[lgb.early_stopping(35,verbose=False)])
        cx=features(ca,columns,categories)
        if kind=='multi':
            processor={'temperature':fit_temperature(model.predict_proba(cx),ca[label])}
        else:
            prediction=model.predict(cx) if kind=='regression' else model.predict_proba(cx)[:,1]
            prior=float(tr[label].mean())
            procs=v9.fit_postprocessors(ca[label],prediction,np.full(len(ca),prior),kind=='binary')
            processor={'prior':prior,'postprocessor':procs.get('sigmoid',procs['shrink']) if kind=='binary' else procs['shrink']}
        heads[name]=(model,categories,processor)
        model.booster_.save_model(str(out/(name+'.txt')))
        report['heads'][name]={'n_fit':len(tr),'trees':model.best_iteration_,'seconds':round(time.monotonic()-begin,1),'categories':categories,**processor}
        write(out/'resultados.json',report)
        print({'head':name,'trees':model.best_iteration_,'seconds':report['heads'][name]['seconds']},flush=True)
    selection=frame.loc[frame.partition.isin(['tune','confirmation'])].reset_index(drop=True)
    outputs={}
    for name,(model,categories,processor) in heads.items():
        x=features(selection,columns,categories)
        if 'temperature' in processor:
            outputs[name]=temperature_probabilities(model.predict_proba(x),processor['temperature'])
        else:
            p=model.predict(x) if name=='rv' else model.predict_proba(x)[:,1]
            outputs[name]=v9.postprocess(p,np.full(len(x),processor['prior']),processor['postprocessor'])
    candidate=joint_predictions(outputs['events'],outputs['hr'],outputs['contact'])
    values=fit_event_values(frame.loc[frame.partition.eq('fit')]);write(out/'event_values.json',values)
    candidate['pred_environment_run_value']=expected_legacy_value(outputs['events'],selection,outputs['rv'],values)
    control=v9.predict_prepared(selection,*bundle)
    targets={'p_whiff':('is_whiff',None),'p_whiff_given_swing':('is_whiff','swing'),
        'p_ball_in_play':('is_ball_in_play',None),'p_called_strike':('is_called_strike',None),
        'p_home_run_per_pitch':('home_run',None),'p_weak_contact':('is_weak_contact','contact'),
        'p_hard_contact':('is_hard_contact','contact'),'pred_environment_run_value':('run_value_proxy',None)}
    report['comparisons']={}
    for col,(label,condition) in targets.items():
        mask=selection.partition.eq('confirmation') & selection[label].notna()
        if condition=='swing':mask &= selection.is_swing.eq(1)
        if condition=='contact':mask &= selection.PitchCall.eq('InPlay') & selection.ExitSpeed.notna()
        report['comparisons'][col]=gain(selection.loc[mask],selection.loc[mask,label],control.loc[mask,col],candidate.loc[mask,col],col!='pred_environment_run_value')
    check=selection.partition.eq('confirmation')
    report['n']=int(check.sum())
    report['coherence']={'control':coherence(control.loc[check]),'candidate':coherence(candidate.loc[check])}
    report['multiclass_logloss']=float(log_loss(selection.loc[check,'_event'],outputs['events'][check],labels=list(range(6))))
    fit=frame.loc[frame.partition.eq('fit')];priors=fit._event.value_counts(normalize=True).reindex(range(6),fill_value=0).to_numpy()
    count_table={}
    for (b,s),rows in fit.groupby(['Balls','Strikes']):
        counts=rows._event.value_counts().reindex(range(6),fill_value=0).to_numpy()
        count_table[f'{int(b)}-{int(s)}']=((counts+50*priors)/(len(rows)+50)).tolist()
    keys=selection.loc[check,'Balls'].astype(int).astype(str)+'-'+selection.loc[check,'Strikes'].astype(int).astype(str)
    report['count_baseline_multiclass_logloss']=float(log_loss(selection.loc[check,'_event'],np.asarray(keys.map(count_table).tolist()),labels=list(range(6))))
    report['screen_passed_all_heads']=all(x['passes'] for x in report['comparisons'].values())
    report['limitations']=['Family and architecture both change; not a pure architecture ablation.',
        'Called-strike and run-value frozen controls use 28 features; joint uses union of 37.',
        'Historical development data reused; no production promotion without more evidence.']
    write(out/'resultados.json',report)
    print({'comparisons':report['comparisons'],'coherence':report['coherence']},flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='joint_lgb_output_2026_10_28');p.add_argument('--iterations',type=int,default=400)
    a=p.parse_args();run(a.output,a.iterations)
