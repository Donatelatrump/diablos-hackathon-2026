# Modelo v7: calibración y compuesto OOF

Esta versión evalúa calibradores de whiff y un compuesto aprendido de componentes físicos. Las decisiones se congelan con datos anteriores a 2026. **2026 ya se examinó en v5/v6: es un benchmark reutilizado, no una confirmación independiente.**

## Separación de datos

Los juegos de cada temporada 2024–2025 se distribuyen de forma reproducible entre entrenamiento (60%), parada temprana (10%), calibración (15%) y selección (15%). Ningún juego comparte roles. Dentro del entrenamiento se generan tres bloques de predicciones fuera de muestra (OOF): cada lanzamiento lo predice un modelo que no entrenó con su juego. Los perfiles de arsenal usan temporadas anteriores.

Se entrenan siete componentes: whiff, whiff dado swing, bola en juego, rodado dado contacto, jonrón por pitch, velocidad de salida dado contacto y un control directo de valor de carreras. Los seis primeros usan las variables físicas ampliadas; el control usa las variables físicas v5. La ubicación, conteo, lado del bateador y altitud quedan fuera de estos componentes.

## Calibración y selección

Se comparan identidad, sigmoide e isotónica. Los mapas se ajustan solamente en juegos de calibración. La selección exige mejorar ECE, sin deterioros relevantes de Brier, log loss o ECE por cuantiles. Si ninguna alternativa cumple, se conserva identidad. Cada bloque OOF usa el mapa ajustado con las predicciones de su propio modelo sobre los juegos de calibración.

El compuesto usa ocho señales, incluyendo probabilidades marginales de rodado y velocidad de salida esperada por pitch. Una regresión regularizada con signos restringidos aprende sus pesos exclusivamente con predicciones OOF. Se comparan regularización, componentes crudos/calibrados y mezclas con el control directo usando exclusivamente selección. Se exige al menos 0.1% de reducción de MSE frente al control para promover el compuesto.

El conjunto de entrenamiento difiere de v6. El reporte separa el efecto de calibrar el mismo núcleo v7, el compuesto frente a su control con los mismos datos y la comparación total v6/v7.

## Reproducir

Desde la raíz, con el entorno de `requirements-hackathon.txt`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dashboard.txt
.\.venv\Scripts\python.exe entrenar_stuff_plus_v7.py --fase todo --hilos 6
.\.venv\Scripts\python.exe verificar_modelo_v7.py
.\.venv\Scripts\python.exe reportar_mejora_v7.py
.\.venv\Scripts\python.exe -m unittest discover
.\.venv\Scripts\python.exe -m streamlit run dashboard_stuff_plus.py
```

También pueden ejecutarse por separado las fases `preparar`, `seleccionar` y `evaluar`. El protocolo guarda hashes del código y datos antes del ajuste; la selección se guarda antes de leer el benchmark 2026. No cambies el script entre fases. Conserva los artefactos originales para auditar una ejecución.

## Inferencia y entrega

```python
from entrenar_stuff_plus_v7 import load_bundle, infer
bundle = load_bundle("stuff_plus_output_v7")
predicciones = infer(datos_sin_resultados, bundle)
```

El bundle incluye una copia portable del modelo v6. Si faltan mediciones físicas adicionales válidas, se conserva exactamente la salida pública del modelo anterior. Si se promueve el compuesto, Stuff+ y Location+ usan una referencia fija aprendida en calibración; Pitching+ conserva v6. Si no se promueve, se conservan los índices anteriores. Los índices de referencias diferentes no deben mezclarse sin identificarlas.

El dashboard principal activa v7 únicamente después de verificar sus artefactos y si la selección anterior a 2026 aceptó al menos un cambio. La interfaz v7 también puede abrirse directamente con `dashboard_stuff_plus_v7.py`.

Los principales entregables están en `stuff_plus_output_v7`: protocolo, particiones, modelos de cada bloque, predicciones OOF, selección congelada, bundle, métricas, scores, pesos, curvas de calibración y reporte. El verificador reproduce muestras de predicciones, mapas y pesos, revisa la exclusión de juegos, hashes, inferencia sin resultados, invariancia física y fallback.

## Límites

El objetivo de carreras sigue siendo un proxy con pesos fijos, no RE24. Las probabilidades condicionales se marginalizan antes de combinarse cuando corresponde. La altitud agrupada no identifica estadios ni efectos causales. Los intervalos remuestrean juegos y describen incertidumbre del benchmark, no talento real. La siguiente confirmación independiente requiere datos futuros no usados durante el desarrollo.
