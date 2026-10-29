# Análisis de entrega y usabilidad para el coach

Fecha: 27 de octubre de 2026. Revisión de convocatoria oficial, código vigente, tablas, PDF, manifiesto y ZIP. Análisis de interacción a partir de código y pruebas Streamlit; no constituye una prueba visual en navegador ni una entrevista con coaches. No se modificaron modelos ni interfaz.

## Dictamen

Tenemos una solución analítica avanzada y los cinco productos de entrega representados. No podemos sostener cumplimiento completo: falta demostrar la transferencia específica a Harp Helú, validar por parque y justificar la normalización por estadio. Para el coach, la principal oportunidad es pasar de explorar tablas y métricas a consultar un pitcher, entender la evidencia y elegir el siguiente paso de revisión.

Convocatoria consultada: https://www.isac-app.com/competition-details/hackathon-diablos-rojos.html. La página conserva entrega el 22/10, finalistas el 02/11 y final el 11/11 de 2026. Hoy ya pasó la fecha publicada de entrega; no hay evidencia local revisada que confirme envío o prórroga.

## Matriz de entrega actual

| Solicitud | Evidencia comprobada | Estado y pendiente |
|---|---|---|
| Scores por pitch, pitcher y arsenal | 135,604 scores de 2026, 550 filas agregadas de pitcher y 2,936 filas de arsenal; tres índices y descargas | Disponible. No equivalen a scores de las tres temporadas completas. Falta contraste nominal por estadio. |
| Perfil ideal para Diablos | Rangos de perfiles del decil superior por tipo, mano y categoría | Parcial: describe perfiles favorecidos por el modelo; no demuestra un óptimo en Harp Helú. |
| Recomendaciones operativas | Tres casos con muestra, índices y acciones; asociaciones ajustadas por entorno | Parcial: las acciones de los tres casos repiten el mismo texto y falta una recomendación específica sustentada para CDMX. |
| Simulador y mapa | Inferencia real, tres índices, nueve probabilidades, SHAP local, mapa de 5,360 medias de perfiles y comparación de categorías | Funcional. Comparar categorías con física fija no reproduce el mismo lanzamiento trasladado entre Harp Helú y nivel del mar. |
| Documento de 6–10 páginas | PDF vigente de ocho páginas | Cumple extensión; las limitaciones científicas permanecen. |
| Validación por temporada y pitcher | Métricas temporales y auditoría separada de pitchers excluidos | Parcial: 2026 es un benchmark reutilizado; auditoría reentrenada distinta del bundle desplegado. |
| Validación por parque y escala ajustada por estadio | Catálogo geográfico y auditoría de cobertura | Pendiente: 0 de 2,127 juegos vinculados a un estadio; la referencia 100 es histórica y fija. |
| Entrega utilizable por terceros | Código, resultados, documento y ZIP coherentes | Integridad comprobada. ZIP sin modelos binarios: la demo completa requiere artefactos adicionales o acceso a un entorno preparado. |
| Administración | README enumera pendientes | Confirmar envío, nombres, correos, elegibilidad y forma de acceso del jurado. |

La revisión anterior señalaba hashes desfasados. Esa observación ya no describe el estado actual: todos los archivos declarados coinciden con el manifiesto, el ZIP tiene el inventario esperado y su contenido coincide con los hashes. Las cinco entradas/módulos de dashboard comprobados también coinciden con las copias empaquetadas.

## Riesgos que más afectan la evaluación

1. **Entorno:** categorías de altitud sin mapeo de juego a estadio. Un catálogo público de sedes no resuelve la identidad de los juegos anónimos. Obtener correspondencia oficial; después diseñar particiones por parque y comparaciones de perfiles con incertidumbre. Si no se obtiene, presentar el alcance por categoría de forma explícita.
2. **Calidad física:** frente al baseline por conteo, el modelo físico tiene ganancia MSE de −1.09%; ubicación +3.03%; entorno +3.09% en el benchmark temporal 2026. El físico dispone de menos contexto que el baseline, pero no lo supera. No presentar la mejora contextual como una mejora del índice físico.
3. **Generalización:** la auditoría de pitchers nuevos aporta evidencia, pero no es idéntica al modelo desplegado ni crea una temporada futura intacta. En ella, HR tiene AUC aproximada de 0.599 y una mejora Brier muy pequeña: evitar vender el riesgo individual de jonrón como una predicción precisa.
4. **Definiciones:** no hay estimación de out por aparición al plato; carreras es un proxy de pesos fijos. La convocatoria describe whiff incluyendo foul o miss; aquí significa swing y fallo. Documentar esta discrepancia. Contacto fuerte no es barrel.
5. **Uso real:** una demo que solo funciona en el workspace deja incierto cómo la usará el jurado o el coach. Preparar un entorno accesible y probarlo desde una sesión limpia con todos los artefactos autorizados.

