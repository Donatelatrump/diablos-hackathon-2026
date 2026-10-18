"""Reporte, curva de calibracion y pesos del compuesto aprendido v7."""
import argparse
import json
from pathlib import Path

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import entrenar_stuff_plus_v5 as v5
import entrenar_stuff_plus_v7 as v7
from reportar_mejora_v6 import arsenal_ranking


def atomic_csv(frame, path):
    temporary = path.with_suffix(".csv.tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def plot_calibration(scores, source, output):
    with duckdb.connect() as con:
        observed = con.execute("SELECT PitchUID,is_whiff,is_swing FROM read_parquet(?) WHERE year=2026", [str(source)]).fetchdf()
    observed = observed.set_index("PitchUID").loc[scores.PitchUID].reset_index()
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
    for j, (task, title) in enumerate([("whiff", "Whiff por lanzamiento"), ("whiff_given_swing", "Whiff dado swing")]):
        mask = observed.is_swing.eq(1).to_numpy() if task.endswith("given_swing") else np.ones(len(observed), dtype=bool)
        y = observed.loc[mask, "is_whiff"].to_numpy(dtype=float)
        raw = scores.loc[mask, f"p_{task}_uncalibrated"].to_numpy()
        calibrated = scores.loc[mask, f"p_{task}"].to_numpy()
        axes[0, j].plot([0, 1], [0, 1], "--", color="gray", label="Ideal")
        for prediction, label, color in [(raw, "Sin calibrar", "#9b4d20"), (calibrated, "Seleccionada", "#245b96")]:
            ids = np.minimum((prediction * 10).astype(int), 9)
            points = [(prediction[ids == b].mean(), y[ids == b].mean()) for b in range(10) if np.sum(ids == b) >= 30]
            if points:
                xx, yy = zip(*points)
                axes[0, j].plot(xx, yy, "o-", color=color, label=label)
            axes[1, j].hist(prediction, bins=np.linspace(0, 1, 31), histtype="step", linewidth=1.8, color=color, label=label)
        axes[0, j].set(title=title, xlabel="Probabilidad pronosticada", ylabel="Frecuencia observada", xlim=(0, 1), ylim=(0, 1))
        axes[1, j].set(xlabel="Probabilidad pronosticada", ylabel="Lanzamientos", xlim=(0, 1))
        for axis in axes[:, j]:
            axis.grid(alpha=.2)
            axis.legend(fontsize=9)
    fig.suptitle("Efecto de calibración sobre el mismo núcleo v7 · benchmark 2026 reutilizado", fontsize=13)
    fig.savefig(output / "calibracion_whiff.png", dpi=180)
    plt.close(fig)


def report(output, source):
    metadata = json.loads((output / "bundle.json").read_text(encoding="utf-8"))
    metrics = json.loads((output / "metricas_benchmark_2026.json").read_text(encoding="utf-8"))
    parts = v5.read_parquet(output / "particiones_pre2026.parquet")
    scores = v5.read_parquet(output / "scores_pitch_v7.parquet")
    chosen = metadata["stack"]["chosen"]
    reference_id = "v7_calibration_reference" if chosen["promoted"] else "v6_reference"
    ranking = arsenal_ranking(scores, reference_id=reference_id)
    atomic_csv(ranking, output / "arsenal_con_incertidumbre.csv")
    model = chosen["model"]
    coefficients = np.asarray(model["coef"])
    scale = np.asarray(model["scale"])
    weights = pd.DataFrame({"component": model["columns"], "coefficient_standardized": coefficients,
                            "coefficient_original_units": coefficients / scale,
                            "mean_oof": model["mean"], "scale_oof": scale})
    atomic_csv(weights, output / "pesos_compuesto.csv")
    plot_calibration(scores, source, output)
    lines = ["# Resultado de los experimentos v7", "",
             f"Se completaron **{len(scores):,} predicciones de 2026**, con calibración separada y un compuesto físico aprendido de predicciones fuera de muestra. V6 se conserva como referencia y respaldo.", "",
             "**2026 ya se evaluó en v5 y v6.** Esta es una comparación reutilizada, no una confirmación independiente con datos nuevos. Los resultados de 2026 no eligen calibradores, pesos ni mezclas de este experimento.", "",
             "## Separación de datos", "",
             "| Función | Filas | Juegos por temporada, disjuntos entre funciones |", "|---|---:|---:|"]
    for name in ["fit", "early_stop", "calibration", "selection"]:
        rows = parts.loc[parts.partition.eq(name)]
        lines.append(f"| {name} | {len(rows):,} | {len(rows[['year','game_anon_id']].drop_duplicates()):,} |")
    lines += ["", "Los componentes se ajustan solo con `fit`; `early_stop` elige el número de árboles; `calibration` ajusta las curvas de probabilidad; `selection` elige calibrador, regularización y mezcla. Todos los juegos son anteriores a 2026. Los perfiles de arsenal usan covariables de temporadas anteriores, sin outcomes; la separación por juegos no pretende simular pitchers completamente desconocidos.", "",
              "Tres bloques de juegos de `fit` generan una predicción OOF por fila. El modelo que la produce excluye su juego. Los calibradores de cada bloque se ajustan con sus predicciones sobre juegos de `calibration`, nunca con los outcomes de las filas OOF. El metamodelo solo aprende con estas predicciones y targets de `fit`.", "",
              "## Calibración seleccionada antes de 2026", "",
              "| Tarea | Método seleccionado | Brier sin calibrar en selección | Brier seleccionado | ECE sin calibrar | ECE seleccionada |", "|---|---|---:|---:|---:|---:|"]
    for task, info in metadata["calibrations"].items():
        raw = info["selection_metrics"]["identity"]["metrics"]
        cal = info["selection_metrics"][info["selected"]]["metrics"]
        lines.append(f"| {task} | {info['selected']} | {raw['brier']:.6f} | {cal['brier']:.6f} | {raw['ece_10_bins']:.6f} | {cal['ece_10_bins']:.6f} |")
    lines += ["", "Para cambiar se exige menor ECE de bins uniformes, control de ECE con bins por cuantiles y no inferioridad de Brier/log loss dentro de tolerancias prefijadas. Si nadie cumple, se mantiene identidad. La calibración isotónica puede introducir empates y cambiar AUC; no se promete que cualquier calibrador mejore todas las métricas.", "",
              "## Efecto de calibrar el mismo núcleo v7 en 2026", "",
              "| Tarea | AUC bruto → calibrado | Brier bruto → calibrado | ECE bruto → calibrado | Reducción Brier e IC 95% por juego |", "|---|---|---|---|---|"]
    for row in metrics:
        if "v7_uncalibrated" not in row:
            continue
        raw, new, ci = row["v7_uncalibrated"], row["v7"], row["calibration_effect"]
        lines.append(f"| {row['task']} | {raw['roc_auc']:.4f} → {new['roc_auc']:.4f} | {raw['brier']:.6f} → {new['brier']:.6f} | {raw['ece_10_bins']:.6f} → {new['ece_10_bins']:.6f} | {ci['relative_mse_reduction']:.2%} [{ci['ci95_low']:.2%}, {ci['ci95_high']:.2%}] |")
    lines += ["", "![Curvas de calibración](calibracion_whiff.png)", "",
              "Las curvas muestran diez bins uniformes con al menos 30 observaciones; las métricas incluyen todas las filas elegibles. Los histogramas permiten ver dónde hay muestra. Estas curvas son de evaluación y no se utilizan para reajustar los modelos.", "",
              "## Comparación total frente a v6", "",
              "| Tarea | Métrica | v6 | v7 | Reducción MSE/Brier e IC 95% por juego |", "|---|---|---:|---:|---|"]
    for row in metrics:
        key = "roc_auc" if "roc_auc" in row["v7"] else "rmse"
        label = "AUC" if key == "roc_auc" else "RMSE"
        ci = row["paired_game_bootstrap_vs_v6"]
        lines.append(f"| {row['task']} | {label} | {row['v6'][key]:.5f} | {row['v7'][key]:.5f} | {ci['relative_mse_reduction']:.2%} [{ci['ci95_low']:.2%}, {ci['ci95_high']:.2%}] |")
    lines += ["", "El núcleo v7 reserva juegos adicionales para calibración y selección: usa aproximadamente 60% de los juegos anteriores para ajustar sus componentes; v6 usó aproximadamente 80% para sus modelos. Cambian datos de ajuste y arquitecturas, además de calibración. Por ello el efecto aislado de calibrar es la tabla anterior, no la diferencia total con v6. El componente de HR v7 es físico y excluye altitud; en v6 el predictor de HR la incluía. Las demás salidas contextuales siguen en v6.", "",
              "## Compuesto aprendido", "",
              f"**Sustitución seleccionada: {'sí' if chosen['promoted'] else 'no; se conservan los índices del padre'}.** Se comparan tres valores de regularización y mezclas prefijadas con un control físico directo. La mejor opción en selección usa alpha={chosen['alpha']:g}, componentes {'calibrados' if chosen['use_calibrated'] else 'sin calibrar'} y peso candidato={chosen['weight']:.2f}; su reducción MSE en selección fue {chosen['relative_gain']:.2%}. El peso de despliegue es {chosen['deployment_weight']:.2f}.", "",
              "El control directo se entrena con los mismos juegos de ajuste y parada que los componentes. Comparar contra él ayuda a separar el efecto del compuesto del cambio de muestra respecto a v6.", ""]
    rv = next(row for row in metrics if row["task"] == "stuff_run_value")
    ci = rv["stack_effect_same_cohort"]
    lines += [f"En 2026, RMSE del control común: **{rv['same_cohort_control']['rmse']:.6f}**; candidato: **{rv['stack_candidate']['rmse']:.6f}**. Reducción MSE frente al control: **{ci['relative_mse_reduction']:.2%}**, IC 95% **[{ci['ci95_low']:.2%}, {ci['ci95_high']:.2%}]**.", "",
              "Los pesos se ajustan mediante ridge con restricciones de signo: whiff/rodado favorables y HR/velocidad de salida desfavorables, manteniendo otras predicciones fijas. Son supuestos de regularización, no efectos causales. Los coeficientes se exportan en `pesos_compuesto.csv`. Los productos P(BIP)·P(GB|BIP) y P(BIP)·EV condicional evitan tratar una probabilidad condicional como si fuera una tasa por pitch.", "",
              "Cuando se selecciona el compuesto, Stuff+ y Location+ usan una referencia guardada de juegos de calibración anteriores a 2026. Pitching+ conserva el modelo contextual con entorno de v6. Si el compuesto no cumple el mínimo en selección, los tres índices permanecen en el padre. Sin mediciones físicas adicionales, todas las predicciones públicas e índices conservan exactamente el respaldo v6/v5.", "",
              "## Límites", "",
              "Los intervalos usan 1,000 remuestreos pareados de juegos y son condicionales a estos modelos; no incluyen incertidumbre de entrenamiento ni corrigen la reutilización de 2026. Si cruzan cero, la mejora no es concluyente bajo este procedimiento. El target de carreras sigue siendo un proxy de pesos fijos, no RE24. El ranking usa regularización descriptiva e intervalos de variación de scores, no de talento real.", "",
              "## Reproducir y auditar", "",
              "`README_MODELO_V7.md` describe las fases. `verificar_modelo_v7.py` comprueba hashes, particiones, exclusión del propio juego, predicciones OOF y calibradas, pesos, selección e inferencia. Los resultados están en `verificacion.json` cuando esa auditoría ha terminado.", ""]
    (output / "RESULTADO_MEJORA.md").write_text("\n".join(lines), encoding="utf-8")
    print(output / "RESULTADO_MEJORA.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, default=Path("stuff_plus_output_v7"))
    parser.add_argument("--parquet", type=Path, default=Path("stuff_model_df.parquet"))
    args = parser.parse_args()
    report(args.salida, args.parquet)
