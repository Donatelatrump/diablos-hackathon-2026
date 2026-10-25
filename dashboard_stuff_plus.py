"""Entry point: walkthrough, local v9 experiment and archived v8 delivery."""
from pathlib import Path
import runpy
import streamlit as st
from proyecto_io import bundle_ready
from dashboard_guia import render_guide

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Diablos · Calidad de pitcheo", page_icon="⚾", layout="wide")
st.sidebar.title("Diablos · Stuff+")
view = st.sidebar.radio("Ir a", ["Entender el proyecto", "Simular y comparar v9", "Entrega histórica v8"])
st.sidebar.caption("ISAC 2026 · Calidad de pitcheo en el entorno LMB")
if view == "Entender el proyecto":
    render_guide(ROOT)
elif view == "Simular y comparar v9":
    incremental = ROOT / "stuff_plus_output_v9_incremental"
    if bundle_ready(ROOT / "stuff_plus_output_v9") or (bundle_ready(incremental) and (incremental / "metricas.json").exists()):
        from dashboard_stuff_plus_v9 import render
        runs = {}
        if bundle_ready(ROOT / "stuff_plus_output_v9"):
            runs["v9 original"] = ROOT / "stuff_plus_output_v9"
        if bundle_ready(incremental) and (incremental / "metricas.json").exists():
            runs["v9 con validación incremental"] = incremental
        selected = st.sidebar.selectbox("Experimento", list(runs), index=len(runs)-1)
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
