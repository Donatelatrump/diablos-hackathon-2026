# Lanzamientos clasificados por estadio

Se cruzaron fechas codificadas en `PitchUID` (UUID v1) con el calendario público de la LMB de 2024–2026 y las horas de sus jugadas. La coincidencia se comprueba dentro de la misma media entrada y se complementa, según el caso, con carreras por entrada, hora inicial y duración. La altitud no decide el estadio.

Resultado: **2,009 de 2,127 juegos y 601,120 de 635,002 lanzamientos clasificados**. Se identificaron **117 juegos y 36,399 lanzamientos en Harp Helú**. Los **118 juegos restantes (33,882 lanzamientos)** conservan el estadio vacío.

## Archivos

- `Lanzamientos_clasificados_por_estadio.xlsx`: todos los lanzamientos, las 84 columnas originales y campos adicionales de clasificación. Incluye LEEME, resumen por estadio, juegos, pendientes y calendario público.
- `stuff_model_df_con_estadios.parquet`: dataset completo enriquecido para análisis/modelado, conservando los valores originales.
- `juegos_clasificados.csv`: correspondencias y evidencia detallada por juego; los candidatos pendientes están separados del estadio asignado.
- `mapeo_juego_estadio.csv`: correspondencias aceptadas con identificador del catálogo local y URL de evidencia; compatible con el argumento `--mapeo` de `estadios_v8.py`. No se aplicó automáticamente al dashboard ni al paquete de entrega.
- `resumen_estadios.csv`: conteos por temporada, estadio y estado.
- `AUDITORIA_CLASIFICACION.json`: conteos, umbrales y hash del origen.
- `fuentes/`: respuestas públicas utilizadas; `candidatos_calendario.csv` y `validacion_horas_jugadas.csv` permiten revisar el cruce.

El Parquet original no se modifica. Se verificó igualdad exacta de sus columnas y valores contra las columnas originales del resultado, además de conservar filas y orden.

Para aplicar estas correspondencias a un CSV o Excel antiguo en otra PC, usa [actualizar_estadios.py y su guía](../ACTUALIZAR_ESTADIOS.md).

## Cómo usar el Excel

En `Lanzamientos`, filtrar `referencia_harp_helu` por **Harp Helu** o **Otro estadio**. También se puede filtrar por `estadio`, `fecha_partido`, pitcher o tipo de lanzamiento. `Resumen_estadios` y `Juegos` permiten comparar cobertura antes de calcular métricas.

Los estados distinguen tres criterios reproducibles:

- `verificado_jugadas`: al menos 85% de timestamps a 30 segundos o menos de una jugada pública de la misma media entrada; mediana de diferencia de hasta 15 segundos, cobertura mínima de 85%, al menos 50 coincidencias y margen de 15 puntos porcentuales respecto de otro candidato comprobado.
- `verificado_huella_y_jugadas`: huella exacta de carreras por media entrada, hora y duración coherentes, complementada por al menos 65% de timestamps a 30 segundos y mediana de hasta 20 segundos.
- `verificado_huella_parcial_y_jugadas`: como máximo una carrera de diferencia en al menos diez medias entradas, hora y duración coherentes, al menos 70% de timestamps a 30 segundos, mediana de hasta 15 segundos y cobertura mínima de 90%.

Los dos criterios de huella exigen además un candidato claramente separado en la comparación del calendario, al menos dos medias entradas con carreras y soporte de jugadas. Los umbrales son reglas de auditoría, no probabilidades de acierto calibradas. Son correspondencias inferidas mediante fuentes públicas, no una llave oficial de la organización.

`fecha_uuid_utc` contiene el timestamp codificado; `fecha_uuid_mexico` lo convierte a America/Mexico_City. No es la hora local de todos los estadios. `fecha_partido` procede del calendario del juego aceptado. Las correcciones horarias usadas para cotejar registros se documentan en `event_hour_correction` y no alteran las fechas originales.

Los nombres comerciales proceden de la API; un venue ID puede tener varios nombres. Kanasín y Kukulcán, Laredo y Nuevo Laredo, y Vasconcelos/YU'VA se mantienen diferenciados en el catálogo local. La altitud se adjunta desde ese catálogo con su propia fuente; no se inventa cuando falta.

Control adicional: `game_001557` (26/04/2026, Olmecas–Guerreros, 11–19) coincide con el partido público [846180](https://lmb.com.mx/juegos/846180), disputado en Domingo Santana, León, pese a que Oaxaca aparece como local administrativo. Conserva `Medium Altitude` en el archivo original, mientras los demás juegos clasificados de esa sede aparecen como `Extreme Altitude`. Se mantiene el dato original y se documenta la discrepancia en `estadios_vs_categorias_observadas.csv`; no se corrige una categoría por suposición. Esto también muestra por qué no se asigna estadio únicamente a partir del equipo local.

## Fuentes y reproducción

Calendarios: `https://statsapi.mlb.com/api/v1/schedule?sportId=23&startDate=2024-03-01&endDate=2024-11-30&hydrate=venue(location),linescore,gameInfo` (también 2025 y 2026).

Jugadas: `https://statsapi.mlb.com/api/v1.1/game/{gamePk}/feed/live`. Cada juego aceptado incluye su URL específica.

Script: `../clasificar_estadios_calendario.py`; ejecutar con el Python del proyecto, en orden, los pasos `prepare`, `schedules`, `match`, `feeds`, `validate` y `export`. Requiere pandas, NumPy, PyArrow y XlsxWriter; `curl.exe` descarga fuentes públicas. Las respuestas guardadas se reutilizan.

`../exportar_excel_estadios.py` también permite reconstruir el Excel completo desde los resultados ya calculados, usando escritura por lotes y ZIP64 para el tamaño de la hoja. `verificar_archivos.py` comprueba integridad, dimensiones, cobertura y hash del origen.

Este resultado corrige el diagnóstico anterior: no hay columna de fecha completa, pero los UUID v1 sí contienen marcas temporales que permiten este cruce. Las clasificaciones añadidas no reentrenan ni revalidan automáticamente los modelos por estadio.

El Excel y el Parquet contienen datos originales de competencia y permanecen locales, fuera del ZIP de resultados.
