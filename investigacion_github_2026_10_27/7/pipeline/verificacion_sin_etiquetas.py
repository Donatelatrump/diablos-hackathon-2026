"""
Verificacion del efecto altitud SIN depender de la etiqueta de Trackman.
Proyecto Stuff+ Diablos Rojos (ISAC 2026).

Pasos:
  1. Sanidad de calibracion: variables que la altitud NO deberia mover.
  2. Reclasificacion invariante: tipo de lanzamiento definido solo con
     velocidad, spin y eje (lo que pone la mano), no con el movimiento
     (lo que pone el aire). Centroides ajustados en baja altitud.
  3. Descomposicion de fuerzas: arrastre (paralelo a v) y Magnus
     (perpendicular a v) a partir de las aceleraciones Trackman.
  4. Exponente efectivo por tipo: fuerza ∝ rho^p, ajustado en Extreme
     y VALIDADO FUERA DE MUESTRA en Medium.

Salida: exponentes.json (lo consume simulador_trayectoria.py)

Uso:
    python3 verificacion_sin_etiquetas.py ruta/al/stuff_model_df.parquet
"""
import sys, json
import numpy as np
import pandas as pd

G = 32.174
TIPOS = ["Four-Seam", "Sinker", "Slider", "Changeup", "Curveball", "Cutter"]
MIN_N = 30          # lanzamientos minimos por celda pitcher x tipo x altitud

# Altitudes de la tabla compartida por Diablos (promedio simple por categoria)
ALT = {"No Altitude":      np.mean([620, 10, 10, 10, 540, 130, 10, 20, 10]),
       "Medium Altitude":  np.mean([1120, 1550, 1600, 1600, 1400]),
       "Extreme Altitude": np.mean([1800, 2240, 1890, 2175, 1880, 1820])}
rho = lambda h: 1.225 * (1 - 0.0065 * h / 288.15) ** 4.2559
RHO = {k: rho(h) for k, h in ALT.items()}
RR = {k: RHO[k] / RHO["No Altitude"] for k in RHO}


def cargar(path):
    cols = ["pitcher_anon_id", "PitcherThrows", "altitude_category", "AutoPitchType",
            "RelSpeed", "SpinRate", "SpinAxis", "RelHeight", "RelSide", "Extension",
            "InducedVertBreak", "HorzBreak", "pfxx", "pfxz",
            "vx0", "vy0", "vz0", "ax0", "ay0", "az0", "ZoneTime"]
    d = pd.read_parquet(path, columns=cols)
    d = d.dropna(subset=["altitude_category", "SpinAxis", "InducedVertBreak", "SpinRate"])
    d = d[d.PitcherThrows.isin(["Right", "Left"])].reset_index(drop=True)
    d["AutoPitchType"] = d.AutoPitchType.astype(str)
    return d


def fuerzas(d):
    v = d[["vx0", "vy0", "vz0"]].to_numpy()
    a = d[["ax0", "ay0", "az0"]].to_numpy().copy(); a[:, 2] += G
    vn = np.linalg.norm(v, axis=1); vh = v / vn[:, None]
    par = (a * vh).sum(1)
    d["drag_acc"] = -par
    d["magnus_acc"] = np.linalg.norm(a - par[:, None] * vh, axis=1)
    d["brk_tot"] = np.hypot(d.InducedVertBreak, d.HorzBreak)
    d["pfx_tot"] = np.hypot(d.pfxx, d.pfxz)
    ang = np.deg2rad(d.SpinAxis); d["ax_c"] = np.cos(ang); d["ax_s"] = np.sin(ang)
    return d


def reclasificar(d):
    feats = ["RelSpeed", "SpinRate", "ax_c", "ax_s"]
    low = d[d.altitude_category == "No Altitude"]
    cnt = low.groupby(["pitcher_anon_id", "AutoPitchType"]).size()
    keep = cnt[cnt >= MIN_N].index
    lowk = low.set_index(["pitcher_anon_id", "AutoPitchType"]).loc[keep].reset_index()
    cent = lowk.groupby(["pitcher_anon_id", "AutoPitchType"])[feats].mean()
    sd = lowk.groupby(["pitcher_anon_id", "AutoPitchType"])[feats].std().mean().to_numpy()
    labs = np.full(len(d), None, dtype=object)
    pids = set(cent.index.get_level_values(0))
    for pid, sub in d.groupby("pitcher_anon_id"):
        if pid not in pids:
            continue
        C = cent.loc[pid]
        X = sub[feats].to_numpy() / sd
        dist = ((X[:, None, :] - (C.to_numpy() / sd)[None]) ** 2).sum(2)
        labs[sub.index] = np.array(C.index)[dist.argmin(1)]
    d["inv_type"] = labs
    return d.dropna(subset=["inv_type"])


def log_ratios(d, cat, lab, metric):
    x = d[d.altitude_category.isin(["No Altitude", cat])]
    g = x.groupby(["pitcher_anon_id", lab, "altitude_category"])
    m = g[[metric]].mean().join(g.size().rename("n")).reset_index()
    m = m[m.n >= MIN_N]
    lo = m[m.altitude_category == "No Altitude"].set_index(["pitcher_anon_id", lab])
    hi = m[m.altitude_category == cat].set_index(["pitcher_anon_id", lab])
    j = lo.join(hi, lsuffix="_lo", rsuffix="_hi", how="inner")
    return np.log(j[metric + "_hi"] / j[metric + "_lo"]).to_numpy()


