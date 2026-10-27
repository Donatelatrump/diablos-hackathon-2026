"""
Simulador de trayectoria de lanzamiento: arrastre + Magnus + gravedad.

Calibrado con los datos Trackman de la LMB (Diablos Rojos, ISAC 2026).
Responde: ¿por que el break cae ~24% en altitud extrema cuando la
densidad del aire solo cae ~16%?

Uso (correr primero verificacion_sin_etiquetas.py, que genera exponentes.json):
    python3 simulador_trayectoria.py ruta/al/stuff_model_df.parquet

Unidades: pies, segundos (sistema de Trackman).
"""

import numpy as np

G = 32.174                 # ft/s^2
Y_RELEASE = 50.0           # Trackman reporta la trayectoria desde y = 50 ft
Y_PLATE = 17.0 / 12.0      # frente del plato
DT = 0.0005                # paso de integracion (s)


# ---------------------------------------------------------------
# Densidad del aire (Atmosfera Estandar Internacional)
# ---------------------------------------------------------------
def rho_isa(h_m: float) -> float:
    return 1.225 * (1 - 0.0065 * h_m / 288.15) ** 4.2559


ALTITUDES = {
    "No Altitude":      np.mean([620, 10, 10, 10, 540, 130, 10, 20, 10]),   # 151 m
    "Medium Altitude":  np.mean([1120, 1550, 1600, 1600, 1400]),           # 1454 m
    "Extreme Altitude": np.mean([1800, 2240, 1890, 2175, 1880, 1820]),     # 1968 m
    "Harp Helu (CDMX)": 2240.0,
}
RHO_REF = rho_isa(ALTITUDES["No Altitude"])

# Exponentes efectivos ajustados con datos (Extreme vs No, dentro de pitcher)
# y validados fuera de muestra en Medium Altitude.
# Los produce verificacion_sin_etiquetas.py.  Fisica ingenua: ambos = 1.0
import json, os
_EXP = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "exponentes.json")))
P_DRAG = _EXP["global"]["p_drag"]
P_MAGNUS_GLOBAL = _EXP["global"]["p_magnus"]
P_MAGNUS_TIPO = {k: v["p_magnus"] for k, v in _EXP["por_tipo"].items()}
VALIDO_TIPO = {k: v["valida_medium"] for k, v in _EXP["por_tipo"].items()}


# ---------------------------------------------------------------
# Calibracion desde las aceleraciones medidas por Trackman
# ---------------------------------------------------------------
def calibrar(v0, a0):
    """Separa la aceleracion medida en arrastre (paralelo a v) y Magnus
    (perpendicular a v). Devuelve los coeficientes k_D, k_L y el eje de spin."""
    a = np.array(a0, float); a[2] += G           # quitar gravedad
    v = np.array(v0, float); vn = np.linalg.norm(v); vh = v / vn
    par = a @ vh
    drag = -par
    M = a - par * vh                             # vector Magnus
    kD = drag / vn**2
    kL = np.linalg.norm(M) / vn**2
    w_hat = np.cross(vh, M / np.linalg.norm(M))  # eje de spin: w x v_hat = M_hat
    return kD, kL, w_hat


def simular(p0, v0, kD, kL, w_hat):
    """Integra con RK4 hasta el frente del plato. Devuelve posicion final y tiempo."""
    def acc(v):
        s = np.linalg.norm(v)
        return -kD * s * v + kL * s * np.cross(w_hat, v) + np.array([0, 0, -G])

    p, v, t = np.array(p0, float), np.array(v0, float), 0.0
    while p[1] > Y_PLATE:
        k1v = acc(v);              k1p = v
        k2v = acc(v + .5*DT*k1v);  k2p = v + .5*DT*k1v
        k3v = acc(v + .5*DT*k2v);  k3p = v + .5*DT*k2v
        k4v = acc(v + DT*k3v);     k4p = v + DT*k3v
        p_new = p + DT/6 * (k1p + 2*k2p + 2*k3p + k4p)
        v_new = v + DT/6 * (k1v + 2*k2v + 2*k3v + k4v)
        if p_new[1] <= Y_PLATE:                  # interpolar el cruce exacto
            f = (p[1] - Y_PLATE) / (p[1] - p_new[1])
            return p + f*(p_new - p), t + f*DT, np.linalg.norm(v + f*(v_new - v))
        p, v, t = p_new, v_new, t + DT


def break_spin(p0, v0, kD, kL, w_hat):
    """Movimiento inducido por spin: trayectoria completa menos la misma sin Magnus.
    Equivale a la definicion de pfx (movimiento vs. lanzamiento sin spin)."""
    pf, t, vplate = simular(p0, v0, kD, kL, w_hat)
    p_ns, _, _ = simular(p0, v0, kD, 0.0, w_hat)
    dx, dz = (pf - p_ns)[[0, 2]] * 12            # pulgadas
    return np.hypot(dx, dz), t, vplate


def escenario(p0, v0, kD, kL, w_hat, rho, modo, p_magnus=None):
    r = rho / RHO_REF
    if modo == "lineal":
        fD, fL = r, r
    elif modo == "empirico":
        fD, fL = r ** P_DRAG, r ** (p_magnus or P_MAGNUS_GLOBAL)
    elif modo == "solo_tiempo":                  # aisla el efecto del tiempo de vuelo
        fD, fL = r, 1.0
    return break_spin(p0, v0, kD * fD, kL * fL, w_hat)


