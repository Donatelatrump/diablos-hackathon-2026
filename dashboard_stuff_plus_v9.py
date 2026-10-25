"""Coach-oriented simulation using the exact frozen v9 inference pipeline."""
import json
from pathlib import Path
import altair as alt
import pandas as pd
import streamlit as st
import entrenar_stuff_plus_v9 as v9
from dashboard_style import apply_dashboard_style, highlight_tutorial_target


@st.cache_resource
def get_bundle(path, modified):
    return v9.load_bundle(path)


TUTORIAL_STEPS = {
    1: ("Elige el lanzamiento", "Selecciona el tipo de lanzamiento y la mano del pitcher. El simulador carga un perfil típico como punto de partida.", "profile"),
    2: ("Ajusta las mediciones", "Cambia velocidad, IVB (movimiento vertical), HB (movimiento lateral) y spin si tienes esos datos. Puedes conservar los valores típicos.", "measurements"),
    3: ("Añade contexto si lo conoces", "Abre “Release, ubicación y arsenal” para ajustar el punto de salida, la ubicación frente al bateador y el repertorio previo. Este paso es opcional.", "advanced"),
    4: ("Compara los resultados", "Cada columna representa un entorno. 100 es el promedio de referencia; un número mayor indica una evaluación relativa más alta. Stuff+ mira el lanzamiento, Location+ su ubicación y Pitching+ los combina.", "results"),
    5: ("Explora las otras vistas", "“Pitchers y movimiento” muestra resúmenes del grupo. “Cómo se validó” explica las pruebas del modelo. Usa estas vistas como apoyo para revisar, no como una decisión automática.", "analysis"),
}


def render_tutorial():
    with st.expander("¿Primera vez? Tutorial paso a paso", expanded=False):
        st.caption("Elige un paso y se resaltará la parte correspondiente de la pantalla.")
        step = st.segmented_control(
            "Paso del tutorial",
            options=list(TUTORIAL_STEPS),
            format_func=lambda value: f"Paso {value}",
            key="simulator_tutorial_step",
        )
        if step is not None:
            title, instructions, target = TUTORIAL_STEPS[step]
            st.info(f"**Paso {step} de {len(TUTORIAL_STEPS)} · {title}**\n\n{instructions}")
            highlight_tutorial_target(target)