## Problemas de uso observables

| Hallazgo en el código actual | Consecuencia para el coach | Cambio propuesto |
|---|---|---|
| Dos grupos de pestañas: dos principales y seis adicionales debajo | Cuesta descubrir dónde empezar y cómo se relacionan las vistas | Una navegación: Pitcher, Comparar, Probar cambios; sección Técnica separada. |
| Apertura en simulador con valores ilustrativos y controles plegados | Puede interpretar un resultado de ejemplo como un diagnóstico real | Abrir en selección de pitcher; identificar explícitamente toda simulación de ejemplo. |
| Aproximadamente veinte controles iniciales y once mediciones adicionales | Mucha carga manual y riesgo de mezclar mediciones incompatibles | Cargar un perfil observado con procedencia; mostrar pocos cambios y dejar el resto en Avanzado. |
| Selección de perfil histórico de arsenal no carga automáticamente sus mediciones físicas | Puede creer que está simulando un lanzamiento real del pitcher | Separar «Usar lanzamiento observado» de «Crear ejemplo» y mostrar qué historial se usa. |
| Pitcher elegido por separado en ficha, scores y arsenal histórico del simulador | Es fácil perder el contexto o revisar otro pitcher | Una selección persistente de pitcher, temporada y referencia de score. |
| Encabezado con versiones, selección, benchmark y detalles del modelo | El primer contacto exige entender implementación | Encabezado deportivo y acceso visible a evidencia técnica. |
| Nueve probabilidades en gráfico y tabla, más índices y salidas estimadas | Sobrecarga y comparación de eventos con denominadores diferentes | Resumen con índice, swing y fallo, riesgo y muestra; ampliar para ver todos los resultados. |
| Tablas con columnas como score_reference_id, HB o p_whiff_given_swing | Obliga a traducir nombres internos | Etiquetas en español, unidades visibles y ayuda breve. |
| Right/Left y categorías en inglés | Añade fricción evitable | Diestro/Zurdo; etiquetas traducidas conservando la categoría original en detalle. |
| Mejores y peores perfiles pueden compartir filas cuando hay pocos | Produce mensajes aparentemente contradictorios | Mostrar una sola lista ordenada cuando no haya suficientes perfiles distintos. |
| Recomendaciones genéricas repetidas | La pantalla informa, pero orienta poco el siguiente paso | Acción específica por caso con motivo y dato que cambiaría la recomendación. |
| Descarga de ficha solo en CSV | Poco práctica en campo o para una reunión | Ficha imprimible de una página, con resumen, arsenal, mapa y siguiente paso. |

## Recorrido propuesto

**Inicio → elegir pitcher → entender su ficha → comparar → exportar.**

La ficha abre con una conclusión prudente y concreta: «Priorizar revisión», «Revisar ubicación» o «Reunir más datos». Debajo: una razón, el tamaño de muestra y la acción sugerida. Es una prioridad de revisión, no una decisión automática de contratación ni una certificación de confianza.

Mostrar calidad física (Stuff+), rendimiento contextual estimado (Pitching+) y una explicación de la referencia. Un Stuff+ de 110 representa una desviación estándar por encima de la referencia guardada; no significa 10% más rendimiento. Location+ queda disponible como detalle de ubicación/contexto, sin presentarlo como medición causal de comando.

El arsenal se resume por tipo: uso observado, velocidad, movimiento, índice y soporte de muestra. El mapa mantiene una vista predeterminada legible, leyenda en español y la orientación por mano explicada. Las comparaciones deben compartir temporada y referencia de score; las discrepancias de referencia se avisan antes de ordenar.

