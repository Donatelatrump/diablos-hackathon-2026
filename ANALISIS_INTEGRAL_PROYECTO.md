# Análisis integral del proyecto Stuff+

Fecha: 17 de octubre de 2026.

## Dictamen

El proyecto es un prototipo de investigación avanzado para evaluar lanzamientos de béisbol con CatBoost. Tiene datos, cuatro generaciones de entrenamiento, modelos serializados, métricas, scores, agregados y una interfaz Streamlit. Sin embargo, la versión actual no constituye todavía un sistema de evaluación confiable para decisiones de scouting: hay fallos de independencia de validación, duplicación de observaciones, componentes ausentes y diferencias entre el simulador y los modelos.

Esta revisión se basa en los archivos locales y consultas directas al Parquet. No se reentrenaron modelos, no se cambiaron resultados y no se verificó externamente la convocatoria. Las métricas citadas son resultados guardados, no una reproducción independiente del entrenamiento.

## 1. Qué contiene y cómo funciona

Flujo previsto: datos Trackman anonimizados → selección y transformación de variables → modelos por resultado → probabilidades/regresiones → índices Stuff+, Location+ y Pitching+ → agregados por pitcher y altitud → recomendaciones y dashboard.

| Componente | Estado observado |
|---|---|
| Datos | `stuff_model_df.parquet`, con copias en PKL y RDS; diccionario CSV |
| Entrenamiento inicial | `entrenar_stuff_plus.py`: siete tareas |
| v2 | Ocho tareas, métricas adicionales y baseline aproximado por conteo |
| v3 | Once tareas, arsenal relacional, holdout por altitud y entregables |
| v4 | Once tareas, splits rolling, ponderación de eventos raros e integración SHAP |
| Continuación v4 | `completar_v4.py`: reutiliza modelos existentes y completa faltantes |
| Enriquecimiento | Scripts v3/v4 unen scores con características físicas mediante PitchUID |
| Visualización | `dashboard_stuff_plus.py`: rankings y simulación heurística |
| Colab | Notebook que todavía ejecuta el entrenamiento inicial de siete tareas |
| Documentos | Informe técnico, recomendaciones operativas y revisión histórica |

Las once tareas v4 son whiff, whiff dado swing, bola en juego, contacto débil, contacto duro, strike cantado, chase, rodado dado bola en juego, jonrón por pitch, velocidad de salida y xRunValue.

Fortalezas: selección explícita de variables; IDs excluidos de la entrada directa; uso de condiciones para entrenar resultados de contacto; tratamiento circular de SpinAxis; validación temporal y por grupos; Brier, ECE y baselines; modelos CatBoost efectivamente cargables; normalización anual de Stuff+.

## 2. Inventario comprobado de datos y resultados

El origen tiene **635,002 lanzamientos únicos y 1,134 pitchers**:

| Temporada | Lanzamientos |
|---|---:|
| 2024 | 243,254 |
| 2025 | 256,144 |
| 2026 | 135,604 |

No se encontraron PitchUID duplicados en el origen.

| Archivo de scores | Filas | PitchUID únicos | Pitchers |
|---|---:|---:|---:|
| v3 | 575,015 | 458,367 | 1,082 |
| v4 | 1,095,336 | 493,170 | 1,095 |
| v4 enriquecido | 1,095,336 | 493,170 | 1,095 |

La duplicación v4 existe antes del enriquecimiento. Hay 89,434 pitches con una fila, 228,174 con dos, 152,694 con tres y 22,868 con cuatro. Los agregados actuales cuentan filas como si fueran lanzamientos independientes.

En v4 faltan 584,456 probabilidades de whiff dado swing, 902,474 predicciones de velocidad de salida y 900,631 probabilidades de rodado dado bola en juego. Solo **192,862 filas, aproximadamente 17.6%,** tienen simultáneamente esos tres componentes del Stuff+.

## 3. Hallazgos críticos

### A. La continuación v4 genera predicciones dentro de muestra bajo el nombre OOS

En `completar_v4.py`, `fit_remaining_models` entrena con el frame completo. Después, `generate_oos_scores` carga esos modelos finales y predice los subconjuntos de test sin reentrenar con el train de cada split. Los modelos han visto las filas evaluadas. Dividir las filas después de entrenar no produce validación fuera de muestra.

