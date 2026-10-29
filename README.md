# Stuff+ Diablos · ISAC 2026

Empieza por **[la guía completa](docs/guias/GUIA_PROYECTO.md)**: explica el reto, sus restricciones, las tres preguntas del modelo, el enfoque ML, la validación y cómo interpretar el dashboard.

**New: [project walkthrough and ML improvement (English)](docs/guias/PROJECT_APPROACH.md).** Explica los requisitos del HTML, el flujo completo y la validación incremental de arsenal y entorno. El [documento técnico generado](reports/v9/DOCUMENTO_TECNICO_V9.pdf) tiene ocho páginas y documenta el experimento v9 original.

El proyecto incorpora un experimento **v9 independiente** con separación física/contextual, aprendizaje residual contra baselines, arsenal histórico regularizado y calibración/confirmación por juegos. La entrega v8 permanece disponible como referencia histórica. Una versión nueva no implica automáticamente mayor precisión: consulta los resultados medidos.

## Ejecutar

Si ya tienes el entorno y los modelos locales, inicia directamente:

```bash
python -m streamlit run dashboard_stuff_plus.py
```

Para preparar un entorno nuevo:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-entrega.txt
python -m unittest tests.test_stuff_plus_v9 -v
python entrenar_stuff_plus_v9.py --incremental-gate --iteraciones 300 --hilos 3 --salida stuff_plus_output_v9_incremental
python -m streamlit run dashboard_stuff_plus.py
```

En Windows: `.venv\Scripts\Activate.ps1`. El cargador busca el parquet completo en `Data/stuff_model_df.parquet`. Los punteros Git LFS no sustituyen los archivos reales. v9 no necesita modelos históricos para entrenar.

Cada ejecución requiere una carpeta de salida nueva. Si ya existen modelos locales, abre directamente el dashboard. La opción incremental conserva la capa anterior cuando arsenal o entorno no demuestran valor adicional en desarrollo; consulta `PROJECT_APPROACH.md` antes de interpretar un delta igual a cero.

## Leer y revisar

- [Guía del enfoque y requisitos](docs/guias/GUIA_PROYECTO.md)
- [Resultados y documento técnico v9](reports/v9/README.md)
- [Comparación medida de la validación incremental](reports/v9_incremental/README.md)
- [Entrenamiento e inferencia v9](entrenar_stuff_plus_v9.py)
- [Entrega histórica v8](entrega_v8/README_ENTREGA.md)
- [Documentación histórica de los modelos](docs/archivo/README_MODELOS_HISTORICOS.md)

**Alcance:** 2026 es un benchmark reutilizado. Las categorías de altitud no identifican Harp Helú. El target de carreras es un proxy, y los escenarios de entorno no son efectos causales. Los datos originales son de uso restringido a la competencia; `Data/` y los nuevos artefactos individuales están excluidos de Git.

## Estructura del proyecto

| Ubicación | Contenido |
| --- | --- |
| `dashboard_stuff_plus.py` | Entrada principal del dashboard |
| `dashboard_*.py` | Pantallas, navegación y visualizaciones |
| `docs/guias/` | Guías de uso, metodología y mantenimiento |
| `docs/archivo/` | Análisis y revisiones históricas |
| `tests/` | Pruebas automatizadas |
| `reports/` | Resultados, gráficas y documentos técnicos |
| `imgs/` | Identidad visual, fuentes e imágenes |
| `clasificacion_estadios/` | Catálogo y auditorías de estadios |
| `entrega_v8/` | Entrega histórica reproducible |
| `entrenar_*.py`, `reportar_*.py`, `verificar_*.py` | Entrenamiento, reportes y validaciones |

Los módulos ejecutables permanecen en la raíz para conservar sus imports y rutas de datos.
Las copias de proyectos externos, logs, temporales y ZIP generados no forman parte de la publicación.
Los modelos y datos locales se conservan en sus rutas originales; los archivos administrados por Git LFS requieren `git lfs pull`.

Consulta el [índice de documentación](docs/README.md). Desde la raíz puedes ejecutar las pruebas con:

```bash
python -m unittest discover -s tests -t . -v
node --test test_dashboard_pitch_trajectory.mjs
```
