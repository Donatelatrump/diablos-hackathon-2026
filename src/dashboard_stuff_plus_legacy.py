"""Dashboard simulador Stuff+ para Diablos Rojos (ISAC Hackathon 2026).

Permite al pitching coach:
1. Ingresar características físicas de un pitch y obtener Stuff+/Location+/Pitching+ estimado.
2. Comparar el mismo pitch en Harp Helú (CDMX) vs. estadio a nivel del mar.
3. Ver ranking de pitchers y efecto de altitud.

Requisitos:
    pip install streamlit pandas pyarrow plotly

Ejecución:
    streamlit run app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Stuff+ Simulador - Diablos Rojos",
    page_icon="⚾",
    layout="wide",
)

SALIDA = Path("stuff_plus_output_v3")


# =============================================================================
# CARGA DE DATOS
# =============================================================================

@st.cache_data
def cargar_scores():
    ruta = SALIDA / "scores_pitch_v4_enriquecido.parquet"
    if ruta.exists():
        return pd.read_parquet(ruta)
    ruta2 = SALIDA / "scores_pitch_v4.parquet"
    if ruta2.exists():
        return pd.read_parquet(ruta2)
    ruta3 = SALIDA / "scores_pitch_v3_enriquecido.parquet"
    if ruta3.exists():
        return pd.read_parquet(ruta3)
    return None


@st.cache_data
def cargar_pitchers():
    ruta = SALIDA / "stuff_plus_por_pitcher.csv"
    if ruta.exists():
        return pd.read_csv(ruta)
    return None


@st.cache_data
def cargar_altitud():
    ruta = SALIDA / "stuff_plus_por_altitud.csv"
    if ruta.exists():
        return pd.read_csv(ruta)
    return None


@st.cache_data
def cargar_perfil():
    ruta = SALIDA / "perfil_ideal_diablos.json"
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    return None


# =============================================================================
# MODELO DE ESTIMACIÓN STUFF+ (heurístico basado en scores observados)
# =============================================================================

def estimar_stuff_plus(velo, spin, ivb, hb, extension, release_height, release_side,
                       pitch_type, pitcher_throws, batter_side, balls, strikes,
                       altitud_m, plato_height, plato_side):
    """Estimación heurística de Stuff+ basada en relaciones observadas en los datos.
    Este es un proxy para el modelo completo; sirve para el simulador del coach.
    """
    # Normalización básica (medidas aproximadas de la liga)
    velo_z = (velo - 90) / 5.0
    spin_z = (spin - 2200) / 200.0
    ivb_z = (ivb - 12) / 6.0
    hb_z = (hb - 10) / 8.0
    ext_z = (extension - 6.0) / 0.5

    # Puntaje base de "stuff físico"
    stuff_score = (
        0.30 * velo_z +
        0.15 * spin_z +
        0.25 * ivb_z +
        0.15 * hb_z +
        0.10 * ext_z
    )

    # Ajuste por altitud (efecto Harp Helú: menor movimiento en altitud)
    if altitud_m > 1500:
        # En altitud extrema, el movimiento se reduce ~20%
        stuff_score = 0.30 * velo_z + 0.15 * spin_z + 0.20 * ivb_z + 0.10 * hb_z + 0.10 * ext_z
        altitud_penalty = -1.5  # penalización leve por altitud
    else:
        altitud_penalty = 0.0

    # Ajuste por ubicación (plato)
    plato_score = 0.0
    if plato_height is not None:
        # Strike zone aprox: 1.5 a 3.5 pies de altura, -0.8 a 0.8 de lado
        dentro_zona = 1.5 <= plato_height <= 3.5 and abs(plato_side) <= 0.8
        if dentro_zona:
            plato_score += 0.5
        # Conteo favorable al pitcher
        if strikes >= 2:
            plato_score += 0.3
        if balls >= 3:
            plato_score -= 0.3

    # Ajuste por tipo de pitcheo (bonificaciones relativas)
    tipo_bonus = {
        "Four-Seam": 0.2,
        "Sinker": 0.1,
        "Slider": 0.3,
        "Curveball": 0.2,
        "Changeup": 0.25,
        "Splitter": 0.2,
        "Cutter": 0.15,
        "Sweeper": 0.25,
    }.get(pitch_type, 0.0)

    stuff_plus = 100 + 10 * (stuff_score + altitud_penalty + plato_score * 0.1 + tipo_bonus * 0.5)
    stuff_plus = max(60, min(140, stuff_plus))

    location_plus = 100 + 10 * (plato_score + altitud_penalty * 0.5)
    location_plus = max(60, min(140, location_plus))

    pitching_plus = (stuff_plus + location_plus) / 2

    return {
        "stuff_plus": round(stuff_plus, 1),
        "location_plus": round(location_plus, 1),
        "pitching_plus": round(pitching_plus, 1),
    }


# =============================================================================
# INTERFAZ
# =============================================================================

st.title("⚾ Stuff+ Simulador - Diablos Rojos")
st.markdown("""
**Sistema de evaluación pitch-by-pitch calibrado para la altitud de la LMB.**

