"""Lectura deportiva del analisis congelado; sin recalcular decisiones en la UI."""
from pathlib import Path
import json
import pandas as pd
import streamlit as st

PITCH_NAMES = {'Four-Seam': 'Recta de cuatro costuras', 'Sinker': 'Sinker',
    'Slider': 'Slider', 'Changeup': 'Cambio', 'Curveball': 'Curva', 'Cutter': 'Cutter',
    'Splitter': 'Splitter', 'Sweeper': 'Sweeper', 'Knuckleball': 'Bola de nudillos', 'Other': 'Otro'}
HANDS = {'Right': 'Derecho', 'Left': 'Zurdo', 'Undefined': 'Sin dato de mano'}
TASK_NAMES = {'stuff_run_value': 'Calidad física', 'xrunvalue': 'Física y ubicación',
    'arsenal_run_value': 'Con repertorio', 'environment_run_value': 'Evaluación combinada',
    'whiff': 'Swing fallido', 'whiff_given_swing': 'Fallo cuando intenta batear',
    'ball_in_play': 'Bola en juego', 'groundball_given_in_play': 'Rodado entre bolas en juego',
    'weak_contact': 'Contacto débil', 'hard_contact': 'Contacto duro',
    'home_run_per_pitch': 'Jonrón', 'called_strike': 'Strike cantado', 'chase': 'Swing fuera de zona'}


def render_validation_summary(output):
    output = Path(output)
    report = output.parent / 'reports/v9_estadios'
    st.write('Evaluamos los resultados en datos separados del ajuste. Cada prueba responde una pregunta distinta.')
    for column, mode, title in zip(st.columns(3), ['season', 'pitcher', 'park'],
        ['¿Funciona en otra temporada?', '¿Funciona con pitchers nuevos?', '¿Funciona sin haber visto Harp?']):
        paths = [output / 'metricas.json'] if mode == 'season' else [
            output.parent / f'stuff_plus_output_v9_estadios_{mode}/metricas.json', report / mode / 'metricas.json']
        source = next((path for path in paths if path.exists()), None)
        with column:
            with st.container(border=True):
                st.markdown('**'+title+'**')
                if source is None:
                    st.write('Prueba en preparación')
                    continue
                result = next(row for row in json.loads(source.read_text()) if row['task'] == 'environment_run_value')
                gain = result['vs_baseline']['gain']
                st.metric('Reducción del error', f'{gain*100:.2f}%')
                st.caption(f"Sobre {result['n']:,} lanzamientos, frente al promedio por conteo. Un valor negativo indica mayor error.")
    st.caption('2026 ya se utilizó en versiones anteriores. Estas pruebas aportan evidencia, pero no sustituyen una evaluación con datos futuros.')
    figure = report / 'calibracion_actual.png'
    if figure.exists():
        with st.expander('Cómo se comparan las probabilidades con lo observado'):
            st.write('Cuanto más cerca está la curva de la diagonal, más se parecen las probabilidades anunciadas a las frecuencias observadas. La muestra de cada resultado puede ser distinta.')
            st.image(str(figure), width='stretch')


