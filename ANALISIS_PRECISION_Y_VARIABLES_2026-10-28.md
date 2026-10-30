# Precisión del algoritmo: auditoría y experimentos exploratorios

## Dictamen

Hay oportunidades para mejorar, pero añadir variables indiscriminadamente no es una solución demostrada. El modelo actual distingue tres ámbitos que deben conservarse: calidad física (Stuff+), ubicación/contexto y evaluación combinada. Una variable puede ayudar a predecir un swing fallido sin ser apropiada para el índice físico ni mejorar la predicción de carreras.

Se revisaron el entrenamiento v9, las variables v5/v6 que reutiliza, los modelos y métricas guardados, el esquema de los dos Parquet y la reconstrucción de turnos. Se ejecutó una prueba de cuatro bloques de variables para dos objetivos, exclusivamente sobre desarrollo 2024–2025. No se cambiaron modelos, referencias, puntuaciones ni decisiones congeladas.

## Qué usa hoy

- Stuff+ usa **23 variables**, incluidas derivadas: velocidad, giro/eje circular, salida, extensión, movimiento y normalización por mano.
- La capa de ubicación usa **28**: añade altura/lado en plato, bolas, strikes y lado del bateador.
- El bloque completo usa **37**: incorpora diferencias históricas frente a la recta primaria, uso/confiabilidad del arsenal, categoría de altitud y estadio.
- Los modelos de arsenal y entorno no confirmaron mejora incremental y conservan la capa anterior para carreras. Algunas probabilidades sí usan los 37 predictores.
- Se utiliza CatBoost, con profundidad 6, regularización 20 y un máximo de 400 árboles en la ejecución instalada. Varios modelos alcanzan ese máximo; esto justifica probar otros presupuestos, pero no demuestra por sí solo que falten árboles.

## Datos disponibles y redundancia

En los 499,398 lanzamientos de desarrollo, los campos de velocidad final, tiempo, pérdida de velocidad, ángulos y componentes del movimiento tienen cobertura numérica finita completa. La altitud continua cubre 468,076 filas (93.73%); no debe rellenarse un estadio desconocido como si estuviera a nivel del mar.

Correlaciones calculadas solo en desarrollo:

| Par | Correlación |
|---|---:|
| Velocidad al plato / velocidad inicial | 0.9868 |
| Tiempo al plato / velocidad inicial | −0.9808 |
| `pfxx` / movimiento horizontal | −0.9946 |
| `pfxz` / movimiento vertical inducido | 0.9974 |
| Ángulo vertical de llegada / altura en plato | 0.7806 |
| Ángulo horizontal de llegada / lado en plato | 0.5777 |

Las primeras cuatro relaciones muestran redundancia fuerte. Los signos y unidades deben verificarse con el diccionario Trackman del dataset antes de implementar un motor físico; no corresponde trasladar convenciones Statcast automáticamente. Los ángulos de llegada contienen información asociada a dónde se dirigió la pelota: en esta exploración se prueban en la capa contextual, no se añaden al Stuff+ independiente de ubicación.

En controles básicos aparecieron cero whiffs sin swing y cero conteos fuera de rango, pero una discrepancia entre la bandera de bola en juego y `PitchCall`. Esto merece una revisión puntual, no atribuirle una mejora grande de precisión. No se eliminaron filas ni se alteraron etiquetas.

## Experimento ejecutado

Script: `analizar_variables_precision.py`. Evidencia: `reports/precision_2026_10_28/`.

Cuatro variantes por objetivo:

1. Base experimental con los 37 predictores del bloque completo.
2. Base + siete proxies aerodinámicos que ya existían en v6: arrastre, sustentación y movimiento por giro, entre otros.
3. Base + siete variables de vuelo y ángulos.
4. Base + altitud continua, densidad estándar, mes circular, entrada y outs.

Cada ajuste usa hasta 200 árboles, la misma semilla, regularización y parada temprana, y las mismas particiones por juegos de v9. Se entrena en `fit`, se detiene con `early_stop` y se calibra con `calibration`. La política de calibración es fija entre variantes: contracción para regresión, sigmoide cuando está disponible para clasificación. Se inspecciona la partición histórica llamada `confirmation`, ya usada anteriormente, sin volver a presentarla como confirmación independiente.

