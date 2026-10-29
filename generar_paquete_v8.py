"""Documentación actual, PDF de ocho páginas y paquete reproducible sin dataset."""
from pathlib import Path
import json
import shutil
import zipfile
from xml.sax.saxutils import escape
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
from pypdf import PdfReader
import entrenar_stuff_plus_v8 as v8
ROOT=Path(__file__).resolve().parent
OUT=ROOT/"entrega_v8"


def read(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def number(value,digits=3): return "N/D" if value is None or pd.isna(value) else f"{value:.{digits}f}"


def main():
    metrics=read(OUT/"validacion_pitchers/metricas.json")
    audit=read(OUT/"validacion_pitchers/verificacion.json")
    protocol=read(OUT/"validacion_pitchers/protocolo.json")
    benchmark=read(ROOT/"stuff_plus_output_v8/metricas.json")
    scores=v8.v5.read_parquet(ROOT/'stuff_plus_output_v8/scores_pitch_v8.parquet')
    prediction_columns=['PitchUID','year','pitcher_anon_id','AutoPitchType','altitude_category','score_reference_id','stuff_plus','location_plus','pitching_plus',
                        'p_whiff','p_whiff_given_swing','p_ball_in_play','p_weak_contact','p_barrel_or_hard_contact',
                        'p_chase','p_called_strike','p_groundball_given_in_play','p_home_run_per_pitch',
                        'pred_stuff_run_value','pred_xrunvalue','pred_environment_run_value','pred_exit_speed_given_in_play']
    scores[prediction_columns].to_csv(OUT/'scores_por_lanzamiento_v8.csv',index=False)
    v8.v6.json_write(OUT/'METRICAS_BENCHMARK_V8.json',benchmark)
    cases=read(OUT/"casos_scouting.json")
    env=pd.read_csv(OUT/"entorno_ajustado.csv")
    summary=pd.read_csv(OUT/"pitchers_v8.csv")
    profiles=pd.read_csv(OUT/"perfiles_fisicos_descriptivos.csv")
    parent=read(ROOT/"stuff_plus_output_v5/metricas_validacion_v5.json")
    baseline=pd.DataFrame([r for r in parent if r['split']=='season_holdout_2026' and r['task'] in ['stuff_run_value','xrunvalue','environment_run_value']])
    baseline.to_csv(OUT/"baseline_conteo_modelo_vigente.csv",index=False)
    holdout=pd.DataFrame([{"task":r['task'],"n":r['n'],**r['metrics'],"gain":r['vs_constant']['gain'],"ci_low":r['vs_constant']['low'],"ci_high":r['vs_constant']['high']} for r in metrics])
    holdout.to_csv(OUT/"validacion_pitchers_resumen.csv",index=False)
    model_rows=[[r['task'],number(r['v7'].get('brier',r['v7'].get('rmse')),6),number(r['v8'].get('brier',r['v8'].get('rmse')),6),f"{r['bootstrap']['relative_mse_reduction']:.2%}"] for r in benchmark]
    validation_rows=[[r['task'],str(r['n']),number(r['metrics'].get('roc_auc',r['metrics'].get('rmse'))),f"{r['vs_constant']['gain']:.2%}",f"[{r['vs_constant']['low']:.2%}, {r['vs_constant']['high']:.2%}]"] for r in metrics]
    env_all=env.loc[env.pitch_type.eq('All')&env.comparison.eq('Extreme Altitude')]
    env_rows=[[r.outcome,number(r.delta,4),f"[{r.ci_low:.4f}, {r.ci_high:.4f}]",str(r.n_pitchers)] for r in env_all.itertuples()]
    pages=[
      ("1. Resumen y uso deportivo",[
        "Objetivo: evaluar lanzamientos y repertorios con un sistema interpretable que permita al cuerpo técnico priorizar observaciones y comparar perfiles. V8 combina modelos CatBoost globales con especialistas por familia, y conserva las tareas anteriores cuando el cambio no supera selección.",
        "La entrega contiene 135,604 scores derivados de 2026, agregados por pitcher y arsenal, tres casos de scouting, un simulador y análisis ajustados entre categorías de altitud. El paquete incluye predicciones identificadas por IDs anónimos, resultados agregados y código; excluye mediciones y outcomes originales por lanzamiento.",
        "V8 mejora Brier en whiff (0.14%), whiff dado swing (2.19%) y bola en juego (0.83%) frente a v7. Las mejoras de probabilidades no se traducen en una mejora demostrada del valor de carreras físico: Stuff+, Location+ y Pitching+ conservaron sus modelos.",
        "La pregunta operativa es qué pitcher merece revisión adicional, qué parte de su repertorio destaca y dónde la evidencia es insuficiente. Ningún ranking representa una orden automática de contratación. Salud, video, rol, calidad de oposición y costo no están modelados.",
        "Todos los resultados de 2026 deben interpretarse como benchmark reutilizado. La auditoría adicional excluye pitchers de sus propios modelos, pero no convierte la temporada en una prueba históricamente intacta."],
       [(["Tarea","v7 error","v8 error","Ganancia"],model_rows)]),
      ("2. Datos, población y alcance",[
        "Origen: 635,002 lanzamientos LMB: 243,254 de 2024, 256,144 de 2025 y 135,604 de 2026. Los identificadores de lanzamiento permiten unir predicciones sin usar resultados como entradas. Los identificadores de pitcher sirven para agrupar y construir historia, no para memorizar jugadores como features.",
        "Variables físicas: velocidad, spin, eje circular, release, extensión y movimiento. V6 añade proxies aerodinámicos; v8 añade ZoneSpeed, SpeedDrop y ZoneTime a los predictores seleccionados. Estas últimas son mediciones del trayecto, no exclusivamente del instante de release.",
        "Disponemos de categorías No Altitude, Medium Altitude y Extreme Altitude. No disponemos de estadio, fecha exacta, secuencia verificable ni ocupación de bases. No se asigna Extreme Altitude a Harp Helú, no se construyen cortes mensuales ficticios ni se presenta RE24 completo.",
        f"Los agregados actuales contienen {len(summary)} filas de pitcher/temporada/referencia. La auditoría excluye {protocol['missing_pitcher_rows_excluded']} filas sin identificador de pitcher del proceso de partición; esa exclusión se registra antes del ajuste.",
        "Las tasas por contacto y swing solo se evalúan donde su condición se observa. Las predicciones condicionales sí pueden generarse para cualquier lanzamiento sin usar su resultado. El diccionario y las reglas de elegibilidad están en los scripts v5-v8."],[]),
      ("3. Arquitectura, objetivos y escala",[
        "Stuff+ predice calidad física mediante el negativo de carreras esperadas con física e historia de arsenal. Location+ representa la diferencia predictiva entre el valor físico y el valor con ubicación, conteo y lado del bateador. Pitching+ incorpora además el contexto categórico de altitud. Las diferencias son predictivas, no una descomposición causal de command.",
        "El target de carreras utiliza pesos fijos: bola +0.03, strike -0.05; resultados terminales como out -0.27, walk +0.30, single +0.47, double +0.78, triple +1.09 y HR +1.40. Es un proxy, no una matriz RE24 estimada de estados base-out. Se informa esta limitación en todos los usos deportivos.",
        "Escala: 100 + 10 por el z-score del valor favorable. La media y desviación se guardan en una población histórica de referencia. No se recentra 2026 para forzar un promedio 100. Un 110 significa una desviación estándar sobre esa referencia, no diez por ciento menos carreras ni una garantía de nivel élite.",
        "El arsenal usa diferenciales de velocidad, IVB, HB y release respecto a una recta primaria histórica, además del uso por tipo. La historia se limita a temporadas anteriores. No se infiere orden de lanzamientos desde identificadores ni se llama tunneling real a una simple distancia de release.",
        "V8 acepta mezclas global/especialistas en whiff, whiff dado swing y bola en juego, y un global ampliado en EV. Las demás tareas conservan el padre. Si faltan mediciones válidas, la inferencia vuelve exactamente al respaldo anterior por fila."],[]),
      ("4. Validación con pitchers no vistos",[
        "Auditoría adicional: partición reproducible por pitcher, semilla 910, aproximadamente 60% ajuste, 10% parada, 10% calibración y 20% prueba. Ajuste, parada y calibración usan solo 2024-2025. Prueba usa 2026 de pitchers excluidos de todas esas funciones. Se registran IDs y hashes.",
        f"Población de prueba: {audit['test_rows']:,} lanzamientos de {audit['test_pitchers']} pitchers. No se permite historial de arsenal para los pitchers de parada, calibración y prueba. Es un escenario cold start, más exigente que un pitcher con historia conocida.",
        "Se reentrena la arquitectura seleccionada, no se evalúan los modelos desplegados sobre pitchers que ya conocieron. Los pesos de mezcla y métodos de calibración se congelan; los parámetros del calibrador se ajustan otra vez en pitchers de calibración. Las tareas contextuales se auditan con controles CatBoost de 250 iteraciones máximas, no como una reproducción exacta de todas las mezclas heredadas v5.",
        "La tabla muestra AUC para clasificación y RMSE para regresión. Ganancia e intervalo comparan MSE/Brier contra una constante aprendida en fit. El bootstrap remuestrea pitchers, con 1,000 repeticiones. Las tareas de carreras también se comparan contra promedio por conteo.",
        "Los pitchers son disjuntos, pero pueden compartir juegos: esta auditoría mide transferencia a pitchers no vistos, no independencia adicional de parque o juego. El diseño fue creado después de observar versiones anteriores; no se afirma confirmación futura independiente."],
       [(["Tarea","N","AUC/RMSE","Ganancia","IC 95%"],validation_rows)]),
      ("5. Entorno: asociaciones y soporte",[
        "Se comparan categorías contra No Altitude dentro de celdas del mismo pitcher, año, tipo de pitch, lado del bateador y conteo. Cada celda necesita al menos tres observaciones por entorno; el peso es el mínimo de ambos tamaños. Se exigen cinco pitchers con solapamiento para emitir un contraste.",
        "La diferencia es media de categoría menos No Altitude, ponderada sobre las celdas comparables. Los intervalos remuestrean pitchers completos 1,000 veces. La población es la que tiene soporte compartido, no toda la liga. Tasas se muestran como fracciones: 0.01 equivale a un punto porcentual.",
        "Se analizan las tres temporadas como evidencia descriptiva, incluidas observaciones utilizadas en desarrollo. No es un resultado fuera de muestra. Los 96 contrastes son exploratorios y no tienen corrección por comparaciones múltiples; no se declaran hipótesis causales validadas.",
        "La tabla resume Extreme Altitude. Diferencias de IVB y HB son firmadas, no cambios universales de magnitud de movimiento. Persisten posibles diferencias de dispositivo, forma específica, clima, bateadores y selección de uso. La coincidencia por tipo no elimina esos factores.",
        "Un cambio de categoría en el simulador conserva la física observada y modifica únicamente el predictor contextual. No transporta trayectoria ni carry. Para comparar Harp Helú nominalmente y realizar park holdout hace falta un mapeo oficial de estadios."],
       [(["Resultado","Diferencia","IC 95%","Pitchers"],env_rows)]),
      ("6. Baselines, calibración y fronteras",[
        "El modelo físico dispone de menos contexto que el baseline por conteo. En los modelos de carreras vigentes, heredados de v5, el físico no supera ese baseline en 2026; los modelos con ubicación y entorno sí lo superan. Se evita presentar el resultado contextual como si fuera precisión física.",
        "La tabla corresponde al modelo desplegado, no a la auditoría reentrenada de la página 4. Como las tres predicciones de carreras se conservaron hasta v8, las métricas se consolidan desde la evaluación original v5 sobre la misma temporada; se conserva su procedencia.",
        "Brier evalúa el error probabilístico total; AUC evalúa ordenamiento y ECE la concordancia por bins. En v8 ECE de whiff dado swing empeora de 0.012782 a 0.021505 y de bola en juego de 0.007973 a 0.013189, pese a mejorar Brier y AUC. Se muestran ambas caras del resultado.",
        "EV empeora de 15.295926 a 15.301194 mph de RMSE en el benchmark; el intervalo de diferencia incluye cero. No se revierte selectivamente usando 2026. El evento HR es raro; accuracy no sería una medida adecuada de utilidad.",
        "La validación por parque sigue pendiente por ausencia de identificadores. Los intervalos no incorporan incertidumbre de entrenamiento ni corrigen reutilización de datos. La referencia histórica tampoco equivale a una normalización demostrada para cada estadio."],
       [(["Modelo vigente","RMSE","RMSE conteo","Ganancia vs conteo"],[[r.task,number(r.rmse,5),number(r.count_baseline_rmse,5),f"{r.mse_skill_vs_count:.2%}"] for r in baseline.itertuples()])]),
      ("7. Casos, perfiles y uso del dashboard",[
        "Los casos son pitchers anonimizados reales, elegidos con reglas declaradas y usando scores predichos de 2026. Sirven para demostrar el flujo de revisión; no son descubrimientos confirmados de talento ni recomendaciones de contrato.",
        *[f"{c['category']} - {c['pitcher']}: {c['n_pitches']} pitches en {c['n_games']} juegos; Stuff+ {c['stuff_plus']:.1f}, Pitching+ {c['pitching_plus']:.1f}. {c['reason']}" for c in cases],
        "El primer caso debe pasar a revisión de video y rol. En el segundo se debe revisar ubicación y contexto; la diferencia entre índices con referencias distintas no es una cantidad causal de carreras perdidas. En el tercero un solo juego no permite un intervalo entre juegos: se informa como no estimable, no como certeza perfecta.",
        "El perfil físico descriptivo se extrae del 10% superior de Pitching+ dentro de tipo, mano y entorno, con al menos 100 pitches y tres pitchers. Se publican cuartiles de velocidad, spin, IVB, HB, altura y extensión. No es un óptimo causal: incluye selección por ubicación y por el propio modelo.",
        "El mapa muestra medias por pitcher/tipo/entorno, con HB normalizado por mano. Las fichas incluyen atribuciones SHAP que reconstruyen exactamente el Stuff+ de los casos; explican el modelo, no efectos causales. El simulador compara tres escenarios con física fija y muestra soporte del tipo/mano; una advertencia señala escasez o velocidad fuera del rango de medias observado."],[]),
      ("8. Reproducción y plan de decisión",[
        "Reproducción: instalar requirements-entrega.txt; ejecutar validar_pitchers_v8.py, analisis_operativo_v8.py, explicar_casos_v8.py y generar_paquete_v8.py. La auditoría no sobrescribe una ejecución iniciada. Abrir dashboard_stuff_plus.py con Streamlit. Los modelos desplegados v8 y sus hashes se mantienen intactos.",
        "El manifiesto registra hashes y archivos. El ZIP incluye scripts, documentación, predicciones y resultados agregados; excluye mediciones y outcomes originales, listas de IDs de auditoría y modelos binarios. Los modelos completos quedan localmente para revisión autorizada. El README distingue la demo local del paquete compartible.",
        "Secuencia de demo: explicar la calidad física; abrir una ficha; recorrer el mapa de movimiento; comparar escenarios de altitud; revisar tres casos; cerrar con la auditoría de pitchers y los límites de estadio. La decisión propuesta es priorizar revisión, no ejecutar una contratación.",
        "Pendiente externo: mapeo de estadio por juego, fechas, orden de PA/pitches y ocupación de bases. Con ello se podrá estudiar transporte de forma, validación por parque y objetivos de carreras con estados completos. El análisis actual identifica categorías, no Harp Helú.",
        "La convocatoria publicada solicita documento técnico de 6-10 páginas, scores, perfil, recomendaciones y simulador. La entrega anunciada es el 22 de octubre de 2026. El equipo debe completar integrantes y correos, verificar elegibilidad y preparar su envío. Este proceso no envía correos ni publica datos.",
        "Fuentes: convocatoria ISAC Diablos Rojos (https://www.isac-app.com/competition-details/hackathon-diablos-rojos.html), consultada el 17/10/2026; diccionario de datos; reportes y protocolos locales v5-v8. Las afirmaciones empíricas de este documento provienen de los artefactos identificados en el manifiesto."],[])
    ]
    pages[6][1].append("Actualización de interfaz 20/10/2026: probabilidades y riesgos con denominadores explícitos, diferencias entre escenarios, explicación SHAP del lanzamiento simulado verificada contra su Stuff+, baseline por conteo y descarga de scores. El catálogo de estadios documenta altitudes publicadas sin adjudicar juegos anónimos.")
    styles=getSampleStyleSheet()
    styles['BodyText'].fontSize=9
    styles['BodyText'].leading=12
    styles['BodyText'].spaceAfter=8
    story=[]; markdown=['# Documento técnico v8 — entrega vigente','']
    for index,(title,paragraphs,tables) in enumerate(pages):
        if index: story.append(PageBreak())
        story.append(Paragraph(escape(title),styles['Heading1']))
        markdown += ['## '+title,'']
        for paragraph in paragraphs:
            story.append(Paragraph(escape(paragraph),styles['BodyText']))
            markdown += [paragraph,'']
        for headings,rows in tables:
            content=[[Paragraph(escape(str(x)),styles['BodyText']) for x in headings]]+[[Paragraph(escape(str(x)),styles['BodyText']) for x in r] for r in rows]
            widths=[180]+[(A4[0]-84-180)/(len(headings)-1)]*(len(headings)-1)
            table=Table(content,colWidths=widths,repeatRows=1)
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9edf3')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.25,colors.lightgrey),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
            story.extend([Spacer(1,6),table])
            markdown += ['| '+' | '.join(headings)+' |','|'+'|'.join(['---']*len(headings))+'|']
            markdown += ['| '+' | '.join(map(str,r))+' |' for r in rows]
            markdown += ['']
    pdf=OUT/'DOCUMENTO_TECNICO_V8.pdf'
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8)
        canvas.drawString(42,26,'Diablos · v8 · benchmark 2026 reutilizado')
        canvas.drawRightString(A4[0]-42,26,str(doc.page))
    SimpleDocTemplate(str(pdf),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=35,bottomMargin=42).build(story,onFirstPage=footer,onLaterPages=footer)
    count=len(PdfReader(pdf).pages)
    assert 6<=count<=10,f'PDF fuera del límite: {count}'
    (OUT/'DOCUMENTO_TECNICO_V8.md').write_text('\n'.join(markdown),encoding='utf-8')
    recommendations=['# Recomendaciones operativas vigentes v8','',
       'Objetivo: priorizar revisión deportiva. Los índices son predicciones, no causalidad ni garantía de rendimiento futuro.','']
    for c in cases:
        ci=f"[{c['ci_low']:.1f}, {c['ci_high']:.1f}]" if c['ci_low'] is not None else 'no estimable con un solo juego'
        recommendations += [f"## {c['category']}: {c['pitcher']}",'',c['reason'],
          f"Muestra: {c['n_pitches']} pitches, {c['n_games']} juegos. Stuff+ {c['stuff_plus']:.1f}; Pitching+ {c['pitching_plus']:.1f}; IC {ci}.",'',
          'Acción: revisar video, comando por zona/conteo y rol. Solicitar historial de salud y datos nuevos. Cambiar la recomendación si el perfil no se sostiene con más juegos o cambian las condiciones de uso.','']
    recommendations += ['## Entorno y perfiles','',
       'Usar entorno_ajustado.csv para asociaciones dentro de soporte compartido. No descartar familias completas por una hipótesis de altitud. Los perfiles físicos son cuartiles descriptivos de grupos con buen score; no umbrales universales ni un perfil confirmado de Harp Helú.',
       'El análisis no identifica estadio, efecto causal ni un óptimo de contratación. La diferencia entre Stuff+ y Pitching+ es un contraste descriptivo de índices, no una cantidad causal de carreras.','',
       '## Demostración sugerida (10 minutos)','',
       '1. Problema y límites (1 min).\n2. Ficha y mapa (2 min).\n3. Escenarios y evidencia de entorno (2 min).\n4. Tres casos y acciones (3 min).\n5. Validación y preguntas abiertas (2 min).','',
       '## Preguntas para la organización','',
       'Solicitar mapeo juego-estadio-altitud, fechas, secuencia de PA y estados de bases. Confirmar definición esperada de whiff y alcance de comparación por parque con buckets. Preguntas preparadas; no enviadas.']
    (OUT/'RECOMENDACIONES_V8.md').write_text('\n'.join(recommendations),encoding='utf-8')
    (OUT/'README_ENTREGA.md').write_text('''# Entrega v8

Documento técnico vigente: DOCUMENTO_TECNICO_V8.pdf. Recomendaciones: RECOMENDACIONES_V8.md. Los documentos antiguos v3/v4 no forman parte del paquete.

## Reproducir localmente

Instalar `requirements-entrega.txt`. Con el dataset autorizado y los artefactos locales v8 disponibles, ejecutar `validar_pitchers_v8.py`, `analisis_operativo_v8.py`, `explicar_casos_v8.py`, `generar_paquete_v8.py` y `verificar_entrega_v8.py`. La auditoría exige una salida nueva y no sobrescribe un protocolo iniciado. Ejecutar `python -m streamlit run dashboard_stuff_plus.py` desde la raíz.

El ZIP contiene scores derivados por lanzamiento (solo IDs anónimos y predicciones), agregados, código y documentación. Para entrenamiento desde cero se necesitan el dataset de la organización y los artefactos parentales generados por la cadena v5-v8. No incluye mediciones/outcomes originales ni modelos binarios. El dashboard completo funciona en el workspace local con esos modelos. Los scores completos se conservan localmente en `stuff_plus_output_v8/scores_pitch_v8.parquet`.

Las cinco mejoras están implementadas: auditoría de pitchers, análisis de entorno, interfaz operativa, tres casos y documentación. Comparación nominal de Harp Helú y park holdout permanecen limitados por datos faltantes. No hay efecto causal confirmado ni benchmark futuro intacto.

## Antes de enviar

Completar nombres, correos y elegibilidad del equipo; confirmar la modalidad de acceso a modelos y scores detallados con la organización. No se envía correo automáticamente. La fecha publicada consultada es 22/10/2026.
''',encoding='utf-8')
    with (OUT/'README_ENTREGA.md').open('a',encoding='utf-8') as handle:
        handle.write('\n## Actualización del dashboard (20/10/2026)\n\nEl simulador expone nueve probabilidades, riesgos y una explicación SHAP local comprobada. Incluye diferencias por categoría, baseline por conteo y scores descargables. La pestaña Estadios y altitudes compara referencias geográficas con fuentes; no infiere estadio desde una categoría. Consultar ESTADIOS_Y_ALTITUDES.md y AUDITORIA_ESTADIOS.json. Ejecutar `python estadios_v8.py` antes de regenerar el paquete para actualizar cobertura. El mapeo por juego necesita evidencia externa explícita.\n')
    source_dir=OUT/'codigo';source_dir.mkdir(exist_ok=True)
    names=['validar_pitchers_v8.py','analisis_operativo_v8.py','explicar_casos_v8.py','generar_paquete_v8.py','verificar_entrega_v8.py','dashboard_entrega_v8.py',
           'dashboard_stuff_plus.py','dashboard_stuff_plus_v5.py','dashboard_stuff_plus_v6.py','dashboard_stuff_plus_v7.py','dashboard_stuff_plus_v8.py',
           'requirements-entrega.txt','requirements-dashboard.txt','requirements-hackathon.txt','README.md','docs/archivo/README_MODELO_V6.md','docs/archivo/README_MODELO_V7.md','docs/archivo/README_MODELO_V8.md']
    names += [f'{prefix}_v{version}.py' for version in [5,6,7,8] for prefix in ['entrenar_stuff_plus','verificar_modelo','reportar_mejora']]
    names += ['tests/__init__.py','tests/test_entrega_v8.py','tests/test_stuff_plus_v8.py','dashboard_revision_v8.py','estadios_v8.py','explicacion_simulador_v8.py','tests/test_estadios_v8.py','tests/test_dashboard_revision_v8.py']
    for name in names:
        if (ROOT/name).exists():
            (source_dir/name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT/name,source_dir/name)
    published=[p for p in OUT.iterdir() if p.is_file() and p.suffix in ['.csv','.md','.pdf']]
    published += [OUT/'casos_scouting.json',OUT/'analisis_manifest.json',OUT/'METRICAS_BENCHMARK_V8.json',OUT/'verificacion_shap.json',OUT/'validacion_pitchers/metricas.json',OUT/'validacion_pitchers/verificacion.json']
    if (OUT/'AUDITORIA_ESTADIOS.json').exists(): published.append(OUT/'AUDITORIA_ESTADIOS.json')
    published += [source_dir/name for name in names if (source_dir/name).is_file()]
    manifest={'version':8,'pdf_pages':count,'files':{str(p.relative_to(OUT)).replace('\\','/'):v8.v6.file_hash(p) for p in published},
              'source_sha256':protocol['source_sha256'],'raw_data_included':False,'predictions_included':True,'models_included':False,'benchmark_reused':True}
    v8.v6.json_write(OUT/'MANIFIESTO.json',manifest)
    with zipfile.ZipFile(ROOT/'ENTREGA_DIABLOS_V8.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
        for file in published+[OUT/'MANIFIESTO.json']: archive.write(file,str(file.relative_to(OUT)))
    print(f'Paquete generado, PDF {count} páginas, {len(published)} archivos')


if __name__=='__main__': main()