El entrenamiento principal v4 sí ajusta un modelo por split. Hay dos rutas con garantías distintas que escriben el mismo archivo. No existe un manifiesto suficiente para atribuir inequívocamente cada artefacto a una ejecución. El patrón de nulos observado es compatible con la ruta de continuación, que predice solamente las filas que cumplen la condición del target.

Acción: separar modelos finales y modelos de validación; generar predicciones OOF con ajuste exclusivo sobre train y guardar procedencia por fila.

### B. Se mezclan splits superpuestos y se pierde su identidad

`make_splits` v4 incluye rolling 2024→2025 y season_holdout_2025 con el mismo train/test; ocurre lo mismo para 2026. Luego concatena predicciones temporales y por altitud sin conservar una columna de split. La continuación incluye además el holdout por pitcher.

Esto duplica trabajo y pondera varias veces algunos pitches al normalizar scores y construir rankings. No se resuelve descartando duplicados arbitrariamente: las predicciones pueden proceder de modelos y poblaciones de entrenamiento diferentes.

Acción: conservar tablas separadas por experimento y definir una única política de predicción por pitch para el producto final.

### C. xRunValue v4 aprende un target agregado con información del test

`load_data` construye un valor aproximado por outcome y después lo reemplaza por la media de todos los datos para cada combinación conteo/outs, antes de crear los splits (`entrenar_stuff_plus_v4.py:323–332`). El target de test depende así de sus propios outcomes y de otras temporadas.

El modelo incluye Balls y Strikes, que forman parte de la clave de esa media. Por ello, el R² de 0.632 no es evidencia de predicción de valor individual por lanzamiento: mide en parte la reconstrucción de una tabla suavizada definida globalmente.

Tampoco hay una implementación real de los 24 estados base-out: `bases_state` devuelve únicamente Outs, sin ocupación de bases. `base_on_balls` se consulta pero no se selecciona al cargar datos, por lo que esa rama no identifica las bases por bolas. Asignar -0.30 a cualquier whiff y cero a gran parte del contacto es una aproximación que requiere justificación.

Acción: definir un target observado defendible, estimar tablas y baselines exclusivamente en train, y evaluar contra ese target en test. Documentar lo que no puede calcularse sin ocupación de bases.

### D. Los componentes condicionales no deben existir solo cuando ocurre el resultado

En la continuación, whiff dado swing se predice únicamente para swings; velocidad de salida y rodados se predicen únicamente para contacto observado. Esas condiciones son apropiadas para seleccionar datos de entrenamiento y evaluación del target, pero el score esperado de un pitch requiere aplicar los modelos condicionales a todos los pitches elegibles para inferencia.

El compuesto convierte componentes ausentes en z=0. Así, la disponibilidad del resultado observado altera la puntuación y disfraza la ausencia de predicciones como rendimiento promedio.

Acción: aplicar los modelos condicionales a todas las filas de inferencia y rechazar scores incompletos, sin imputar silenciosamente el promedio.

## 4. Otros problemas metodológicos importantes

