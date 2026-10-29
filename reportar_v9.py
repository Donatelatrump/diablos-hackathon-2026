"""Build aggregate, shareable evidence from completed, frozen v9 experiments."""
from pathlib import Path
import argparse
import json
import shutil
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve

import entrenar_stuff_plus_v9 as v9

ROOT = Path(__file__).resolve().parent


def historical_predictions(test):
    """Invert the persisted v8 scale; verify against the archived RMSE table."""
    old = pd.read_csv(ROOT / "entrega_v8/scores_por_lanzamiento_v8.csv")
    if old.PitchUID.duplicated().any() or set(old.PitchUID) != set(test.PitchUID):
        raise ValueError("La comparación v8 requiere exactamente los mismos PitchUID")
    old = old.set_index("PitchUID").loc[test.PitchUID].reset_index()
    if not old.score_reference_id.eq("v6_reference").all():
        raise ValueError("La reconstrucción requiere la referencia v6 para todas las filas")
    ref = json.loads((ROOT / "stuff_plus_output_v8/parent_v7/parent_v6/bundle.json").read_text())["reference"]
    raw = {key: ref[key]["mean"] + (old[key].to_numpy()-100)*ref[key]["std"]/10 for key in ref}
    predictions = {"stuff_run_value": -raw["stuff_plus"],
                   "xrunvalue": -raw["stuff_plus"]-raw["location_plus"],
                   "environment_run_value": -raw["pitching_plus"]}
    archived = pd.read_csv(ROOT / "entrega_v8/baseline_conteo_modelo_vigente.csv").set_index("task")
    for task, p in predictions.items():
        rmse = np.sqrt(np.mean((test.run_value_proxy.to_numpy()-p)**2))
        if not np.isclose(rmse, archived.loc[task, "rmse"], rtol=1e-8, atol=1e-10):
            raise ValueError(f"La reconstrucción {task} no reproduce el RMSE archivado")
    return predictions


