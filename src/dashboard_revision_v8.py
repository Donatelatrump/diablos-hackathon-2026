"""Vistas de evidencia, resultados y catálogo geográfico de la entrega."""
import json
import altair as alt
import pandas as pd
import streamlit as st

PROBABILITIES = {
    "p_whiff": "Whiff por pitch",
    "p_whiff_given_swing": "Whiff dado swing",
    "p_ball_in_play": "Bola en juego por pitch",
    "p_chase": "Swing fuera de zona por pitch",
    "p_called_strike": "Strike cantado por pitch",
    "p_weak_contact": "Contacto débil dado contacto medido",
    "p_barrel_or_hard_contact": "Contacto fuerte dado contacto medido",
    "p_groundball_given_in_play": "Rodado dado bola en juego clasificada",
    "p_home_run_per_pitch": "Jonrón por pitch",
}


@st.cache_data
def read_csv(path, modified):
    return pd.read_csv(path)


def csv(path):
    return read_csv(str(path), path.stat().st_mtime_ns)


def render_probabilities(result):
    rows = [{"Resultado": label, "Probabilidad (%)": 100 * float(result[key])}
            for key, label in PROBABILITIES.items() if key in result]
    table = pd.DataFrame(rows)
    st.subheader("Resultados y riesgo esperado")
    st.bar_chart(table, x="Resultado", y="Probabilidad (%)", horizontal=True, height=350, color="#c62828")
    st.dataframe(table, hide_index=True, width="stretch",
                 column_config={"Probabilidad (%)": st.column_config.NumberColumn(format="%.2f %%")})
    st.caption("Son eventos con denominadores diferentes; no suman 100%. Contacto débil: salida <85 mph; fuerte: ≥95 mph, no barrel. Chase usa el indicador de swing fuera de zona por lanzamiento; no se presenta como tasa condicionada a estar fuera de zona. Whiff significa swing y fallo, sin incluir foul.")
    st.caption("El valor de carreras es un proxy de pesos fijos. No hay estimación de out por aparición al plato sin una reconstrucción válida de PA.")


def render_evidence(out):
    st.subheader("Modelo desplegado frente al baseline por conteo")
    path = out / "baseline_conteo_modelo_vigente.csv"
    if path.exists():
        baseline = csv(path)[["task", "n_test", "rmse", "count_baseline_rmse", "mse_skill_vs_count"]].copy()
        baseline["Ganancia MSE (%)"] = baseline.pop("mse_skill_vs_count") * 100
        baseline = baseline.rename(columns={"task": "Modelo", "n_test": "Pitches de prueba", "rmse": "RMSE modelo", "count_baseline_rmse": "RMSE por conteo"})
        st.dataframe(baseline, hide_index=True, width="stretch")
        st.warning("El modelo físico no supera el baseline por conteo en 2026. Los modelos con ubicación/entorno sí lo superan. La mejora contextual no demuestra una mejora de Stuff+ físico.")
        st.caption("Evaluación temporal 2026 heredada de v5: las predicciones de carreras se conservaron hasta v8. El baseline conoce conteo; el modelo físico dispone de menos contexto. Ganancia positiva significa menor MSE.")
    st.subheader("Cambios probabilísticos v8 en el benchmark temporal")
    path = out / "METRICAS_BENCHMARK_V8.json"
    if path.exists():
        records = json.loads(path.read_text(encoding="utf-8"))
        rows = []
        for record in records:
            for version in ("v7", "v8"):
                rows.append({"Tarea": record["task"], "Versión": version, **record[version]})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption("Se muestran Brier, AUC y ECE cuando están disponibles, y RMSE para regresión. Una mejora de Brier puede coexistir con peor ECE. 2026 ya se utilizó en el desarrollo histórico.")
    st.info("La referencia 100 es histórica y fija; no se ha demostrado normalización por estadio/temporada. Validación por parque pendiente de identificar los juegos. La auditoría de pitchers que sigue reentrena modelos y no es una evaluación idéntica del bundle desplegado.")


def render_scores(out):
    st.subheader("Scores por lanzamiento")
    path = out / "scores_por_lanzamiento_v8.csv"
    if not path.exists():
        st.info("Genera el paquete v8 para consultar los scores.")
        return
    scores = csv(path)
    options = sorted(scores.pitcher_anon_id.dropna().unique())
    chosen = st.selectbox("Pitcher para explorar lanzamientos", ["Todos", *options])
    selected = scores if chosen == "Todos" else scores.loc[scores.pitcher_anon_id.eq(chosen)]
    direction = st.radio("Orden de lanzamientos", ["Mayor Stuff+", "Menor Stuff+"], horizontal=True)
    selected = selected.sort_values("stuff_plus", ascending=direction == "Menor Stuff+")
    st.caption(f"{len(selected):,} resultados seleccionados. Se muestran hasta 500; la descarga incluye toda la selección. Scores temporales de 2026; no son toda la base original 2024–2026.")
    st.dataframe(selected.head(500), hide_index=True, width="stretch")
    st.download_button("Descargar scores seleccionados", selected.to_csv(index=False), "scores_seleccionados_v8.csv", "text/csv")
    for name, label in [("pitchers_v8.csv", "pitchers"), ("arsenal_v8.csv", "arsenal")]:
        path = out / name
        st.download_button(f"Descargar agregados de {label}", path.read_bytes(), name, "text/csv")
    path = out / "RECOMENDACIONES_V8.md"
    if path.exists():
        st.download_button("Descargar recomendaciones de scouting", path.read_bytes(), path.name, "text/markdown")