1. **Arsenal con información futura.** Las medias de fastball y frecuencias de uso se calculan con todas las temporadas antes del split. Para validar predicción futura se necesitan perfiles construidos con historia anterior o con una política explícita de observación previa. El holdout de pitchers tampoco representa un escenario sin información previa del pitcher si sus estadísticas de test ya están disponibles.
2. **Secuencia no demostrada.** Ordenar por IDs anónimos de juego no garantiza cronología ni orden de pitches. `shift(1)` por pitcher cruza juegos. Sin una variable de orden fiable, `prev_pitch_type` no debe presentarse como secuenciación validada.
3. **Fastball primaria distinta de lo descrito.** Se promedian Four-Seam y Sinker juntos; no se selecciona el tipo más usado como afirma el documento.
4. **Pesos aprendidos inactivos.** El frame entregado a `add_provisional_scores` no contiene las probabilidades que busca `available_cols`. La regresión no se ejecuta en la ruta normal y el JSON guardado contiene pesos 1.0. Además, la ruta de salida está fijada a `stuff_plus_output_v4`, ignorando `--salida`. Si se habilita el aprendizaje, habrá que revisar también el signo: menor run value debe equivaler a mejor calidad.
5. **Stuff+ v4 incluye ubicación indirectamente.** Su componente de velocidad de salida utiliza PlateLocHeight, PlateLocSide, Balls, Strikes y las banderas de zona. Esto contradice la separación estricta de calidad física y ubicación que se comunica al usuario.
6. **Pitching+ no tiene desviación 10.** Se promedian dos índices ya normalizados sin volver a normalizar. Se midieron desviaciones anuales aproximadamente 7.26–7.29; la documentación afirma 10 para los tres índices.
7. **La normalización depende del conjunto evaluado.** Los parámetros anuales se recalculan sobre los scores exportados, que contienen repeticiones y selecciones de holdout. No se conserva una referencia de liga reutilizable para puntuar un pitch nuevo.
8. **Altitud no identifica estadio.** El origen contiene buckets de altitud, sin identificador de parque. El mapeo a Harp Helú es un supuesto local. El denominado park holdout es un holdout por bucket, no una validación identificable por estadio.
9. **Comparación observacional presentada como efecto.** Diferencias de scores medios por altitud pueden reflejar pitchers, tipos de pitch, temporadas y selección de muestra. No prueban el efecto de trasladar el mismo lanzamiento a CDMX. El Stuff+ físico no incorpora altitud directamente en la mayoría de sus tareas.
10. **Perfil ideal confunde composición y ventaja.** Que haya muchos sliders entre el top 10% no demuestra que mejoren más por altitud. Se necesitan tasas relativas por tipo, comparación con su frecuencia base y análisis con incertidumbre. Un promedio físico de todos los tipos mezclados no es un objetivo universal de scouting.
11. **Targets aproximados.** Todo rodado con ExitSpeed conocido puede etiquetarse como contacto débil incluso si sale muy fuerte; contacto duro exige además un rango estrecho de ángulo. Estos nombres requieren definiciones explícitas y etiquetas faltantes cuando no se observa Angle.

`DIRECTION_FEATURES` incluye Direction, descrita por el diccionario como resultado del batazo. Actualmente esa lista no se utiliza en TASKS: no se encontró fuga activa por esa variable, pero no debe activarse como predictor previo al lanzamiento.

## 5. Qué dicen realmente las métricas guardadas

v4, holdout temporal 2026; el experimento rolling equivalente repite los mismos valores:

| Tarea | AUC | Brier skill |
|---|---:|---:|
| Whiff | 0.623 | +0.0176 |
| Whiff dado swing | 0.633 | +0.0383 |
| Bola en juego | 0.545 | +0.0036 |
| Contacto débil | 0.569 | +0.0110 |
| Contacto duro | 0.549 | **-1.5475** |
| Strike cantado | 0.857 | +0.2477 |
| Chase | 0.903 | +0.3884 |
| Rodado dado bola en juego | 0.624 | +0.0468 |
| Jonrón por pitch | 0.573 | **-0.6045** |

Brier skill negativo significa que el error probabilístico supera al baseline constante calculado con train. Para contacto duro es aproximadamente 2.55 veces el error del baseline; para jonrón, 1.60 veces. El peso positivo fijo de 10 coincide con una degradación considerable de calibración frente a v3; debe investigarse con comparación controlada y calibración independiente.

La velocidad de salida obtiene RMSE 14.389 mph y R² 0.126. xRunValue obtiene R² 0.632, sujeto al problema de target explicado arriba. Location tiene la señal más fuerte; la predicción física muestra mejoras modestas. Las AUC superiores de la versión inicial no son directamente comparables porque cambió la información de entrada.

`rmse_skill` calcula mejora relativa del error cuadrático medio, no del RMSE; debe renombrarse o cambiar su fórmula. Las métricas no incorporan intervalos de confianza ni validación del índice compuesto frente a resultados independientes.

## 6. Dashboard, ejecución y reproducibilidad