def render(output):
    output = Path(output)
    bundle = get_bundle(str(output), (output / "bundle.json").stat().st_mtime_ns)
    meta = bundle[0]
    
    st.title("Simular un lanzamiento")
    st.caption("Experimento v9 · física, ubicación, arsenal y entorno. Referencia histórica fija; benchmark 2026 reutilizado.")
    
    inherited = [task for task, item in meta["tasks"].items() if item["postprocessor"]["method"] == "parent"]
    if inherited:
        st.info(
            "La validación conservó la capa más simple en: " + ", ".join(inherited) +
            ". Un delta de entorno igual a cero significa que no se confirmó una mejora predictiva adicional; "
            "no demuestra ausencia de un efecto físico de la altitud."
        )
    
    if not (output / "metricas.json").exists():
        st.warning("Estos modelos terminaron entrenamiento, pero su evaluación todavía no está disponible.")
    
    render_tutorial()
    
    sim, rankings, evidence = st.tabs(["Lanzamiento y entorno", "Pitchers y movimiento", "Cómo se validó"])
    
    with sim:
        profiles = meta["input_profiles"]
        
        # Profile selection
        with st.container(key="tour-profile"):
            st.subheader("1. Perfil del lanzamiento")
            left, right = st.columns(2)
            pitch_type = left.selectbox(
                "Tipo de lanzamiento",
                sorted({p["type"] for p in profiles}),
                key="sim_pitch_type"
            )
            hand = right.selectbox(
                "Mano del pitcher",
                sorted({p["hand"] for p in profiles if p["type"] == pitch_type}),
                key="sim_hand"
            )
        
        profile = next(p for p in profiles if p["type"] == pitch_type and p["hand"] == hand)
        row = {
            **profile["median"],
            "AutoPitchType": pitch_type,
            "PitcherThrows": hand,
            "pitcher_anon_id": "unknown",
            "PitchUID": "simulation",
            "BatterSide": "Right",
            "PlateLocHeight": 2.5,
            "PlateLocSide": 0.0,
            "Balls": 0,
            "Strikes": 0,
            "altitude_category": "No Altitude",
        }
        
        st.write("Parte del perfil típico y cambia solo las mediciones que conozcas.")
        
        # Physical measurements
        with st.container(key="tour-measurements"):
            st.subheader("2. Mediciones físicas")
            controls = [
                ("RelSpeed", "Velocidad (mph)"),
                ("InducedVertBreak", "IVB (pulgadas)"),
                ("HorzBreak", "HB (pulgadas)"),
                ("SpinRate", "Spin (rpm)"),
            ]
            field_cues = {
                "RelSpeed": ("↗", "Rapidez al salir", "Velocidad de la pelota al salir de la mano del pitcher, en millas por hora."),
                "InducedVertBreak": ("↕", "Movimiento vertical", "Cuánto se desvía verticalmente el lanzamiento por su movimiento aerodinámico, en pulgadas."),
                "HorzBreak": ("↔", "Movimiento lateral", "Cuánto se desvía a los lados, en pulgadas. La orientación depende de la mano del pitcher."),
                "SpinRate": ("⟳", "Giro de la pelota", "Velocidad de rotación de la pelota, en revoluciones por minuto (rpm)."),
            }
            
            cols = st.columns(4)
            for col, (key, label) in zip(cols, controls):
                value = row[key]
                icon, cue, explanation = field_cues[key]
                col.caption(f"{icon} {cue}")
                row[key] = col.number_input(
                    label,
                    value=float(value) if value is not None else None,
                    help=explanation,
                    key=f"{pitch_type}-{hand}-{key}",
                )
        
        # Advanced context
        with st.container(key="tour-advanced"):
            st.subheader("3. Contexto avanzado (opcional)")
            with st.expander("Release, ubicación y arsenal", expanded=False):
                st.caption("Punto de salida del pitcher · posición de la pelota al llegar al plato · contexto del bateador y el repertorio previo.")
                
                advanced = [
                    ("EffectiveVelo", "Velocidad efectiva (mph)"),
                    ("SpinAxis", "Eje de spin (grados)"),
                    ("RelHeight", "Altura de release (pies)"),
                    ("RelSide", "Lado de release (pies)"),
                    ("Extension", "Extensión (pies)"),
                    ("VertBreak", "Break vertical total (pulgadas)"),
                    ("PlateLocHeight", "Altura en plato (pies)"),
                    ("PlateLocSide", "Lado en plato (pies)"),
                ]
                cols = st.columns(3)
                for i, (key, label) in enumerate(advanced):
                    value = row[key]
                    row[key] = cols[i % 3].number_input(
                        label,
                        value=float(value) if value is not None else None,
                        key=f"{pitch_type}-{hand}-{key}",
                    )
                
                row["Balls"] = cols[0].number_input("Bolas", 0, 3, 0, key=f"{pitch_type}-{hand}-Balls")
                row["Strikes"] = cols[1].number_input("Strikes", 0, 2, 0, key=f"{pitch_type}-{hand}-Strikes")
                row["BatterSide"] = cols[2].selectbox("Lado del bateador", ["Right", "Left"], key=f"{pitch_type}-{hand}-BatterSide")
                
                known = sorted({r["pitcher_anon_id"] for r in meta["profile"]["fastballs"]})
                row["pitcher_anon_id"] = st.selectbox(
                    "Arsenal histórico",
                    ["Sin historial", *known],
                    key=f"{pitch_type}-{hand}-arsenal",
                )
        
        # Validation warnings
        missing = [key for key in profile["median"] if row.get(key) is None]
        if missing:
            st.warning("Completa las mediciones para simular: " + ", ".join(missing))
        else:
            outside = [
                key for key in profile["median"]
                if profile["p01"][key] is not None and not profile["p01"][key] <= row[key] <= profile["p99"][key]
            ]
            if outside:
                st.warning("Fuera del rango central 98% de entrenamiento para este tipo y mano: " + ", ".join(outside))
            
            st.caption(
                f"Perfil basado en {profile['n']:,} pitches de entrenamiento. "
                "Estar dentro de rangos individuales no garantiza que la combinación esté bien representada."
            )
            
            # Run simulation
            scenarios = pd.DataFrame([
                {**row, "PitchUID": f"scenario-{i}", "altitude_category": category}
                for i, category in enumerate(["No Altitude", "Medium Altitude", "Extreme Altitude"])
            ])
            predicted = v9.infer(scenarios, bundle)
            labels = ["Sin altitud", "Altitud media", "Altitud extrema"]
            
            # Results
            with st.container(key="tour-results"):
                st.subheader("4. Resultados por entorno")
                result_cols = st.columns(3)
                for col, label, (_, result) in zip(result_cols, labels, predicted.iterrows()):
                    with col:
                        st.markdown(f"#### {label}")
                        st.metric("Stuff+ · física", f"{result.stuff_plus:.1f}")
                        st.metric("Location+ · ubicación", f"{result.location_plus:.1f}")
                        st.metric("Pitching+ · combinado", f"{result.pitching_plus:.1f}")
                        st.caption(f"Carreras proxy esperadas: {result.pred_environment_run_value:.4f}")
            
            if not predicted.arsenal_history_available.iloc[0]:
                st.info("Sin historial de recta primaria: el modelo recibe una bandera de arsenal ausente.")
            
            for name, ref in meta["reference"].items():
                if not ref["informative"]:
                    st.info(f"{name}: referencia constante; se muestra 100 y no permite ordenar lanzamientos.")
            
            st.caption(
                "La comparación mantiene fija la física medida. No transporta movimiento al cambiar el aire. "
                "Altitud extrema no identifica Harp Helú; el delta es predictivo."
            )
            
            # Probabilities table
            probabilities = {
                "p_whiff": "Whiff por pitch",
                "p_whiff_given_swing": "Whiff dado swing",
                "p_ball_in_play": "Bola en juego",
                "p_groundball_given_in_play": "Rodado dado bola en juego",
                "p_weak_contact": "Contacto <85 mph dado contacto medido",
                "p_hard_contact": "Contacto ≥95 mph dado contacto medido",
                "p_home_run_per_pitch": "Jonrón por pitch",
                "p_called_strike": "Strike cantado",
                "p_chase": "Swing fuera de zona por pitch",
            }
            table = pd.DataFrame({"Resultado": [label for key, label in probabilities.items() if key in predicted]})
            for i, label in enumerate(labels):
                table[label] = [f"{100 * predicted.iloc[i][key]:.1f}%" for key in probabilities if key in predicted]
            
            st.subheader("Probabilidades condicionales")
            st.dataframe(table, hide_index=True, width="stretch")
            st.caption("Estas probabilidades incorporan ubicación y contexto. Las filas condicionales tienen denominadores distintos y no deben sumarse.")
            
            st.download_button(
                "Descargar escenarios",
                predicted.to_csv(index=False),
                "escenarios_v9.csv",
                "text/csv",
                use_container_width=True,
            )
            
            # SHAP explanation
            with st.expander("Qué impulsa el Stuff+ físico", expanded=False):
                if st.button("Explicar este pitch", type="primary", key="explain_pitch"):
                    from explicar_v9 import explain_physical
                    explanation = explain_physical(scenarios.iloc[:1], bundle)
                    if explanation["informative"]:
                        contributions = explanation["contributions"].iloc[0]
                        top = contributions.abs().sort_values(ascending=False).head(8).index
                        shown = contributions.loc[top].copy()
                        shown.loc["Otras variables"] = contributions.drop(top).sum()
                        chart_data = shown.rename("Puntos").rename_axis("Variable").reset_index()
                        chart = alt.Chart(chart_data).mark_bar().encode(
                            x="Puntos:Q",
                            y=alt.Y("Variable:N", sort="-x"),
                            color=alt.condition(
                                alt.datum.Puntos > 0,
                                alt.value("#ad1830"),
                                alt.value("#718096")
                            ),
                            tooltip=["Variable", "Puntos"],
                        ).properties(height=300)
                        st.altair_chart(chart, width="stretch")
                        st.caption(
                            f"Base del modelo: {explanation['base'][0]:.2f} puntos. "
                            f"Base + contribuciones = {explanation['score'][0]:.2f}. "
                            "Atribuciones SHAP a la predicción actual; no estiman el efecto causal de modificar una variable."
                        )
                    else:
                        st.info("El modelo físico conserva un baseline constante; no hay diferencias de features que explicar.")
    
    with rankings:
        st.subheader("Pitchers y movimiento")
        if (output / "pitchers.csv").exists():
            pitchers = pd.read_csv(output / "pitchers.csv")
            
            filter_col, _ = st.columns([1, 3])
            with filter_col:
                min_pitches = st.checkbox("Al menos 100 pitches y cinco juegos", value=True, key="filter_pitchers")
            
            if min_pitches:
                pitchers = pitchers.loc[pitchers.n_pitches.ge(100) & pitchers.n_games.ge(5)]
            
            st.dataframe(
                pitchers.sort_values("pitching_plus", ascending=False),
                hide_index=True,
                width="stretch",
            )
            st.caption(
                "Promedios descriptivos de los pitches evaluados. "
                "La muestra y el contexto afectan el ranking; no son estimaciones de talento ni intervalos de confianza."
            )
            
            # Movement map
            st.markdown("### Mapa de movimiento")
            movement = pd.read_csv(output / "mapa_movimiento.csv")
            chosen = st.selectbox(
                "Pitcher del mapa",
                sorted(movement.pitcher_anon_id.unique()),
                key="movement_pitcher"
            )
            local = movement.loc[movement.pitcher_anon_id.eq(chosen)]
            
            color_options = {
                "stuff_plus": "Stuff+",
                "pitching_plus": "Pitching+",
                "p_whiff_given_swing": "Whiff / Swing",
            }
            color_key = st.selectbox(
                "Color del mapa",
                list(color_options.keys()),
                format_func=lambda x: color_options[x],
                key="movement_color"
            )
            
            chart = alt.Chart(local).mark_circle(opacity=0.85).encode(
                x=alt.X("HB:Q", title="HB normalizado por mano (pulgadas)"),
                y=alt.Y("IVB:Q", title="IVB (pulgadas)"),
                size=alt.Size("n:Q", title="Pitches", scale=alt.Scale(range=[20, 500])),
                color=alt.Color(f"{color_key}:Q", title=color_options[color_key], scale=alt.Scale(scheme="redyellowgreen")),
                shape="AutoPitchType:N",
                tooltip=["AutoPitchType", "altitude_category", "n", "velocity", "stuff_plus", "pitching_plus"],
            ).interactive().properties(height=450)
            
            st.altair_chart(chart, width="stretch")
            st.caption(
                "Cada punto es una media por tipo y categoría de altitud; no muestra trayectorias ni pitches individuales. "
                "HB de zurdos se refleja para comparar por mano."
            )
            
            # Arsenal
            st.markdown("### Arsenal del pitcher")
            arsenal_path = output / "arsenal.csv"
            if arsenal_path.exists():
                arsenal = pd.read_csv(arsenal_path)
                st.dataframe(
                    arsenal.loc[arsenal.pitcher_anon_id.eq(chosen)],
                    hide_index=True,
                    width="stretch",
                )
        else:
            st.info("La evaluación genera los agregados de pitchers y el mapa.")
    
    with evidence:
        st.subheader("Cómo se validó")
        st.write(
            "Los juegos se separan en ajuste, parada temprana, calibración, búsqueda y confirmación. "
            "La temporada de evaluación no decide modelos ni escalas."
        )
        
        st.markdown("### Selección de modelos")
        st.dataframe(
            pd.DataFrame([{
                "Tarea": task,
                "Predicción elegida": item["selection"].get("selected", "baseline"),
                "Comparada contra": item["selection"].get("control_task", "baseline"),
                "Confirmada": item["selection"]["promoted"],
                "Filas de ajuste": item["n_fit"],
            } for task, item in meta["tasks"].items()]),
            hide_index=True,
            width="stretch",
        )
        
        if (output / "ablaciones.json").exists():
            st.markdown("### Ablaciones: cambio de error al añadir ubicación, arsenal y entorno")
            st.dataframe(
                pd.DataFrame(json.loads((output / "ablaciones.json").read_text())),
                hide_index=True,
                width="stretch",
            )
            st.caption(
                "Ganancia = 1 − MSE nuevo / MSE anterior. Intervalos mediante remuestreo de juegos. "
                "No representan efectos causales."
            )


if __name__ == "__main__":
    st.set_page_config(page_title="Diablos · Simulador v9", layout="wide")
    apply_dashboard_style()
    render(Path(__file__).resolve().parent / "stuff_plus_output_v9")