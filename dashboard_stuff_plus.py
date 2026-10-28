"""Entry point: walkthrough, local v9 experiment and archived v8 delivery."""
from pathlib import Path
import runpy
import streamlit as st
from proyecto_io import bundle_ready
from dashboard_guia import render_guide
from dashboard_style import apply_dashboard_style

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Diablos · Calidad de pitcheo", page_icon="⚾", layout="wide")
apply_dashboard_style()

# Sidebar
with st.sidebar:
    st.markdown("### Diablos · Stuff+")
    st.caption("Guía: conoce las estadísticas. Simulador: prueba un lanzamiento; puedes dejar las opciones avanzadas sin tocar.")
    view = st.radio(
        "Ir a",
        ["Entender el proyecto", "Simular y comparar v9", "Entrega histórica v8"],
        label_visibility="collapsed",
        format_func=lambda value: {"Entender el proyecto": "Cómo interpretar los resultados", "Simular y comparar v9": "Comparar un lanzamiento", "Entrega histórica v8": "Resultados anteriores"}[value],
    )
    
    st.markdown('<div class="sidebar-section">Sobre el proyecto</div>', unsafe_allow_html=True)
    st.caption(
        "Este dashboard implementa el reto **2026 ISAC Hackathon – Diablos Rojos**. "
        "Evalúa la calidad del pitcheo mediante tres índices: Stuff+, Location+ y Pitching+."
    )
    
    with st.expander("Guías y documentación"):
        for title, relative in [("Guía de revisión para Harp", "reports/v9_estadios/RECOMENDACIONES_ACTUALES.md"),
                                ("Documento técnico actualizado", "reports/v9_estadios/DOCUMENTO_TECNICO_ESTADIOS.pdf")]:
            document = ROOT / relative
            if document.exists():
                st.download_button(title, document.read_bytes(), document.name, key='sidebar-'+document.stem)

if view == "Entender el proyecto":
    render_guide(ROOT)
elif view == "Simular y comparar v9":
    incremental = ROOT / "stuff_plus_output_v9_incremental"
    stadiums = ROOT / "stuff_plus_output_v9_estadios"
    stadiums_ready = bundle_ready(stadiums) and (stadiums / "estadios.csv").exists() and (stadiums / "metricas.json").exists()
    if stadiums_ready or bundle_ready(ROOT / "stuff_plus_output_v9") or (bundle_ready(incremental) and (incremental / "metricas.json").exists()):
        from dashboard_stuff_plus_v9 import render
        runs = {}
        if bundle_ready(ROOT / "stuff_plus_output_v9"):
            runs["v9 original"] = ROOT / "stuff_plus_output_v9"
        if bundle_ready(incremental) and (incremental / "metricas.json").exists():
            runs["v9 con validación incremental"] = incremental
        if stadiums_ready:
            runs["v9 por estadios · Harp Helú"] = stadiums
        with st.sidebar.expander("Versión de los resultados", expanded=False):
            selected = st.selectbox("Experimento", list(runs), index=len(runs)-1,
                format_func=lambda value: "Modelo actual por estadios" if value == "v9 por estadios · Harp Helú" else value,
                label_visibility="collapsed")
            st.caption("La versión actual está seleccionada. No necesitas cambiar esta opción.")
        render(runs[selected])
    else:
        st.title("Preparar el simulador")
        st.info("La guía y los resultados históricos están disponibles. Para simular v9, entrena sus modelos con el parquet local.")
        st.code("python entrenar_stuff_plus_v9.py --parquet Data/stuff_model_df.parquet --hilos 3")
else:
    if bundle_ready(ROOT / "stuff_plus_output_v8"):
        runpy.run_path(str(ROOT / "dashboard_stuff_plus_v8.py"), run_name="__main__")
    else:
        st.title("Entrega histórica v8")
        st.info("Los modelos v8 son punteros Git LFS en este checkout. Los documentos y métricas guardadas sí pueden consultarse.")
        for name in ["DOCUMENTO_TECNICO_V8.pdf", "RECOMENDACIONES_V8.md", "README_ENTREGA.md"]:
            path = ROOT / "entrega_v8" / name
            if path.exists():
                st.download_button(name, path.read_bytes(), name)
        st.caption("Recuperación de modelos originales: git lfs pull desde una cuenta con acceso al repositorio.")