Para carreras hay 249,488 filas de ajuste y 48,963 de comparación; para fallo condicionado a swing, 117,175 y 23,010. Los intervalos remuestrean 168 juegos. La reducción se compara con la base experimental de igual presupuesto, **no con la predicción congelada de producción**, que para carreras hereda una capa más sencilla. Se conservan diferencias por 2024 y 2025.

Es una prueba de orientación, no una selección definitiva: el presupuesto es menor al de producción, se inspeccionan varias variantes, no hay corrección por búsquedas múltiples y no se hacen en esta ejecución pruebas temporales independientes, por pitcher o parque. No se entrenaron ni eligieron variables con resultados de 2026. Las métricas ya existentes de ese año se usan solo para diagnosticar límites conocidos.

### Resultados de los ocho ajustes

Reducción relativa de MSE (carreras) o Brier (fallo condicionado a swing) frente a la base experimental de igual presupuesto. Positivo es mejor; negativo es peor.

| Variables añadidas | Carreras: reducción del error | Fallo dado swing: reducción del Brier |
|---|---:|---:|
| Proxies aerodinámicos | −0.0629% | +0.1728% |
| Vuelo y ángulos | −0.0557% | +0.3374% |
| Entorno y situación | −0.0341% | +0.1982% |

Para fallo condicionado a swing, la base tiene Brier 0.151319 y AUC 0.745796. Con vuelo y ángulos se obtiene Brier 0.150808 y AUC 0.748237. El intervalo exploratorio del 95% de reducción relativa del Brier es [0.1521%, 0.5143%]; las reducciones son positivas en 2024 (+0.4483%) y 2025 (+0.2270%). El bloque aerodinámico también mejora en ambos años. El bloque de entorno/situación mejora en el agregado, pero en 2025 da −0.0023%: no es evidencia de mejora estable.

Para carreras, la base experimental tiene RMSE 0.214926. Los tres bloques aumentan ligeramente el error y sus intervalos exploratorios quedan del lado desfavorable. Por tanto, esta prueba no respalda incorporarlos al modelo de carreras. No demuestra que ninguna configuración o variable individual pueda ayudar: aquí solo se probaron bloques concretos y un presupuesto fijo.

**Conclusión práctica:** el candidato más prometedor de esta exploración es vuelo/ángulos para el clasificador contextual de fallo de swing, seguido del bloque aerodinámico. El siguiente paso es separarlos en variables individuales y contrastarlos contra el clasificador de producción con su presupuesto completo y pruebas temporales/grupales adicionales. Ningún candidato se promovió automáticamente.

## Mejoras que priorizaría

### 1. Revisar el objetivo, además de las variables

El objetivo actual es un proxy de pesos fijos: por ejemplo, un strike no terminal vale −0.05, una bola +0.03 y muchos fouls quedan en cero. El mismo evento no tiene necesariamente el mismo valor deportivo en todos los conteos. El modelo contextual ya aprende un residual frente a una referencia por conteo; eso no convierte los pesos fijos en un valor de carrera completo.

Propuesta: estimar dentro de entrenamiento un valor esperado del turno por conteo, y construir el cambio de valor entre estados y cierre con las PA completas reconstruidas. Las tablas se vuelven a ajustar en cada separación; nunca se calculan con el año evaluado. Comparar también la predicción de resultados terminales. Al cambiar la etiqueta, los RMSE antiguos y nuevos no se pueden comparar como si midieran el mismo objetivo. Sin estado completo de bases no corresponde llamarlo RE24.

### 2. Secuencia y carga de trabajo, usando solamente pasado

Variables candidatas: tipo y velocidad del lanzamiento anterior, diferencia de movimiento entre lanzamientos sucesivos, número acumulado de lanzamientos previos del pitcher en el juego, número de lanzamientos previos en el turno y cambios recientes de velocidad/salida. La reconstrucción actual ya verifica muchas secuencias de PA mediante UUID v1.

Hay que comprobar orden, interrupciones y sustituciones, aplicar desplazamientos temporales y evitar cruzar límites de juegos. No usar totales finales del juego ni el lanzamiento siguiente. Estas variables pertenecen al contexto/arsenal; no deben modificar el Stuff+ físico de un lanzamiento aislado. Un diferencial de trayectoria no demuestra tunneling perceptual real.

