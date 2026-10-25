# Experimento v9

Holdout: pitcher; año: 2026; pitches: 25,426.
Benchmark 2026 reutilizado. Probabilidades v9 conocen contexto; no comparar sus AUC con probabilidades físicas v8 como si usaran la misma información.

| Tarea | n | RMSE / Brier | Mejora MSE/Brier vs baseline |
|---|---:|---:|---:|
| stuff_run_value | 25426 | 0.216408 | 0.19% |
| xrunvalue | 25426 | 0.211949 | 2.90% |
| arsenal_run_value | 25426 | 0.211960 | 2.89% |
| environment_run_value | 25426 | 0.211953 | 2.90% |
