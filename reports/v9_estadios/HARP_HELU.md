# Reentrenamiento por estadios: Harp Helu

Origen del mapeo: origin/main, commit 9e75629. Desarrollo: 499,398 pitches de 2024-2025.
Harp Helu: 30,394 pitches de desarrollo; 6,005 pitches y 19 juegos evaluados de 2026.
2026 es un benchmark reutilizado. El mapeo es inferido y auditado; no es una llave oficial.
Estadio se incorpora solo en las tareas de entorno. Los pendientes usan una categoria ausente explicita.
Los escenarios conservan fisica, ubicacion y conteo medidos; no simulan cambios aerodinamicos ni efectos causales.

| Tarea | n Harp Helu | RMSE / Brier | Ganancia vs baseline |
|---|---:|---:|---:|
| stuff_run_value | 6005 | 0.231442 | 0.25% |
| xrunvalue | 6005 | 0.227930 | 2.71% |
| arsenal_run_value | 6005 | 0.227930 | 2.71% |
| environment_run_value | 6005 | 0.227930 | 2.71% |
| whiff | 6005 | 0.088748 | 6.84% |
| whiff_given_swing | 2797 | 0.144212 | 18.34% |
| ball_in_play | 6005 | 0.124650 | 18.31% |
| groundball_given_in_play | 1118 | 0.231086 | 7.41% |
| weak_contact | 1107 | 0.218701 | 12.00% |
| hard_contact | 1107 | 0.190876 | 8.98% |
| home_run_per_pitch | 6005 | 0.008482 | 1.20% |
| called_strike | 6005 | 0.091006 | 31.69% |
| chase | 6005 | 0.097239 | 41.47% |

## Seleccion congelada

- `stuff_run_value`: `{'method': 'identity'}`.
- `xrunvalue`: `{'method': 'identity'}`.
- `arsenal_run_value`: `{'method': 'parent', 'task': 'xrunvalue'}`.
- `environment_run_value`: `{'method': 'parent', 'task': 'arsenal_run_value'}`.

La herencia de entorno implica delta cero por construccion cuando no se confirma una ganancia en desarrollo.
Predicciones observadas, escenarios, metricas y catalogo estan en esta misma carpeta.
