# Validación de la entrega v7

Ejecución completada el 17 de octubre de 2026 en el entorno local del proyecto.

- Entrenamiento: tres bloques OOF de siete componentes y siete modelos finales; selección congelada antes de leer 2026.
- Auditoría: `verificar_modelo_v7.py` terminó con código 0. Revisó 135,604 scores, 299,031 filas OOF, roles disjuntos por juego, exclusión del juego predicho, hashes, reproducción de predicciones y pesos, inferencia sin resultados, invariancia física, independencia del tamaño del lote y respaldo exacto.
- Modelos: `python -m unittest test_stuff_plus_v5 test_stuff_plus_v6 test_stuff_plus_v7 -v`: 33 pruebas aprobadas.
- Interfaz: `python -m unittest test_dashboard_stuff_plus_v6 test_dashboard_stuff_plus_v7 -v`: dos pruebas aprobadas con Streamlit AppTest, incluyendo la entrada principal ya activada en v7, mediciones adicionales, respaldo, ubicación y orden del arsenal. La interfaz compartida v6 también se comprobó antes de activar v7.
- Reporte y gráfica generados; gráfica inspeccionada visualmente.

La selección aceptó sigmoide para whiff e isotónica para whiff dado swing. El compuesto obtuvo 0.0597% de reducción de MSE en selección, inferior al mínimo prefijado de 0.1%; no reemplaza los índices anteriores.

En el benchmark reutilizado 2026, calibrar whiff dado swing redujo Brier 0.93% respecto al mismo núcleo v7 sin calibrar, mientras calibrar whiff por pitch lo empeoró aproximadamente 0.06%. La comparación total frente a v6 también es mixta: no se afirma una mejora global. No se modificaron las decisiones usando estos resultados.

Consulta `RESULTADO_MEJORA.md` para métricas e intervalos y `verificacion.json` para las comprobaciones reproducibles. La siguiente confirmación requiere datos futuros independientes.