def render_stadiums(out):
    path = out / "estadios_altitudes.csv"
    if not path.exists():
        st.info("El catálogo de estadios todavía no está disponible.")
        return
    catalog = csv(path)
    st.subheader("Estadios y altitudes publicadas")
    st.caption("Catálogo de referencia LMB. No certifica visitas de Diablos ni asigna estadios a los IDs anónimos. Altitudes publicadas para sedes/equipos, no mediciones topográficas nuevas.")
    visits_path = out / "visitas_diablos_documentadas.csv"
    if visits_path.exists():
        with st.expander("Visitas de Diablos comprobadas en fuentes públicas"):
            visits = csv(visits_path).merge(catalog[["stadium_id", "stadium", "altitude_m"]], on="stadium_id", validate="many_to_one")
            st.dataframe(visits[["stadium", "altitude_m", "evidence_date", "date_type", "source_url"]], hide_index=True, width="stretch",
                         column_config={"source_url": st.column_config.LinkColumn("Evidencia del juego/visita")})
            st.caption("Muestra documentada de visitas, no inventario completo de 2024–2026. La fecha puede ser de publicación, como indica su columna. Ninguna fuente pública proporciona aquí la correspondencia con los IDs anónimos.")
    known = catalog.loc[catalog.altitude_m.notna()].sort_values("altitude_m", ascending=False)
    st.altair_chart(alt.Chart(known).mark_bar(color="#b71c1c").encode(
        x=alt.X("altitude_m:Q", title="Altitud publicada (m sobre el nivel del mar)"),
        y=alt.Y("stadium:N", sort="-x", title="Estadio"),
        tooltip=["stadium", "city", "altitude_m", "altitude_status"]
    ).properties(height=570), width="stretch")
    left, right = st.columns(2)
    first = left.selectbox("Estadio de referencia", catalog.stadium_id.tolist(),
                           format_func=lambda value: catalog.set_index("stadium_id").loc[value, "stadium"])
    second = right.selectbox("Estadio para comparar altitud", catalog.stadium_id.tolist(),
                            index=catalog.stadium_id.tolist().index("campeche_barrera"),
                            format_func=lambda value: catalog.set_index("stadium_id").loc[value, "stadium"])
    comparison = catalog.loc[catalog.stadium_id.isin([first, second])].copy()
    reference = catalog.set_index("stadium_id").loc[first, "altitude_m"]
    comparison["Diferencia vs referencia (m)"] = comparison.altitude_m - reference
    st.dataframe(comparison[["stadium", "city", "altitude_m", "Diferencia vs referencia (m)", "altitude_status"]], hide_index=True, width="stretch")
    if comparison.altitude_m.isna().any():
        st.warning("Una de las sedes carece de altitud verificada. No se completa con la altitud de otra sede o de la ciudad.")
    st.info("Esta diferencia geográfica no es un delta de Stuff+. El modelo aprende categorías sin umbrales publicados; no se convierten metros a categorías ni se identifica un juego por su altitud.")
    st.subheader("Cobertura de identificación de los juegos")
    path = out / "AUDITORIA_ESTADIOS.json"
    if path.exists():
        audit = json.loads(path.read_text(encoding="utf-8"))
        st.write(f"{audit['mapped_games']:,} de {audit['games']:,} juegos con mapeo documentado; {audit['mapped_pitches']:,} de {audit['pitches']:,} lanzamientos vinculados.")
        st.dataframe(pd.DataFrame(audit["categories"]), hide_index=True, width="stretch")
        st.caption(f"{audit['missing_altitude_pitches']:,} lanzamientos sin categoría de altitud. No se les asigna estadio.")
        st.warning(audit["reason"])
    st.caption("Yucatán jugó temporalmente en Kanasín en 2024; Oaxaca tiene nueva sede YU’VA en 2026. Se conservan como sedes distintas y con altitud pendiente cuando no hay fuente verificable.")
    st.dataframe(catalog, hide_index=True, width="stretch", column_config={
        "altitude_source": st.column_config.LinkColumn("Fuente de altitud"),
        "venue_source": st.column_config.LinkColumn("Fuente de sede")})
    st.download_button("Descargar catálogo de estadios y fuentes", (out / "estadios_altitudes.csv").read_bytes(), "estadios_altitudes.csv", "text/csv")
    with st.expander("Fuentes y requisitos para vincular juegos"):
        st.markdown((out / "ESTADIOS_Y_ALTITUDES.md").read_text(encoding="utf-8"))
