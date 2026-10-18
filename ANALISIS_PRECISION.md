# Análisis de precisión de los modelos

Análisis del 17 de octubre de 2026, basado en el código, el diccionario, consultas al parquet original y métricas exportadas v6/v7. No se entrenaron modelos ni se cambiaron decisiones de despliegue durante este análisis. Los diagnósticos de 2026 son exploratorios: la temporada ya fue reutilizada.

## Hallazgos

| Tarea | Evidencia | Interpretación |
|---|---|---|
| Whiff por pitch | AUC v6 0.6508 → v7 0.6443; Brier 0.096926 → 0.097279 | V7 no constituye una mejora global. Cambiaron datos, ajustes y calibración. |
| Whiff dado swing | Calibración v7: Brier 0.170656 → 0.169068, ECE 0.021742 → 0.012782; AUC total v6 0.6815 → v7 0.6752 | Mejoran las probabilidades del mismo núcleo, pero no su capacidad de ordenar casos frente a v6. |
| Bola en juego | AUC v6 0.5437 → v7 0.5755 | Hay señal física adicional, todavía modesta. |
| Velocidad de salida física | RMSE v7 15.296 mph; R² 0.0119 | Explica aproximadamente 1.19% de la variación observada; otros determinantes del contacto no están en este modelo físico. |
| Valor de carreras físico | R² 0.00167; compuesto mejora MSE de selección solo 0.0597% | Mejorar componentes no garantiza mejorar el objetivo agregado. El compuesto no alcanzó el mínimo de 0.1%. |
| Jonrón | Frecuencia 2026 0.680%; average precision v7 0.879% | Señal débil para un evento raro. Accuracy sería engañosa: predecir siempre “no HR” acertaría aproximadamente 99.32%. |

El ajuste v7 reserva aproximadamente 60% de los juegos para entrenar, frente al 80% aproximado usado por v6. No podemos atribuir la pérdida de discriminación exclusivamente a calibración ni afirmar que provenga exclusivamente del tamaño de muestra.

## Diagnóstico por tipo

Sesgo de whiff por pitch en 2026 = probabilidad media v7 menos frecuencia observada. No es una evaluación independiente ni una prueba de que un especialista vaya a mejorar.

| Tipo | Pitches 2026 | Sesgo, puntos porcentuales |
|---|---:|---:|
| Four-Seam | 43,572 | -0.36 |
| Slider | 30,851 | +1.62 |
| Sinker | 25,125 | -0.21 |
| Changeup | 17,278 | +1.04 |
| Curveball | 11,265 | +0.39 |
| Cutter | 5,788 | +0.13 |
| Splitter | 1,474 | +3.71 |

Los datos 2024–2025 incluyen 174,046 Four-Seam, 108,278 Slider, 85,772 Sinker, 61,647 Changeup y 42,759 Curveball, pero solo 5,815 Splitter y 340 Sweeper. Un modelo independiente para cada etiqueta sería frágil para los tipos minoritarios. Además, AutoPitchType ya entra al modelo global: la especialización debe demostrar valor adicional frente a ese control.

## Experimentos prioritarios

1. **Comparación controlada del núcleo físico.** Entrenar v6 y v7 sobre exactamente los mismos juegos, con el mismo presupuesto de búsqueda y sin calibración inicial. Comparar variables base, movimiento, aerodinámica y sus combinaciones. Evaluar después cada calibrador sobre las mismas predicciones. Esto identifica qué cambio aporta señal y cuál causa deterioro.

2. **Especialistas con mezcla y respaldo global.** Comparar familias de rectas, rompientes y cambios/splitters, además del global. Elegir la mezcla por familia usando desarrollo, con mayor peso global cuando haya poca muestra. Medir Brier/log loss, AUC y calibración por familia; añadir incertidumbre por juego. Las familias y criterios de promoción deben quedar definidos antes de la evaluación.

3. **Aprovechar mediciones disponibles mediante ablaciones.** ZoneSpeed, SpeedDrop y ZoneTime tienen cobertura completa en 2024–2025. Probarlas individualmente y en conjunto tras revisar unidades, valores extremos y redundancia con velocidad efectiva. Las variables de trayectoria y ángulos pueden codificar ubicación: los ángulos de aproximación crudos deben evaluarse primero en modelos contextuales, y cualquier uso en Stuff+ requiere justificar la separación de ubicación. No asumir mejora por agregar columnas.

4. **Calibración regularizada y verificable por grupos.** Comparar identidad, sigmoide y mapas por familia contraídos hacia un mapa global. Evitar mapas independientes con pocas observaciones. Examinar Brier y log loss junto con ECE uniforme y por cuantiles. Los sesgos por tipo sugieren un experimento; no justifican corregir usando las etiquetas 2026.

5. **Reformular contacto y carreras.** Comparar un modelo de distribución o categorías de calidad de contacto con la regresión de EV media. EV, Angle y resultados observados sirven como objetivos, nunca como entradas disponibles al predecir un pitch. Un objetivo esperado de contacto tendría que aprenderse y generarse fuera de muestra. La media de EV no resume las colas ni toda la información necesaria para carreras.

6. **Búsqueda y ensembles después de aislar las mejoras.** Comparar profundidad, regularización, tamaño de entrenamiento y curvas de aprendizaje. Probar una media de varias semillas solo si sus errores aportan diversidad. La selección debe usar una métrica principal prefijada, con controles de deterioro por tarea/familia; no elegir únicamente por AUC.

## Validación viable y datos faltantes

El parquet tiene `year`, pero no fecha del juego, mes ni un orden de pitches documentado. Por tanto, la recomendación anterior de cortes mensuales requiere datos adicionales. Los IDs anónimos no deben utilizarse como sustituto de fechas. Con lo actual puede hacerse evaluación anual 2024 → 2025, separación por juegos y validación adicional dejando pitchers fuera; esta última mide generalización a pitchers no vistos, no estabilidad temporal.

Solo hay dos temporadas anteriores al benchmark reutilizado. Las repeticiones por juego ayudan a medir sensibilidad a la partición, pero no crean nuevos periodos independientes. Para confirmar mejoras, solicitar fechas y reservar datos futuros antes de experimentar.

Hay outs, carreras anotadas y resultados de jugada, pero faltan ocupación de bases y secuencia verificable para reconstruir las transiciones completas de RE24. Solicitar estados antes/después y orden de jugadas antes de prometer ese objetivo. También ayudarían metadatos de dispositivo para diagnosticar cambios de medición.

Las tasas observadas cambian entre temporadas: HR 0.694% en 2024, 0.783% en 2025 y 0.680% en 2026; whiff dado swing 24.41%, 23.82% y 24.19%. Son cambios descriptivos que pueden mezclar composición, entorno y medición; no prueban una causa. La comprobación básica no encontró whiffs etiquetados sin swing ni valores no nulos de EffectiveVelo imposibles de convertir a número. Esto no constituye una auditoría completa de etiquetas.

## Orden recomendado

Primero: comparación con los mismos juegos y ablación de variables. Segundo: especialistas mezclados con el global y calibración regularizada. Tercero: objetivo de contacto esperado. En paralelo: solicitar fechas y estados base-out. El éxito se define por tarea y sobre evaluación reservada; no por aumentar la versión ni el número de modelos.

Fuentes locales: `stuff_plus_output_v7/metricas_benchmark_2026.json`, `stuff_plus_output_v7/bundle.json`, `stuff_plus_output_v7/RESULTADO_MEJORA.md`, scripts de entrenamiento v5/v6/v7, `stuff_plus_data_dictionary.csv` y consultas agregadas a `stuff_model_df.parquet`.
