"""Audited PA target and season/park score references, without modifying frozen v9."""
from pathlib import Path
import json
import uuid
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score, log_loss
import entrenar_stuff_plus_v9 as v9

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/v9_estadios/complemento'
TERMINAL = {'Out', 'Strikeout', 'Sacrifice', 'FieldersChoice', 'Single', 'Double',
            'Triple', 'HomeRun', 'Walk', 'HitByPitch', 'Error'}


def reconstruct_pa(raw):
    """Require complete 0-0 to terminal, consistent counts, batter and half inning.

    Target: at least one recorded out on the terminal PA event (includes FC/DP).
    Incomplete/censored sequences and nonterminal baserunning outs are excluded.
    UUID times order rows; they and all outcome fields never become features.
    """
    d = raw.copy()
    def timestamp(value):
        try:
            u = uuid.UUID(str(value))
            return u.time if u.version == 1 else -1
        except (ValueError, AttributeError):
            return -1
    d['_time'] = d.PitchUID.map(timestamp)
    d = d.sort_values(['year', 'game_anon_id', '_time', 'PitchUID']).reset_index(drop=True)
    same_half = (d[['year', 'game_anon_id', 'Inning', 'Top/Bottom']]
                 .eq(d[['year', 'game_anon_id', 'Inning', 'Top/Bottom']].shift()).all(axis=1))
    terminal = d.play_result.isin(TERMINAL)
    boundary = ~same_half | d.batter_anon_id.ne(d.batter_anon_id.shift()) | terminal.shift(fill_value=True)
    d['pa_id'] = boundary.cumsum().astype(str)
    ball = d.PitchCall.isin(['BallCalled', 'BallinDirt'])
    strike = d.PitchCall.isin(['StrikeCalled', 'StrikeSwinging'])
    foul = d.PitchCall.astype(str).str.startswith('Foul')
    expected_b = d.Balls + ball.astype(int)
    expected_s = d.Strikes + strike.astype(int) + (foul & d.Strikes.lt(2)).astype(int)
    transition_ok = boundary | (d.Balls.eq(expected_b.shift()) & d.Strikes.eq(expected_s.shift()))
    bad = (~transition_ok | d._time.lt(0) | d.batter_anon_id.isna()
           | d[['Inning', 'Top/Bottom', 'Balls', 'Strikes']].isna().any(axis=1)
           | (d.OutsOnPlay.gt(0) & ~terminal)
           | d.duplicated(['year', 'game_anon_id', '_time'], keep=False))
    grouped = d.groupby('pa_id', sort=False)
    first, last = grouped.head(1).set_index('pa_id'), grouped.tail(1).set_index('pa_id')
    valid = (first.Balls.eq(0) & first.Strikes.eq(0) & last.play_result.isin(TERMINAL)
             & last.OutsOnPlay.isin([0, 1, 2, 3]) & ~bad.groupby(d.pa_id).any())
    # A strikeout not accompanied by a recorded out may be a dropped third strike;
    # do not infer an out from its name alone.
    labels = last.OutsOnPlay.gt(0).astype(float).where(valid)
    d['out_within_pa'] = d.pa_id.map(labels)
    counts = {'pitches': len(d), 'candidate_pa': len(valid), 'valid_pa': int(valid.sum()),
              'labeled_pitches': int(d.out_within_pa.notna().sum()),
              'excluded_pa': int((~valid).sum()), 'definition': 'At least one out on terminal PA event; FC and double plays included; not necessarily batter retired'}
    return d[['PitchUID', 'pa_id', 'out_within_pa']], counts


def predict_pa(raw, bundle, folder):
    meta = json.loads((folder / 'out_pa.json').read_text())
    model = CatBoostClassifier().load_model(str(folder / 'out_pa.cbm'))
    if v9.v6.file_hash(folder / 'out_pa.cbm') != meta['model_sha256']:
        raise ValueError('Modelo PA modificado')
    frame = v9.apply_profile(raw, bundle[0]['profile'])
    p = model.predict_proba(v9.model_features(frame, meta['features']))[:, 1]
    return v9.postprocess(p, v9.baseline_predict(frame, meta['baseline']), meta['postprocessor'])


