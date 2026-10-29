# Experimento v9

Holdout: park; año: 2026; pitches: 6,005.
Benchmark 2026 reutilizado. Probabilidades v9 conocen contexto; no comparar sus AUC con probabilidades físicas v8 como si usaran la misma información.

| Tarea | n | RMSE / Brier | Mejora MSE/Brier vs baseline |
|---|---:|---:|---:|
| stuff_run_value | 6005 | 0.231505 | 0.22% |
| xrunvalue | 6005 | 0.227901 | 2.78% |
| arsenal_run_value | 6005 | 0.227901 | 2.78% |
| environment_run_value | 6005 | 0.227901 | 2.78% |
| whiff | 6005 | 0.088771 | 6.82% |
| whiff_given_swing | 2797 | 0.143539 | 18.73% |
| ball_in_play | 6005 | 0.124975 | 18.09% |
| groundball_given_in_play | 1118 | 0.231712 | 7.21% |
| weak_contact | 1107 | 0.219040 | 11.86% |
| hard_contact | 1107 | 0.189652 | 9.74% |
| home_run_per_pitch | 6005 | 0.008487 | 1.16% |
| called_strike | 6005 | 0.091659 | 31.19% |
| chase | 6005 | 0.096562 | 41.87% |