Evalúe la calidad física de un lanzamiento (Stuff+), su ubicación (Location+) y la combinación (Pitching+),
comparando el comportamiento en el Estadio Alfredo Harp Helú (CDMX, ~2,240 msnm) frente a un estadio a
nivel del mar.
""")

df = cargar_scores()
pitchers_df = cargar_pitchers()
altitud_df = cargar_altitud()
perfil = cargar_perfil()

# --- Sidebar: entrada del coach ---
st.sidebar.header("1. Características del pitch")

st.sidebar.subheader("Físicas del release")
velo = st.sidebar.number_input("Velocidad de salida (mph)", min_value=70.0, max_value=105.0, value=92.0, step=0.5)
spin = st.sidebar.number_input("Spin rate (rpm)", min_value=1000, max_value=3500, value=2200, step=50)
ivb = st.sidebar.number_input("IVB (pulgadas)", min_value=-20.0, max_value=30.0, value=14.0, step=1.0)
hb = st.sidebar.number_input("HB (pulgadas)", min_value=-20.0, max_value=30.0, value=10.0, step=1.0)
extension = st.sidebar.number_input("Extensión (ft)", min_value=5.0, max_value=7.5, value=6.0, step=0.1)
release_height = st.sidebar.number_input("Altura de release (ft)", min_value=4.5, max_value=7.0, value=5.8, step=0.1)
release_side = st.sidebar.number_input("Lado de release (ft)", min_value=-3.0, max_value=3.0, value=0.5, step=0.1)

st.sidebar.subheader("Contexto")
pitch_type = st.sidebar.selectbox(
    "Tipo de pitcheo",
    ["Four-Seam", "Sinker", "Cutter", "Changeup", "Splitter", "Slider", "Curveball", "Sweeper", "Other"],
    index=0,
)
pitcher_throws = st.sidebar.selectbox("Mano del lanzador", ["Right", "Left"], index=0)
batter_side = st.sidebar.selectbox("Lado del bateador", ["Right", "Left"], index=0)
balls = st.sidebar.number_input("Bolas", min_value=0, max_value=3, value=0)
strikes = st.sidebar.number_input("Strikes", min_value=0, max_value=2, value=0)

st.sidebar.subheader("Ubicación en plato")
plato_height = st.sidebar.number_input("Altura en plato (ft)", min_value=1.0, max_value=5.0, value=2.5, step=0.1)
plato_side = st.sidebar.number_input("Lado en plato (ft)", min_value=-1.5, max_value=1.5, value=0.0, step=0.1)

st.sidebar.subheader("Entorno")
altitud_opcion = st.sidebar.radio(
    "Estadio",
    ["Harp Helú (CDMX, ~2,240 m)", "Nivel del mar (~0-100 m)"],
    index=0,
)
altitud_m = 2240.0 if altitud_opcion.startswith("Harp") else 100.0

# --- Cálculo ---
resultado_mar = estimar_stuff_plus(
    velo, spin, ivb, hb, extension, release_height, release_side,
    pitch_type, pitcher_throws, batter_side, balls, strikes, 100.0,
    plato_height, plato_side,
)
resultado_cdmx = estimar_stuff_plus(
    velo, spin, ivb, hb, extension, release_height, release_side,
    pitch_type, pitcher_throws, batter_side, balls, strikes, 2240.0,
    plato_height, plato_side,
)

# --- Métricas principales ---
st.header("2. Scores estimados")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Stuff+ (físico)", f"{resultado_cdmx['stuff_plus']:.0f}",
              delta=f"{resultado_cdmx['stuff_plus'] - resultado_mar['stuff_plus']:+.1f} vs. nivel del mar")
with col2:
    st.metric("Location+ (ubicación)", f"{resultado_cdmx['location_plus']:.0f}",
              delta=f"{resultado_cdmx['location_plus'] - resultado_mar['location_plus']:+.1f}")
with col3:
    st.metric("Pitching+ (combinado)", f"{resultado_cdmx['pitching_plus']:.0f}",
              delta=f"{resultado_cdmx['pitching_plus'] - resultado_mar['pitching_plus']:+.1f}")

st.info(f"""
**Efecto de altitud (Harp Helú vs. nivel del mar):**
- Stuff+: {resultado_cdmx['stuff_plus'] - resultado_mar['stuff_plus']:+.1f} puntos
- Location+: {resultado_cdmx['location_plus'] - resultado_mar['location_plus']:+.1f} puntos
- Pitching+: {resultado_cdmx['pitching_plus'] - resultado_mar['pitching_plus']:+.1f} puntos

