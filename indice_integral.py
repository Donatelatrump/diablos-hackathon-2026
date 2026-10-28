"""Explicit multi-objective index. Unitless utility, NOT an event probability."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import entrenar_stuff_plus_v9 as v9
from completar_targets_pa import OUT, ROOT, predict_pa, normalized_by_cohort

# Equal weights declared a priori, never optimized on 2026 outcomes.
# Conditional targets retain their denominators: standardized utilities may be
# combined, unlike probabilities of overlapping / incompatible events.
COMPONENTS = {'p_whiff':1, 'p_chase':1, 'p_called_strike':1, 'p_weak_contact':1,
              'p_groundball_given_in_play':1, 'p_hard_contact':-1,
              'pred_environment_run_value':-1, 'p_out_within_pa':1}


def utility(predictions, reference):
    result=np.zeros(len(predictions))
    for col, direction in COMPONENTS.items():
        ref=reference['components'][col]
        if ref['std']>1e-8:
            result += direction*(predictions[col].to_numpy()-ref['mean'])/ref['std']/len(COMPONENTS)
    return result


def fit_reference(predictions):
    ref={'components':{c:{'mean':float(predictions[c].mean()),'std':float(predictions[c].std(ddof=0)),
                          'direction':s,'weight':1/len(COMPONENTS)} for c,s in COMPONENTS.items()}}
    values=utility(predictions,ref)
    ref.update(mean=float(values.mean()), std=float(values.std()),
               interpretation='Standardized equal-weight utility, not probability or causal effect',
               selection='Weights fixed without benchmark labels; correlated targets may double-count signals')
    return ref


def score(predictions, reference):
    values=utility(predictions,reference)
    return 100+10*(values-reference['mean'])/reference['std'] if reference['std']>1e-8 else np.full(len(values),100.)


def enrich_scenarios(raw, predictions, bundle, folder=OUT/'season'):
    result=predictions.copy()
    result['p_out_within_pa']=predict_pa(raw,bundle,folder)
    ref=json.loads((folder/'indice_integral.json').read_text())
    result['indice_integral']=score(result,ref)
    return result


def main():
    source=ROOT/'stuff_model_df_con_estadios.parquet'
    for mode,suffix in [('season',''),('pitcher','_pitcher'),('park','_park')]:
        base=ROOT/('stuff_plus_output_v9_estadios'+suffix)
        folder=OUT/mode
        bundle=v9.load_bundle(base)
        parts=pd.read_parquet(base/'particiones.parquet')
        raw=v9.read_rows(source,2026,True)
        cal=raw.loc[raw.PitchUID.isin(parts.loc[parts.partition.eq('calibration'),'PitchUID'])].reset_index(drop=True)
        preds=v9.infer(cal,bundle)
        preds['p_out_within_pa']=predict_pa(cal,bundle,folder)
        ref=fit_reference(preds)
        ref.update(n_calibration=len(cal), years=sorted(cal.year.unique().tolist()),
                   base_bundle_sha256=v9.v6.file_hash(base/'bundle.json'),
                   pa_metadata_sha256=v9.v6.file_hash(folder/'out_pa.json'))
        (folder/'indice_integral.json').write_text(json.dumps(ref,indent=2))
        # Reuse frozen benchmark forecasts, adding PA forecasts for every pitch.
        test=v9.read_rows(source,2026,False)
        predictions=pd.read_parquet(base/'scores_pitch_v9.parquet')
        test=test.set_index('PitchUID').loc[predictions.PitchUID].reset_index()
        predictions=enrich_scenarios(test,predictions,bundle,folder)
        normalized, refs=normalized_by_cohort(predictions,['stuff_plus','location_plus','pitching_plus','indice_integral'])
        columns=['PitchUID','year','game_anon_id','pitcher_anon_id','AutoPitchType','stadium_id',
                 'p_out_within_pa','indice_integral']+[c for c in normalized if c.endswith('_temporada_estadio')]
        normalized[columns].to_parquet(folder/'scores_integrales.parquet',index=False)
        (folder/'referencias_temporada_estadio.json').write_text(json.dumps(refs,indent=2))
        for groups,name in [(['year','pitcher_anon_id'],'pitchers_integrales.csv'),
                            (['year','pitcher_anon_id','AutoPitchType','stadium_id'],'arsenales_integrales.csv')]:
            normalized.groupby(groups,dropna=False).agg(n_pitches=('PitchUID','size'),n_games=('game_anon_id','nunique'),
                p_out_within_pa=('p_out_within_pa','mean'),indice_integral=('indice_integral','mean'),
                indice_integral_temporada_estadio=('indice_integral_temporada_estadio','mean')).reset_index().to_csv(folder/name,index=False)
        print(mode+': indice integral y referencias exportados',flush=True)


if __name__=='__main__':
    main()
