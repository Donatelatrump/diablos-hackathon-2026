# Validación de esta entrega

Fecha: 17 de octubre de 2026.

- Entrenamiento y selección de alternativas completados; protocolo congelado con 2025 antes del benchmark v6 de 2026.
- 135,604 pitches de 2026 con predicciones completas, sin PitchUID repetidos.
- `verificar_modelo_v6.py` completado con código de salida 0, antes y después de instalar las dependencias de interfaz. Los resultados están en `verificacion.json`.
- Suite de 22 pruebas completada con código de salida 0: `python -m unittest test_stuff_plus_v5.py test_stuff_plus_v6.py test_dashboard_stuff_plus_v6.py -v`.
- La prueba de interfaz usa Streamlit AppTest, sin navegador visible: comprueba el respaldo v5, las mediciones adicionales, los cambios de ubicación y el orden del ranking por whiff.
- Los tres índices compuestos coinciden exactamente con v5 en esta ejecución. No se seleccionaron sustitutos para los modelos de valor de carreras; las mejoras están en whiff y en la salida contextual separada.
- El ranking se publica mediante reemplazo atómico del CSV para evitar lecturas parciales mientras se regenera.

Los resultados predictivos y sus contrapartidas están en `RESULTADO_MEJORA.md`. 2026 es un benchmark reutilizado y la ECE empeora: esta entrega no demuestra generalización a datos nuevos ni una mejora del índice compuesto.