En altitud extrema, el movimiento de ruptura (IVB/HB) se reduce por la menor densidad del aire,
lo que afecta más a lanzamientos de movimiento (curveball, slider) que a rectas.
""")

# --- Comparación lado a lado ---
st.header("3. Comparación: Harp Helú vs. Nivel del mar")

fig_comp = go.Figure()
fig_comp.add_trace(go.Bar(
    x=["Stuff+", "Location+", "Pitching+"],
    y=[resultado_mar["stuff_plus"], resultado_mar["location_plus"], resultado_mar["pitching_plus"]],
    name="Nivel del mar",
    marker_color="#1f77b4",
))
fig_comp.add_trace(go.Bar(
    x=["Stuff+", "Location+", "Pitching+"],
    y=[resultado_cdmx["stuff_plus"], resultado_cdmx["location_plus"], resultado_cdmx["pitching_plus"]],
    name="Harp Helú (CDMX)",
    marker_color="#d62728",
))
fig_comp.update_layout(
    title="Scores por estadio",
    yaxis_title="Puntos (100 = promedio)",
    barmode="group",
    height=400,
)
st.plotly_chart(fig_comp, use_container_width=True)

# --- Ranking de pitchers ---
st.header("4. Ranking de pitchers (Stuff+ medio)")

if pitchers_df is not None:
    top_n = st.slider("Mostrar top N pitchers", 5, 30, 10)
    top_pitchers = pitchers_df.head(top_n)

    fig_rank = px.bar(
        top_pitchers.sort_values("stuff_plus_overall"),
        x="stuff_plus_overall",
        y="pitcher_anon_id",
        orientation="h",
        title=f"Top {top_n} pitchers por Stuff+ general",
        labels={"stuff_plus_overall": "Stuff+ medio", "pitcher_anon_id": "Pitcher"},
    )
    fig_rank.update_layout(height=400)
    st.plotly_chart(fig_rank, use_container_width=True)

    st.subheader("Detalle del ranking")
    st.dataframe(
        top_pitchers[["pitcher_anon_id", "total_pitches", "stuff_plus_overall",
                      "location_plus_overall", "pitching_plus_overall",
                      "delta_stuff_plus_extreme_vs_no_altitude", "arsenal_tipos"]],
        use_container_width=True,
    )
else:
    st.warning("No se encontró el archivo stuff_plus_por_pitcher.csv")

# --- Efecto por altitud ---
st.header("5. Efecto de altitud en la LMB")

if altitud_df is not None:
    fig_alt = px.bar(
        altitud_df.sort_values("stuff_plus_mean"),
        x="altitude_category",
        y="stuff_plus_mean",
        color="altitude_category",
        title="Stuff+ medio por categoría de altitud",
        labels={"stuff_plus_mean": "Stuff+ medio", "altitude_category": "Categoría de altitud"},
    )
    fig_alt.update_layout(height=400, showlegend=False)
    st.plotly_chart(fig_alt, use_container_width=True)

    st.dataframe(altitud_df, use_container_width=True)
else:
    st.warning("No se encontró stuff_plus_por_altitud.csv")

# --- Perfil ideal Diablos ---
st.header("6. Perfil físico ideal para Diablos Rojos (Harp Helú)")

if perfil:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Velo medio (top 10%)", f"{perfil.get('velocidad_media_elite_mph', 0):.1f} mph")
    with col2:
        st.metric("Spin medio (top 10%)", f"{perfil.get('spin_rate_media_elite_rpm', 0):.0f} rpm")
    with col3:
        st.metric("IVB medio (top 10%)", f"{perfil.get('ivb_media_elite_pulg', 0):.2f} in")
    with col4:
        st.metric("HB medio (top 10%)", f"{perfil.get('hb_media_elite_pulg', 0):.2f} in")

    st.markdown("**Tipos de pitcheo más efectivos en el top 10% de Stuff+ en Harp Helú:**")
    tipos = perfil.get("tipos_elite", {})
    if tipos:
        fig_tipos = px.bar(
            x=list(tipos.values()),
            y=list(tipos.keys()),
            orientation="h",
            title="Frecuencia de tipos en pitches élite (top 10% Stuff+)",
            labels={"x": "Nº de pitches", "y": "Tipo"},
        )
        fig_tipos.update_layout(height=300)
        st.plotly_chart(fig_tipos, use_container_width=True)

    st.markdown(f"""
    - **Umbral top 10% Stuff+ en Harp Helú:** {perfil.get('umbral_stuff_plus_top10', 0):.1f}
    - **Stuff+ medio elite:** {perfil.get('stuff_plus_medio_elite', 0):.1f}
    - **Stuff+ medio todos en Harp Helú:** {perfil.get('stuff_plus_medio_todos_harp', 0):.1f}
    - **Lanzadores diestros en elite:** {perfil.get('mano_lanzadora_elite', {}).get('Right', 0)} pitches
    - **Lanzadores zurdos en elite:** {perfil.get('mano_lanzadora_elite', {}).get('Left', 0)} pitches
    """)
else:
    st.warning("No se encontró perfil_ideal_diablos.json")

# --- Footer ---
st.markdown("---")
st.markdown("""
**Notas técnicas:**
- Los scores usan una escala "plus" donde 100 = promedio de la liga y ±10 = ±1 desviación estándar.
- Stuff+ evalúa únicamente propiedades físicas en el punto de release (velocidad, spin, movimiento, extensión).
- Location+ evalúa ubicación en plato, conteo y lado del bateador.
- Pitching+ = promedio de Stuff+ y Location+.
- El simulador es una heurística basada en los datos observados; para producción usar los modelos CatBoost entrenados (`modelos/*.cbm`).
""")

# =============================================================================
# SHAP POR ALTITUD (nuevo en v4)
# =============================================================================
st.header("7. Importancia de Features (SHAP) por Altitud")

shap_alt_path = SALIDA / "shap_by_altitude.csv"
shap_task_path = SALIDA / "shap_importance_task.csv"

if shap_alt_path.exists():
    shap_df = pd.read_csv(shap_alt_path)
    st.subheader("Comparación SHAP: Harp Helú (Extreme) vs. Nivel del mar (No Altitude)")
    # Tomar top 10 features por importancia media
    top_feats = (
        shap_df.groupby("feature")["mean_abs_shap"]
        .mean().sort_values(ascending=False).head(10).index.tolist()
    )
    shap_top = shap_df[shap_df["feature"].isin(top_feats)]
    fig_shap = px.bar(
        shap_top,
        x="mean_abs_shap",
        y="feature",
        color="altitud",
        orientation="h",
        title="Top 10 features por importancia SHAP (|SHAP| medio)",
        labels={"mean_abs_shap": "|SHAP| medio", "feature": "Feature", "altitud": "Altitud"},
    )
    fig_shap.update_layout(height=400, yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig_shap, use_container_width=True)

    st.subheader("Tabla SHAP por altitud")
    st.dataframe(shap_df, use_container_width=True)
else:
    st.warning("No se encontró shap_by_altitude.csv. Ejecutar completar_v4.py para generar SHAP.")

if shap_task_path.exists():
    st.subheader("Importancia SHAP por tarea")
    shap_task = pd.read_csv(shap_task_path)
    st.dataframe(shap_task, use_container_width=True)
