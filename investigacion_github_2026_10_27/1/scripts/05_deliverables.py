"""Etapa 5: entregables 1, 2 y 3.

  1. Stuff+ por lanzamiento, pitcher y arsenal, y el delta CDMX vs nivel del mar.
  2. Perfil fisico ideal para el Harp Helu.
  3. Recomendaciones operativas: que perfiles ganan, cuales pierden, como perfilar.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.stuffplus import physics  # noqa: E402

ART = ROOT / "artifacts"
MIN_PITCHES = 150


def score_at(booster, df, feats, shp, shape_ref, center, scale) -> np.ndarray:
    """Puntua el dataset con la forma transferida a otra densidad."""
    X = physics.transfer_features(df[feats], shape_ref, shp)
    return 100.0 + 10.0 * (-booster.predict(X) - center) / scale


def main() -> None:
    df = pd.read_pickle(ART / "scored.pkl")
    phys = json.loads((ART / "physics.json").read_text())
    scale = json.loads((ART / "scale.json").read_text())["stuff"]
    booster = lgb.Booster(model_file=str(ART / "model_stuff.txt"))
    feats = booster.feature_name()
    rho_ext = phys["rho_altitud_extrema"]
    gv, gh = phys["magnus_gamma_vertical"], phys["magnus_gamma_horizontal"]

    aero = physics.decompose(df)
    rho_obs = df.rho_game.to_numpy()
    kw = dict(rho_observed=rho_obs, aero=aero, magnus_gamma=gv, magnus_gamma_h=gh)

    shape_ref = physics.observed_shape(df)
    shape_mar = physics.transfer_shape(df, 1.0, **kw)
    df["plus_mar"] = score_at(booster, df, feats, shape_mar, shape_ref,
                              scale["center"], scale["scale"])
    df["plus_alt"] = score_at(booster, df, feats, physics.transfer_shape(df, rho_ext, **kw),
                              shape_ref, scale["center"], scale["scale"])
    df["delta_plus"] = df.plus_alt - df.plus_mar

    # --- 1. agregacion por pitcher y por arsenal --------------------------------
    by_pitcher = df.groupby("pitcher_anon_id").agg(
        n=("PitchUID", "size"),
        stuff_mar=("plus_mar", "mean"), stuff_alt=("plus_alt", "mean"),
        delta=("delta_plus", "mean"),
        whiff=("is_whiff", "mean"), gb=("y_groundball", "mean"),
        velo=("RelSpeed", "mean"), ext=("Extension", "mean"),
    ).query(f"n >= {MIN_PITCHES}").sort_values("stuff_alt", ascending=False)
    by_pitcher.round(3).to_csv(ART / "stuff_por_pitcher.csv")

    by_arsenal = df.groupby(["pitcher_anon_id", "pitch_type"], observed=True).agg(
        n=("PitchUID", "size"), stuff_alt=("plus_alt", "mean"), delta=("delta_plus", "mean"),
    ).query("n >= 40")
    by_arsenal.round(3).to_csv(ART / "stuff_por_arsenal.csv")

    # --- 2. perfil fisico ideal para el Harp Helu -------------------------------
    # Busqueda DENTRO de los lanzamientos reales, no sobre una rejilla libre.
    #
    # Una busqueda aleatoria sobre los ejes fisicos produce combinaciones que nunca
    # ocurren (una recta de 100 mph con quiebre de curva), y ahi un modelo de arboles
    # extrapola cualquier cosa. Caracterizar los envios reales mejor puntuados mantiene
    # la respuesta sobre el manifold de lo fisicamente posible para un brazo humano.
    ejes = ["RelSpeed", "InducedVertBreak", "HorzBreak", "SpinRate", "SpinAxis",
            "Extension", "RelHeight", "RelSide", "spin_efficiency", "movement_total"]
    # Se compara con la mano derecha para que el quiebre horizontal no se cancele al promediar.
    rhp = df[df.is_rhp == 1]
    corte = 0.99
    top_alt = rhp[rhp.plus_alt >= rhp.plus_alt.quantile(corte)]
    top_mar = rhp[rhp.plus_mar >= rhp.plus_mar.quantile(corte)]
    perfil = pd.DataFrame({
        "optimo_altitud": top_alt[ejes].mean(),
        "optimo_nivel_mar": top_mar[ejes].mean(),
        "liga_mediana": rhp[ejes].median(),
    })
    perfil["diferencia"] = perfil.optimo_altitud - perfil.optimo_nivel_mar
    perfil = perfil[["optimo_nivel_mar", "optimo_altitud", "diferencia", "liga_mediana"]]
    perfil.round(2).to_csv(ART / "perfil_ideal.csv")

    # Que tipos componen el 1% mejor en cada entorno: el mix es la recomendacion real.
    mezcla = pd.DataFrame({
        "top_nivel_mar": top_mar.pitch_type.value_counts(normalize=True),
        "top_altitud": top_alt.pitch_type.value_counts(normalize=True),
        "liga": rhp.pitch_type.value_counts(normalize=True),
    }).fillna(0).round(4)

    # --- 3. recomendaciones: que gana y que pierde ------------------------------
    tipo = df.groupby("pitch_type", observed=True).agg(
        n=("PitchUID", "size"), stuff_mar=("plus_mar", "mean"), stuff_alt=("plus_alt", "mean"),
        delta=("delta_plus", "mean"),
        d_ivb=("InducedVertBreak", "mean"), whiff=("is_whiff", "mean"),
    ).sort_values("delta", ascending=False)

    # --- el castigo es regresivo: cae sobre los buenos ------------------------
    # Partiendo los lanzamientos en quintiles por su Stuff+ a nivel del mar, el delta de
    # altitud no es parejo. Los peores no pierden nada; los mejores pierden mucho. La
    # altitud no danha al lanzamiento malo, borra la ventaja del bueno.
    quint = {}
    for t in ["Four-Seam", "Slider", "Changeup", "Curveball", "Sinker"]:
        sub_t = df[df.pitch_type.astype(str) == t]
        if len(sub_t) < 5000:
            continue
        q = pd.qcut(sub_t.plus_mar, 5, labels=["q1", "q2", "q3", "q4", "q5"])
        quint[t] = sub_t.groupby(q, observed=True).agg(
            n=("PitchUID", "size"), plus_mar=("plus_mar", "mean"),
            plus_alt=("plus_alt", "mean"), delta=("delta_plus", "mean"),
        ).round(2).to_dict("index")
    q_all = pd.qcut(df.plus_mar, 5, labels=["q1", "q2", "q3", "q4", "q5"])
    quint["TODOS"] = df.groupby(q_all, observed=True).agg(
        n=("PitchUID", "size"), plus_mar=("plus_mar", "mean"),
        plus_alt=("plus_alt", "mean"), delta=("delta_plus", "mean"),
    ).round(2).to_dict("index")

    # H2 se prueba en terminos RELATIVOS: el cambio no gana Stuff+ en altitud, pero la
    # recta contra la que se compara pierde mas. Lo que importa al bateador es la brecha.
    d_fb = float(tipo.loc["Four-Seam", "delta"])
    tipo["delta_vs_recta"] = (tipo["delta"] - d_fb).round(3)

    # Riesgo de contacto duro y jonron en altitud, medido directo
    bip = df[df.is_ball_in_play == 1]
    riesgo = bip.groupby("altitude_category", observed=True).agg(
        n=("PitchUID", "size"), exit_speed=("ExitSpeed", "mean"),
        distancia=("Distance", "mean"), hr_por_bip=("home_run", "mean"),
        gb_rate=("y_groundball", "mean"),
    )
    fb = bip[bip.hit_type.astype(str) == "FlyBall"]
    riesgo_fb = fb.groupby("altitude_category", observed=True).agg(
        n=("PitchUID", "size"), distancia=("Distance", "mean"), hr_por_fb=("home_run", "mean"),
    )

    salida = {
        "pitchers_evaluados": int(len(by_pitcher)),
        "delta_promedio_liga": round(float(df.delta_plus.mean()), 3),
        "por_tipo": tipo.round(3).to_dict("index"),
        "perfil_ideal": perfil.round(2).to_dict("index"),
        "mezcla_top_1pct": mezcla.to_dict("index"),
        "delta_por_quintil": quint,
        "riesgo_contacto": riesgo.round(4).to_dict("index"),
        "riesgo_fly_balls": riesgo_fb.round(4).to_dict("index"),
        "top_10_altitud": by_pitcher.head(10).round(2).reset_index().to_dict("records"),
        "mas_castigados": by_pitcher.nsmallest(10, "delta").round(2).reset_index().to_dict("records"),
        "mas_resistentes": by_pitcher.nlargest(10, "delta").round(2).reset_index().to_dict("records"),
    }
    (ART / "deliverables.json").write_text(json.dumps(salida, indent=2, ensure_ascii=False, default=str))
    df[["PitchUID", "plus_mar", "plus_alt", "delta_plus"]].to_parquet(ART / "stuff_por_pitch.parquet")

    print(f"pitchers evaluados (>={MIN_PITCHES} lanzamientos): {len(by_pitcher)}")
    print(f"delta Stuff+ promedio de la liga en altitud: {df.delta_plus.mean():+.2f}\n")
    print("por tipo de lanzamiento:")
    print(tipo[["n", "stuff_mar", "stuff_alt", "delta", "delta_vs_recta", "whiff"]].round(2).to_string())
    print("\nperfil fisico ideal (promedio del 1% mejor puntuado, lanzadores derechos):")
    print(perfil.round(2).to_string())
    print("\nmezcla de tipos en el 1% mejor:")
    print((mezcla * 100).round(1).to_string())
    print("\ncastigo por quintil de calidad (recta de cuatro costuras):")
    print(pd.DataFrame(quint["Four-Seam"]).T.to_string())
    print("\ncastigo por quintil, todos los lanzamientos:")
    print(pd.DataFrame(quint["TODOS"]).T.to_string())
    print("\nriesgo de contacto por entorno:")
    print(riesgo.round(4).to_string())
    print("\nfly balls:")
    print(riesgo_fb.round(4).to_string())


if __name__ == "__main__":
    main()
