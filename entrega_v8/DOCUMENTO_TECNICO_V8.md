# Documento técnico v8 — entrega vigente

## 1. Resumen y uso deportivo

Objetivo: evaluar lanzamientos y repertorios con un sistema interpretable que permita al cuerpo técnico priorizar observaciones y comparar perfiles. V8 combina modelos CatBoost globales con especialistas por familia, y conserva las tareas anteriores cuando el cambio no supera selección.

La entrega contiene 135,604 scores derivados de 2026, agregados por pitcher y arsenal, tres casos de scouting, un simulador y análisis ajustados entre categorías de altitud. El paquete incluye predicciones identificadas por IDs anónimos, resultados agregados y código; excluye mediciones y outcomes originales por lanzamiento.

V8 mejora Brier en whiff (0.14%), whiff dado swing (2.19%) y bola en juego (0.83%) frente a v7. Las mejoras de probabilidades no se traducen en una mejora demostrada del valor de carreras físico: Stuff+, Location+ y Pitching+ conservaron sus modelos.

La pregunta operativa es qué pitcher merece revisión adicional, qué parte de su repertorio destaca y dónde la evidencia es insuficiente. Ningún ranking representa una orden automática de contratación. Salud, video, rol, calidad de oposición y costo no están modelados.

Todos los resultados de 2026 deben interpretarse como benchmark reutilizado. La auditoría adicional excluye pitchers de sus propios modelos, pero no convierte la temporada en una prueba históricamente intacta.

| Tarea | v7 error | v8 error | Ganancia |
|---|---|---|---|
| whiff | 0.097279 | 0.097139 | 0.14% |
| whiff_given_swing | 0.169068 | 0.165359 | 2.19% |
| ball_in_play | 0.146656 | 0.145445 | 0.83% |
| groundball_given_in_play | 0.237707 | 0.237707 | 0.00% |
| home_run_per_pitch | 0.006751 | 0.006751 | 0.00% |
| exit_speed_given_in_play | 15.295926 | 15.301194 | -0.07% |
| physical_control | 0.217639 | 0.217639 | 0.00% |

## 2. Datos, población y alcance

Origen: 635,002 lanzamientos LMB: 243,254 de 2024, 256,144 de 2025 y 135,604 de 2026. Los identificadores de lanzamiento permiten unir predicciones sin usar resultados como entradas. Los identificadores de pitcher sirven para agrupar y construir historia, no para memorizar jugadores como features.

Variables físicas: velocidad, spin, eje circular, release, extensión y movimiento. V6 añade proxies aerodinámicos; v8 añade ZoneSpeed, SpeedDrop y ZoneTime a los predictores seleccionados. Estas últimas son mediciones del trayecto, no exclusivamente del instante de release.

Disponemos de categorías No Altitude, Medium Altitude y Extreme Altitude. No disponemos de estadio, fecha exacta, secuencia verificable ni ocupación de bases. No se asigna Extreme Altitude a Harp Helú, no se construyen cortes mensuales ficticios ni se presenta RE24 completo.

Los agregados actuales contienen 550 filas de pitcher/temporada/referencia. La auditoría excluye 3272 filas sin identificador de pitcher del proceso de partición; esa exclusión se registra antes del ajuste.

Las tasas por contacto y swing solo se evalúan donde su condición se observa. Las predicciones condicionales sí pueden generarse para cualquier lanzamiento sin usar su resultado. El diccionario y las reglas de elegibilidad están en los scripts v5-v8.

## 3. Arquitectura, objetivos y escala

Stuff+ predice calidad física mediante el negativo de carreras esperadas con física e historia de arsenal. Location+ representa la diferencia predictiva entre el valor físico y el valor con ubicación, conteo y lado del bateador. Pitching+ incorpora además el contexto categórico de altitud. Las diferencias son predictivas, no una descomposición causal de command.

El target de carreras utiliza pesos fijos: bola +0.03, strike -0.05; resultados terminales como out -0.27, walk +0.30, single +0.47, double +0.78, triple +1.09 y HR +1.40. Es un proxy, no una matriz RE24 estimada de estados base-out. Se informa esta limitación en todos los usos deportivos.

Escala: 100 + 10 por el z-score del valor favorable. La media y desviación se guardan en una población histórica de referencia. No se recentra 2026 para forzar un promedio 100. Un 110 significa una desviación estándar sobre esa referencia, no diez por ciento menos carreras ni una garantía de nivel élite.

El arsenal usa diferenciales de velocidad, IVB, HB y release respecto a una recta primaria histórica, además del uso por tipo. La historia se limita a temporadas anteriores. No se infiere orden de lanzamientos desde identificadores ni se llama tunneling real a una simple distancia de release.

V8 acepta mezclas global/especialistas en whiff, whiff dado swing y bola en juego, y un global ampliado en EV. Las demás tareas conservan el padre. Si faltan mediciones válidas, la inferencia vuelve exactamente al respaldo anterior por fila.

## 4. Validación con pitchers no vistos