- `estimar_stuff_plus` usa coeficientes, bonificaciones y penalización de altitud escritos a mano. No carga modelos CatBoost. Sus resultados no son los del entrenamiento.
- La función acepta altura/lado de release y manos de pitcher/bateador, pero no utiliza esos argumentos en el cálculo.
- El selector de entorno calcula `altitud_m`, pero las métricas principales muestran siempre `resultado_cdmx`.
- `SALIDA` apunta a v3, aunque primero busca nombres de scores v4 dentro de esa carpeta. Puede mostrar rankings y perfiles antiguos.
- El dashboard permite que ubicación y conteo modifiquen Stuff+ y que la altitud altere Location+, pese a las definiciones que muestra.
- `requirements-hackathon.txt` omite Streamlit, Plotly, un motor Parquet para pandas y SHAP. En la `.venv` revisada faltan Streamlit, PyArrow y SHAP. Pandas necesita PyArrow o fastparquet para estas lecturas; DuckDB ya disponible podría unificar ese acceso.
- SHAP se escribe con el mismo nombre de archivo para cada tarea, sobrescribiendo resultados anteriores, tanto en importancia general como por altitud.
- Los once modelos v4 cargan correctamente, pero tres tienen 80 árboles y ocho tienen 40. Reutilizar archivos existentes sin comprobar configuración permite mezclar ejecuciones; no demuestra por sí solo que los modelos estén corruptos.
- No hay README de ejecución, pruebas automatizadas del pipeline ni configuración central de versión. Las dependencias tienen mínimos abiertos, sin un entorno fijado.
- La documentación técnica describe v3 y declara que está lista para entrega; la revisión histórica refleja una etapa anterior. Algunos valores publicados tampoco coinciden con las métricas v3 guardadas: por ejemplo, AUC de strike cantado 0.871 frente a 0.855 observado.
- Las recomendaciones de +2.7 puntos por altitud no coinciden con el resumen v4 actual, cuya diferencia es aproximadamente +0.198 puntos. Esa diferencia v4 también está afectada por los problemas de agregación y no debe interpretarse como efecto físico.
- Git LFS está configurado para datos y modelos. El intento de `git status` falló por un error de creación de signal pipe del proceso LFS; no se pudo certificar el estado del árbol de trabajo. No se modificó Git para eludirlo.

## 7. Orden recomendado de trabajo

1. **Integridad:** bloquear publicación de scores incompletos, conservar split/modelo/configuración y separar predicciones de evaluación de las finales. Definir unicidad por PitchUID para la tabla operativa.
2. **Validación:** eliminar splits temporales repetidos y entrenar transformaciones y perfiles únicamente con información permitida. Corregir la ruta de continuación.
3. **Objetivo:** rehacer xRunValue y el baseline por conteo sin utilizar outcomes de test. Mantener documentadas las aproximaciones inevitables.
4. **Índices:** generar todos los componentes por pitch, separar variables físicas y ubicación, fijar referencia de normalización y evaluar el compuesto. Aprender pesos con predicciones OOF y validación independiente si se conserva esa opción.
5. **Probabilidades:** comparar ponderación de clases frente a modelos sin ponderar; calibrar con datos separados y conservar solo mejoras demostradas.
6. **Producto:** conectar el dashboard a una única ruta de inferencia real, sincronizar versión y selector de entorno, completar dependencias y proporcionar instrucciones reproducibles.
7. **Comunicación:** rehacer rankings y perfiles con mínimos de muestra e incertidumbre; corregir afirmaciones sobre estadios, causalidad, escala y desempeño; generar tablas del documento directamente desde los artefactos finales.

Criterios mínimos de aceptación: una predicción operativa por PitchUID; componentes completos; train/test independientes con procedencia auditable; baseline sin información del test; scores invariantes a ubicación si se anuncian como Stuff+ físico; coincidencia entre inferencia del dashboard y del pipeline; documentación consistente con una ejecución identificada.

## 8. Comprobaciones realizadas y límites

Se revisaron los nueve scripts Python, el notebook, los documentos, el diccionario, requisitos y configuración Git/LFS. Se analizaron las métricas de las cinco carpetas de resultados, se consultaron origen y scores con DuckDB y se cargaron los once modelos v4. Los nueve scripts pasaron análisis sintáctico con AST.

No se ejecutó entrenamiento completo ni la interfaz Streamlit. La disponibilidad de un módulo se comprobó mediante descubrimiento de imports; la carga efectiva de CatBoost y DuckDB sí se ejercitó. No se abrieron los archivos PKL/RDS: para esta revisión se utilizó el Parquet, que es la entrada efectiva de los entrenamientos. No se certificó equivalencia entre esos tres formatos.
