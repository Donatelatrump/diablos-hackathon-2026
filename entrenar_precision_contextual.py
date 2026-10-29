"""Gated context-only whiff experiment; no rewrite of frozen v9 or its scores."""
import argparse
import json
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.metrics import log_loss

import entrenar_stuff_plus_v9 as v9
from precision_features import FLIGHT, SEQUENCE, RECENT, past_context
from precision_model import model_features

BASE = Path('stuff_plus_output_v9_estadios')
SOURCE = Path('stuff_model_df_con_estadios.parquet')
TASK = 'whiff_given_swing'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def read_development():
    raw = v9.read_rows(SOURCE, 2026, True)
    extras = FLIGHT + ['Inning', 'Top/Bottom', 'OutsOnPlay', 'batter_anon_id', 'catcher_anon_id', 'fecha_partido']
    with duckdb.connect() as con:
        columns = ','.join('"' + c + '"' for c in ['PitchUID', *extras])
        extra = con.execute(f'SELECT {columns} FROM read_parquet(?) WHERE year < 2026', [str(SOURCE)]).fetchdf()
    raw = raw.merge(extra, on='PitchUID', validate='one_to_one')
    raw = v9.v5.prepare_raw(raw)
    parts = pd.read_parquet(BASE / 'particiones.parquet', columns=['PitchUID', 'partition'])
    return raw.merge(parts, on='PitchUID', validate='one_to_one')


def prepare(raw, history_mask):
    chunks = []
    for year in sorted(raw.year.unique()):
        history = raw.loc[history_mask & raw.year.lt(year)]
        chunks.append(v9.apply_profile(raw.loc[raw.year.eq(year)], v9.fit_profile(history)))
    prepared = pd.concat(chunks, ignore_index=True)
    # Merge by identity, not row order, after year-wise history preparation.
    context = past_context(raw, history_mask)
    context['PitchUID'] = raw.PitchUID.to_numpy()
    return prepared.merge(context, on='PitchUID', validate='one_to_one')


def fit_classifier(fit, stop, columns, iterations, seed=v9.SEED, l2=20.):
    model = CatBoostClassifier(iterations=iterations, depth=6, learning_rate=.045,
        l2_leaf_reg=l2, random_seed=seed, thread_count=3, loss_function='Logloss',
        allow_writing_files=False, verbose=False)
    model.fit(model_features(fit, columns), fit.is_whiff,
        cat_features=[c for c in columns if c in v9.v5.CATEGORICAL or c == 'stadium_id'],
        eval_set=(model_features(stop, columns), stop.is_whiff), early_stopping_rounds=35, use_best_model=True)
    return model


def predict(model, rows, columns, processor=None, baseline=None):
    p = model.predict_proba(model_features(rows, columns))[:, 1]
    return v9.postprocess(p, v9.baseline_predict(rows, baseline), processor) if processor else p


def diagnostics(rows, reference, candidate):
    groups = rows.year.astype(str) + ':' + rows.game_anon_id.astype(str)
    result = v9.grouped_gain(rows.is_whiff, reference, candidate, groups, repetitions=1000)
    loss = lambda p: float(log_loss(rows.is_whiff, np.clip(p, 1e-6, 1-1e-6), labels=[0,1]))
    result['baseline_logloss'], result['candidate_logloss'] = loss(reference), loss(candidate)
    result['n'] = len(rows)
    result['year_gains'] = {}
    for year in sorted(rows.year.unique()):
        mask = rows.year.eq(year).to_numpy()
        base_error = np.mean((rows.loc[mask, 'is_whiff'].to_numpy()-reference[mask])**2)
        result['year_gains'][str(year)] = float(1-np.mean((rows.loc[mask, 'is_whiff'].to_numpy()-candidate[mask])**2)/base_error)
    result['passes'] = bool(result['groups'] >= 5 and result['gain'] >= .001 and result['ci_low'] is not None
        and result['ci_low'] > 0 and result['candidate_logloss'] <= result['baseline_logloss']*1.0015
        and all(v >= -.001 for v in result['year_gains'].values()))
    return result


