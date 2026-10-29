# Stuff+ v6

V6 amplía la información física disponible, compara alternativas y publica intervalos de incertidumbre. Conserva los artefactos de v5. La interfaz principal elige v6 solamente cuando existe su verificación completa.

## Entrenamiento y selección

```powershell
.\.venv\Scripts\python.exe -m unittest test_stuff_plus_v5.py test_stuff_plus_v6.py -v
.\.venv\Scripts\python.exe entrenar_stuff_plus_v6.py --fase seleccionar --hilos 6
.\.venv\Scripts\python.exe entrenar_stuff_plus_v6.py --fase evaluar --hilos 6
.\.venv\Scripts\python.exe verificar_modelo_v6.py
.\.venv\Scripts\python.exe reportar_mejora_v6.py
```

También se pueden ejecutar las dos fases seguidas con `--fase todo`. La selección lee mediante SQL únicamente temporadas hasta 2025. No permite sobrescribir un protocolo congelado. La evaluación comprueba los hashes del código, los datos y el manifest de v5; no permite reevaluar una salida ya cerrada. Para un experimento nuevo hay que utilizar otra carpeta mediante `--salida` y describirlo como un nuevo experimento, no como confirmación independiente.

Se comparan dos configuraciones CatBoost y su promedio, mezcladas con v5 con pesos predeterminados de 0.25, 0.50, 0.75 o 1.00. Una tarea conserva v5 si no logra al menos 0.1% de reducción de MSE/Brier en desarrollo 2025. Los juegos de validación interna de 2024 eligen el número de árboles de los candidatos. Tras congelar variantes y mezclas, los modelos seleccionados se ajustan con la partición interna 2024–2025 de v5 y se comparan con v5 en 2026.

**2026 ya se observó en v5 y no es un test nuevo.** No se usan sus outcomes para elegir las alternativas v6, pero la evaluación sigue siendo un benchmark reutilizado. Hace falta información posterior o nueva para una confirmación independiente. Los cambios de objetivos y de protocolo de v4 no se repiten: se conservan los targets de v5 para que esta comparación tenga una interpretación directa.

## Variables físicas

Se mantienen velocidad, spin, movimiento, release y arsenal histórico de v5. Se añaden relaciones físicas, movimiento normalizado por mano, pfxx/pfxz y proxies de aceleración paralela y perpendicular a la velocidad después de restar gravedad. Las unidades están declaradas en `stuff_plus_data_dictionary.csv`.

No se usan las componentes de velocidad inicial como entradas directas para reconstruir la ubicación en plato. Solo intervienen en la proyección de aceleración; tampoco se añaden ángulos de aproximación, outcomes, conteo, posición en plato ni lado del bateador al modelo físico. Los proxies de aceleración proceden del ajuste de trayectoria y no equivalen a una medición directa de fuerzas de Magnus o eficiencia de spin.

Las columnas físicas adicionales son `pfxx`, `pfxz`, `vx0`, `vy0`, `vz0`, `ax0`, `ay0`, `az0`. Si alguna falta o el vector de velocidad es inválido, las tareas físicas y los índices conservan v5 para esa fila. El resultado declara `enhancement_available` y `score_reference_id`; no se rellenan aceleraciones con ceros ni se mezclan las dos referencias en el ranking.

La velocidad de salida contextual conoce ubicación, conteo y lado del bateador. Se publica en `pred_exit_speed_contextual`, separada de `pred_exit_speed_given_in_play`, y no entra al índice Stuff+.

## Inferencia

```python
from entrenar_stuff_plus_v6 import load_bundle, infer
bundle = load_bundle("stuff_plus_output_v6")
predicciones = infer(frame_con_mediciones, bundle)
```

El bundle incluye los modelos v5 de respaldo: no depende de rutas externas a su carpeta. Como en v5, no necesita conocer resultados observados para inferir, y las probabilidades condicionales se predicen para todos los pitches.

## Métricas y rankings

Los resultados se guardan en [RESULTADO_MEJORA.md](../../stuff_plus_output_v6/RESULTADO_MEJORA.md), con métricas v5/v6 y un bootstrap pareado de 1,000 remuestreos de juegos. No se tratan los pitches del mismo juego como observaciones independientes. Los intervalos son condicionales a los modelos entrenados y no corrigen la reutilización de 2026 ni incorporan la incertidumbre de entrenamiento.

El ranking incluye media física cruda, score regularizado hacia la media de temporada, cantidad de pitches, cantidad de juegos e intervalo de la media cruda. Usa un peso de regularización fijo equivalente a 100 pitches; no es un prior aprendido. El intervalo usa 400 remuestreos de juegos y solo se publica cuando hay al menos cinco juegos. Se consideran elegibles para ordenar muestras de 100 pitches y cinco juegos. Esto no representa una garantía de calidad ni una medida de talento real.

## Interfaz

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements/requirements-dashboard.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

La interfaz conserva la referencia v5 si faltan mediciones adicionales. Muestra por separado la velocidad de salida física y contextual, y permite consultar los rankings con intervalos.

Con Streamlit instalado y los artefactos verificados, el flujo real se prueba sin abrir un navegador con:

```powershell
.\.venv\Scripts\python.exe -m unittest test_stuff_plus_v5.py test_stuff_plus_v6.py test_dashboard_stuff_plus_v6.py -v
```

La prueba de interfaz usa Streamlit AppTest y comprueba inferencia real, respaldo v5 cuando faltan mediciones, invariancia de Stuff+ ante cambios de ubicación y consulta del ranking.

El run value sigue siendo un proxy de pesos lineales, no RE24. Los buckets de altitud no identifican estadios y las consultas de altitud no son efectos causales.
