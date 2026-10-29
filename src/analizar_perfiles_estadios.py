"""Comparaciones pareadas y perfiles descriptivos con modelos congelados.

Los intervalos remuestrean juegos y condicionan en el modelo ya ajustado.
No son efectos causales ni incorporan incertidumbre del entrenamiento.
"""
from pathlib import Path
import json

import duckdb
import numpy as np
import pandas as pd

import entrenar_stuff_plus_v9 as v9

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'stuff_plus_output_v9_estadios'
REPORT = ROOT / 'reports/v9_estadios'
MEASUREMENTS = ['RelSpeed', 'InducedVertBreak', 'HorzBreak', 'SpinRate']
OUTCOMES = ['pitching_plus', 'p_whiff', 'p_groundball_given_in_play',
            'p_hard_contact', 'p_home_run_per_pitch']
SEA = ['veracruz_avila', 'campeche_barrera', 'cancun_avila']


def read_parquet(path):
    with duckdb.connect() as con:
        return con.execute('SELECT * FROM read_parquet(?)', [str(path)]).fetchdf()


def cluster_mean_interval(values, groups, repetitions=1000, seed=904):
    frame = pd.DataFrame({'value': np.asarray(values, float), 'group': np.asarray(groups)})
    frame = frame.dropna()
    agg = frame.groupby('group').value.agg(['sum', 'count'])
    if len(agg) < 2:
        return float(frame.value.mean()), None, None
    rng = np.random.default_rng(seed)
    sums, counts = agg['sum'].to_numpy(), agg['count'].to_numpy()
    draws = rng.integers(0, len(agg), size=(repetitions, len(agg)))
    means = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
    return float(frame.value.mean()), *np.quantile(means, [.025, .975]).tolist()


def scenario(frame, bundle, catalog, stadium):
    rows = frame.copy()
    rows['stadium_id'] = stadium
    rows['stadium'] = catalog.loc[stadium, 'estadio']
    rows['altitude_category'] = catalog.loc[stadium, 'altitude_category']
    return v9.infer(rows, bundle)


