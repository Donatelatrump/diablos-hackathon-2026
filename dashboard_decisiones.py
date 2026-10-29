"""Decision-oriented presentation of existing predictions and evaluated aggregates."""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard_navigation import open_view
from dashboard_perfiles_estadios import PITCH_NAMES, TASK_NAMES, render_validation_summary


def pitcher_label(identifier):
    value=str(identifier)
    return 'Lanzador ' + value.removeprefix('pitcher_') if value.startswith('pitcher_') else value


def comparison_rows(current, reference):
    """Keep score points and probability percentage points in distinct units."""
    fields = [('stuff_plus', 'Calidad física · Stuff+', 'puntos'),
              ('location_plus', 'Ubicación · Location+', 'puntos'),
              ('pitching_plus', 'Evaluación general · Pitching+', 'puntos'),
              ('p_whiff', 'Swing fallado por lanzamiento', 'pp'),
              ('p_home_run_per_pitch', 'Jonrón por lanzamiento', 'pp')]
    return [{'Resultado': label, 'Elegido': float(current[key]) * (100 if unit == 'pp' else 1),
             'Referencia': float(reference[key]) * (100 if unit == 'pp' else 1),
             'Diferencia': (float(current[key]) - float(reference[key])) * (100 if unit == 'pp' else 1),
             'Unidad': unit} for key, label, unit in fields if key in current and key in reference]


def render_comparison(current, reference, current_place, reference_place):
    rows = comparison_rows(current, reference)
    st.markdown('#### Qué cambia entre los dos escenarios')
    st.write(f'**Elegido:** {current_place}  \n**Referencia:** {reference_place}')
    table = pd.DataFrame(rows)
    if table.empty:
        st.info('No hay resultados compartidos para comparar estos escenarios.')
        return
    shown = table.copy()
    for col in ['Elegido', 'Referencia']:
        shown[col] = [f'{value:.3f}%' if unit == 'pp' else f'{value:.2f}' for value, unit in zip(table[col], table.Unidad)]
    shown['Diferencia'] = [f'{value:+.3f} pp' if unit == 'pp' else f'{value:+.2f} puntos' for value, unit in zip(table.Diferencia, table.Unidad)]
    st.dataframe(shown.drop(columns='Unidad'), hide_index=True, width='stretch')
    score_rows = [r for r in rows if r['Unidad'] == 'puntos']
    if score_rows and all(abs(r['Diferencia']) < .005 for r in score_rows):
        st.info('Los tres índices se mantienen iguales. Con las mismas mediciones físicas, el modelo actual no añade un ajuste de puntuación por estadio. Esto no significa que la altitud carezca de efecto físico. Revisa las probabilidades: algunas sí pueden variar.')
    else:
        delta = float(current['pitching_plus']) - float(reference['pitching_plus'])
        st.write(f'La evaluación general cambia **{delta:+.2f} puntos** frente a la referencia, conservando las mismas mediciones del lanzamiento.')
    st.caption('pp = puntos porcentuales. Una diferencia de probabilidad no es una diferencia de Stuff+. Los resultados no garantizan lo que ocurrirá en un lanzamiento.')


def render_paths():
    with st.container(key='decision-paths'):
        st.markdown('### ¿Qué quieres resolver?')
        routes = [
            ('Para el coach', 'Comparar el contexto', 'Revisa el mismo lanzamiento en varios estadios y qué probabilidades cambian.', 'Comparar estadios', 'Simular y comparar v9'),
            ('Para dirección deportiva', 'Conocer un lanzador', 'Consulta su repertorio, evaluación y cuántos juegos respaldan la muestra.', 'Ver lanzadores', 'Lanzadores'),
            ('Para interpretar la evidencia', 'Saber cuánto confiar', 'Revisa el error, la calibración y los límites de cada prueba.', 'Ver confianza', 'Confianza'),
        ]
        for column, (role, title, description, label, view) in zip(st.columns(3), routes):
            with column, st.container(border=True):
                st.caption(role)
                st.markdown('#### ' + title)
                st.write(description)
                st.button(label, key='decision-' + view, on_click=open_view, args=(view,), use_container_width=True)


def game_variation(frame):
    games = frame.groupby(['year', 'pitcher_anon_id', 'game_anon_id']).pitching_plus.mean()
    return games.groupby(level=['year', 'pitcher_anon_id']).agg(
        variation_between_games='std', games_with_scores='count').reset_index()


@st.cache_data(show_spinner=False)
def load_game_variation(path, modified):
    frame = pd.read_parquet(path, columns=['year', 'pitcher_anon_id', 'game_anon_id', 'pitching_plus'])
    return game_variation(frame)


