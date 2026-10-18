"""Reporte honesto de v6 y rankings con regularizacion e intervalos por juego."""
from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd

import entrenar_stuff_plus_v5 as v5
import entrenar_stuff_plus_v6 as v6


def arsenal_ranking(scores, repetitions=400, seed=624, reference_id="v6_reference"):
    eligible_scores = scores.loc[scores.score_reference_id.eq(reference_id)].copy()
    league = eligible_scores.groupby("year")["stuff_plus"].mean().to_dict()
    game = eligible_scores.groupby(["year", "pitcher_anon_id", "AutoPitchType", "game_anon_id"]).agg(
        n=("PitchUID", "size"), stuff_sum=("stuff_plus", "sum"),
        location_sum=("location_plus", "sum"), pitching_sum=("pitching_plus", "sum")).reset_index()
    rng = np.random.default_rng(seed)
    records = []
    for (year, pitcher, pitch_type), group in game.groupby(["year", "pitcher_anon_id", "AutoPitchType"], sort=True):
        n, n_games = int(group.n.sum()), len(group)
        mean = float(group.stuff_sum.sum() / n)
        prior_pitches = 100
        shrunk = league[year] + n / (n + prior_pitches) * (mean - league[year])
        low, high = np.nan, np.nan
        if n_games >= 5:
            counts = rng.multinomial(n_games, np.full(n_games, 1 / n_games), size=repetitions)
            means = (counts @ group.stuff_sum.to_numpy()) / (counts @ group.n.to_numpy())
            low, high = np.quantile(means, [.025, .975])
        records.append({"year": year, "pitcher_anon_id": pitcher, "AutoPitchType": pitch_type,
                        "n_pitches": n, "n_games": n_games, "stuff_plus_raw": mean,
                        "stuff_plus_shrunk": float(shrunk), "raw_mean_ci95_low": float(low),
                        "raw_mean_ci95_high": float(high), "location_plus": float(group.location_sum.sum() / n),
                        "pitching_plus": float(group.pitching_sum.sum() / n),
                        "ranking_eligible": n >= 100 and n_games >= 5, "shrinkage_prior_pitches": prior_pitches})
    result = pd.DataFrame(records)
    if not result.empty:
        optional = [c for c in ["p_whiff", "p_whiff_given_swing", "pred_exit_speed_given_in_play", "pred_exit_speed_contextual"] if c in eligible_scores]
        if optional:
            means = eligible_scores.groupby(["year", "pitcher_anon_id", "AutoPitchType"])[optional].mean().reset_index()
            result = result.merge(means, on=["year", "pitcher_anon_id", "AutoPitchType"], validate="one_to_one")
        result = result.sort_values(["ranking_eligible", "stuff_plus_shrunk"], ascending=[False, False])
    return result


