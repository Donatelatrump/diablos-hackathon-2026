"""Generate the eight-page technical document from measured v9 artifacts."""
from pathlib import Path
import json
from xml.sax.saxutils import escape

import pandas as pd
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"reports/v9"
RED = colors.HexColor("#ad1830")
DARK = colors.HexColor("#172332")
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TitleV9", fontName="Helvetica-Bold", fontSize=25, leading=29, textColor=DARK, spaceAfter=16))
styles.add(ParagraphStyle(name="HeadingV9", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=RED, spaceAfter=12))
styles.add(ParagraphStyle(name="BodyV9", fontName="Helvetica", fontSize=10.3, leading=14.5, spaceAfter=10, textColor=DARK))
styles.add(ParagraphStyle(name="SmallV9", fontName="Helvetica", fontSize=8.2, leading=10.7, spaceAfter=7))
styles.add(ParagraphStyle(name="CellV9", fontName="Helvetica", fontSize=8.2, leading=10.3, alignment=TA_LEFT))


def p(text, small=False):
    return Paragraph(text, styles["SmallV9" if small else "BodyV9"])


def table(rows, widths):
    content = [[Paragraph(escape(str(cell)), styles["CellV9"]) for cell in row] for row in rows]
    result = Table(content, colWidths=widths, repeatRows=1, hAlign="LEFT")
    result.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f2e6e9")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f4f6f8")]),
        ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 7),
        ("RIGHTPADDING", (0,0), (-1,-1), 7), ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6), ("LINEBELOW", (0,0), (-1,0), .7, RED)]))
    return result


