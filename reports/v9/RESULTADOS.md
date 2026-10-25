# Experimento v9

Holdout: season; año: 2026; pitches: 135,604.
Benchmark 2026 reutilizado. Probabilidades v9 conocen contexto; no comparar sus AUC con probabilidades físicas v8 como si usaran la misma información.

| Tarea | n | RMSE / Brier | Mejora MSE/Brier vs baseline |
|---|---:|---:|---:|
| stuff_run_value | 135604 | 0.217595 | 0.22% |
| xrunvalue | 135604 | 0.213384 | 2.81% |
| arsenal_run_value | 135604 | 0.213449 | 2.75% |
| environment_run_value | 135604 | 0.213457 | 2.75% |
| whiff | 135604 | 0.091839 | 7.99% |
| whiff_given_swing | 63044 | 0.149512 | 18.47% |
| ball_in_play | 135604 | 0.121128 | 18.18% |
| groundball_given_in_play | 24033 | 0.228062 | 8.75% |
| weak_contact | 23814 | 0.218817 | 11.79% |
| hard_contact | 23814 | 0.178214 | 7.19% |
| home_run_per_pitch | 135604 | 0.006685 | 1.02% |
| called_strike | 135604 | 0.098171 | 28.67% |
| chase | 135604 | 0.098449 | 43.00% |