def run(args):
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    raw = read_development()
    source_hash = v9.v6.file_hash(SOURCE)
    bundle = v9.load_bundle(BASE)
    protocol = {'source_sha256': source_hash, 'base_bundle_sha256': v9.v6.file_hash(BASE/'bundle.json'),
        'years': [2024,2025], 'iterations': args.iterations, 'seed': v9.SEED,
        'feature_candidates': {'flight': FLIGHT, 'flight_context': FLIGHT+SEQUENCE+RECENT},
        'scope': 'Retrospective development selection and robustness audits; 2026 not used for selection.',
        'code_sha256': v9.v6.file_hash(__file__), 'feature_code_sha256': v9.v6.file_hash('precision_features.py')}
    write(out/'protocolo.json', protocol)
    frame = prepare(raw, raw.partition.eq('fit'))
    frame = frame.loc[frame.is_swing.eq(1) & frame.is_whiff.notna()].reset_index(drop=True)
    fit, stop, cal, selection = [frame.loc[frame.partition.eq(p)].reset_index(drop=True)
        for p in ['fit','early_stop','calibration','unused']]
    selection = frame.loc[frame.partition.isin(['tune','confirmation'])].reset_index(drop=True)
    columns_base = bundle[0]['tasks'][TASK]['features']
    control = v9.predict_prepared(selection, *bundle)['p_whiff_given_swing'].to_numpy()
    baseline = v9.fit_baseline(fit, v9.task_spec(TASK, True))
    options, candidates = {'baseline': control}, {}
    for name, extras in protocol['feature_candidates'].items():
        begin = time.monotonic()
        columns = list(dict.fromkeys(columns_base + extras))
        model = fit_classifier(fit, stop, columns, args.iterations)
        pcal = predict(model, cal, columns)
        processors = v9.fit_postprocessors(cal.is_whiff, pcal, v9.baseline_predict(cal, baseline), True)
        for processor_name, processor in processors.items():
            key = name + '__' + processor_name
            options[key] = predict(model, selection, columns, processor, baseline)
            candidates[key] = {'name':name,'features':columns,'postprocessor':processor}
        model.save_model(str(out/(name+'.cbm')))
        print(json.dumps({'fit':name,'trees':model.tree_count_,'seconds':round(time.monotonic()-begin,1)}), flush=True)
    choice = v9.choose_candidate(selection.is_whiff, options, selection.partition.eq('tune'), selection.year,
        selection.year.astype(str)+':'+selection.game_anon_id.astype(str), True)
    write(out/'seleccion.json', choice)
    report = {'selection':choice, 'audits':{}, 'accepted':False}
    selected = choice['candidate']
    if selected == 'baseline':
        write(out/'precision.json', report)
        print('No candidate beat the frozen baseline on development.', flush=True)
        return
    item = candidates[selected]
    report.update(item, baseline=baseline, model=item['name']+'.cbm', model_sha256=v9.v6.file_hash(out/(item['name']+'.cbm')),
        base_bundle_sha256=protocol['base_bundle_sha256'])
    required = FLIGHT.copy()
    if item['name'] == 'flight_context':
        required += ['observed_workload','previous_available','recent_available']
    report['required_inputs'] = required
    report['bounds'] = {c:[float(fit[c].min()),float(fit[c].max())] for c in required}
    write(out/'precision.json', report)
    # A non-promoted winner remains an experiment; audits still document it.
    for mode in ['temporal', 'pitcher', 'park']:
        trainable = raw.partition.eq('fit')
        if mode == 'temporal':
            keep = raw.year.eq(2024)
            audit_mask = raw.year.eq(2025)
        elif mode == 'pitcher':
            held = raw.pitcher_anon_id.map(v9.held_pitcher)
            keep, audit_mask = ~held, held & raw.partition.eq('confirmation')
        else:
            held = raw.stadium_id.eq('mexico_ahh')
            keep, audit_mask = ~held, held & raw.partition.eq('confirmation')
        local = prepare(raw, trainable & keep)
        local = local.set_index('PitchUID').loc[raw.PitchUID].reset_index()
        eligible = local.is_swing.eq(1) & local.is_whiff.notna()
        tr = local.loc[keep.to_numpy() & local.partition.eq('fit') & eligible].reset_index(drop=True)
        va = local.loc[keep.to_numpy() & local.partition.eq('early_stop') & eligible].reset_index(drop=True)
        ca = local.loc[keep.to_numpy() & local.partition.eq('calibration') & eligible].reset_index(drop=True)
        ev = local.loc[audit_mask.to_numpy() & eligible].reset_index(drop=True)
        audit_base = v9.fit_baseline(tr, v9.task_spec(TASK, True))
        outputs = []
        for columns in [columns_base,item['features']]:
            model = fit_classifier(tr,va,columns,args.iterations)
            pca = predict(model,ca,columns)
            processors = v9.fit_postprocessors(ca.is_whiff,pca,v9.baseline_predict(ca,audit_base),True)
            # Identical fixed calibration policy for refitted audit models.
            processor = processors.get('sigmoid',processors['raw'])
            outputs.append(predict(model,ev,columns,processor,audit_base))
        result = diagnostics(ev,*outputs)
        report['audits'][mode] = result
        write(out/'precision.json', report)
        print(json.dumps({'audit':mode,**result}), flush=True)
    report['accepted'] = bool(choice['promoted'] and all(r['passes'] for r in report['audits'].values()))
    report['claim'] = 'Conditional-whiff overlay only; no change to RV scores or physical Stuff+; retrospective evidence, not prospective validation.'
    write(out/'precision.json', report)
    print(json.dumps({'accepted':report['accepted'],'selected':selected}), flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='precision_output_2026_10_28')
    parser.add_argument('--iterations',type=int,default=400)
    run(parser.parse_args())
