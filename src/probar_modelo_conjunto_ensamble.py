"""Development-only trials of joint events and CatBoost/LightGBM blending.

No production promotion. Labels, histories, calibration and blend selection
remain inside the appropriate training/development partitions.
"""
import argparse
import json
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier,CatBoostRegressor
from sklearn.metrics import log_loss,roc_auc_score

import entrenar_stuff_plus_v9 as v9
from coherent_events import event_labels,EVENTS,fit_temperature,temperature_probabilities,joint_predictions,fit_event_values,expected_legacy_value

BASE=Path('stuff_plus_output_v9_estadios')
SOURCE=Path('stuff_model_df_con_estadios.parquet')


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def fit_cb(fit,stop,features,label,kind,iterations):
    cls=CatBoostRegressor if kind=='regression' else CatBoostClassifier
    model=cls(iterations=iterations,depth=6,learning_rate=.045,l2_leaf_reg=20.,random_seed=v9.SEED,
        thread_count=3,loss_function={'regression':'RMSE','binary':'Logloss','multi':'MultiClass'}[kind],
        allow_writing_files=False,verbose=False)
    model.fit(v9.model_features(fit,features),fit[label],
        cat_features=[c for c in features if c in v9.v5.CATEGORICAL or c=='stadium_id'],
        eval_set=(v9.model_features(stop,features),stop[label]),early_stopping_rounds=35,use_best_model=True)
    return model


def gain(rows,y,control,prediction,binary=True):
    y=np.asarray(y);control=np.asarray(control);prediction=np.asarray(prediction)
    g=rows.year.astype(str)+':'+rows.game_anon_id.astype(str)
    r=v9.grouped_gain(y,control,prediction,g,repetitions=1000)
    r.update(n=len(y),control_mse=float(np.mean((y-control)**2)),candidate_mse=float(np.mean((y-prediction)**2)))
    r['year_gains']={}
    for year in sorted(rows.year.unique()):
        mask=rows.year.eq(year).to_numpy();den=np.mean((y[mask]-control[mask])**2)
        r['year_gains'][str(year)]=float(1-np.mean((y[mask]-prediction[mask])**2)/den) if den>1e-15 else 0.
    if binary:
        r['control_logloss']=float(log_loss(y,np.clip(control,1e-6,1-1e-6),labels=[0,1]))
        r['candidate_logloss']=float(log_loss(y,np.clip(prediction,1e-6,1-1e-6),labels=[0,1]))
        r['control_auc']=float(roc_auc_score(y,control)) if len(np.unique(y))>1 else None
        r['candidate_auc']=float(roc_auc_score(y,prediction)) if len(np.unique(y))>1 else None
        def ece(p):
            b=np.minimum((p*10).astype(int),9)
            return float(sum((b==i).mean()*abs(p[b==i].mean()-y[b==i].mean()) for i in range(10) if (b==i).any()))
        r['control_ece']=ece(control)
        r['candidate_ece']=ece(prediction)
    r['passes']=bool(r['gain'] is not None and r['gain']>=.001 and r['ci_low'] is not None and r['ci_low']>0
        and all(x>=-.001 for x in r['year_gains'].values())
        and (not binary or r['candidate_logloss']<=r['control_logloss']*1.0015))
    return r


def coherence(p):
    return {name:int((values>1e-8).sum()) for name,values in {
        'whiff_gt_conditional':p.p_whiff-p.p_whiff_given_swing,
        'hr_gt_inplay':p.p_home_run_per_pitch-p.p_ball_in_play,
        'weak_hard_gt_one':p.p_weak_contact+p.p_hard_contact-1,
        'called_whiff_inplay_gt_one':p.p_called_strike+p.p_whiff+p.p_ball_in_play-1}.items()}


def categorical_frames(frames,columns):
    prepared=[v9.model_features(x,columns) for x in frames]
    for c in columns:
        if c in v9.v5.CATEGORICAL or c=='stadium_id':
            categories=sorted(prepared[0][c].dropna().astype(str).unique())
            for x in prepared:x[c]=pd.Categorical(x[c].where(x[c].isin(categories)),categories=categories)
    return prepared