def normalized_by_cohort(frame, columns, minimum=300):
    """Descriptive normalization of predictions ONLY. Never uses held-out labels.

    Frozen after cohort close; not used to claim predictive improvement.
    Unknown/small parks fall back to the season reference explicitly.
    """
    result = frame.copy()
    refs = []
    for year, season in frame.groupby('year'):
        for park, rows in season.groupby('stadium_id', dropna=False):
            supported = pd.notna(park) and len(rows) >= minimum
            reference = rows if supported else season
            for col in columns:
                mean, std = float(reference[col].mean()), float(reference[col].std(ddof=0))
                result.loc[rows.index, col + '_temporada_estadio'] = (
                    100 + 10 * (rows[col] - mean) / std if std > 1e-8 else 100.)
                refs.append(dict(year=int(year), stadium_id=None if pd.isna(park) else park,
                                 score=col, mean=mean, std=std, n=len(rows),
                                 reference='season_park' if supported else 'season_fallback'))
    return result, refs


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'stuff_model_df_con_estadios.parquet'
    raw = pd.read_parquet(source)
    labels, audit = reconstruct_pa(raw)
    (OUT / 'auditoria_pa.json').write_text(json.dumps(audit, indent=2))
    print(json.dumps(audit), flush=True)
    for mode, suffix in [('season', ''), ('pitcher', '_pitcher'), ('park', '_park')]:
        folder = OUT / mode
        folder.mkdir(exist_ok=True)
        if (folder / 'metricas.json').exists():
            print('Conservando evaluacion completa: ' + mode, flush=True)
            continue
        base = ROOT / ('stuff_plus_output_v9_estadios' + suffix)
        bundle = v9.load_bundle(base)
        parts = pd.read_parquet(base / 'particiones.parquet')[['PitchUID', 'partition']]
        development = v9.read_rows(source, 2026, True).merge(parts, on='PitchUID', validate='one_to_one')
        development = v9.v5.prepare_raw(development).merge(labels, on='PitchUID', validate='one_to_one')
        frame = v9.prepare_development(development)
        frame = frame.loc[frame.out_within_pa.notna()].reset_index(drop=True)
        fit, stop, cal = [frame.loc[frame.partition.eq(p)] for p in v9.ROLES[:3]]
        selection = frame.loc[frame.partition.isin(v9.ROLES[3:])]
        features = v9.ENVIRONMENT + ['stadium_id']
        # A count baseline is more demanding than the unconditional PA prior.
        prior = float(fit.out_within_pa.mean())
        counts = fit.groupby(['Balls', 'Strikes']).out_within_pa.agg(['sum', 'count'])
        baseline = dict(prior=prior, counts={f'{int(b)}-{int(s)}':float((r['sum']+50*prior)/(r['count']+50)) for (b,s),r in counts.iterrows()})
        model = CatBoostClassifier(iterations=400, depth=6, learning_rate=.045, l2_leaf_reg=20,
                                   random_seed=v9.SEED, thread_count=6, verbose=False, allow_writing_files=False)
        model.fit(v9.model_features(fit, features), fit.out_within_pa,
                  cat_features=[c for c in features if c in v9.v5.CATEGORICAL or c=='stadium_id'],
                  eval_set=(v9.model_features(stop, features), stop.out_within_pa), early_stopping_rounds=35)
        pcal = model.predict_proba(v9.model_features(cal, features))[:,1]
        psel = model.predict_proba(v9.model_features(selection, features))[:,1]
        processors = v9.fit_postprocessors(cal.out_within_pa, pcal, v9.baseline_predict(cal, baseline), True)
        control = v9.baseline_predict(selection, baseline)
        options = {'baseline': control, **{k:v9.postprocess(psel,control,p) for k,p in processors.items()}}
        chosen = v9.choose_candidate(selection.out_within_pa, options, selection.partition.eq('tune'),
                                    selection.year, selection.game_anon_id, True)
        post = processors[chosen['selected']] if chosen['promoted'] else {'method':'baseline'}
        model.save_model(str(folder/'out_pa.cbm'))
        meta = dict(features=features, baseline=baseline, postprocessor=post, selection=chosen,
                    source_sha256=v9.v6.file_hash(source), model_sha256=v9.v6.file_hash(folder/'out_pa.cbm'),
                    code_sha256=v9.v6.file_hash(__file__), base_bundle_sha256=v9.v6.file_hash(base/'bundle.json'),
                    n_fit=len(fit), n_calibration=len(cal), trees=model.tree_count_, benchmark_reused=True)
        (folder/'out_pa.json').write_text(json.dumps(meta,indent=2))
        print(mode+' modelo y calibracion congelados', flush=True)
        scores = pd.read_parquet(base/'scores_pitch_v9.parquet')
        test = v9.read_rows(source,2026,False)
        test = test.loc[test.PitchUID.isin(scores.PitchUID)].merge(labels,on='PitchUID',validate='one_to_one')
        test = test.loc[test.out_within_pa.notna()].reset_index(drop=True)
        assert set(development.PitchUID).isdisjoint(test.PitchUID)
        assert not set(development.pa_id).intersection(test.pa_id)
        if mode=='pitcher':
            assert set(development.pitcher_anon_id).isdisjoint(test.pitcher_anon_id)
        if mode=='park':
            assert not development.stadium_id.eq('mexico_ahh').any()
            assert test.stadium_id.eq('mexico_ahh').all()
        probability = predict_pa(test,bundle,folder)
        control = v9.baseline_predict(test,baseline)
        metric = dict(pitches=len(test), pa=int(test.pa_id.nunique()), games=int(test.game_anon_id.nunique()),
                      brier=float(brier_score_loss(test.out_within_pa,probability)),
                      baseline_brier=float(brier_score_loss(test.out_within_pa,control)),
                      auc=float(roc_auc_score(test.out_within_pa,probability)),
                      logloss=float(log_loss(test.out_within_pa,probability)),
                      observed=float(test.out_within_pa.mean()), predicted=float(probability.mean()),
                      gain=v9.grouped_gain(test.out_within_pa,control,probability,test.game_anon_id))
        predictions=test[['PitchUID','pa_id','year','game_anon_id','stadium_id']].copy()
        predictions['p_out_within_pa']=probability
        predictions.to_parquet(folder/'predicciones_pa.parquet',index=False)
        (folder/'metricas.json').write_text(json.dumps(metric,indent=2))
        print(mode+' '+json.dumps(metric),flush=True)
    # Park-season normalization remains separate from prospective frozen scores.
    scores=pd.read_parquet(ROOT/'stuff_plus_output_v9_estadios/scores_pitch_v9.parquet')
    normalized, refs=normalized_by_cohort(scores,['stuff_plus','location_plus','pitching_plus'])
    cols=['PitchUID','year','game_anon_id','pitcher_anon_id','stadium_id']+[c for c in normalized if c.endswith('_temporada_estadio')]
    normalized[cols].to_parquet(OUT/'scores_normalizados.parquet',index=False)
    (OUT/'referencias_temporada_estadio.json').write_text(json.dumps(refs,indent=2))
    print('Normalizacion por temporada y estadio completada',flush=True)


if __name__=='__main__':
    main()
