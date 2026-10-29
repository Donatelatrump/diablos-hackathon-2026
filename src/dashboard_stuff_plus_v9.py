"""Coach-oriented simulation using the exact frozen v9 inference pipeline."""
import json
from pathlib import Path
import altair as alt
import pandas as pd
import streamlit as st
import entrenar_stuff_plus_v9 as v9
from dashboard_style import apply_dashboard_style, highlight_tutorial_target
from dashboard_perfiles_estadios import render_profiles, render_validation_summary, PITCH_NAMES, HANDS, TASK_NAMES


@st.cache_resource
def get_bundle(path, modified):
    return v9.load_bundle(path)


def stadium_scenarios(row, catalog, selected):
    """Each stadium carries its development altitude category, with fixed pitch physics."""
    indexed = catalog.set_index("stadium_id")
    return pd.DataFrame([
        {**row, "PitchUID": f"scenario-{i}", "stadium_id": identifier,
         "stadium": indexed.loc[identifier, "estadio"],
         "altitude_category": indexed.loc[identifier, "altitude_category"]}
        for i, identifier in enumerate(selected)
    ])


TUTORIAL_STEPS = {
    1: ("Elige el lanzamiento", "Selecciona el tipo de lanzamiento y la mano del pitcher. El simulador carga un perfil típico como punto de partida.", "profile"),
    2: ("Ajusta las mediciones", "Cambia velocidad, IVB (movimiento vertical), HB (movimiento lateral) y spin si tienes esos datos. Puedes conservar los valores típicos.", "measurements"),
    3: ("Añade contexto si lo conoces", "Abre “Release, ubicación y arsenal” para ajustar el punto de salida, la ubicación frente al bateador y el repertorio previo. Este paso es opcional.", "advanced"),
    4: ("Compara los resultados", "Cada columna representa un entorno. 100 es el promedio de referencia; un número mayor indica una evaluación relativa más alta. Stuff+ mira el lanzamiento, Location+ su ubicación y Pitching+ los combina.", "results"),
    5: ("Explora las otras vistas", "“Pitchers y movimiento” muestra resúmenes del grupo. “Cómo se validó” explica las pruebas del modelo. Usa estas vistas como apoyo para revisar, no como una decisión automática.", "analysis"),
}


def render_tutorial():
    with st.expander("¿Primera vez? Tutorial paso a paso", expanded=False):
        st.caption("Elige un paso y se resaltará la parte correspondiente de la pantalla.")
        step = st.segmented_control(
            "Paso del tutorial",
            options=list(TUTORIAL_STEPS),
            format_func=lambda value: f"Paso {value}",
            key="simulator_tutorial_step",
        )
        if step is not None:
            title, instructions, target = TUTORIAL_STEPS[step]
            st.info(f"**Paso {step} de {len(TUTORIAL_STEPS)} · {title}**\n\n{instructions}")
            highlight_tutorial_target(target)