def report(output):
    protocol = json.loads((output / "protocolo_congelado.json").read_text(encoding="utf-8"))
    metrics = json.loads((output / "metricas_benchmark_2026.json").read_text(encoding="utf-8"))
    scores = v5.read_parquet(output / "scores_pitch_v6.parquet")
    ranking = arsenal_ranking(scores)
    # La interfaz puede estar leyendo el ranking mientras se regenera el reporte.
    # Reemplazar el archivo completo evita que observe un CSV vacio o parcial.
    ranking_path = output / "arsenal_con_incertidumbre.csv"
    temporary_ranking = ranking_path.with_suffix(".csv.tmp")
    ranking.to_csv(temporary_ranking, index=False)
    temporary_ranking.replace(ranking_path)
    selected_count = sum(r["chosen"]["weight"] > 0 for r in protocol["tasks"].values())
    lines = ["# Resultado de la mejora v6", "",
             f"Se generaron **{len(scores):,} scores únicos de 2026**. Se seleccionaron mejoras para **{selected_count} de {len(protocol['tasks'])} tareas** usando exclusivamente 2025; las demás conservan v5.", "",
             "2024 sirve para entrenar candidatos; juegos completos de 2024 deciden early stopping. La selección de variantes y mezcla se hace con resultados temporales de 2025. Luego se vuelven a entrenar las alternativas seleccionadas con la misma partición interna 2024–2025 de v5, sin incorporar 2026 al ajuste.", "",
             "**2026 ya fue evaluado durante v5.** Es un benchmark temporal reutilizado, no un test nuevo e intacto. Las elecciones quedaron congeladas antes de calcular los resultados v6 de 2026; no se repitió la selección con esos resultados. Para confirmar generalización hace falta una temporada posterior o datos nuevos.", "",
             "## Qué cambia", "",
             "Las nuevas variables combinan movimiento normalizado por mano, relaciones entre spin/velocidad y extensión/altura, pfxx/pfxz y proyecciones de aceleración tras sustraer gravedad. No se añaden posición en plato, conteo, lado del bateador, ángulos de aproximación ni resultados al modelo físico. Las proyecciones de aceleración son proxies del ajuste de trayectoria: no son mediciones directas de Magnus ni de eficiencia de spin.", "",
             "Cada tarea puede conservar v5, mezclarlo con una alternativa o combinar dos alternativas. La mejora mínima para cambiar es 0.1% de MSE/Brier en desarrollo 2025. Las seis tareas comparadas se fijaron antes de evaluar 2026.", "",
             "## Selección congelada con 2025", "",
             "| Tarea | Miembros seleccionados | Peso nuevo | Reducción relativa MSE/Brier en desarrollo |", "|---|---|---:|---:|"]
    for name, task in protocol["tasks"].items():
        chosen = task["chosen"]
        members = ", ".join(chosen["members"]) or "v5"
        lines.append(f"| {name} | {members} | {chosen['weight']:.2f} | {chosen['relative_gain']:.2%} |")
    lines += ["", "## Comparación pareada en 2026", "",
              "| Tarea | Métrica | v5 | v6 | Reducción MSE/Brier | IC 95% de esa reducción |", "|---|---|---:|---:|---:|---|"]
    for row in metrics:
        metric = "roc_auc" if "roc_auc" in row["v6"] else "rmse"
        label = "AUC" if metric == "roc_auc" else "RMSE"
        ci = row["paired_game_bootstrap"]
        old_label = "v5 físico" if row["task"] == "exit_speed_contextual" else "v5"
        lines.append(f"| {row['task']} | {label} ({old_label}) | {row['v5'][metric]:.5f} | {row['v6'][metric]:.5f} | {ci['relative_mse_reduction']:.2%} | [{ci['ci95_low']:.2%}, {ci['ci95_high']:.2%}] |")
    lines += ["", "### Calibración de probabilidades", "",
              "| Tarea | Brier v5 | Brier v6 | ECE v5 | ECE v6 |", "|---|---:|---:|---:|---:|"]
    for row in metrics:
        if "brier" in row["v6"]:
            lines.append(f"| {row['task']} | {row['v5']['brier']:.6f} | {row['v6']['brier']:.6f} | {row['v5']['ece_10_bins']:.6f} | {row['v6']['ece_10_bins']:.6f} |")
    lines += ["", "La mejora del Brier no implica que cada medida de calibración mejore. La ECE aumenta en este benchmark, especialmente para whiff dado swing: las probabilidades discriminan mejor y tienen menor error global, pero su calibración por bins empeora. No se recalibran usando estos resultados de 2026. Hace falta una muestra adicional, separada de evaluación, para verificar una recalibración futura."]
    lines += ["", "En la columna Reducción MSE/Brier, un valor positivo indica menor error que v5; negativo indica deterioro. AUC mayor es mejor; RMSE menor es mejor. Los intervalos usan 1,000 remuestreos pareados de juegos completos, conservando la dependencia entre pitches del mismo juego. Son condicionales a estos modelos ajustados y no incluyen la incertidumbre de volver a entrenar ni eliminan el sesgo de reutilizar un benchmark. Si el intervalo cruza cero, la mejora no es concluyente bajo este procedimiento.", "",
              "La velocidad de salida contextual añade ubicación, conteo y lado del bateador y se publica como salida separada. Su comparación es contra la velocidad física de v5: mejorar con más información no significa haber mejorado la predicción física. Esa salida contextual no entra a Stuff+.", "",
              "## Scores y rankings", "",
              "Stuff+ conserva la definición de valor esperado físico negativo. Location+ y Pitching+ mantienen sus definiciones de v5; sus referencias se recalculan solamente con validación interna anterior a 2026 y se guardan en el bundle. No se normaliza con test. El run value sigue siendo un proxy de pesos fijos, no RE24 ni un efecto causal.", "",
              "En esta ejecución no se seleccionaron reemplazos para valor físico de carreras ni valor con entorno: los modelos que sustentan los índices permanecen en v5. Las mejoras predictivas de whiff se publican explícitamente como probabilidades; no se presentan como una mejora demostrada del índice Stuff+ compuesto.", "",
              f"El ranking contiene {len(ranking):,} combinaciones pitcher/tipo. Ordena primero las que tienen al menos 100 pitches y cinco juegos, y aplica shrinkage fijo de 100 pitches hacia la media de la temporada. Es una regularización descriptiva predeterminada, no una estimación empírica bayesiana del prior.", "",
              "Los intervalos del ranking corresponden a la media Stuff+ **sin shrinkage** y usan 400 remuestreos de juegos. Describen variación de scores, no incertidumbre sobre el talento real ni sobre los parámetros del modelo. Con menos de cinco juegos no se publica intervalo. No se mezclan referencias v5 y v6 en el ranking. Se publican también las probabilidades medias de whiff y las dos estimaciones de velocidad de salida para consultar las tareas predictivas sin confundirlas con el índice compuesto.", "",
              f"Hay {int((~scores.enhancement_available).sum()):,} pitches sin las mediciones físicas adicionales. Si faltan en una consulta nueva, la inferencia conserva los outputs e índices de v5 para esa fila y declara `score_reference_id=v5_fallback`; la predicción contextual puede seguir disponible.", "",
              "## Artefactos y uso", "",
              "- `bundle.json`, `base_v5/` y `modelos/`: bundle autocontenido con pesos, referencias y modelos de respaldo.",
              "- `protocolo_congelado.json`: selección anterior al benchmark y hashes de código/datos.",
              "- `scores_pitch_v6.parquet`: predicciones nuevas y de comparación, una fila por pitch.",
              "- `metricas_benchmark_2026.json`: métricas y bootstrap por tarea.",
              "- `arsenal_con_incertidumbre.csv`: ranking regularizado con intervalos por juego.",
              "- `importancia_variables.csv`: PredictionValuesChange por modelo, sin atribución causal.", "",
              "Ejecutar `verificar_modelo_v6.py` para auditar artefactos, datos, inferencia y fallback. Consultar `README_MODELO_V6.md` para reproducir las fases separadas.", ""]
    (output / "RESULTADO_MEJORA.md").write_text("\n".join(lines), encoding="utf-8")
    metadata, _, models = v6.load_bundle(output)
    importances = []
    for (task, member), model in models.items():
        selection = metadata["tasks"][task]["chosen"]
        for feature, value in zip(model.feature_names_, model.get_feature_importance()):
            importances.append({"task": task, "member": member, "feature": feature,
                                "prediction_values_change": float(value),
                                "mixture_weight_per_member": selection["weight"] / len(selection["members"])})
    pd.DataFrame(importances).to_csv(output / "importancia_variables.csv", index=False)
    print(output / "RESULTADO_MEJORA.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, default=Path("stuff_plus_output_v6"))
    report(parser.parse_args().salida)