Auditoría adicional: partición reproducible por pitcher, semilla 910, aproximadamente 60% ajuste, 10% parada, 10% calibración y 20% prueba. Ajuste, parada y calibración usan solo 2024-2025. Prueba usa 2026 de pitchers excluidos de todas esas funciones. Se registran IDs y hashes.

Población de prueba: 26,536 lanzamientos de 105 pitchers. No se permite historial de arsenal para los pitchers de parada, calibración y prueba. Es un escenario cold start, más exigente que un pitcher con historia conocida.

Se reentrena la arquitectura seleccionada, no se evalúan los modelos desplegados sobre pitchers que ya conocieron. Los pesos de mezcla y métodos de calibración se congelan; los parámetros del calibrador se ajustan otra vez en pitchers de calibración. Las tareas contextuales se auditan con controles CatBoost de 250 iteraciones máximas, no como una reproducción exacta de todas las mezclas heredadas v5.

La tabla muestra AUC para clasificación y RMSE para regresión. Ganancia e intervalo comparan MSE/Brier contra una constante aprendida en fit. El bootstrap remuestrea pitchers, con 1,000 repeticiones. Las tareas de carreras también se comparan contra promedio por conteo.

Los pitchers son disjuntos, pero pueden compartir juegos: esta auditoría mide transferencia a pitchers no vistos, no independencia adicional de parque o juego. El diseño fue creado después de observar versiones anteriores; no se afirma confirmación futura independiente.

| Tarea | N | AUC/RMSE | Ganancia | IC 95% |
|---|---|---|---|---|
| whiff | 26536 | 0.647 | 2.40% | [1.66%, 3.19%] |
| whiff_given_swing | 12269 | 0.696 | 9.85% | [8.05%, 11.60%] |
| ball_in_play | 26536 | 0.612 | 1.88% | [1.65%, 2.12%] |
| groundball_given_in_play | 4602 | 0.618 | 4.30% | [3.08%, 5.54%] |
| home_run_per_pitch | 26536 | 0.599 | 0.08% | [0.04%, 0.14%] |
| exit_speed_given_in_play | 4555 | 15.169 | 1.09% | [0.41%, 1.70%] |
| physical_control | 26536 | 0.213 | 0.23% | [0.09%, 0.38%] |
| xrunvalue | 26536 | 0.208 | 4.53% | [3.96%, 5.17%] |
| environment_run_value | 26536 | 0.208 | 4.55% | [3.95%, 5.19%] |

## 5. Entorno: asociaciones y soporte

Se comparan categorías contra No Altitude dentro de celdas del mismo pitcher, año, tipo de pitch, lado del bateador y conteo. Cada celda necesita al menos tres observaciones por entorno; el peso es el mínimo de ambos tamaños. Se exigen cinco pitchers con solapamiento para emitir un contraste.

La diferencia es media de categoría menos No Altitude, ponderada sobre las celdas comparables. Los intervalos remuestrean pitchers completos 1,000 veces. La población es la que tiene soporte compartido, no toda la liga. Tasas se muestran como fracciones: 0.01 equivale a un punto porcentual.

Se analizan las tres temporadas como evidencia descriptiva, incluidas observaciones utilizadas en desarrollo. No es un resultado fuera de muestra. Los 96 contrastes son exploratorios y no tienen corrección por comparaciones múltiples; no se declaran hipótesis causales validadas.

La tabla resume Extreme Altitude. Diferencias de IVB y HB son firmadas, no cambios universales de magnitud de movimiento. Persisten posibles diferencias de dispositivo, forma específica, clima, bateadores y selección de uso. La coincidencia por tipo no elimina esos factores.

Un cambio de categoría en el simulador conserva la física observada y modifica únicamente el predictor contextual. No transporta trayectoria ni carry. Para comparar Harp Helú nominalmente y realizar park holdout hace falta un mapeo oficial de estadios.

| Resultado | Diferencia | IC 95% | Pitchers |
|---|---|---|---|
| is_whiff | -0.0095 | [-0.0134, -0.0058] | 681 |
| whiff_swing | -0.0248 | [-0.0356, -0.0134] | 456 |
| home_run | 0.0011 | [0.0004, 0.0020] | 681 |
| run_value_proxy | 0.0111 | [0.0088, 0.0133] | 681 |
| InducedVertBreak | -2.2925 | [-2.4400, -2.1376] | 681 |
| HB_normalized | -1.9305 | [-2.1126, -1.7482] | 681 |

## 6. Baselines, calibración y fronteras

El modelo físico dispone de menos contexto que el baseline por conteo. En los modelos de carreras vigentes, heredados de v5, el físico no supera ese baseline en 2026; los modelos con ubicación y entorno sí lo superan. Se evita presentar el resultado contextual como si fuera precisión física.

La tabla corresponde al modelo desplegado, no a la auditoría reentrenada de la página 4. Como las tres predicciones de carreras se conservaron hasta v8, las métricas se consolidan desde la evaluación original v5 sobre la misma temporada; se conserva su procedencia.

