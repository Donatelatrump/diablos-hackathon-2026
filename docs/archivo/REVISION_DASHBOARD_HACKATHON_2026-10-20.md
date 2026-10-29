# Revisión del dashboard frente al hackatón

Actualización posterior aplicada el 20/10/2026: se corrigieron las brechas de interfaz identificadas abajo. Ya se muestran nueve probabilidades y sus denominadores, riesgos HR/contacto fuerte y deltas por categoría, baseline por conteo, métricas temporales, explicación SHAP local del simulador, perfiles con mayor/menor efectividad y consulta/descarga de scores. Se añadió catálogo de 23 sedes con fuentes (21 referencias publicadas de altitud; dos pendientes), auditoría de identificación y unión exacta por juego documentado. Se regeneró el paquete. La matriz siguiente conserva el diagnóstico inicial; siguen pendientes la identificación nominal de parques, el park holdout, un óptimo demostrado para Harp Helú, el transporte físico entre entornos y la normalización validada por estadio. La búsqueda pública no proporciona correspondencia con IDs anónimos: ningún juego se adjudicó por conjetura. Véase `entrega_v8/ESTADIOS_Y_ALTITUDES.md`.

Fecha: 20 de octubre de 2026. Alcance: código local vigente, pruebas Streamlit, tablas y documentación v8. No se reentrenaron modelos ni se certifica la evaluación del jurado. No se hizo inspección visual en navegador ni se repitió toda la auditoría de entrenamiento.

