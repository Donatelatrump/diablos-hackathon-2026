"""Documento tecnico y paquete ejecutable con evidencia actual.

Requiere las tres evaluaciones completas. Excluye mediciones y outcomes originales.
"""
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json
import shutil
import subprocess
import sys

import pandas as pd
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / 'reports/v9_estadios'
RUN = ROOT / 'stuff_plus_output_v9_estadios'
PACKAGE = ROOT / 'entrega_estadios'
LABELS = {'stuff_run_value': 'Fisica', 'xrunvalue': 'Ubicacion', 'arsenal_run_value': 'Arsenal',
    'environment_run_value': 'Combinado', 'whiff': 'Swing fallido', 'whiff_given_swing': 'Fallo dado swing',
    'ball_in_play': 'Bola en juego', 'groundball_given_in_play': 'Rodado dado juego',
    'weak_contact': 'Contacto debil', 'hard_contact': 'Contacto duro',
    'home_run_per_pitch': 'Jonron', 'called_strike': 'Strike cantado', 'chase': 'Swing fuera de zona'}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def make_pdf(audits):
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BodyD', fontName='Helvetica', fontSize=10, leading=14, spaceAfter=10, textColor=colors.HexColor('#20242b')))
    styles.add(ParagraphStyle(name='SmallD', fontName='Helvetica', fontSize=8, leading=10.5, spaceAfter=7))
    styles.add(ParagraphStyle(name='CellD', fontName='Helvetica', fontSize=8, leading=10))
    styles.add(ParagraphStyle(name='HeadD', fontName='Helvetica-Bold', fontSize=21, leading=25, spaceAfter=17, textColor=colors.HexColor('#ad1830')))
    def p(text, small=False):
        return Paragraph(text, styles['SmallD' if small else 'BodyD'])
    def title(text):
        return Paragraph(text, styles['HeadD'])
    def table(rows, widths):
        t = Table([[Paragraph(escape(str(value)), styles['CellD']) for value in row] for row in rows], colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([('BACKGROUND', (0,0),(-1,0),colors.HexColor('#f2e6e9')),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f5f6f8')]),
            ('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        return t
    temporal = {r['task']: r for r in audits['season']}
    harp = {r['task']: r for r in load(REPORT/'metricas_harp_helu.json')}
    support = load(REPORT/'protocolo_perfiles.json')
    meta = load(RUN/'bundle.json')
    profiles = pd.read_csv(REPORT/'perfiles_fisicos.csv')
    deltas = pd.read_csv(REPORT/'deltas_por_perfil.csv')
    pages = []
    pages.append([title('1. Calidad de pitcheo para Harp Helu'),
        p('<b>Una herramienta para revisar lanzamientos, repertorios y prospectos.</b> El sistema estima resultados esperados a partir de fisica medida, ubicacion, historia del arsenal y estadio. El coach puede comparar escenarios y llevar a video los perfiles con evidencia suficiente.'),
        table([['Pregunta deportiva','Salida'],['Que calidad fisica tiene el lanzamiento','Stuff+'],['Que aporta su ubicacion','Location+'],['Como se evalua el conjunto','Pitching+ y probabilidades'],['Que cambia entre estadios','Deltas por perfil, soporte e intervalos']], [6.4*cm,10.2*cm]),Spacer(1,14),
        p('<b>Resultado principal.</b> El modelo combinado reduce el error cuadratico medio frente al promedio por conteo en '+f"{temporal['environment_run_value']['vs_baseline']['gain']:.2%}"+'. La seleccion de arsenal y entorno conserva la capa anterior cuando no confirma una mejora adicional.'),
        p('El Pitching+ de carreras no cambia al modificar solo el estadio. Varias probabilidades y el nuevo indice integral multiobjetivo si pueden cambiar. El indice integral no reemplaza la evidencia de error de carreras ni demuestra una ventaja causal de Harp Helu.'),
        p('El trabajo integra sabermetria para valorar resultados esperados, fisica para formular hipotesis y aprendizaje supervisado para medir asociaciones en la LMB. La literatura de Nathan explica que la densidad del aire afecta fuerzas aerodinamicas y movimiento; no determina por si sola la magnitud para este dataset [1, 2].'),
        p('Entrega actualizada: modelos por estadios, validacion temporal y auditorias independientes por pitcher y parque, perfiles descriptivos, recomendaciones, simulador y archivos reproducibles. Los resultados siguen sujetos a las limitaciones descritas en la pagina 8.')])
    pages.append([title('2. Datos, identificacion y alcance'),
        table([['Temporada','Lanzamientos','Juegos','Uso'],['2024','243,254','833','Desarrollo'],['2025','256,144','839','Desarrollo'],['2026','135,604','455','Evaluacion reutilizada']], [3*cm,4*cm,3*cm,6.6*cm]),Spacer(1,13),
        p('La clasificacion cubre 601,120 de 635,002 lanzamientos y 2,009 de 2,127 juegos. Harp Helu tiene 36,399 lanzamientos: 30,394 en desarrollo y 6,005 en 19 juegos evaluados de 2026. Hay 33,882 lanzamientos pendientes de identificar.'),
        p('El mapeo del commit 9e75629 relaciona year + game_anon_id con estadio. Cruza timestamps UUID v1, calendario publico y jugadas de la misma media entrada. Es inferido y auditado, no una llave oficial. Se preservan las 84 columnas originales y sus valores; los pendientes no reciben un estadio inventado.'),
        p('Fisica: velocidad, IVB/HB, spin circular, release, extension, forma normalizada por mano y tipo de pitch. Ubicacion: coordenadas en plato, conteo y lado del bateador. Arsenal: diferencias respecto a recta primaria, uso y confiabilidad de historia. Entorno: categoria de altitud y stadium_id.'),
        p('Los IDs de pitcher y juego sirven para particiones, historia y agregados; no entran como predictores. El identificador del estadio es una categoria contextual estable. No se incorpora el resultado del lanzamiento como entrada de inferencia.'),
        p('Existen 150 filas de desarrollo y 3,122 de evaluacion sin ID de pitcher. Se conservan en la prueba temporal con historia ausente y se excluyen de la auditoria de pitchers. Las filas sin parque se excluyen cuando definen el park holdout.'),
        p('IVB y HB representan la forma observada del lanzamiento, no una medicion instantanea en el release. Las PA se reconstruyen por orden UUID, bateador, media entrada y conteo; se excluyen secuencias incompletas o ambiguas. No se conocen completamente bases, clima ni densidad del aire.')])
    pages.append([title('3. Modelos, targets y escala'),
        p('Trece tareas CatBoost: cuatro regresiones de carreras y nueve clasificadores. Profundidad 6, learning rate 0.045, L2=20, hasta 400 iteraciones y parada temprana tras 35 sin mejora. Las regresiones aprenden el residual respecto al baseline de ajuste; las clasificaciones minimizan Logloss sin pesos de clase.'),
        p('El target run_value_proxy usa pesos fijos: out -0.27, sencillo +0.47, doble +0.78, triple +1.09, jonron +1.40, walk +0.30 y HBP +0.33; para pitches sin resultado terminal emplea pesos pequenos de ball/strike. Es un proxy, no RE24 empirico.'),
        table([['Indice','Valor que se normaliza'],['Stuff+','-RV fisico'],['Location+','RV fisico - RV con ubicacion'],['Pitching+','-RV contextual seleccionado']], [4*cm,12.6*cm]),Spacer(1,12),
        p('<b>Indice = 100 + 10 x (valor - media de referencia) / desviacion de referencia.</b> La referencia se estima en calibracion y queda fija. 110 es una desviacion estandar favorable, no 10% mas outs. Los tres indices no se suman.'),
        p('Se conserva referencia fija para nuevos escenarios. Ademas se entrega una vista historica centrada por temporada y estadio, usando predicciones sin etiquetas de prueba. Ambas escalas se distinguen en la interfaz y archivos; no se deben mezclar ni comparar con versiones anteriores.'),
        p('Los targets incluyen whiff, whiff dado swing, bola en juego, rodado dado juego, contacto debil/duro dados contacto y velocidad observada, HR por pitch, strike cantado y swing fuera de zona por pitch. Whiff sigue el diccionario: swing y fallo. Contacto duro usa 95 mph; no se denomina barrel.'),
        p('El complemento incorpora P(out al cerrar PA), indice integral de ocho objetivos y escala por temporada/estadio. Los indices originales conservan su significado; el nuevo indice combina utilidades estandarizadas, no suma probabilidades incompatibles. Formulas, resultados y limites en la pagina 9.')])
    pages.append([title('4. Protocolo y pruebas independientes'),
        table([['Fase de desarrollo','Juegos','Uso'],['Ajuste','50%','Estimar modelo y baseline'],['Parada temprana','15%','Elegir numero de arboles'],['Calibracion','15%','Ajustar probabilidades y referencia'],['Busqueda','10%','Elegir candidato'],['Confirmacion','10%','Aceptar o rechazar la mejora']], [4.5*cm,2.3*cm,9.8*cm]),Spacer(1,12),
        p('Se separan juegos completos en cada temporada. La historia de arsenal se calcula solo con juegos de ajuste de temporadas anteriores. Las decisiones y la escala se congelan antes de leer el conjunto de evaluacion. Hashes permiten detectar cambios de datos, codigo y modelos.'),
        p('Se prueban prediccion cruda, mezcla hacia baseline y calibracion sigmoidal. Se exige ganancia minima 0.1% en busqueda y confirmacion, IC95% positivo por juegos, estabilidad por temporada y log loss no inferior en clasificacion. Arsenal compite contra ubicacion; entorno contra arsenal. Si falla, hereda la capa anterior.'),
        p('<b>Temporada:</b> desarrollo 2024-2025; evaluacion 2026. Es un benchmark reutilizado en el proyecto, no evidencia futura intacta.'),
        p('<b>Pitcher:</b> hash fijo reserva aproximadamente 20% de pitchers; se excluye toda su historia del desarrollo. Se reentrenan las trece tareas y se evalua a esos pitchers en 2026.'),
        p('<b>Parque:</b> se excluye Harp Helu de todo el desarrollo, se reentrenan las trece tareas y se evalua Harp Helu de 2026. Su categoria de altitud puede verse en otros parques. Es una prueba de transferencia a un parque no visto, no una estimacion causal de altitud.'),
        p('Los intervalos de rendimiento remuestrean juegos o pitchers segun la auditoria. Los deltas por perfil remuestrean juegos con el modelo fijo. Ninguno incluye toda la incertidumbre de volver a entrenar.')])
    rows = [['Tarea','n liga','RMSE/Brier liga','Ganancia liga','RMSE/Brier Harp']]
    for task in LABELS:
        r, h = temporal[task], harp[task]
        rows.append([LABELS[task],str(r['n']),f"{r['metrics'].get('rmse',r['metrics'].get('brier')):.5f}",f"{r['vs_baseline']['gain']:.2%}",f"{h['metrics'].get('rmse',h['metrics'].get('brier')):.5f}"])
    pages.append([title('5. Resultados y calibracion'),table(rows,[4.5*cm,2.1*cm,3.6*cm,2.8*cm,3.6*cm]),Spacer(1,11),
        p('RMSE corresponde a regresiones; Brier a probabilidades. Ganancia usa el baseline especifico de cada tarea. El modelo fisico supera su media global, pero no el baseline por conteo, que conoce informacion adicional. El combinado si supera el baseline por conteo.',True),
        Image(str(REPORT/'calibracion_actual.png'),width=16.5*cm,height=5.25*cm),
        p('Curvas descriptivas de liga: bins de probabilidad de amplitud 0.1, minimo 30 observaciones por punto. Los archivos incluyen calibracion y metricas por estadio. Brier combina calibracion y discriminacion; no demuestra por si solo buena calibracion.',True),
        p('En Harp Helu, HR medio predicho: 0.695%; observado: 0.866% (52 HR / 6,005 pitches). Este desfase limita una lectura optimista del riesgo. No se recalibra usando las etiquetas del benchmark.',True)])
    rows = [['Prueba / tarea','n','RMSE/Brier','Ganancia / IC95%']]
    for mode in ['pitcher','park']:
        for r in audits[mode]:
            if r['task'] not in ['stuff_run_value','environment_run_value','whiff','hard_contact','home_run_per_pitch']:
                continue
            g=r['vs_baseline']; m=r['metrics']; fmt=lambda x: f'{x:.1%}' if x is not None else 'n/e'
            rows.append([mode+' / '+LABELS[r['task']],str(r['n']),f"{m.get('rmse',m.get('brier')):.5f}",f"{fmt(g['gain'])} [{fmt(g['ci_low'])}, {fmt(g['ci_high'])}]"])
    pages.append([title('6. Robustez y aporte incremental'),table(rows,[5.6*cm,2*cm,3*cm,6*cm]),Spacer(1,13),
        p('Cada auditoria tiene modelos, calibracion y escala propios. Sus puntos Stuff+ no se mezclan directamente con la ejecucion temporal. Las tablas completas de las trece tareas se adjuntan; esta pagina presenta tareas representativas.'),
        p('En la ejecucion temporal, ubicacion mejora MSE frente a fisica en 3.94%. Arsenal y entorno heredan la prediccion anterior: delta de carreras igual a cero por construccion. No se presenta ese cero como prueba de ausencia de efecto fisico.'),
        p('El mapeo por estadio elimina una limitacion de identificacion, pero no controla todos los factores de seleccion, rival, defensa o condiciones atmosfericas. La generalizacion se juzga con estas pruebas y con muestras posteriores, no con una etiqueta de estadio agregada al modelo.'),
        p('La auditoria por parque deja Harp Helu fuera del desarrollo y evalua solamente sus 19 juegos de 2026. Ese tamaño limita la precision y no certifica transferencia a todos los estadios de la liga.')])
    rows = [['Perfil derecho','Velocidad p25-p75','IVB p25-p75','n top']]
    for kind in ['Four-Seam','Sinker','Slider','Changeup']:
        r=profiles.loc[profiles.pitch_type.eq(kind)&profiles.hand.eq('Right')].iloc[0]
        rows.append([kind,f'{r.RelSpeed_p25:.1f}-{r.RelSpeed_p75:.1f} mph',f'{r.InducedVertBreak_p25:.1f}-{r.InducedVertBreak_p75:.1f} in',str(int(r.n_top))])
    pages.append([title('7. Perfiles y decisiones deportivas'),
        p(f"Se comparan {support['supported_pitches']:,} pitches con soporte de desarrollo entre Harp y la referencia equiponderada Veracruz-Campeche-Cancun. Se exigen 300 pitches y 10 juegos por grupo/tipo/mano y rangos marginales compartidos 1-99% de velocidad, IVB, HB y spin."),
        p('Los deltas conservan fisica, ubicacion y arsenal del mismo lanzamiento. Los intervalos describen variacion entre juegos con el modelo fijo; son exploratorios, sin correccion de comparaciones multiples ni garantia de soporte multivariado.'),
        table(rows,[4.1*cm,4.8*cm,4.8*cm,2.9*cm]),Spacer(1,11),
        p('Rangos descriptivos del cuartil central del 10% con mejor Stuff+ fisico en calibracion. El archivo completo contiene ambas manos, spin, HB y diferenciales de arsenal. No combinar extremos como un pitch artificial ni afirmar ventaja exclusiva de Harp.',True),
        p('<b>Scouting:</b> comparar tipo y mano, verificar mediciones completas del mismo pitch, historial de recta primaria, volumen de juegos y ubicacion. Llevar a video perfiles favorables y desfavorables; salud y rol requieren informacion externa.'),
        p('<b>Coaching:</b> revisar juntos swing fallido, contacto duro y jonron. Si falta soporte o el intervalo cruza cero, pedir mas datos. Un cambio de probabilidad no justifica por si solo aumentar el uso del repertorio.'),
        p('Las predicciones de HR resultan ligeramente menores en el escenario Harp que en la referencia, manteniendo forma fija. Dado el desfase de calibracion observado, esto no respalda afirmar que Harp reduzca el riesgo real. El resultado puede reflejar condicionamiento y factores no medidos.'),
        p('No se demuestra una mezcla optima de arsenal ni ganadores/perdedores de Pitching+ por altitud. Las recomendaciones son una guia de revision, con las diferencias y limites visibles.')])
    pages.append([title('8. Uso, reproduccion y limites'),
        p('<b>Para el coach.</b> Con Python 3.12 instalado, abrir ABRIR_DASHBOARD.bat. La primera apertura prepara el entorno y requiere internet. Elegir "Comparar un lanzamiento". La primera vista ofrece perfiles y decisiones para Harp; el simulador permite introducir mediciones y comparar hasta tres estadios. La ayuda explica 100 como referencia y muestra probabilidades con su denominador.'),
        p('<b>Reproduccion.</b> El paquete incluye codigo, dependencias, modelos seleccionados, scores derivados, metricas y catalogo. Instalar requirements-portable.txt; ejecutar python -m streamlit run dashboard_stuff_plus.py. Entrenar otra vez requiere el dataset autorizado, que no se incluye.'),
        p('Comandos de auditoria: completar_validaciones_estadios.py; analisis: analizar_perfiles_estadios.py; reporte Harp: reportar_estadios_v9.py; paquete: generar_entrega_estadios.py. Las salidas existentes se preservan. MANIFIESTO.json contiene hashes de los archivos empaquetados.'),
        p('<b>Limites que permanecen.</b> Benchmark 2026 reutilizado; proxy de carreras; mapeo inferido y cobertura incompleta; clima y bases no disponibles; soporte marginal y efectos no causales. El target PA solo se evalua en secuencias completas. Normalizar una muestra historica no mejora por si mismo la precision predictiva; el indice integral tiene pesos convencionales, no optimizados para utilidad deportiva.'),
        p('El reporte no certifica cumplimiento literal total de todos los targets de la convocatoria ni elegibilidad administrativa. El equipo debe completar nombres/correos, confirmar inscripcion y modalidad de envio. No se envia correo ni se publica el paquete automaticamente.'),
        p('<b>Datos.</b> Uso exclusivo de la competencia; no para apuestas. La entrega contiene resultados derivados y modelos, no mediciones ni outcomes originales. Los scores conservan IDs anonimos para trazabilidad y deben compartirse solo por el canal autorizado.'),
        p('<b>Fuentes.</b> [1] Alan M. Nathan, Baseball at High Altitude: https://baseball.physics.illinois.edu/Denver.html. [2] Nathan (2012), Determining Pitch Movement from PITCHf/x Data: https://baseball.physics.illinois.edu/Movement.pdf. [3] Convocatoria ISAC-Diablos 2026 y diccionario locales. [4] Mapeo auditado del commit 9e75629 y protocolos de esta entrega.',True),
        p('Origen enriquecido SHA-256: '+load(RUN/'protocolo.json')['source_sha256'],True)])
    complement=REPORT/'complemento'
    pa_audit=load(complement/'auditoria_pa.json')
    pa_rows=[['Prueba','Pitches / PA','Brier','Mejora vs conteo']]
    for mode in ['season','pitcher','park']:
        metric=load(complement/mode/'metricas.json')
        pa_rows.append([mode, f"{metric['pitches']:,} / {metric['pa']:,}", f"{metric['brier']:.5f}", f"{metric['gain']['gain']:.2%}"])
    pages.append([title('9. Outs, indice integral y ajuste'),
        p(f"<b>PA reconstruidas.</b> {pa_audit['valid_pa']:,} turnos completos y {pa_audit['labeled_pitches']:,} pitches etiquetados; {pa_audit['excluded_pa']:,} secuencias excluidas. Se exige inicio 0-0, conteos coherentes, mismo bateador/media entrada y cierre reconocido. Un out de corredor en un pitch no terminal invalida la secuencia; no se inventa un out por el nombre Strikeout."),
        p('<b>Target.</b> Al menos un out registrado en la jugada que cierra el turno, condicionado al lanzamiento actual. Incluye seleccion y doble play; no implica necesariamente bateador retirado. La etiqueta terminal se propaga hacia atras dentro de la PA completa, solo como objetivo; nunca entra como feature. El estimando y las metricas ponderan pitches, no cada PA por igual.'),
        table(pa_rows,[3*cm,5.2*cm,3.2*cm,5.2*cm]),Spacer(1,10),
        p('Un clasificador adicional por auditoria reutiliza las particiones de juegos y exclusiones v9; ajuste, parada, calibracion y seleccion separados. Se congela antes de evaluar. Features fisicas, ubicacion, arsenal y estadio; sin IDs de bateador/PA, timestamp ni resultados. El benchmark sigue siendo reutilizado.',True),
        p('<b>Indice integral.</b> U = (z(whiff) + z(chase) + z(strike cantado) + z(contacto debil) + z(rodado) - z(contacto duro) - z(RV contextual) + z(out PA)) / 8. Cada z usa media y desviacion de predicciones en calibracion. Indice = 100 + 10 z(U). Pesos iguales prefijados, sin optimizacion con resultados 2026. Es utilidad relativa, no una probabilidad; targets correlacionados pueden contar señales repetidas.'),
        p('<b>Temporada y estadio.</b> Los archivos scores_integrales.parquet y scores_normalizados.parquet incluyen 100 + 10 z por cohorte year/stadium_id. Con al menos 300 pitches y varianza positiva: media 100 y desviacion 10 en esa muestra. Parque ausente o pequeño: referencia de temporada. Se usan solo predicciones; nunca etiquetas del benchmark.'),
        p('Esta escala de revision es descriptiva y depende del cierre de la muestra. Para nuevos escenarios se usa la escala fija de calibracion, evitando cambiar la puntuacion al llegar nuevos pitches. No mezclar indices entre versiones ni interpretar el ajuste como efecto causal del parque. La UI ofrece ambas vistas con su referencia visible.')])
    story=[]
    for i,page in enumerate(pages):
        if i: story.append(PageBreak())
        story.extend(page)
    def footer(canvas, doc):
        canvas.saveState(); canvas.setFont('Helvetica',8); canvas.setFillColor(colors.HexColor('#565d6a'))
        canvas.drawString(1.8*cm,1.1*cm,'Diablos | Modelo por estadios | 27 octubre 2026')
        canvas.drawRightString(A4[0]-1.8*cm,1.1*cm,f'{doc.page} / {len(pages)}'); canvas.restoreState()
    target=REPORT/'DOCUMENTO_TECNICO_ESTADIOS.pdf'
    SimpleDocTemplate(str(target),pagesize=A4,rightMargin=1.8*cm,leftMargin=1.8*cm,topMargin=1.6*cm,bottomMargin=1.9*cm,
        title='Calidad de pitcheo para Harp Helu',author='Equipo del proyecto').build(story,onFirstPage=footer,onLaterPages=footer)
    if len(PdfReader(target).pages)!=len(pages):
        raise ValueError('El documento no tiene las paginas previstas; revisar antes de entregar')
    return target


def main():
    audits={}
    for mode,suffix in [('season',''),('pitcher','_pitcher'),('park','_park')]:
        folder=ROOT/('stuff_plus_output_v9_estadios'+suffix)
        audits[mode]=load(folder/'metricas.json')
        if len(audits[mode])!=13:
            raise ValueError(f'Auditoria {mode} incompleta')
        if mode!='season':
            dest=REPORT/mode; dest.mkdir(exist_ok=True)
            for name in ['metricas.json','protocolo.json','ablaciones.json','RESULTADOS.md']:
                shutil.copyfile(folder/name,dest/name)
    if '--conservar-pdf-revisado' in sys.argv:
        pdf=REPORT/'DOCUMENTO_TECNICO_ESTADIOS.pdf'
        review=load(REPORT/'REVISION_VISUAL.json')
        if digest(pdf)!=review['pdf_sha256']:
            raise ValueError('El PDF cambio desde su revision visual')
    else:
        pdf=make_pdf(audits)
    status = ['# Estado actualizado de la entrega', '',
        'Se completaron las mejoras de validación, análisis por perfil, recomendaciones, interfaz y documentación. Se mantienen límites metodológicos explícitos; no se certifica cumplimiento literal total ni elegibilidad del equipo.', '',
        '## Evaluaciones ejecutadas', '',
        '| Prueba | Tareas | Pitches | RMSE combinado | Mejora MSE vs conteo |',
        '|---|---:|---:|---:|---:|']
    for mode, records in audits.items():
        row = next(r for r in records if r['task'] == 'environment_run_value')
        status.append(f"| {mode} | {len(records)} | {row['n']} | {row['metrics']['rmse']:.6f} | {row['vs_baseline']['gain']:.2%} |")
    status += ['', '## Entregables disponibles', '',
        '- Modelos y scores por lanzamiento, pitcher y arsenal; escenarios Harp Helú.',
        '- Comparaciones por tipo y mano, soporte de desarrollo e intervalos por juegos.',
        '- Rangos físicos descriptivos y tres casos de scouting con acciones concretas.',
        '- Dashboard con lenguaje deportivo, explicaciones de escala, denominadores y avisos de muestra insuficiente.',
        '- Documento técnico actualizado de nueve páginas y paquete con modelos para inferencia sin dataset original.',
        '- Calibración y métricas por estadio; el desfase de HR en Harp se muestra explícitamente.', '',
        '## Límites y decisiones conservadas', '',
        '- Pitching+ de carreras mantiene delta cero por estadio al no confirmarse ganancia incremental; el índice integral puede variar. Ambos describen predicciones, no efectos causales.',
        '- No hay óptimo causal de contratación ni mezcla óptima de arsenal demostrados. Los perfiles son referencias descriptivas.',
        '- P(out al cerrar PA) implementado y validado en tres auditorías; excluye secuencias incompletas. Incluye selección/doble play, no necesariamente bateador retirado.',
        '- Índice integral de ocho objetivos con pesos iguales prefijados y referencia de calibración. No es una probabilidad ni prueba de superioridad del índice sobre RV.',
        '- Normalización descriptiva por temporada/estadio disponible, con respaldo a temporada en grupos pequeños o desconocidos. El simulador conserva escala prospectiva fija.',
        '- 2026 es reutilizado. La clasificación de estadio es inferida y tiene filas pendientes.',
        '- Las pruebas funcionales usan Streamlit AppTest. No hubo navegador conectado para inspección visual de la aplicación; no se afirma una revisión visual móvil/escritorio.',
        '- El PDF se renderiza y revisa por páginas antes de la entrega final. La verificación de integridad se registra en VERIFICACION_ACTUAL.json.',
        '- Nombres, correos, elegibilidad y envío quedan a cargo del equipo. No se ha enviado ni publicado el paquete.', '',
        'Consultar README_PRIMERO.md del paquete para abrir el tablero y RECOMENDACIONES_ACTUALES.md para la revisión deportiva.']
    (REPORT/'ESTADO_ENTREGA.md').write_text('\n'.join(status)+'\n',encoding='utf-8')
    PACKAGE.mkdir(exist_ok=True)
    # Explicit allowlist; original dataset and raw outcomes never enter the archive.
    sources=['dashboard_stuff_plus.py','dashboard_stuff_plus_v9.py','dashboard_perfiles_estadios.py',
        'dashboard_guia.py','dashboard_style.py','proyecto_io.py','entrenar_stuff_plus.py',
        'entrenar_stuff_plus_v5.py','entrenar_stuff_plus_v6.py','entrenar_stuff_plus_v9.py','explicar_v9.py',
        'actualizar_estadios.py','reportar_estadios_v9.py','analizar_perfiles_estadios.py','analizar_casos_scouting.py',
        'completar_validaciones_estadios.py','generar_entrega_estadios.py','verificar_entrega_estadios.py',
        'tests/__init__.py','tests/test_dashboard_navigation_helpers.py',
        'tests/test_stuff_plus_v9.py','tests/test_estadios_modelo_v9.py','tests/test_dashboard_estadios_v9.py',
        'tests/test_perfiles_estadios.py','completar_targets_pa.py','indice_integral.py','reportar_complemento_pa.py','tests/test_complemento_pa.py',
        'docs/guias/REENTRENAMIENTO_ESTADIOS.md','docs/guias/GUIA_PROYECTO.md','.streamlit/config.toml',
        'imgs/diablos-rojos-del-mexico-logo-brandlogos.net_kvga6c13n.svg']
    for name in sources:
        path=ROOT/name
        if not path.exists():
            raise FileNotFoundError(path)
        dest=PACKAGE/name; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(path,dest)
    for path in REPORT.rglob('*'):
        if path.is_file():
            dest=PACKAGE/path.relative_to(ROOT); dest.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(path,dest)
    allowed=['bundle.json','seleccion_congelada.json','protocolo.json','metricas.json','ablaciones.json',
        'RESULTADOS.md','HARP_HELU.md','estadios.csv','pitchers.csv','arsenal.csv','mapa_movimiento.csv',
        'scores_pitch_v9.parquet','scores_harp_helu_observados_2026.parquet',
        'escenarios_harp_helu_2026.parquet','arsenal_escenario_harp_helu.csv','metricas_harp_helu.json']
    for path in [RUN/name for name in allowed]+list((RUN/'modelos').glob('*.cbm')):
        dest=PACKAGE/path.relative_to(ROOT); dest.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(path,dest)
    from importlib.metadata import version
    requirements='\n'.join(name+'=='+version(name) for name in ['catboost','duckdb','numpy','pandas',
        'scikit-learn','streamlit','altair','pyarrow','matplotlib','reportlab','pypdf'])+'\n'
    # Record the actual training environment in addition to portable requirements.
    versions=subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True)
    (PACKAGE/'requirements-entorno-verificado.txt').write_text(versions,encoding='utf-8')
    (PACKAGE/'requirements-portable.txt').write_text(requirements,encoding='utf-8')
    launcher = r'''@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto dependencies
echo Preparando el tablero. Necesitas Python 3.12 instalado.
py -3.12 -m venv .venv
if exist ".venv\Scripts\python.exe" goto dependencies
echo No se encontro Python 3.12. Instala Python y vuelve a abrir este archivo.
pause
exit /b 1
:dependencies
if exist ".venv\dashboard-listo" goto run
echo La primera apertura descarga las herramientas. Necesitas internet.
".venv\Scripts\python.exe" -m pip install -r requirements-portable.txt
if errorlevel 1 goto failed
echo listo > ".venv\dashboard-listo"
:run
echo Abriendo el tablero. Manten esta ventana abierta mientras lo usas.
".venv\Scripts\python.exe" -m streamlit run dashboard_stuff_plus.py --server.address 127.0.0.1
if errorlevel 1 goto failed
exit /b 0
:failed
echo No fue posible abrir el tablero. Conserva este mensaje para el equipo de soporte.
pause
exit /b 1
'''
    (PACKAGE/'ABRIR_DASHBOARD.bat').write_text(launcher,encoding='ascii')
    (PACKAGE/'README_PRIMERO.md').write_text('# Entrega por estadios\n\nDocumento: reports/v9_estadios/DOCUMENTO_TECNICO_ESTADIOS.pdf.\n\n'
        '## Abrir el simulador\n\nCon Python 3.12 instalado, abre ABRIR_DASHBOARD.bat. La primera apertura crea un entorno local y descarga las herramientas; requiere internet y puede tardar varios minutos. '
        'Despues abre el mismo archivo cada vez que quieras usar el tablero. Manten su ventana abierta durante el uso. '
        'No necesita el dataset original para simular con los modelos incluidos.\n\n'
        'La vista inicial explica como leer los resultados. En Comparar un lanzamiento hay perfiles para Harp Helu, simulacion, mapa y evidencia.\n\n'
        '## Evidencia y limites\n\nTres evaluaciones completas de 13 tareas: temporada, pitchers reservados y Harp Helu excluido del entrenamiento. '
        'Consultar metricas, recomendaciones y ESTADO_ENTREGA.md. 2026 es un benchmark reutilizado; no hay efecto causal ni mejora incremental de carreras por estadio confirmados. '
        'Incluye probabilidad de out al cerrar el turno, indice integral y comparacion historica normalizada por temporada y estadio; consulta sus definiciones en la pagina 9 del PDF.\n\n'
        'El paquete contiene modelos y resultados derivados con identificadores anonimos. Uso exclusivo de la competencia. '
        'No contiene mediciones ni outcomes originales. Completar nombres y correos del equipo antes de enviar por el canal autorizado.\n',encoding='utf-8')
    manifest={str(p.relative_to(PACKAGE)).replace('\\','/'):digest(p) for p in sorted(PACKAGE.rglob('*'))
        if p.is_file() and p.name!='MANIFIESTO.json' and '__pycache__' not in p.parts
        and '.venv' not in p.parts and p.suffix not in ['.pyc','.log']}
    (PACKAGE/'MANIFIESTO.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    archive=ROOT/'ENTREGA_ESTADIOS_ACTUALIZADA.zip'
    with ZipFile(archive,'w',ZIP_DEFLATED) as z:
        for name in sorted([*manifest, 'MANIFIESTO.json']):
            z.write(PACKAGE/name,name)
    print(f'PDF: {pdf}\nPaquete: {archive}\nArchivos verificados: {len(manifest)}',flush=True)


if __name__ == '__main__':
    main()
