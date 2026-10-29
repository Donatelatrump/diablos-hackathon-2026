# Validación v8

Entrega completada el 17 de octubre de 2026.

- Entrenamiento de siete alternativas globales y nueve especialistas; controles v7 reutilizados con las mismas particiones, semillas y presupuestos de las alternativas globales.
- Selección congelada antes de evaluar 135,604 pitches de 2026. Cuatro tareas aceptadas en desarrollo: whiff, whiff dado swing, bola en juego y EV.
- `python -m unittest test_stuff_plus_v5 test_stuff_plus_v6 test_stuff_plus_v7 test_stuff_plus_v8 -v`: 39 pruebas aprobadas.
- `python src/verificar_modelo_v8.py`: auditoría aprobada; hashes, particiones iguales al control, juegos disjuntos, decisiones reproducidas, predicciones reproducidas, inferencia sin outcomes, invariancia física, respaldo completo y por fila, e independencia del tamaño de lote.
- `python src/reportar_mejora_v8.py`: reporte, ranking y gráfica generados; gráfica inspeccionada visualmente.
- `python -m unittest test_dashboard_stuff_plus_v6 test_dashboard_stuff_plus_v7 test_dashboard_stuff_plus_v8 -v`: tres pruebas de interfaz aprobadas, incluida la entrada principal activa en v8, simulación, mediciones nuevas y ordenamiento del arsenal.

En total: 42 pruebas aprobadas, además de la auditoría de artefactos. La interfaz principal activa v8 porque la selección anterior a 2026 aceptó cambios y los artefactos están verificados.

## Resultado y límites

Frente a v7, Brier mejora 0.144% en whiff, 2.194% en whiff dado swing y 0.825% en bola en juego. Sus AUC también mejoran. Sin embargo, ECE empeora en whiff dado swing (0.012782 → 0.021505) y bola en juego (0.007973 → 0.013189): la mejora no abarca todas las medidas de calibración.

EV empeora de 15.295926 a 15.301194 mph de RMSE; el intervalo de la diferencia de MSE incluye cero. Rodados, HR y valor de carreras conservan el padre. Stuff+, Location+ y Pitching+ no cambian en esta ejecución.

2026 es un benchmark reutilizado. La selección se conserva tal como quedó fijada con desarrollo: los resultados de 2026 no se usan para reajustar, cambiar calibradores ni revertir selectivamente tareas. Hace falta evaluación futura independiente.

V8 implementa velocidad y especialistas, no un nuevo objetivo esperado de contacto ni RE24. Esos experimentos se describen como trabajo posterior en README_MODELO_V8.md.
