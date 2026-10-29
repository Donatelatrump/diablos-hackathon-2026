# Aplicar los estadios en otra PC

Descarga el repositorio o copia estos archivos manteniendo su estructura:

- `actualizar_estadios.py`
- `clasificacion_estadios/juegos_clasificados.csv`

No necesitas descargar calendarios, consultar APIs ni entrenar modelos. Las correspondencias ya están auditadas; sus criterios y limitaciones están en [clasificacion_estadios/README.md](../../clasificacion_estadios/README.md).

Instala Python 3.11 o posterior y las dependencias:

```powershell
python -m pip install pandas openpyxl xlsxwriter pyarrow
```

Desde la carpeta donde está el script, ejecuta el ejemplo correspondiente:

```powershell
python actualizar_estadios.py "datos_antiguos.csv" --salida "datos_con_estadios.csv"
python actualizar_estadios.py "datos_antiguos.xlsx" --hoja "Lanzamientos" --salida "datos_con_estadios.xlsx"
python actualizar_estadios.py "stuff_model_df.parquet" --salida "stuff_model_df_con_estadios.parquet"
```

Puedes convertir entre esos formatos cambiando la extensión de salida. Para CSV separado por punto y coma añade `--separador ";"`. La entrada CSV se interpreta como UTF-8; los identificadores deben conservarse como texto en el archivo original. `.xls` requiere guardarlo primero como `.xlsx`.

La tabla debe contener `year` y `game_anon_id` con los identificadores originales de este proyecto. No funciona con identificadores reasignados. Conserva filas, orden y columnas originales y añade estadio, fecha del partido, equipos, identificadores, altitud disponible, fuentes y estado de clasificación. No añade coordenadas geográficas ni reconstruye las fechas UUID por lanzamiento. Si ya existen columnas añadidas de estadio, se detiene para evitar conflictos.

Los 118 juegos pendientes conservan el estadio vacío. Juegos ajenos al mapeo quedan con `sin_correspondencia` y sin estadio; revisa ese estado antes de analizar resultados. El mapeo completo cubre 2,009 juegos y 601,120 lanzamientos de los 635,002 originales.

El archivo de salida debe ser nuevo: nunca se sobrescribe el original. En Excel se procesa solo la hoja indicada (por defecto la primera); se exporta una tabla de valores en una nueva hoja `Lanzamientos`, sin conservar otras hojas, fórmulas ni formato del libro. Para el dataset completo se recomienda CSV o Parquet por consumo de memoria y tiempo. La carga/escritura de Excel puede tardar varios minutos.
