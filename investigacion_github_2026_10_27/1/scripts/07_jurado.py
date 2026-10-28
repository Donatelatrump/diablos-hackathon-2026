"""Etapa 7: todo lo que el reto pide y la entrega no mostraba.

Organizado exactamente como los entregables y los criterios de evaluación, para que cada
número del reporte y de la app tenga un dueño en la rúbrica.

  E1  Stuff+, Location+ y Pitching+ por pitcher y por arsenal; CDMX contra nivel del mar
  E2  Perfil físico ideal (ya en 05; aquí se ordena para mostrar)
  E3  Qué perfiles ganan y pierden, con riesgo de contacto duro y jonrón
  E4  Mapa de movimiento de los lanzamientos más y menos efectivos
  C1  Calidad: calibración y discriminación fuera de muestra, contra el modelo nulo
  C2  Robustez: holdout de pitcher, temporada y parque
  ★   La pregunta del club: qué lanzadores sufren más la altitud y cuáles son constantes
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"
OUT = ROOT / "app" / "public" / "data"
MIN_P = 300          # lanzamientos mínimos para entrar a una tabla de pitchers
MIN_ENT = 120        # lanzamientos mínimos en CADA entorno para comparar casa contra fuera

NOMBRES = {"Four-Seam": "Recta", "Sinker": "Sinker", "Cutter": "Cutter", "Slider": "Slider",
           "Curveball": "Curva", "Changeup": "Cambio", "Splitter": "Splitter"}


CELDA = 2.0        # pulgadas por lado de cada celda del mapa de movimiento
MIN_CELDA = 10     # lanzamientos mínimos para publicar una celda


def etiqueta(pid: str) -> str:
    """Los IDs vienen anonimizados; se muestran como 'Lanzador 469'."""
    return "Lanzador " + str(int(pid.split("_")[1]))


def main() -> None:
    print("cargando…", flush=True)
    df = pd.read_pickle(ART / "scored.pkl")
    pp = pd.read_parquet(ART / "stuff_por_pitch.parquet")
    df = df.merge(pp, on="PitchUID", how="left")
    df["tipo"] = df.pitch_type.astype(str).map(NOMBRES)
    oof = np.load(ART / "oof_rv.npy")          # filas: stuff, location, pitching (fuera de muestra)
    modelos = json.loads((ART / "models.json").read_text())
    scale = json.loads((ART / "scale.json").read_text())
    out: dict = {}

    # ------------------------------------------------------------------ C1
    # ¿Distingue buenos de malos? Se usa la predicción FUERA DE MUESTRA (ningún pitcher en
    # entrenamiento y prueba a la vez), convertida a escala plus, y se mira qué pasó de
    # verdad con los lanzamientos en cada tramo de Stuff+.
    print("C1 calibración…", flush=True)
    s = scale["stuff"]
    df["stuff_oof"] = 100 + 10 * (-oof[0] - s["center"]) / s["scale"]
    tramos = [-np.inf, 80, 90, 100, 110, 120, np.inf]
    nombres_t = ["< 80", "80-90", "90-100", "100-110", "110-120", "120 +"]
    df["tramo"] = pd.cut(df.stuff_oof, tramos, labels=nombres_t)
    g = df.groupby("tramo", observed=True)
    cal = pd.DataFrame({
        "n": g.size(),
        "carreras_100": g.rv.mean() * 100,                         # carreras por 100 lanzamientos
        "carreras_pred_100": g.apply(lambda x: oof[0][x.index].mean()) * 100,
        "whiff_swing": g.y_whiff.mean(),
        "hard_bip": g.y_hard_contact.mean(),
        "hr_bip": g.apply(lambda x: x.home_run[x.is_ball_in_play == 1].mean()),
    }).reset_index()
    out["calibracion"] = cal.round(4).to_dict("records")
    out["modelo_nulo"] = modelos["baseline_nulo_por_conteo"]
    out["holdout"] = {
        "pitcher": modelos["holdout_pitcher"],
        "temporada": modelos["holdout_temporada"],
        "parque": modelos["holdout_parque"],
        "componentes": modelos["componentes"],
        "ablacion_whiff": modelos.get("ablacion_whiff", {}),
    }

    # ------------------------------------------------------------------ C1 + C2: rasgo estable y futuro
    # Un Stuff+ de física pura casi no predice un lanzamiento suelto: eso lo deciden la ubicación y el
    # azar. Se valida como se valida públicamente un Stuff+: (1) es un rasgo estable del lanzador y
    # (2) predice sus carreras futuras mejor que sus propias carreras pasadas. Todo con la predicción
    # fuera de muestra (el lanzador nunca estuvo en entrenamiento), así que no hay fuga.
    print("C1 estabilidad y futuro…", flush=True)
    capas = {"stuff": oof[0], "location": oof[1], "pitching": oof[2]}
    base = pd.DataFrame({"p": df.pitcher_anon_id.astype(str), "year": df.year, "rv": df.rv,
                         **{k: -v for k, v in capas.items()}})        # signo: más alto = mejor
    base = base[df.pitcher_anon_id.notna().to_numpy() & base.rv.notna().to_numpy()]
    base["mitad"] = base.groupby("p").cumcount() % 2
    h = base.groupby(["p", "mitad"]).agg(n=("rv", "size"), rv=("rv", "mean"), **{k: (k, "mean") for k in capas}).unstack()
    h = h[(h["n"] >= 150).all(axis=1)]
    estab = {k: float(np.corrcoef(h[k][0], h[k][1])[0, 1]) for k in [*capas, "rv"]}
    pas = base[base.year < 2026].groupby("p").agg(n=("rv", "size"), rv=("rv", "mean"), **{k: (k, "mean") for k in capas})
    fut = base[base.year == 2026].groupby("p").agg(n=("rv", "size"), rv=("rv", "mean"))
    pf = pas.join(fut, lsuffix="_pas", rsuffix="_fut", how="inner").query("n_pas >= 300 and n_fut >= 300")
    # correlación con las carreras futuras: el signo se invierte en rv pasado para que "más alto = mejor" en todos
    futuro = {k: float(np.corrcoef(pf[k], -pf.rv_fut)[0, 1]) for k in capas}
    futuro["carreras_pasadas"] = float(np.corrcoef(-pf.rv_pas, -pf.rv_fut)[0, 1])
    out["estabilidad"] = {"mitades": estab, "lanzadores_mitades": int(len(h)),
                          "futuro": futuro, "lanzadores_futuro": int(len(pf))}
    print(f"  estabilidad entre mitades {', '.join(f'{k} {v:.3f}' for k, v in estab.items())} ({len(h)} lanzadores)")
    print(f"  predice carreras 2026 {', '.join(f'{k} {v:+.3f}' for k, v in futuro.items())} ({len(pf)} lanzadores)")

    # ------------------------------------------------------------------ E1 pitchers
    print("E1 pitchers…", flush=True)
    gp = df.groupby("pitcher_anon_id")
    tabla = pd.DataFrame({
        "n": gp.size(),
        "stuff": gp.stuff_plus.mean(),
        "location": gp.location_plus.mean(),
        "pitching": gp.pitching_plus.mean(),
        "stuff_mar": gp.plus_mar.mean(),
        "stuff_hh": gp.plus_alt.mean(),
        "velo": gp.RelSpeed.mean(),
        "whiff": gp.y_whiff.mean(),
        "gb": gp.y_groundball.mean(),
        "mano": gp.PitcherThrows.agg(lambda x: x.mode().iat[0] if x.notna().any() else None),
        "pct_altura": gp.altitude_category.apply(lambda x: (x == "Extreme Altitude").mean()),
    })
    tabla["delta_hh"] = tabla.stuff_hh - tabla.stuff_mar
    # Constancia: qué tanto se mueve su Stuff+ de un juego a otro. Se usa la desviación de
    # su promedio por juego, en juegos con al menos 15 lanzamientos.
    pj = df.groupby(["pitcher_anon_id", "game_anon_id"]).agg(s=("stuff_plus", "mean"), n=("PitchUID", "size"))
    pj = pj[pj.n >= 15]
    cons = pj.groupby(level=0).s.agg(["std", "size"]).rename(columns={"std": "sd_juego", "size": "juegos"})
    tabla = tabla.join(cons)
    tabla = tabla[(tabla.n >= MIN_P) & (tabla.juegos >= 8)].copy()

    # Arsenal de cada uno: tipos con al menos 8% de uso
    uso = df.groupby(["pitcher_anon_id", "tipo"]).size().unstack(fill_value=0)
    uso = uso.div(uso.sum(axis=1), axis=0)
    tabla["arsenal"] = [
        " · ".join(t for t, u in uso.loc[p].sort_values(ascending=False).items() if u >= 0.08)
        for p in tabla.index
    ]
    tabla["nombre"] = [etiqueta(p) for p in tabla.index]

    # ------------------------------------------------------------------ ★ evidencia observada
    # Lo que el modelo predice (delta_hh) se contrasta con lo que de verdad le pasó a cada
    # pitcher que lanzó en los dos entornos: carreras permitidas por 100 lanzamientos.
    print("★ casa contra fuera…", flush=True)
    sub = df[df.altitude_category.isin(["Extreme Altitude", "No Altitude"])]
    obs = sub.groupby(["pitcher_anon_id", "altitude_category"]).agg(
        n=("PitchUID", "size"), rv=("rv", "mean"), whiff=("y_whiff", "mean"),
        hard=("y_hard_contact", "mean"),
    ).unstack()
    ok = (obs[("n", "Extreme Altitude")] >= MIN_ENT) & (obs[("n", "No Altitude")] >= MIN_ENT)
    obs = obs[ok]
    tabla = tabla.join(pd.DataFrame({
        "n_hh": obs[("n", "Extreme Altitude")], "n_mar": obs[("n", "No Altitude")],
        "carreras_hh": obs[("rv", "Extreme Altitude")] * 100,
        "carreras_mar": obs[("rv", "No Altitude")] * 100,
        "whiff_hh": obs[("whiff", "Extreme Altitude")], "whiff_mar": obs[("whiff", "No Altitude")],
    }))
    tabla["carreras_delta"] = tabla.carreras_hh - tabla.carreras_mar
    con_ambos = tabla.dropna(subset=["carreras_delta"])
    r = float(np.corrcoef(con_ambos.delta_hh, -con_ambos.carreras_delta)[0, 1]) if len(con_ambos) > 10 else None
    out["pitchers_n"] = int(len(tabla))
    out["pitchers_con_ambos"] = int(len(con_ambos))
    out["corr_modelo_vs_observado"] = r

    cols = ["nombre", "mano", "n", "stuff", "location", "pitching", "stuff_mar", "stuff_hh",
            "delta_hh", "sd_juego", "juegos", "velo", "whiff", "gb", "pct_altura", "arsenal",
            "n_hh", "n_mar", "carreras_hh", "carreras_mar", "carreras_delta"]
    tabla = tabla[cols].sort_values("stuff_hh", ascending=False)
    out["pitchers"] = json.loads(tabla.round(3).to_json(orient="records"))

    # ------------------------------------------------------------------ E1 arsenales
    print("E1 arsenales…", flush=True)
    ars = tabla.groupby("arsenal").agg(
        pitchers=("nombre", "size"), stuff_hh=("stuff_hh", "mean"), stuff_mar=("stuff_mar", "mean"),
        delta=("delta_hh", "mean"),
    ).query("pitchers >= 6").sort_values("stuff_hh", ascending=False)
    out["arsenales"] = json.loads(ars.round(2).reset_index().to_json(orient="records"))

    # ------------------------------------------------------------------ E1 por tipo
    tipo = df[df.tipo.notna()].groupby("tipo").agg(
        n=("PitchUID", "size"), stuff_mar=("plus_mar", "mean"), stuff_hh=("plus_alt", "mean"),
        ivb=("InducedVertBreak", "mean"), hb=("HorzBreak", "mean"), velo=("RelSpeed", "mean"),
        whiff=("y_whiff", "mean"),
    )
    tipo["delta"] = tipo.stuff_hh - tipo.stuff_mar
    out["tipos"] = json.loads(tipo.round(3).reset_index().sort_values("delta", ascending=False).to_json(orient="records"))

    # ------------------------------------------------------------------ E3 riesgo
    bip = df[df.is_ball_in_play == 1]
    r_ent = bip.groupby("altitude_category", observed=True).agg(
        n=("PitchUID", "size"), hr=("home_run", "mean"), hard=("y_hard_contact", "mean"),
        dist=("Distance", "mean"), gb=("y_groundball", "mean"))
    fb = bip[bip.hit_type.astype(str) == "FlyBall"].groupby("altitude_category", observed=True).agg(
        dist_fb=("Distance", "mean"), hr_fb=("home_run", "mean"))
    out["riesgo"] = json.loads(r_ent.join(fb).round(4).reset_index().to_json(orient="records"))

    # ------------------------------------------------------------------ E4 mapa de movimiento
    # Lanzamientos reales de diestros (el quiebre horizontal de un zurdo es el espejo), con su Stuff+ en el
    # Harp Helú: el 10 % mejor y el 10 % peor de cada tipo. Las reglas del reto permiten presentar resultados
    # pero no datos, así que no se exporta ningún lanzamiento suelto. Se agregan en celdas de 2 pulgadas y
    # sólo salen las celdas con al menos MIN_CELDA lanzamientos, con su promedio de velocidad y de Stuff+.
    print("E4 mapa…", flush=True)
    rhp = df[(df.PitcherThrows == "Right") & df.tipo.notna() & df.plus_alt.notna()
             & df.HorzBreak.notna() & df.InducedVertBreak.notna()]   # NaN no es JSON válido
    puntos = []
    for t, gt in rhp.groupby("tipo"):
        lo, hi = gt.plus_alt.quantile([0.10, 0.90])
        for clase, sel in (("mejor", gt[gt.plus_alt >= hi]), ("peor", gt[gt.plus_alt <= lo])):
            c = sel.assign(bx=(sel.HorzBreak / CELDA).round() * CELDA, by=(sel.InducedVertBreak / CELDA).round() * CELDA)
            agg = c.groupby(["bx", "by"]).agg(n=("plus_alt", "size"), v=("RelSpeed", "mean"), s=("plus_alt", "mean"))
            for (bx, by), rr in agg[agg.n >= MIN_CELDA].iterrows():
                puntos.append({"t": t, "c": clase, "hb": float(bx), "ivb": float(by), "n": int(rr.n),
                               "v": round(float(rr.v), 1), "s": round(float(rr.s), 1)})
    out["mapa"] = puntos

    (OUT / "jurado.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    (ART / "jurado.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, allow_nan=False))
    tabla.to_csv(ART / "pitchers_jurado.csv")

    # --- resumen para leer en consola ---
    print("\n=== C1: ¿distingue buenos de malos? (fuera de muestra) ===")
    print(cal[["tramo", "n", "carreras_100", "carreras_pred_100", "whiff_swing", "hard_bip", "hr_bip"]].round(3).to_string(index=False))
    print(f"\npitchers en tabla: {len(tabla)} | con ≥{MIN_ENT} lanzamientos en ambos entornos: {len(con_ambos)}")
    print(f"correlación delta del modelo vs delta observado de carreras: {r}")
    print("\n=== los que más pierden en el Harp Helú (modelo) ===")
    print(tabla.nsmallest(8, "delta_hh")[["nombre", "arsenal", "stuff_mar", "stuff_hh", "delta_hh", "sd_juego"]].round(2).to_string(index=False))
    print("\n=== los que menos pierden ===")
    print(tabla.nlargest(8, "delta_hh")[["nombre", "arsenal", "stuff_mar", "stuff_hh", "delta_hh", "sd_juego"]].round(2).to_string(index=False))
    print("\n=== más constantes (menor variación entre juegos) ===")
    print(tabla.nsmallest(8, "sd_juego")[["nombre", "arsenal", "stuff_hh", "sd_juego", "juegos"]].round(2).to_string(index=False))
    print("\n=== arsenales con mejor Stuff+ en el Harp Helú ===")
    print(ars.head(10).round(2).to_string())


if __name__ == "__main__":
    main()
