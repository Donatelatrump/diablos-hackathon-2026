"""Exploratory density-only movement hypothesis, independent of production scoring.

Assumes induced displacement scales linearly with standard-atmosphere density
at fixed flight time, spin, release and speed. Omits drag and seam effects.
This is an educational approximation, not a calibrated flight integrator.
"""
import math


def relative_density(altitude):
    altitude = float(altitude)
    if not math.isfinite(altitude) or not 0 <= altitude <= 3000:
        raise ValueError('Altitude must be finite and between 0 and 3000 metres')
    return (1 - 2.25577e-5 * altitude) ** 4.25588


def transfer_movement(measurements, origin, destination):
    ratio = relative_density(destination) / relative_density(origin)
    result = dict(measurements)
    for key in ['RelSpeed', 'HorzBreak', 'InducedVertBreak']:
        value = float(measurements[key])
        if not math.isfinite(value) or (key == 'RelSpeed' and value <= 0):
            raise ValueError('Invalid movement measurements')
        result[key] = value if key == 'RelSpeed' else value * ratio
    return result