### 3. Historial reciente del arsenal y del rival

Hoy la historia de desarrollo usa solo juegos `fit` de temporadas anteriores: es prudente, pero la primera temporada no tiene historia y la segunda no refleja cambios recientes. Probar medias móviles y uso del repertorio calculados antes de cada juego, suavizados hacia pares por tipo/mano. Para bateador y catcher, probar perfiles históricos con regularización y respaldo cuando sean nuevos, en lugar de introducir sus identificadores como atajos. Los datos del propio turno aún no ocurrido no pueden construir esos perfiles.

### 4. Entorno continuo y calibración local

La altitud continua existe en el Parquet enriquecido aunque el catálogo simplificado del dashboard use categorías. Es candidata a modelo, no una mejora garantizada por estar disponible. Un modelo físico de transporte necesitaría validar unidades, origen, arrastre, giro y vuelo real; el laboratorio visual no cumple esa validación.

Para jonrón, las métricas históricas de Harp muestran 0.695% estimado frente a 0.866% observado, sobre 6,005 lanzamientos y 19 juegos. La diferencia puede ser ruidosa y no autoriza recalibrar con ese mismo conjunto de prueba. Probar calibración parcial por estadio con suavizado hacia el global, usando únicamente calibración de desarrollo. Temperatura, presión, humedad y viento serían futuras incorporaciones con fuentes y horarios verificables; no están en las mediciones originales.

### 5. Regularización y combinación de objetivos

Probar pocas configuraciones prefijadas de profundidad, regularización y máximo de árboles, con parada temprana. No se necesita cambiar de familia de modelo antes de medir estos factores. Un ensemble pequeño de semillas puede reducir variación, pero debe compararse con el mismo presupuesto.

El índice integral actual asigna pesos iguales a ocho señales. No está demostrado que esa combinación mejore la predicción de carreras. Si se aprenden pesos o se alimenta otro modelo con sus probabilidades, deben usarse predicciones fuera de pliegue en entrenamiento, con separación por juegos y tiempo; reutilizar predicciones de ajuste produciría una evaluación optimista.

## Qué no añadiría como predictor del lanzamiento

`ExitSpeed`, ángulo/distancia del batazo, resultado de la jugada, carreras, outs de la jugada o etiquetas del swing que se quiere anticipar. Son resultados del lanzamiento o se conocen después. `Outs` antes del lanzamiento es distinto de `OutsOnPlay`; este último no es una entrada válida. Tampoco usaría identificadores de juego, UUID o el estado de verificación del mapeo de estadios como atajos predictivos.

## Criterio para aceptar una mejora

Separar por juegos y por tiempo; añadir pruebas con pitchers y parques excluidos. Ajustar historia, normalización, objetivo y calibración dentro de cada entrenamiento. Evaluar reducción de MSE/Brier y log loss, calibración, tamaño de muestra y desempeño por tipo/mano/parque. Para eventos raros, revisar también precisión-recall y el error frente a una referencia adecuada: AUC alta no implica probabilidades útiles.

Prefijar candidatos y criterio antes de reservar la siguiente comprobación. Un intervalo de una exploración reutilizada no sustituye una nueva validación. 2026 ya fue inspeccionado; cualquier comparación adicional ahí sería retrospectiva, no una prueba futura intacta. La promoción requiere mejora estable con incertidumbre razonable y sin degradaciones relevantes, no solo una cifra promedio favorable.

## Fuentes

Evidencia local: `entrenar_stuff_plus_v9.py`, v5/v6, `completar_targets_pa.py`, `indice_integral.py`, los Parquet autorizados, bundle y métricas guardados. La importancia exportada de CatBoost describe el uso de variables en modelos ajustados; no mide causalidad ni prueba una mejora por agregar o retirar una columna.

Referencias primarias consultadas: [CatBoost: ajuste de parámetros](https://catboost.ai/docs/en/concepts/parameter-tuning), [scikit-learn: prevención de fugas de información](https://scikit-learn.org/stable/common_pitfalls), [scikit-learn: validación y datos temporales](https://scikit-learn.org/stable/modules/cross_validation.html), [MLB: documentación de variables Statcast](https://baseballsavant.mlb.com/csv-docs). Esta última sirve de referencia conceptual; no certifica las unidades ni convenciones del dataset Trackman de LMB.
