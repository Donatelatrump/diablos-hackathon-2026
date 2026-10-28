# Estado actualizado de la entrega

Se completaron las mejoras de validación, análisis por perfil, recomendaciones, interfaz y documentación. Se mantienen límites metodológicos explícitos; no se certifica cumplimiento literal total ni elegibilidad del equipo.

## Evaluaciones ejecutadas

| Prueba | Tareas | Pitches | RMSE combinado | Mejora MSE vs conteo |
|---|---:|---:|---:|---:|
| season | 13 | 135604 | 0.213269 | 2.92% |
| pitcher | 13 | 25426 | 0.211864 | 2.98% |
| park | 13 | 6005 | 0.227901 | 2.78% |

## Entregables disponibles

- Modelos y scores por lanzamiento, pitcher y arsenal; escenarios Harp Helú.
- Comparaciones por tipo y mano, soporte de desarrollo e intervalos por juegos.
- Rangos físicos descriptivos y tres casos de scouting con acciones concretas.
- Dashboard con lenguaje deportivo, explicaciones de escala, denominadores y avisos de muestra insuficiente.
- Documento técnico actualizado de nueve páginas y paquete con modelos para inferencia sin dataset original.
- Calibración y métricas por estadio; el desfase de HR en Harp se muestra explícitamente.

## Límites y decisiones conservadas

- Pitching+ de carreras mantiene delta cero por estadio al no confirmarse ganancia incremental; el índice integral puede variar. Ambos describen predicciones, no efectos causales.
- No hay óptimo causal de contratación ni mezcla óptima de arsenal demostrados. Los perfiles son referencias descriptivas.
- P(out al cerrar PA) implementado y validado en tres auditorías; excluye secuencias incompletas. Incluye selección/doble play, no necesariamente bateador retirado.
- Índice integral de ocho objetivos con pesos iguales prefijados y referencia de calibración. No es una probabilidad ni prueba de superioridad del índice sobre RV.
- Normalización descriptiva por temporada/estadio disponible, con respaldo a temporada en grupos pequeños o desconocidos. El simulador conserva escala prospectiva fija.
- 2026 es reutilizado. La clasificación de estadio es inferida y tiene filas pendientes.
- Las pruebas funcionales usan Streamlit AppTest. No hubo navegador conectado para inspección visual de la aplicación; no se afirma una revisión visual móvil/escritorio.
- El PDF se renderiza y revisa por páginas antes de la entrega final. La verificación de integridad se registra en VERIFICACION_ACTUAL.json.
- Nombres, correos, elegibilidad y envío quedan a cargo del equipo. No se ha enviado ni publicado el paquete.

Consultar README_PRIMERO.md del paquete para abrir el tablero y RECOMENDACIONES_ACTUALES.md para la revisión deportiva.