Fuente: [convocatoria oficial ISAC Diablos Rojos](https://www.isac-app.com/competition-details/hackathon-diablos-rojos.html), consultada el 20/10/2026, secciones de entregables, arquitectura y evaluación.

## Dictamen

Cumplimiento parcial. La demo local permite simular, obtener los tres índices, consultar fichas y arsenal, visualizar movimiento y revisar casos. No permite afirmar cumplimiento completo del contraste específico Harp Helú/nivel del mar, la validación por parque ni la normalización por estadio. Estas brechas requieren datos o evidencia adicional, no solo diseño de interfaz.

## Matriz de evidencia

| Requisito o criterio | Estado | Evidencia y brecha |
|---|---|---|
| Ingresar características físicas y obtener Stuff+ | Cumple funcionalmente | `dashboard_stuff_plus_v6.py`, reutilizado por v8; controles de velocidad, spin, movimiento, release y extensión; inferencia real. Respaldo de versión explícito cuando faltan mediciones adicionales. |
| Mostrar Stuff+, Location+, Pitching+ | Cumple funcionalmente | Tres indicadores calculados; pruebas verifican que cambiar ubicación no cambia Stuff+. No prueba calibración por estadio. |
| Comparar mismo pitch Harp Helú vs. nivel del mar | Parcial, brecha principal | `dashboard_entrega_v8.py` compara tres categorías de altitud con física fija. No existe mapeo validado de categoría a Harp Helú. Stuff+ físico permanece igual; cambia el contexto de Pitching+. No hay transporte físico de movimiento. |
| Mapa de movimiento y efectividad | Cumple en versión agregada | HB/IVB, tipo, tamaño de muestra y color por índice/probabilidad. Son 5,360 medias de perfiles; no pitches individuales. Falta una selección explícita de mejores/peores y escala visual centrada en 100 para facilitar interpretación. |
| Scores por lanzamiento, pitcher y arsenal | Disponibles; acceso parcial en interfaz | 135,604 filas de scores, 550 agregados pitcher y 2,936 pitcher/tipo. Fichas y arsenal visibles; descarga de ficha. Falta explorador/descarga de scores por pitch desde la app. |
| Perfil físico ideal para Diablos | Parcial | Tabla de perfiles del decil superior por tipo/mano/entorno. Es descriptiva y condicionada al modelo; no demuestra un óptimo para Harp Helú. |
| Recomendaciones operativas | Parcial | Tres casos y acciones de revisión, con muestras e intervalos. Falta síntesis por perfil de ganancias/pérdidas en CDMX y cuantificación de riesgo específico del estadio. |
| Explicaciones interpretables | Parcial | SHAP agregado disponible para tres casos. No hay explicación local de cada lanzamiento simulado. |
| Validación fuera de muestra | Parcial | Vista de auditoría con pitchers excluidos y documentación temporal. Park holdout pendiente. Benchmark 2026 reutilizado, advertido. No se equipara la auditoría reentrenada al modelo desplegado. |
| Baseline de carreras por conteo | Disponible, poco visible | `baseline_conteo_modelo_vigente.csv` y PDF; la pestaña solo muestra ganancia contra constante. Debe mostrar la comparación por conteo y procedencia. |
| Escala 100 por temporada/estadio | Parcial | Referencia histórica fija; no evidencia de normalización por cada estadio. No corregir recentrando artificialmente los datos de prueba. |
| Targets multiobjetivo | Parcial en pantalla | La pantalla muestra whiff, whiff dado swing, bola en juego, HR y velocidad de salida. Los modelos heredados incluyen chase, strike cantado, contacto débil/fuerte y rodado, pero no se exponen allí. No se encontró objetivo de out por PA en las tareas revisadas. |
| Documento técnico de 6–10 páginas | Cumple extensión | PDF vigente de ocho páginas descargable. Extensión comprobada; no implica cumplimiento de las brechas científicas anteriores. |
| Entrega reproducible y coherente | Pendiente de actualizar | Los hashes del manifiesto no coinciden para `codigo/dashboard_entrega_v8.py` y `codigo/dashboard_stuff_plus_v6.py` tras las correcciones visuales. El ZIP existente no debe asumirse actualizado con la demo. Sin modelos binarios, no ejecuta la demo completa de forma autónoma; requiere acceso autorizado a artefactos. |

## Evidencia de calidad del modelo

Comparación temporal 2026 conservada desde v5 para los modelos de carreras desplegados hasta v8; no corresponde a una evaluación nueva ni al holdout de pitchers reentrenado:

| Modelo | RMSE | RMSE baseline por conteo | Ganancia MSE frente al conteo |
|---|---:|---:|---:|
| Físico | 0.21764 | 0.21646 | -1.09% |
| Ubicación/contexto | 0.21315 | 0.21646 | +3.03% |
| Con entorno | 0.21308 | 0.21646 | +3.09% |

El modelo físico no supera ese baseline; la mejora contextual no demuestra por sí misma una mejora de Stuff+ físico. No asigno puntuación ni porcentaje de cumplimiento del jurado.

## Verificaciones ejecutadas

- `python -m unittest test_dashboard_stuff_plus_v8.py test_entrega_v8.py -v`: seis pruebas pasaron, sin excepciones de aplicación. Cubren cambio de mediciones, independencia de Stuff+ ante ubicación, ranking, fichas, muestra insuficiente, comparación de HR y descarga de PDF; además, partición de pitchers y controles del análisis.
- Se comprobaron extensión del PDF, tamaños/columnas de las tablas y hashes del manifiesto contra archivos actuales.
- Aparecieron advertencias de Streamlit por `use_container_width` y un error de permisos al limpiar un directorio temporal al salir. Las seis pruebas terminaron en OK; la limpieza temporal no quedó resuelta en esta revisión.
- La verificación integral de entrenamiento/ZIP no se volvió a ejecutar. El archivo previo `VERIFICACION_ENTREGA.json` no certifica el estado actual, dado el desfase de hashes.

## Prioridades antes de presentar

1. Obtener o documentar la ausencia del mapeo oficial juego-estadio. Con mapeo, construir comparación nominal y validación por parque. Sin él, presentar expresamente cumplimiento parcial.
2. Hacer visible en la demo la comparación contra baseline por conteo, validación temporal y limitaciones de la referencia 100.
3. Mostrar riesgos HR/contacto fuerte y probabilidades disponibles, con etiquetas que distingan tasas por lanzamiento de tasas condicionadas a contacto/swing.
4. Añadir lectura rápida de perfiles buenos/malos y diferencias entre escenarios, conservando las advertencias de soporte muestral.
5. Facilitar consulta/exportación de scores y recomendaciones. Definir cómo recibirá el jurado acceso al dashboard con sus modelos.
6. Regenerar paquete y manifiesto después de cerrar cambios, y volver a verificar su integridad. Completar integrantes/correos y requisitos administrativos por separado.

No se enviaron mensajes a la organización ni se modificaron modelos, ZIP o manifiesto durante esta revisión.
