"""Auditoría adicional: arquitectura congelada, pitchers no vistos, temporada 2026.
No cambia el modelo desplegado. 2026 fue observado durante el desarrollo histórico.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, CatBoostRegressor
import entrenar_stuff_plus_v8 as v8
v5,v6,v7=v8.v5,v8.v6,v8.v7
OUT=Path("entrega_v8/validacion_pitchers")


def pitcher_roles(ids,seed=910):
    shuffled=np.random.default_rng(seed).permutation(sorted(set(ids)))
    n=len(shuffled)
    return {name:set(values) for name,values in {
        "fit":shuffled[:int(.6*n)],"stop":shuffled[int(.6*n):int(.7*n)],
        "cal":shuffled[int(.7*n):int(.8*n)],"test":shuffled[int(.8*n):]}.items()}


def cluster_interval(frame,y,p,baseline,seed=910):
    t=pd.DataFrame({"pitcher":frame.pitcher_anon_id.to_numpy(),"new":(np.asarray(y)-p)**2,
                    "old":(np.asarray(y)-baseline)**2})
    g=t.groupby("pitcher")[["new","old"]].sum().to_numpy()
    rng=np.random.default_rng(seed)
    gains=[]
    for _ in range(1000):
        x=g[rng.integers(0,len(g),len(g))].sum(axis=0)
        gains.append(1-x[0]/x[1])
    return {"gain":float(1-g[:,0].sum()/g[:,1].sum()),"low":float(np.quantile(gains,.025)),
            "high":float(np.quantile(gains,.975)),"n_pitchers":len(g)}


def main():
    if (OUT/"protocolo.json").exists(): raise FileExistsError("Auditoría ya iniciada")
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"modelos").mkdir(exist_ok=True)
    meta=json.loads(Path("stuff_plus_output_v8/bundle.json").read_text(encoding="utf-8"))
    raw=v5.prepare_raw(v5.read_parquet("stuff_model_df.parquet"))
    missing_pitcher_rows=int(raw.pitcher_anon_id.isna().sum())
    raw=raw.loc[raw.pitcher_anon_id.notna()].copy()
    roles=pitcher_roles(raw.pitcher_anon_id)
    protocol={"seed":910,"missing_pitcher_rows_excluded":missing_pitcher_rows,"roles":{k:sorted(v) for k,v in roles.items()},
              "source_sha256":v6.file_hash("stuff_model_df.parquet"),"script_sha256":v6.file_hash(__file__),
              "v8_bundle_sha256":v6.file_hash("stuff_plus_output_v8/bundle.json"),
              "training_max_year":2025,"test_year":2026,"benchmark_previously_seen":True,
              "architecture":"v8 frozen choices; models retrained without test pitchers", "calibration":"method frozen, parameters refitted on disjoint calibration pitchers"}
    v6.json_write(OUT/"protocolo.json",protocol)
    history=raw.loc[raw.year.le(2025)]
    fit_raw=history.loc[history.pitcher_anon_id.isin(roles["fit"])]
    fit=v6.enhance(v5.historical_features(fit_raw))
    empty={"fastballs":[],"usage":[]}
    parts={name:v6.enhance(v5.apply_profile(history.loc[history.pitcher_anon_id.isin(roles[name])],empty)).reset_index(drop=True)
           for name in ["stop","cal"]}
    test_raw=raw.loc[raw.year.eq(2026)&raw.pitcher_anon_id.isin(roles["test"])].reset_index(drop=True)
    test=v6.enhance(v5.apply_profile(test_raw,empty))
    assert not set(fit.pitcher_anon_id)&set(test.pitcher_anon_id)
    assert test.arsenal_history_available.eq(0).all()
    assert len(test)>1000
    for name,table in {"fit":fit,**parts,"test":test}.items():
        v5.write_parquet(table[v6.IDENTITY],OUT/f"{name}_ids.parquet")
    tasks=dict(v7.COMPONENTS)
    tasks.update({k:v5.TASKS[k] for k in ["xrunvalue","environment_run_value"]})
    outputs=test[v6.IDENTITY].copy()
    records=[]
    for task,base_spec in tasks.items():
        choice=meta["selection"].get(task,{"promoted":False})
        is_new=choice["promoted"]
        spec=v8.spec_for(task) if is_new else base_spec
        if task=="physical_control": spec=v5.TASKS["stuff_run_value"]
        if task not in v7.COMPONENTS: config=dict(iterations=250,depth=6,learning_rate=.06,l2_leaf_reg=8.,random_seed=42)
        else: config=v7.config_for(task,0)
        def train_model(train,valid,label):
            a,b=train.loc[v5.eligible(train,spec)],valid.loc[v5.eligible(valid,spec)]
            cls=CatBoostClassifier if spec[3]=="classification" else CatBoostRegressor
            m=cls(**config,loss_function="Logloss" if spec[3]=="classification" else "RMSE",thread_count=6,verbose=False,allow_writing_files=False)
            m.fit(v6.features(a,spec[1]),a[spec[0]],cat_features=[c for c in spec[1] if c in v5.CATEGORICAL],
                  eval_set=(v6.features(b,spec[1]),b[spec[0]]),early_stopping_rounds=30,use_best_model=True)
            m.save_model(str(OUT/"modelos"/f"{task}__{label}.cbm"))
            return m
        print(f"Pitcher holdout: {task}",flush=True)
        global_model=train_model(fit,parts["stop"],"global")
        cal_pred=v6.predict(global_model,spec,parts["cal"])
        pred=v6.predict(global_model,spec,test)
        if is_new and choice["candidate"].startswith("family_"):
            weight=float(choice["candidate"].split("|")[0].split("_")[1])
            for group in ["fast","breaking","offspeed"]:
                tr=fit.loc[v8.family(fit).eq(group)]
                va=parts["stop"].loc[v8.family(parts["stop"]).eq(group)]
                if v5.eligible(tr,spec).sum()<3000 or v5.eligible(va,spec).sum()<500: continue
                print(f"  familia {group}",flush=True)
                m=train_model(tr,va,group)
                for frame,p in [(parts["cal"],cal_pred),(test,pred)]:
                    mask=v8.family(frame).eq(group).to_numpy()
                    if mask.any(): p[mask]=(1-weight)*p[mask]+weight*v6.predict(m,spec,frame.loc[mask])
        calibration={"method":"identity"}
        if is_new and choice["candidate"].endswith("|sigmoid"):
            cm=v5.eligible(parts["cal"],spec).to_numpy()
            calibration=v7.fit_calibrators(parts["cal"].loc[cm,spec[0]],cal_pred[cm])["sigmoid"]
            pred=v7.apply_calibrator(pred,calibration)
        mask=v5.eligible(test,spec).to_numpy()
        y=test.loc[mask,spec[0]].to_numpy()
        train_y=fit.loc[v5.eligible(fit,spec),spec[0]]
        baseline=np.full(len(y),train_y.mean())
        count=v5.count_baseline(fit,test.loc[mask]) if spec[0]=="run_value_proxy" else None
        metric=v5.metrics(y,pred[mask],train_y,spec[3],count)
        record={"task":task,"n":int(mask.sum()),"metrics":metric,"vs_constant":cluster_interval(test.loc[mask],y,pred[mask],baseline),"calibrator":calibration}
        if count is not None: record["vs_count"]=cluster_interval(test.loc[mask],y,pred[mask],count)
        records.append(record)
        outputs[task]=pred
        v6.json_write(OUT/"metricas_parciales.json",records)
    v5.write_parquet(outputs,OUT/"predicciones.parquet")
    v6.json_write(OUT/"metricas.json",records)
    hashes={str(p.relative_to(OUT)):v6.file_hash(p) for p in OUT.rglob("*.cbm")}
    v6.json_write(OUT/"verificacion.json",{"pitchers_disjoint":all(not a&b for i,a in enumerate(roles.values()) for b in list(roles.values())[i+1:]),
                   "cold_start":True,"test_rows":len(test),"test_pitchers":test.pitcher_anon_id.nunique(),
                   "training_max_year":int(fit.year.max()),"model_hashes":hashes,"test_is_reused":True})
    print("Auditoría de pitchers terminada",flush=True)


if __name__=="__main__": main()