def render_pitcher_card(pitchers, arsenal, chosen):
    local = pitchers.loc[pitchers.pitcher_anon_id.eq(chosen)]
    if local.empty:
        st.info('Este lanzador no cumple el filtro de muestra actual. Elige otro para consultar su ficha.')
        return
    # A card always represents one evaluated season; never average yearly means.
    years = sorted(local.year.unique().tolist(), reverse=True)
    year = st.selectbox('Temporada de la ficha', years, key='pitcher-card-year')
    item = local.loc[local.year.eq(year)].iloc[0]
    with st.container(border=True, key='pitcher-decision-card'):
        st.markdown('### ' + pitcher_label(chosen))
        st.caption(f'Temporada {int(year)} · Identificador anónimo: {chosen}')
        for column, label, value in zip(st.columns(3), ['Calidad física', 'Ubicación', 'Evaluación general'],
                                        [item.stuff_plus, item.location_plus, item.pitching_plus]):
            column.metric(label, f'{value:.1f}')
        st.write(f'**Muestra:** {int(item.n_pitches):,} lanzamientos en **{int(item.n_games)} juegos**.')
        st.write('La evaluación está ' + ('por encima' if item.pitching_plus > 100 else 'por debajo' if item.pitching_plus < 100 else 'en el nivel') + ' de la referencia histórica de 100. Describe la muestra evaluada, no el talento futuro.')
        if arsenal is not None:
            repertoire = arsenal.loc[arsenal.pitcher_anon_id.eq(chosen) & arsenal.year.eq(year)]
            counts = repertoire.groupby('AutoPitchType').n_pitches.sum().sort_values(ascending=False)
            if not counts.empty:
                st.markdown('**Su repertorio en esta muestra**')
                st.dataframe(pd.DataFrame({'Lanzamiento': [PITCH_NAMES.get(t, t) for t in counts.index],
                    'Lanzamientos': counts.values, 'Uso (%)': (counts / counts.sum() * 100).round(1).values}),
                    hide_index=True, width='stretch')
        if pd.notna(item.get('variation_between_games')):
            st.metric('Variación entre juegos', f'{item.variation_between_games:.2f} puntos')
            st.caption(f'Desviación estándar de la evaluación general media de cada juego, sobre {int(item.games_with_scores)} juegos. Cada juego pesa igual. Menor variación describe mayor constancia en esta muestra, no predice estabilidad futura ni resistencia a la altura.')
        else:
            st.caption('No hay suficientes puntuaciones por juego para calcular la constancia de esta ficha.')
        st.write('**Qué revisar con el coach:** video, salud, rol previsto y cambios del repertorio antes de decidir un fichaje o una apertura.')


def render_confidence(root, output):
    root, output = Path(root), Path(output) if output else None
    st.title('¿Qué tan confiable es la evaluación?')
    st.write('Una puntuación ayuda a comparar. La confianza depende de qué se predice, con cuántos datos y contra qué referencia se evaluó.')
    if output is None or not (output / 'metricas.json').exists():
        st.info('Las métricas del modelo no están disponibles en esta copia.')
        return
    records = json.loads((output / 'metricas.json').read_text(encoding='utf-8'))
    by_task = {r['task']: r for r in records}
    if output.name == 'stuff_plus_output_v9_estadios':
        render_validation_summary(output)
    st.markdown('### Lo que muestran las pruebas actuales')
    physical = by_task.get('stuff_run_value', {})
    metrics = physical.get('metrics', {})
    skill = metrics.get('mse_skill_vs_count')
    if skill is not None:
        st.warning(f'La capa física tiene un error cuadrático {abs(skill)*100:.2f}% ' +
                   ('mayor' if skill < 0 else 'menor') + ' que una referencia que conoce solo el conteo. La puntuación física no basta para decidir por sí sola.')
    st.write('Las capas de ubicación y contexto pueden aportar información adicional. Una mejora promedio no garantiza una mejora para cada lanzador ni en cada estadio.')
    st.markdown('### ¿Las probabilidades coinciden con lo observado?')
    st.write('Comparamos las probabilidades anunciadas con lo que ocurrió en juegos de evaluación. El error cambia según el resultado que se quiere anticipar; no hay un único porcentaje de precisión para toda la herramienta.')
    rows = []
    for r in records:
        m = r.get('metrics', {})
        if 'brier' in m:
            rows.append({'Resultado': TASK_NAMES.get(r['task'], r['task']), 'Muestra': r['n'],
                         'Error Brier': m['brier'], 'Error de referencia': m.get('brier_baseline'),
                         'Mejora frente a referencia (%)': 100*m.get('brier_skill', 0),
                         'Diferencia de calibración (pp)': 100*m['ece_10_bins'] if 'ece_10_bins' in m else None})
    with st.expander('Ver errores, muestras y calibración'):
        st.caption('Esta tabla corresponde al modelo habitual. Las pruebas experimentales se pueden consultar al final y usan sus propias muestras.')
        st.dataframe(pd.DataFrame(rows).round(4), hide_index=True, width='stretch')
        st.caption('Brier mide el error de las probabilidades: menor es mejor. La diferencia de calibración resume la distancia entre probabilidades y frecuencias observadas por grupos; puede ocultar errores locales. Las tareas usan muestras y denominadores distintos.')
    st.markdown('### Qué sabemos y qué falta comprobar')
    for title, explanation in [
        ('Comparar contextos de estadio', 'La comparación predictiva mantiene fija la física medida. Algunos índices pueden ser idénticos porque el entrenamiento conservó la capa anterior; algunas probabilidades sí varían.'),
        ('Explorar el efecto físico del aire', 'El laboratorio de altitud ilustra una hipótesis simplificada de densidad y movimiento. Sus comprobaciones matemáticas no equivalen a validación contra vuelos reales; no modifica los índices de producción.'),
        ('Elegir lanzadores', 'Las fichas describen promedios y, cuando hay datos por juego, variación de la evaluación entre juegos. No identifican efectos causales ni demuestran constancia futura o resistencia a la altura.'),
        ('Evaluar hipótesis del reto', 'Los perfiles de Harp permiten revisar asociaciones por tipo y mano. No basta para confirmar mecanismos físicos, causalidad ni reglas universales sobre qué lanzamiento conviene.'),
        ('Validar con datos nuevos', '2026 ya se inspeccionó durante el desarrollo. Las separaciones históricas aportan evidencia retrospectiva; hace falta una evaluación futura independiente.'),
    ]:
        with st.expander(title):
            st.write(explanation)
    st.download_button('Descargar métricas evaluadas', (output / 'metricas.json').read_bytes(),
                       file_name='metricas_modelo.json', mime='application/json')
    st.divider()
    if st.toggle('Consultar investigación y modelos experimentales', key='confidence-research'):
        from dashboard_precision import render_precision_status
        render_precision_status(root)
