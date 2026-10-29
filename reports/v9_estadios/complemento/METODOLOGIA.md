# Complemento de objetivos y normalización

## Out al cerrar el turno

Se reconstruye cada turno al bate ordenando los UUID v1 dentro del juego. Se exige inicio 0-0, mismo bateador y media entrada, conteos sucesivos coherentes y jugada terminal reconocida. Se excluyen timestamps inválidos/duplicados, secuencias incompletas, cambios de conteo inexplicados y outs de corredor en lanzamientos no terminales.

El objetivo es al menos un out registrado en la jugada que cierra la PA. Incluye selección y doble play; **no equivale necesariamente a que el bateador sea retirado**. No se supone que todo strikeout termina en out: se consulta OutsOnPlay, para no inventar el resultado de un tercer strike no atrapado. La etiqueta del cierre se propaga a los lanzamientos de esa PA, como resultado futuro que se quiere predecir, nunca como entrada.

Se recuperaron 159.921 PA completas, con 611.413 lanzamientos etiquetados de 635.002. Se excluyeron 8.537 secuencias. La cobertura no garantiza que todos los eventos de la liga hayan sido capturados: las evaluaciones son condicionales a las secuencias verificables. Las métricas ponderan lanzamientos, por lo que los turnos largos pesan más.

Cada una de las tres auditorías usa sus particiones v9 originales. Se excluyen los pitchers/parques reservados antes de preparar historia. El modelo no recibe bateador, PA, timestamp, jugada ni outs como predictor; sí física, ubicación, conteo, mano, historia y estadio. Se ajusta en fit, se detiene en early_stop, calibra en calibration y selecciona en tune/confirmation. Los modelos y decisiones se congelan antes de evaluar 2026. El baseline es probabilidad de out por conteo, suavizada hacia la media de fit.

## Índice integral

Ocho componentes: whiff, chase, strike cantado, contacto débil, rodado, contacto duro (signo negativo), carreras esperadas (signo negativo) y out PA. Cada predicción se estandariza con la media/desviación de calibración y recibe peso 1/8, prefijado sin consultar los resultados de 2026. Una componente constante aporta cero. La utilidad resultante se transforma a 100 + 10 z usando calibración.

Es un índice de utilidad relativa, no una probabilidad, ni la suma de eventos mutuamente excluyentes. Se conservan los denominadores condicionales de contacto débil/duro y rodado. La correlación puede redundar señales; los pesos no están optimizados para maximizar carreras, scouting o rendimiento. No se afirma que supere al modelo de carreras. Stuff+ físico, Location+ y Pitching+ de carreras siguen disponibles con sus definiciones originales.

## Referencia por temporada y estadio

Se añade una normalización descriptiva de las predicciones en cada combinación año/estadio: media 100 y desviación 10 si hay al menos 300 lanzamientos y variación. Si el grupo es pequeño o el estadio es desconocido, se usa la referencia de toda la temporada; si la referencia es constante, se muestra 100. Los parámetros y el respaldo usado están en referencias_temporada_estadio.json.

Esta vista corresponde a la muestra evaluada, no a un censo garantizado de toda la LMB. Usa predicciones, nunca etiquetas del año de prueba. Al depender de la cohorte completa, es retrospectiva; no se emplea para demostrar precisión fuera de muestra. El simulador conserva la escala fija de calibración para que una nueva observación no cambie las puntuaciones anteriores.

## Reproducción

1. `python src/completar_targets_pa.py`: reconstrucción, tres modelos de outs y normalización de los índices originales. Requiere los datos autorizados y las tres ejecuciones v9; conserva evaluaciones terminadas.
2. `python src/indice_integral.py`: referencia de calibración, predicciones, puntuaciones y agregados por pitcher/arsenal para cada auditoría.
3. `python -m unittest test_complemento_pa test_dashboard_estadios_v9 -q`: casos límite e integración.
4. `python src/verificar_entrega_estadios.py --paquete`: integridad, referencias y exclusiones.

La evaluación 2026 es reutilizada. Estas mejoras no crean una prueba prospectiva nueva ni eliminan los límites causales, climáticos o de calidad de datos.
