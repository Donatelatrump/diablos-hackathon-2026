"""Optional measurement controls and transparent precision experiment status."""
import json
import math
from pathlib import Path

import streamlit as st

from precision_model import OUTPUT


def flight_inputs(row, prefix):
    with st.expander('Mediciones adicionales del vuelo (opcional)'):
        st.write('Si tu equipo de medición registra estos datos, puedes añadirlos. Si falta alguno o el ajuste no supera las pruebas, se conserva el modelo habitual.')
        fields = [('ZoneSpeed','Velocidad al llegar al plato (mph)'),('ZoneTime','Tiempo de vuelo (segundos)'),
                  ('SpeedDrop','Pérdida de velocidad (mph)'),('VertRelAngle','Ángulo vertical de salida (grados)'),
                  ('HorzRelAngle','Ángulo lateral de salida (grados)'),('VertApprAngle','Ángulo vertical de llegada (grados)'),
                  ('HorzApprAngle','Ángulo lateral de llegada (grados)')]
        cols=st.columns(2)
        for i,(key,label) in enumerate(fields):
            row[key]=cols[i%2].number_input(label,value=None,key=f'{prefix}-precision-{key}')
        st.caption('Estas mediciones pueden ajustar la probabilidad de fallo cuando el bateador intenta batear. No cambian el índice de calidad física ni sustituyen datos desconocidos por promedios.')
    with st.expander('Lanzamientos anteriores e historial reciente (opcional)'):
        st.write('Añade solo datos anteriores al lanzamiento que estás evaluando. El historial reciente debe corresponder a los últimos cinco juegos disponibles del mismo tipo de lanzamiento.')
        row['observed_workload']=st.number_input('Lanzamientos previos registrados en este juego',min_value=0,value=None,key=prefix+'-workload')
        previous={}
        recent={}
        cols=st.columns(3)
        for i,(source,label) in enumerate([('velocity','Velocidad (mph)'),('hb','Movimiento lateral (pulgadas)'),('ivb','Movimiento vertical inducido (pulgadas)')]):
            previous[source]=cols[i].number_input('Lanzamiento anterior · '+label,value=None,key=prefix+'-previous-'+source)
            recent[source]=cols[i].number_input('Media de juegos anteriores · '+label,value=None,key=prefix+'-recent-'+source)
        count=st.number_input('Lanzamientos que respaldan esas medias',min_value=0,value=None,key=prefix+'-recent-count')
        complete=lambda values: all(v is not None and math.isfinite(v) for v in values)
        first=row['observed_workload']==0
        row['previous_available']=0. if first else 1. if complete(previous.values()) else None
        for suffix,source in [('velocity','RelSpeed'),('hb','HorzBreak'),('ivb','InducedVertBreak')]:
            row['previous_'+suffix]=None if first else previous[suffix]
            row[suffix+'_change']=float(row[source])-previous[suffix] if not first and previous[suffix] is not None and row[source] is not None else None
            row['recent_'+suffix]=recent[suffix] if count is not None and count>=10 and complete(recent.values()) else None
        row['recent_available']=float(count is not None and count>=10 and complete(recent.values()))
        row['recent_pitches']=count if count is not None else 0.
        st.caption('Si no conoces el orden anterior o la carga registrada, se conserva el modelo habitual. No uses totales finales del juego ni datos de turnos futuros.')


