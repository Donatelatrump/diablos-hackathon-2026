"""Etapa 4: exportar modelo y tablas a app/public/data/.

El simulador corre entero en el navegador, asi que aqui se serializa todo lo que necesita:
los arboles del modelo Stuff+, la escala plus, las regresiones auxiliares y las tablas de
arsenal.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.stuffplus import export, models, physics  # noqa: E402
from src.stuffplus.constants import ALT_COORS, ALT_HARP_HELU  # noqa: E402

ART = ROOT / "artifacts"
OUT = ROOT / "app" / "public" / "data"

TIPOS = ["Four-Seam", "Sinker", "Cutter", "Slider", "Curveball", "Changeup", "Splitter"]


def isa(h_m: float) -> float:
    """Densidad relativa del aire, atmosfera estandar internacional."""
    return (1 - 2.25577e-5 * h_m) ** 4.25588


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.read_pickle(ART / "scored.pkl")
    phys = json.loads((ART / "physics.json").read_text())
    scale = json.loads((ART / "scale.json").read_text())

    rho_ext = phys["rho_altitud_extrema"]
    gamma_v = phys["magnus_gamma_vertical"]
    gamma_h = phys["magnus_gamma_horizontal"]

    # --- calibracion altitud -> indice de arrastre -------------------------------
    # El indice que se mide del arrastre (0.853 en altitud extrema) NO es la densidad del
    # aire (0.802 a 2,240 m segun atmosfera estandar): el arrastre es rho*Cd y Cd sube
    # cuando Reynolds baja. Se ajusta un solo exponente que ancla el indice medido a la
    # altitud del Harp Helu, y se verifica contra la cubeta intermedia.
    k = float(np.log(rho_ext) / np.log(isa(ALT_HARP_HELU)))
    check_medium = isa(ALT_COORS) ** k
    rho_medium_medido = phys["rho_por_cubeta"].get("Medium Altitude")

    # --- modelo Stuff+ -----------------------------------------------------------
    booster = lgb.Booster(model_file=str(ART / "model_stuff.txt"))
    model_json = export.export_booster(booster, "regression")
    n_bytes = export.write_json(OUT / "model_stuff.json", model_json)

    export.write_json(OUT / "helpers.json", export.fit_helpers(df))
    shutil.copy(ART / "scale.json", OUT / "scale.json")
    shutil.copy(ART / "models.json", OUT / "models.json")

    # --- arsenal: el mismo pitch en los dos aires --------------------------------
    # Cada lanzamiento del dataset se transfiere a las dos densidades y se puntua con el
    # mismo modelo. Como Stuff+ solo ve forma, la diferencia es atribuible al aire.
    sub = df[df.pitch_type.astype(str).isin(TIPOS)].copy()
    aero = physics.decompose(sub)
    rho_obs = sub.rho_game.to_numpy()
    feats = booster.feature_name()

    tk = dict(rho_observed=rho_obs, aero=aero, magnus_gamma=gamma_v, magnus_gamma_h=gamma_h)
    shape_ref = physics.observed_shape(sub)
    filas = []
    for objetivo, nombre in ((1.0, "mar"), (rho_ext, "alt")):
        shp = physics.transfer_shape(sub, objetivo, **tk)
        X = physics.transfer_features(sub[feats], shape_ref, shp)
        plus = 100.0 + 10.0 * (-booster.predict(X) - scale["stuff"]["center"]) / scale["stuff"]["scale"]
        filas.append(pd.DataFrame({
            "tipo": sub.pitch_type.astype(str).to_numpy(),
            "ivb": shp["ivb"].to_numpy(), "hb": shp["hb"].to_numpy(),
            "plus": plus, "cual": nombre,
        }))

    largo = pd.concat(filas)
    agg = largo.groupby(["tipo", "cual"]).agg(ivb=("ivb", "mean"), hb=("hb", "mean"),
                                              plus=("plus", "mean"), n=("plus", "size"))
    tipos = []
    for t in TIPOS:
        if (t, "mar") not in agg.index:
            continue
        m, a = agg.loc[(t, "mar")], agg.loc[(t, "alt")]
        tipos.append({
            "tipo": t, "n": int(m.n),
            "mar": {"ivb": round(float(m.ivb), 2), "hb": round(float(m.hb), 2), "plus": round(float(m.plus), 1)},
            "alt": {"ivb": round(float(a.ivb), 2), "hb": round(float(a.hb), 2), "plus": round(float(a.plus), 1)},
            "delta_plus": round(float(a.plus - m.plus), 2),
        })
    export.write_json(OUT / "arsenal.json", {"tipos": tipos}, compact=False)

    # El hallazgo con mas consecuencias practicas va tambien al tablero.
    deliv_path = ART / "deliverables.json"
    if deliv_path.exists():
        deliv = json.loads(deliv_path.read_text())
        export.write_json(OUT / "compresion.json", {
            "quintiles": deliv.get("delta_por_quintil", {}),
            "mezcla_top_1pct": deliv.get("mezcla_top_1pct", {}),
            "perfil_ideal": deliv.get("perfil_ideal", {}),
        }, compact=False)

    phys["altitud_a_indice_arrastre"] = {
        "exponente": round(k, 4),
        "nota": "indice = isa(h)^exponente; el arrastre es rho*Cd y Cd sube cuando Reynolds baja",
        "verificacion_cubeta_intermedia": {"predicho": round(check_medium, 4),
                                           "medido": round(rho_medium_medido, 4)},
    }
    export.write_json(OUT / "physics.json", phys, compact=False)

    # --- casos de referencia para la prueba del evaluador del navegador --------
    # El simulador puntua con su propio recorrido de arboles; estos casos verifican que
    # coincide con LightGBM al bit. Viven fuera de public/ para no viajar en el bundle.
    muestra = df.sample(12, random_state=3)
    raw = booster.predict(muestra[feats])
    plus_m = 100.0 + 10.0 * (-raw - scale["stuff"]["center"]) / scale["stuff"]["scale"]
    fixtures = ROOT / "app" / "test" / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    export.write_json(fixtures / "gbm.json", {"casos": [
        {"features": {k: (None if pd.isna(v) else float(v)) for k, v in row.items()},
         "raw": float(r), "plus": float(p)}
        for (_, row), r, p in zip(muestra[feats].iterrows(), raw, plus_m)
    ]}, compact=False)

    print(f"modelo Stuff+: {len(model_json['trees'])} arboles, {n_bytes/1024:.0f} KB")
    print(f"exponente altitud->arrastre: {k:.4f}")
    print(f"  verificacion en la cubeta intermedia: predicho {check_medium:.4f}, medido {rho_medium_medido:.4f}")
    print("\nefecto de la altitud por tipo de lanzamiento:")
    for t in sorted(tipos, key=lambda r: r["delta_plus"], reverse=True):
        print(f"  {t['tipo']:11s} Stuff+ {t['mar']['plus']:6.1f} -> {t['alt']['plus']:6.1f}"
              f"  ({t['delta_plus']:+.2f})   IVB {t['mar']['ivb']:6.2f} -> {t['alt']['ivb']:6.2f}")


if __name__ == "__main__":
    main()