def render(output, initial_tab='Lanzamiento y entorno'):
    output = Path(output)
    bundle = get_bundle(str(output), (output / "bundle.json").stat().st_mtime_ns)
    meta = bundle[0]

    st.title("Lanzadores y repertorios" if initial_tab == 'Pitchers y movimiento' else "Comparar un lanzamiento entre estadios")
    st.caption('Elige un lanzador para consultar su repertorio, muestra y constancia entre juegos.' if initial_tab == 'Pitchers y movimiento' else 'Elige un lanzamiento, ajusta sus mediciones y compara qué resultados esperamos en cada estadio.')
    with st.expander("Cómo leer los resultados", expanded=False):
        st.write("**100 es la referencia.** Una puntuación mayor indica una evaluación más favorable. 110 representa una desviación estándar sobre la referencia; no significa 10% más outs.")
        st.write("**Stuff+** describe la calidad física del lanzamiento. **Location+** describe su ubicación. **Pitching+** resume su evaluación combinada.")
        st.caption("Las probabilidades indican resultados esperados en muchos lanzamientos similares. Úsalas junto con video, consistencia y criterio del cuerpo técnico.")

    inherited = [task for task, item in meta["tasks"].items() if item["postprocessor"]["method"] == "parent"]
    if inherited:
        with st.expander('¿Por qué puede coincidir la puntuación entre estadios?'):
            st.info(
                "Si la puntuación es igual en dos estadios, los datos disponibles no respaldan cambiarla. "
                "Revisa también las probabilidades de swing fallido, contacto y jonrón: pueden ser diferentes. "
                "Esto no demuestra ausencia de un efecto físico de la altitud."
            )

    if not (output / "metricas.json").exists():
        st.warning("Estos modelos terminaron entrenamiento, pero su evaluación todavía no está disponible.")

    if initial_tab != 'Pitchers y movimiento':
        render_tutorial()

    profiles_tab, sim, rankings, evidence = st.tabs(["Qué revisar para Harp Helú", "Lanzamiento y entorno", "Lanzadores y movimiento", "Cómo se validó"],
        default='Lanzadores y movimiento' if initial_tab == 'Pitchers y movimiento' else initial_tab)
    with profiles_tab:
        render_profiles(output.parent / 'reports/v9_estadios')

    with sim:
        profiles = meta["input_profiles"]

        # Profile selection
        with st.container(key="tour-profile"):
            st.subheader("1. Perfil del lanzamiento")
            left, right = st.columns(2)
            pitch_type = left.selectbox(
                "Tipo de lanzamiento",
                sorted({p["type"] for p in profiles}),
                key="sim_pitch_type",
                format_func=lambda value: PITCH_NAMES.get(value, value)
            )
            hand = right.selectbox(
                "Mano del pitcher",
                sorted({p["hand"] for p in profiles if p["type"] == pitch_type}),
                key="sim_hand",
                format_func=lambda value: HANDS.get(value, value)
            )

        profile = next(p for p in profiles if p["type"] == pitch_type and p["hand"] == hand)
        row = {
            **profile["median"],
            "AutoPitchType": pitch_type,
            "PitcherThrows": hand,
            "pitcher_anon_id": "unknown",
            "PitchUID": "simulation",
            "BatterSide": "Right",
            "PlateLocHeight": 2.5,
            "PlateLocSide": 0.0,
            "Balls": 0,
            "Strikes": 0,
            "altitude_category": "No Altitude",
        }

        st.write("Parte del perfil típico y cambia solo las mediciones que conozcas.")

        # Physical measurements
        with st.container(key="tour-measurements"):
            st.subheader("2. Mediciones físicas")
            controls = [
                ("RelSpeed", "Velocidad (mph)"),
                ("InducedVertBreak", "IVB (pulgadas)"),
                ("HorzBreak", "HB (pulgadas)"),
                ("SpinRate", "Spin (rpm)"),
            ]
            field_cues = {
                "RelSpeed": ("↗", "Rapidez al salir", "Velocidad de la pelota al salir de la mano del pitcher, en millas por hora."),
                "InducedVertBreak": ("↕", "Movimiento vertical", "Cuánto se desvía verticalmente el lanzamiento por su movimiento aerodinámico, en pulgadas."),
                "HorzBreak": ("↔", "Movimiento lateral", "Cuánto se desvía a los lados, en pulgadas. La orientación depende de la mano del pitcher."),
                "SpinRate": ("⟳", "Giro de la pelota", "Velocidad de rotación de la pelota, en revoluciones por minuto (rpm)."),
            }

            cols = st.columns(4)
            for col, (key, label) in zip(cols, controls):
                value = row[key]
                icon, cue, explanation = field_cues[key]
                col.caption(f"{icon} {cue}")
                row[key] = col.number_input(
                    label,
                    value=float(value) if value is not None else None,
                    help=explanation,
                    key=f"{pitch_type}-{hand}-{key}",
                )

        # Advanced context
        with st.container(key="tour-advanced"):
            st.subheader("3. Contexto avanzado (opcional)")
            with st.expander("Release, ubicación y arsenal", expanded=False):
                st.caption("Punto de salida del pitcher · posición de la pelota al llegar al plato · contexto del bateador y el repertorio previo.")

                advanced = [
                    ("EffectiveVelo", "Velocidad efectiva (mph)"),
                    ("SpinAxis", "Eje de spin (grados)"),
                    ("RelHeight", "Altura de release (pies)"),
                    ("RelSide", "Lado de release (pies)"),
                    ("Extension", "Extensión (pies)"),
                    ("VertBreak", "Break vertical total (pulgadas)"),
                    ("PlateLocHeight", "Altura en plato (pies)"),
                    ("PlateLocSide", "Lado en plato (pies)"),
                ]
                cols = st.columns(3)
                for i, (key, label) in enumerate(advanced):
                    value = row[key]
                    row[key] = cols[i % 3].number_input(
                        label,
                        value=float(value) if value is not None else None,
                        key=f"{pitch_type}-{hand}-{key}",
                    )

                row["Balls"] = cols[0].number_input("Bolas", 0, 3, 0, key=f"{pitch_type}-{hand}-Balls")
                row["Strikes"] = cols[1].number_input("Strikes", 0, 2, 0, key=f"{pitch_type}-{hand}-Strikes")
                row["BatterSide"] = cols[2].selectbox("Lado del bateador", ["Right", "Left"], key=f"{pitch_type}-{hand}-BatterSide")

                known = sorted({r["pitcher_anon_id"] for r in meta["profile"]["fastballs"]})
                row["pitcher_anon_id"] = st.selectbox(
                    "Arsenal histórico",
                    ["Sin historial", *known],
                    key=f"{pitch_type}-{hand}-arsenal",
                )

        # Validation warnings
        from dashboard_precision import flight_inputs
        flight_inputs(row, f'{pitch_type}-{hand}')
        missing = [key for key in profile["median"] if row.get(key) is None]
        if missing:
            st.warning("Completa las mediciones para simular: " + ", ".join(missing))
        else:
            outside = [
                key for key in profile["median"]
                if profile["p01"][key] is not None and not profile["p01"][key] <= row[key] <= profile["p99"][key]
            ]
            if outside:
                st.warning("Fuera del rango central 98% de entrenamiento para este tipo y mano: " + ", ".join(outside))

            st.caption(
                f"Perfil basado en {profile['n']:,} pitches de entrenamiento. "
                "Estar dentro de rangos individuales no garantiza que la combinación esté bien representada."
            )

            # Run simulation
            scenarios = pd.DataFrame([
                {**row, "PitchUID": f"scenario-{i}", "altitude_category": category}
                for i, category in enumerate(["No Altitude", "Medium Altitude", "Extreme Altitude"])
            ])
            stadium_context = "stadium_id" in meta["tasks"]["environment_run_value"]["features"]
            if stadium_context:
                catalog = pd.read_csv(output / "estadios.csv")
                identifiers = catalog.stadium_id.tolist()
                defaults = [identifier for identifier in ["mexico_ahh", "veracruz_avila", "campeche_barrera"] if identifier in identifiers]
                selected_stadiums = st.multiselect(
                    "Estadios para comparar", identifiers, default=defaults, max_selections=3,
                    format_func=lambda identifier: catalog.set_index("stadium_id").loc[identifier, "estadio"],
                )
                if not selected_stadiums:
                    st.info("Selecciona al menos un estadio para simular.")
                    scenarios = None
                else:
                    scenarios = stadium_scenarios(row, catalog, selected_stadiums)
            if scenarios is not None:
                from precision_model import infer_dashboard
                predicted = infer_dashboard(scenarios, bundle, output)
                if predicted.precision_whiff_available.any():
                    st.caption('Fallo cuando intenta batear: se aplicó el ajuste ampliado con tus mediciones de vuelo. Los índices conservan su definición y modelo habituales.')
                complement = Path(__file__).resolve().parents[1] / 'reports/v9_estadios/complemento/season'
                has_complement = output.name == 'stuff_plus_output_v9_estadios' and (complement / 'indice_integral.json').exists()
                if has_complement:
                    from indice_integral import enrich_scenarios
                    predicted = enrich_scenarios(scenarios, predicted, bundle, complement)
                labels = ["Sin altitud", "Altitud media", "Altitud extrema"]
                if stadium_context:
                    labels = scenarios.stadium.tolist()

                # Results
                if len(predicted) > 1:
                    from dashboard_decisiones import render_comparison
                    render_comparison(predicted.iloc[0], predicted.iloc[1], labels[0], labels[1])
                    st.caption('La primera selección es el escenario elegido y la segunda su referencia. El detalle de todos los escenarios aparece a continuación.')
                with st.container(key="tour-results"):
                    st.subheader("4. Resultados por entorno")
                    st.caption('100 es la referencia histórica de cada índice. Una puntuación mayor indica una evaluación más favorable. La comparación conserva las mismas mediciones físicas.')
                    result_cols = st.columns(len(labels))
                    for col, label, (_, result) in zip(result_cols, labels, predicted.iterrows()):
                        with col:
                            st.markdown(f"#### {label}")
                            st.metric("Stuff+ · física", f"{result.stuff_plus:.1f}")
                            st.metric("Location+ · ubicación", f"{result.location_plus:.1f}")
                            st.metric("Pitching+ · combinado", f"{result.pitching_plus:.1f}")
                            if has_complement:
                                with st.expander('Más señales del lanzamiento'):
                                    st.metric("Índice integral", f"{result.indice_integral:.1f}")
                                    st.metric("Out al terminar el turno", f"{100 * result.p_out_within_pa:.1f}%")

                if not predicted.arsenal_history_available.iloc[0]:
                    st.info("Sin historial de recta primaria: el modelo recibe una bandera de arsenal ausente.")
                if has_complement:
                    st.caption("Out al terminar el turno: posibilidad de registrar al menos un out en la jugada que cierra el turno al bate, desde este lanzamiento. Incluye jugadas de selección y doble play; no necesariamente sale el bateador.")
                    with st.expander("Cómo leer el índice integral"):
                        st.write("Reúne ocho señales: fallos de swing, swings fuera de zona, strikes cantados, contacto débil, rodados, contacto duro, carreras esperadas y out al cerrar el turno. Más de 100 indica un perfil más favorable que la referencia histórica.")
                        st.write("Cada señal tiene el mismo peso después de llevarla a una escala comparable. Es un índice de comparación, no un porcentaje ni una promesa de rendimiento. Algunas señales están relacionadas entre sí.")

                for name, ref in meta["reference"].items():
                    if not ref["informative"]:
                        st.info(f"{name}: referencia constante; se muestra 100 y no permite ordenar lanzamientos.")

                st.caption(
                    "La comparación mantiene fija la física medida. No transporta movimiento al cambiar el aire. "
                    + ("El estadio procede del mapeo auditado; el delta es predictivo." if stadium_context
                     else "Altitud extrema no identifica Harp Helú; el delta es predictivo.")
                )

                # Probabilities table
                probabilities = {
                    "p_whiff": "Swing fallado por lanzamiento",
                    "p_whiff_given_swing": "Fallo cuando intenta batear",
                    "p_ball_in_play": "Bola en juego",
                    "p_groundball_given_in_play": "Rodado entre bolas en juego",
                    "p_weak_contact": "Contacto <85 mph dado contacto medido",
                    "p_hard_contact": "Contacto ≥95 mph dado contacto medido",
                    "p_home_run_per_pitch": "Jonrón por lanzamiento",
                    "p_called_strike": "Strike cantado",
                    "p_chase": "Swing fuera de zona por lanzamiento",
                    "p_out_within_pa": "Al menos un out al cerrar el turno al bate",
                }
                table = pd.DataFrame({"Resultado": [label for key, label in probabilities.items() if key in predicted]})
                for i, label in enumerate(labels):
                    table[label] = [f"{100 * predicted.iloc[i][key]:.1f}%" for key in probabilities if key in predicted]

                with st.expander('Ver probabilidades y descargar los escenarios', expanded=False):
                    st.dataframe(table, hide_index=True, width="stretch")
                    st.caption("Estas probabilidades incorporan ubicación y contexto. Las filas condicionales tienen denominadores distintos y no deben sumarse.")
                    st.download_button(
                        "Descargar escenarios", predicted.to_csv(index=False),
                        "escenarios_v9.csv", "text/csv", use_container_width=True,
                    )

                from dashboard_precision import render_candidate_preview
                render_candidate_preview(scenarios, predicted, bundle, output, labels)

                # SHAP explanation
                with st.expander("Qué impulsa el Stuff+ físico", expanded=False):
                    if st.button("Explicar este pitch", type="primary", key="explain_pitch"):
                        from explicar_v9 import explain_physical
                        explanation = explain_physical(scenarios.iloc[:1], bundle)
                        if explanation["informative"]:
                            contributions = explanation["contributions"].iloc[0]
                            top = contributions.abs().sort_values(ascending=False).head(8).index
                            shown = contributions.loc[top].copy()
                            shown.loc["Otras variables"] = contributions.drop(top).sum()
                            chart_data = shown.rename("Puntos").rename_axis("Variable").reset_index()
                            chart = alt.Chart(chart_data).mark_bar().encode(
                                x="Puntos:Q",
                                y=alt.Y("Variable:N", sort="-x"),
                                color=alt.condition(
                                    alt.datum.Puntos > 0,
                                    alt.value("#ad1830"),
                                    alt.value("#718096")
                                ),
                                tooltip=["Variable", "Puntos"],
                            ).properties(height=300)
                            st.altair_chart(chart, width="stretch")
                            st.caption(
                                f"Base del modelo: {explanation['base'][0]:.2f} puntos. "
                                f"Base + contribuciones = {explanation['score'][0]:.2f}. "
                                "Atribuciones SHAP a la predicción actual; no estiman el efecto causal de modificar una variable."
                            )
                        else:
                            st.info("El modelo físico conserva un baseline constante; no hay diferencias de features que explicar.")

    with rankings:
        st.subheader("Explora al lanzador y su repertorio")
        complement = Path(__file__).resolve().parents[1] / 'reports/v9_estadios/complemento/season'
        integral_path = complement / 'pitchers_integrales.csv'
        if output.name == 'stuff_plus_output_v9_estadios' and integral_path.exists():
            with st.expander("Comparar con el promedio de cada temporada y estadio"):
                st.write("Esta tabla ajusta las puntuaciones al grupo de lanzamientos evaluados de cada temporada y estadio: 100 es su promedio y 10 puntos equivalen a una desviación estándar. Sirve para revisar esa muestra histórica; el simulador conserva una referencia fija para lanzamientos nuevos.")
                st.caption("Con menos de 300 lanzamientos o estadio desconocido se usa el promedio de la temporada. Los promedios de lanzadores combinan sus distintos estadios; no garantizan que cada lanzador tenga media 100. El ajuste usa predicciones, nunca resultados reales del año evaluado.")
                integral = pd.read_csv(integral_path)
                integral = integral.loc[integral.n_pitches.ge(100) & integral.n_games.ge(5)]
                st.dataframe(integral.sort_values('indice_integral_temporada_estadio', ascending=False).rename(columns={
                    'year':'Temporada', 'pitcher_anon_id':'Lanzador', 'n_pitches':'Lanzamientos',
                    'n_games':'Juegos', 'p_out_within_pa':'Probabilidad de out al cerrar el turno',
                    'indice_integral':'Índice integral · referencia fija',
                    'indice_integral_temporada_estadio':'Índice integral · ajustado al grupo'}), hide_index=True, width='stretch')
                st.download_button('Descargar comparación ajustada', integral_path.read_bytes(), file_name=integral_path.name, mime='text/csv')
        if (output / "pitchers.csv").exists():
            pitchers = pd.read_csv(output / "pitchers.csv")

            with st.container(key='pitcher-filter-bar'):
                filter_col, order_col = st.columns([2, 3], vertical_alignment='bottom')
            with filter_col:
                min_pitches = st.checkbox("Al menos 100 lanzamientos y cinco juegos", value=True, key="filter_pitchers")

            if min_pitches:
                pitchers = pitchers.loc[pitchers.n_pitches.ge(100) & pitchers.n_games.ge(5)]

            orders = {'Mejor evaluación combinada': 'pitching_plus', 'Mayor calidad física': 'stuff_plus', 'Mayor muestra de lanzamientos': 'n_pitches'}
            from dashboard_decisiones import load_game_variation
            scores_path = output / 'scores_pitch_v9.parquet'
            if scores_path.exists():
                pitchers = pitchers.merge(load_game_variation(str(scores_path), scores_path.stat().st_mtime_ns),
                    on=['year', 'pitcher_anon_id'], how='left', validate='one_to_one')
                orders['Menor variación entre juegos'] = 'variation_between_games'
            order = order_col.selectbox('Ordenar la lista por', list(orders), key='pitcher-decision-order')
            pitchers = pitchers.sort_values(orders[order], ascending=orders[order] == 'variation_between_games', na_position='last')
            movement = pd.read_csv(output / 'mapa_movimiento.csv')
            choices = pitchers.pitcher_anon_id.drop_duplicates().tolist()
            if not choices:
                st.info('No hay lanzadores que cumplan el filtro de muestra. Puedes desactivarlo para explorar los datos disponibles.')
                return
            if st.session_state.get('movement_pitcher') not in choices:
                st.session_state['movement_pitcher'] = choices[0]
            from dashboard_decisiones import pitcher_label
            st.caption(f'{len(choices):,} lanzadores disponibles con el filtro actual. Los nombres están anonimizados por la liga.')
            chosen = st.selectbox('Lanzador que quieres conocer', choices, key='movement_pitcher', format_func=pitcher_label)
            arsenal_path = output / 'arsenal.csv'
            from dashboard_decisiones import render_pitcher_card
            render_pitcher_card(pitchers, pd.read_csv(arsenal_path) if arsenal_path.exists() else None, chosen)

            with st.expander('Ver la tabla completa de lanzadores'):
                st.dataframe(
                    pitchers.rename(columns={
                        "pitcher_anon_id": "Lanzador anónimo", "year": "Temporada", "n_pitches": "Lanzamientos",
                        "n_games": "Juegos", "stuff_plus": "Stuff+ · física", "location_plus": "Location+ · ubicación",
                        "pitching_plus": "Pitching+ · combinado"}),
                    hide_index=True,
                    width="stretch",
                )
                st.caption(
                    "Promedios descriptivos de los lanzamientos evaluados. "
                    "La muestra y el contexto afectan el ranking; no son estimaciones de talento ni intervalos de confianza."
                )

            # Movement map
            st.markdown("### Mapa de movimiento")
            local = movement.loc[movement.pitcher_anon_id.eq(chosen)].copy()
            local['Lanzamiento'] = local.AutoPitchType.map(lambda value: PITCH_NAMES.get(value, value))
            local['Entorno'] = local.altitude_category.map({'No Altitude':'Altitud baja', 'Medium Altitude':'Altitud media', 'Extreme Altitude':'Altitud extrema'}).fillna('Sin categoría disponible')

            color_options = {
                "stuff_plus": "Stuff+",
                "pitching_plus": "Pitching+",
            }
            color_key = st.selectbox(
                "Color del mapa",
                list(color_options.keys()),
                format_func=lambda x: color_options[x],
                key="movement_color"
            )

            chart = alt.Chart(local).mark_circle(opacity=0.9, stroke='#49614c', strokeWidth=.6).encode(
                x=alt.X("HB:Q", title="Movimiento lateral (pulgadas)"),
                y=alt.Y("IVB:Q", title="Movimiento vertical inducido (pulgadas)"),
                size=alt.Size("n:Q", title="Lanzamientos", scale=alt.Scale(range=[25, 500])),
                color=alt.Color(f"{color_key}:Q", title=color_options[color_key], scale=alt.Scale(range=['#dce9de','#244c3a'])),
                shape=alt.Shape('Lanzamiento:N', title='Tipo de lanzamiento'),
                tooltip=[alt.Tooltip('Lanzamiento:N'),alt.Tooltip('Entorno:N'),alt.Tooltip('n:Q',title='Lanzamientos',format=',.0f'),
                         alt.Tooltip('velocity:Q',title='Velocidad (mph)',format='.1f'),
                         alt.Tooltip('HB:Q',title='Movimiento lateral (pulgadas)',format='.1f'),
                         alt.Tooltip('IVB:Q',title='Movimiento vertical (pulgadas)',format='.1f'),
                         alt.Tooltip('stuff_plus:Q',title='Calidad física · Stuff+',format='.1f'),
                         alt.Tooltip('pitching_plus:Q',title='Evaluación general · Pitching+',format='.1f')],
            ).interactive().properties(height=450)

            st.altair_chart(chart, width="stretch")
            st.caption(
                "Cada punto es una media por tipo y categoría de altitud; no muestra trayectorias ni pitches individuales. "
                "HB de zurdos se refleja para comparar por mano."
            )

            # Arsenal
            st.markdown("### Repertorio del lanzador")
            arsenal_path = output / "arsenal.csv"
            if arsenal_path.exists():
                arsenal = pd.read_csv(arsenal_path)
                st.dataframe(
                    arsenal.loc[arsenal.pitcher_anon_id.eq(chosen)].rename(columns={
                        "pitcher_anon_id": "Lanzador anónimo", "AutoPitchType": "Tipo de lanzamiento",
                        "altitude_category": "Categoría de altitud", "year": "Temporada", "n_pitches": "Lanzamientos",
                        "n_games": "Juegos", "stuff_plus": "Stuff+", "location_plus": "Location+", "pitching_plus": "Pitching+"}),
                    hide_index=True,
                    width="stretch",
                )
        else:
            st.info("La evaluación genera los agregados de pitchers y el mapa.")

    with evidence:
        st.subheader("Cómo se validó")
        supplement = Path(__file__).resolve().parents[1] / 'reports/v9_estadios/complemento'
        if output.name == 'stuff_plus_output_v9_estadios' and (supplement / 'park/metricas.json').exists():
            with st.expander("Pruebas de la probabilidad de out al terminar el turno"):
                records = []
                for mode, label in [('season', 'Temporada 2026'), ('pitcher', 'Lanzadores reservados'), ('park', 'Harp fuera del entrenamiento')]:
                    item = json.loads((supplement / mode / 'metricas.json').read_text())
                    records.append({'Prueba':label, 'Lanzamientos evaluados':item['pitches'], 'Turnos':item['pa'],
                        'Error de probabilidad (menor es mejor)':round(item['brier'], 4),
                        'Reducción frente al promedio por conteo':f"{item['gain']['gain']:.2%}"})
                st.dataframe(pd.DataFrame(records), hide_index=True, width='stretch')
                st.caption("Solo se evalúan turnos reconstruidos completos. Un mismo turno aporta varios lanzamientos; los intervalos remuestrean juegos completos. No es una prueba futura intacta.")
        render_validation_summary(output)
        st.write(
            "Los juegos se separan en ajuste, parada temprana, calibración, búsqueda y confirmación. "
            "La temporada de evaluación no decide modelos ni escalas."
        )

        with st.expander("Detalle para el equipo de análisis", expanded=False):
            st.markdown("### Selección de modelos")
            st.dataframe(
                pd.DataFrame([{
                    "Resultado": TASK_NAMES.get(task, task),
                    "Predicción elegida": {"raw": "Modelo", "sigmoid": "Modelo calibrado", "shrink": "Modelo ajustado", "parent": "Capa anterior", "baseline": "Promedio de referencia"}.get(item["selection"].get("selected", "baseline"), "Promedio de referencia"),
                    "Comparada contra": TASK_NAMES.get(item["selection"].get("control_task"), "Promedio de referencia"),
                    "Confirmada": item["selection"]["promoted"],
                    "Filas de ajuste": item["n_fit"],
                } for task, item in meta["tasks"].items()]),
                hide_index=True,
                width="stretch",
            )

            if (output / "ablaciones.json").exists():
                st.markdown("### Ablaciones: cambio de error al añadir ubicación, arsenal y entorno")
                st.dataframe(
                    pd.DataFrame(json.loads((output / "ablaciones.json").read_text())),
                    hide_index=True,
                    width="stretch",
                )
                st.caption(
                    "Ganancia = 1 − MSE nuevo / MSE anterior. Intervalos mediante remuestreo de juegos. "
                    "No representan efectos causales."
                )


if __name__ == "__main__":
    st.set_page_config(page_title="Diablos · Simulador v9", layout="wide")
    apply_dashboard_style()
    render(Path(__file__).resolve().parents[1] / "stuff_plus_output_v9")
