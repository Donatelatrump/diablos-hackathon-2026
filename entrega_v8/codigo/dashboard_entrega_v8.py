"""Vistas operativas; leen exclusivamente agregados y resultados de entrega."""
from pathlib import Path
import json
import pandas as pd
import altair as alt
import streamlit as st
import entrenar_stuff_plus_v8 as v8
from dashboard_revision_v8 import render_evidence, render_scores, render_stadiums
ROOT=Path(__file__).resolve().parent
OUT = next((path for path in (ROOT / "entrega_v8", ROOT.parent, ROOT.parent / "entrega_v8")
            if (path / "pitchers_v8.csv").exists()), ROOT / "entrega_v8")


def render(simulation,bundle):
    if not (OUT/"pitchers_v8.csv").exists():
        st.info("Genera los análisis de entrega con analisis_operativo_v8.py.")
        return
    pitchers=pd.read_csv(OUT/"pitchers_v8.csv")
    arsenal=pd.read_csv(OUT/"arsenal_v8.csv")
    movement=pd.read_csv(OUT/"mapa_movimiento.csv")
    cases=json.loads((OUT/"casos_scouting.json").read_text(encoding="utf-8"))
    tab_map,tab_env,tab_cases,tab_validation,tab_scores,tab_stadiums=st.tabs(["Mapa y ficha", "Comparar entornos", "Casos de scouting", "Evidencia y validación", "Scores y descargas", "Estadios y altitudes"])
    with tab_map:
        ids=sorted(pitchers.pitcher_anon_id.unique())
        chosen=st.selectbox("Pitcher de la ficha",ids,index=ids.index(cases[0]["pitcher"]))
        info=pitchers.loc[pitchers.pitcher_anon_id.eq(chosen)]
        st.dataframe(info,hide_index=True)
        st.caption("IC de Pitching+ medio mediante remuestreo de juegos. No es un intervalo de talento. La regularización usa 100 pitches de peso hacia 100 y es descriptiva.")
        if not info.eligible.all(): st.warning("Muestra insuficiente para una comparación estable: mínimo orientativo 100 pitches y cinco juegos.")
        local=movement.loc[movement.pitcher_anon_id.eq(chosen)]
        color=st.selectbox("Color del mapa",["stuff_plus","pitching_plus","p_whiff_given_swing"])
        minimum = st.number_input("Mínimo de pitches por perfil del mapa", 1, 10000, 20)
        supported = local.loc[local.n.ge(minimum)].sort_values(color, ascending=False)
        scale = alt.Scale(scheme="redblue", domainMid=100) if color.endswith("plus") else alt.Scale(scheme="blues", domain=[0, 1])
        chart=alt.Chart(supported).mark_circle(opacity=0.85, stroke="white", strokeWidth=1).properties(height=420).encode(x=alt.X("HB:Q",title="HB normalizado por mano (pulgadas)"),
            y=alt.Y("IVB:Q",title="IVB (pulgadas)"),size=alt.Size("n:Q",title="Pitches"),color=alt.Color(f"{color}:Q",scale=scale),
            shape="AutoPitchType:N",tooltip=["AutoPitchType","altitude_category","PitcherThrows","n","velocity","HB","IVB",color]).interactive()
        st.altair_chart(chart,width="stretch")
        st.caption("En los índices, el color se centra en la referencia 100. La escala de whiff es una probabilidad entre 0 y 1.")
        st.write("Perfiles con mayor y menor efectividad predicha de este pitcher")
        if supported.empty:
            st.info("No hay perfiles con ese tamaño de muestra. Reduce el mínimo para explorar.")
        else:
            best, worst = st.columns(2)
            columns = ["AutoPitchType", "altitude_category", "n", "velocity", "HB", "IVB", color]
            best.write("Mayor efectividad predicha")
            best.dataframe(supported.head(3)[columns],hide_index=True,width="stretch")
            worst.write("Menor efectividad predicha")
            worst.dataframe(supported.tail(3).sort_values(color)[columns],hide_index=True,width="stretch")
            st.caption("El orden compara medias predichas, no talento confirmado. Con menos de seis perfiles, las listas pueden compartir filas.")
        st.caption("Cada punto es una media por tipo y categoría de altitud; no muestra trayectorias ni pitches individuales. HB de zurdos se refleja para comparar por mano.")
        st.dataframe(arsenal.loc[arsenal.pitcher_anon_id.eq(chosen)],hide_index=True)
        st.download_button("Descargar ficha CSV",info.to_csv(index=False),file_name=f"ficha_{chosen}.csv",mime="text/csv")
    with tab_env:
        st.write("Mismo pitch, tres categorías de entorno")
        rows=pd.DataFrame([{**simulation,"altitude_category":category} for category in ["No Altitude","Medium Altitude","Extreme Altitude"]])
        predicted=v8.infer(rows,bundle)
        cols=st.columns(3)
        for index,category in enumerate(rows.altitude_category):
            with cols[index]:
                st.markdown(f"**{category}**")
                st.write(f"Stuff+: {predicted.iloc[index].stuff_plus:.1f}")
                st.write(f"Location+: {predicted.iloc[index].location_plus:.1f}")
                st.write(f"Pitching+: {predicted.iloc[index].pitching_plus:.1f}")
                st.write(f"Carreras proxy esperadas: {predicted.iloc[index].pred_environment_run_value:.4f}")
                st.write(f"Jonrón por pitch: {100*predicted.iloc[index].p_home_run_per_pitch:.2f}%")
                st.write(f"Contacto fuerte dado contacto medido: {100*predicted.iloc[index].p_barrel_or_hard_contact:.2f}%")
        baseline = predicted.iloc[0]
        deltas = pd.DataFrame({
            "Categoría": rows.altitude_category,
            "Delta Stuff+": predicted.stuff_plus.to_numpy()-baseline.stuff_plus,
            "Delta Pitching+": predicted.pitching_plus.to_numpy()-baseline.pitching_plus,
            "Delta carreras proxy": predicted.pred_environment_run_value.to_numpy()-baseline.pred_environment_run_value,
            "Delta HR (puntos porcentuales)": 100*(predicted.p_home_run_per_pitch.to_numpy()-baseline.p_home_run_per_pitch),
            "Delta contacto fuerte (puntos porcentuales)": 100*(predicted.p_barrel_or_hard_contact.to_numpy()-baseline.p_barrel_or_hard_contact),
        })
        st.dataframe(deltas,hide_index=True,width="stretch")
        st.caption("Diferencias respecto a No Altitude con física fija. Un delta cero puede corresponder a un predictor que no usa altitud; no demuestra ausencia de efecto real. Contacto fuerte es condicional, HR es por lanzamiento. El catálogo geográfico está en Estadios y altitudes.")
        st.caption("Escenario predictivo con física fija. No transporta movimiento ni estima un efecto causal. Extreme Altitude no está identificado como Harp Helú. Stuff+ físico permanece igual al cambiar solo el entorno.")
        shape=movement.loc[movement.AutoPitchType.eq(simulation["AutoPitchType"])&movement.PitcherThrows.eq(simulation["PitcherThrows"])]
        support=shape.groupby("altitude_category").n.sum().rename("Pitches de ese tipo y mano").reset_index()
        st.dataframe(support,hide_index=True)
        if len(support)<3 or (support.iloc[:,1]<100).any(): st.warning("Soporte escaso o ausente para este tipo y mano en al menos un entorno.")
        if not shape.empty and not shape.velocity.min()<=simulation["RelSpeed"]<=shape.velocity.max():
            st.warning("Velocidad fuera del rango de medias de perfiles observados. Interpreta la simulación como exploratoria.")
        env=pd.read_csv(OUT/"entorno_ajustado.csv")
        outcome_labels={"home_run":"Jonrón por lanzamiento", "is_whiff":"Whiff por lanzamiento", "whiff_swing":"Whiff dado swing", "run_value_proxy":"Carreras proxy", "InducedVertBreak":"IVB observado", "HB_normalized":"HB observado normalizado por mano"}
        task=st.selectbox("Resultado para comparar entornos",sorted(env.outcome.unique()),format_func=lambda value: outcome_labels.get(value,value))
        st.dataframe(env.loc[env.outcome.eq(task)],hide_index=True)
        st.caption("Diferencia categoría menos No Altitude, ajustada por coincidencias de pitcher, año, tipo, lado del bateador y conteo. IC por pitcher; múltiples comparaciones exploratorias. No equivale a un park holdout.")
    with tab_cases:
        st.subheader("Perfiles que cambian entre categorías de altitud")
        contrasts=pd.read_csv(OUT/"entorno_ajustado.csv")
        category=st.selectbox("Categoría para revisar perfiles",["Extreme Altitude","Medium Altitude"])
        selected_contrasts=contrasts.loc[contrasts.comparison.eq(category)&contrasts.pitch_type.ne("All")&contrasts.outcome.isin(["home_run","is_whiff","run_value_proxy"])]
        st.dataframe(selected_contrasts[["pitch_type","outcome","delta","ci_low","ci_high","n_pitchers"]],hide_index=True,width="stretch")
        st.caption("Asociaciones ajustadas respecto a No Altitude, dentro de soporte compartido. Para HR/whiff, multiplica delta por 100 para puntos porcentuales. Más whiff es favorable; más HR o carreras proxy indica mayor riesgo. Los intervalos remuestrean pitchers; comparaciones exploratorias múltiples. No son recomendaciones confirmadas para Harp Helú.")
        for case in cases:
            with st.expander(f"{case['category']}: {case['pitcher']}",expanded=True):
                st.write(case["reason"])
                ci=f"[{case['ci_low']:.1f}, {case['ci_high']:.1f}]" if case['ci_low'] is not None else "no estimable con un solo juego"
                st.write(f"{case['n_pitches']} pitches / {case['n_games']} juegos. Stuff+ {case['stuff_plus']:.1f}; Pitching+ {case['pitching_plus']:.1f}, IC {ci}.")
                st.write("Antes de decidir: revisar video, salud, rol, rival y representatividad de la muestra. Estas variables no están resueltas por el modelo.")
                if (OUT/"explicaciones_shap.csv").exists():
                    explanations=pd.read_csv(OUT/"explicaciones_shap.csv")
                    explanations=explanations.loc[explanations.pitcher.eq(case['pitcher'])].sort_values('mean_absolute_points',ascending=False).head(6)
                    st.dataframe(explanations[['feature','mean_stuff_points','mean_absolute_points']],hide_index=True)
                    st.caption("Atribuciones SHAP al Stuff+ medio del caso, en puntos de índice respecto al valor base del modelo. No predicen el efecto causal de cambiar una variable.")
        profiles=pd.read_csv(OUT/"perfiles_fisicos_descriptivos.csv")
        profile_type=st.selectbox("Familia del perfil físico",sorted(profiles.pitch_type.unique()))
        st.dataframe(profiles.loc[profiles.pitch_type.eq(profile_type)],hide_index=True,width="stretch")
        st.caption("Rangos del 10% superior de Pitching+ predicho dentro de tipo, mano y entorno. Perfil descriptivo condicionado a este modelo, no óptimo causal ni garantía de transferencia a CDMX.")
    with tab_validation:
        render_evidence(OUT)
        path=OUT/"validacion_pitchers/metricas.json"
        if path.exists():
            records=json.loads(path.read_text(encoding="utf-8"))
            st.dataframe(pd.DataFrame([{"task":r["task"],"n":r["n"],**r["metrics"],"gain_vs_constant":r["vs_constant"]["gain"]} for r in records]),hide_index=True)
        st.caption("Modelos de auditoría reentrenados sin los pitchers de prueba. Prueba 2026 sin historial de arsenal. El año ya fue visto en el desarrollo histórico: esta auditoría no crea un benchmark futuro intacto.")
        if (OUT/"DOCUMENTO_TECNICO_V8.pdf").exists():
            st.download_button("Documento técnico PDF",(OUT/"DOCUMENTO_TECNICO_V8.pdf").read_bytes(),"DOCUMENTO_TECNICO_V8.pdf","application/pdf")
    with tab_scores:
        render_scores(OUT)
    with tab_stadiums:
        render_stadiums(OUT)
