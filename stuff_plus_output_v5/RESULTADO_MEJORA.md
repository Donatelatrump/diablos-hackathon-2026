# Resultado de la mejora v5

Se generaron **391,748 predicciones temporales únicas**. Se entrenaron trece tareas por holdout y se conservaron los modelos exactos utilizados en evaluación.

La temporada evaluada no interviene en entrenamiento, selección de iteraciones, mezcla con baseline ni referencia de normalización. Los modelos se seleccionan con juegos completos reservados dentro de temporadas anteriores.

## Comparación descriptiva con v4

Cambian la partición interna, las variables y el protocolo. Esta tabla no es un experimento controlado que aísle una única modificación. Las métricas v4 son las guardadas anteriormente, con los límites descritos en el análisis integral.

| Holdout | Tarea | AUC v4 | AUC v5 | Brier skill v4 | Brier skill v5 |
|---|---|---:|---:|---:|---:|
| season_holdout_2025 | whiff | 0.6319 | 0.6308 | 0.0197 | 0.0204 |
| season_holdout_2025 | whiff_given_swing | 0.6407 | 0.6387 | 0.0422 | 0.0421 |
| season_holdout_2025 | ball_in_play | 0.5520 | 0.5504 | 0.0047 | 0.0048 |
| season_holdout_2025 | called_strike | 0.8716 | 0.8820 | 0.2666 | 0.2922 |
| season_holdout_2025 | chase | 0.9049 | 0.9133 | 0.3915 | 0.4301 |
| season_holdout_2025 | groundball_given_in_play | 0.6193 | 0.6151 | 0.0443 | 0.0452 |
| season_holdout_2025 | home_run_per_pitch | 0.5666 | 0.5628 | -0.4504 | 0.0003 |
| season_holdout_2026 | whiff | 0.6230 | 0.6260 | 0.0176 | 0.0187 |
| season_holdout_2026 | whiff_given_swing | 0.6328 | 0.6356 | 0.0383 | 0.0400 |
| season_holdout_2026 | ball_in_play | 0.5447 | 0.5437 | 0.0036 | 0.0035 |
| season_holdout_2026 | called_strike | 0.8571 | 0.8761 | 0.2477 | 0.2885 |
| season_holdout_2026 | chase | 0.9035 | 0.9137 | 0.3884 | 0.4331 |
| season_holdout_2026 | groundball_given_in_play | 0.6244 | 0.6219 | 0.0468 | 0.0482 |
| season_holdout_2026 | home_run_per_pitch | 0.5730 | 0.5670 | -0.6045 | 0.0004 |

Brier skill positivo indica menor error que la probabilidad constante de entrenamiento; negativo indica peor resultado. La ponderación de clase fija de v4 se eliminó. V5 elige la mezcla con el baseline solo con validación interna.

## Targets corregidos y valor esperado

Contacto débil y fuerte tienen definiciones nuevas basadas exclusivamente en ExitSpeed. xRunValue deja de ser una media global por estado y pasa a predecir un proxy individual con pesos fijos. Por ello no se comparan sus AUC/R² directamente con v4.

| Holdout | Tarea | Métrica | Resultado | Comparación con baseline |
|---|---|---|---:|---:|
| season_holdout_2025 | weak_contact | AUC | 0.5651 | Brier skill +0.0126 |
| season_holdout_2025 | barrel_or_hard_contact | AUC | 0.5523 | Brier skill +0.0062 |
| season_holdout_2025 | exit_speed_given_in_play | RMSE | 15.27093 | MSE skill +0.0119 |
| season_holdout_2025 | stuff_run_value | RMSE | 0.22196 | MSE skill +0.0023; vs. conteo -0.0120 |
| season_holdout_2025 | xrunvalue | RMSE | 0.21764 | MSE skill +0.0408; vs. conteo +0.0270 |
| season_holdout_2025 | environment_run_value | RMSE | 0.21765 | MSE skill +0.0407; vs. conteo +0.0270 |
| season_holdout_2026 | weak_contact | AUC | 0.5604 | Brier skill +0.0107 |
| season_holdout_2026 | barrel_or_hard_contact | AUC | 0.5508 | Brier skill +0.0073 |
| season_holdout_2026 | exit_speed_given_in_play | RMSE | 15.30304 | MSE skill +0.0111 |
| season_holdout_2026 | stuff_run_value | RMSE | 0.21764 | MSE skill +0.0018; vs. conteo -0.0109 |
| season_holdout_2026 | xrunvalue | RMSE | 0.21315 | MSE skill +0.0425; vs. conteo +0.0303 |
| season_holdout_2026 | environment_run_value | RMSE | 0.21308 | MSE skill +0.0431; vs. conteo +0.0309 |

## Contrapartidas y límites predictivos

La regresión de velocidad de salida conserva el target, pero v5 elimina la ubicación de sus entradas para mantener una evaluación física separada. El error aumenta respecto al modelo contextual anterior:

| Holdout | RMSE velocidad de salida v4 (mph) | RMSE v5 físico (mph) |
|---|---:|---:|
| season_holdout_2025 | 14.465 | 15.271 |
| season_holdout_2026 | 14.389 | 15.303 |

El valor de carreras físico muestra una señal pequeña; no debe interpretarse su escala normalizada como prueba de gran capacidad predictiva. Un score físico no dispone del conteo, por lo que puede mejorar el baseline constante y aun rendir peor que un baseline que sí conoce conteo. Los pesos de carreras siguen siendo aproximados, sin ocupación de bases. Una mejora de integridad no implica que cada tarea mejore su discriminación.

## Uso

Los modelos y sus referencias están en `holdout_2025/` y `holdout_2026/`. La tabla operativa contiene una fila por pitch y los resultados condicionales se infieren para todos los lanzamientos, con independencia de su resultado observado. Los rankings se separan por temporada y declaran tamaño de muestra.

Ejecutar `verificar_modelo_v5.py` para comprobar independencia de filas y juegos, cobertura, predicciones completas, igualdad entre inferencia y exportación e invariancia del Stuff+ a ubicación y altitud. El resultado queda en `verificacion.json`.

`importancia_variables.csv` exporta PredictionValuesChange por modelo y tarea, sin sobrescribir resultados entre tareas. No son valores SHAP ni efectos causales; `model_alpha` indica la proporción de modelo frente al baseline en la predicción final.

El dashboard usa la misma inferencia. Se requiere instalar `requirements/requirements-dashboard.txt` para abrir Streamlit. La revisión automática de artefactos no sustituye una revisión visual de esa interfaz.
