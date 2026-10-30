# Stuff+ Diablos · ISAC 2026

Empieza por **[la guía completa](docs/guias/GUIA_PROYECTO.md)**: explica el reto, sus restricciones, las tres preguntas del modelo, el enfoque ML, la validación y cómo interpretar el dashboard.

**New: [project walkthrough and ML improvement (English)](docs/guias/PROJECT_APPROACH.md).** Explica los requisitos del HTML, el flujo completo y la validación incremental de arsenal y entorno. El [documento técnico generado](reports/v9/DOCUMENTO_TECNICO_V9.pdf) tiene ocho páginas y documenta el experimento v9 original.

El proyecto incorpora un experimento **v9 independiente** con separación física/contextual, aprendizaje residual contra baselines, arsenal histórico regularizado y calibración/confirmación por juegos. La entrega v8 permanece disponible como referencia histórica. Una versión nueva no implica automáticamente mayor precisión: consulta los resultados medidos.

## Ejecutar

### Docker (React + API Python)

Con Docker Desktop iniciado y el modelo entrenado en
`stuff_plus_output_v9_incremental/`, ejecuta desde la raíz:

```bash
docker compose up --build -d
```

Abre **http://localhost:8000**. Un solo contenedor sirve React y la API.
Los modelos se montan en modo lectura desde tu equipo; no se incluyen en la
imagen ni se vuelven a entrenar. No necesitas iniciar Vite ni Streamlit.

```bash
docker compose logs -f
docker compose down
```

Después de volver a entrenar, ejecuta `docker compose restart` para vaciar
la caché de inferencia. Si cambias el código, repite el comando con `--build`.

### Frontend React + TypeScript

Para desarrollar con hot refresh dentro de Docker:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build -d
```

Abre **http://localhost:5173**. Los cambios en `frontend/src` se reflejan
automáticamente. Vite envía las llamadas API al contenedor Python. Las
dependencias Node viven en un volumen Docker separado de las de tu equipo.
Si cambias `package.json` o el lockfile, reinicia el frontend con
`docker compose -f compose.yaml -f compose.dev.yaml restart frontend`.
El código Python también está montado; después de editarlo, ejecuta
`docker compose -f compose.yaml -f compose.dev.yaml restart dashboard`.
Para detener ambos contenedores:

```bash
docker compose -f compose.yaml -f compose.dev.yaml down
```

El nuevo frontend está en `frontend/`. Conserva la identidad visual, la escena 3D y las vistas de simulación, comparación, lanzadores, confianza, ayuda y resultados históricos. La inferencia continúa en Python mediante `src/dashboard_api.py`.

Terminal 1, desde la raíz:

```bash
python3 src/dashboard_api.py
```

Terminal 2:

```bash
cd frontend
npm install
npm run dev
```

Abre **http://127.0.0.1:5173**. Requiere Node.js 20.19+ o 22.12+ y Python 3.11+. La API sirve los reportes guardados sin dependencias adicionales. Para simular, instala `requirements/requirements-entrega.txt` en el entorno Python y proporciona un bundle v9 completo en una de sus rutas habituales. Si no hay modelos, la interfaz muestra el estado no disponible sin inventar puntuaciones; ofrece los reportes históricos guardados y una ilustración del lanzamiento.

Para compilar y servir todo desde Python:

```bash
cd frontend
npm run build
cd ..
python3 src/dashboard_api.py
```

Abre **http://127.0.0.1:8000**. Este servidor está pensado para uso local y escucha solo en `127.0.0.1`.

Verificación:

```bash
python3 -m unittest tests.test_dashboard_api -v
cd frontend
npm run build
npm test
```

Las pruebas de navegador usan Google Chrome instalado y arrancan ambos servidores automáticamente. Consulta [la guía de migración](frontend/README.md) para el alcance y la estructura.

### Interfaz Streamlit existente

Si ya tienes el entorno y los modelos locales, inicia directamente:

```bash
python -m streamlit run app.py
```

Para preparar un entorno nuevo:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/requirements-entrega.txt
python -m unittest tests.test_stuff_plus_v9 -v
python src/entrenar_stuff_plus_v9.py --incremental-gate --iteraciones 300 --hilos 3 --salida stuff_plus_output_v9_incremental
python -m streamlit run app.py
```

En Windows: `.venv\Scripts\Activate.ps1`. El cargador busca el parquet completo en `Data/stuff_model_df.parquet`. Los punteros Git LFS no sustituyen los archivos reales. v9 no necesita modelos históricos para entrenar.

Cada ejecución requiere una carpeta de salida nueva. Si ya existen modelos locales, abre directamente el dashboard. La opción incremental conserva la capa anterior cuando arsenal o entorno no demuestran valor adicional en desarrollo; consulta `PROJECT_APPROACH.md` antes de interpretar un delta igual a cero.

## Leer y revisar

- [Guía del enfoque y requisitos](docs/guias/GUIA_PROYECTO.md)
- [Resultados y documento técnico v9](reports/v9/README.md)
- [Comparación medida de la validación incremental](reports/v9_incremental/README.md)
- [Entrenamiento e inferencia v9](src/entrenar_stuff_plus_v9.py)
- [Entrega histórica v8](entrega_v8/README_ENTREGA.md)
- [Documentación histórica de los modelos](docs/archivo/README_MODELOS_HISTORICOS.md)

**Alcance:** 2026 es un benchmark reutilizado. Las categorías de altitud no identifican Harp Helú. El target de carreras es un proxy, y los escenarios de entorno no son efectos causales. Los datos originales son de uso restringido a la competencia; `Data/` y los nuevos artefactos individuales están excluidos de Git.

## Estructura del proyecto

| Ubicación | Contenido |
| --- | --- |
| `app.py` | Entrada principal del dashboard |
| `src/` | Código del dashboard, modelos, entrenamiento y validaciones |
| `assets/visualizacion/` | Escena 3D, JavaScript, HTML y estilos |
| `requirements/` | Dependencias y versiones verificadas |
| `notebooks/` | Experimentos en Jupyter/Colab |
| `scripts/` | Herramientas de verificación en navegador |
| `docs/guias/` | Guías de uso, metodología y mantenimiento |
| `docs/archivo/` | Análisis y revisiones históricas |
| `tests/` | Pruebas automatizadas |
| `reports/` | Resultados, gráficas y documentos técnicos |
| `imgs/` | Identidad visual, fuentes e imágenes |
| `clasificacion_estadios/` | Catálogo y auditorías de estadios |
| `entrega_v8/` | Entrega histórica reproducible |

Ejecuta los comandos desde la raíz. `app.py` carga los módulos de `src/`; los scripts de entrenamiento y reportes se ejecutan con `python src/nombre_del_script.py`.
Las copias de proyectos externos, logs, temporales y ZIP generados no forman parte de la publicación.
Los modelos y datos locales se conservan en sus rutas originales; los archivos administrados por Git LFS requieren `git lfs pull`.

Consulta el [índice de documentación](docs/README.md). Desde la raíz puedes ejecutar las pruebas con:

```bash
python -m unittest discover -s tests -t . -v
node --test tests/test_dashboard_pitch_trajectory.mjs
```