«Comparar» conserva al pitcher seleccionado y distingue dos tareas: comparar pitchers con referencia compatible y explorar categorías de entorno. Hasta tener mapeo, la comparación de entorno se llama «Escenarios de altitud» y explica junto al resultado que mantiene la física fija. Las probabilidades que no usan altitud pueden permanecer iguales; eso no demuestra ausencia de efecto real.

«Probar cambios» parte de un lanzamiento observado o un ejemplo identificado. Para una primera exploración: velocidad, movimiento horizontal y vertical; los demás datos se conservan desde la observación con procedencia visible. Para un pitcher nuevo se requieren las mediciones necesarias o se informa claramente el respaldo utilizado. No ocultar datos faltantes ni inventar valores para conservar v8.

Un botón «Calcular comparación» permite revisar un conjunto de cambios antes de ejecutar. El resultado muestra antes/después y soporte observado; no afirma que modificar una variable producirá esa mejora en campo. Ubicación puede elegirse sobre una zona visual, manteniendo conteo y lado del bateador como contexto.

La sección Técnica reúne validación, SHAP completo, catálogo de estadios, descargas extensas y documento. Las limitaciones que cambian la interpretación siguen junto al resultado correspondiente; no se ocultan todas en esa sección.

## Ejemplo de ficha usando resultados actuales

**pitcher_01050 — Revisar ubicación y contexto.** Calidad física 111.8 y rendimiento contextual estimado 101.6; 331 lanzamientos en 19 juegos. La diferencia sugiere qué revisar y no atribuye causalidad a comando. Siguiente paso: revisar video y distribución de ubicación por tipo/conteo. El intervalo del Pitching+ medio observado es aproximadamente 100.1–103.1; no es un intervalo del talento futuro.

Para pitcher_00408, con 48 lanzamientos en un juego, la primera conclusión sería «Reunir más datos». Para pitcher_00036, 529 lanzamientos en siete juegos y Pitching+ 104.0, «Priorizar revisión de scouting», acompañado de evidencia y límites.

## Orden recomendado de trabajo

1. Confirmar estado administrativo y acceso efectivo a la demo. Gestionar datos de estadio y explicitar cualquier requisito que no se pueda demostrar.
2. Unificar navegación y selección del pitcher; abrir en ficha; traducir etiquetas; reducir tablas y explicaciones técnicas iniciales.
3. Diferenciar ejemplos de observaciones, conservar contexto en simulación y añadir comparación antes/después sin sobreinterpretación causal.
4. Redactar acciones específicas por caso y ficha imprimible.
5. Con mapeo oficial, completar evaluación por parque, contraste de Harp Helú, perfiles y normalización sustentada. Si se busca simular cambio de movimiento entre entornos, necesita un modelo adicional validado.

Propuesta de prueba de uso, todavía no realizada: pedir a tres coaches que encuentren un candidato, expliquen qué significa 110, identifiquen una muestra insuficiente, comparen dos perfiles y exporten una ficha. Medir tiempo, errores y necesidad de ayuda. Como objetivo de diseño, la ficha debe entenderse en menos de un minuto y las tareas principales completarse sin explicación del equipo. Estos tiempos son metas, no resultados medidos.

## Comprobaciones de esta revisión

- Lectura directa de código, reportes, auditoría de estadios, métricas, recomendaciones y convocatoria vigente.
- Conteos de CSV, PDF de ocho páginas, hashes del manifiesto y de cada entrada del ZIP, inventario y CRC del ZIP: correctos.
- Comparación de las cinco entradas/módulos del dashboard con sus copias empaquetadas: coinciden.
- Doce pruebas de interfaz, explicaciones, análisis y vinculación de estadios terminaron en OK (`test_dashboard_stuff_plus_v8.py`, `test_dashboard_revision_v8.py`, `test_entrega_v8.py`, `test_estadios_v8.py`). Al finalizar apareció un error de permisos al limpiar un temporal; no fallaron las pruebas, pero esa limpieza queda pendiente.
- No se reentrenaron modelos ni se repitió la auditoría integral de entrenamiento. La revisión de usabilidad no certifica apariencia, accesibilidad o comprensión por usuarios reales.
