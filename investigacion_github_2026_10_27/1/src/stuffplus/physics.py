"""Fisica del vuelo de la pelota: densidad del aire y transferencia de forma.

El dataset no trae estadio ni altitud en metros, solo una cubeta de tres niveles
(`altitude_category`). Pero la aceleracion medida en el release contiene la firma
de la densidad del aire, y de ahi se recupera una variable continua.

Descomposicion
--------------
Restando la gravedad, la aceleracion aerodinamica se parte en dos componentes:

    a_aero = a_total - g                       (g = -32.174 ft/s^2 en z)
    a_drag = (a_aero . v_hat) v_hat            (paralela a la velocidad, la frena)
    a_magnus = a_aero - a_drag                 (perpendicular, la curva)

Ambas fuerzas son proporcionales a la densidad del aire:

    F_drag   = 0.5 rho Cd A v^2
    F_magnus = 0.5 rho Cl A v^2

El coeficiente de sustentacion Cl depende del spin factor S = r*omega/v, que no
cambia con la densidad. Por eso escalar `rho` escala ambas componentes por igual,
y el contrafactual "el mismo pitch con otro aire" queda determinado por la fisica
en vez de estimado por regresion.

    k_drag = |a_drag| / v^2   es proporcional a rho -> indice de densidad
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .constants import FPS_TO_MPH, FT_TO_IN, G, Y_PLATE_FRONT

STATE_COLS = ["x0", "y0", "z0", "vx0", "vy0", "vz0", "ax0", "ay0", "az0"]

# El estado de nueve parametros se reporta en el plano y=50, pero la pelota sale de la
# mano en y = 60.5 - Extension. Verificado: retro-integrando de y=50 a ese plano se
# recupera RelHeight con un error medio de 0.0025 ft (0.03 pulgadas).
RUBBER_Y = 60.5
EXTENSION_RANGE = (2.0, 9.0)  # ft; fuera de esto la medicion es basura (hay valores negativos)

# Los ejes reportados (RelSide, HorzBreak, PlateLocSide, HorzApprAngle, pfxx) usan el
# signo opuesto al eje x crudo de la trayectoria. Verificado: corr(x0, RelSide) = -0.9985
# y la retro-integracion coincide con -RelSide con error medio de 0.0027 ft.
X_SIGN = -1.0

# Exponente de respuesta del Magnus a la densidad del aire.
#
# Si arrastre y Magnus fueran ambos proporcionales a rho, el movimiento caeria en la misma
# proporcion que el frenado. No es lo que pasa. Midiendo la respuesta DENTRO de cada pitcher
# (1,187 combinaciones pitcher x tipo, siete cubetas de densidad, respuesta monotona):
#
#     k_drag   ~ rho^0.96        k_magnus ~ rho^1.39        ->  cociente 1.45
#
# Es decir: el Magnus responde 1.45 veces mas fuerte que el arrastre. A la densidad del
# Harp Helu el aire cae 14.7% pero el movimiento cae ~20%. Un modelo que escale todo por
# densidad subestima el castigo de la altitud en cerca de un tercio.
#
# Mecanismo: Reynolds cae con rho, y Cd y Cl no son constantes en ese regimen. Verificado
# que NO es el spin: intra-pitcher, SpinRate cambia +0.5%, el spin factor +0.3% y la
# velocidad de release +0.1% entre nivel del mar y altitud extrema.
# El break vertical y el horizontal no responden igual. Calibrados fuera de muestra
# (mitad de los pitchers para ajustar, la otra mitad para evaluar):
#
#     vertical   gamma_v = 1.6      horizontal  gamma_h = 2.2
#
# Mecanismo probable: buena parte del movimiento horizontal, sobre todo en sinkers y
# changeups, no viene del Magnus puro sino de la estela desviada por las costuras
# (seam-shifted wake), un fenomeno de estela mucho mas sensible al numero de Reynolds
# que la sustentacion por spin. La componente vertical, dominada por Magnus limpio,
# responde mas suave.
MAGNUS_GAMMA = 1.6
MAGNUS_GAMMA_H = 2.2


def decompose(df: pd.DataFrame) -> pd.DataFrame:
    """Separa la aceleracion medida en arrastre y Magnus.

    Devuelve un DataFrame alineado al indice de `df` con:
      v_rel      magnitud de la velocidad en el release (ft/s)
      k_drag     |a_drag| / v^2, proporcional a la densidad del aire
      mx, my, mz componentes de la aceleracion de Magnus (ft/s^2)
      a_magnus   magnitud de Magnus (ft/s^2)
    """
    vx, vy, vz = df["vx0"].to_numpy(), df["vy0"].to_numpy(), df["vz0"].to_numpy()
    # Aceleracion aerodinamica = medida - gravedad
    ax = df["ax0"].to_numpy()
    ay = df["ay0"].to_numpy()
    az = df["az0"].to_numpy() + G

    v = np.sqrt(vx * vx + vy * vy + vz * vz)
    inv_v = 1.0 / v

    # Componente paralela a la velocidad (negativa: frena)
    c = (ax * vx + ay * vy + az * vz) * inv_v
    dx, dy, dz = c * vx * inv_v, c * vy * inv_v, c * vz * inv_v

    return pd.DataFrame(
        {
            "v_rel": v,
            "k_drag": -c / (v * v),
            "mx": ax - dx,
            "my": ay - dy,
            "mz": az - dz,
            "a_magnus": np.sqrt((ax - dx) ** 2 + (ay - dy) ** 2 + (az - dz) ** 2),
        },
        index=df.index,
    )


def air_density_index(
    df: pd.DataFrame, aero: pd.DataFrame | None = None, reference: str = "No Altitude"
) -> pd.DataFrame:
    """Indice de densidad del aire, por pitch y por juego.

    `k_drag` individual es ruidoso (depende de las costuras y el estado de la pelota),
    pero su mediana por juego es un estimador estable de la densidad de ese partido.
    Normalizamos contra la mediana de los estadios a nivel del mar para que el indice
    se lea directamente como "fraccion del aire que hay al nivel del mar".
    """
    aero = decompose(df) if aero is None else aero
    k = aero["k_drag"]

    ref_mask = df["altitude_category"] == reference
    k_ref = float(k[ref_mask].median())

    game_k = k.groupby(df["game_anon_id"]).median()
    game_rho = (game_k / k_ref).rename("rho_game")

    out = pd.DataFrame(index=df.index)
    out["k_drag"] = k
    out["rho_pitch"] = k / k_ref
    out["rho_game"] = df["game_anon_id"].map(game_rho).astype(float)
    return out


def release_state(df: pd.DataFrame, aero: pd.DataFrame | None = None) -> dict[str, np.ndarray]:
    """Retrocede el estado de nueve parametros desde y=50 hasta el punto real de release.

    Importa porque el break se mide desde la mano, no desde y=50: anclar la referencia
    en el plano equivocado subestima el movimiento en ~9% (la fraccion de vuelo que se
    pierde), que en una recta de 17 pulgadas son 1.5 pulgadas de error.

    El tramo son ~4.6 ft, asi que un paso cuadratico con la aceleracion medida basta;
    reproduce RelHeight y RelSide con error medio de 0.003 ft.
    """
    aero = decompose(df) if aero is None else aero
    ext = df["Extension"].to_numpy(dtype=float)
    ext = np.clip(ext, *EXTENSION_RANGE)
    ext = np.where(np.isfinite(ext), ext, np.nanmedian(ext))

    x0, z0 = df["x0"].to_numpy(float), df["z0"].to_numpy(float)
    vx0, vy0, vz0 = df["vx0"].to_numpy(float), df["vy0"].to_numpy(float), df["vz0"].to_numpy(float)
    ax0, ay0, az0 = df["ax0"].to_numpy(float), df["ay0"].to_numpy(float), df["az0"].to_numpy(float)

    y_rel = RUBBER_Y - ext
    dt = (y_rel - df["y0"].to_numpy(float)) / vy0  # negativo: antes de y=50

    st = {
        "x0": x0 + vx0 * dt + 0.5 * ax0 * dt * dt,
        "y0": y_rel,
        "z0": z0 + vz0 * dt + 0.5 * az0 * dt * dt,
        "vx0": vx0 + ax0 * dt,
        "vy0": vy0 + ay0 * dt,
        "vz0": vz0 + az0 * dt,
    }
    # Magnus se midio a la velocidad de y=50; se reescala a la velocidad de release
    # porque la fuerza va como v^2 y el integrador la normaliza con su estado inicial.
    v50 = aero["v_rel"].to_numpy()
    v_rel = np.sqrt(st["vx0"] ** 2 + st["vy0"] ** 2 + st["vz0"] ** 2)
    scale = (v_rel / v50) ** 2
    st["mx"] = aero["mx"].to_numpy() * scale
    st["my"] = aero["my"].to_numpy() * scale
    st["mz"] = aero["mz"].to_numpy() * scale
    st["v_rel"] = v_rel
    st["k_drag"] = aero["k_drag"].to_numpy()
    return st


def spin_axis_from_magnus(vx, vy, vz, mx, my, mz):
    """Direccion del eje de giro a partir de la velocidad y la aceleracion de Magnus.

    La fuerza de Magnus va como omega x v, asi que si m_hat = w_hat x v_hat entonces
    w_hat = v_hat x m_hat. Solo se recupera la componente de omega perpendicular a la
    velocidad, que es justamente la unica que produce movimiento (el gyro-spin no curva).
    """
    v = np.sqrt(vx * vx + vy * vy + vz * vz)
    m = np.sqrt(mx * mx + my * my + mz * mz)
    m = np.where(m > 1e-9, m, np.nan)
    vxh, vyh, vzh = vx / v, vy / v, vz / v
    mxh, myh, mzh = mx / m, my / m, mz / m
    return (
        vyh * mzh - vzh * myh,
        vzh * mxh - vxh * mzh,
        vxh * myh - vyh * mxh,
    )


def _accel(vx, vy, vz, k_drag, spin, m_mag, inv_v0sq):
    """Aceleracion instantanea: arrastre + Magnus + gravedad.

    El Magnus se mantiene perpendicular a la velocidad en todo el vuelo. El eje de giro se
    conserva (no hay torque que lo cambie), pero la velocidad se inclina hacia abajo, asi
    que la direccion de la fuerza rota con ella. Mantenerla fija es un error de segundo
    orden que se paga sobre todo en el break horizontal.
    """
    v = np.sqrt(vx * vx + vy * vy + vz * vz)
    kv = k_drag * v
    wx, wy, wz = spin
    # omega_hat x v_hat, renormalizado (omega_hat no queda perpendicular a v al rotar esta)
    cx = wy * vz - wz * vy
    cy = wz * vx - wx * vz
    cz = wx * vy - wy * vx
    cn = np.sqrt(cx * cx + cy * cy + cz * cz)
    cn = np.where(cn > 1e-9, cn, np.nan)
    s = m_mag * (v * v) * inv_v0sq / cn
    return (
        -kv * vx + cx * s,
        -kv * vy + cy * s,
        -kv * vz + cz * s - G,
    )


def integrate(
    state: dict[str, np.ndarray],
    k_drag: np.ndarray,
    magnus: tuple[np.ndarray, np.ndarray, np.ndarray],
    y_end: float = Y_PLATE_FRONT,
    dt: float = 0.005,
    max_steps: int = 160,
) -> dict[str, np.ndarray]:
    """Integra el vuelo con RK4 hasta que la pelota cruza `y_end`.

    El arrastre se recalcula a cada paso con la velocidad instantanea (a diferencia del
    modelo de aceleracion constante de nueve parametros, que la promedia sobre el vuelo).
    Magnus conserva su direccion y escala con v^2.

    Devuelve el estado interpolado en el cruce: posicion, velocidad y tiempo.
    """
    x, y, z = (np.asarray(state[c], dtype=float).copy() for c in ("x0", "y0", "z0"))
    vx, vy, vz = (np.asarray(state[c], dtype=float).copy() for c in ("vx0", "vy0", "vz0"))
    mx, my, mz = magnus
    k_drag = np.asarray(k_drag, dtype=float)
    inv_v0sq = 1.0 / (vx * vx + vy * vy + vz * vz)
    # El eje de giro se conserva; la magnitud del Magnus escala con v^2.
    spin = spin_axis_from_magnus(vx, vy, vz, mx, my, mz)
    m_mag = np.sqrt(mx * mx + my * my + mz * mz)

    n = x.shape[0]
    out = {c: np.full(n, np.nan) for c in ("x", "y", "z", "vx", "vy", "vz", "t")}
    done = ~np.isfinite(x + y + z + vx + vy + vz + k_drag + mx + my + mz)
    t = np.zeros(n)

    for _ in range(max_steps):
        if done.all():
            break
        # --- RK4 sobre (posicion, velocidad) ---
        a1 = _accel(vx, vy, vz, k_drag, spin, m_mag, inv_v0sq)
        k1 = (vx, vy, vz, *a1)

        vx2, vy2, vz2 = vx + 0.5 * dt * a1[0], vy + 0.5 * dt * a1[1], vz + 0.5 * dt * a1[2]
        a2 = _accel(vx2, vy2, vz2, k_drag, spin, m_mag, inv_v0sq)
        k2 = (vx2, vy2, vz2, *a2)

        vx3, vy3, vz3 = vx + 0.5 * dt * a2[0], vy + 0.5 * dt * a2[1], vz + 0.5 * dt * a2[2]
        a3 = _accel(vx3, vy3, vz3, k_drag, spin, m_mag, inv_v0sq)
        k3 = (vx3, vy3, vz3, *a3)

        vx4, vy4, vz4 = vx + dt * a3[0], vy + dt * a3[1], vz + dt * a3[2]
        a4 = _accel(vx4, vy4, vz4, k_drag, spin, m_mag, inv_v0sq)
        k4 = (vx4, vy4, vz4, *a4)

        w = dt / 6.0
        nx = x + w * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
        ny = y + w * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
        nz = z + w * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2])
        nvx = vx + w * (k1[3] + 2 * k2[3] + 2 * k3[3] + k4[3])
        nvy = vy + w * (k1[4] + 2 * k2[4] + 2 * k3[4] + k4[4])
        nvz = vz + w * (k1[5] + 2 * k2[5] + 2 * k3[5] + k4[5])

        # --- cruce de y_end: interpolacion lineal dentro del paso ---
        crossed = (~done) & (ny <= y_end) & (y > y_end)
        if crossed.any():
            f = (y[crossed] - y_end) / (y[crossed] - ny[crossed])
            idx = np.flatnonzero(crossed)
            out["x"][idx] = x[crossed] + f * (nx[crossed] - x[crossed])
            out["y"][idx] = y_end
            out["z"][idx] = z[crossed] + f * (nz[crossed] - z[crossed])
            out["vx"][idx] = vx[crossed] + f * (nvx[crossed] - vx[crossed])
            out["vy"][idx] = vy[crossed] + f * (nvy[crossed] - vy[crossed])
            out["vz"][idx] = vz[crossed] + f * (nvz[crossed] - vz[crossed])
            out["t"][idx] = t[crossed] + f * dt
            done |= crossed

        x, y, z, vx, vy, vz = nx, ny, nz, nvx, nvy, nvz
        t = t + dt

    return out


def shape_at_density(
    df: pd.DataFrame,
    rho_ratio: np.ndarray | float = 1.0,
    aero: pd.DataFrame | None = None,
    y_end: float = Y_PLATE_FRONT,
    magnus_gamma: float = MAGNUS_GAMMA,
    magnus_gamma_h: float = MAGNUS_GAMMA_H,
) -> pd.DataFrame:
    """La forma que tendria cada pitch si el aire tuviera densidad `rho_ratio` veces la medida.

    `rho_ratio=1.0` reproduce el pitch tal como se lanzo (asi se valida el integrador).
    Para llevar un pitch de su entorno real a otro: rho_ratio = rho_objetivo / rho_observada.

    Devuelve las mismas magnitudes que reporta Trackman, en sus unidades y con su signo:
      ivb, hb (pulgadas), zone_speed (mph), vaa, haa (grados),
      plate_x, plate_z (pies), zone_time (s), speed_drop (mph), rel_speed (mph)
    """
    aero = decompose(df) if aero is None else aero
    r = np.asarray(rho_ratio, dtype=float)
    st = release_state(df, aero)

    rv, rh = r ** magnus_gamma, r ** magnus_gamma_h
    magnus = (st["mx"] * rh, st["my"] * rh, st["mz"] * rv)
    res = integrate(st, st["k_drag"] * r, magnus, y_end=y_end)

    t = res["t"]
    # Break = desviacion respecto a la trayectoria sin spin y sin arrastre, anclada en la
    # mano, con la gravedad ya descontada en el eje vertical (convencion Trackman).
    z_ref = st["z0"] + st["vz0"] * t - 0.5 * G * t * t
    x_ref = st["x0"] + st["vx0"] * t

    v_plate = np.sqrt(res["vx"] ** 2 + res["vy"] ** 2 + res["vz"] ** 2)
    v_horz = np.hypot(res["vx"], res["vy"])

    return pd.DataFrame(
        {
            "ivb": (res["z"] - z_ref) * FT_TO_IN,
            "hb": X_SIGN * (res["x"] - x_ref) * FT_TO_IN,
            "zone_speed": v_plate * FPS_TO_MPH,
            "rel_speed": st["v_rel"] * FPS_TO_MPH,
            "vaa": np.degrees(np.arctan2(res["vz"], v_horz)),
            "haa": X_SIGN * np.degrees(np.arctan2(res["vx"], -res["vy"])),
            "plate_x": X_SIGN * res["x"],
            "plate_z": res["z"],
            "zone_time": t,
            "speed_drop": (st["v_rel"] - v_plate) * FPS_TO_MPH,
        },
        index=df.index,
    )


# Columnas de Trackman que corresponden a cada magnitud del integrador.
SHAPE_ANCHORS = {
    "ivb": "InducedVertBreak",
    "hb": "HorzBreak",
    "zone_speed": "ZoneSpeed",
    "rel_speed": "RelSpeed",
    "vaa": "VertApprAngle",
    "haa": "HorzApprAngle",
    "plate_x": "PlateLocSide",
    "plate_z": "PlateLocHeight",
    "zone_time": "ZoneTime",
    "speed_drop": "SpeedDrop",
}


def transfer_shape(
    df: pd.DataFrame,
    rho_target: np.ndarray | float,
    rho_observed: np.ndarray | None = None,
    aero: pd.DataFrame | None = None,
    magnus_gamma: float = MAGNUS_GAMMA,
    magnus_gamma_h: float = MAGNUS_GAMMA_H,
) -> pd.DataFrame:
    """Lleva cada pitch a un aire de densidad `rho_target` (1.0 = nivel del mar).

    Metodo de diferencias: el integrador no se usa para predecir la forma, sino solo el
    *cambio* de forma entre dos densidades, y ese cambio se suma a la medicion real de
    Trackman. Asi los niveles coinciden con Trackman por construccion y el unico error que
    queda es el diferencial.

    Ese error diferencial esta medido: el sesgo del integrador contra Trackman es
    +0.85 in de IVB a nivel del mar y +0.90 in en altitud extrema. La diferencia entre
    ambos, 0.05 in, es el error real del contrafactual, contra deltas de 2 a 3.6 pulgadas
    que queremos medir. Un 2%.
    """
    aero = decompose(df) if aero is None else aero
    if rho_observed is None:
        rho_observed = air_density_index(df, aero)["rho_game"].to_numpy()
    rho_observed = np.asarray(rho_observed, dtype=float)
    ratio = np.asarray(rho_target, dtype=float) / rho_observed

    kw = dict(aero=aero, magnus_gamma=magnus_gamma, magnus_gamma_h=magnus_gamma_h)
    here = shape_at_density(df, 1.0, **kw)
    there = shape_at_density(df, ratio, **kw)

    out = pd.DataFrame(index=df.index)
    for col, anchor in SHAPE_ANCHORS.items():
        out[col] = df[anchor].to_numpy(dtype=float) + (there[col] - here[col])
    return out


# Que le pasa a cada feature del modelo cuando cambia la densidad del aire.
#
# Es la regla mas delicada del sistema. Si se transfieren unas features y otras no, se le
# entrega al modelo una combinacion que no existe —mucha eficiencia de giro con poco
# movimiento, por ejemplo— y ahi un ensamble de arboles extrapola sin control. El
# contrafactual tiene que mover TODO lo que la fisica mueve, y solo eso.
TRANSFERRED = {
    "InducedVertBreak": "ivb",
    "HorzBreak": "hb",
    "ZoneSpeed": "zone_speed",
    "VertApprAngle": "vaa",
    "HorzApprAngle": "haa",
    "SpeedDrop": "speed_drop",
    "ZoneTime": "zone_time",
}

# Invariantes del release: el aire no los toca.
#   RelSpeed, EffectiveVelo, Extension, RelHeight, RelSide, VertRelAngle, HorzRelAngle
#   SpinRate    verificado en los datos: cambia +0.5% entre entornos
#   SpinAxis    el eje de giro es una propiedad del release, no del quiebre resultante.
#               No se recalcula de atan2(hb, ivb): eso lo haria girar solo porque las
#               componentes vertical y horizontal se escalan con exponentes distintos.


def observed_shape(df: pd.DataFrame) -> pd.DataFrame:
    """Forma medida que corresponde a las variables originales, antes de transferir.

    Una referencia a nivel del mar sólo corresponde a un frame que ya fue normalizado
    entero a nivel del mar. Usar esta función cuando X conserva mediciones observadas.
    """
    return pd.DataFrame({key: df[col].to_numpy(dtype=float)
                         for key, col in SHAPE_ANCHORS.items()}, index=df.index)


def transfer_features(
    X: pd.DataFrame, shape_ref: pd.DataFrame, shape_new: pd.DataFrame
) -> pd.DataFrame:
    """Aplica el cambio de forma desde el entorno que realmente representa X.

    shape_ref debe corresponder a X, no ser una referencia arbitraria de nivel del mar.
    La comprobación evita mezclar IVB/HB transferidos con VertBreak y eficiencia observados.
    """
    if len(X) != len(shape_ref) or len(X) != len(shape_new):
        raise ValueError("X y las dos formas deben contener las mismas filas en el mismo orden")
    for col, key in (("InducedVertBreak", "ivb"), ("HorzBreak", "hb")):
        if col in X and not np.allclose(X[col].to_numpy(dtype=float),
                                       shape_ref[key].to_numpy(dtype=float),
                                       atol=1e-6, rtol=0, equal_nan=True):
            raise ValueError(f"La forma de referencia no corresponde a X[{col}]")
    out = X.copy()
    for col, key in TRANSFERRED.items():
        if col in out.columns:
            out[col] = shape_new[key].to_numpy()

    mov_ref = np.hypot(shape_ref["ivb"], shape_ref["hb"]).to_numpy()
    mov_new = np.hypot(shape_new["ivb"], shape_new["hb"]).to_numpy()
    if "movement_total" in out.columns:
        out["movement_total"] = mov_new
    if "VertBreak" in out.columns and "VertBreak" in X.columns:
        # El quiebre vertical bruto incluye gravedad; solo su parte de spin responde al aire.
        out["VertBreak"] = X["VertBreak"].to_numpy() + (
            shape_new["ivb"].to_numpy() - shape_ref["ivb"].to_numpy()
        )
    if "spin_efficiency" in out.columns:
        # La eficiencia es movimiento por revolucion: si el movimiento baja y el giro no,
        # la eficiencia baja en la misma proporcion.
        ratio = np.divide(mov_new, mov_ref, out=np.ones_like(mov_new), where=mov_ref > 1e-6)
        out["spin_efficiency"] = X["spin_efficiency"].to_numpy() * ratio
    return out
