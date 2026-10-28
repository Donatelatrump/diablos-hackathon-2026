"""
Nucleo del simulador en Python: la misma logica que lib/simulator.ts.
Lo usan 06_export.py (casos de prueba) y 10_arsenal.py (evaluador de arsenal y su validacion).

Suavizado: la prediccion se promedia sobre K variaciones del lanzamiento y de la recta del
pitcher, con desviaciones iguales a la mitad de la variacion natural lanzamiento a lanzamiento
(medida dentro de un mismo pitcher y tipo). Un modelo de arboles tiene escalones; promediar
sobre la variacion de ejecucion evita que un cambio de una decima mueva la calificacion.
"""
import numpy as np
import pandas as pd

FIELDS = ["RelSpeed", "ivb", "hb_arm", "SpinRate", "spin_axis_m", "Extension", "RelHeight", "rel_side_arm",
          "fb_relspeed", "fb_ivb", "fb_hb", "fb_axis"]
# mitad de la mediana de la desviacion estandar dentro de pitcher x tipo x temporada x sede
SIGMA = {"RelSpeed": 0.6, "ivb": 1.2, "hb_arm": 1.2, "SpinRate": 50.0, "spin_axis_m": 5.0, "Extension": 0.11,
         "RelHeight": 0.06, "rel_side_arm": 0.09, "fb_relspeed": 0.6, "fb_ivb": 1.2, "fb_hb": 1.2, "fb_axis": 5.0}
K = 128


def make_offsets(seed=7):
    from scipy.stats import qmc, norm
    u = qmc.Sobol(d=len(FIELDS), scramble=True, seed=seed).random(K)
    z = norm.ppf(np.clip(u, 1e-6, 1 - 1e-6))
    z = z - z.mean(axis=0)                       # sin sesgo: cada variacion promedia cero
    return np.round(z, 4)


def factor(meta, tipo, rho_ratio):
    p = meta["physics"]["p_magnus_tipo"].get(tipo, meta["physics"]["p_magnus_global"])
    return rho_ratio ** p


def feature_rows(meta, p, sede, offsets):
    """Filas de features (una por variacion) para un lanzamiento ya expresado a nivel del mar.
    p: dict con tipo, RelSpeed, ivb, hb_arm, SpinRate, spin_axis_m, Extension, RelHeight, rel_side_arm,
       isFastball, fbTipo, fb_relspeed, fb_ivb, fb_hb, fb_axis (fb_* tambien a nivel del mar)."""
    S = meta["sedes"][sede]; sg = SIGMA
    f = factor(meta, p["tipo"], S["rho_ratio"])
    fbT = p["tipo"] if p["isFastball"] else p["fbTipo"]
    ff = factor(meta, fbT, S["rho_ratio"])
    base_fb = ((p["RelSpeed"], p["ivb"], p["hb_arm"], p["spin_axis_m"]) if p["isFastball"]
               else (p["fb_relspeed"], p["fb_ivb"], p["fb_hb"], p["fb_axis"]))
    o = np.asarray(offsets)
    v = p["RelSpeed"] + o[:, 0] * sg["RelSpeed"]
    iv = (p["ivb"] + o[:, 1] * sg["ivb"]) * f
    hh = (p["hb_arm"] + o[:, 2] * sg["hb_arm"]) * f
    ax = p["spin_axis_m"] + o[:, 4] * sg["spin_axis_m"]
    fv = base_fb[0] + o[:, 8] * sg["fb_relspeed"]
    fi = (base_fb[1] + o[:, 9] * sg["fb_ivb"]) * ff
    fh = (base_fb[2] + o[:, 10] * sg["fb_hb"]) * ff
    fa = base_fb[3] + o[:, 11] * sg["fb_axis"]
    return pd.DataFrame({
        "RelSpeed": v, "ivb": iv, "hb_arm": hh,
        "SpinRate": p["SpinRate"] + o[:, 3] * sg["SpinRate"], "spin_axis_m": ax,
        "Extension": p["Extension"] + o[:, 5] * sg["Extension"],
        "RelHeight": p["RelHeight"] + o[:, 6] * sg["RelHeight"],
        "rel_side_arm": p["rel_side_arm"] + o[:, 7] * sg["rel_side_arm"],
        "fb_relspeed": fv, "fb_ivb": fi, "d_velo": v - fv, "d_ivb": iv - fi, "d_hb": hh - fh,
        "d_axis": ((ax - fa + 180) % 360) - 180, "alt": float(S["alt"]),
    })[meta["features"]]


def stuff_plus(meta, rv, alt):
    sc = meta["scale"][str(int(alt))]
    return 100 + 10 * (sc["mean"] - rv) / sc["std"]


def simulate(booster, meta, p, measured_at="No Altitude", sedes=("No Altitude", "Medium Altitude", "Harp Helu"),
             offsets=None):
    """Equivalente a simulate() de lib/simulator.ts. Devuelve {sede: Stuff+}."""
    offsets = np.asarray(meta["smoothing"]["offsets"]) if offsets is None else offsets
    r0 = meta["sedes"][measured_at]["rho_ratio"]
    fbT = p["tipo"] if p["isFastball"] else p["fbTipo"]
    q = dict(p)
    q["ivb"] = p["ivb"] / factor(meta, p["tipo"], r0); q["hb_arm"] = p["hb_arm"] / factor(meta, p["tipo"], r0)
    if not p["isFastball"]:
        q["fb_ivb"] = p["fb_ivb"] / factor(meta, fbT, r0); q["fb_hb"] = p["fb_hb"] / factor(meta, fbT, r0)
    X = pd.concat([feature_rows(meta, q, s, offsets) for s in sedes], ignore_index=True)
    pr = booster.predict(X).reshape(len(sedes), -1).mean(axis=1)
    return {s: float(stuff_plus(meta, pr[i], meta["sedes"][s]["alt"])) for i, s in enumerate(sedes)}
