# V8: velocidad, familias y selección por juegos

V8 aplica la comparación controlada de variables y especialistas del análisis de precisión. Conserva el modelo global como respaldo y compara contra los modelos v7 entrenados exactamente con los mismos juegos. Añade ZoneSpeed, SpeedDrop y ZoneTime como bloque a cada control. Los especialistas de rectas, rompientes y cambios/splitters se prueban para whiff, whiff dado swing y bola en juego. Para las demás tareas se prueba la alternativa global.

La versión evalúa estas intervenciones antes de cambiar el objetivo. No incluye un nuevo modelo de contacto esperado ni un nuevo compuesto. El target de carreras sigue siendo un proxy; RE24 requiere información adicional de bases y secuencia. El archivo solo contiene año: no se simulan cortes mensuales a partir de IDs anónimos.

## Protocolo

Se reutilizan las particiones v7 de 2024–2025: 60% de juegos para ajuste, 10% para parada, 15% para calibración y 15% para selección. Las alternativas globales conservan la arquitectura, semilla y presupuesto del control correspondiente. Los especialistas usan los juegos de esas mismas particiones dentro de su familia; el número de árboles se decide por parada temprana.

La selección se divide por juegos en búsqueda y comprobación. Se elige una alternativa en búsqueda y se exige reducción de MSE/Brier de al menos 0.1% en ambas mitades. Ninguna temporada de comprobación puede perder más de 0.1%. En clasificación se exige no inferioridad de log loss dentro de 0.15%. Si falla, se conserva el padre; no se busca un segundo candidato utilizando comprobación. El historial de desarrollo v7 ya utilizó estos datos, por lo que ninguna mitad es una confirmación independiente de todo el proceso histórico.

Para whiff se incluyen calibradores sigmoidales aprendidos solo en calibración. Se comparan probabilidades crudas con controles crudos para aislar cambios; la comparación final exportada mide v8 contra la salida completa v7. Por eso una mejora de selección frente al control no garantiza superar al padre desplegado en todas las métricas.

El protocolo y hashes se guardan antes del ajuste. La selección se congela antes de leer 2026 en esta ejecución. **2026 ya se usó en versiones anteriores y sigue siendo un benchmark reutilizado.** No se reajusta v8 con sus resultados.

## Ejecución

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dashboard.txt
.\.venv\Scripts\python.exe -m unittest test_stuff_plus_v8 -v
.\.venv\Scripts\python.exe entrenar_stuff_plus_v8.py --fase todo --hilos 6
.\.venv\Scripts\python.exe verificar_modelo_v8.py
.\.venv\Scripts\python.exe reportar_mejora_v8.py
.\.venv\Scripts\python.exe -m unittest test_dashboard_stuff_plus_v8 -v
.\.venv\Scripts\python.exe -m streamlit run dashboard_stuff_plus.py
```

Las fases `entrenar` y `evaluar` pueden ejecutarse por separado. Una salida con protocolo existente no se sobrescribe. El código y los datos deben conservar sus hashes entre fases. La preparación requiere los artefactos v7 originales; el bundle final contiene los modelos padres necesarios para inferencia sin consultar otras carpetas de salida.

```python
from entrenar_stuff_plus_v8 import load_bundle, infer
bundle = load_bundle("stuff_plus_output_v8")
predicciones = infer(datos, bundle)
```

Las mediciones nuevas deben corresponder al mismo lanzamiento. Si faltan valores finitos o física adicional válida, se usa exactamente v7 para esa fila. Las tareas rechazadas conservan v7. Si el modelo directo de carreras se acepta, Stuff+ y Location+ usan una referencia fija de calibración; Pitching+ conserva el modelo contextual anterior. Los tipos no conocidos por los especialistas usan el global. La interfaz principal activa v8 solo tras verificar artefactos y aceptar algún cambio con desarrollo.

Las salidas activas son las probabilidades públicas `p_*`, las predicciones de cada tarea y los índices. Las columnas auxiliares `component_*`, `pred_stack_candidate` y `pred_physical_control` se heredan de v7 para diagnóstico de su compuesto; no deben reinterpretarse como componentes reentrenados de un compuesto v8. V8 no ajusta ese compuesto.

## Artefactos

`stuff_plus_output_v8` contiene protocolo, particiones, roles de búsqueda/comprobación, modelos, predicciones de todas las alternativas en selección, selección congelada, bundle portable, scores, métricas con bootstrap por juegos, ranking, gráfica y reporte. `verificar_modelo_v8.py` reproduce decisiones y muestras de predicciones, comprueba hashes, separación por juegos, respaldo, independencia del tamaño del lote e inferencia sin resultados observados.

El siguiente experimento de contacto esperado debe construirse con objetivos fuera de muestra y evaluarse por separado. La siguiente confirmación temporal requiere fechas y datos futuros reservados.
