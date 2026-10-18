"""Interfaz v6: modelos seleccionados antes de evaluar el benchmark 2026."""
from pathlib import Path

import pandas as pd
import streamlit as st

MODEL_VERSION = globals().get("MODEL_VERSION", 6)
if MODEL_VERSION == 8:
    from entrenar_stuff_plus_v8 import infer, load_bundle
elif MODEL_VERSION == 7:
    from entrenar_stuff_plus_v7 import infer, load_bundle
else:
    from entrenar_stuff_plus_v6 import infer, load_bundle

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / f"stuff_plus_output_v{MODEL_VERSION}"
st.set_page_config(page_title=f"Stuff+ v{MODEL_VERSION}", layout="wide")
st.title(f"Stuff+ v{MODEL_VERSION} · Diablos")
st.caption("100 representa la referencia histórica guardada. La ubicación y el resultado observado no entran al modelo físico de Stuff+.")
if not (OUTPUT / "bundle.json").exists():
    st.info("Primero ejecuta entrenar_stuff_plus_v6.py y verifica sus artefactos.")
    st.stop()


@st.cache_resource
def get_bundle(path):
    return load_bundle(path)


bundle = get_bundle(str(OUTPUT))
profile = bundle[2][2][1][0]["profile"] if MODEL_VERSION == 8 else (bundle[2][1][0]["profile"] if MODEL_VERSION == 7 else bundle[1][0]["profile"])
if MODEL_VERSION == 8:
    selected = [name for name, item in bundle[0]["selection"].items() if item["promoted"]]
    st.caption(f"v8: velocidad y familias. Cambios aceptados: {', '.join(selected) or 'ninguno'}. Selección con juegos de 2024–2025; 2026 es un benchmark reutilizado.")
elif MODEL_VERSION == 7:
    methods = ", ".join(f"{name}: {item['selected']}" for name, item in bundle[0]["calibrations"].items())
    status = "compuesto OOF seleccionado" if bundle[0]["stack"]["chosen"]["promoted"] else "índices del modelo anterior conservados"
    st.caption(f"Selección con juegos separados de 2024–2025; 2026 es un benchmark reutilizado. {methods}; {status}. Pitching+ conserva v6.")
else:
    st.caption("Entrenamiento con datos anteriores a 2026. Las alternativas se eligieron con 2025; 2026 es un benchmark reutilizado tras v5.")
tab_sim, tab_rank = st.tabs(["Simular lanzamiento", "Arsenal con incertidumbre"])
with tab_sim:
    c1, c2, c3 = st.columns(3)
    with c1:
        velo = st.number_input("Velocidad en release (mph)", 60., 110., 92.)
        effective = st.number_input("Velocidad efectiva (mph)", 60., 115., 92.)
        spin = st.number_input("Spin (rpm)", 0., 4000., 2200.)
        axis = st.number_input("Eje de spin (grados)", 0., 360., 180.)
        pitch_type = st.selectbox("Tipo", ["Four-Seam", "Sinker", "Slider", "Changeup", "Curveball", "Cutter", "Splitter", "Sweeper", "Other"])
        throws = st.selectbox("Mano del pitcher", ["Right", "Left"])
    with c2:
        ivb = st.number_input("IVB (pulgadas)", -60., 60., 14.)
        hb = st.number_input("Movimiento horizontal (pulgadas)", -60., 60., 10.)
        vb = st.number_input("Break vertical total (pulgadas)", -100., 60., -15.)
        extension = st.number_input("Extensión (pies)", 2., 9., 6.)
        height = st.number_input("Altura de release (pies)", 2., 9., 5.8)
        side = st.number_input("Lado de release (pies)", -5., 5., .5)
    with c3:
        plate_height = st.number_input("Altura en plato (pies)", 0., 7., 2.5)
        plate_side = st.number_input("Lado en plato (pies)", -4., 4., 0.)
        balls = st.number_input("Bolas", 0, 3, 0)
        strikes = st.number_input("Strikes", 0, 2, 0)
        batter = st.selectbox("Lado del bateador", ["Right", "Left"])
        altitude = st.selectbox("Categoría de altitud", ["No Altitude", "Medium Altitude", "Extreme Altitude"])
    known = sorted({r["pitcher_anon_id"] for r in profile["fastballs"]})
    pitcher = st.selectbox("Perfil histórico de arsenal", ["Sin historial", *known])
    row = dict(PitchUID="simulation", pitcher_anon_id=pitcher, AutoPitchType=pitch_type,
               PitcherThrows=throws, BatterSide=batter, RelSpeed=velo, EffectiveVelo=effective,
               SpinRate=spin, SpinAxis=axis, InducedVertBreak=ivb, HorzBreak=hb, VertBreak=vb,
               Extension=extension, RelHeight=height, RelSide=side, PlateLocHeight=plate_height,
               PlateLocSide=plate_side, Balls=balls, Strikes=strikes, altitude_category=altitude)
    if st.checkbox("Dispongo de movimiento y aceleraciones adicionales"):
        with st.expander("Mediciones adicionales", expanded=True):
            st.caption("Usa mediciones del mismo pitch. Los valores iniciales son ilustrativos; no se estiman automáticamente desde IVB/HB.")
            columns = st.columns(4)
            inputs = [("pfxx", "pfxx (pulgadas)", -5.), ("pfxz", "pfxz (pulgadas)", 8.),
                      ("vx0", "vx0 (pies/s)", 4.), ("vy0", "vy0 (pies/s)", -132.),
                      ("vz0", "vz0 (pies/s)", -4.), ("ax0", "ax0 (pies/s²)", -5.),
                      ("ay0", "ay0 (pies/s²)", 24.), ("az0", "az0 (pies/s²)", -23.)]
            for i, (key, label, value) in enumerate(inputs):
                row[key] = columns[i % 4].number_input(label, value=value)
            if MODEL_VERSION == 8:
                row["ZoneSpeed"] = columns[0].number_input("Velocidad en plato (mph)", value=85.)
                row["SpeedDrop"] = columns[1].number_input("Pérdida de velocidad (mph)", value=7.)
                row["ZoneTime"] = columns[2].number_input("Tiempo hasta el plato (s)", value=.40)
    result = infer(pd.DataFrame([row]), bundle).iloc[0]
    if MODEL_VERSION == 8 and not result["v8_available"] and result["score_reference_id"] != "v5_fallback":
        st.info("Faltan mediciones válidas de velocidad o trayectoria para v8: se utiliza el respaldo v7.")
    if result["score_reference_id"] == "v5_fallback":
        st.info("Faltan mediciones físicas adicionales válidas: los índices conservan el modelo y la referencia de v5. La predicción contextual se calcula por separado.")
    for col, name in zip(st.columns(3), ["stuff_plus", "location_plus", "pitching_plus"]):
        col.metric(name.replace("_plus", "+").title(), f"{result[name]:.1f}")
    st.caption("Location+ mide la contribución predictiva de ubicación y contexto; Pitching+ incluye además el bucket de altitud. El valor de carreras sigue siendo un proxy de pesos fijos.")
    physical_col, contextual_col = st.columns(2)
    physical_col.metric("Velocidad de salida física, dado contacto", f"{result['pred_exit_speed_given_in_play']:.1f} mph")
    contextual_col.metric("Velocidad de salida con ubicación, dado contacto", f"{result['pred_exit_speed_contextual']:.1f} mph")
    st.caption("La segunda estimación conoce ubicación, conteo y lado del bateador. No participa en Stuff+ y no es directamente comparable con una predicción solo física.")
    st.dataframe(pd.DataFrame({"Predicción": ["Whiff por pitch", "Whiff dado swing", "Bola en juego", "Jonrón por pitch"],
                               "Probabilidad": [result[c] for c in ["p_whiff", "p_whiff_given_swing", "p_ball_in_play", "p_home_run_per_pitch"]]}), hide_index=True)
    st.caption("Las categorías de altitud no identifican estadios. Cambiarlas no simula automáticamente el cambio físico ni estima un efecto causal.")
