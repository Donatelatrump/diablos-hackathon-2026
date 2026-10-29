"""Reporte de ablation, selección y benchmark reutilizado v8."""
from pathlib import Path
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import entrenar_stuff_plus_v8 as v8
from reportar_mejora_v6 import arsenal_ranking


def report(out=Path("stuff_plus_output_v8")):
    meta=json.loads((out/"bundle.json").read_text(encoding="utf-8"))
    metrics=json.loads((out/"metricas.json").read_text(encoding="utf-8"))
    scores=v8.v5.read_parquet(out/"scores_pitch_v8.parquet")
    reference="v8_calibration_reference" if meta["selection"]["physical_control"]["promoted"] else scores.score_reference_id.mode().iloc[0]
    ranking=arsenal_ranking(scores,reference_id=reference)
    temp=out/"arsenal_con_incertidumbre.csv.tmp"
    ranking.to_csv(temp,index=False)
    temp.replace(out/"arsenal_con_incertidumbre.csv")
    lines=["# Resultados v8","",f"Se generaron {len(scores):,} predicciones. **2026 es un benchmark reutilizado**, no una prueba independiente. Las decisiones se congelaron antes de leerlo en esta ejecución.","",
           "## Comparación controlada","",
           "Cada alternativa global usa los mismos juegos de ajuste y parada, semilla, arquitectura y presupuesto que su control v7. Se añaden ZoneSpeed, SpeedDrop y ZoneTime como bloque; este experimento no identifica el aporte individual de cada variable. Los especialistas usan el subconjunto de esos juegos correspondiente a su familia y se mezclan con el global (25%, 50% o 75%). Los tipos desconocidos usan el global.","",
           "El control de carreras usa las variables base v5, igual que el control directo v7. Los demás usan la física v6. El target sigue siendo un proxy de carreras, no RE24. No se entrenó un nuevo compuesto ni un objetivo esperado de contacto en esta versión.","",
           "## Selección anterior a 2026","",
           "La partición v7 se conserva: ajuste, parada, calibración y selección por juegos. Selección se divide en búsqueda y comprobación con juegos disjuntos. Se elige una sola alternativa en búsqueda y se exige al menos 0.1% de ganancia MSE/Brier en ambas mitades, sin deterioro superior a 0.1% en ninguna temporada de comprobación. Para clasificación se controla también log loss. Si falla, no se prueba la segunda mejor alternativa.","",
           "**Las mitades reutilizan datos de desarrollo de v7**: no son un holdout históricamente intacto. Tampoco representan validación mensual; el archivo solo contiene año. Sigmoide se ajusta exclusivamente en calibración. El control crudo permite comparar el núcleo en igualdad de condiciones; el resultado desplegado se compara abajo con la salida completa de v7, incluida su calibración. Estas comparaciones no son equivalentes.","",
           "| Tarea | Mejor candidato | Ganancia búsqueda | Ganancia comprobación | Activado |","|---|---|---:|---:|---|"]
    for task,item in meta["selection"].items():
        label=item['candidate'].replace('|', ' / ')
        lines.append(f"| {task} | {label} | {item['gains']['tune']:.3%} | {item['gains']['confirmation']:.3%} | {'Sí' if item['promoted'] else 'No'} |")
    lines += ["","## Aporte del bloque de velocidad sin calibración","",
              "Reducción frente al control crudo con igual muestra. La comparación identifica el efecto conjunto de las tres variables, sin atribuir efectos individuales.","",
              "| Tarea | Búsqueda | Comprobación |","|---|---:|---:|"]
    for task,item in meta["selection"].items():
        trials=item["trials"]
        gains=[1-trials["velocity|raw"][part]/trials["control"][part] for part in ["tune_mse","confirmation_mse"]]
        lines.append(f"| {task} | {gains[0]:.3%} | {gains[1]:.3%} |")
    lines += ["","## Comparación desplegada v7 → v8 en 2026","",
              "| Tarea | Métrica | v7 | v8 | Reducción MSE/Brier [IC 95%] |","|---|---|---:|---:|---|"]
    for row in metrics:
        key="brier" if "brier" in row["v8"] else "rmse"
        ci=row["bootstrap"]
        lines.append(f"| {row['task']} | {key} | {row['v7'][key]:.6f} | {row['v8'][key]:.6f} | {ci['relative_mse_reduction']:.3%} [{ci['ci95_low']:.3%}, {ci['ci95_high']:.3%}] |")
    lines += ["","| Tarea de clasificación | AUC v7 | AUC v8 | ECE v7 | ECE v8 |","|---|---:|---:|---:|---:|"]
    for row in metrics:
        if "roc_auc" in row["v8"]:
            lines.append(f"| {row['task']} | {row['v7']['roc_auc']:.5f} | {row['v8']['roc_auc']:.5f} | {row['v7']['ece_10_bins']:.6f} | {row['v8']['ece_10_bins']:.6f} |")
    lines += ["","![Comparación](comparacion_v8.png)","",
              "Los intervalos usan 1,000 remuestreos pareados de juegos; no incorporan incertidumbre de entrenamiento ni eliminan el sesgo de reutilizar 2026. Las métricas completas (incluidos AUC, ECE y R²) están en metricas.json. Una ganancia en Brier no implica mejora en todas las métricas.","",
              "## Inferencia y límites","",
              "Cada tarea rechazada conserva exactamente la salida v7. Si faltan mediciones nuevas finitas o las mediciones físicas necesarias, la fila usa el respaldo v7. Pitching+ se conserva; Stuff+/Location+ solo cambian si se acepta el control directo de carreras, con una referencia fija de calibración. No mezclar referencias diferentes sin identificarlas.","",
              "Los especialistas se probaron para whiff, whiff dado swing y bola en juego. EV, rodados, HR y carreras recibieron la alternativa global de velocidad. La especialización ya compite con un global que conoce AutoPitchType; no se asume que segmentar mejore. El cambio de velocidades puede reflejar también medición o entorno; no se atribuyen efectos causales.","",
              "Para confirmar generalización temporal hacen falta fechas y datos futuros reservados; para RE24 hacen falta estados base-out y secuencia verificable. No se inventan esos datos. Ver docs/archivo/README_MODELO_V8.md y verificacion.json para reproducir y auditar."]
    (out/"RESULTADO_MEJORA.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    means=[r["bootstrap"]["relative_mse_reduction"]*100 for r in metrics]
    lower=[m-r["bootstrap"]["ci95_low"]*100 for m,r in zip(means,metrics)]
    upper=[r["bootstrap"]["ci95_high"]*100-m for m,r in zip(means,metrics)]
    fig,ax=plt.subplots(figsize=(10,5),layout="constrained")
    ax.errorbar(means,range(len(metrics)),xerr=[lower,upper],fmt="o",capsize=4)
    ax.axvline(0,color="gray",linestyle="--")
    ax.set(yticks=range(len(metrics)),yticklabels=[r["task"] for r in metrics],
           xlabel="Reducción MSE/Brier frente a v7 (%) · positivo = mejora",
           title="v8 · benchmark 2026 reutilizado · IC 95% por juego")
    ax.grid(axis="x",alpha=.2)
    fig.savefig(out/"comparacion_v8.png",dpi=170)
    plt.close(fig)
    print(out/"RESULTADO_MEJORA.md")


if __name__=="__main__": report()
