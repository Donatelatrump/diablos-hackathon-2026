# Aplicación del análisis de precisión

## Cambios implementados

Se añadió una capa independiente para mejorar la probabilidad de fallo **condicionada a que el bateador intente batear**. El motor v9, sus archivos, sus tres índices y sus referencias permanecen intactos. No se trasladaron ángulos de llegada a Stuff+.

`precision_features.py` construye variables del lanzamiento anterior, diferencias de velocidad/movimiento, carga observada del juego e historial del mismo tipo de lanzamiento en los últimos cinco juegos elegibles. Las medias usan solo juegos de entrenamiento estrictamente anteriores. Se excluyen del historial los pitchers/parques reservados en cada auditoría. Los timestamps solo ordenan registros; no son predictores. El historial no usa resultados del swing o de la jugada.

La carga cuenta los lanzamientos registrados, no garantiza la carga total real. El historial requiere al menos diez lanzamientos; si no hay soporte, se marca ausente. Los juegos con orden ambiguo desactivan las variables de secuencia: es una preparación retrospectiva de registros, no un sistema de streaming en vivo.

`entrenar_precision_contextual.py` compara dos candidatos con hasta 400 árboles contra el clasificador congelado: vuelo y ángulos; vuelo más secuencia/historial. Se escoge una combinación de candidato/calibración en tune y se comprueba una sola vez en la partición histórica confirmation. No se escoge un segundo candidato después de ver que el primero falle una auditoría.

El ganador se somete además a:

- Entrenamiento, parada y calibración con 2024; evaluación en todos los swings elegibles de 2025.
- Exclusión de los pitchers reservados antes de ajustar modelos e historia.
- Exclusión de Harp antes de ajustar modelos e historia.

Las auditorías reajustan tanto el control de 37 variables como el candidato con el mismo presupuesto y política de calibración. Exigen reducción relativa de Brier de al menos 0.1%, intervalo por juegos favorable, log loss sin degradación relevante y ausencia de degradaciones anuales mayores a 0.1%. Estos son criterios prefijados para esta ejecución, no garantías de utilidad deportiva.

La selección de desarrollo se compara con el booster congelado; las auditorías se comparan con controles reajustados que respetan sus exclusiones. No deben confundirse ambos controles ni sus muestras. Todo es evidencia retrospectiva sobre datos ya inspeccionados, no una prueba prospectiva nueva.

## Uso en la página

La vista Comparar estadios permite introducir mediciones adicionales de vuelo y, opcionalmente, datos anteriores del juego e historial reciente. Son controles nativos y permanecen plegados. No se inventan mediciones faltantes.

`precision_model.py` solo aplica el ajuste si el manifiesto final lo acepta, coincide el hash del bundle base y hay entradas válidas dentro de los rangos requeridos. Si falta un campo necesario, hay datos no finitos o cambia la versión base, conserva el clasificador habitual. El ajuste solo modifica `p_whiff_given_swing`; no altera las demás probabilidades, Stuff+, Location+, Pitching+ ni el índice integral, que usa otro componente de whiff.

La columna `precision_whiff_available` identifica qué escenarios recibieron el ajuste. La sección Confianza muestra por separado sus auditorías y las métricas del modelo habitual; no combina cifras de muestras diferentes.

También existe una comparación experimental explícita en Comparar estadios. Requiere activar su casilla y aportar datos válidos. Carga el candidato con hash verificado aunque no esté aceptado para producción, presenta su probabilidad al lado de la habitual y conserva intactas la tabla principal y las puntuaciones. Esta vía no modifica la decisión de activación automática.

## Objetivo por conteo

`entrenar_objetivo_conteo.py` implementa y entrena un objetivo separado: cambio del valor esperado del turno entre conteos y cierre. Sus tablas se ajustan solo con PA completas de juegos fit. Un turno aporta como máximo una observación por conteo a esas tablas. Los fouls con dos strikes no cambian el conteo y reciben transición cero, salvo una jugada terminal reconocida.

Se ajustaron las tablas con **63,262 PA completas**. El modelo obtuvo RMSE **0.215006**, frente a **0.218183** de la referencia por conteo del mismo objetivo, en 47,387 lanzamientos de comprobación. La reducción de MSE fue **2.89%**, con intervalo por juegos de **2.62% a 3.22%**.

Ese resultado no demuestra que supere al objetivo v9: cambiaron las etiquetas. No es RE24 porque faltan estados completos de bases. Se mantiene como experimento separado hasta contar con auditorías temporales/grupales y contraste deportivo. La normalización de claves de conteo entero/decimal se verificó sin cambios numéricos de objetivo en las 499,398 filas de desarrollo; el modelo entrenado permanece idéntico.

`precision_count_model.predict_count_transition(frame)` permite inferir el nuevo objetivo sin suministrar resultados de la jugada. Verifica el hash del modelo, devuelve su referencia por conteo y lo marca experimental. No modifica el frame de entrada ni transforma ese valor en un Stuff+/Pitching+ nuevo sin validación.