def common_support(development, test):
    """Intersection of marginal 1-99% ranges, never a guarantee of joint support."""
    mask = pd.Series(False, index=test.index)
    evidence = []
    for (kind, hand), rows in test.groupby(['AutoPitchType', 'PitcherThrows']):
        same = development.loc[development.AutoPitchType.eq(kind) & development.PitcherThrows.eq(hand)]
        harp = same.loc[same.stadium_id.eq('mexico_ahh')]
        sea = same.loc[same.stadium_id.isin(SEA)]
        n_harp_games = harp.groupby(['year', 'game_anon_id']).ngroups
        n_sea_games = sea.groupby(['year', 'game_anon_id']).ngroups
        enough = len(harp) >= 300 and len(sea) >= 300 and min(n_harp_games, n_sea_games) >= 10
        included = pd.Series(enough, index=rows.index)
        for column in MEASUREMENTS:
            a = pd.to_numeric(harp[column], errors='coerce').quantile([.01, .99])
            b = pd.to_numeric(sea[column], errors='coerce').quantile([.01, .99])
            low, high = max(a.iloc[0], b.iloc[0]), min(a.iloc[1], b.iloc[1])
            included &= pd.to_numeric(rows[column], errors='coerce').between(low, high)
        mask.loc[rows.index] = included
        evidence.append(dict(pitch_type=kind, hand=hand, n_harp_development=len(harp),
            n_sea_development=len(sea), games_harp=n_harp_games, games_sea=n_sea_games,
            n_test=len(rows), n_supported=int(included.sum()), sufficient_development=bool(enough)))
    return mask, pd.DataFrame(evidence)


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    protocol = json.loads((OUT / 'protocolo.json').read_text())
    source = ROOT / 'stuff_model_df_con_estadios.parquet'
    if v9.v6.file_hash(source) != protocol['source_sha256']:
        raise ValueError('Dataset distinto al del entrenamiento')
    bundle = v9.load_bundle(OUT)
    development = v9.read_rows(source, 2026, True)
    test = v9.read_rows(source, 2026, False)
    catalog = pd.read_csv(OUT / 'estadios.csv').set_index('stadium_id')
    assert catalog.loc[SEA, 'altitude_category'].eq('No Altitude').all()
    supported, coverage = common_support(development, test)
    coverage.to_csv(REPORT / 'soporte_perfiles.csv', index=False)
    harp = scenario(test, bundle, catalog, 'mexico_ahh')
    sea = sum(scenario(test, bundle, catalog, stadium)[OUTCOMES] for stadium in SEA) / len(SEA)
    delta = harp[OUTCOMES] - sea
    groups = test.year.astype(str) + ':' + test.game_anon_id.astype(str)
    records = []
    for (kind, hand), rows in test.loc[supported].groupby(['AutoPitchType', 'PitcherThrows']):
        idx = rows.index
        for outcome in OUTCOMES:
            mean, low, high = cluster_mean_interval(delta.loc[idx, outcome], groups.loc[idx])
            records.append(dict(pitch_type=kind, hand=hand, outcome=outcome, n=len(idx),
                games=groups.loc[idx].nunique(), harp_mean=float(harp.loc[idx, outcome].mean()),
                sea_mean=float(sea.loc[idx, outcome].mean()), delta=mean, ci_low=low, ci_high=high))
    deltas = pd.DataFrame(records)
    deltas.to_csv(REPORT / 'deltas_por_perfil.csv', index=False)

    # Select descriptive ranges using development calibration only; no 2026 outcomes.
    partitioned = v9.partition_games(development)
    prepared = v9.prepare_development(partitioned)
    cal = prepared.loc[prepared.partition.eq('calibration')].reset_index(drop=True)
    cal['stadium_id'] = 'mexico_ahh'
    cal['stadium'] = catalog.loc['mexico_ahh', 'estadio']
    cal['altitude_category'] = catalog.loc['mexico_ahh', 'altitude_category']
    scores = v9.add_scores(v9.predict_prepared(cal, bundle[0], bundle[1]), bundle[0]['reference'])
    # Profiles use physical score so a good location does not define a physical recipe.
    cal['physical_score'] = scores.stuff_plus.to_numpy()
    profiles = []
    for (kind, hand), rows in cal.groupby(['AutoPitchType', 'PitcherThrows']):
        if len(rows) < 300 or rows.groupby(['year', 'game_anon_id']).ngroups < 10:
            continue
        top = rows.loc[rows.physical_score.ge(rows.physical_score.quantile(.90))]
        record = dict(pitch_type=kind, hand=hand, n_calibration=len(rows), n_top=len(top),
            games_top=top.groupby(['year', 'game_anon_id']).ngroups,
            selection='top_10pct_physical_score_calibration',
            qualification='perfil descriptivo de calidad fisica; ventaja exclusiva Harp no demostrada')
        for column in MEASUREMENTS + ['velo_diff_vs_fb', 'ivb_diff_vs_fb', 'hb_diff_vs_fb', 'pitch_usage_pct']:
            values = pd.to_numeric(top[column], errors='coerce')
            record[column + '_p25'] = values.quantile(.25)
            record[column + '_p75'] = values.quantile(.75)
        profiles.append(record)
    pd.DataFrame(profiles).to_csv(REPORT / 'perfiles_fisicos.csv', index=False)

    # Curves describe reliability for every classifier and each observed stadium.
    raw = v9.v5.prepare_raw(test)
    observed = v9.infer(raw, bundle)
    reliability, by_stadium = [], []
    for task, spec in v9.TASKS.items():
        if spec[3] != 'classification':
            continue
        eligible = v9.v5.eligible(raw, spec)
        probability = observed[v9.v5.prediction_column(task, spec)]
        for stadium in ['ALL', *sorted(raw.stadium_id.dropna().unique())]:
            mask = eligible if stadium == 'ALL' else eligible & raw.stadium_id.eq(stadium)
            y, p = raw.loc[mask, spec[0]], probability.loc[mask]
            if not len(y):
                continue
            metrics = v9.v5.metrics(y.to_numpy(), p.to_numpy(), [bundle[0]['tasks'][task]['baseline']['prior']], 'classification')
            by_stadium.append(dict(stadium_id=stadium, task=task, n=len(y),
                games=raw.loc[mask].game_anon_id.nunique(), **metrics))
            bins = np.minimum((p * 10).astype(int), 9)
            for bin_id in sorted(bins.unique()):
                chosen = bins.eq(bin_id)
                reliability.append(dict(stadium_id=stadium, task=task, bin=int(bin_id),
                    n=int(chosen.sum()), predicted=float(p.loc[chosen].mean()), observed=float(y.loc[chosen].mean())))
    pd.DataFrame(by_stadium).to_csv(REPORT / 'metricas_por_estadio.csv', index=False)
    pd.DataFrame(reliability).to_csv(REPORT / 'calibracion_por_estadio.csv', index=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    curve = pd.DataFrame(reliability)
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.5), layout='constrained')
    for ax, task, title in zip(axes, ['whiff', 'hard_contact', 'home_run_per_pitch'],
                               ['Swing fallido', 'Contacto duro (condicional)', 'Jonrón por lanzamiento']):
        selected = curve.loc[curve.task.eq(task) & curve.stadium_id.eq('ALL')]
        selected = selected.loc[selected.n.ge(30)]
        ax.plot([0, 1], [0, 1], '--', color='#88909a', label='Predicción ideal')
        ax.plot(selected.predicted, selected.observed, 'o-', color='#ad1830', label='Modelo')
        maximum = min(1., max(.1, selected[['predicted', 'observed']].max().max() * 1.15))
        ax.set(xlim=(0, maximum), ylim=(0, maximum), title=title,
               xlabel='Probabilidad predicha', ylabel='Frecuencia observada')
        ax.grid(alpha=.2)
    fig.savefig(REPORT / 'calibracion_actual.png', dpi=170)
    plt.close(fig)
    lines = ['# Perfiles y recomendaciones para Harp Helú', '',
        'Comparación de 2026 con modelos congelados. Referencia: promedio equiponderado de Veracruz, Campeche y Cancún, todos en la categoría sin altitud.',
        'Cada lanzamiento conserva física, ubicación y arsenal. Las diferencias son predictivas, no efectos causales ni transporte aerodinámico.',
        'Se exige soporte de desarrollo: al menos 300 pitches y 10 juegos en Harp y en el grupo de referencia por tipo/mano; intersección de rangos marginales 1-99% de velocidad, IVB, HB y spin. Esto no garantiza soporte multivariado.',
        f'Pitches evaluados dentro de ese soporte: {int(supported.sum()):,} de {len(test):,}.',
        'Intervalos 95% con 1,000 remuestreos de juegos; condicionados al modelo, sin corregir múltiples comparaciones. Son análisis exploratorios.', '',
        '## Cómo actuar', '',
        '1. Comparar candidatos dentro del mismo tipo de lanzamiento y mano; revisar el rango físico y la historia de recta primaria.',
        '2. Si el intervalo del riesgo de jonrón o contacto duro queda por encima de cero, priorizar revisión de ubicación y video antes de aumentar uso.',
        '3. Si el intervalo cruza cero o falta soporte, solicitar más juegos. No etiquetar al pitcher como adaptado o inadaptado.',
        '4. Un diferencial favorable de swing fallido no compensa automáticamente un riesgo mayor de jonrón: revisar ambos resultados.',
        '5. El score combinado conserva delta cero entre estadios. No hay ganadores o perdedores de Pitching+ por altitud demostrados con esta selección.', '',
        'Advertencia de calibración: en Harp, el modelo estima en promedio 0.695 jonrones por 100 pitches y se observan 0.866 (52 en 6,005). Las pequeñas diferencias favorables del escenario no justifican afirmar menor riesgo real; se necesita validación prospectiva.', '',
        '## Diferencias observadas en las predicciones', '',
        '| Tipo / mano | n / juegos | Cambio HR por 100 pitches | IC95% | Lectura |',
        '|---|---:|---:|---:|---|']
    for r in deltas.loc[deltas.outcome.eq('p_home_run_per_pitch')].itertuples():
        reading = 'Riesgo predicho mayor: revisar ubicación' if r.ci_low > 0 else ('Riesgo predicho menor: validar con más datos' if r.ci_high < 0 else 'Diferencia incierta')
        lines.append(f'| {r.pitch_type} / {r.hand} | {r.n} / {r.games} | {r.delta*100:+.3f} | [{r.ci_low*100:+.3f}, {r.ci_high*100:+.3f}] | {reading} |')
    lines += ['', '## Perfil físico de referencia', '',
        'perfiles_fisicos.csv describe el cuartil central del 10% de mayor Stuff+ físico en calibración, por tipo y mano. Incluye diferenciales contra recta y uso histórico cuando existen.',
        'Son combinaciones observadas para comparar prospectos, no instrucciones para combinar por separado extremos de cada rango. No son un óptimo de contratación ni una ventaja exclusiva de Harp.',
        'Usar video, salud, comando y rol para decidir; los datos anonimizados no permiten resolver esos aspectos.', '',
        '## Fundamento y límites físicos', '',
        'La menor densidad del aire motiva examinar movimiento y riesgo de batazo elevado. El cambio real de movimiento requiere mediciones o un modelo físico adicional; no se aplica un porcentaje impuesto.',
        'El diferencial de velocidad y el rodado son hipótesis de interés del reto. Los resultados locales deben contrastarlas; no se recomienda una familia de pitcheos únicamente por esa hipótesis.', '',
        'Fuentes: convocatoria local, diccionario de datos, protocolo y modelos congelados de esta ejecución.',
        'Marco físico: Alan M. Nathan, Baseball at High Altitude (https://baseball.physics.illinois.edu/Denver.html) y Determining Pitch Movement from PITCHf/x Data (https://baseball.physics.illinois.edu/Movement.pdf). Las magnitudes observadas de este análisis proceden de los datos locales, no de trasladar porcentajes de MLB.']
    (REPORT / 'RECOMENDACIONES_ACTUALES.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    v9.v6.json_write(REPORT / 'protocolo_perfiles.json', dict(
        source_sha256=protocol['source_sha256'], bundle_sha256=v9.v6.file_hash(OUT / 'bundle.json'),
        reference_stadiums=SEA, model_fixed=True, causal=False, bootstrap_repetitions=1000,
        marginal_support_only=True, supported_pitches=int(supported.sum()), test_pitches=len(test),
        profile_selection='calibration physical score top 10%, no 2026 outcomes',
        uncertainty='sampling of test games conditional on fitted model; exploratory, no multiplicity correction'))
    print(f'Análisis terminado: {REPORT}', flush=True)


if __name__ == '__main__':
    main()