if __name__ == "__main__":
    import sys
    import pandas as pd
    ruta = sys.argv[1] if len(sys.argv) > 1 else "../data/stuff_model_df.parquet"
    # Condiciones iniciales: promedio por tipo, lanzadores derechos, sedes a nivel del mar
    _c = ["PitcherThrows", "altitude_category", "AutoPitchType", "x0", "z0",
          "vx0", "vy0", "vz0", "ax0", "ay0", "az0"]
    _d = pd.read_parquet(ruta, columns=_c)
    _d = _d[(_d.altitude_category == "No Altitude") & (_d.PitcherThrows == "Right")]
    cal = (_d.assign(AutoPitchType=_d.AutoPitchType.astype(str))
             .groupby("AutoPitchType")[_c[3:]].mean()
             .loc[["Four-Seam", "Sinker", "Slider", "Changeup", "Curveball", "Cutter"]])
    OBS = {"Medium Altitude": -19.1, "Extreme Altitude": -25.5}   # break observado, dentro de pitcher

    print("=" * 78)
    print("1. ¿EL TIEMPO DE VUELO EXPLICA LA BRECHA?  (Four-Seam, Extreme vs No)")
    print("=" * 78)
    r = cal.loc["Four-Seam"]
    p0 = [r.x0, Y_RELEASE, r.z0]; v0 = [r.vx0, r.vy0, r.vz0]
    kD, kL, w = calibrar(v0, [r.ax0, r.ay0, r.az0])
    b0, t0, vp0 = break_spin(p0, v0, kD, kL, w)
    rho_e = rho_isa(ALTITUDES["Extreme Altitude"])
    bt, tt, vpt = escenario(p0, v0, kD, kL, w, rho_e, "solo_tiempo")
    print(f"  Nivel del mar:          break {b0:.2f} in | vuelo {t0*1000:.1f} ms | llega a {vp0*0.6818:.1f} mph")
    print(f"  Solo menos arrastre:    break {bt:.2f} in | vuelo {tt*1000:.1f} ms | llega a {vpt*0.6818:.1f} mph")
    print(f"  Cambio:                 break {100*(bt/b0-1):+.2f}%  | vuelo {100*(tt/t0-1):+.2f}%")
    print("  -> El vuelo se acorta, pero la pelota viaja mas rapido y Magnus (∝ v²) empuja mas")
    print("     fuerte durante menos tiempo. Los dos efectos se cancelan: HIPOTESIS DESCARTADA.\n")

    print("=" * 78)
    print("2. ¿CUANTO DEL EFECTO EXPLICA CADA CAPA?  (promedio de tipos validados)")
    print("=" * 78)
    for sede in ["Medium Altitude", "Extreme Altitude"]:
        rh = rho_isa(ALTITUDES[sede]); lin, emp = [], []
        for tipo, r in cal.iterrows():
            if not VALIDO_TIPO.get(tipo, False):
                continue
            p0 = [r.x0, Y_RELEASE, r.z0]; v0 = [r.vx0, r.vy0, r.vz0]
            kD, kL, w = calibrar(v0, [r.ax0, r.ay0, r.az0])
            b0, _, _ = break_spin(p0, v0, kD, kL, w)
            lin.append(100 * (escenario(p0, v0, kD, kL, w, rh, "lineal")[0] / b0 - 1))
            emp.append(100 * (escenario(p0, v0, kD, kL, w, rh, "empirico", P_MAGNUS_TIPO[tipo])[0] / b0 - 1))
        L, E, O = np.mean(lin), np.mean(emp), OBS[sede]
        print(f"  {sede}:  observado {O:.1f}%")
        print(f"     solo densidad del aire ......... {L:6.1f}%   ({100*L/O:4.0f}% del efecto)")
        print(f"     + coeficientes ajustados ....... {E:6.1f}%   ({100*E/O:4.0f}% del efecto)")
        print(f"     residuo sin explicar ........... {O-E:6.1f} pp\n")

    print("=" * 78)
    print("3. HARP HELU (2,240 m): break inducido por spin, diestro promedio")
    print("=" * 78)
    rh = rho_isa(ALTITUDES["Harp Helu (CDMX)"])
    print(f"  {'tipo':10s}{'mar':>7s}{'Harp Helu':>11s}{'Δ in':>7s}{'Δ %':>8s}{'p':>7s}   validado")
    for tipo, r in cal.iterrows():
        p0 = [r.x0, Y_RELEASE, r.z0]; v0 = [r.vx0, r.vy0, r.vz0]
        kD, kL, w = calibrar(v0, [r.ax0, r.ay0, r.az0])
        b0, _, _ = break_spin(p0, v0, kD, kL, w)
        p = P_MAGNUS_TIPO[tipo]
        be, _, _ = escenario(p0, v0, kD, kL, w, rh, "empirico", p)
        print(f"  {tipo:10s}{b0:6.1f}\"{be:9.1f}\"{be-b0:+7.1f}{100*(be/b0-1):+7.1f}%{p:7.2f}   "
              f"{'si' if VALIDO_TIPO[tipo] else 'NO (usar con cautela)'}")
    print("\n  Nota: 2,240 m esta fuera del rango usado para ajustar (promedio Extreme = 1,968 m).")
    print("        Es extrapolacion de ~270 m sobre una ley que se valido entre 151 y 1,968 m.")
