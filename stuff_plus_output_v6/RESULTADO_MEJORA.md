# Resultado de la mejora v6

Se generaron **135,604 scores únicos de 2026**. Se seleccionaron mejoras para **3 de 6 tareas** usando exclusivamente 2025; las demás conservan v5.

2024 sirve para entrenar candidatos; juegos completos de 2024 deciden early stopping. La selección de variantes y mezcla se hace con resultados temporales de 2025. Luego se vuelven a entrenar las alternativas seleccionadas con la misma partición interna 2024–2025 de v5, sin incorporar 2026 al ajuste.

**2026 ya fue evaluado durante v5.** Es un benchmark temporal reutilizado, no un test nuevo e intacto. Las elecciones quedaron congeladas antes de calcular los resultados v6 de 2026; no se repitió la selección con esos resultados. Para confirmar generalización hace falta una temporada posterior o datos nuevos.

## Qué cambia

Las nuevas variables combinan movimiento normalizado por mano, relaciones entre spin/velocidad y extensión/altura, pfxx/pfxz y proyecciones de aceleración tras sustraer gravedad. No se añaden posición en plato, conteo, lado del bateador, ángulos de aproximación ni resultados al modelo físico. Las proyecciones de aceleración son proxies del ajuste de trayectoria: no son mediciones directas de Magnus ni de eficiencia de spin.

Cada tarea puede conservar v5, mezclarlo con una alternativa o combinar dos alternativas. La mejora mínima para cambiar es 0.1% de MSE/Brier en desarrollo 2025. Las seis tareas comparadas se fijaron antes de evaluar 2026.

## Selección congelada con 2025

| Tarea | Miembros seleccionados | Peso nuevo | Reducción relativa MSE/Brier en desarrollo |
|---|---|---:|---:|
| whiff | deep | 1.00 | 0.68% |
| whiff_given_swing | deep | 1.00 | 3.92% |
| exit_speed_given_in_play | v5 | 0.00 | 0.00% |
| stuff_run_value | v5 | 0.00 | 0.00% |
| environment_run_value | v5 | 0.00 | 0.00% |
| exit_speed_contextual | deep | 1.00 | 14.39% |

## Comparación pareada en 2026

| Tarea | Métrica | v5 | v6 | Reducción MSE/Brier | IC 95% de esa reducción |
|---|---|---:|---:|---:|---|
| whiff | AUC (v5) | 0.62598 | 0.65079 | 1.05% | [0.96%, 1.15%] |
| whiff_given_swing | AUC (v5) | 0.63555 | 0.68152 | 3.61% | [1.93%, 4.83%] |
| exit_speed_given_in_play | RMSE (v5) | 15.30304 | 15.30304 | 0.00% | [0.00%, 0.00%] |
| stuff_run_value | RMSE (v5) | 0.21764 | 0.21764 | 0.00% | [0.00%, 0.00%] |
| environment_run_value | RMSE (v5) | 0.21308 | 0.21308 | 0.00% | [0.00%, 0.00%] |
| exit_speed_contextual | RMSE (v5 físico) | 15.30304 | 14.02020 | 16.06% | [15.07%, 17.03%] |

### Calibración de probabilidades

| Tarea | Brier v5 | Brier v6 | ECE v5 | ECE v6 |
|---|---:|---:|---:|---:|
| whiff | 0.097954 | 0.096926 | 0.002215 | 0.003355 |
| whiff_given_swing | 0.176052 | 0.169694 | 0.005097 | 0.023401 |

La mejora del Brier no implica que cada medida de calibración mejore. La ECE aumenta en este benchmark, especialmente para whiff dado swing: las probabilidades discriminan mejor y tienen menor error global, pero su calibración por bins empeora. No se recalibran usando estos resultados de 2026. Hace falta una muestra adicional, separada de evaluación, para verificar una recalibración futura.

En la columna Reducción MSE/Brier, un valor positivo indica menor error que v5; negativo indica deterioro. AUC mayor es mejor; RMSE menor es mejor. Los intervalos usan 1,000 remuestreos pareados de juegos completos, conservando la dependencia entre pitches del mismo juego. Son condicionales a estos modelos ajustados y no incluyen la incertidumbre de volver a entrenar ni eliminan el sesgo de reutilizar un benchmark. Si el intervalo cruza cero, la mejora no es concluyente bajo este procedimiento.

La velocidad de salida contextual añade ubicación, conteo y lado del bateador y se publica como salida separada. Su comparación es contra la velocidad física de v5: mejorar con más información no significa haber mejorado la predicción física. Esa salida contextual no entra a Stuff+.

## Scores y rankings

Stuff+ conserva la definición de valor esperado físico negativo. Location+ y Pitching+ mantienen sus definiciones de v5; sus referencias se recalculan solamente con validación interna anterior a 2026 y se guardan en el bundle. No se normaliza con test. El run value sigue siendo un proxy de pesos fijos, no RE24 ni un efecto causal.

En esta ejecución no se seleccionaron reemplazos para valor físico de carreras ni valor con entorno: los modelos que sustentan los índices permanecen en v5. Las mejoras predictivas de whiff se publican explícitamente como probabilidades; no se presentan como una mejora demostrada del índice Stuff+ compuesto.

El ranking contiene 2,936 combinaciones pitcher/tipo. Ordena primero las que tienen al menos 100 pitches y cinco juegos, y aplica shrinkage fijo de 100 pitches hacia la media de la temporada. Es una regularización descriptiva predeterminada, no una estimación empírica bayesiana del prior.

Los intervalos del ranking corresponden a la media Stuff+ **sin shrinkage** y usan 400 remuestreos de juegos. Describen variación de scores, no incertidumbre sobre el talento real ni sobre los parámetros del modelo. Con menos de cinco juegos no se publica intervalo. No se mezclan referencias v5 y v6 en el ranking. Se publican también las probabilidades medias de whiff y las dos estimaciones de velocidad de salida para consultar las tareas predictivas sin confundirlas con el índice compuesto.

Hay 0 pitches sin las mediciones físicas adicionales. Si faltan en una consulta nueva, la inferencia conserva los outputs e índices de v5 para esa fila y declara `score_reference_id=v5_fallback`; la predicción contextual puede seguir disponible.

## Artefactos y uso

- `bundle.json`, `base_v5/` y `modelos/`: bundle autocontenido con pesos, referencias y modelos de respaldo.
- `protocolo_congelado.json`: selección anterior al benchmark y hashes de código/datos.
- `scores_pitch_v6.parquet`: predicciones nuevas y de comparación, una fila por pitch.
- `metricas_benchmark_2026.json`: métricas y bootstrap por tarea.
- `arsenal_con_incertidumbre.csv`: ranking regularizado con intervalos por juego.
- `importancia_variables.csv`: PredictionValuesChange por modelo, sin atribución causal.

Ejecutar `verificar_modelo_v6.py` para auditar artefactos, datos, inferencia y fallback. Consultar `README_MODELO_V6.md` para reproducir las fases separadas.
