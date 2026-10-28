"""Evalua Harp Helu observado y exporta escenarios con fisica fija por estadio."""
import argparse
import json
from pathlib import Path

import pandas as pd

import entrenar_stuff_plus_v9 as v9


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', type=Path, default=Path('stuff_plus_output_v9_estadios'))
    parser.add_argument('--parquet', type=Path, default=Path('stuff_model_df_con_estadios.parquet'))
    args = parser.parse_args()
    out = args.salida
    protocol = json.loads((out / 'protocolo.json').read_text())
    if v9.v6.file_hash(args.parquet) != protocol['source_sha256']:
        raise ValueError('El dataset no coincide con el utilizado para entrenar')
    bundle = v9.load_bundle(out)
    development = v9.read_rows(args.parquet, protocol['test_year'], True)
    # Catalogo y categorias del desarrollo; nunca elegir contexto con outcomes de 2026.
    catalog = development.dropna(subset=['stadium_id']).groupby('stadium_id').agg(
        estadio=('stadium', lambda x: x.mode().iloc[0]),
        altitude_category=('altitude_category', lambda x: x.mode().iloc[0]),
        n_development=('PitchUID', 'size')).reset_index()
    catalog.to_csv(out / 'estadios.csv', index=False)
    test = v9.v5.prepare_raw(v9.read_rows(args.parquet, protocol['test_year'], False))
    observed = v9.infer(test, bundle)
    harp = test.stadium_id.eq('mexico_ahh')
    records = []
    for task, item in bundle[0]['tasks'].items():
        spec = v9.TASKS[task]
        mask = harp & v9.v5.eligible(test, spec)
        rows = test.loc[mask]
        if rows.empty:
            continue
        y = rows[spec[0]].to_numpy()
        predicted = observed.loc[mask, v9.v5.prediction_column(task, spec)].to_numpy()
        base = v9.baseline_predict(rows, item['baseline'])
        records.append(dict(task=task, n=len(rows),
            metrics=v9.v5.metrics(y, predicted, [item['baseline']['prior']], spec[3]),
            vs_baseline=v9.grouped_gain(y, base, predicted, rows.year.astype(str)+':'+rows.game_anon_id)))
    v9.v6.json_write(out / 'metricas_harp_helu.json', records)
    v9.v5.write_parquet(observed.loc[harp].reset_index(drop=True), out / 'scores_harp_helu_observados_2026.parquet')
    scenarios = test.copy()
    context = catalog.set_index('stadium_id').loc['mexico_ahh']
    scenarios['stadium_id'] = 'mexico_ahh'
    scenarios['stadium'] = context.estadio
    scenarios['altitude_category'] = context.altitude_category
    projected = v9.infer(scenarios, bundle)
    projected['stadium_id_original'] = test.stadium_id.to_numpy()
    projected['scenario'] = 'Harp Helu; fisica y ubicacion medidas fijas'
    v9.v5.write_parquet(projected, out / 'escenarios_harp_helu_2026.parquet')
    projected.groupby(['pitcher_anon_id', 'AutoPitchType']).agg(
        n_pitches=('PitchUID', 'size'), n_games=('game_anon_id', 'nunique'),
        stuff_plus=('stuff_plus', 'mean'), pitching_plus=('pitching_plus', 'mean'),
        expected_run_value=('pred_environment_run_value', 'mean')).to_csv(out / 'arsenal_escenario_harp_helu.csv')
    lines = ['# Reentrenamiento por estadios: Harp Helu', '',
        f"Origen del mapeo: origin/main, commit 9e75629. Desarrollo: {len(development):,} pitches de 2024-2025.",
        f"Harp Helu: {development.stadium_id.eq('mexico_ahh').sum():,} pitches de desarrollo; "
        f"{harp.sum():,} pitches y {test.loc[harp, 'game_anon_id'].nunique()} juegos evaluados de 2026.",
        '2026 es un benchmark reutilizado. El mapeo es inferido y auditado; no es una llave oficial.',
        'Estadio se incorpora solo en las tareas de entorno. Los pendientes usan una categoria ausente explicita.',
        'Los escenarios conservan fisica, ubicacion y conteo medidos; no simulan cambios aerodinamicos ni efectos causales.', '',
        '| Tarea | n Harp Helu | RMSE / Brier | Ganancia vs baseline |', '|---|---:|---:|---:|']
    for record in records:
        metric = record['metrics'].get('rmse', record['metrics'].get('brier'))
        gain = record['vs_baseline']['gain']
        gain_text = f'{gain:.2%}' if gain is not None else 'no estimable'
        lines.append(f"| {record['task']} | {record['n']} | {metric:.6f} | {gain_text} |")
    lines += ['', '## Seleccion congelada', '']
    for task in v9.CORE_TASKS:
        item = bundle[0]['tasks'][task]
        lines.append(f"- `{task}`: `{item['postprocessor']}`.")
    lines += ['', 'La herencia de entorno implica delta cero por construccion cuando no se confirma una ganancia en desarrollo.',
        'Predicciones observadas, escenarios, metricas y catalogo estan en esta misma carpeta.']
    (out / 'HARP_HELU.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('\n'.join(lines), flush=True)


if __name__ == '__main__':
    main()
