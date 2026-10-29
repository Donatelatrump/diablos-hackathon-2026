"""Atribuciones SHAP del Stuff+ vigente en los tres casos; no son efectos causales."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor,Pool
import entrenar_stuff_plus_v8 as v8
OUT=Path('entrega_v8')


def main():
    cases=json.loads((OUT/'casos_scouting.json').read_text(encoding='utf-8'))
    base=Path('stuff_plus_output_v8/parent_v7/parent_v6/base_v5')
    meta=json.loads((base/'bundle.json').read_text(encoding='utf-8'))
    task=meta['tasks']['stuff_run_value'];ref=meta['reference']['stuff_plus']
    model=CatBoostRegressor().load_model(str(base/'modelos/stuff_run_value.cbm'))
    raw=v8.v6.read_seasons('stuff_model_df.parquet',2026)
    raw=raw.loc[raw.year.eq(2026)&raw.pitcher_anon_id.isin([c['pitcher'] for c in cases])].reset_index(drop=True)
    frame=v8.v5.apply_profile(raw,meta['profile'])
    x=v8.v5.features(frame,task['features'])
    pool=Pool(x,cat_features=[c for c in task['features'] if c in v8.v5.CATEGORICAL])
    shap=model.get_feature_importance(pool,type='ShapValues',thread_count=6)
    alpha=task['alpha']
    contribution=-10*alpha*shap[:,:-1]/ref['std']
    base_score=100+10*(-(alpha*shap[:,-1]+(1-alpha)*task['prior'])-ref['mean'])/ref['std']
    scores=v8.v5.read_parquet('stuff_plus_output_v8/scores_pitch_v8.parquet').set_index('PitchUID')
    np.testing.assert_allclose(base_score+contribution.sum(axis=1),scores.loc[raw.PitchUID,'stuff_plus'],atol=1e-7)
    rows=[]
    for c in cases:
        mask=raw.pitcher_anon_id.eq(c['pitcher']).to_numpy()
        for i,name in enumerate(task['features']):
            rows.append({'pitcher':c['pitcher'],'feature':name,'mean_stuff_points':float(contribution[mask,i].mean()),
                         'mean_absolute_points':float(np.abs(contribution[mask,i]).mean()),'n':int(mask.sum()),'base_stuff':float(base_score[mask].mean())})
    pd.DataFrame(rows).to_csv(OUT/'explicaciones_shap.csv',index=False)
    v8.v6.json_write(OUT/'verificacion_shap.json',{'reconstructs_exported_stuff':True,'rows':len(raw),'model_sha256':v8.v6.file_hash(base/'modelos/stuff_run_value.cbm'),'causal':False})
    print('SHAP reconstruye exactamente los scores de los casos')


if __name__=='__main__':main()
