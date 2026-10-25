# Validación incremental de arsenal y entorno

Mismos 135,604 pitches, target y presupuesto de 300 iteraciones. 2026 es un benchmark reutilizado; esto no es una evaluación nueva e independiente.

| Capa | RMSE original | RMSE incremental | Reducción MSE | IC 95% por juegos |
|---|---:|---:|---:|---:|
| stuff_run_value | 0.217595 | 0.217595 | 0.000% | [0.000%, 0.000%] |
| xrunvalue | 0.213384 | 0.213384 | 0.000% | [0.000%, 0.000%] |
| arsenal_run_value | 0.213449 | 0.213384 | 0.061% | [0.036%, 0.085%] |
| environment_run_value | 0.213457 | 0.213384 | 0.068% | [0.039%, 0.104%] |

Las diferencias se calculan sobre predicciones de carreras, no sobre índices con referencias distintas. Una reducción positiva favorece el nuevo método. Los intervalos describen este benchmark y no corrigen su reutilización.

## Decisiones congeladas en desarrollo

- `arsenal_run_value`: `{'method': 'parent', 'task': 'xrunvalue'}`; control: `xrunvalue`.
- `environment_run_value`: `{'method': 'parent', 'task': 'arsenal_run_value'}`; control: `arsenal_run_value`.

Si entorno hereda la capa anterior, su delta de carreras es cero por construcción. No equivale a demostrar que no existe un efecto físico de altitud. Los clasificadores contextuales siguen siendo independientes. Esta ejecución no incorpora una nueva auditoría por pitcher o parque.

[Explicación completa](../../PROJECT_APPROACH.md)
