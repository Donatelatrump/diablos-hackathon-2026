"""Genera una comparacion descriptiva sin seleccionar modelos con el test."""
import json
from pathlib import Path

import pandas as pd

from entrenar_stuff_plus_v5 import load_bundle

OUTPUT = Path(__file__).resolve().parent / "stuff_plus_output_v5"


def main():
    rows = json.loads((OUTPUT / "metricas_validacion_v5.json").read_text(encoding="utf-8"))
    old_path = OUTPUT.parent / "stuff_plus_output_v4" / "metricas_validacion_v4.json"
    old = json.loads(old_path.read_text(encoding="utf-8")) if old_path.exists() else []
    old = {(r["split"], r["task"]): r for r in old}
    manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    importances = []
    for folder in sorted(OUTPUT.glob("holdout_*")):
        if not (folder / "bundle.json").exists():
            continue
        metadata, models = load_bundle(folder)
        for task, model in models.items():
            for feature, value in zip(model.feature_names_, model.get_feature_importance()):
                importances.append({"holdout_year": metadata["test_year"], "task": task,
                                    "feature": feature, "prediction_values_change": float(value),
                                    "model_alpha": metadata["tasks"][task]["alpha"]})
    pd.DataFrame(importances).to_csv(OUTPUT / "importancia_variables.csv", index=False)
    text = ["# Resultado de la mejora v5", "",
            f"Se generaron **{manifest['oos_rows']:,} predicciones temporales únicas**. Se entrenaron trece tareas por holdout y se conservaron los modelos exactos utilizados en evaluación.", "",
            "La temporada evaluada no interviene en entrenamiento, selección de iteraciones, mezcla con baseline ni referencia de normalización. Los modelos se seleccionan con juegos completos reservados dentro de temporadas anteriores.", "",
            "## Comparación descriptiva con v4", "",
            "Cambian la partición interna, las variables y el protocolo. Esta tabla no es un experimento controlado que aísle una única modificación. Las métricas v4 son las guardadas anteriormente, con los límites descritos en el análisis integral.", "",
            "| Holdout | Tarea | AUC v4 | AUC v5 | Brier skill v4 | Brier skill v5 |", "|---|---|---:|---:|---:|---:|"]
    for r in rows:
        if "roc_auc" not in r or r["task"] in ["weak_contact", "barrel_or_hard_contact"]:
            continue
        prior = old.get((r["split"], r["task"]), {})
        fmt = lambda v: f"{v:.4f}" if v is not None else "—"
        text.append(f"| {r['split']} | {r['task']} | {fmt(prior.get('roc_auc'))} | {fmt(r['roc_auc'])} | {fmt(prior.get('brier_skill'))} | {fmt(r['brier_skill'])} |")
    text += ["", "Brier skill positivo indica menor error que la probabilidad constante de entrenamiento; negativo indica peor resultado. La ponderación de clase fija de v4 se eliminó. V5 elige la mezcla con el baseline solo con validación interna.", "",
             "## Targets corregidos y valor esperado", "",
             "Contacto débil y fuerte tienen definiciones nuevas basadas exclusivamente en ExitSpeed. xRunValue deja de ser una media global por estado y pasa a predecir un proxy individual con pesos fijos. Por ello no se comparan sus AUC/R² directamente con v4.", "",
             "| Holdout | Tarea | Métrica | Resultado | Comparación con baseline |", "|---|---|---|---:|---:|"]
    for r in rows:
        if r["task"] in ["weak_contact", "barrel_or_hard_contact"]:
            text.append(f"| {r['split']} | {r['task']} | AUC | {r['roc_auc']:.4f} | Brier skill {r['brier_skill']:+.4f} |")
        elif r["task"] in ["exit_speed_given_in_play", "stuff_run_value", "xrunvalue", "environment_run_value"]:
            comparison = f"MSE skill {r['mse_skill']:+.4f}"
            if "mse_skill_vs_count" in r:
                comparison += f"; vs. conteo {r['mse_skill_vs_count']:+.4f}"
            text.append(f"| {r['split']} | {r['task']} | RMSE | {r['rmse']:.5f} | {comparison} |")
    text += ["", "## Contrapartidas y límites predictivos", "",
             "La regresión de velocidad de salida conserva el target, pero v5 elimina la ubicación de sus entradas para mantener una evaluación física separada. El error aumenta respecto al modelo contextual anterior:", "",
             "| Holdout | RMSE velocidad de salida v4 (mph) | RMSE v5 físico (mph) |", "|---|---:|---:|"]
    for r in rows:
        if r["task"] == "exit_speed_given_in_play":
            prior = old.get((r["split"], r["task"]), {})
            old_value = f"{prior['rmse']:.3f}" if "rmse" in prior else "—"
            text.append(f"| {r['split']} | {old_value} | {r['rmse']:.3f} |")
    text += ["", "El valor de carreras físico muestra una señal pequeña; no debe interpretarse su escala normalizada como prueba de gran capacidad predictiva. Un score físico no dispone del conteo, por lo que puede mejorar el baseline constante y aun rendir peor que un baseline que sí conoce conteo. Los pesos de carreras siguen siendo aproximados, sin ocupación de bases. Una mejora de integridad no implica que cada tarea mejore su discriminación.", "",
             "## Uso", "", "Los modelos y sus referencias están en `holdout_2025/` y `holdout_2026/`. La tabla operativa contiene una fila por pitch y los resultados condicionales se infieren para todos los lanzamientos, con independencia de su resultado observado. Los rankings se separan por temporada y declaran tamaño de muestra.", "",
             "Ejecutar `verificar_modelo_v5.py` para comprobar independencia de filas y juegos, cobertura, predicciones completas, igualdad entre inferencia y exportación e invariancia del Stuff+ a ubicación y altitud. El resultado queda en `verificacion.json`.", "",
             "`importancia_variables.csv` exporta PredictionValuesChange por modelo y tarea, sin sobrescribir resultados entre tareas. No son valores SHAP ni efectos causales; `model_alpha` indica la proporción de modelo frente al baseline en la predicción final.", "",
             "El dashboard usa la misma inferencia. Se requiere instalar `requirements-dashboard.txt` para abrir Streamlit. La revisión automática de artefactos no sustituye una revisión visual de esa interfaz.", ""]
    (OUTPUT / "RESULTADO_MEJORA.md").write_text("\n".join(text), encoding="utf-8")
    print(OUTPUT / "RESULTADO_MEJORA.md")


if __name__ == "__main__":
    main()