def footer(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(RED)
    canvas.line(1.8*cm, 1.5*cm, width-1.8*cm, 1.5*cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(DARK)
    canvas.drawString(1.8*cm, 1.05*cm, "Diablos · ISAC 2026 | Experimento v9 | Benchmark reutilizado")
    canvas.drawRightString(width-1.8*cm, 1.05*cm, f"{doc.page} / 8")
    canvas.restoreState()


def main():
    metrics = json.loads((OUT/"metricas.json").read_text())
    protocol = json.loads((OUT/"protocolo.json").read_text())
    ablations = json.loads((OUT/"ablaciones.json").read_text())
    comparison = pd.read_csv(OUT/"comparacion_carreras_v8_v9.csv")
    audits = pd.read_csv(OUT/"auditorias.csv")
    verification = json.loads((OUT/"VERIFICACION.json").read_text())
    meta = json.loads((ROOT/"stuff_plus_output_v9/bundle.json").read_text())
    pages = []
    pages.append([
        Paragraph("Stuff+ para Diablos Rojos", styles["TitleV9"]),
        Paragraph("1. Pregunta deportiva y marco del reto", styles["HeadingV9"]),
        p("Estimamos la calidad esperada de un lanzamiento a partir de su física, ubicación, relación con el arsenal y categoría de altitud. El objetivo operativo es comparar perfiles y apoyar una revisión de scouting o coaching con evidencia que el usuario pueda interpretar."),
        p("<b>Tres preguntas.</b> Stuff+ evalúa física; Location+ representa la diferencia predictiva al conocer ubicación y contexto del enfrentamiento; Pitching+ incorpora arsenal y entorno. Un mismo pitch puede tener buena calidad física y mala ubicación. Los índices resumen expectativas, no juzgan un resultado aislado."),
        p("La sabermetría aporta la evaluación de resultados esperados; la física motiva estudiar la interacción entre movimiento y ambiente; la ciencia de datos permite estimarla con información histórica. La menor densidad del aire es una motivación del reto. Su magnitud específica en Harp Helú no se impone como parámetro conocido."),
        table([["Criterio ISAC", "Peso", "Evidencia del proyecto"],
               ["Calidad", "25%", "RMSE, probabilidades, calibración y baseline por conteo"],
               ["Robustez", "25%", "Temporada, pitchers reservados y categoría de entorno"],
               ["Arsenal + altitud", "25%", "Historia anterior y comparación incremental de capas"],
               ["Aplicabilidad", "25%", "Scores, simulador, mapa, guía y casos descriptivos"]], [4*cm, 1.6*cm, 11*cm]),
        Spacer(1, 12),
        p("<b>Estado de la evidencia.</b> Este es un experimento v9 reproducible, independiente de los bundles históricos. 2026 ya fue usado en versiones previas y sigue siendo un benchmark reutilizado. Una nueva partición no crea evidencia futura intacta."),
        p("Fuente del alcance: HTML local ‘2026 ISAC Hackathon – Diablos Rojos: Stuff Plus Model, Calidad de Pitcheo Ajustada por Entorno’. La guía docs/guias/GUIA_PROYECTO.md conserva el detalle de requisitos administrativos y restricciones.", True),
    ])
    pages.append([
        Paragraph("2. Datos, población y objetivos", styles["HeadingV9"]),
        table([["Temporada", "Pitches", "Juegos", "Pitchers identificados"], [2024, "243,254", 833, 541], [2025, "256,144", 839, 627], [2026, "135,604", 455, 550]], [3.5*cm, 4*cm, 4*cm, 5.1*cm]),
        Spacer(1, 12),
        p("Origen: Data/stuff_model_df.parquet. Se verificó SHA-256 contra el puntero original del repositorio. Los IDs anónimos se utilizan para unir filas, crear grupos de validación y agregar scores; no se incluyen como predictores."),
        p("Hay 150 pitches sin ID de pitcher en desarrollo y 3,122 en 2026. Se conservan en la evaluación temporal, con historia ausente. Se excluyen de la auditoría de pitchers para poder verificar identidades disjuntas. Filas sin la categoría que define un holdout de entorno también se excluyen de su desarrollo."),
        p("<b>Target de carreras.</b> run_value_proxy asigna pesos fijos por resultado: out −0.27, sencillo +0.47, doble +0.78, triple +1.09, HR +1.40; walk +0.30 y HBP +0.33. En pitches sin resultado terminal usa pesos pequeños de ball/strike. No es RE24 ni una estimación empírica de los 24 estados base-out."),
        p("<b>Targets binarios.</b> Whiff por pitch; whiff dado swing; bola en juego; rodado dado bola en juego; contacto débil (&lt;85 mph) y duro (≥95 mph) dados contacto y velocidad observada; HR por pitch; strike cantado; swing fuera de zona por pitch. Los denominadores condicionales restringen ajuste y evaluación, no la posibilidad de inferir para un pitch nuevo."),
        p("Whiff sigue is_whiff del diccionario: swing y fallo. El texto de convocatoria mezcla foul y miss; no se reinterpretó la etiqueta. Contacto duro no se denomina barrel. No se estima out dentro de PA sin reconstrucción fiable de PA y secuencia."),
        p("<b>Información faltante.</b> altitude_category no identifica estadio ni altitud exacta. No hay un mapeo oficial a Harp Helú, ni fechas/orden suficientes para inventar secuencias desde IDs. Por eso el park holdout permanece pendiente."),
    ])
    pages.append([
        Paragraph("3. Arquitectura y escala", styles["HeadingV9"]),
        table([["Capa", "Features", "Uso"],
               ["Física", "Velocidad, spin circular, release, extensión, forma, tipo y mano", "Stuff+"],
               ["Ubicación", "Física + posición en plato, bolas, strikes y lado del bateador", "Location+"],
               ["Arsenal", "Ubicación + diferenciales, uso e historia disponible", "Ablación de arsenal"],
               ["Entorno", "Arsenal + categoría de altitud", "Pitching+"]], [2.7*cm, 10.4*cm, 3.5*cm]),
        Spacer(1, 12),
        p("v9 separa arsenal de la definición física. El índice físico excluye ubicación, conteo, lado del bateador, altitud, IDs y outcomes. Usa IVB/HB observados como forma; esas mediciones no son una observación instantánea al release. Las transformaciones de movimiento se normalizan por mano y el spin se representa circularmente."),
        p("CatBoost aprende interacciones no lineales. Cada regresión minimiza RMSE sobre el residual respecto a su baseline: media global para física, media por conteo suavizada con 50 observaciones para las capas contextuales. La predicción final suma el baseline al residual. Ambos se ajustan solo con juegos de fit."),
        p(f"Configuración de esta ejecución: profundidad 6, learning rate 0.045, L2=20, hasta {protocol['iterations']} iteraciones y parada temprana tras 35 sin mejora. No se aplican pesos de clase. Las probabilidades incorporan contexto completo, salvo called_strike/chase que usan física y ubicación."),
        p("<b>Arsenal.</b> La recta primaria es Four-Seam o Sinker, según uso histórico. Sus medias se regularizan hacia pares históricos del mismo tipo/mano con peso n/(n+30). Las variables se construyen solo con temporadas anteriores de juegos de ajuste; la confiabilidad de historia se informa al modelo."),
        p("<b>Escala fija:</b> índice = 100 + 10 × (valor − media de referencia) / desviación de referencia. Los valores son −RV_físico; RV_físico − RV_ubicación; y −RV_entorno. Cada índice tiene su propia referencia de calibración y no se suma a los otros."),
        p("110 representa una desviación estándar favorable, no 10% más outs. No se recentra el año de evaluación. Si una referencia es constante, se informa 100 sin capacidad de ordenar pitches. Los puntos de v8 y v9 no son intercambiables."),
    ])
    pages.append([
        Paragraph("4. Validación, calibración y selección", styles["HeadingV9"]),
        table([["Rol de juegos", "Proporción", "Decisión permitida"],
               ["Fit", "50%", "Ajustar modelos y baselines"], ["Early stop", "15%", "Elegir número de árboles"],
               ["Calibración", "15%", "Ajustar sigmoid/shrinkage y referencia"], ["Búsqueda", "10%", "Elegir un solo candidato"],
               ["Confirmación", "10%", "Aceptar o rechazar ese candidato"]], [4*cm, 2.5*cm, 10.1*cm]),
        Spacer(1, 12),
        p("La división se realiza por juegos completos dentro de cada temporada anterior a 2026, con semilla 904. No hay filas del mismo juego en roles distintos. La versión guarda las identidades de cada partición y congela selección, modelos y escala antes de leer las etiquetas de evaluación."),
        p("En calibración se aprende una mezcla continua hacia el baseline, con peso entre 0 y 1. Para probabilidades se prueba además una sigmoide sobre logit cuando hay al menos 20 positivos y 20 negativos. Una pendiente no positiva se rechaza. Todas las transformaciones usadas en selección son las mismas exportadas para inferencia."),
        p("Búsqueda elige por MSE/Brier. Confirmación exige mejora ≥0.1% en ambas partes, IC95% de ganancia por juegos con límite inferior positivo, ninguna temporada peor que −0.1%, y log loss no peor que 0.15% en clasificación. Si falla, queda el baseline. No se elige un segundo candidato con confirmación."),
        p("Se reportan RMSE/R², Brier/AUC, log loss y ECE según tarea. Brier combina calibración y discriminación; no demuestra por sí solo buena calibración. Las curvas de confiabilidad describen cómo las probabilidades se comparan con frecuencias observadas."),
        p("El bootstrap es pareado y ponderado por pitches: remuestrea juegos completos, o pitchers en la auditoría correspondiente. Los intervalos describen la evaluación condicionada a estos modelos; no toda la incertidumbre de entrenar nuevamente. 2026 y los años anteriores tienen historia de exploración en el proyecto."),
    ])
    metric_rows = [["Tarea", "n", "RMSE/Brier", "Ganancia vs baseline"]]
    for row in metrics:
        if "metrics" not in row:
            continue
        m = row["metrics"]
        gain = row["vs_baseline"]["gain"]
        metric_rows.append([row["task"], row["n"], f"{m.get('rmse',m.get('brier')):.5f}", f"{gain:.2%}" if gain is not None else "n/e"])
    comparison_rows = [["Carreras", "v8 RMSE", "v9 RMSE", "Reducción MSE / IC95%"]]
    for row in comparison.itertuples():
        comparison_rows.append([row.task, f"{row.v8_rmse:.6f}", f"{row.v9_rmse:.6f}", f"{row.gain:.2%} [{row.ci_low:.2%}, {row.ci_high:.2%}]"])
    pages.append([
        Paragraph("5. Resultados temporales medidos", styles["HeadingV9"]),
        table(metric_rows, [6.2*cm, 2.4*cm, 3.4*cm, 4.6*cm]), Spacer(1, 10),
        p("RMSE se usa para las cuatro regresiones; Brier para clasificación. La ganancia compara MSE/Brier con el baseline específico de la tarea. Los JSON adjuntos incluyen AUC, log loss, ECE e intervalos.", True),
        table(comparison_rows, [5.5*cm, 2.7*cm, 2.7*cm, 5.7*cm]), Spacer(1, 10),
        p("La comparación de carreras usa el mismo target y 135,604 pitches. Se invierte la escala histórica v8 y se reproduce su RMSE archivado antes de comparar. Cambian features, definición física, tamaño de ajuste y selección: la diferencia mide pipelines completos. Un valor negativo es deterioro.", True),
        p("No se atribuye una mejora algorítmica aislada al cambio de AUC de probabilidades v9 frente a v8: v9 conoce ubicación y contexto que muchas probabilidades físicas v8 no conocían.", True),
    ])
    audit_rows = [["Holdout / tarea", "n", "RMSE", "Ganancia vs conteo"]]
    for row in audits.itertuples():
        audit_rows.append([f"{row.holdout}: {row.task}", row.n, f"{row.rmse:.5f}", f"{row.gain_vs_count:.2%}"])
    ablation_rows = [["Bloque añadido", "Ganancia MSE", "IC95%"]]
    for row in ablations:
        ablation_rows.append([row["to"], f"{row['gain']:.3%}", f"[{row['ci_low']:.3%}, {row['ci_high']:.3%}]"])
    pages.append([
        Paragraph("6. Robustez y aporte de cada capa", styles["HeadingV9"]),
        table(audit_rows, [7.5*cm, 2.3*cm, 2.8*cm, 4*cm]), Spacer(1, 10),
        p("Pitcher holdout reserva aproximadamente 20% de IDs con un hash fijo, excluyendo todas sus temporadas de desarrollo y perfiles. La prueba 2026 corresponde a pitchers sin historia disponible. Las filas sin ID se excluyen de esa auditoría. Se reentrenan las cuatro regresiones, no los nueve clasificadores.", True),
        p("Environment holdout excluye Extreme Altitude del desarrollo y evalúa esa categoría en 2026. Es transferencia de categoría y temporada; no es una prueba sobre Harp Helú identificado. Un park holdout requiere stadium y un mapeo oficial.", True),
        table(ablation_rows, [6.5*cm, 4.3*cm, 5.8*cm]), Spacer(1, 10),
        p("Las comparaciones incrementales usan las mismas filas: física → ubicación → arsenal → entorno. Los modelos comparten el protocolo de ajuste. Intervalos que cruzan cero no demuestran ganancia incremental. Esta comparación es predictiva; no es una intervención causal sobre el pitcher o el estadio.", True),
        p("La escala de cada auditoría se estima con su propia calibración. Sus puntos de índice no deben mezclarse directamente con el ranking de la ejecución temporal.", True),
    ])
    pages.append([
        Paragraph("7. Aplicación y simulador", styles["HeadingV9"]),
        p("La entrada dashboard_stuff_plus.py abre una guía con las tres preguntas, un explorador de escala y una tabla de requisitos. El simulador utiliza exactamente infer() del bundle congelado. Los valores iniciales son medianas de entrenamiento por tipo y mano, no una combinación inventada de máximos."),
        p("El coach introduce velocidad, IVB, HB y spin, y puede completar release, ubicación, conteo y arsenal. Se muestran lado a lado categorías sin altitud, media y extrema. La física se mantiene fija: cambiar la categoría no transporta automáticamente movimiento ni calcula un efecto causal."),
        p("El panel de explicación local transforma SHAP a puntos de Stuff+: valor base más contribuciones reproduce la predicción, incluyendo la mezcla hacia el baseline. Son atribuciones al resultado del modelo, no efectos causales de cambiar una medición."),
        p("El mapa HB–IVB normaliza el signo horizontal por mano y agrega tipo/pitcher/entorno. El ranking informa pitches y juegos y permite filtrar muestras de al menos 100 pitches y cinco juegos. Esos mínimos son orientativos; no equivalen a un intervalo de talento."),
        p("<b>Uso para scouting.</b> Comparar dentro de tipo y mano; revisar consistencia y contexto; llevar a video tanto perfiles favorables como desfavorables; identificar qué información cambiaría la conclusión. Los casos en RECOMENDACIONES_V9.md son ejemplos descriptivos seleccionados después de evaluar, no decisiones automáticas de contratación."),
        p("Las alertas de soporte usan percentiles 1–99 de cada variable en entrenamiento. Estar dentro de cada rango no garantiza soporte para la combinación multivariada. La disponibilidad de historia del pitcher se muestra de forma explícita."),
        p("Las probabilidades condicionales tienen denominadores diferentes. No deben sumarse entre sí ni confundirse con probabilidad de out dentro de PA. Los modelos se ajustan por separado; no forman una distribución conjunta exhaustiva de todos los posibles resultados."),
        p("<b>Perfil ideal.</b> Este dataset no permite afirmar un óptimo causal exclusivo de Harp Helú. Las hipótesis de menor movimiento Magnus, valor relativo del cambio y utilidad de rodados motivan análisis, pero no se imponen como hechos. Recomendaciones fuertes requieren evidencia del delta, soporte del perfil y validación del mapeo de parques."),
    ])
    pages.append([
        Paragraph("8. Límites, reproducción y fuentes", styles["HeadingV9"]),
        p("<b>Límites centrales.</b> El target es un proxy de carreras. La referencia fija no demuestra una normalización por cada parque/temporada. 2026 es reutilizado. Se desconoce el parque exacto, la densidad del aire y parte de la secuencia. Los intervalos no miden talento causal ni resuelven selección de pitchers, salud, rol o rivales."),
        p("<b>Reproducción.</b> Crear entorno virtual, instalar requirements/requirements-entrega.txt y ejecutar test_stuff_plus_v9.py. Entrenar con: python src/entrenar_stuff_plus_v9.py --iteraciones 300 --hilos 3. El parquet local se descubre en Data/. Una ejecución existente no se sobrescribe. Las fases entrenar/evaluar pueden separarse; hashes verifican que código y datos no cambiaron."),
        p("Auditorías: usar --holdout pitcher, o --holdout environment --grupo-excluido 'Extreme Altitude', en salidas independientes. El presupuesto de esta evidencia es 300 iteraciones. Los cuatro modelos de carreras son obligatorios para sus índices. reportar_v9.py genera tablas, curvas y verificación; generar_documento_v9.py produce este PDF."),
        p("La verificación local reprodujo predicciones guardadas, invariancia física frente a cambios contextuales, inferencia sin outcomes e independencia del tamaño de lote. Los modelos históricos que siguen siendo punteros LFS no se presentan como ejecutados de nuevo. Las pruebas que los necesitan se marcan como omitidas hasta recuperarlos."),
        p("<b>Uso de datos.</b> Competencia ISAC; datos anónimos de rendimiento; no publicar el dataset original ni usarlo para apuestas. Los artefactos internos de modelos/perfiles y scores por pitch permanecen en carpetas locales ignoradas. La documentación compartible incluye agregados y hashes. El equipo debe verificar integrantes, evidencias de inscripción y envío de la entrega."),
        p("<b>Fuentes.</b> Convocatoria HTML y stuff_plus_data_dictionary.csv locales; código/artefactos históricos v5–v8; documentación de calibración de scikit-learn (scikit-learn.org/stable/modules/calibration.html); pérdidas CatBoost (catboost.ai/docs/en/concepts/loss-functions-regression). La fundamentación física se toma como hipótesis del reto, sin cuantificar causalmente Harp Helú.", True),
        p("Origen SHA-256: " + verification["source_sha256"], True),
        p("Protocolo SHA-256: " + verification["protocol_sha256"], True),
        p("Ver docs/guias/GUIA_PROYECTO.md para explicación completa, semántica de columnas, ejemplos y comandos por plataforma.", True),
    ])
    story = []
    for index, page in enumerate(pages):
        if index:
            story.append(PageBreak())
        story.extend(page)
    target = OUT/"DOCUMENTO_TECNICO_V9.pdf"
    document = SimpleDocTemplate(str(target), pagesize=A4, rightMargin=1.8*cm, leftMargin=1.8*cm,
                                 topMargin=1.8*cm, bottomMargin=2*cm, title="Stuff+ Diablos · Documento técnico v9", author="Equipo Diablos ISAC")
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    count = len(PdfReader(target).pages)
    if count != 8:
        raise RuntimeError(f"El documento produjo {count} páginas; se requieren las 8 previstas")
    print(f"{target}: {count} páginas")


if __name__ == "__main__":
    main()