with tab_rank:
    path = OUTPUT / "arsenal_con_incertidumbre.csv"
    if not path.exists():
        st.info("Ejecuta reportar_mejora_v6.py para generar los rankings.")
    else:
        ranking = pd.read_csv(path)
        if st.checkbox("Solo muestras de al menos 100 pitches y cinco juegos", value=True):
            ranking = ranking.loc[ranking.ranking_eligible]
        order = st.selectbox("Ordenar arsenal por", ["Stuff+ regularizado", "Whiff dado swing"])
        sort_column = "stuff_plus_shrunk" if order == "Stuff+ regularizado" else "p_whiff_given_swing"
        ranking = ranking.sort_values(["ranking_eligible", sort_column], ascending=[False, False])
        labels = {"pitcher_anon_id": "Pitcher", "AutoPitchType": "Tipo", "n_pitches": "Lanzamientos",
                  "n_games": "Juegos", "stuff_plus_raw": "Stuff+ medio", "stuff_plus_shrunk": "Stuff+ regularizado",
                  "raw_mean_ci95_low": "IC 95% media: inferior", "raw_mean_ci95_high": "IC 95% media: superior",
                  "location_plus": "Location+", "pitching_plus": "Pitching+", "p_whiff_given_swing": "P(whiff dado swing)",
                  "pred_exit_speed_given_in_play": "Salida física (mph)", "pred_exit_speed_contextual": "Salida contextual (mph)",
                  "ranking_eligible": "Cumple mínimo de muestra"}
        st.dataframe(ranking[list(labels)].rename(columns=labels), hide_index=True)
        st.caption("Stuff+ se regulariza hacia la media de temporada con un peso fijo de 100 pitches. Los intervalos corresponden al Stuff+ medio sin regularizar, mediante remuestreo de juegos; no miden incertidumbre sobre talento real ni parámetros del modelo. Whiff dado swing se muestra como probabilidad, sin reinterpretarlo como índice de carreras.")
if MODEL_VERSION == 7 and (OUTPUT / "calibracion_whiff.png").exists():
    with st.expander("Validación de calibración en el benchmark reutilizado 2026"):
        st.image(str(OUTPUT / "calibracion_whiff.png"))
        st.caption("Compara probabilidades del mismo núcleo antes y después de calibrar. Esta temporada no se usó para seleccionar calibradores ni pesos.")
if MODEL_VERSION == 8 and (OUTPUT / "comparacion_v8.png").exists():
    with st.expander("Comparación v7 → v8 en el benchmark reutilizado 2026"):
        st.image(str(OUTPUT / "comparacion_v8.png"))
        st.caption("Los intervalos remuestrean juegos. Un valor positivo indica menor error; la selección se fijó antes de esta evaluación.")
if MODEL_VERSION == 8:
    from dashboard_entrega_v8 import render
    render(row, bundle)