def render_precision_status(root):
    path=OUTPUT/'precision.json'
    st.markdown('### Mejoras de precisión en evaluación')
    if not path.exists():
        st.write('Se conserva el modelo habitual mientras terminan las comprobaciones del ajuste ampliado.')
        return
    try:
        report=json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        st.write('Se están actualizando las comprobaciones. El modelo habitual sigue disponible.')
        return
    if report.get('accepted'):
        st.success('El ajuste de fallo de swing superó las comprobaciones históricas. Se utiliza cuando hay mediciones adicionales válidas; en los demás casos se conserva el modelo habitual.')
    else:
        st.info('El ajuste ampliado no está activado: las comprobaciones aún no respaldan sustituir el modelo habitual.')
    rows=[]
    for key,label in [('temporal','Entrenar antes y evaluar después'),('pitcher','Lanzadores excluidos del ajuste'),('park','Harp excluido del ajuste')]:
        r=report.get('audits',{}).get(key)
        if r:
            rows.append({'Prueba':label,'Lanzamientos':r['n'],'Juegos':r['groups'],
                'Reducción de Brier (%)':100*r['gain'],'Límite inferior 95% (%)':100*r['ci_low'] if r['ci_low'] is not None else None,
                'Supera criterio':r['passes']})
    if rows:
        st.dataframe(rows,hide_index=True,width='stretch')
    st.caption('Evidencia retrospectiva de 2024–2025. No es una prueba prospectiva nueva. Se exige mejora del error, incertidumbre favorable y ausencia de degradaciones relevantes; más variables no garantizan mayor precisión.')
    st.download_button('Descargar comprobaciones del ajuste',path.read_bytes(),file_name='comprobaciones_precision.json',mime='application/json')
    count=Path(root)/'precision_count_output_2026_10_28/resultados.json'
    if count.exists():
        with st.expander('Objetivo experimental que distingue el conteo'):
            st.write('Este experimento valora el cambio entre conteos y el cierre del turno. Sus tablas se calculan solo con turnos completos de entrenamiento. No equivale a RE24 y no reemplaza las puntuaciones actuales.')
            data=json.loads(count.read_text(encoding='utf-8'))
            st.metric('Error del nuevo objetivo',f"{data['new_target_rmse']:.5f}")
            st.metric('Error de referencia del mismo objetivo',f"{data['new_target_count_reference_rmse']:.5f}")
            st.caption('Menor es mejor. Estos errores no se comparan directamente con el RMSE del objetivo anterior, porque las etiquetas son distintas. Falta validar este objetivo en otras separaciones y en decisiones deportivas.')
    calibration=Path(root)/'precision_calibration_output_2026_10_28/resultado.json'
    if calibration.exists():
        with st.expander('Calibración experimental por estadio'):
            data=json.loads(calibration.read_text(encoding='utf-8'))
            st.write('Se probaron ajustes de probabilidad de jonrón por estadio, suavizados hacia un ajuste global. Solo usan las etiquetas de calibración de desarrollo.')
            st.write('El ajuste ' + ('superó' if data['selection'].get('promoted') else 'no superó') + ' el criterio de selección de desarrollo. No se activa sin comprobar también la estabilidad temporal y por grupos del modelo completo.')


def render_candidate_preview(scenarios, predictions, bundle, output, labels):
    with st.expander('Comparar el candidato experimental de fallo de swing'):
        st.write('El candidato añade vuelo, secuencia e historial. No superó todas las comprobaciones de generalización: esta comparación no sustituye la evaluación habitual ni sus probabilidades.')
        if st.checkbox('Calcular comparación experimental',key='preview-precision'):
            from precision_model import preview_dashboard
            preview=preview_dashboard(scenarios,predictions,bundle,output)
            valid=preview.precision_whiff_available
            if not valid.any():
                st.info('No hay mediciones completas y válidas para esta comparación. Revisa los apartados opcionales de vuelo y lanzamientos anteriores; no necesitas completarlos para usar el modelo habitual.')
            else:
                table=[]
                for i,label in enumerate(labels):
                    if valid.iloc[i]:
                        base=100*predictions.iloc[i].p_whiff_given_swing
                        candidate=100*preview.iloc[i].p_whiff_given_swing
                        table.append({'Escenario':label,'Modelo habitual (%)':base,'Candidato experimental (%)':candidate,
                                      'Cambio (pp)':candidate-base})
                st.dataframe(table,hide_index=True,width='stretch')
                st.caption('Probabilidad de fallo condicionada a que intente batear. Que la cifra sea mayor no significa que el modelo sea más preciso. El resultado experimental no modifica los índices ni la tabla principal.')
