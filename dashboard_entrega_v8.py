"""Vistas operativas; leen exclusivamente agregados y resultados de entrega."""
from pathlib import Path
import json
import pandas as pd
import altair as alt
import streamlit as st
import entrenar_stuff_plus_v8 as v8
ROOT=Path(__file__).resolve().parent
OUT=ROOT/"entrega_v8"


def render(simulation,bundle):
    if not (OUT/"pitchers_v8.csv").exists():
        st.info("Genera los análisis de entrega con analisis_operativo_v8.py.")
        return
    pitchers=pd.read_csv(OUT/"pitchers_v8.csv")
    arsenal=pd.read_csv(OUT/"arsenal_v8.csv")
    movement=pd.read_csv(OUT/"mapa_movimiento.csv")
    cases=json.loads((OUT/"casos_scouting.json").read_text(encoding="utf-8"))
    tab_map,tab_env,tab_cases,tab_validation=st.tabs(["Mapa y ficha", "Comparar entornos", "Casos de scouting", "Evidencia y validación"])
    with tab_map:
        ids=sorted(pitchers.pitcher_anon_id.unique())
        chosen=st.selectbox("Pitcher de la ficha",ids,index=ids.index(cases[0]["pitcher"]))
        info=pitchers.loc[pitchers.pitcher_anon_id.eq(chosen)]
        st.dataframe(info,hide_index=True)
        st.caption("IC de Pitching+ medio mediante remuestreo de juegos. No es un intervalo de talento. La regularización usa 100 pitches de peso hacia 100 y es descriptiva.")
        if not info.eligible.all(): st.warning("Muestra insuficiente para una comparación estable: mínimo orientativo 100 pitches y cinco juegos.")
        local=movement.loc[movement.pitcher_anon_id.eq(chosen)]
        color=st.selectbox("Color del mapa",["stuff_plus","pitching_plus","p_whiff_given_swing"])
        chart=alt.Chart(local).mark_circle().encode(x=alt.X("HB:Q",title="HB normalizado por mano (pulgadas)"),
            y=alt.Y("IVB:Q",title="IVB (pulgadas)"),size=alt.Size("n:Q",title="Pitches"),color=alt.Color(f"{color}:Q"),
            shape="AutoPitchType:N",tooltip=["AutoPitchType","altitude_category","PitcherThrows","n","velocity","HB","IVB",color]).interactive()
        st.altair_chart(chart,use_container_width=True)
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
        st.caption("Escenario predictivo con física fija. No transporta movimiento ni estima un efecto causal. Extreme Altitude no está identificado como Harp Helú. Stuff+ físico permanece igual al cambiar solo el entorno.")
        shape=movement.loc[movement.AutoPitchType.eq(simulation["AutoPitchType"])&movement.PitcherThrows.eq(simulation["PitcherThrows"])]
        support=shape.groupby("altitude_category").n.sum().rename("Pitches de ese tipo y mano").reset_index()
        st.dataframe(support,hide_index=True)
        if len(support)<3 or (support.iloc[:,1]<100).any(): st.warning("Soporte escaso o ausente para este tipo y mano en al menos un entorno.")
        if not shape.empty and not shape.velocity.min()<=simulation["RelSpeed"]<=shape.velocity.max():
            st.warning("Velocidad fuera del rango de medias de perfiles observados. Interpreta la simulación como exploratoria.")
        env=pd.read_csv(OUT/"entorno_ajustado.csv")
        task=st.selectbox("Resultado para comparar entornos",sorted(env.outcome.unique()))
        st.dataframe(env.loc[env.outcome.eq(task)],hide_index=True)
        st.caption("Diferencia categoría menos No Altitude, ajustada por coincidencias de pitcher, año, tipo, lado del bateador y conteo. IC por pitcher; múltiples comparaciones exploratorias. No equivale a un park holdout.")
    with tab_cases:
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
        st.dataframe(profiles,hide_index=True)
        st.caption("Rangos del 10% superior de Pitching+ predicho dentro de tipo, mano y entorno. Perfil descriptivo condicionado a este modelo, no óptimo causal ni garantía de transferencia a CDMX.")
    with tab_validation:
        path=OUT/"validacion_pitchers/metricas.json"
        if path.exists():
            records=json.loads(path.read_text(encoding="utf-8"))
            st.dataframe(pd.DataFrame([{"task":r["task"],"n":r["n"],**r["metrics"],"gain_vs_constant":r["vs_constant"]["gain"]} for r in records]),hide_index=True)
        st.caption("Modelos de auditoría reentrenados sin los pitchers de prueba. Prueba 2026 sin historial de arsenal. El año ya fue visto en el desarrollo histórico: esta auditoría no crea un benchmark futuro intacto.")
        if (OUT/"DOCUMENTO_TECNICO_V8.pdf").exists():
            st.download_button("Documento técnico PDF",(OUT/"DOCUMENTO_TECNICO_V8.pdf").read_bytes(),"DOCUMENTO_TECNICO_V8.pdf","application/pdf")