Brier evalúa el error probabilístico total; AUC evalúa ordenamiento y ECE la concordancia por bins. En v8 ECE de whiff dado swing empeora de 0.012782 a 0.021505 y de bola en juego de 0.007973 a 0.013189, pese a mejorar Brier y AUC. Se muestran ambas caras del resultado.

EV empeora de 15.295926 a 15.301194 mph de RMSE en el benchmark; el intervalo de diferencia incluye cero. No se revierte selectivamente usando 2026. El evento HR es raro; accuracy no sería una medida adecuada de utilidad.

La validación por parque sigue pendiente por ausencia de identificadores. Los intervalos no incorporan incertidumbre de entrenamiento ni corrigen reutilización de datos. La referencia histórica tampoco equivale a una normalización demostrada para cada estadio.

| Modelo vigente | RMSE | RMSE conteo | Ganancia vs conteo |
|---|---|---|---|
| stuff_run_value | 0.21764 | 0.21646 | -1.09% |
| xrunvalue | 0.21315 | 0.21646 | 3.03% |
| environment_run_value | 0.21308 | 0.21646 | 3.09% |

## 7. Casos, perfiles y uso del dashboard

Los casos son pitchers anonimizados reales, elegidos con reglas declaradas y usando scores predichos de 2026. Sirven para demostrar el flujo de revisión; no son descubrimientos confirmados de talento ni recomendaciones de contrato.

Revisar - pitcher_00036: 529 pitches en 7 juegos; Stuff+ 105.7, Pitching+ 104.0. Mayor Pitching+ regularizado entre muestras de al menos 300 pitches y cinco juegos.

Cautela - pitcher_01050: 331 pitches en 19 juegos; Stuff+ 111.8, Pitching+ 101.6. Mayor diferencia entre Stuff+ y Pitching+ entre muestras amplias: revisar ubicación y contexto.

Información insuficiente - pitcher_00408: 48 pitches en 1 juegos; Stuff+ 95.4, Pitching+ 99.2. Menos de 50 pitches; solicitar una muestra adicional antes de comparar talento.

El primer caso debe pasar a revisión de video y rol. En el segundo se debe revisar ubicación y contexto; la diferencia entre índices con referencias distintas no es una cantidad causal de carreras perdidas. En el tercero un solo juego no permite un intervalo entre juegos: se informa como no estimable, no como certeza perfecta.

El perfil físico descriptivo se extrae del 10% superior de Pitching+ dentro de tipo, mano y entorno, con al menos 100 pitches y tres pitchers. Se publican cuartiles de velocidad, spin, IVB, HB, altura y extensión. No es un óptimo causal: incluye selección por ubicación y por el propio modelo.

El mapa muestra medias por pitcher/tipo/entorno, con HB normalizado por mano. Las fichas incluyen atribuciones SHAP que reconstruyen exactamente el Stuff+ de los casos; explican el modelo, no efectos causales. El simulador compara tres escenarios con física fija y muestra soporte del tipo/mano; una advertencia señala escasez o velocidad fuera del rango de medias observado.

## 8. Reproducción y plan de decisión

Reproducción: instalar requirements-entrega.txt; ejecutar validar_pitchers_v8.py, analisis_operativo_v8.py, explicar_casos_v8.py y generar_paquete_v8.py. La auditoría no sobrescribe una ejecución iniciada. Abrir dashboard_stuff_plus.py con Streamlit. Los modelos desplegados v8 y sus hashes se mantienen intactos.

El manifiesto registra hashes y archivos. El ZIP incluye scripts, documentación, predicciones y resultados agregados; excluye mediciones y outcomes originales, listas de IDs de auditoría y modelos binarios. Los modelos completos quedan localmente para revisión autorizada. El README distingue la demo local del paquete compartible.

Secuencia de demo: explicar la calidad física; abrir una ficha; recorrer el mapa de movimiento; comparar escenarios de altitud; revisar tres casos; cerrar con la auditoría de pitchers y los límites de estadio. La decisión propuesta es priorizar revisión, no ejecutar una contratación.

Pendiente externo: mapeo de estadio por juego, fechas, orden de PA/pitches y ocupación de bases. Con ello se podrá estudiar transporte de forma, validación por parque y objetivos de carreras con estados completos. El análisis actual identifica categorías, no Harp Helú.

La convocatoria publicada solicita documento técnico de 6-10 páginas, scores, perfil, recomendaciones y simulador. La entrega anunciada es el 22 de octubre de 2026. El equipo debe completar integrantes y correos, verificar elegibilidad y preparar su envío. Este proceso no envía correos ni publica datos.

Fuentes: convocatoria ISAC Diablos Rojos (https://www.isac-app.com/competition-details/hackathon-diablos-rojos.html), consultada el 17/10/2026; diccionario de datos; reportes y protocolos locales v5-v8. Las afirmaciones empíricas de este documento provienen de los artefactos identificados en el manifiesto.
