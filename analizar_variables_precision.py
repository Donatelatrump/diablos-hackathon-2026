"""Exploratory feature-block ablations on reused DEVELOPMENT partitions only.

Never reads 2026 outcomes, modifies production artifacts or promotes a model.
"""
import argparse
import json
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, CatBoostRegressor

import entrenar_stuff_plus_v9 as v9

EXTRA = list(dict.fromkeys(v9.v6.EXTRA_RAW + ['ZoneSpeed', 'ZoneTime', 'SpeedDrop',
    'VertRelAngle', 'HorzRelAngle', 'VertApprAngle', 'HorzApprAngle',
    'altitud_estadio_m', 'fecha_partido', 'Inning', 'Outs']))
GROUPS = {
    'actual': [],
    'aerodinamica': v9.v6.AERO_DERIVED,
    'vuelo_y_angulos': ['ZoneSpeed', 'ZoneTime', 'SpeedDrop', 'VertRelAngle',
                       'HorzRelAngle', 'VertApprAngle', 'HorzApprAngle'],
    'entorno_y_situacion': ['altitud_estadio_m', 'density_standard', 'month_sin', 'month_cos', 'Inning', 'Outs'],
}


def run(args):
    folder = Path(args.output)
    folder.mkdir(parents=True, exist_ok=False)
    source = Path('stuff_model_df_con_estadios.parquet')
    raw = v9.read_rows(source, 2026, True)
    with duckdb.connect() as con:
        cols = ','.join('"' + c + '"' for c in ['PitchUID', *EXTRA])
        extra = con.execute(f'SELECT {cols} FROM read_parquet(?) WHERE year < 2026', [str(source)]).fetchdf()
    raw = raw.merge(extra, on='PitchUID', validate='one_to_one')
    raw = v9.v5.prepare_raw(raw)
    parts = pd.read_parquet('stuff_plus_output_v9_estadios/particiones.parquet', columns=['PitchUID', 'partition'])
    raw = raw.merge(parts, on='PitchUID', validate='one_to_one')
    coverage = []
    for year, rows in raw.groupby('year'):
        for col in EXTRA:
            numeric = pd.to_numeric(rows[col], errors='coerce') if col != 'fecha_partido' else pd.to_datetime(rows[col], errors='coerce')
            finite = numeric.notna() if col == 'fecha_partido' else np.isfinite(numeric)
            coverage.append({'year': int(year), 'variable': col, 'n': len(rows), 'finite': int(finite.sum()),
                             'coverage': float(finite.mean()), 'unique': int(rows[col].nunique())})
    (folder/'cobertura.json').write_text(json.dumps(coverage, indent=2), encoding='utf-8')
    frame = v9.prepare_development(raw)
    altitude = pd.to_numeric(frame.altitud_estadio_m, errors='coerce')
    frame['density_standard'] = (1 - 2.25577e-5 * altitude) ** 4.25588
    month = pd.to_datetime(frame.fecha_partido, errors='coerce').dt.month
    frame['month_sin'], frame['month_cos'] = np.sin(2*np.pi*month/12), np.cos(2*np.pi*month/12)
    metadata = {'scope': 'Exploratory ablations; development partitions already inspected in v9; not new confirmation or production validation.',
        'source': str(source), 'source_sha256': v9.v6.file_hash(source), 'years': sorted(frame.year.unique().tolist()),
        'iterations': args.iterations, 'groups': GROUPS, 'seed': v9.SEED, 'tasks': args.tasks,
        'code_sha256': v9.v6.file_hash(__file__), 'rows_by_partition': frame.partition.value_counts().to_dict()}
    (folder/'protocolo.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    records = []
    for task in args.tasks:
        spec = v9.task_spec(task, True)
        classification = spec[3] == 'classification'
        rows = frame.loc[v9.v5.eligible(frame, spec)].reset_index(drop=True)
        fit, stop, cal, test = [rows.loc[rows.partition.eq(role)] for role in ['fit', 'early_stop', 'calibration', 'confirmation']]
        baseline = v9.fit_baseline(frame.loc[frame.partition.eq('fit')], spec)
        base_cal, base_test = v9.baseline_predict(cal, baseline), v9.baseline_predict(test, baseline)
        controls = None
        for name, extras in GROUPS.items():
            begin = time.monotonic()
            columns = list(dict.fromkeys(spec[1] + extras))
            cls = CatBoostClassifier if classification else CatBoostRegressor
            model = cls(iterations=args.iterations, depth=6, learning_rate=.045, l2_leaf_reg=20.,
                random_seed=v9.SEED, thread_count=3, loss_function='Logloss' if classification else 'RMSE',
                allow_writing_files=False, verbose=False)
            target = lambda data: data[spec[0]].to_numpy() if classification else data[spec[0]].to_numpy()-v9.baseline_predict(data, baseline)
            model.fit(v9.model_features(fit, columns), target(fit),
                cat_features=[c for c in columns if c in v9.v5.CATEGORICAL or c == 'stadium_id'],
                eval_set=(v9.model_features(stop, columns), target(stop)), early_stopping_rounds=35, use_best_model=True)
            pred_cal = v9.predict_raw(model, cal, task, baseline, columns)
            raw_test = v9.predict_raw(model, test, task, baseline, columns)
            processors = v9.fit_postprocessors(cal[spec[0]], pred_cal, base_cal, classification)
            # Fixed calibration policy across variants, not picked on this evaluation.
            processor = processors.get('sigmoid', processors['shrink']) if classification else processors['shrink']
            prediction = v9.postprocess(raw_test, base_test, processor)
            if controls is None:
                controls = prediction
            groups = test.year.astype(str) + ':' + test.game_anon_id.astype(str)
            gain = v9.grouped_gain(test[spec[0]], controls, prediction, groups, repetitions=500)
            per_year = {}
            for year in sorted(test.year.unique()):
                mask = test.year.eq(year).to_numpy()
                denominator = np.mean((test.loc[mask, spec[0]].to_numpy()-controls[mask])**2)
                per_year[str(year)] = float(1-np.mean((test.loc[mask, spec[0]].to_numpy()-prediction[mask])**2)/denominator)
            metric = v9.v5.metrics(test[spec[0]], prediction, fit[spec[0]], spec[3], count_baseline=base_test)
            record = {'task': task, 'variant': name, 'features': len(columns), 'n_fit': len(fit), 'n_evaluation': len(test),
                      'trees': model.tree_count_, 'seconds': round(time.monotonic()-begin, 2),
                      'metrics': metric, 'vs_same_budget_current': gain, 'year_gains': per_year,
                      'postprocessor': processor}
            records.append(record)
            (folder/'resultados.json').write_text(json.dumps(records, indent=2, allow_nan=False), encoding='utf-8')
            print(json.dumps(record, ensure_ascii=True), flush=True)
    print('Finished; production untouched.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='reports/precision_2026_10_28')
    parser.add_argument('--iterations', type=int, default=200)
    parser.add_argument('--tasks', nargs='+', default=['environment_run_value', 'whiff_given_swing'], choices=list(v9.TASKS))
    run(parser.parse_args())
