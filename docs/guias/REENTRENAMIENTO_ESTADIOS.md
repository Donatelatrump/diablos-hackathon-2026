# Modelo v9 con estadios

Las correspondencias proceden de `origin/main`, commit `9e75629`, y se aplican por
`year` + `game_anon_id` mediante `actualizar_estadios.py`. Se conserva el dataset
original. El mapeo cubre 601,120 de 635,002 lanzamientos; los restantes mantienen
el estadio ausente. Es un cruce inferido y auditado con fuentes publicas, no una
llave oficial.

`--stadium-context` incorpora el identificador estable `stadium_id` como categoria
en la regresion de entorno y los clasificadores que ya utilizaban altitud.
Stuff+ fisico, ubicacion y arsenal mantienen sus respectivos conjuntos de variables.
Las columnas guardadas en cada bundle gobiernan tambien la inferencia, permitiendo
cargar modelos anteriores y modelos con estadio en el mismo simulador.

El desarrollo usa 2024-2025 y separa juegos completos para ajuste, parada temprana,
calibracion, busqueda y confirmacion. Son 499,398 lanzamientos, incluidos 30,394
identificados en Harp Helu. Se evalua 2026 con 135,604 lanzamientos, incluidos
6,005 de Harp Helu. 2026 es un benchmark reutilizado.

Se conserva el control incremental: arsenal debe superar ubicacion y entorno debe
superar arsenal en desarrollo. Cuando no confirma una mejora, la capa hereda la
prediccion anterior. Por tanto incorporar el estadio no garantiza un delta distinto
de cero en Pitching+. Los clasificadores se validan por separado.

## Reproduccion

En el entorno Python del proyecto, con las dependencias de entrenamiento y PyArrow:

```powershell
.\.venv\Scripts\python.exe actualizar_estadios.py stuff_model_df.parquet --salida stuff_model_df_con_estadios.parquet
.\.venv\Scripts\python.exe entrenar_stuff_plus_v9.py --parquet stuff_model_df_con_estadios.parquet --salida stuff_plus_output_v9_estadios --stadium-context --incremental-gate --iteraciones 400 --hilos 6
.\.venv\Scripts\python.exe reportar_estadios_v9.py
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Las salidas deben ser nuevas. Para repetir un experimento usa otra carpeta y pasa
el mismo argumento `--salida` al reporte. El comando de entrenamiento tambien
realiza la evaluacion temporal y verifica hashes de datos, codigo y modelos.

El simulador ofrece `v9 por estadios · Harp Helu` cuando existen modelos, metricas y
catalogo completos. Permite comparar hasta tres estadios, usando la categoria de
altitud modal observada en desarrollo para cada uno.

## Artefactos

En `stuff_plus_output_v9_estadios/`:

- `bundle.json`, `modelos/`, `protocolo.json`: modelos y decisiones reproducibles.
- `metricas.json`, `RESULTADOS.md`: evaluacion temporal completa.
- `metricas_harp_helu.json`, `HARP_HELU.md`: evaluacion en juegos identificados de Harp Helu.
- `scores_harp_helu_observados_2026.parquet`: predicciones para sus lanzamientos observados.
- `escenarios_harp_helu_2026.parquet`: todos los lanzamientos de 2026 contextualizados en Harp Helu.
- `arsenal_escenario_harp_helu.csv`: agregados por pitcher y tipo para ese escenario.
- `estadios.csv`: catalogo para el simulador derivado exclusivamente del desarrollo.

Los escenarios mantienen fisica, ubicacion y conteo medidos. No transportan el
movimiento aerodinamico ni representan un efecto causal de trasladar al pitcher.
Los datos enriquecidos y los resultados por lanzamiento permanecen ignorados por Git.

## Resultado de la ejecucion

Los trece modelos terminaron con un presupuesto maximo de 400 iteraciones y seis
hilos. En los 6,005 lanzamientos de 19 juegos identificados de Harp Helu en 2026,
el RMSE de carreras contextual fue 0.227930; la reduccion de MSE frente al baseline
por conteo fue 2.71%. Arsenal y entorno heredaron la prediccion de ubicacion al no
confirmar una mejora adicional en desarrollo. Por ello el resultado no demuestra
una ganancia incremental atribuible al estadio.

El resumen compartible y las metricas agregadas se conservan en
[reports/v9_estadios/HARP_HELU.md](../../reports/v9_estadios/HARP_HELU.md), junto a la
evaluacion de liga completa y el protocolo. Los clasificadores contextuales incluyen
estadio y conservan sus propias decisiones de calibracion y validacion.