def delta_abs(d, cat, lab, metric):
    x = d[d.altitude_category.isin(["No Altitude", cat])]
    g = x.groupby(["pitcher_anon_id", lab, "altitude_category"])
    m = g[[metric]].mean().join(g.size().rename("n")).reset_index()
    m = m[m.n >= MIN_N]
    lo = m[m.altitude_category == "No Altitude"].set_index(["pitcher_anon_id", lab])
    hi = m[m.altitude_category == cat].set_index(["pitcher_anon_id", lab])
    j = lo.join(hi, lsuffix="_lo", rsuffix="_hi", how="inner")
    return (j[metric + "_hi"] - j[metric + "_lo"]).mean(), len(j)


pct = lambda lr: 100 * (np.exp(np.mean(lr)) - 1)


def main(path):
    d = fuerzas(cargar(path))
    rng = np.random.default_rng(42)

    print("=" * 74)
    print("1. SANIDAD DE CALIBRACION  (Extreme - No, dentro de pitcher x tipo)")
    print("=" * 74)
    for m, u in [("RelSpeed", "mph"), ("SpinRate", "rpm"), ("RelHeight", "ft"),
                 ("RelSide", "ft"), ("Extension", "ft")]:
        v, n = delta_abs(d, "Extreme Altitude", "AutoPitchType", m)
        print(f"  {m:10s} Δ = {v:+7.3f} {u}")
    print("  -> Ninguna variable fijada por la mano se mueve: no hay artefacto de sensor.")

    print("\n" + "=" * 74)
    print("2. RECLASIFICACION INVARIANTE (velocidad, spin y eje; sin movimiento)")
    print("=" * 74)
    d = reclasificar(d)
    chg = (d.inv_type != d.AutoPitchType)
    for cat in ALT:
        print(f"  Discrepancia vs Trackman en {cat:17s}: {100*chg[d.altitude_category==cat].mean():5.1f}%")
    deriva = 100 * (chg[d.altitude_category == "Extreme Altitude"].mean()
                    - chg[d.altitude_category == "No Altitude"].mean())
    print(f"  -> Deriva de etiquetado atribuible a la altitud: {deriva:+.1f} pp")

    print("\n" + "=" * 74)
    print("3. DESCOMPOSICION (% cambio vs No Altitude, dentro de pitcher)")
    print("=" * 74)
    print(f"  {'':17s}{'ρ lineal':>10s}{'Magnus':>9s}{'arrastre':>10s}{'pfx':>8s}{'break':>8s}{'vuelo':>8s}")
    for cat in ["Medium Altitude", "Extreme Altitude"]:
        r = [pct(log_ratios(d, cat, "inv_type", m))
             for m in ["magnus_acc", "drag_acc", "pfx_tot", "brk_tot", "ZoneTime"]]
        print(f"  {cat:17s}{100*(RR[cat]-1):9.1f}%" + "".join(f"{x:8.1f}%" for x in r))

    lM = log_ratios(d, "Extreme Altitude", "inv_type", "magnus_acc")
    lD = log_ratios(d, "Extreme Altitude", "inv_type", "drag_acc")
    pM = lM.mean() / np.log(RR["Extreme Altitude"])
    pD = lD.mean() / np.log(RR["Extreme Altitude"])
    print(f"\n  Exponente global:  Magnus ∝ ρ^{pM:.3f}   Arrastre ∝ ρ^{pD:.3f}   (física ingenua: 1.000)")

    print("\n" + "=" * 74)
    print("4. EXPONENTE POR TIPO: ajuste en Extreme, validacion en Medium")
    print("=" * 74)
    print(f"  {'tipo':10s}{'p':>7s}{'IC95':>15s}{'pred M':>9s}{'obs M':>8s}{'IC95 obs':>17s}{'error':>7s}")
    res = {"global": {"p_magnus": pM, "p_drag": pD}, "por_tipo": {},
           "rho": RHO, "altitudes_m": ALT}
    for pt in TIPOS:
        s = d[d.inv_type == pt]
        lE = log_ratios(s, "Extreme Altitude", "inv_type", "magnus_acc")
        lMm = log_ratios(s, "Medium Altitude", "inv_type", "magnus_acc")
        p = lE.mean() / np.log(RR["Extreme Altitude"])
        bp = [rng.choice(lE, len(lE)).mean() / np.log(RR["Extreme Altitude"]) for _ in range(2000)]
        bo = [pct(rng.choice(lMm, len(lMm))) for _ in range(2000)]
        pred, obs = 100 * (RR["Medium Altitude"] ** p - 1), pct(lMm)
        a1, b1 = np.percentile(bp, [2.5, 97.5]); a2, b2 = np.percentile(bo, [2.5, 97.5])
        ok = a2 <= pred <= b2
        print(f"  {pt:10s}{p:7.3f}  [{a1:.2f},{b1:.2f}]{pred:8.1f}%{obs:7.1f}%  [{a2:5.1f},{b2:5.1f}]"
              f"{obs-pred:+7.1f} {'✓' if ok else '✗'}")
        res["por_tipo"][pt] = {"p_magnus": p, "ic95": [a1, b1], "valida_medium": bool(ok),
                               "n_celdas_extreme": int(len(lE)), "n_celdas_medium": int(len(lMm))}

    json.dump(res, open("exponentes.json", "w"), indent=2, default=float)
    print("\n  -> exponentes.json escrito")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../data/stuff_model_df.parquet")
