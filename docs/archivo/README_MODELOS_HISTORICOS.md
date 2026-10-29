# Stuff+ Diablos · modelos v8, v7, v6 y v5

**Entrega vigente:** [Documento técnico PDF](../../entrega_v8/DOCUMENTO_TECNICO_V8.pdf), [guía de entrega](../../entrega_v8/README_ENTREGA.md), [recomendaciones y casos](../../entrega_v8/RECOMENDACIONES_V8.md) y [paquete compartible](../../ENTREGA_DIABLOS_V8.zip). Incluye auditoría de pitchers no vistos, análisis ajustado por categorías de entorno, mapa de movimiento y fichas operativas. El dashboard principal abre estas vistas. Los documentos históricos v3/v4 no forman parte de la entrega.

**V8** compara nuevas mediciones de velocidad y especialistas por familia contra controles entrenados con los mismos juegos. [Instrucciones v8](README_MODELO_V8.md) · [Resultados v8](../../stuff_plus_output_v8/RESULTADO_MEJORA.md). Los cambios deben superar búsqueda y comprobación por juegos anteriores a 2026; las tareas rechazadas conservan el respaldo. El dashboard activa v8 cuando sus artefactos están verificados y se aceptó alguna alternativa. 2026 sigue siendo un benchmark reutilizado.

**V7** incorpora calibración de probabilidades y un compuesto aprendido con predicciones fuera de muestra por juegos. [Reproducir v7](README_MODELO_V7.md) · [Resultados v7](../../stuff_plus_output_v7/RESULTADO_MEJORA.md). La selección utiliza juegos separados de 2024–2025; 2026 es un benchmark reutilizado. El dashboard activa v7 después de verificar sus artefactos si se aceptó algún cambio en selección; de lo contrario conserva v6. Los bundles anteriores se mantienen para comparación y respaldo.

**V6** incorpora variables físicas adicionales, selección de alternativas con 2025, comparación pareada por juegos y rankings con intervalos. [Instrucciones v6](README_MODELO_V6.md) · [Resultados y límites](../../stuff_plus_output_v6/RESULTADO_MEJORA.md).

V6 mejora tareas seleccionadas y conserva v5 cuando no se demuestra mejora en desarrollo. La interfaz principal utiliza v6 cuando sus artefactos están verificados. El bundle v6 contiene su respaldo v5 y permite inferencia sin depender de otra carpeta.

Los pasos siguientes reproducen **v5**, base del entrenamiento y la comparación v6.

Modelo CatBoost para lanzamientos de LMB. La versión v5 corrige la independencia temporal, los scores incompletos y la mezcla de experimentos detectados en v4. Los archivos anteriores se conservan como antecedentes.

## Ejecutar

Desde la carpeta del proyecto, con Python 3.11 o posterior y las dependencias de `requirements/requirements-hackathon.txt`:

```powershell
.\.venv\Scripts\python.exe -m unittest test_stuff_plus_v5.py -v
.\.venv\Scripts\python.exe entrenar_stuff_plus_v5.py --iteraciones 250 --hilos 6
.\.venv\Scripts\python.exe verificar_modelo_v5.py
.\.venv\Scripts\python.exe reportar_mejora_v5.py
```

El entrenamiento evalúa 2025 usando solamente datos de 2024 y evalúa 2026 usando solamente 2024–2025. Dentro de cada historia, reserva juegos completos para early stopping y para elegir cuánto mezclar cada predicción con el baseline de entrenamiento. La temporada de test no decide parámetros. Los modelos exportados son exactamente los evaluados; no se reajustan incluyendo test.

El arsenal de cada temporada utiliza únicamente temporadas anteriores. No se infiere orden temporal a partir de IDs anónimos. Sin historia, las características de arsenal permanecen ausentes y el modelo recibe una bandera explícita.

## Resultados

`stuff_plus_output_v5/` contiene:

