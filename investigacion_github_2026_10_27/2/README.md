# Stuff+ calibrado para el Harp Helú

Equipo **Data Divas** · Sports Analytics Hackathon 2026 (ISAC), presentado por Diablos Rojos del México.

Un sistema de evaluación pitch-by-pitch para la LMB que mide la calidad física de cada lanzamiento, la traduce entre ambientes y cuantifica, con datos de la propia liga, qué pierde cada forma de pitch a 2,240 metros.

## Entregables

| Entregable | Dónde |
|---|---|
| Dashboard simulador (interactivo, sin instalación) | [`docs/index.html`](docs/index.html) · versión hosteada: (https://ariadnapa.github.io/Diablos-Hackathon-2026/) |
| Reporte técnico | [`docs/reporte_tecnico.pdf`](docs/reporte_tecnico.pdf) · [versión HTML con gráficas interactivas](docs/reporte_tecnico.html) |
| Scores agregados y resultados | [`outputs/`](outputs/) |
| Código reproducible | [`src/`](src/) |

## Resultados en tres líneas

- El mismo pitcher con el mismo pitch pierde **26 % de movimiento** en el Harp Helú; su velocidad y su spin no cambian.
- El ambiente le quita **~14 puntos de Stuff+** al pitch promedio; el slider gyro es el que menos pierde (−10) y las rectas con ride/run las que más (−16).
- Un elevado en juego cuesta **0.14 carreras** en el Harp Helú contra 0.03 a nivel del mar.

## Reproducir

```bash
pip install -r requirements.txt
python src/01_pipeline.py      # limpieza, features, clustering de pitches
python src/02_altitude.py      # efecto altitud (diseño pareado por pitcher)
python src/03_targets.py       # linear weights de la LMB, xRunValue
python src/04_models.py        # Stuff+ / Location+ / Pitching+ y validación (~14 min)
python src/export_js.py        # exporta el modelo para el navegador y lo verifica
python src/05_scores.py        # escala, scores, sensibilidad, SHAP, perfil ideal
python src/05b_validation_figs.py
python src/06_dashboard.py     # genera docs/index.html
python src/07_report.py && python src/08_pdf.py
```

El dataset del hackathon (`stuff_model_df.parquet`) no se incluye en este repositorio. Para reproducir, colócalo en `data/` y ajusta `SRC` en `src/01_pipeline.py`.

## Estructura

```
src/       pipeline completo en Python (LightGBM, scikit-learn, Plotly)
docs/      dashboard y reporte (se sirven con GitHub Pages)
outputs/   métricas de validación, efecto altitud por familia, scores por pitcher, factores de traslado
```