def render_profiles(report):
    report = Path(report)
    st.subheader('Qué revisar para Harp Helú')
    st.write('Compara perfiles similares y prepara la conversación con el coach. Los datos orientan qué revisar; la decisión requiere video, salud, rol y consistencia.')
    if not (report / 'deltas_por_perfil.csv').exists():
        st.info('El análisis por perfil todavía está en preparación. Puedes usar el simulador para comparar un lanzamiento.')
        return
    deltas = pd.read_csv(report / 'deltas_por_perfil.csv')
    profiles = pd.read_csv(report / 'perfiles_fisicos.csv')
    coverage = pd.read_csv(report / 'soporte_perfiles.csv')
    left, right = st.columns(2)
    kind = left.selectbox('Lanzamiento que quieres revisar', sorted(coverage.pitch_type.unique()),
        format_func=lambda value: PITCH_NAMES.get(value, value), key='coach_profile_type')
    hands = sorted(coverage.loc[coverage.pitch_type.eq(kind), 'hand'].unique())
    hand = right.selectbox('Brazo del lanzador', hands, format_func=lambda value: HANDS.get(value, value), key='coach_profile_hand')
    support = coverage.loc[coverage.pitch_type.eq(kind) & coverage.hand.eq(hand)].iloc[0]
    local = deltas.loc[deltas.pitch_type.eq(kind) & deltas.hand.eq(hand)]
    a, b, c = st.columns(3)
    a.metric('Lanzamientos comparables', f'{int(support.n_supported):,}')
    b.metric('Juegos previos en Harp', f'{int(support.games_harp):,}')
    c.metric('Juegos previos de referencia', f'{int(support.games_sea):,}')
    st.caption('Referencia: Veracruz, Campeche y Cancún. La comparación conserva las mismas mediciones del lanzamiento y cambia su contexto de estadio.')
    calibration_path = report / 'calibracion_por_estadio.csv'
    if calibration_path.exists():
        calibration = pd.read_csv(calibration_path)
        hr = calibration.loc[calibration.stadium_id.eq('mexico_ahh') & calibration.task.eq('home_run_per_pitch')]
        if not hr.empty:
            expected = (hr.predicted * hr.n).sum() / hr.n.sum()
            observed = (hr.observed * hr.n).sum() / hr.n.sum()
            st.warning(f'Precaución con el riesgo de jonrón: en los juegos evaluados de Harp, el modelo estimó {expected*100:.2f} por 100 lanzamientos y se observaron {observed*100:.2f}. Una diferencia favorable entre escenarios requiere validación con más datos.')
    if local.empty:
        st.warning('Muestra insuficiente para comparar este perfil. Pide más mediciones y juegos antes de recomendar cambios de repertorio.')
    else:
        st.markdown('### Qué cambia en la predicción')
        for column, outcome, label, condition in zip(st.columns(3),
            ['p_whiff', 'p_hard_contact', 'p_home_run_per_pitch'],
            ['Swing fallido', 'Contacto duro', 'Jonrón'],
            ['por 100 lanzamientos', 'por 100 contactos con velocidad medida', 'por 100 lanzamientos']):
            selected = local.loc[local.outcome.eq(outcome)]
            if selected.empty:
                continue
            r = selected.iloc[0]
            with column:
                with st.container(border=True):
                    st.markdown(f'**{label}**')
                    st.metric('Harp Helú', f'{100*r.harp_mean:.2f} de 100',
                        delta=f'{100*r.delta:+.2f} frente a referencia', delta_color='off')
                    st.caption(condition)
                    st.write(f'Rango de incertidumbre del cambio: **{100*r.ci_low:+.2f} a {100*r.ci_high:+.2f}**.')
                    st.caption('Diferencia incierta' if r.ci_low <= 0 <= r.ci_high else 'Señal para revisar con video')
        st.info('La puntuación combinada permanece igual entre estadios: no se confirmó una mejora adicional al incorporar estadio. Los cambios anteriores son de probabilidades y no prueban que trasladar al pitcher cause ese efecto.')
        st.caption('Intervalos del 95% por juegos, con el modelo ya ajustado. Análisis exploratorio; no incluye toda la incertidumbre del entrenamiento ni garantiza resultados futuros.')
    st.markdown('### Rango físico para revisar prospectos')
    ranges = profiles.loc[profiles.pitch_type.eq(kind) & profiles.hand.eq(hand)]
    if ranges.empty:
        st.info('Todavía no hay una muestra suficiente para proponer rangos físicos de este tipo y mano.')
    else:
        r = ranges.iloc[0]
        rows = []
        for key, label, unit in [('RelSpeed', 'Velocidad de salida', 'mph'),
                                ('InducedVertBreak', 'Movimiento vertical inducido', 'pulgadas'),
                                ('HorzBreak', 'Movimiento horizontal', 'pulgadas'),
                                ('SpinRate', 'Giro de la pelota', 'rpm'),
                                ('velo_diff_vs_fb', 'Diferencia frente a su recta', 'mph')]:
            low, high = r[key+'_p25'], r[key+'_p75']
            rows.append({'Medición': label, 'Rango observado': f'{low:.1f} a {high:.1f} {unit}' if pd.notna(low) else 'Sin historial suficiente'})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
        st.caption(f'Rangos centrales del grupo con mejor calidad física: {int(r.n_top):,} lanzamientos en {int(r.games_top)} juegos de calibración. Son perfiles descriptivos; no son una receta ni una ventaja exclusiva de Harp Helú. No combines los extremos como si fueran un solo lanzamiento real.')
    with st.container(border=True):
        st.markdown('**Siguiente paso con el coach**')
        st.write('1. Revisa video y ubicación de los lanzamientos comparables.\n2. Contrasta el riesgo de contacto duro y jonrón con la capacidad de generar swings fallidos.\n3. Confirma salud, rol y consistencia antes de cambiar el uso del repertorio.')
    cases_path = report / 'casos_scouting.csv'
    if cases_path.exists():
        with st.expander('Tres ejemplos para preparar la revisión con el coach'):
            st.caption('Casos elegidos después de evaluar. Son perfiles anónimos para orientar una revisión; no son recomendaciones automáticas de contratación.')
            for case in pd.read_csv(cases_path).itertuples():
                with st.container(border=True):
                    st.markdown('**'+case.caso+'**')
                    st.write(f'Lanzador anónimo {case.pitcher_anon_id} · {case.n:,} lanzamientos · {case.games} juegos')
                    st.write(f'Pitching+ en escenario Harp: **{case.pitching_plus:.1f}**. {case.accion}')
                    st.caption('Repertorio observado: '+case.repertorio)
                    if pd.notna(case.ci_low):
                        st.caption(f'Intervalo por juegos: {case.ci_low:.1f} a {case.ci_high:.1f}. Describe estas predicciones con el modelo fijo; no es un intervalo del talento del jugador.')
    path = report / 'RECOMENDACIONES_ACTUALES.md'
    if path.exists():
        st.download_button('Descargar guía de revisión', path.read_bytes(), 'Recomendaciones_Harp_Helu.md', key='coach_recommendations_download')
