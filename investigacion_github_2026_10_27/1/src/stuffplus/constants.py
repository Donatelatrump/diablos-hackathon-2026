"""Constantes fisicas y de geometria del campo (unidades Trackman: pies, segundos)."""

G = 32.174          # ft/s^2, gravedad
Y_PLATE_FRONT = 17.0 / 12.0   # ft, frente del home (la punta esta en y=0)
Y_RELEASE = 50.0    # ft, plano de medicion de Trackman
FT_TO_IN = 12.0
FPS_TO_MPH = 0.681818

# Altitudes de referencia (m) y su densidad relativa aproximada (modelo ISA)
ALT_SEA_LEVEL = 0
ALT_COORS = 1609
ALT_HARP_HELU = 2240

# Cubetas del dataset -> densidad relativa mediana medida (ver physics.air_density_index)
# Estos valores se recalculan desde los datos; quedan aqui como referencia documentada.
RHO_REF = {
    "No Altitude": 1.000,
    "Medium Altitude": 0.900,
    "Extreme Altitude": 0.855,
}

PITCH_TYPE_MAP = {
    "Four-Seam": "Four-Seam",
    "Sinker": "Sinker",
    "Cutter": "Cutter",
    "Changeup": "Changeup",
    "Splitter": "Splitter",
    "Slider": "Slider",
    "Sweeper": "Slider",
    "Curveball": "Curveball",
    "OneSeamFastBall": "Sinker",
    "TwoSeamFastBall": "Sinker",
    "Knuckleball": "Other",
    "Other": "Other",
}

FASTBALL_TYPES = {"Four-Seam", "Sinker", "Cutter"}