- `scores_pitch_v5.parquet`: una fila por PitchUID evaluado, sin mezclar holdouts superpuestos; no incluye 2024, que carece de una temporada anterior de entrenamiento.
- `metricas_validacion_v5.json`: métricas temporales y comparación con baseline; para valor de carreras también baseline por conteo construido solamente con fit.
- `pitchers_por_temporada.csv` y `arsenal_por_temporada.csv`: agregados por temporada, con tamaño de muestra.
- `holdout_2026/`: modelos evaluados, referencias de escala, perfiles históricos, metadatos y listas de filas de fit y validación.
- `manifest.json`: parámetros, versiones y hashes del código y del origen.
- `RESULTADO_MEJORA.md` e `importancia_variables.csv`: comparación descriptiva e importancia de variables por tarea, generadas con `reportar_mejora_v5.py`. Las importancias son PredictionValuesChange de CatBoost, no SHAP ni efectos causales.

Las predicciones de resultados condicionales se generan para todos los pitches: por ejemplo P(rodado | bola en juego) se estima incluso si el pitch observado no terminó en contacto. La condición restringe entrenamiento y evaluación, no inferencia.

## Definición de los índices

El target `run_value_proxy` usa pesos lineales fijos para resultados observados. **Es una aproximación, no RE24 ni una reconstrucción empírica de 24 estados base-out.** No se estiman promedios de targets con datos de test.

- Stuff+: negativo del valor esperado con variables físicas y arsenal, sin ubicación, conteo ni altitud.
- Location+: diferencia entre el valor esperado físico y el esperado al incorporar ubicación, conteo y lado del bateador. Es una contribución contextual predictiva, no una medida causal de command.
- Pitching+: negativo del valor esperado físico, contextual y de altitud combinado.

Cada índice utiliza `100 + 10 * (raw - media_referencia) / desviacion_referencia`. La referencia se guarda usando la validación interna de la historia de entrenamiento. No se recalcula con test ni con cada consulta nueva; por ello una temporada futura no tiene que promediar exactamente 100. Las referencias difieren entre bundles: los rankings se separan por temporada.

Contacto débil significa ExitSpeed <85 mph; contacto fuerte significa ExitSpeed >=95 mph. Por compatibilidad, la clave de tarea de contacto fuerte sigue siendo `barrel_or_hard_contact`, pero no representa un barrel ni es directamente comparable con el target antiguo que exigía un ángulo específico.

## Inferencia y dashboard

```python
from entrenar_stuff_plus_v5 import load_bundle, infer
bundle = load_bundle("stuff_plus_output_v5/holdout_2026")
scores = infer(frame_con_mediciones, bundle)
```

Las columnas necesarias están en `PHYSICAL`, `LOCATION` y las transformaciones de `features` y `apply_profile`. No se necesitan outcomes para inferir. Un pitcher desconocido usa características de arsenal ausentes.

Instalar `requirements/requirements-dashboard.txt` y ejecutar:

```powershell
.\.venv\Scripts\python.exe -m streamlit run src/dashboard_stuff_plus_v5.py
```

Esta interfaz usa los modelos exportados y la misma función de inferencia. La entrada habitual `dashboard_stuff_plus.py` también abre v5. El simulador heurístico anterior se conserva en `dashboard_stuff_plus_legacy.py` como antecedente.

## Límites

Los buckets de altitud no identifican estadios. Cambiar el bucket en una consulta no modela automáticamente el cambio de movimiento ni prueba causalidad. Las comparaciones entre pitchers requieren contexto y suficiente muestra. No se ha estimado un intervalo de confianza del ranking. Los holdouts por pitcher y estadio deben diseñarse como experimentos separados antes de afirmar generalización a pitchers nuevos o parques concretos.

El análisis previo está en `ANALISIS_INTEGRAL_PROYECTO.md`. La mejora de integridad no garantiza mejoras en cada AUC; los resultados reales se reportan tras el entrenamiento.