## Calibración por estadio

`calibracion_estadios_precision.py` implementa desplazamientos logísticos globales y por estadio, penalizados hacia el global, ajustados únicamente en calibración. Los estadios nuevos usan el ajuste global y no un coeficiente inventado.

Se probaron penalizaciones prefijadas 20 y 100 para jonrón. El candidato de penalización 20 redujo el Brier solo **0.0166%** en confirmation, con intervalo **−0.0326% a +0.0639%** y ligera degradación en 2025. No superó el criterio y **no está activo**. No se recalibró con las etiquetas de Harp de 2026.

## Artefactos y reproducción

- `precision_output_2026_10_28/`: candidatos, decisión y auditorías de fallo condicionado a swing.
- `precision_count_output_2026_10_28/`: tablas por conteo, modelo y evaluación del nuevo objetivo.
- `precision_calibration_output_2026_10_28/`: calibradores y rechazo estadístico.

Los directorios contienen modelos reproducibles y se excluyen de Git. No se copiaron datos de la competencia a una entrega pública ni se modificó el Parquet original. Las ejecuciones se niegan a sobrescribir una carpeta existente: usar `--output` con una carpeta nueva para repetir.

```powershell
.venv/Scripts/python.exe entrenar_precision_contextual.py --output precision_whiff_nueva_ejecucion
.venv/Scripts/python.exe entrenar_objetivo_conteo.py --output precision_conteo_nueva_ejecucion
.venv/Scripts/python.exe calibracion_estadios_precision.py --output precision_calibracion_nueva_ejecucion
```

Para una nueva ejecución no se cambia automáticamente la carpeta activa de la página. Antes hay que revisar el manifiesto, las entradas necesarias, los hashes y las comprobaciones. No se considera que añadir variables, recalibrar o cambiar el objetivo implique por sí solo una mejora.

## Límites pendientes

No hay temperatura, presión, humedad ni viento verificados por lanzamiento: no se inventaron. Los perfiles históricos de bateador/catcher y un ensemble de semillas no se incorporaron sin validación. No se reoptimizaron los pesos del índice integral con predicciones de entrenamiento; eso requeriría predicciones fuera de pliegue. El laboratorio de altitud sigue siendo una ilustración independiente, no una transferencia física validada que alimente los índices.

## Resultado final

Se entrenaron ocho clasificadores para selección y auditorías, un regresor del objetivo por conteo y dos calibradores de estadio. El candidato seleccionado fue vuelo más secuencia/historial con calibración identidad. No se seleccionó usando 2026.

| Comprobación de fallo dado swing | Muestra / juegos | Reducción relativa de Brier | Intervalo 95% | Criterio |
|---|---:|---:|---:|---|
| Desarrollo frente al clasificador congelado | 23,010 / 168 | 0.3821% | 0.1790% a 0.6046% | Superado |
| 2024 → 2025, modelos reajustados | 119,384 / 839 | 0.1327% | 0.0254% a 0.2510% | Superado |
| Pitchers excluidos, modelos reajustados | 3,977 / 146 | 0.4597% | −0.1151% a 0.9862% | No superado |
| Harp excluido, modelos reajustados | 1,098 / 8 | 1.3428% | 0.6588% a 2.0674% | Superado |

**El candidato no está activado como sustituto del modelo habitual.** En pitchers excluidos la mejora media es positiva, pero el intervalo incluye degradación. El criterio exigía superar las tres auditorías, y no se cambió después de observar los resultados. Está disponible para comparación experimental explícita con sus limitaciones. La muestra de Harp es pequeña, pese al resultado favorable.

El objetivo por conteo verificó además la identidad de sus transiciones en **126,360 PA completas** de desarrollo: error máximo de telescopado **2.22×10⁻¹⁶** frente al valor terminal. Esto demuestra consistencia aritmética, no superioridad predictiva sobre v9.

## Verificación ejecutada

La suite conjunta ejecutó **40 casos: 38 aprobados y 2 omitidos por artefactos opcionales ausentes**. Se repitió la suite específica de precisión tras añadir la comparación experimental. Cubre orden y dependencia del pasado, exclusión del historial reservado, normalización de conteos enteros/decimales, objetivo con PA completas, ausencia de cambios en índices y entradas originales, fallback sin datos, generación base incompatible, controles del dashboard e inferencia del regresor nuevo sin outcomes.

Las auditorías conservaron el SHA del Parquet y del bundle base. El código de características usado al iniciar el entrenamiento quedó archivado en `precision_output_2026_10_28/precision_features_frozen.py`; la posterior normalización de claves del objetivo por conteo se verificó numéricamente sin cambiar ese entrenamiento ni sus predictores. Los resultados y hashes quedan en cada carpeta de artefactos.

`git diff --check` no reportó errores; el servidor de localhost:8501 respondió `ok`. Las interacciones se comprobaron con Streamlit AppTest. No hubo navegador conectado para inspeccionar el renderizado visual.
