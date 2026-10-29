# Stuff+ Diablos · ISAC 2026

Empieza por **[la guía completa](GUIA_PROYECTO.md)**: explica el reto, sus restricciones, las tres preguntas del modelo, el enfoque ML, la validación y cómo interpretar el dashboard.

**New: [project walkthrough and ML improvement (English)](PROJECT_APPROACH.md).** Explica los requisitos del HTML, el flujo completo y la validación incremental de arsenal y entorno. El [documento técnico generado](reports/v9/DOCUMENTO_TECNICO_V9.pdf) tiene ocho páginas y documenta el experimento v9 original.

El proyecto incorpora un experimento **v9 independiente** con separación física/contextual, aprendizaje residual contra baselines, arsenal histórico regularizado y calibración/confirmación por juegos. La entrega v8 permanece disponible como referencia histórica. Una versión nueva no implica automáticamente mayor precisión: consulta los resultados medidos.

## Ejecutar

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-entrega.txt
python -m unittest test_stuff_plus_v9 -v
python entrenar_stuff_plus_v9.py --incremental-gate --iteraciones 300 --hilos 3 --salida stuff_plus_output_v9_incremental
python -m streamlit run dashboard_stuff_plus.py
```

En Windows: `.venv\Scripts\Activate.ps1`. El cargador busca el parquet completo en `Data/stuff_model_df.parquet`. Los punteros Git LFS no sustituyen los archivos reales. v9 no necesita modelos históricos para entrenar.

Cada ejecución requiere una carpeta de salida nueva. Si ya existen modelos locales, abre directamente el dashboard. La opción incremental conserva la capa anterior cuando arsenal o entorno no demuestran valor adicional en desarrollo; consulta `PROJECT_APPROACH.md` antes de interpretar un delta igual a cero.

Las ejecuciones completas `stuff_plus_output_v9_estadios`, `stuff_plus_output_v9_estadios_park` y `stuff_plus_output_v9_estadios_pitcher` incluyen sus 39 modelos CatBoost, bundles, métricas, selecciones y resultados. Después de clonar, ejecuta `git lfs install` y `git lfs pull` para descargar los archivos `.cbm` y `.parquet`. Las ejecuciones interrumpidas permanecen excluidas.

## Leer y revisar

- [Guía del enfoque y requisitos](GUIA_PROYECTO.md)
- [Resultados y documento técnico v9](reports/v9/README.md)
- [Comparación medida de la validación incremental](reports/v9_incremental/README.md)
- [Entrenamiento e inferencia v9](entrenar_stuff_plus_v9.py)
- [Entrega histórica v8](entrega_v8/README_ENTREGA.md)
- [Documentación histórica de los modelos](README_MODELOS_HISTORICOS.md)

**Alcance:** 2026 es un benchmark reutilizado. Las categorías de altitud no identifican Harp Helú. El target de carreras es un proxy, y los escenarios de entorno no son efectos causales. Los datos originales son de uso restringido a la competencia; `Data/` permanece excluido de Git. Se publican los artefactos de las tres ejecuciones v9 completas indicadas arriba.
