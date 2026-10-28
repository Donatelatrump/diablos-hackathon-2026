"""
Semana 1 - Ancla fisica del proyecto Stuff+ LMB
Densidad del aire por altitud y primer escalado del break.

Uso:
    python3 densidad_altitud.py

Este script NO es el modelo fisico final (eso va en semanas 3-4).
Es el ancla numerica que necesitas para no volver a citar
porcentajes de altitud sin poder derivarlos.
"""

import math

# ---------------------------------------------------------------
# Constantes de la Atmosfera Estandar Internacional (ISA)
# ---------------------------------------------------------------
RHO0 = 1.225        # densidad al nivel del mar, kg/m3 (15 C, 101325 Pa)
T0   = 288.15       # temperatura al nivel del mar, K
L    = 0.0065       # gradiente termico, K/m
G    = 9.80665      # gravedad, m/s2
M    = 0.0289644    # masa molar aire seco, kg/mol
R    = 8.31447      # constante universal de los gases, J/(mol K)

R_ESPECIFICO_SECO = 287.058   # J/(kg K)
R_ESPECIFICO_VAPOR = 461.495  # J/(kg K)

EXPONENTE = G * M / (R * L) - 1   # ~4.2559


def densidad_isa(altitud_m: float) -> float:
    """Densidad del aire segun atmosfera estandar. Solo depende de la altitud.

    Sirve como referencia, pero para dias de juego reales usa
    densidad_real(), que toma presion y temperatura observadas.
    """
    return RHO0 * (1 - L * altitud_m / T0) ** EXPONENTE


def presion_isa(altitud_m: float) -> float:
    """Presion atmosferica estandar en Pa a una altitud dada."""
    return 101325.0 * (1 - L * altitud_m / T0) ** (G * M / (R * L))


def presion_vapor_saturacion(temp_c: float) -> float:
    """Presion de vapor de saturacion en Pa (formula de Tetens)."""
    return 610.78 * math.exp(17.27 * temp_c / (temp_c + 237.3))


def densidad_real(presion_pa: float, temp_c: float, humedad_rel: float = 0.0) -> float:
    """Densidad del aire humedo via ley de gases ideales.

    Esta es la funcion que vas a usar en el modelo real: la altitud
    del estadio es constante, pero temperatura y humedad cambian
    juego a juego y mueven la densidad varios puntos porcentuales.

    presion_pa   : presion de estacion en Pascales
    temp_c       : temperatura en Celsius
    humedad_rel  : humedad relativa, 0.0 a 1.0
    """
    temp_k = temp_c + 273.15
    p_vapor = humedad_rel * presion_vapor_saturacion(temp_c)
    p_seco = presion_pa - p_vapor
    return p_seco / (R_ESPECIFICO_SECO * temp_k) + p_vapor / (R_ESPECIFICO_VAPOR * temp_k)


ESTADIOS = [
    ("Nivel del mar (referencia)", 0),
    ("Coors Field, Denver",        1609),
    ("Harp Helu, CDMX",            2240),
]


def main() -> None:
    print("=" * 66)
    print("DENSIDAD DEL AIRE POR ALTITUD (atmosfera estandar)")
    print("=" * 66)
    for nombre, h in ESTADIOS:
        rho = densidad_isa(h)
        print(f"{nombre:28s} {h:5d} m   rho = {rho:.4f} kg/m3   "
              f"({100 * (1 - rho / RHO0):5.2f}% vs mar)")

    rho_coors = densidad_isa(1609)
    rho_cdmx = densidad_isa(2240)
    print(f"\nEl aire del Harp Helu es {100 * (1 - rho_cdmx / rho_coors):.2f}% "
          f"menos denso que el de Coors Field.")

    print("\n" + "=" * 66)
    print("ESCALADO LINEAL DEL BREAK  (Magnus proporcional a rho)")
    print("=" * 66)
    print("Referencia: un lanzamiento con 18\" de break al nivel del mar\n")
    for nombre, h in ESTADIOS[1:]:
        rho = densidad_isa(h)
        print(f"  {nombre:28s} -> {18 * rho / RHO0:5.2f} pulgadas")

    print("\n" + "-" * 66)
    print("HUECO ABIERTO (resolver en semanas 3-4):")
    print("-" * 66)
    print("""
El escalado lineal predice 15.38\" en Coors. La convocatoria cita a
Nathan con 14-15\". Es decir, el efecto observado es MAS fuerte que
lineal en rho.

Hipotesis a probar:
  (a) Menos arrastre  ->  la bola llega mas rapido  ->  menos tiempo
      de vuelo  ->  menos tiempo para que actue la fuerza Magnus.
      Es un efecto de segundo orden que AMPLIFICA la perdida de break.
  (b) El coeficiente de sustentacion C_L depende del numero de Reynolds,
      que tambien cambia con rho.
  (c) Nathan mide break percibido respecto a una trayectoria sin spin,
      no deflexion pura.

Hasta resolverlo, NO reportes un delta de break para CDMX como si
fuera un hecho. El numero honesto de la semana 1 es un rango:
    14.4\" (lineal)  a  ~13.5\" (si el efecto super-lineal se sostiene)
""")

    print("=" * 66)
    print("SENSIBILIDAD A CONDICIONES DE JUEGO (Harp Helu)")
    print("=" * 66)
    p_cdmx = presion_isa(2240)
    print(f"Presion de estacion estandar en CDMX: {p_cdmx:.0f} Pa\n")
    for temp in (12, 18, 24, 30):
        for hum in (0.20, 0.60):
            rho = densidad_real(p_cdmx, temp, hum)
            print(f"  {temp:2d} C, {int(hum * 100):2d}% HR  ->  rho = {rho:.4f} kg/m3  "
                  f"({100 * (1 - rho / RHO0):5.2f}% vs mar)")
    print("""
Nota: un juego caluroso y humedo en CDMX puede tener aire varios
puntos porcentuales menos denso que uno frio y seco. Si el dataset
del hackathon trae temperatura, la altitud NO deberia entrar al
modelo como dummy de estadio, sino como densidad calculada por juego.
Ese solo cambio de encuadre ya te distingue del resto de equipos.
""")


if __name__ == "__main__":
    main()
