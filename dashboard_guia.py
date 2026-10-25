"""A project walkthrough that works even without model binaries."""
import json
import pandas as pd
import streamlit as st


def render_guide(root):
    st.title("¿Qué tan bueno es este lanzamiento?")
    st.write("Evaluamos sus características físicas, dónde llega al plato y cómo encaja en el arsenal y el entorno. El resultado ayuda a comparar perfiles y a preparar una revisión de scouting.")
    tabs = st.tabs(["En dos minutos", "El reto y su alcance", "Evidencia", "Reproducir"])
    with tabs[0]:
        for col, title, question in zip(st.columns(3), ["1 · Stuff+", "2 · Location+", "3 · Pitching+"],
                ["¿Qué calidad tiene por su física?", "¿Cuánto aporta su ubicación y conteo?", "¿Qué calidad esperamos con arsenal y entorno?"]):
            with col:
                st.subheader(title)
                st.write(question)
        st.info("100 es la referencia histórica. 110 significa una desviación estándar por encima de esa referencia; no significa 10% más outs ni 10% menos carreras.")
        score = st.slider("Explora la escala del índice", 70, 130, 110, 1)
        st.metric("Índice de ejemplo", score, f"{(score-100)/10:+.1f} desviaciones estándar", delta_color="off")
        st.caption("Ejemplo educativo de la escala. No es una predicción de un lanzamiento.")
        st.markdown("**De los datos a una decisión**\n\nMediciones del pitch → modelos entrenados con juegos anteriores → valor esperado → índice de referencia → comparación de perfiles → revisión con el coach.")
        st.write("Un buen score físico puede coexistir con una mala ubicación. Revisa ambos antes de interpretar el índice combinado. Un pitcher nuevo puede recibir predicciones físicas; su arsenal se marca sin historial.")
        with st.expander("¿Por qué una capa puede conservar el modelo anterior?"):
            st.write("En el experimento incremental, arsenal debe mejorar la predicción de ubicación y entorno debe mejorar la capa anterior. Si no superan la validación por juegos, conservamos la predicción más simple. Un delta de altitud igual a cero significa que no se confirmó información predictiva adicional; no significa que la altitud carezca de efecto físico.")
        with st.expander("Diccionario rápido"):
            st.dataframe(pd.DataFrame([
                ["IVB / HB", "Movimiento vertical inducido / horizontal, en pulgadas."],
                ["Whiff", "Swing y fallo. El dataset lo distingue del foul."],
                ["P(rodado | contacto)", "Probabilidad entre bolas en juego; no entre todos los pitches."],
                ["Calibración", "Si el modelo dice 20%, esperamos cerca de 20 eventos en 100 casos semejantes."],
                ["xRunValue proxy", "Promedio esperado de pesos por resultado; menor favorece al pitcher."],
                ["Holdout", "Grupo de datos excluido del entrenamiento para evaluar generalización."],
            ], columns=["Término", "Significado"]), hide_index=True, width="stretch")
    with tabs[1]:
        st.write("El HTML local asigna 25% a cada criterio de evaluación.")
        st.dataframe(pd.DataFrame([
            ["Calidad · 25%", "RMSE, Brier, calibración y baseline por conteo", "Evaluación v9 y métricas históricas v8"],
            ["Robustez · 25%", "Temporada, pitchers nuevos y parque", "Modos por temporada, pitcher y entorno; parque necesita stadium"],
            ["Arsenal + altitud · 25%", "Diferenciales y comparación entre entornos", "Historia previa, cuatro capas y ablaciones pareadas"],
            ["Uso real · 25%", "Scores, perfil, recomendaciones, simulador, documento de 6–10 páginas", "Guía, simulador y entrega histórica disponibles"],
        ], columns=["Criterio", "Qué pide", "Implementación"]), hide_index=True, width="stretch")
        st.warning("El dataset identifica categorías de altitud, pero no identifica Harp Helú. Una comparación entre categorías no demuestra un efecto causal ni constituye una validación por estadio.")
        st.write("El reto permite usar los datos para la competencia y presentar resultados, pero no publicar el dataset. El análisis es deportivo. El HTML fija la entrega el 22 de octubre de 2026 y equipos de 2–4 estudiantes.")
        st.caption("Fuente: HTML ISAC guardado en este repositorio. La guía completa documenta entregables, límites y definiciones.")
    with tabs[2]:
        comparison = root / "reports/v9_incremental/comparacion.json"
        if comparison.exists():
            st.subheader("¿Qué cambió con la validación incremental?")
            changes = json.loads(comparison.read_text())
            st.dataframe(pd.DataFrame([{"Capa": r["task"], "RMSE original": r["rmse_original"],
                "RMSE incremental": r["rmse_incremental"], "Reducción MSE (%)": 100*r["gain"],
                "IC 95% inferior (%)": 100*r["ci_low"], "IC 95% superior (%)": 100*r["ci_high"]}
                for r in changes]), hide_index=True, width="stretch")
            st.caption("Mismos pitches y presupuesto de entrenamiento. Menor RMSE es mejor. El benchmark 2026 ya se había inspeccionado: esta comparación no sustituye una temporada nueva.")
        path = root / "stuff_plus_output_v9" / "metricas.json"
        if path.exists():
            records = json.loads(path.read_text())
            st.subheader("Experimento v9 · benchmark 2026 reutilizado")
            st.dataframe(pd.DataFrame([{
                "Tarea": r["task"], "Pitches evaluados": r["n"], "RMSE": r["metrics"].get("rmse"),
                "Brier": r["metrics"].get("brier"), "Mejora vs baseline (%)": 100*r["vs_baseline"]["gain"] if r["vs_baseline"]["gain"] is not None else None,
            } for r in records if "metrics" in r]), hide_index=True, width="stretch")
            st.caption("Menor RMSE/Brier es mejor. La mejora se calcula sobre MSE/Brier; el baseline contextual de carreras conoce el conteo. Las probabilidades v9 incorporan contexto y tienen un alcance distinto de las probabilidades físicas v8.")
        else:
            st.info("v9 todavía no tiene resultados locales de evaluación. Entrenar y evaluar genera la tabla; la existencia del código no demuestra una mejora de precisión.")
        historical_path = root / "stuff_plus_output_v8/metricas.json"
        historical = json.loads(historical_path.read_text()) if historical_path.exists() else []
        with st.expander("Resultados guardados de v8"):
            st.dataframe(pd.DataFrame([{"Tarea": r["task"], "n": r["n"],
                "AUC v8": r["v8"].get("roc_auc"), "Brier v8": r["v8"].get("brier"),
                "RMSE v8": r["v8"].get("rmse"), "Mejora MSE/Brier vs v7 (%)": 100*r["bootstrap"]["relative_mse_reduction"]
            } for r in historical]), hide_index=True, width="stretch")
            st.caption("v8 mejoró whiff y bola en juego, pero conservó el modelo físico de carreras. 2026 ya se había usado durante versiones anteriores.")
    with tabs[3]:
        st.code("python -m venv .venv\nsource .venv/bin/activate\npython -m pip install -r requirements-entrega.txt\npython -m unittest test_stuff_plus_v9 -v\npython entrenar_stuff_plus_v9.py --incremental-gate --iteraciones 300 --hilos 3 --salida stuff_plus_output_v9_incremental\npython -m streamlit run dashboard_stuff_plus.py", language="bash")
        st.write("El cargador busca primero Data/stuff_model_df.parquet. Los modelos v9 son independientes de los bundles v5–v8. En Windows, activa el entorno con .venv\\Scripts\\Activate.ps1.")
        guide = root / "GUIA_PROYECTO.md"
        if guide.exists():
            st.download_button("Descargar la guía completa", guide.read_bytes(), guide.name, "text/markdown")
        approach = root / "PROJECT_APPROACH.md"
        if approach.exists():
            st.download_button("Project walkthrough (English)", approach.read_bytes(), approach.name, "text/markdown")
        document = root / "reports/v9/DOCUMENTO_TECNICO_V9.pdf"
        if document.exists():
            st.download_button("Documento técnico v9 · 8 páginas", document.read_bytes(), document.name, "application/pdf")
