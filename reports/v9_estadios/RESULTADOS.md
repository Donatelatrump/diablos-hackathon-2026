# Experimento v9

Holdout: season; año: 2026; pitches: 135,604.
Benchmark 2026 reutilizado. Probabilidades v9 conocen contexto; no comparar sus AUC con probabilidades físicas v8 como si usaran la misma información.

| Tarea | n | RMSE / Brier | Mejora MSE/Brier vs baseline |
|---|---:|---:|---:|
| stuff_run_value | 135604 | 0.217595 | 0.22% |
| xrunvalue | 135604 | 0.213269 | 2.92% |
| arsenal_run_value | 135604 | 0.213269 | 2.92% |
| environment_run_value | 135604 | 0.213269 | 2.92% |
| whiff | 135604 | 0.091548 | 8.29% |
| whiff_given_swing | 63044 | 0.149233 | 18.63% |
| ball_in_play | 135604 | 0.120959 | 18.29% |
| groundball_given_in_play | 24033 | 0.227889 | 8.82% |
| weak_contact | 23814 | 0.218531 | 11.90% |
| hard_contact | 23814 | 0.178600 | 6.98% |
| home_run_per_pitch | 135604 | 0.006684 | 1.03% |
| called_strike | 135604 | 0.097739 | 28.98% |
| chase | 135604 | 0.097587 | 43.49% |
