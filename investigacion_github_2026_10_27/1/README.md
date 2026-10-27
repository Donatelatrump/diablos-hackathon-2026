# Diablos Stuff+

Calidad de lanzamiento ajustada por la altitud del Estadio Alfredo Harp Helú.
**Hackathon ISAC 2026 · Reto Diablos Rojos del México.**

El Harp Helú está a 2,240 metros, más alto que Coors Field. Ahí hay 20 % menos aire, y el movimiento de
un lanzamiento lo produce el aire. Este proyecto califica los 635,002 lanzamientos de la LMB de 2024 a 2026,
mide cuánto vale cada uno en el Harp Helú y le dice al club qué lanzadores le sirven en casa.

| | |
|---|---|
| **Dashboard alojado anterior, pendiente de actualizar** | https://claude.ai/artifact/1HXhuyBtkDd6szvLv9M7xo |
| **Dashboard corregido preparado** | [`entrega/actualizar_artifact.md`](entrega/actualizar_artifact.md), paquete de actualización y respaldo autónomo |
| **Código de esta entrega** | [rama corregida](https://github.com/dulongski/diablos-hackathon/tree/main) |
| **Documento técnico** | [`entrega/documento_tecnico.pdf`](entrega/documento_tecnico.pdf) |
| **Reporte ejecutivo** | [`entrega/reporte.pdf`](entrega/reporte.pdf) |

## La respuesta corta

La transferencia física permite comparar el mismo lanzamiento en aire de nivel del mar y de altura. La recta resulta más sensible que el cutter, pero las pérdidas y los perfiles dependen del modelo. El dashboard y los documentos toman sus cifras de los mismos JSON para que las recomendaciones se actualicen juntas.

Se conserva el modelo entrenado de producción y se corrige la referencia de transferencia. Las métricas predictivas por lanzamiento son pequeñas. La validación por categoría de altitud no equivale a dejar fuera un estadio, y las asociaciones entre temporadas son retrospectivas. Los límites completos están en el documento técnico y en `CLAUDE.md`.

## Cómo funciona

La altitud no entra al modelo como una variable. Entra por física.

1. **Medimos el aire en la trayectoria.** Los datos no dicen el estadio, pero Trackman mide cuánto frena
   cada pelota, y eso depende del aire.
2. **Volamos cada lanzamiento en el otro aire.** El lanzador suelta igual, y sólo cambia el aire. El simulador de vuelo
   reproduce la cifra de Alan Nathan para Coors Field (18 pulgadas se vuelven 14.9).
3. **Lo calificamos otra vez.** Stuff+ sólo ve física, así que la diferencia es el efecto del aire.

Tres capas, como pide el reto. Stuff+ (física pura), Location+ (más ubicación y conteo) y Pitching+ (más
arsenal y secuencia, con las variables relacionales contra la recta del lanzador). Todo con LightGBM y
evaluado con lanzadores, temporada y categoría de altitud fuera del ajuste del calificador. La preparación global de tablas del objetivo limita el aislamiento de toda la validación.

## Dónde está cada cosa que pide el reto

| Lo que pide el reto | Dónde lo respondemos |
|---|---|
| Stuff+, Location+ y Pitching+ por lanzamiento, pitcher y arsenal | Dashboard, pestañas Lanzadores y Arsenal y perfil |
| Stuff+ en CDMX contra otros estadios de la LMB | Arsenal y perfil, y `scripts/10_local_extras.py` para los tres entornos |
| Perfil físico ideal con argumento físico y estadístico | Arsenal y perfil, documento técnico 6.2 |
| Qué gana, qué pierde, riesgo de jonrón, cómo perfilar un prospecto | Arsenal y perfil, documento técnico 7 |
| Simulador con Stuff+ lado a lado y mapa de movimiento | Pestaña Simulador |
| Documento técnico de 6 a 10 páginas | `entrega/documento_tecnico.pdf` |
| Hipótesis H1 a H4 | Pestaña Hipótesis, documento técnico 5 |
| Causal Forest táctico (opcional) | Pestaña Causal Forest, `scripts/09` y `scripts/10` |
| Calibración y modelo nulo | Pestaña Validación |
| Pruebas de robustez (categoría de altitud con física, discriminación, futuro, combinación ponderada) | Pestaña Validación, documento Anexo C, `scripts/11_robustez.py` |
| Holdout de lanzador, temporada y categoría de altitud | Pestaña Validación |
| Variables de arsenal e interpretación con SHAP | Pestaña Metodología |

## Correr el proyecto

Los datos de la LMB no están en el repositorio. Pon `stuff_model_df.parquet` en la raíz y corre esto.

```bash
uv venv && uv pip install -e . && uv pip install econml
python scripts/01_physics.py        # densidad del aire y transferencia de forma
python scripts/02_features.py       # secuencia, arsenal, objetivos
STUFF_ENTRENA=todo python scripts/03_models.py  # las tres capas y sus holdouts
python scripts/04_export.py         # modelo y tablas al simulador
python scripts/05_deliverables.py   # entregables 1, 2 y 3
python scripts/04_export.py         # actualiza compresion.json desde 05
python scripts/07_jurado.py         # tabla por lanzador, calibración y mapa
python scripts/08_hipotesis.py      # H1 a H4
python scripts/09_causal_forest.py  # Causal Forest de entorno
python scripts/10_local_extras.py   # Causal Forest táctico, SHAP y tres entornos
python scripts/11_robustez.py       # pruebas de robustez (categoría de altitud con física, discriminación, futuro, combinación)
```

El dashboard corre completo en el navegador. El enlace público anterior puede corresponder a una versión previa de esta revisión. La compilación local en `app/dist` y los PDF de esta carpeta contienen la entrega regenerada.

```bash
cd app && npm install && npm test && npm run dev
```

`npm test` verifica que el simulador reproduce el lanzamiento que le pides y que el evaluador de árboles
del navegador coincide exacto con LightGBM.

Los documentos se regeneran desde los datos exportados.

```bash
python3 docs/tecnico.py && node docs/pdf.mjs entrega/documento_tecnico.html entrega/documento_tecnico.pdf
python3 docs/reporte.py && node docs/pdf.mjs entrega/reporte.html entrega/reporte.pdf lamina
python3 docs/estilo.py entrega/documento_tecnico.html entrega/reporte.html
python3 docs/verifica_cifras.py     # cifras del documento que ya no salen de los datos
```

## Estructura

```
src/stuffplus/   física, variables, modelos y exportación
scripts/         las etapas del análisis, en orden
app/             dashboard y simulador (Vite, React y three.js)
docs/            documento técnico, reporte y revisión de estilo
entrega/         los PDF y el borrador del correo
artifacts/       modelos entrenados y tablas agregadas
```

Usamos los datos de la LMB sólo para esta competencia. El repositorio presenta resultados, no datos.
