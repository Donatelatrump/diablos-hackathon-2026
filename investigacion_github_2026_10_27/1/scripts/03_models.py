"""Etapa 3: entrenamiento y validacion fuera de muestra de las tres capas.

Valida en las tres direcciones que pide la rubrica:
  - holdout de pitcher  : generaliza a lanzadores no vistos (GroupKFold)
  - holdout de temporada: entrena 2024-2025, prueba 2026
  - holdout de parque   : entrena sin altitud extrema, prueba en altitud extrema

y contra el modelo nulo explicito de la rubrica: el run value promedio por conteo.

Stuff+ usa todos los juegos por defecto (STUFF_ENTRENA=todo), la configuración
seleccionada. STUFF_ENTRENA=mar conserva la sensibilidad de entrenamiento solo a
nivel del mar. La evaluación rv reconstruye centro, valores por conteo y baseline
con cada entrenamiento. La física y las features de arsenal siguen precalculadas.
Los modelos finales conservan el target global de producción.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.stuffplus import features as F  # noqa: E402
from src.stuffplus import models  # noqa: E402

ART = Path(__file__).resolve().parents[1] / "artifacts"
COMPONENTS = [
    "y_swing", "y_whiff", "y_called_strike", "y_chase",
    "y_groundball", "y_barrel", "y_hard_contact", "y_weak_contact",
]


ENTRENA = os.environ.get("STUFF_ENTRENA", "todo")
if ENTRENA not in {"todo", "mar"}:
    raise ValueError("STUFF_ENTRENA must be todo or mar")


def main() -> None:
    df = pd.read_pickle(ART / "model_frame.pkl")
    sets = F.feature_sets()
    out: dict = {"n_pitches": int(len(df)), "stuff_entrena": ENTRENA,
                 "target_reference": {"validation": "training_split_only",
                                      "final_training": "full_dataset_production_target",
                                      "limits": "Physics and arsenal preprocessing remain global; not fully nested."}}
    mar = (df.altitude_category == "No Altitude").to_numpy()
    # Filas con las que puede entrenar cada capa.
    puede = {name: (mar if (name == "stuff" and ENTRENA == "mar") else np.ones(len(df), dtype=bool)) for name in sets}
    print(f"Stuff+ entrena con {'juegos a nivel del mar' if ENTRENA == 'mar' else 'todos los juegos'} "
          f"({int(puede['stuff'].sum()):,} de {len(df):,} lanzamientos)")

    # --- holdout de pitcher sobre las tres capas ---
    out["holdout_pitcher"] = {}
    oof_store = {}
    for name, feats in sets.items():
        t0 = time.time()
        p_c, n_c = models.capa(name)
        oof, sc = models.cross_val(df, feats, target="rv", n_splits=4, params=p_c, n_rounds=n_c,
                                   train_mask=puede[name], rebuild_rv=True)
        oof_store[name] = oof
        sc["n_features"] = len(feats)
        sc["segundos"] = round(time.time() - t0, 1)
        out["holdout_pitcher"][name] = sc
        if name == "stuff":
            out["baseline_nulo_por_conteo"] = sc["baseline_nulo_por_conteo"]
        print(f"  {name:9s} rmse {sc['rmse']:.5f}  r2 {sc['r2']:.5f}  corr {sc['corr']:.4f}"
              f"  ({len(feats)} features, {sc['segundos']}s)")
    np.save(ART / "oof_rv.npy", np.vstack([oof_store[k] for k in sets]))

    # --- holdout de temporada y de parque, sobre la capa Stuff+ ---
    out["holdout_temporada"] = {}
    tr = df[(df.year < 2026).to_numpy() & puede["stuff"]]
    te = df[df.year == 2026]
    tr, te, baseline = models.fold_run_values(tr, te)
    p_s, n_s = models.capa("stuff")
    fit = models.train(tr, sets["stuff"], params=p_s, n_rounds=n_s)
    out["holdout_temporada"]["stuff"] = models.score(te["rv"].to_numpy(), fit.raw(te))
    out["holdout_temporada"]["baseline"] = models.score(te.rv.to_numpy(), baseline)
    print("  temporada (entrena 24-25, prueba 26): rmse %.5f r2 %.5f"
          % (out["holdout_temporada"]["stuff"]["rmse"], out["holdout_temporada"]["stuff"]["r2"]))

    out["holdout_parque"] = {}
    # Entrena sin altitud extrema (con STUFF_ENTRENA=mar, solo nivel del mar) y prueba en altitud extrema.
    tr = df[(df.altitude_category != "Extreme Altitude").to_numpy() & puede["stuff"]]
    te = df[df.altitude_category == "Extreme Altitude"]
    tr, te, baseline = models.fold_run_values(tr, te)
    fit_park = models.train(tr, sets["stuff"], params=p_s, n_rounds=n_s)
    out["holdout_parque"]["stuff"] = models.score(te["rv"].to_numpy(), fit_park.raw(te))
    out["holdout_parque"]["baseline"] = models.score(te.rv.to_numpy(), baseline)
    out["holdout_parque"]["scope"] = "altitude_bucket_holdout_not_stadium_holdout"
    print("  parque (entrena sin altitud, prueba en altitud): rmse %.5f r2 %.5f"
          % (out["holdout_parque"]["stuff"]["rmse"], out["holdout_parque"]["stuff"]["r2"]))

    # --- modelos de componente, para el tablero y la interpretacion ---
    out["componentes"] = {}
    comp_fits = {}
    for y in COMPONENTS:
        t0 = time.time()
        p_y = models.params_for(y)
        n_y = 400 if y in models.RARE_TARGETS else 300
        oof, _ = models.cross_val(df, sets["pitching"], target=y, n_splits=4,
                                  params=p_y, n_rounds=n_y)
        m = df[y].notna().to_numpy()
        b = models.brier(df[y].to_numpy()[m], oof[m])
        b["segundos"] = round(time.time() - t0, 1)
        out["componentes"][y] = b
        comp_fits[y] = models.train(df, sets["pitching"], target=y, params=p_y, n_rounds=n_y)
        print(f"  {y:18s} brier {b['brier']:.5f}  skill {b['skill']:+.4f}  n={b['n']:,}")

    # --- ablacion de arsenal sobre whiff ---
    # En el run value agregado el arsenal aporta poco, porque la varianza de un solo
    # lanzamiento la dominan la ubicacion y el conteo. Donde si se ve es en el swing fallido,
    # que es el mecanismo que el arsenal explica: diferencial de velocidad y tunel.
    out["ablacion_whiff"] = {}
    for name, feats in sets.items():
        oof, _ = models.cross_val(df, feats, target="y_whiff", n_splits=4,
                                  params={"objective": "binary"}, n_rounds=300)
        m = df["y_whiff"].notna().to_numpy()
        b = models.brier(df["y_whiff"].to_numpy()[m], oof[m])
        b["n_features"] = len(feats)
        out["ablacion_whiff"][name] = b
        print(f"  ablacion whiff {name:9s} brier {b['brier']:.5f}  skill {b['skill']:+.4f}")

    # --- modelos finales sobre todos los datos + escala plus ---
    final = {name: models.reescalar(models.train(df[puede[name]], feats, params=models.capa(name)[0],
                                                 n_rounds=models.capa(name)[1]), df)
             for name, feats in sets.items()}
    for name, fit in final.items():
        df[f"{name}_plus"] = fit.plus(df)
        fit.booster.save_model(str(ART / f"model_{name}.txt"))
    for y, fit in comp_fits.items():
        fit.booster.save_model(str(ART / f"model_{y}.txt"))

    scale = {name: {"center": f.center, "scale": f.scale} for name, f in final.items()}
    (ART / "scale.json").write_text(json.dumps(scale, indent=2))
    df.to_pickle(ART / "scored.pkl")

    out["escala"] = scale
    out["distribucion_stuff_plus"] = {
        q: round(float(df.stuff_plus.quantile(q / 100)), 1) for q in (1, 5, 25, 50, 75, 95, 99)
    }
    (ART / "models.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))

    print("\ndistribucion de Stuff+ (percentiles):")
    print(json.dumps(out["distribucion_stuff_plus"], indent=2))


if __name__ == "__main__":
    main()
