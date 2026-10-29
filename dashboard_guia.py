"""A project walkthrough that works even without model binaries."""
import json
from pathlib import Path
import pandas as pd
import streamlit as st


def render_guide(root: Path):
    st.title('Cómo leer tu evaluación')
    st.write('Empieza por estas respuestas. Más abajo encontrarás ejemplos y el detalle del proyecto.')
    for question, answer in [
        ('¿Qué significa el resultado?', 'Es una puntuación comparada con una referencia histórica de 100. Más alto indica una evaluación más favorable. No es un porcentaje de éxito.'),
        ('¿Qué datos puedo cambiar?', 'Puedes elegir tipo de lanzamiento, mano y estadio. Si tienes mediciones propias, añade velocidad, giro y movimiento. Los demás datos conservan los valores del ejemplo.'),
        ('¿Por qué a veces no cambia entre estadios?', 'El modelo conserva una estimación anterior cuando la capa de estadio no demuestra una mejora adicional. La comparación mantiene las mediciones físicas; no traslada el vuelo a otro aire.'),
        ('¿Qué representa la animación?', 'Ilustra el movimiento del lanzamiento elegido, amplificado para verlo mejor. El modo normal no cambia con el estadio. El laboratorio permite explorar una hipótesis de densidad con altitudes de origen y destino; no predice el vuelo real ni modifica los índices.'),
    ]:
        with st.expander(question):
            st.write(answer)
    
    tabs = st.tabs(["En dos minutos", "El reto y su alcance", "Evidencia", "Reproducir"])
    
    # Tab 1: En dos minutos
    with tabs[0]:
        st.subheader("Tres preguntas sobre el mismo lanzamiento")
        cards = [
            ("guide-stuff", "⚾ Stuff+ · calidad física", "Resume velocidad, giro y movimiento frente a lanzamientos históricos comparables."),
            ("guide-location", "🎯 Location+ · ubicación", "Estima el valor asociado al lugar donde llega la pelota, el conteo y el lado del bateador."),
            ("guide-pitching", "📊 Pitching+ · combinación", "Integra la calidad física con información contextual, como arsenal previo y entorno."),
        ]
        cols = st.columns(3)
        for col, (key, title, explanation) in zip(cols, cards):
            with col:
                with st.container(key=key):
                    st.markdown(f"#### {title}")
                    st.write(explanation)
        
        st.info(
            "**Cómo leerlos:** 100 es el promedio de referencia del índice. "
            "110 equivale a una desviación estándar por encima, no a 10% más outs ni a 10% menos carreras. "
            "Cada índice usa una referencia propia."
        )
        if (root / 'reports/v9_estadios/complemento/season/indice_integral.json').exists():
            st.write("El simulador también muestra la posibilidad de out al cerrar el turno y un índice integral que reúne ocho señales. En la tabla de lanzadores puedes comparar con el promedio de cada temporada y estadio. La ayuda junto a cada resultado explica qué significa.")
        
        # Interactive scale explorer
        st.markdown("### Explora la escala")
        score = st.slider("Índice de ejemplo", 70, 130, 110, 1, key="scale_slider")
        st.metric("Índice de ejemplo", score, f"{(score-100)/10:+.1f} desviaciones estándar", delta_color="off")
        st.caption("Ejemplo educativo de la escala. No es una predicción de un lanzamiento.")
        
        st.markdown("**Del campo a la revisión**")
        st.write(
            "Mediciones del lanzamiento → estimación del modelo → comparación de perfiles → "
            "revisión con video y contexto deportivo."
        )
        st.write(
            "Una buena calificación física puede coexistir con una ubicación poco favorable. "
            "Lee los tres índices juntos. Si el pitcher no tiene historial en el dataset, "
            "el modelo lo indica y continúa con la información disponible."
        )
        
        with st.expander("¿Por qué a veces se conserva una estimación anterior?"):
            st.write(
                "El modelo solo añade una capa nueva cuando mejora la predicción en juegos "
                "reservados para validación. Si arsenal o entorno no muestran una mejora consistente, "
                "se conserva la estimación más sencilla. Un cambio de altitud igual a cero significa "
                "que el modelo no confirmó información predictiva adicional; no prueba que la altitud "
                "carezca de efecto físico."
            )
        
        with st.expander("Diccionario rápido"):
            st.dataframe(
                pd.DataFrame([
                    ["IVB / HB", "Movimiento vertical inducido / horizontal, en pulgadas; describe hacia dónde se mueve el pitcheo."],
                    ["Spin", "Velocidad de giro de la pelota, medida en revoluciones por minuto (rpm)."],
                    ["Whiff", "Swing y fallo. El dataset lo distingue de una pelota bateada de foul."],
                    ["P(rodado | contacto)", "Probabilidad de rodado entre pelotas puestas en juego; no entre todos los lanzamientos."],
                    ["Calibración", "Si el modelo asigna 20% a muchos casos parecidos, cerca de 20 de cada 100 deberían ocurrir."],
                    ["Holdout", "Juegos apartados del ajuste para comprobar si el modelo generaliza a datos no usados al entrenarlo."],
                ], columns=["Término", "Significado"]),
                hide_index=True,
                width="stretch",
            )
    
    # Tab 2: El reto y su alcance
    with tabs[1]:
        st.subheader("Qué evalúa el reto")
        st.write(
            "Se revisan cuatro dimensiones: precisión predictiva, estabilidad ante distintos grupos, "
            "aporte del arsenal y entorno, y utilidad para el trabajo de scouting."
        )
        
        with st.expander("Ver criterios, métricas y entregables", expanded=False):
            st.caption("El detalle técnico permite verificar qué evidencia respalda cada dimensión.")
            st.write("El HTML local asigna 25% a cada criterio de evaluación.")
            
            st.dataframe(
                pd.DataFrame([
                    ["Calidad · 25%", "RMSE, Brier, calibración y baseline por conteo", "Evaluación v9 y métricas históricas v8"],
                    ["Robustez · 25%", "Temporada, pitchers nuevos y parque", "Auditorías por temporada, pitcher y Harp excluido; consultar su estado en el simulador"],
                    ["Arsenal + altitud · 25%", "Diferenciales y comparación entre entornos", "Historia previa, cuatro capas y ablaciones pareadas"],
                    ["Uso real · 25%", "Scores, perfil, recomendaciones, simulador, documento de 6–10 páginas", "Guía, simulador y entrega histórica disponibles"],
                ], columns=["Criterio", "Qué pide", "Implementación"]),
                hide_index=True,
                width="stretch",
            )
            
            st.warning(
                "El mapeo auditado identifica Harp Helú y otros estadios, con algunas filas pendientes. "
                "Comparar estadios no demuestra por sí solo un efecto causal de la altitud."
            )
            st.write(
                "El reto permite presentar resultados, pero no publicar los datos originales. "
                "El análisis es deportivo. El HTML fija la entrega el 22 de octubre de 2026 y equipos de 2–4 estudiantes."
            )
            st.caption("Fuente: HTML ISAC guardado en este repositorio.")
    
    # Tab 3: Evidencia
    with tabs[2]:
        st.subheader("Qué muestran estas cifras")
        st.write(
            "Las tablas resumen el desempeño medido en datos de evaluación. Busca el tamaño de muestra "
            "y compara cada resultado con su baseline: una métrica aislada no demuestra que el sistema "
            "sea mejor en todos los pitchers o estadios."
        )
        
        comparison = root / "reports/v9_incremental/comparacion.json"
        if comparison.exists():
            st.subheader("¿Qué cambió con la validación incremental?")
            changes = json.loads(comparison.read_text())
            st.dataframe(
                pd.DataFrame([{
                    "Capa": r["task"],
                    "RMSE original": r["rmse_original"],
                    "RMSE incremental": r["rmse_incremental"],
                    "Reducción MSE (%)": 100 * r["gain"],
                    "IC 95% inferior (%)": 100 * r["ci_low"],
                    "IC 95% superior (%)": 100 * r["ci_high"],
                } for r in changes]),
                hide_index=True,
                width="stretch",
            )
            st.caption(
                "Mismos pitches y presupuesto de entrenamiento. Menor RMSE es mejor. "
                "El benchmark 2026 ya se había inspeccionado: esta comparación no sustituye una temporada nueva."
            )
        
        path = root / "stuff_plus_output_v9_estadios" / "metricas.json"
        if not path.exists():
            path = root / "stuff_plus_output_v9" / "metricas.json"
        if path.exists():
            records = json.loads(path.read_text())
            st.subheader("Experimento v9 · benchmark 2026 reutilizado")
            st.dataframe(
                pd.DataFrame([{
                    "Tarea": r["task"],
                    "Pitches evaluados": r["n"],
                    "RMSE": r["metrics"].get("rmse"),
                    "Brier": r["metrics"].get("brier"),
                    "Mejora vs baseline (%)": 100 * r["vs_baseline"]["gain"] if r["vs_baseline"]["gain"] is not None else None,
                } for r in records if "metrics" in r]),
                hide_index=True,
                width="stretch",
            )
            st.caption(
                "Menor RMSE/Brier es mejor. La mejora se calcula sobre MSE/Brier; "
                "el baseline contextual de carreras conoce el conteo. "
                "Las probabilidades v9 incorporan contexto y tienen un alcance distinto de las probabilidades físicas v8."
            )
        else:
            st.info(
                "v9 todavía no tiene resultados locales de evaluación. "
                "Entrenar y evaluar genera la tabla; la existencia del código no demuestra una mejora de precisión."
            )
        
        historical_path = root / "stuff_plus_output_v8/metricas.json"
        historical = json.loads(historical_path.read_text()) if historical_path.exists() else []
        
        with st.expander("Resultados guardados de v8"):
            st.dataframe(
                pd.DataFrame([{
                    "Tarea": r["task"],
                    "n": r["n"],
                    "AUC v8": r["v8"].get("roc_auc"),
                    "Brier v8": r["v8"].get("brier"),
                    "RMSE v8": r["v8"].get("rmse"),
                    "Mejora MSE/Brier vs v7 (%)": 100 * r["bootstrap"]["relative_mse_reduction"]
                } for r in historical]),
                hide_index=True,
                width="stretch",
            )
            st.caption("v8 mejoró whiff y bola en juego, pero conservó el modelo físico de carreras. 2026 ya se había usado durante versiones anteriores.")
    
    # Tab 4: Reproducir
    with tabs[3]:
        st.subheader("Reproducir el análisis")
        st.write(
            "Para consultar la guía y usar los modelos disponibles, inicia el dashboard. "
            "El entrenamiento es un paso técnico opcional que requiere el parquet local autorizado."
        )
        st.info("En el paquete de entrega, abre ABRIR_DASHBOARD.bat. La primera instalación requiere preparar Python siguiendo README_PRIMERO.md.")
        st.code("python -m streamlit run dashboard_stuff_plus.py", language="bash")
        
        with st.expander("Instrucciones para crear modelos desde los datos locales"):
            st.code(
                "python -m venv .venv\n"
                "source .venv/bin/activate\n"
                "python -m pip install -r requirements-entrega.txt\n"
                "python -m unittest test_stuff_plus_v9 -v\n"
                "python entrenar_stuff_plus_v9.py --incremental-gate --iteraciones 300 --hilos 3 --salida stuff_plus_output_v9_incremental\n"
                "python -m streamlit run dashboard_stuff_plus.py",
                language="bash",
            )
            st.write(
                "El cargador busca primero Data/stuff_model_df.parquet. "
                "Los modelos v9 son independientes de los bundles v5–v8. "
                "En Windows, activa el entorno con .venv\\Scripts\\Activate.ps1."
            )
        
        st.markdown("### Descargas")
        col1, col2, col3 = st.columns(3)
        
        guide = root / "docs/guias/GUIA_PROYECTO.md"
        if guide.exists():
            with col1:
                st.download_button(
                    "📄 Guía completa (ES)",
                    guide.read_bytes(),
                    guide.name,
                    "text/markdown",
                    use_container_width=True,
                )
        
        approach = root / "docs/guias/PROJECT_APPROACH.md"
        if approach.exists():
            with col2:
                st.download_button(
                    "📄 Project walkthrough (EN)",
                    approach.read_bytes(),
                    approach.name,
                    "text/markdown",
                    use_container_width=True,
                )
        
        document = root / "reports/v9_estadios/DOCUMENTO_TECNICO_ESTADIOS.pdf"
        if document.exists():
            with col3:
                st.download_button(
                    "📄 Documento técnico actualizado",
                    document.read_bytes(),
                    document.name,
                    "application/pdf",
                    use_container_width=True,
                )
