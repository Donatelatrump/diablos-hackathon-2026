# Experimento v9

Holdout: pitcher; año: 2026; pitches: 25,426.
Benchmark 2026 reutilizado. Probabilidades v9 conocen contexto; no comparar sus AUC con probabilidades físicas v8 como si usaran la misma información.

| Tarea | n | RMSE / Brier | Mejora MSE/Brier vs baseline |
|---|---:|---:|---:|
| stuff_run_value | 25426 | 0.216408 | 0.19% |
| xrunvalue | 25426 | 0.211864 | 2.98% |
| arsenal_run_value | 25426 | 0.211864 | 2.98% |
| environment_run_value | 25426 | 0.211864 | 2.98% |
| whiff | 25426 | 0.087481 | 7.36% |
| whiff_given_swing | 11593 | 0.147513 | 17.10% |
| ball_in_play | 25426 | 0.122293 | 17.52% |
| groundball_given_in_play | 4515 | 0.229069 | 8.53% |
| weak_contact | 4464 | 0.216947 | 12.82% |
| hard_contact | 4464 | 0.176334 | 6.53% |
| home_run_per_pitch | 25426 | 0.006506 | 0.90% |
| called_strike | 25426 | 0.098331 | 30.00% |
| chase | 25426 | 0.096774 | 43.73% |
