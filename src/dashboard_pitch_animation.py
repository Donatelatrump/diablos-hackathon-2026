"""Illustrate measured pitch break without claiming to reconstruct a full flight."""
import html
import json
import math
from pathlib import Path

import streamlit as st

from dashboard_perfiles_estadios import HANDS, PITCH_NAMES


def animation_document(pitch, hand, measurements, reference=None):
    values = {}
    for key in ("RelSpeed", "HorzBreak", "InducedVertBreak"):
        try:
            number = float(measurements.get(key))
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number):
            return None
        values[key] = number
    if values["RelSpeed"] <= 0:
        return None
    # Retain the signed measurement: hand-specific profiles already contain direction.
    values["hand"] = hand if hand in ("Right", "Left") else "Undefined"
    if reference is not None:
        try:
            for key in ('RelSpeed', 'HorzBreak', 'InducedVertBreak'):
                value = float(reference[key])
                if not math.isfinite(value) or (key == 'RelSpeed' and value <= 0):
                    return None
        except (KeyError, TypeError, ValueError):
            return None
        values['comparison'] = {key: float(reference[key]) for key in ('RelSpeed', 'HorzBreak', 'InducedVertBreak')}
    payload = json.dumps(values, allow_nan=False)
    template = (Path(__file__).resolve().parents[1] / "assets/visualizacion/dashboard_pitch_animation.html").read_text(encoding="utf-8")
    scene_code = (Path(__file__).resolve().parents[1] / "assets/visualizacion/dashboard_pitch_scene.bundle.js").read_text(encoding="utf-8")
    document = (template.replace("__PITCH__", html.escape(PITCH_NAMES.get(pitch, pitch)))
        .replace("__HAND__", html.escape(HANDS.get(hand, hand)))
        .replace("__MEASUREMENTS__", payload)
        .replace("__THREE_SCENE__", scene_code))
    if reference is not None:
        document = document.replace('Línea roja: lanzamiento elegido · Línea azul punteada: referencia sin movimiento inducido, a 90 mph.',
            'Línea roja: destino exploratorio · Línea azul punteada: mediciones de origen.')
        document = document.replace('Es una ilustración: no predice la ubicación real ni el efecto del estadio elegido.',
            'Hipótesis de densidad: velocidad y tiempo de vuelo fijos, sin arrastre. No es una trayectoria validada ni modifica la evaluación.')
    return document


def render_pitch_animation(pitch, hand, measurements):
    st.subheader("Mira el lanzamiento en 3D")
    explore = st.toggle('Explorar el efecto de la altitud', key='altitude-lab-enabled')
    reference = None
    if explore:
        from pitch_altitude_lab import relative_density, transfer_movement
        st.markdown('<div class="visual-scope"><b>Laboratorio exploratorio</b> · Compara una hipótesis física; los índices de evaluación se conservan.</div>', unsafe_allow_html=True)
        a, b = st.columns(2)
        origin = a.slider('Altitud de origen (metros)', 0, 3000, 0, 10, key='lab-origin')
        destination = b.slider('Altitud de destino (metros)', 0, 3000, 2240, 10, key='lab-destination')
        st.caption('Ejemplo: Harp Helú está a unos 2,240 m. Estas altitudes son independientes del selector de estadio. Indica dónde se midió el lanzamiento de origen.')
        try:
            transferred = transfer_movement(measurements, origin, destination)
        except (KeyError, ValueError, TypeError):
            st.info('Completa velocidad y movimiento para explorar la altitud.')
            return
        st.dataframe([{'Medición': label, 'Origen (pulgadas)': float(measurements[key]),
                       'Destino exploratorio (pulgadas)': transferred[key],
                       'Cambio (pulgadas)': transferred[key] - float(measurements[key])}
                      for key, label in [('InducedVertBreak', 'Movimiento vertical inducido'), ('HorzBreak', 'Movimiento lateral')]],
                     hide_index=True, width='stretch')
        ratio = relative_density(destination) / relative_density(origin)
        st.write(f'La densidad relativa cambia **{(ratio-1)*100:+.1f}%** respecto al origen. En esta hipótesis, el movimiento inducido cambia en la misma proporción; su dirección se conserva.')
        st.caption('Aproximación educativa: mantiene velocidad y tiempo de vuelo; omite arrastre, cambios de giro y efectos de costuras. Tiene comprobaciones matemáticas, pero no validación contra vuelos reales. No alimenta Stuff+, Location+ ni Pitching+.')
        reference, measurements = measurements, transferred
    else:
        st.markdown('<div class="visual-scope"><b>Movimiento ilustrado</b> · Esta animación no cambia con el estadio. Activa el laboratorio para explorar una hipótesis de altitud.</div>', unsafe_allow_html=True)
    st.caption("Cambia de lanzamiento para comparar su movimiento. Si introduces mediciones, pulsa «Ver evaluación» para aplicarlas.")
    document = animation_document(pitch, hand, measurements, reference=reference)
    if document is None:
        st.info("No hay suficientes mediciones válidas para ilustrar este lanzamiento.")
        return
    st.iframe(document, height="content", alt="Escena 3D con pitcher animado, pelota y trayectoria; permite girar la cámara, pausar y repetir")