def fit_lgb(fit,stop,features,iterations):
    train_x,stop_x=categorical_frames([fit,stop],features)
    model=lgb.LGBMClassifier(objective='binary',n_estimators=iterations,learning_rate=.045,max_depth=6,
        num_leaves=31,min_child_samples=300,reg_lambda=20.,subsample=.8,subsample_freq=1,
        colsample_bytree=.85,random_state=v9.SEED,n_jobs=3,verbosity=-1)
    model.fit(train_x,fit.is_whiff,eval_X=stop_x,eval_y=stop.is_whiff,eval_metric='binary_logloss',
        callbacks=[lgb.early_stopping(35,verbose=False)])
    return model


def prepare_history(raw,mask):
    return pd.concat([v9.apply_profile(raw.loc[raw.year.eq(y)],v9.fit_profile(raw.loc[mask & raw.year.lt(y)]))
                      for y in sorted(raw.year.unique())],ignore_index=True)


def run(args):
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    raw=v9.v5.prepare_raw(v9.read_rows(SOURCE,2026,True))
    parts=pd.read_parquet(BASE/'particiones.parquet',columns=['PitchUID','partition'])
    raw=raw.merge(parts,on='PitchUID',validate='one_to_one')
    bundle=v9.load_bundle(BASE)
    columns=bundle[0]['tasks']['whiff']['features']
    protocol={'source_sha256':v9.v6.file_hash(SOURCE),'bundle_sha256':v9.v6.file_hash(BASE/'bundle.json'),
        'code_sha256':v9.v6.file_hash(__file__),'event_code_sha256':v9.v6.file_hash('src/coherent_events.py'),
        'years':[2024,2025],'iterations':args.iterations,'features':columns,'events':EVENTS,
        'blend_lgb_weights':[.25,.5,.75,1.],'calibration':'Event/contact temperature; HR/LGB sigmoid when available; contact RV shrink.',
        'scope':'Reused development partitions; retrospective evidence only. No 2026 labels used for selection.',
        'activation':'No production changes; advancement requires separate robustness evidence.',
        'versions':{'lightgbm':lgb.__version__,'catboost':__import__('catboost').__version__}}
    write(out/'protocolo.json',protocol)
    frame=v9.prepare_development(raw)
    frame['_event']=event_labels(frame)
    excluded=int(frame._event.isna().sum());frame=frame.loc[frame._event.notna()].reset_index(drop=True)
    frame['_event']=frame._event.astype(int)
    frame['_contact']=np.select([frame.ExitSpeed.lt(85),frame.ExitSpeed.ge(95)],[0,2],default=1)
    masks={'hr':frame.PitchCall.eq('InPlay') & frame.home_run.notna(),
           'contact':frame.PitchCall.eq('InPlay') & frame.ExitSpeed.notna(),
           'rv':frame.PitchCall.eq('InPlay')}
    fits={}
    report={'excluded_unknown_events':excluded,'heads':{},'accepted':False}
    for name,label,kind in [('events','_event','multi'),('hr','home_run','binary'),('contact','_contact','multi'),('rv','run_value_proxy','regression')]:
        rows=frame if name=='events' else frame.loc[masks[name]]
        fit,stop,cal=[rows.loc[rows.partition.eq(role)].reset_index(drop=True) for role in ['fit','early_stop','calibration']]
        start=time.monotonic();model=fit_cb(fit,stop,columns,label,kind,args.iterations)
        if kind=='multi':
            temperature=fit_temperature(model.predict_proba(v9.model_features(cal,columns)),cal[label])
            processor={'temperature':temperature}
        else:
            p=model.predict_proba(v9.model_features(cal,columns))[:,1] if kind=='binary' else model.predict(v9.model_features(cal,columns))
            prior=float(fit[label].mean());baseline=np.full(len(cal),prior)
            processors=v9.fit_postprocessors(cal[label],p,baseline,kind=='binary')
            processor={'postprocessor':processors.get('sigmoid',processors['shrink']) if kind=='binary' else processors['shrink'],'prior':prior}
        model.save_model(str(out/(name+'.cbm')))
        fits[name]=(model,processor)
        report['heads'][name]={'n_fit':len(fit),'trees':model.tree_count_,'seconds':round(time.monotonic()-start,1),**processor}
        write(out/'resultados_conjunto.json',report)
        print(json.dumps({'head':name,**report['heads'][name]}),flush=True)
    selection=frame.loc[frame.partition.isin(['tune','confirmation'])].reset_index(drop=True)
    X=v9.model_features(selection,columns)
    event_p=temperature_probabilities(fits['events'][0].predict_proba(X),fits['events'][1]['temperature'])
    contact_p=temperature_probabilities(fits['contact'][0].predict_proba(X),fits['contact'][1]['temperature'])
    model,meta=fits['hr'];hr=v9.postprocess(model.predict_proba(X)[:,1],np.full(len(X),meta['prior']),meta['postprocessor'])
    candidate=joint_predictions(event_p,hr,contact_p)
    model,meta=fits['rv'];contact_rv=v9.postprocess(model.predict(X),np.full(len(X),meta['prior']),meta['postprocessor'])
    fit_rows=frame.loc[frame.partition.eq('fit')]
    event_values=fit_event_values(fit_rows)
    write(out/'event_values.json',event_values)
    candidate['pred_environment_run_value']=expected_legacy_value(event_p,selection,contact_rv,event_values)
    reference=v9.predict_prepared(selection,*bundle)
    targets={'p_whiff':('is_whiff',None),'p_whiff_given_swing':('is_whiff','swing'),
        'p_ball_in_play':('is_ball_in_play',None),'p_called_strike':('is_called_strike',None),
        'p_home_run_per_pitch':('home_run',None),'p_weak_contact':('is_weak_contact','contact'),
        'p_hard_contact':('is_hard_contact','contact'),'pred_environment_run_value':('run_value_proxy',None)}
    report['comparisons']={}
    for column,(label,condition) in targets.items():
        mask=selection.partition.eq('confirmation') & selection[label].notna()
        if condition=='swing':mask &= selection.is_swing.eq(1)
        if condition=='contact':mask &= selection.PitchCall.eq('InPlay') & selection.ExitSpeed.notna()
        report['comparisons'][column]=gain(selection.loc[mask],selection.loc[mask,label],reference.loc[mask,column],candidate.loc[mask,column],column!='pred_environment_run_value')
    check=selection.partition.eq('confirmation')
    report['coherence']={'control':coherence(reference.loc[check]),'candidate':coherence(candidate.loc[check])}
    report['multiclass_logloss']=float(log_loss(selection.loc[check,'_event'],event_p[check],labels=list(range(6))))
    # A distribution over events is not available from the independent binary control.
    priors=fit_rows._event.value_counts(normalize=True).reindex(range(6),fill_value=0).to_numpy()
    count_table={}
    for (b,s),rows in fit_rows.groupby(['Balls','Strikes']):
        counts=rows._event.value_counts().reindex(range(6),fill_value=0).to_numpy()
        count_table[f'{int(b)}-{int(s)}']=((counts+50*priors)/(len(rows)+50)).tolist()
    keys=selection.loc[check,'Balls'].astype(int).astype(str)+'-'+selection.loc[check,'Strikes'].astype(int).astype(str)
    count_p=np.asarray(keys.map(count_table).tolist())
    report['count_baseline_multiclass_logloss']=float(log_loss(selection.loc[check,'_event'],count_p,labels=list(range(6))))
    report['screen_passed_all_heads']=all(x['passes'] for x in report['comparisons'].values())
    report['limitations']=['Called-strike control uses 28 features; joint uses union of 37 already available features. This comparison is not a pure architecture ablation for that head.',
        'Run-value control inherits the selected location layer (28 features); joint expected value has 37 features. Same observed target, different representation.',
        'No joint-event probability from independent control; multinomial log loss compares against count frequencies, not that control.',
        'No new prospective validation or automatic promotion.']
    write(out/'resultados_conjunto.json',report)
    print(json.dumps({'joint_results':report['comparisons'],'coherence':report['coherence']}),flush=True)
    # Independent ensemble trial on the exact same conditional-whiff target and features.
    rows=frame.loc[frame.is_swing.eq(1) & frame.is_whiff.notna()].reset_index(drop=True)
    fit,stop,cal=[rows.loc[rows.partition.eq(role)].reset_index(drop=True) for role in ['fit','early_stop','calibration']]
    se=rows.loc[rows.partition.isin(['tune','confirmation'])].reset_index(drop=True)
    start=time.monotonic();model=fit_lgb(fit,stop,columns,args.iterations)
    train_x,cal_x,sel_x=categorical_frames([fit,cal,se],columns)
    pcal=model.predict_proba(cal_x)[:,1]
    prior=float(fit.is_whiff.mean())
    processors=v9.fit_postprocessors(cal.is_whiff,pcal,np.full(len(cal),prior),True)
    post=processors.get('sigmoid',processors['raw'])
    plgb=v9.postprocess(model.predict_proba(sel_x)[:,1],np.full(len(se),prior),post)
    pcb=v9.predict_prepared(se,*bundle).p_whiff_given_swing.to_numpy()
    options={'baseline':pcb,**{f'lgb_weight_{w}':(1-w)*pcb+w*plgb for w in protocol['blend_lgb_weights']}}
    choice=v9.choose_candidate(se.is_whiff,options,se.partition.eq('tune'),se.year,se.year.astype(str)+':'+se.game_anon_id.astype(str),True)
    check=se.partition.eq('confirmation').to_numpy()
    winner=choice['candidate']
    metrics=gain(se.loc[check],se.loc[check,'is_whiff'],pcb[check],options[winner][check])
    result={'selection':choice,'comparison':metrics,'n_fit':len(fit),'trees':model.best_iteration_,
        'seconds':round(time.monotonic()-start,1),'postprocessor':post,'accepted':False,
        'scope':'Conditional-whiff blend selection; no automatic promotion from development alone.'}
    model.booster_.save_model(str(out/'conditional_lgb.txt'))
    write(out/'resultados_ensamble.json',result)
    print(json.dumps({'ensemble':result}),flush=True)
    # Freeze the winner before re-fitting the pair under distinct exclusions.
    if choice['promoted']:
        weight=float(winner.removeprefix('lgb_weight_'))
        result['audits']={}
        for mode in ['temporal','pitcher','park']:
            if mode=='temporal':keep=raw.year.eq(2024);evmask=raw.year.eq(2025)
            elif mode=='pitcher':
                held=raw.pitcher_anon_id.map(v9.held_pitcher);keep=~held;evmask=held & raw.partition.eq('confirmation')
            else:
                held=raw.stadium_id.eq('mexico_ahh');keep=~held;evmask=held & raw.partition.eq('confirmation')
            local=prepare_history(raw,keep & raw.partition.eq('fit')).set_index('PitchUID').loc[raw.PitchUID].reset_index()
            eligible=local.is_swing.eq(1) & local.is_whiff.notna()
            tr,va,ca=[local.loc[keep.to_numpy() & local.partition.eq(role) & eligible].reset_index(drop=True)
                      for role in ['fit','early_stop','calibration']]
            ev=local.loc[evmask.to_numpy() & eligible].reset_index(drop=True)
            base=fit_cb(tr,va,columns,'is_whiff','binary',args.iterations)
            lgbmodel=fit_lgb(tr,va,columns,args.iterations)
            outputs=[]
            train_x,cal_x,ev_x=categorical_frames([tr,ca,ev],columns)
            for pc,pe in [(base.predict_proba(v9.model_features(ca,columns))[:,1],base.predict_proba(v9.model_features(ev,columns))[:,1]),
                          (lgbmodel.predict_proba(cal_x)[:,1],lgbmodel.predict_proba(ev_x)[:,1])]:
                procs=v9.fit_postprocessors(ca.is_whiff,pc,np.full(len(ca),tr.is_whiff.mean()),True)
                outputs.append(v9.postprocess(pe,np.full(len(ev),tr.is_whiff.mean()),procs.get('sigmoid',procs['raw'])))
            blended=(1-weight)*outputs[0]+weight*outputs[1]
            result['audits'][mode]=gain(ev,ev.is_whiff,outputs[0],blended)
            write(out/'resultados_ensamble.json',result)
            print(json.dumps({'ensemble_audit':mode,**result['audits'][mode]}),flush=True)
        result['eligible_for_review']=all(x['passes'] for x in result['audits'].values())
        write(out/'resultados_ensamble.json',result)
    print('Finished. Production artifacts unchanged.',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='joint_ensemble_output_2026_10_28');p.add_argument('--iterations',type=int,default=400)
    run(p.parse_args())
