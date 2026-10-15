# Revisión del proyecto y entregables del Hackathon Diablos Rojos 2026

**Fecha de revisión:** 15 de octubre de 2026  
**Fecha límite de entrega publicada:** 22 de octubre de 2026

## Resumen

El proyecto ya cuenta con una base de modelos de predicción y una primera versión de scores por lanzamiento. Aún no está listo para entregar: faltan varios productos obligatorios y la puntuación actual está marcada como provisional. La brecha más importante para el reto es demostrar con datos el efecto del estadio y la altitud, además de separar claramente Stuff+, Location+ y Pitching+.

La convocatoria pide enviar los entregables por correo a **itamsportsanalytics@gmail.com** e incluir los correos de todos los integrantes. Los equipos deben tener entre 2 y 4 integrantes, y todos deben estar inscritos en licenciatura o maestría. La entrega de proyectos está publicada para el **22 de octubre de 2026**.

Fuentes:

- [Reto Diablos Rojos: requisitos, entregables y evaluación](https://www.isac-app.com/competition-details/hackathon-diablos-rojos.html)
- [Anuncio del Hackathon ISAC 2026 en el sitio del ITAM](https://eventos.itam.mx/es/evento/hackathon-isac-2026)

## Estado de los entregables

| Entregable solicitado | Estado encontrado | Trabajo pendiente |
|---|---|---|
| Scores por lanzamiento, pitcher y arsenal: Stuff+, Location+ y Pitching+ | Hay scores provisionales por lanzamiento. No se encontraron agregados por pitcher o repertorio ni un Pitching+ combinado. | Definir y validar los tres índices; producir agregados por pitcher y repertorio. |
| Comparación Harp Helú contra otros estadios y cuantificación de altitud | El Parquet incluye `altitude_category`, pero no una columna `stadium` con el identificador del parque. | Confirmar la correspondencia entre categorías y parques. Sin ella no se puede hacer una comparación específica por estadio ni un park holdout identificable. |
| Perfil físico ideal para Diablos Rojos | No se encontró análisis ni documento con el perfil recomendado. | Identificar perfiles que maximicen el score bajo el entorno pertinente y explicar la evidencia física y estadística. |
| Recomendaciones operativas y de scouting | No se encontró documento con recomendaciones. | Explicar qué perfiles ganan o pierden valor por entorno y cómo usar el modelo al evaluar prospectos o agentes libres. |
| Dashboard simulador y mapa de movimiento | No se encontró dashboard o simulador. | Permitir ingresar características del pitch, comparar entornos y visualizar pitches efectivos y menos efectivos. |
| Documento técnico de 6–10 páginas | No se encontró el documento. | Documentar teoría, datos, decisiones de modelado, normalización, validación y límites. |

La convocatoria asigna 25% a cada categoría: calidad del modelo, robustez fuera de muestra, integración del arsenal y altitud, y aplicabilidad real. Pide comparar con un baseline —incluido xRunValue promedio por conteo— y reportar validación por pitcher, temporada y estadio.

## Revisión de los modelos y métricas

Se revisaron las métricas ya guardadas en `stuff_plus_output/metricas_validacion.json` y `stuff_plus_output_reentrenado/metricas_reentrenadas.json`. **No se volvió a entrenar ningún modelo.**

- **Chase y called strike:** discriminación prometedora en los holdouts; AUC aproximado de 0.91 para chase y 0.88 para called strike.
- **Whiff:** desempeño moderado, con AUC cercano a 0.73 en validación por temporada y por pitcher.
- **Groundball condicional a bola en juego:** AUC aproximado de 0.64–0.65 en el primer entrenamiento. El reentrenamiento sube a aproximadamente 0.67.
- **Velocidad de salida:** en el holdout por temporada, el primer modelo tiene RMSE de 14.55 mph y R² de 0.11. El reentrenamiento mejora a RMSE de 14.03 mph y R² de 0.17, aunque sigue explicando una fracción limitada de la variación.
- **Jonrón por lanzamiento:** el reentrenamiento sube el AUC a aproximadamente 0.81, pero el evento es muy raro. La mejora del Brier frente al baseline de tasa constante es cercana al 1%; conviene presentar calibración y métricas de precisión junto al AUC.

Los valores de `stuff_plus_provisional` tienen promedio 100 y desviación estándar 10 por construcción. Eso no demuestra que el índice esté calibrado al promedio de liga por temporada y estadio. Además, los modelos finales se ajustan con todas las temporadas y sus predicciones se generan sobre esas mismas filas; por ello los scores de salida son predicciones dentro de muestra, no una evaluación independiente.

## Hallazgos técnicos y mejoras prioritarias

### 1. Resolver la identificación de estadios

El dataset local contiene `altitude_category`, con categorías como `No Altitude`, `Medium Altitude` y `Extreme Altitude`, pero no contiene una columna `stadium`. El diccionario describe la variable como una categoría de altitud específica del dataset. Antes de afirmar que una categoría representa Harp Helú o un conjunto de parques, hay que confirmar el mapeo con la organización.

Sin identificadores o una correspondencia validada no se puede aislar el efecto de Harp Helú, hacer un holdout por parque ni presentar una comparación estadística específica entre ese estadio y otros.

### 2. Separar Stuff+, Location+ y Pitching+

La convocatoria define Stuff+ como calidad física del lanzamiento en el release. En la lista `PHYSICAL_FEATURES` del código se incluyen variables como `ZoneSpeed`, `SpeedDrop`, `ZoneTime` y ángulos de aproximación, que describen el trayecto hacia o cerca del plato. Para que Stuff+ corresponda estrictamente a la definición del reto, conviene limitarlo a velocidad, movimiento, spin y características de release.

El modelo de `called_strike` usa variables físicas y de ubicación; puede capturar señal útil, pero su probabilidad no representa por sí sola el valor marginal de ubicación. Conviene modelar Location+ condicionado al tipo o cluster del pitch, conteo y lado del bateador, y después construir Pitching+ como combinación documentada de las capas.

### 3. Hacer coherente el compuesto de outcomes

El score provisional de Stuff combina `p_whiff`, `p_groundball_given_in_play` y la velocidad de salida predicha condicionada a bola en juego. El modelo de `ball_in_play` existe, pero actualmente no se utiliza en ese compuesto.

Una probabilidad condicional como `P(groundball | bola en juego)` no equivale a la probabilidad por lanzamiento. Si se quiere estimar su contribución esperada por pitch, debe combinarse con `P(bola en juego)`. Lo mismo aplica a la velocidad de salida y a otros outcomes observados solo cuando la pelota entra en juego. Hay que documentar las ponderaciones y la dirección favorable de cada componente.

### 4. Añadir baselines y calibración

Para cada target, comparar el modelo con baselines apropiados. Incluir el baseline de xRunValue promedio por conteo solicitado por la convocatoria si las variables necesarias están disponibles. Reportar calibración —por ejemplo, Brier y curvas de calibración para clasificación— además de AUC y precisión promedio. Para regresión, conservar RMSE/MAE y comparar contra una predicción base.

Mantener una evaluación fuera de muestra separada de los datos usados para generar los scores finales. Reportar resultados por temporada, pitcher y estadio cuando la identificación de parques lo permita.

### 5. Completar los productos utilizables por el cuerpo técnico

Preparar agregados por pitcher y repertorio, análisis de perfiles ideales, recomendaciones de scouting y un simulador que compare el mismo pitch entre entornos. El documento técnico debe describir las variables, los targets, la función de pérdida, la construcción de la escala, la validación y las limitaciones.

## Estado de los archivos existentes

- `entrenar_stuff_plus.py`: script que entrena siete tareas, calcula validaciones temporales y por pitcher, guarda modelos y genera scores provisionales.
- `stuff_plus_output/`: contiene métricas, scores por pitch y siete modelos.
- `stuff_plus_output_reentrenado/`: contiene métricas y solo tres modelos (`groundball_given_in_play`, `home_run_per_pitch`, `exit_speed_given_in_play`); no contiene scores ni el resto de modelos. Es una comparación parcial, no un paquete final autocontenido.
- `stuff_plus_data_dictionary.csv`: describe variables, unidades y usos recomendados.
- `entrenar_stuff_plus_colab.ipynb`: instrucciones para entrenar en Google Colab y copiar resultados a Drive.
- No se encontró README, reporte técnico ni dashboard entre los archivos revisados.

## Plan recomendado antes de la entrega

1. Confirmar con la organización el mapeo de `altitude_category` a estadios y qué variables/contexto están autorizados para presentar.
2. Replantear el compuesto para respetar la naturaleza condicional de los outcomes y separar las capas Stuff+, Location+ y Pitching+.
3. Recalcular validaciones y comparar contra baselines; reportar calibración y holdouts disponibles con sus limitaciones.
4. Generar scores agregados por pitcher y repertorio, y sustentar cualquier conclusión de altitud con la identificación de parques confirmada.
5. Preparar recomendaciones, dashboard simulador y documento técnico de 6–10 páginas.
6. Enviar los entregables al correo de la convocatoria antes del 22 de octubre de 2026 e incluir los correos de todos los integrantes.

## Uso de datos

La convocatoria indica que los datos proporcionados son solo para la competencia, que no se deben presentar los datos en sí y que sí se pueden presentar resultados. Revisar los archivos adjuntos y las visualizaciones para evitar incluir el dataset original. Consultar la sección de disclaimers de la [convocatoria](https://www.isac-app.com/competition-details/hackathon-diablos-rojos.html).
