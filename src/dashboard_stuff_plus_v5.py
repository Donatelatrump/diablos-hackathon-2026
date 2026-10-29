"""Interfaz del modelo evaluado: streamlit run src/dashboard_stuff_plus_v5.py."""
from pathlib import Path

import pandas as pd
import streamlit as st

from entrenar_stuff_plus_v5 import infer, load_bundle

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "stuff_plus_output_v5"
st.set_page_config(page_title="Stuff+ v5", layout="wide")
st.title("Stuff+ v5 · Diablos")
st.caption("Predicciones CatBoost del modelo evaluado. 100 representa la referencia histórica guardada; 10 puntos equivalen a una desviación de esa referencia.")


@st.cache_resource
def bundle(path):
    return load_bundle(path)


available = sorted(p for p in OUTPUT.glob("holdout_*") if (p / "bundle.json").exists())
if not available:
    st.info("Primero ejecuta entrenar_stuff_plus_v5.py para generar los modelos.")
    st.stop()
selected = st.sidebar.selectbox("Modelo evaluado", available, index=len(available) - 1, format_func=lambda p: p.name)
model_bundle = bundle(str(selected))
metadata = model_bundle[0]
st.caption(f"Temporadas de entrenamiento hasta {metadata['training_max_year']}; evaluación temporal {metadata['test_year']}. El modelo conserva los datos de evaluación fuera del entrenamiento.")

tab_sim, tab_rank = st.tabs(["Simular lanzamiento", "Arsenal observado"])
with tab_sim:
    st.write("Introduce las mediciones físicas del lanzamiento y su ubicación. La categoría de altitud es la del dataset; no identifica un estadio concreto.")
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
    known = sorted({r["pitcher_anon_id"] for r in metadata["profile"]["fastballs"]})
    pitcher = st.selectbox("Perfil histórico de arsenal", ["Sin historial", *known])
    row = pd.DataFrame([dict(PitchUID="simulation", pitcher_anon_id=pitcher,
        AutoPitchType=pitch_type, PitcherThrows=throws, BatterSide=batter,
        RelSpeed=velo, EffectiveVelo=effective, SpinRate=spin, SpinAxis=axis,
        InducedVertBreak=ivb, HorzBreak=hb, VertBreak=vb, Extension=extension,
        RelHeight=height, RelSide=side, PlateLocHeight=plate_height,
        PlateLocSide=plate_side, Balls=balls, Strikes=strikes, altitude_category=altitude)])
    result = infer(row, model_bundle).iloc[0]
    for col, name in zip(st.columns(3), ["stuff_plus", "location_plus", "pitching_plus"]):
        col.metric(name.replace("_plus", "+").title(), f"{result[name]:.1f}")
    st.caption("Stuff+ usa características físicas y arsenal. Location+ mide el cambio de valor al añadir ubicación y contexto. Pitching+ incorpora además el bucket de altitud. El valor de carreras es un proxy de pesos lineales, no RE24.")
    st.write("Probabilidades por lanzamiento o condicionadas, según la etiqueta:")
    st.dataframe(pd.DataFrame({"Predicción": ["Whiff por pitch", "Whiff dado swing", "Bola en juego", "Rodado dado bola en juego", "Contacto fuerte dado bola en juego", "Jonrón por pitch"],
                               "Probabilidad": [result[k] for k in ["p_whiff", "p_whiff_given_swing", "p_ball_in_play", "p_groundball_given_in_play", "p_barrel_or_hard_contact", "p_home_run_per_pitch"]]}), hide_index=True)
    st.caption("Cambiar altitud manteniendo las mediciones fijas es una consulta predictiva al modelo. No simula el cambio físico del movimiento ni estima un efecto causal de trasladar el pitch.")

with tab_rank:
    path = OUTPUT / "arsenal_por_temporada.csv"
    if path.exists():
        ranking = pd.read_csv(path)
        year = st.selectbox("Temporada observada", sorted(ranking.year.unique()), index=len(ranking.year.unique()) - 1)
        minimum = st.number_input("Mínimo de lanzamientos por tipo", 1, 10000, 100)
        st.dataframe(ranking.loc[ranking.year.eq(year) & ranking.n_pitches.ge(minimum)].sort_values("stuff_plus", ascending=False), hide_index=True)
        st.caption("Ranking descriptivo fuera de muestra. Una muestra pequeña puede producir posiciones inestables; el umbral no equivale a un intervalo de confianza.")