def main(args):
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    bundle = v9.load_bundle(args.run)
    meta = bundle[0]
    protocol = json.loads((args.run/"protocolo.json").read_text())
    if protocol["holdout"] != "season" or protocol["test_year"] != 2026:
        raise ValueError("Este informe comparativo requiere el experimento temporal 2026")
    test = v9.v5.prepare_raw(v9.read_rows(v9.data_path(args.parquet), 2026, False))
    predicted = v9.v5.read_parquet(args.run/"scores_pitch_v9.parquet").set_index("PitchUID").loc[test.PitchUID].reset_index()
    parts = v9.v5.read_parquet(args.run/"particiones.parquet")
    if parts.groupby(["year", "game_anon_id"]).partition.nunique().max() != 1:
        raise ValueError("Un juego ocupa varios roles de desarrollo")
    if parts.year.max() >= protocol["test_year"] or set(parts.PitchUID) & set(test.PitchUID):
        raise ValueError("Desarrollo y evaluación se solapan")
    decisions_checked = []
    for task, item in meta["tasks"].items():
        path = args.run/f"seleccion_{task}.parquet"
        if not path.exists():
            continue
        selection = v9.v5.read_parquet(path)
        options = {key: selection[key].to_numpy() for key in ["baseline", "raw", "shrink", "sigmoid"] if key in selection}
        groups_selection = selection.year.astype(str)+":"+selection.game_anon_id.astype(str)
        spec = v9.TASKS[task]
        reproduced = v9.choose_candidate(selection[spec[0]], options, selection.partition.eq("tune"),
                                         selection.year, groups_selection, spec[3] == "classification")
        if "control_task" in item["selection"]:
            reproduced["control_task"] = item["selection"]["control_task"]
            if not reproduced["promoted"]:
                reproduced["selected"] = "parent"
        if reproduced != item["selection"]:
            raise ValueError(f"No se reproduce la decisión de selección: {task}")
        decisions_checked.append(task)
    old = historical_predictions(test)
    groups = test.year.astype(str)+":"+test.game_anon_id.astype(str)
    comparison = []
    y = test.run_value_proxy.to_numpy()
    for task, previous in old.items():
        current = predicted[f"pred_{task}"].to_numpy()
        comparison.append({"task": task, "n": len(test), "v8_rmse": float(np.sqrt(np.mean((y-previous)**2))),
                           "v9_rmse": float(np.sqrt(np.mean((y-current)**2))),
                           **v9.grouped_gain(y, previous, current, groups, repetitions=1000)})
    pd.DataFrame(comparison).to_csv(out/"comparacion_carreras_v8_v9.csv", index=False)
    v9.v6.json_write(out/"comparacion_carreras_v8_v9.json", comparison)
    for name in ["metricas.json", "ablaciones.json", "protocolo.json", "RESULTADOS.md"]:
        shutil.copy2(args.run/name, out/name)
    audits = []
    for scope in ["pitcher", "environment"]:
        directory = ROOT/f"stuff_plus_output_v9_{scope}"
        if (directory/"metricas.json").exists():
            audit_parts = v9.v5.read_parquet(directory/"particiones.parquet")
            audit_scores = v9.v5.read_parquet(directory/"scores_pitch_v9.parquet")
            if scope == "pitcher":
                if set(audit_parts.pitcher_anon_id) & set(audit_scores.pitcher_anon_id):
                    raise ValueError("Pitchers compartidos entre desarrollo y auditoría")
            elif audit_parts.altitude_category.eq("Extreme Altitude").any() or not audit_scores.altitude_category.eq("Extreme Altitude").all():
                raise ValueError("Entorno excluido no respetado")
            (out/scope).mkdir(exist_ok=True)
            for name in ["metricas.json", "ablaciones.json", "protocolo.json", "RESULTADOS.md"]:
                shutil.copy2(directory/name, out/scope/name)
            for row in json.loads((directory/"metricas.json").read_text()):
                audits.append({"holdout": scope, "task": row["task"], "n": row["n"],
                               "rmse": row["metrics"]["rmse"], "gain_vs_count": row["metrics"]["mse_skill_vs_count"],
                               **row["vs_baseline"]})
    pd.DataFrame(audits).to_csv(out/"auditorias.csv", index=False)
    task_names = [t for t in ["whiff", "ball_in_play", "home_run_per_pitch"] if t in meta["tasks"]]
    if task_names:
        fig, axes = plt.subplots(1, len(task_names), figsize=(4.2*len(task_names), 3.4), squeeze=False)
        for ax, task in zip(axes.ravel(), task_names):
            spec = v9.TASKS[task]
            mask = v9.v5.eligible(test, spec).to_numpy()
            actual, estimated = calibration_curve(test.loc[mask, spec[0]], predicted.loc[mask, f"p_{task}"], n_bins=10, strategy="quantile")
            ax.plot(estimated, actual, "o-", color="#bd1832", label="v9")
            maximum = max(float(np.max(actual)), float(np.max(estimated)), .01)*1.08
            ax.plot([0, maximum], [0, maximum], "--", color="#777777", label="Calibración ideal")
            ax.set(title=task, xlabel="Probabilidad media predicha", ylabel="Frecuencia observada", xlim=(0, maximum), ylim=(0, maximum))
            ax.grid(alpha=.15)
        axes[0,0].legend(fontsize=8)
        fig.suptitle("Calibración · benchmark 2026 reutilizado · bins por cuantiles", fontsize=11)
        fig.tight_layout()
        fig.savefig(out/"calibracion_v9.png", dpi=160)
        plt.close(fig)
    # Audits reproduce the saved predictions, feature boundaries and fixed scale.
    sample = test.iloc[np.linspace(0, len(test)-1, 30, dtype=int)].copy().reset_index(drop=True)
    first = v9.infer(sample, bundle)
    stored = predicted.set_index("PitchUID").loc[sample.PitchUID]
    for col in ["stuff_plus", "location_plus", "pitching_plus"]:
        np.testing.assert_allclose(first[col], stored[col], atol=1e-10)
    changed = sample.copy()
    changed["PlateLocSide"] = 2.
    changed["pitcher_anon_id"] = "unseen"
    changed["altitude_category"] = "Medium Altitude"
    np.testing.assert_array_equal(first.stuff_plus, v9.infer(changed, bundle).stuff_plus)
    single = v9.infer(sample.iloc[:1][v9.RAW_REQUIRED], bundle)
    np.testing.assert_allclose(first.iloc[0][["stuff_plus", "location_plus", "pitching_plus"]].astype(float),
                               single.iloc[0][["stuff_plus", "location_plus", "pitching_plus"]].astype(float), atol=1e-10)
    manifest = {"source_sha256": protocol["source_sha256"], "protocol_sha256": v9.v6.file_hash(args.run/"protocolo.json"),
                "bundle_sha256": v9.v6.file_hash(args.run/"bundle.json"), "n_test": len(test),
                "missing_pitcher_test": int(test.pitcher_anon_id.isna().sum()), "python": sys.version.split()[0],
                "saved_predictions_reproduced": True, "physical_invariance": True, "outcomes_not_required": True,
                "batch_invariance": True, "v8_scale_inverse_verified_against_archived_rmse": True,
                "development_games_disjoint": True, "development_test_disjoint": True,
                "selection_decisions_reproduced": decisions_checked,
                "report_script_sha256": v9.v6.file_hash(__file__),
                "benchmark_reused": True, "holdouts_completed": sorted(set(r["holdout"] for r in audits)),
                "park_holdout": "unavailable_without_stadium_mapping"}
    v9.v6.json_write(out/"VERIFICACION.json", manifest)
    selected = sum(r["selection"]["promoted"] for r in meta["tasks"].values())
    lines = ["# Evidencia del experimento v9", "", f"{len(test):,} pitches de evaluación; {selected}/{len(meta['tasks'])} tareas superaron el criterio de selección antes de evaluar 2026.",
             "2026 es un benchmark reutilizado. Las comparaciones siguientes usan el mismo target de carreras y exactamente los mismos pitches. Cambian definición física, features, muestra de ajuste y selección: es una comparación de pipelines, no una ablación aislada de algoritmo.", "",
             "| Modelo | RMSE v8 | RMSE v9 | Reducción MSE | IC 95% reducción |", "|---|---:|---:|---:|---:|"]
    for row in comparison:
        lines.append(f"| {row['task']} | {row['v8_rmse']:.6f} | {row['v9_rmse']:.6f} | {row['gain']:.2%} | [{row['ci_low']:.2%}, {row['ci_high']:.2%}] |")
    lines += ["", "Las predicciones de carreras v8 se reconstruyen invirtiendo su referencia guardada, y se verifican contra los tres RMSE archivados antes de comparar. Un valor negativo indica deterioro y se conserva en el informe.", "",
              "- [Métricas temporales completas](RESULTADOS.md)", "- [Comparación de carreras en CSV](comparacion_carreras_v8_v9.csv)",
              "- [Auditorías de pitchers y entorno](auditorias.csv)", "- [Ablaciones de ubicación, arsenal y entorno](ablaciones.json)",
              "- [Documento técnico de ocho páginas](DOCUMENTO_TECNICO_V9.pdf)", "- [Verificación de inferencia](VERIFICACION.json)",
              "- [Guía del proyecto y requisitos](../../docs/guias/GUIA_PROYECTO.md)", "", "![Calibración v9](calibracion_v9.png)", "",
              "Las probabilidades v9 incorporan ubicación y contexto. No se presenta su cambio de AUC frente a las probabilidades físicas v8 como una mejora algorítmica aislada. El gráfico de calibración es descriptivo y no incluye intervalos.", "",
              "Las auditorías de pitcher y entorno reentrenan los cuatro modelos de carreras. No certifican los nueve clasificadores contextuales. La auditoría de entorno excluye una categoría de altitud, no un parque identificado."]
    (out/"README.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    # Descriptive cases from the frozen scores, with no recruitment thresholds implied.
    pitchers = pd.read_csv(args.run/"pitchers.csv")
    enough = pitchers.loc[pitchers.n_pitches.ge(100) & pitchers.n_games.ge(5)].sort_values("pitching_plus", ascending=False)
    cases = []
    if not enough.empty:
        cases += [("Revisar perfil de mayor score", enough.iloc[0]), ("Revisar perfil de menor score", enough.iloc[-1])]
    small = pitchers.loc[pitchers.n_games.lt(5) | pitchers.n_pitches.lt(100)].sort_values("n_pitches")
    if not small.empty:
        cases.append(("Información insuficiente", small.iloc[0]))
    recommendations = ["# Recomendaciones de uso · experimento v9", "", "Casos descriptivos seleccionados después de evaluar. No son validación de talento ni decisiones automáticas de contratación.", ""]
    for title, row in cases:
        recommendations += [f"## {title}: {row.pitcher_anon_id}", "",
                            f"{int(row.n_pitches)} pitches / {int(row.n_games)} juegos. Stuff+ {row.stuff_plus:.1f}; Location+ {row.location_plus:.1f}; Pitching+ {row.pitching_plus:.1f}.",
                            "Revisar el repertorio, la distribución por entorno, video, salud, rol y rival. El ranking se refiere a los lanzamientos observados y no tiene un intervalo de talento. La decisión debe poder cambiar si aparece evidencia externa contradictoria.", ""]
    recommendations += ["## Perfil para Diablos", "", "Comparar candidatos dentro de tipo y mano, con muestra suficiente y física medida del mismo lanzamiento. Evaluar el escenario de altitud como una asociación predictiva. No hay identificación validada de Harp Helú ni transporte físico de movimiento, por lo que no se propone una receta universal de velocidad, spin o mezcla de arsenal.", "",
                        "La inclusión de arsenal o entorno debe justificarse con las ganancias y sus intervalos en ablaciones.json. Cuando el intervalo cruza cero, el aporte incremental permanece incierto. No imponer H1–H4 como hechos ni recomendar aumentar el uso de un pitch solo porque el modelo lo puntúa mejor."]
    (out/"RECOMENDACIONES_V9.md").write_text("\n".join(recommendations)+"\n", encoding="utf-8")
    print(f"Informe agregado: {out/'README.md'}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, default=ROOT/"stuff_plus_output_v9")
    p.add_argument("--parquet", type=Path)
    p.add_argument("--output", type=Path, default=ROOT/"reports/v9")
    main(p.parse_args())
