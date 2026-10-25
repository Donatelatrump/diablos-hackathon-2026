"""Coach-oriented simulation using the exact frozen v9 inference pipeline."""
import json
from pathlib import Path
import altair as alt
import pandas as pd
import streamlit as st
import entrenar_stuff_plus_v9 as v9


@st.cache_resource
def get_bundle(path, modified):
    return v9.load_bundle(path)


def render(output):
    output = Path(output)
    bundle = get_bundle(str(output), (output / "bundle.json").stat().st_mtime_ns)
    meta = bundle[0]
    st.title("Simular un lanzamiento")
    st.caption("Experimento v9 · física, ubicación, arsenal y entorno. Referencia histórica fija; benchmark 2026 reutilizado.")
    inherited = [task for task, item in meta["tasks"].items() if item["postprocessor"]["method"] == "parent"]
    if inherited:
        st.info("La validación conservó la capa más simple en: " + ", ".join(inherited) +
                ". Un delta de entorno igual a cero significa que no se confirmó una mejora predictiva adicional; no demuestra ausencia de un efecto físico de la altitud.")
    if not (output / "metricas.json").exists():
        st.warning("Estos modelos terminaron entrenamiento, pero su evaluación todavía no está disponible.")
    sim, rankings, evidence = st.tabs(["Lanzamiento y entorno", "Pitchers y movimiento", "Cómo se validó"])
    with sim:
        profiles = meta["input_profiles"]
        left, right = st.columns(2)
        pitch_type = left.selectbox("Tipo de lanzamiento", sorted({p["type"] for p in profiles}))
        hand = right.selectbox("Mano del pitcher", sorted({p["hand"] for p in profiles if p["type"] == pitch_type}))
        profile = next(p for p in profiles if p["type"] == pitch_type and p["hand"] == hand)
        row = {**profile["median"], "AutoPitchType": pitch_type, "PitcherThrows": hand,
               "pitcher_anon_id": "unknown", "PitchUID": "simulation", "BatterSide": "Right",
               "PlateLocHeight": 2.5, "PlateLocSide": 0., "Balls": 0, "Strikes": 0, "altitude_category": "No Altitude"}
        st.write("Empieza con un perfil típico del entrenamiento y cambia las mediciones de tu pitch.")
        controls = [("RelSpeed", "Velocidad (mph)"), ("InducedVertBreak", "IVB (pulgadas)"),
                    ("HorzBreak", "HB (pulgadas)"), ("SpinRate", "Spin (rpm)")]
        for col, (key, label) in zip(st.columns(4), controls):
            value = row[key]
            row[key] = col.number_input(label, value=float(value) if value is not None else None,
                                        key=f"{pitch_type}-{hand}-{key}")
        with st.expander("Release, ubicación y arsenal"):
            cols = st.columns(3)
            advanced = [("EffectiveVelo", "Velocidad efectiva (mph)"), ("SpinAxis", "Eje de spin (grados)"),
                        ("RelHeight", "Altura de release (pies)"), ("RelSide", "Lado de release (pies)"),
                        ("Extension", "Extensión (pies)"), ("VertBreak", "Break vertical total (pulgadas)"),
                        ("PlateLocHeight", "Altura en plato (pies)"), ("PlateLocSide", "Lado en plato (pies)")]
            for i, (key, label) in enumerate(advanced):
                value = row[key]
                row[key] = cols[i%3].number_input(label, value=float(value) if value is not None else None,
                                                 key=f"{pitch_type}-{hand}-{key}")
            row["Balls"] = cols[0].number_input("Bolas", 0, 3, 0)
            row["Strikes"] = cols[1].number_input("Strikes", 0, 2, 0)
            row["BatterSide"] = cols[2].selectbox("Lado del bateador", ["Right", "Left"])
            known = sorted({r["pitcher_anon_id"] for r in meta["profile"]["fastballs"]})
            row["pitcher_anon_id"] = st.selectbox("Arsenal histórico", ["Sin historial", *known])
        missing = [key for key in profile["median"] if row.get(key) is None]
        if missing:
            st.warning("Completa las mediciones para simular: " + ", ".join(missing))
        else:
            outside = [key for key in profile["median"] if profile["p01"][key] is not None and
                       not profile["p01"][key] <= row[key] <= profile["p99"][key]]
            if outside:
                st.warning("Fuera del rango central 98% de entrenamiento para este tipo y mano: " + ", ".join(outside))
            st.caption(f"Perfil basado en {profile['n']:,} pitches de entrenamiento. Estar dentro de rangos individuales no garantiza que la combinación esté bien representada.")
            scenarios = pd.DataFrame([{**row, "PitchUID": f"scenario-{i}", "altitude_category": category}
                                     for i, category in enumerate(["No Altitude", "Medium Altitude", "Extreme Altitude"])])
            predicted = v9.infer(scenarios, bundle)
            labels = ["Sin altitud", "Altitud media", "Altitud extrema"]
            for col, label, (_, result) in zip(st.columns(3), labels, predicted.iterrows()):
                with col:
                    st.subheader(label)
                    st.metric("Stuff+ · física", f"{result.stuff_plus:.1f}")
                    st.metric("Location+ · ubicación", f"{result.location_plus:.1f}")
                    st.metric("Pitching+ · combinado", f"{result.pitching_plus:.1f}")
                    st.caption(f"Carreras proxy esperadas: {result.pred_environment_run_value:.4f}")
            if not predicted.arsenal_history_available.iloc[0]:
                st.info("Sin historial de recta primaria: el modelo recibe una bandera de arsenal ausente.")
            for name, ref in meta["reference"].items():
                if not ref["informative"]:
                    st.info(f"{name}: referencia constante; se muestra 100 y no permite ordenar lanzamientos.")
            st.caption("La comparación mantiene fija la física medida. No transporta movimiento al cambiar el aire. Altitud extrema no identifica Harp Helú; el delta es predictivo.")
            probabilities = {"p_whiff": "Whiff por pitch", "p_whiff_given_swing": "Whiff dado swing",
                             "p_ball_in_play": "Bola en juego", "p_groundball_given_in_play": "Rodado dado bola en juego",
                             "p_weak_contact": "Contacto <85 mph dado contacto medido", "p_hard_contact": "Contacto ≥95 mph dado contacto medido",
                             "p_home_run_per_pitch": "Jonrón por pitch", "p_called_strike": "Strike cantado", "p_chase": "Swing fuera de zona por pitch"}
            table = pd.DataFrame({"Resultado": [label for key, label in probabilities.items() if key in predicted]})
            for i, label in enumerate(labels):
                table[label] = [f"{100*predicted.iloc[i][key]:.1f}%" for key in probabilities if key in predicted]
            st.dataframe(table, hide_index=True, width="stretch")
            st.caption("Estas probabilidades incorporan ubicación y contexto. Las filas condicionales tienen denominadores distintos y no deben sumarse.")
            st.download_button("Descargar escenarios", predicted.to_csv(index=False), "escenarios_v9.csv", "text/csv")
            with st.expander("Qué impulsa el Stuff+ físico"):
                if st.button("Explicar este pitch"):
                    from explicar_v9 import explain_physical
                    explanation = explain_physical(scenarios.iloc[:1], bundle)
                    if explanation["informative"]:
                        contributions = explanation["contributions"].iloc[0]
                        top = contributions.abs().sort_values(ascending=False).head(8).index
                        shown = contributions.loc[top].copy()
                        shown.loc["Otras variables"] = contributions.drop(top).sum()
                        chart_data = shown.rename("Puntos").rename_axis("Variable").reset_index()
                        chart = alt.Chart(chart_data).mark_bar().encode(
                            x="Puntos:Q", y=alt.Y("Variable:N", sort="-x"),
                            color=alt.condition(alt.datum.Puntos > 0, alt.value("#ad1830"), alt.value("#718096")),
                            tooltip=["Variable", "Puntos"])
                        st.altair_chart(chart, width="stretch")
                        st.caption(f"Base del modelo: {explanation['base'][0]:.2f} puntos. Base + contribuciones = {explanation['score'][0]:.2f}. Atribuciones SHAP a la predicción actual; no estiman el efecto causal de modificar una variable.")
                    else:
                        st.info("El modelo físico conserva un baseline constante; no hay diferencias de features que explicar.")
    with rankings:
        if (output / "pitchers.csv").exists():
            pitchers = pd.read_csv(output / "pitchers.csv")
            if st.checkbox("Al menos 100 pitches y cinco juegos", value=True):
                pitchers = pitchers.loc[pitchers.n_pitches.ge(100) & pitchers.n_games.ge(5)]
            st.dataframe(pitchers.sort_values("pitching_plus", ascending=False), hide_index=True, width="stretch")
            st.caption("Promedios descriptivos de los pitches evaluados. La muestra y el contexto afectan el ranking; no son estimaciones de talento ni intervalos de confianza.")
            movement = pd.read_csv(output / "mapa_movimiento.csv")
            chosen = st.selectbox("Pitcher del mapa", sorted(movement.pitcher_anon_id.unique()))
            local = movement.loc[movement.pitcher_anon_id.eq(chosen)]
            chart = alt.Chart(local).mark_circle().encode(x=alt.X("HB:Q", title="HB normalizado por mano (pulgadas)"),
                y=alt.Y("IVB:Q", title="IVB (pulgadas)"), size="n:Q", color="stuff_plus:Q", shape="AutoPitchType:N",
                tooltip=["AutoPitchType", "altitude_category", "n", "velocity", "stuff_plus", "pitching_plus"]).interactive()
            st.altair_chart(chart, width="stretch")
        else:
            st.info("La evaluación genera los agregados de pitchers y el mapa.")
    with evidence:
        st.write("Los juegos se separan en ajuste, parada temprana, calibración, búsqueda y confirmación. La temporada de evaluación no decide modelos ni escalas.")
        st.dataframe(pd.DataFrame([{"Tarea": task, "Predicción elegida": item["selection"].get("selected", "baseline"),
                                   "Comparada contra": item["selection"].get("control_task", "baseline"),
                                   "Confirmada": item["selection"]["promoted"], "Filas de ajuste": item["n_fit"]}
                                  for task, item in meta["tasks"].items()]), hide_index=True, width="stretch")
        if (output / "ablaciones.json").exists():
            st.write("Cambio de error al añadir ubicación, arsenal y entorno")
            st.dataframe(pd.DataFrame(json.loads((output / "ablaciones.json").read_text())), hide_index=True, width="stretch")
            st.caption("Ganancia = 1 − MSE nuevo / MSE anterior. Intervalos mediante remuestreo de juegos. No representan efectos causales.")


if __name__ == "__main__":
    st.set_page_config(page_title="Diablos · Simulador v9", layout="wide")
    render(Path(__file__).resolve().parent / "stuff_plus_output_v9")
