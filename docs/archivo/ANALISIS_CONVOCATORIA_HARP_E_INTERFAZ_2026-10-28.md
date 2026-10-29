# Revisión de convocatoria, Harp Helú e interfaz

Fecha: 28 de octubre de 2026. Versión revisada: dashboard_stuff_plus.py y modelo stuff_plus_output_v9_estadios, con su complemento multiobjetivo.

## Dictamen

La entrega es funcional y tiene evidencia técnica relevante, pero el cumplimiento científico/deportivo sigue siendo parcial. Los cinco productos están representados; eso no implica que todas sus preguntas estén resueltas. La brecha principal es la identificación de una ventaja específica de perfiles y arsenales en Harp Helú. La segunda es convertir los resultados en un recorrido comprensible para el coach.

La interfaz funciona en las comprobaciones realizadas, pero obliga al usuario a reconciliar selecciones independientes y cuatro índices. El tutorial y los textos añadidos ayudan, aunque no resuelven esa estructura.

Esta revisión sustituye las conclusiones que dependían de carencias ya corregidas: ya hay mapeo inferido de estadios, auditorías por pitcher y parque, probabilidad de out al cerrar el turno, complemento integral, PDF actualizado y modelos incluidos en el ZIP.

## Fuente y alcance

Se consultó la [convocatoria oficial](https://www.isac-app.com/competition-details/hackathon-diablos-rojos.html) y se contrastó con el HTML archivado. Se revisaron el código, los modelos y metadatos locales, métricas de las tres auditorías, deltas por perfil, recomendaciones, metodología del complemento, las nueve páginas extraídas del PDF y el ZIP.

La convocatoria pide scores y agregados, perfiles para Diablos, recomendaciones, simulador con contraste Harp/nivel del mar y documento de 6–10 páginas. Sus cuatro bloques de evaluación pesan lo mismo: calidad predictiva, robustez, integración de arsenal/altitud y utilidad deportiva. La comparación debe servir para distinguir perfiles y sustentar decisiones, además de presentar dos columnas de resultados.

La revisión funcional usa Streamlit AppTest. No hubo navegador disponible para inspeccionar composición visual, móvil, contraste o accesibilidad; tampoco hubo una prueba con coaches. No se reentrenó ni se reprodujo toda la auditoría de exclusiones sobre el dataset enriquecido. Se distingue evidencia archivada de comprobaciones ejecutadas en esta revisión.

## Matriz de cumplimiento

| Elemento | Dictamen | Evidencia y límite |
|---|---|---|
| Scores por lanzamiento, pitcher y arsenal | Cumple disponibilidad | Hay scores derivados y agregados de evaluación 2026, con escenarios Harp. No equivalen a una puntuación publicada de las tres temporadas completas. |
| Comparación Harp frente a otros parques | Parcial | El simulador usa estadios nominales y hay deltas por tipo/mano con soporte e intervalos. El Pitching+ de carreras conserva delta cero. |
| Perfil físico ideal para Diablos | Parcial | Hay rangos del grupo con mayor Stuff+ físico. No se demuestra que sean el óptimo específico de Harp ni una mezcla óptima de arsenal. |
| Recomendaciones operativas | Parcial | Hay criterios de revisión y casos. Falta una conclusión validada sobre quién gana/pierde valor en Harp que permita priorizar candidatos con esa razón. |
| Simulador | Funcional; interpretación parcial | Inferencia real, comparación y mapa disponibles. No calcula cómo cambiaría el movimiento del lanzamiento al trasladarlo físicamente. |
| Mapa de movimiento | Disponible; presentación mejorable | Muestra medias por pitcher/tipo/altitud. No destaca de entrada los perfiles más y menos efectivos ni conserva una selección única con las otras vistas. |
| Documento técnico | Cumple formato y cobertura amplia | Nueve páginas; describe modelo actual, pruebas, escalas y límites. No elimina las brechas científicas que él mismo reconoce. |
| Validación fuera de muestra | Evidencia disponible con límites | Métricas de temporada, pitchers reservados y Harp excluido de desarrollo. Un parque y una temporada de prueba no certifican generalización a todos los parques o temporadas. |
| Escala y múltiples objetivos | Parcial respecto a una interpretación única | Existen escala fija, escala retrospectiva por temporada/estadio e índice integral. Hay que distinguir sus usos y cuál representa la evaluación final del reto. |
| Entrega operativa | Paquete íntegro; administración sin verificar | ZIP con modelos, scripts y resultados. El arranque requiere Python y conexión para instalar dependencias. No se comprobó envío, recepción ni elegibilidad. |

## Qué demuestra realmente la comparación de Harp

Hay dos preguntas diferentes que conviene mostrar explícitamente:

1. **Con las mismas mediciones físicas, ¿qué predice el modelo si cambia el estadio?** Es la comparación actual. Conserva movimiento, velocidad, ubicación y arsenal; cambia el contexto de parque. Ofrece un contraste predictivo condicionado en esas mediciones.
2. **Si trasladamos al pitcher a Harp, ¿cómo cambiarán el movimiento y su efectividad?** No está resuelta por ese contraste. Necesita evidencia de cambios de forma entre entornos, controles apropiados o un modelo adicional validado.

Mantener el Stuff+ físico constante cuando solo cambia el estadio es coherente con su definición de calidad física separada. No es por sí mismo un fallo. La brecha está en que también permanece constante el Pitching+ de carreras: las capas de arsenal y entorno no confirmaron mejora adicional y heredan la predicción de ubicación. Eso es una decisión estadística defendible, pero no demuestra el valor diferencial por altitud que interesa al club.

El índice integral incorpora ocho señales estandarizadas con pesos iguales prefijados. Puede variar entre parques aun cuando Pitching+ no varíe. No se ha demostrado que ese índice mejore la predicción de carreras o las decisiones deportivas. Debe presentarse como complemento y evitar que el usuario lo confunda con otra versión intercambiable de Stuff+.

La referencia del informe por perfil es el promedio equiponderado de Veracruz, Campeche y Cancún; el simulador abre con Harp, Veracruz y Campeche. Ambos contrastes son válidos para explorar, pero no son exactamente la misma comparación. La pantalla debería identificar la referencia antes de mostrar diferencias.

Los deltas agrupan principalmente por tipo y mano. No bastan para afirmar que se ha aislado el efecto para cada forma de lanzamiento: dos sliders del mismo brazo pueden tener formas muy distintas. Los intervalos por juegos mantienen fijo el modelo y no incluyen toda la incertidumbre del entrenamiento.

## Evidencia numérica y consecuencias

| Prueba | Lanzamientos | RMSE combinado | Reducción MSE frente a promedio por conteo |
|---|---:|---:|---:|
| Temporada 2026 | 135,604 | 0.213269 | 2.92% |
| Pitchers reservados | 25,426 | 0.211864 | 2.98% |
| Harp excluido del desarrollo | 6,005 | 0.227901 | 2.78% |

Estos resultados aportan evidencia de utilidad predictiva del combinado. No permiten atribuir su mejora al estadio: en la ejecución temporal, la ganancia adicional de arsenal y entorno es cero por herencia.

El físico tiene RMSE 0.217595 frente a 0.216451 del baseline por conteo: empeora aproximadamente 1.06% en MSE frente a ese control, aunque mejora frente a la media global. El baseline dispone de contexto adicional; hay que explicar esa asimetría y evitar presentar la mejora del combinado como si fuera del físico.

En Harp, HR predicho medio es 0.695 por 100 lanzamientos frente a 0.866 observado: una diferencia de 0.171 puntos porcentuales. Los deltas de HR entre escenarios por tipo/mano son pequeños, aproximadamente de −0.013 a −0.028 por 100 lanzamientos. El desfase medio no es un intervalo de incertidumbre del delta, pero sí impide una lectura convincente de esas pequeñas diferencias como protección real ante el jonrón.

La probabilidad de out al cierre tiene auditorías adicionales: reducción Brier frente a conteo de 2.67%, 2.65% y 2.68% en temporada/pitcher/parque. Su target es al menos un out en la jugada terminal, no necesariamente bateador retirado. Whiff usa swing y fallo; la convocatoria incluye foul en su descripción. Son diferencias semánticas que deben permanecer documentadas.

La escala retrospectiva centrada por temporada/parque describe la cohorte evaluada; el simulador usa referencia fija de calibración. Recentrar cada parque en 100 no demuestra un efecto de altitud y puede ocultar diferencias de nivel. Deben compararse escenarios con una referencia común y mostrarse aparte las posiciones relativas dentro de cada cohorte.

## Por qué la interfaz resulta confusa

Hallazgos comprobados en código y ejecución:

| Problema | Lo que puede interpretar el usuario | Corrección propuesta |
|---|---|---|
| “Comparar un lanzamiento” abre primero una pestaña de perfiles agregados | No sabe si está revisando un pitcher, un perfil de liga o una simulación | Abrir directamente en comparación; separar exploración de perfiles. |
| Tipo/mano se seleccionan en perfiles y otra vez en simulación | Cree que cambiar una selección actualiza ambas | Una selección compartida o una acción explícita “Usar este perfil en el simulador”. |
| Arsenal histórico y pitcher del mapa son independientes | Cree que todos los resultados pertenecen al mismo jugador | Una selección persistente de pitcher para ficha, mapa y repertorio. |
| Elegir historial no carga sus mediciones físicas | Interpreta un perfil típico como lanzamiento observado de ese pitcher | Identificar “ejemplo con medianas” y “historial usado”; ofrecer observación real solo cuando esté disponible. |
| Cuatro índices y una probabilidad por estadio | No sabe cuál debe guiar la comparación | Resumen con resultado principal, delta e interpretación; índices secundarios desplegables. |
| 14 campos numéricos y nueve selectores en el recorrido completo | Tiene que entender el sistema antes de obtener una respuesta | Pocos controles iniciales, contexto esencial visible y mediciones adicionales agrupadas. |
| Ubicación, conteo y bateador quedan bajo “avanzado opcional” | Supone que no afectan materialmente al resultado | Mostrar su valor activo siempre; son contexto del resultado aunque se conserven predeterminados. |
| Predeterminados por orden alfabético | Puede tomar el cambio zurdo inicial como recomendación | Mostrar “Ejemplo de demostración” y una elección deportiva deliberada. |
| Tres estadios seleccionados inicialmente | Cuesta identificar la comparación principal | Harp fijo y un rival a nivel del mar; más parques en una opción secundaria. |
| Puntuaciones repetidas, probabilidades e información extensa | Cuesta encontrar qué cambió | Tabla de diferencias Harp menos referencia con unidades y dirección favorable por resultado. |
| Cambios calculados automáticamente | No está claro cuándo la comparación está lista | Formulario con “Comparar en Harp” y resumen de datos utilizados. |

El ejemplo inicial confirmado muestra Stuff+ 97.5 y Pitching+ 99.3 en los tres parques; índice integral 90.5, 92.2 y 92.9. Ese patrón necesita una explicación junto al resultado. Añadir un tutorial sin cambiar la jerarquía obliga a aprender más controles para entender una tarea que debería ser directa.

## Recorrido recomendado

**Comparar en Harp → elegir origen → revisar contexto → calcular → entender diferencia.**

Primera pantalla: pregunta “¿Cómo se evalúa este lanzamiento en Harp Helú frente a Veracruz?”. Harp queda fijo; el otro estadio es una selección. Elegir entre introducir mediciones y usar un ejemplo identificado. Solo ofrecer “lanzamiento observado” cuando se disponga de una observación verificable.

Mostrar tipo, mano, velocidad, movimiento vertical/horizontal y giro. Debajo, un resumen visible de ubicación, conteo, bateador e historial. Permitir editarlos sin mezclar datos de otro pitcher silenciosamente. Conservar los valores activos en el resultado y la descarga.

Resultado: dos columnas comparables, diferencia explícita y una conclusión concreta. Si Pitching+ no cambia, decir “El modelo no detectó una mejora adicional de carreras por estadio”; debajo, mostrar qué probabilidades sí cambian y su denominador. La calidad física se puede explicar una sola vez con indicación de que se conserva entre escenarios.

Navegación propuesta: **Comparar en Harp**, **Revisar un pitcher**, **Perfiles para scouting**, **Evidencia y entrega**. Cada pantalla debe responder una tarea. Versiones históricas, selección técnica de experimentos y métricas extensas quedan en evidencia.

Esto es una propuesta de reorganización, no un rediseño implementado en esta revisión.

## Prioridades antes de presentar

1. Simplificar comparación y selecciones; hacer visibles procedencia, contexto y referencia. Es la mejora de uso más inmediata.
2. Explicitar el resultado nulo de Pitching+ y decidir cómo se relacionan combinado de carreras e índice multiobjetivo. Validar el complemento contra un objetivo deportivo antes de usarlo para ordenar contrataciones.
3. Profundizar contraste por forma/arsenal con soporte, calibración e incertidumbre; estudiar cambios de movimiento entre parques sin imponer porcentajes de MLB ni forzar una mejora del modelo.
4. Reformular “perfil ideal” como “perfil de referencia para revisión” mientras no se demuestre una ventaja específica en Harp. El reto no exige fingir que sus hipótesis sean verdaderas.
5. Probar el recorrido con personas: comparar un lanzamiento, explicar 110, reconocer muestra insuficiente y exportar. Registrar errores y comprensión; una ejecución sin excepciones no valida usabilidad.
6. Confirmar envío y acceso del jurado. La página consultada mantiene 22 de octubre como entrega; no hay evidencia revisada que confirme envío o prórroga. El análisis no certifica esos pasos.

## Comprobaciones ejecutadas

- Consulta de convocatoria vigente y lectura del HTML local.
- Lectura de métricas, decisiones congeladas y tablas de deltas; extracción del texto completo del PDF: nueve páginas.
- ZIP: CRC correcto, 128 archivos declarados, hashes internos correctos y 16 modelos CBM. Los cuatro módulos de interfaz comparados coinciden en texto; una diferencia binaria en perfiles corresponde a saltos de línea.
- AppTest: inicio y simulador sin excepciones de la aplicación; inventario de selecciones, pestañas, 14 entradas numéricas, métricas y aviso de calibración HR.
- El proceso AppTest emitió un error de permisos al limpiar su directorio temporal después de producir los resultados. Esa limpieza no se considera validada.
- No se modificaron modelos ni interfaz, no se envió correo y no se publicó la entrega.
