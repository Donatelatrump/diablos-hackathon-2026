"""Guided entry to the existing frozen inference pipeline."""
from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard_perfiles_estadios import HANDS, PITCH_NAMES
from dashboard_navigation import open_view


def choose_example(pitch):
    st.session_state['start_pitch'] = pitch


def choose_hand(hand):
    st.session_state['start_hand'] = hand


def render_start(output):
    st.markdown('''<section class="editorial-hero" aria-labelledby="start-title">
<div><span class="editorial-kicker">BÉISBOL · DATOS · CRITERIO DEPORTIVO</span>
<h1 id="start-title">Conoce tu <em>lanzamiento.</em></h1>
<p>Elige un lanzamiento y compara su evaluación entre estadios. Empieza con un ejemplo o añade tus propias mediciones.</p>
</div>
</section>''', unsafe_allow_html=True)
    if output is None:
        st.info("El análisis aún no está disponible en este equipo. Puedes consultar la ayuda desde el menú de arriba.")
        return

    from dashboard_stuff_plus_v9 import get_bundle, stadium_scenarios
    import entrenar_stuff_plus_v9 as v9

    output = Path(output)
    bundle = get_bundle(str(output), (output / "bundle.json").stat().st_mtime_ns)
    meta = bundle[0]
    profiles = meta["input_profiles"]

    st.markdown('<div id="simulador" class="workbench-heading"><div><span class="editorial-kicker">TU PUNTO DE PARTIDA</span><h2>Prepara tu lanzamiento</h2></div><p>Elige el lanzamiento y el escenario.<br>Después consulta tu evaluación.</p></div>', unsafe_allow_html=True)
    types = sorted({p["type"] for p in profiles})
    if st.session_state.get('start_pitch') not in types:
        st.session_state['start_pitch'] = 'Four-Seam' if 'Four-Seam' in types else types[0]
    with st.container(key="pitch-presets"):
        for col, (value, label) in zip(st.columns(4), [('Four-Seam', 'Recta de cuatro costuras'), ('Curveball', 'Curva'), ('Slider', 'Slider'), ('Changeup', 'Cambio')]):
            if value in types:
                col.button(label, key='preset-' + value, use_container_width=True,
                    type='primary' if st.session_state.get('start_pitch', 'Four-Seam') == value else 'secondary',
                    on_click=choose_example, args=(value,))
    with st.container(key="start-workbench"):
        pitch_panel, visual_panel = st.columns([.9, 1.6], gap="large")
    with pitch_panel, st.container(border=False, key="start-pitch-card"):
        st.markdown('<div class="pitch-card-heading"><span>01</span><h3>Elige tu lanzamiento</h3></div>', unsafe_allow_html=True)
        pitch = st.selectbox("Tipo de lanzamiento", types,
            index=None, format_func=lambda value: PITCH_NAMES.get(value, value), key="start_pitch")
        hands = sorted({p["hand"] for p in profiles if p["type"] == pitch})
        hand = st.session_state.get('start_hand', hands[0])
        if hand not in hands:
            hand = hands[0]
        st.session_state['start_hand'] = hand
        with st.container(key='start-hand-choice'):
            st.markdown('<p class="hand-field-label">Mano del lanzador</p>', unsafe_allow_html=True)
            for column, value in zip(st.columns(len(hands)), hands):
                column.button(HANDS.get(value, value), key='start-hand-' + value,
                    use_container_width=True, type='primary' if value == hand else 'secondary',
                    on_click=choose_hand, args=(value,))
        st.markdown('<div class="profile-help"><span aria-hidden="true">i</span><p>Ejemplo con mediciones típicas.<br>No representa a un jugador concreto.</p></div>', unsafe_allow_html=True)

    profile = next(p for p in profiles if p["type"] == pitch and p["hand"] == hand)
    row = {**profile["median"], "AutoPitchType": pitch, "PitcherThrows": hand,
        "pitcher_anon_id": "unknown", "PitchUID": "guided", "BatterSide": "Right",
        "PlateLocHeight": 2.5, "PlateLocSide": 0., "Balls": 0, "Strikes": 0,
        "altitude_category": "No Altitude"}
    stadium_context = "stadium_id" in meta["tasks"]["environment_run_value"]["features"]
    with pitch_panel, st.container(key="start-scenario-card"), st.form(f"start_form-{pitch}-{hand}", border=False):
        st.markdown('<div class="pitch-card-heading"><span>02</span><h3>Elige el escenario</h3></div>', unsafe_allow_html=True)
        if stadium_context:
            catalog = pd.read_csv(output / "estadios.csv")
            ids = catalog.stadium_id.tolist()
            selected = st.selectbox("Estadio", ids,
                index=ids.index("mexico_ahh") if "mexico_ahh" in ids else 0,
                format_func=lambda value: catalog.set_index("stadium_id").loc[value, "estadio"])
            reference_place = st.selectbox('Comparar con', ids,
                index=ids.index('veracruz_avila') if 'veracruz_avila' in ids else 0,
                format_func=lambda value: catalog.set_index('stadium_id').loc[value, 'estadio'])
        else:
            selected = st.selectbox("Altitud del lugar", ["No Altitude", "Medium Altitude", "Extreme Altitude"],
                format_func=lambda value: {"No Altitude": "Baja", "Medium Altitude": "Media", "Extreme Altitude": "Alta"}[value])
        st.markdown('<p class="scenario-help">Usaremos las mediciones del ejemplo. Si tienes las de tu lanzamiento, puedes agregarlas aquí.</p>', unsafe_allow_html=True)
        with st.expander("Agregar mis mediciones · Opcional"):
            st.write("Cambia solo los datos que conozcas. Los demás conservarán los valores del ejemplo.")
            for key, label in [("RelSpeed", "Velocidad de la pelota (millas por hora)"),
                ("InducedVertBreak", "Movimiento vertical (pulgadas)"),
                ("HorzBreak", "Movimiento lateral (pulgadas)"),
                ("SpinRate", "Giro de la pelota (vueltas por minuto)")]:
                value = row[key]
                row[key] = st.number_input(label, value=float(value) if value is not None else None)
        submitted = st.form_submit_button("Ver evaluación del lanzamiento", type="primary", use_container_width=True)
        st.markdown('<p class="scenario-result-hint">El resultado aparecerá debajo del simulador.</p>', unsafe_allow_html=True)

    identity = (str(output), pitch, hand)
    if submitted:
        missing = [key for key in profile["median"] if row.get(key) is None]
        if missing:
            st.warning("Faltan mediciones para este ejemplo. Prueba con otro tipo de lanzamiento o completa los datos en el análisis detallado.")
            st.session_state.pop("start_result", None)
        else:
            if stadium_context:
                scenarios = stadium_scenarios(row, catalog, [selected, reference_place])
                place = scenarios.stadium.iloc[0]
            else:
                scenarios = pd.DataFrame([{**row, "altitude_category": selected}])
                place = {"No Altitude": "Altitud baja", "Medium Altitude": "Altitud media", "Extreme Altitude": "Altitud alta"}[selected]
            with st.spinner("Preparando tu evaluación…"):
                from precision_model import infer_dashboard
                predicted = infer_dashboard(scenarios, bundle, output)
            outside = any(profile["p01"].get(key) is not None and
                not profile["p01"][key] <= row[key] <= profile["p99"][key] for key in profile["median"])
            st.session_state.start_result = (identity, predicted.iloc[0].to_dict(), place, outside)
            st.session_state['start_comparison'] = (identity, predicted.iloc[1].to_dict(), scenarios.stadium.iloc[1]) if stadium_context else None

    from dashboard_pitch_animation import render_pitch_animation
    with visual_panel, st.container(key="start-visual"):
        render_pitch_animation(pitch, hand, row)

    saved = st.session_state.get("start_result")
    if saved and saved[0] == identity:
        _, result, place, outside = saved
        with st.container(border=True, key="start-result-card"):
            st.markdown('<div class="pitch-card-heading"><span>03</span><h3>Tu evaluación</h3></div>', unsafe_allow_html=True)
            st.write(f"**{PITCH_NAMES.get(pitch, pitch)} · {HANDS.get(hand, hand)} · {place}**")
            st.markdown('<div class="evaluation-status">Resultado del último envío. Si cambias datos, pulsa «Ver evaluación» para actualizarlo.</div>', unsafe_allow_html=True)
            score = result["pitching_plus"]
            score_panel, reading_panel = st.columns([1, 2], gap='large', vertical_alignment='center')
            with score_panel:
                st.metric("Evaluación general", f"{score:.1f} puntos")
            with reading_panel:
                if abs(score - 100) < .05:
                    st.write("La evaluación coincide con la referencia histórica: **100 puntos**.")
                else:
                    direction = "por encima" if score > 100 else "por debajo"
                    st.write(f"Este ejemplo está **{abs(score - 100):.1f} puntos {direction}** de la referencia histórica de 100. Una puntuación mayor indica una evaluación más favorable.")
                st.write("Los puntos sirven para comparar lanzamientos. No son un porcentaje de éxito.")
            comparison = st.session_state.get('start_comparison')
            if comparison and comparison[0] == identity:
                from dashboard_decisiones import render_comparison
                render_comparison(result, comparison[1], place, comparison[2])
            if outside:
                st.warning("Alguna medición es poco habitual para este lanzamiento. Interpreta el resultado con cautela y revisa los datos introducidos.")
            if not meta["reference"]["pitching_plus"]["informative"]:
                st.info("Esta referencia es constante: no permite distinguir entre lanzamientos.")
            with st.expander("Ver qué significa cada resultado"):
                st.metric("Calidad física (Stuff+)", f"{result['stuff_plus']:.1f}")
                st.write("Resume la velocidad, el giro y el movimiento de la pelota.")
                st.metric("Ubicación (Location+)", f"{result['location_plus']:.1f}")
                st.write("En este ejemplo usamos una pelota al centro del plato, a 2.5 pies de altura, con conteo de 0 bolas y 0 strikes y bateador derecho. Puedes cambiar este contexto en «Comparar estadios».")
                st.write("La evaluación general (Pitching+) reúne la calidad física y el contexto disponible. Este ejemplo no utiliza el historial de un lanzador concreto.")
            st.info("Úsalo como apoyo para revisar con el coach y el video. La estimación no garantiza el resultado del próximo lanzamiento.")
    else:
        with st.container(border=True, key='start-empty-result'):
            st.markdown('<div class="pitch-card-heading"><span>03</span><h3>Tu evaluación aparecerá aquí</h3></div>', unsafe_allow_html=True)
            st.write('Revisa el lanzamiento y el estadio, y pulsa **Ver evaluación del lanzamiento** para obtener el resultado.')


    st.markdown('''<div class="reading-strip"><span>LEE EL LANZAMIENTO EN TRES PARTES</span><div><b>Stuff+</b><p>La calidad física de la pelota.</p></div><div><b>Location+</b><p>El lugar donde llega al plato.</p></div><div><b>Pitching+</b><p>Su evaluación combinada.</p></div></div>''', unsafe_allow_html=True)
    from dashboard_decisiones import render_paths
    render_paths()
    st.button("Ver la guía de resultados →", on_click=open_view, args=('Entender el proyecto',), use_container_width=True)
    st.markdown('<footer class="editorial-footer"><b>DIABLOS · ANÁLISIS DE PITCHEO</b><span>LMB · ISAC 2026 · Una herramienta de apoyo para el criterio deportivo.</span></footer>', unsafe_allow_html=True)
