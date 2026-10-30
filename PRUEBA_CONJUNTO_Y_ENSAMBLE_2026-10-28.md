# Prueba de modelo conjunto y ensamble

## Qué se probó

Se implementaron las dos primeras propuestas de la revisión de los otros equipos, sin copiar modelos ni pesos externos:

1. Una distribución conjunta de seis resultados: bola, strike cantado, fallo, foul, bola en juego y pelotazo. Se derivan swing y fallo dado swing; se añaden cabezas de jonrón dado bola en juego, contacto débil/medio/duro dado contacto medido y valor del contacto.
2. Un clasificador LightGBM de fallo dado swing y combinaciones de probabilidades con el CatBoost congelado, con pesos LightGBM 0.25, 0.50, 0.75 y 1.00. Peso 1.00 representa LightGBM solo, no un ensamble.

El objetivo y denominador de cada comparación binaria se conserva. Para carreras, el modelo conjunto usa el **mismo proxy observado v9**: combina las probabilidades con valores por evento/conteo aprendidos en fit y una regresión del contacto. No se compara el RMSE de ese proxy con el objetivo experimental distinto de transiciones por conteo.

## Protocolo

Solo desarrollo 2024–2025, particiones por juegos de la ejecución v9, semilla 904, máximo 400 árboles y parada temprana de 35. La historia procede de juegos fit de temporadas anteriores. Los calibradores se ajustan solo en calibration. No se usaron etiquetas de 2026 para selección ni se modificaron sus salidas guardadas.

Se utilizan los 37 predictores ya existentes del bloque contextual: no se añaden ángulos, clima, historial reciente ni variables nuevas de la revisión anterior. Las clases desconocidas se excluyen con su conteo registrado; pelotazo permanece separado de bola. Los resultados de contacto solo evalúan su denominador válido.

El primer intento multiclase con CatBoost se interrumpió por costo de cómputo durante su primer ajuste, antes de producir resultados reservados del candidato. Se conservan su protocolo y código en `joint_ensemble_output_2026_10_28/`, con `interrupcion.json`; no se registra como prueba de mala precisión. La ejecución completada del modelo conjunto usa LightGBM y está en `joint_lgb_output_2026_10_28/`. Por ello cambian **familia y arquitectura** respecto al control CatBoost, no solo la arquitectura.

Calibración del modelo conjunto: temperatura multiclase para eventos y contacto, sigmoide cuando hay soporte para jonrón condicionado, y contracción para valor del contacto. Estas transformaciones conservan la distribución conjunta. No se ajustaron pesos inversos a la frecuencia de las clases para aparentar mejores probabilidades de eventos raros.

El ensamble usa LightGBM 4.7.0 con profundidad máxima 6, 31 hojas, mínimo 300 observaciones por hoja, regularización L2 20 y muestreo prefijado. Los niveles categóricos se aprenden en fit; una categoría desconocida en evaluación no entra al vocabulario de entrenamiento. Las probabilidades LightGBM se calibran en calibration y el peso se elige una vez en tune. La partición histórica confirmation puede rechazarlo, sin escoger después otro peso.

Para un ganador de ensamble que supere el criterio de desarrollo, el script ejecuta además comprobaciones temporal (2024 → 2025), pitchers excluidos y Harp excluido. En ellas se reajustan ambos modelos, se reconstruye la historia sin los grupos excluidos y se conserva el peso elegido. El criterio requiere mejora relativa de Brier de al menos 0.1%, intervalo por juegos favorable, log loss sin degradación relevante y ausencia de degradación anual mayor a 0.1%.

Las particiones y temporadas ya se inspeccionaron antes. Estos son experimentos retrospectivos, no una nueva prueba prospectiva independiente. Los artefactos experimentales no se activan automáticamente en la página.

## Qué comparaciones permiten concluir

- Brier, log loss binario, AUC y calibración se comparan con el modelo congelado en **las mismas filas y etiquetas de cada tarea**. Los tamaños de muestra de tareas condicionales difieren.
- El log loss multiclase se compara contra frecuencias por conteo aprendidas en fit. El control de clasificadores independientes no define una distribución completa de seis clases, por lo que no se le inventa un log loss conjunto.
- El control de strike cantado usa 28 variables y el conjunto usa la unión contextual de 37. Una mejora de esa cabeza no demostraría que la arquitectura sea su única causa.
- El control de carreras conserva la capa de ubicación seleccionada; el valor esperado conjunto usa los 37 predictores. Se mantiene el mismo target, pero tampoco es una ablación estricta de una sola diferencia para esa salida.
- Una mezcla que mejore fallo dado swing no resuelve por sí sola la coherencia de las demás cabezas independientes.

## Evidencia y reproducción

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-precision-experiments.txt
.venv/Scripts/python.exe -m unittest test_coherent_events -q
.venv/Scripts/python.exe probar_conjunto_lightgbm.py --output joint_lgb_otra_ejecucion
.venv/Scripts/python.exe probar_ensamble_condicional.py --output ensemble_otra_ejecucion
.venv/Scripts/python.exe auditar_ensamble_condicional.py --output ensemble_otra_ejecucion
```

La ejecución se niega a sobrescribir una carpeta existente. Los resultados finales del conjunto están en `joint_lgb_output_2026_10_28/`; los del ensamble y sus auditorías, en `ensemble_screen_output_2026_10_28/`. Los directorios con modelos están excluidos de Git. No se exportan filas de datos de competencia a terceros.

El ensamble se ejecutó por separado mientras entrenaba el conjunto. Conserva los swings con etiqueta `is_whiff` válida, incluidos dos con `PitchCall=Undefined` en todo el desarrollo; la taxonomía conjunta excluye los cinco `Undefined` porque no puede asignarles un evento. No se mezclan las dos ejecuciones como una sola validación. El ensamble conserva el denominador de su control binario original.

Las pruebas de `coherent_events.py` cubren 1,000 distribuciones aleatorias, las cuatro restricciones auditadas, ausencia de división no finita cuando no hay swings, separación de HBP, rechazo de probabilidades inválidas, conservación de sumas durante calibración, valor esperado del mismo target y vocabulario categórico de fit.

Referencias técnicas: [LightGBM: clasificador y calibración de probabilidades](https://lightgbm.readthedocs.io/en/stable/pythonapi/lightgbm.LGBMClassifier.html). Las ideas de los equipos y sus límites están en `REVISION_RIVALES_PRECISION_2026-10-28.md`.

## Resultado del modelo conjunto

Comprobación sobre **48,963 lanzamientos de 168 juegos** de desarrollo. Las tareas condicionales usan sus propias filas elegibles. Reducción relativa del error: positivo favorece al candidato; negativo indica degradación.

| Salida | Reducción de Brier o MSE | Intervalo 95% | Criterio |
|---|---:|---:|---|
| Fallo por lanzamiento | +0.5206% | +0.2801% a +0.7707% | Superado |
| Fallo dado swing | +0.0449% | −0.2713% a +0.3459% | No superado |
| Bola en juego | −0.0867% | −0.2928% a +0.1223% | No superado |
| Strike cantado | +0.4712% | +0.1534% a +0.7750% | Superado, con límite de comparación de features |
| Jonrón por lanzamiento | −0.0203% | −0.1683% a +0.1262% | No superado |
| Contacto débil dado contacto medido | −1.1321% | −1.5580% a −0.6804% | No superado |
| Contacto duro dado contacto medido | −0.7264% | −1.0613% a −0.4101% | No superado |
| Carreras, mismo proxy v9 | +0.4973% de MSE | +0.3164% a +0.6754% | Superado, con límite de comparación de features |

La mejora de 0.4973% en carreras es sobre **error cuadrático**, no una reducción de carreras permitidas ni una mejora porcentual equivalente en RMSE. El RMSE pasa aproximadamente de 0.21462 a 0.21409 en esta muestra.

El log loss de seis clases es **1.02826**, frente a **1.47024** de las frecuencias por conteo. Esta comparación no es contra un log loss multiclase del modelo anterior, que no existe como distribución conjunta.

La diferencia de calibración por diez intervalos de probabilidad (ECE, menor es mejor) se comprobó también sobre las mismas filas. Un menor ECE no garantiza menor error predictivo ni elimina errores dentro de cada intervalo.

| Salida | ECE control (pp) | ECE candidato (pp) |
|---|---:|---:|
| Fallo por lanzamiento | 0.5022 | 0.4230 |
| Fallo dado swing | 0.9540 | 0.6603 |
| Bola en juego | 0.6132 | 0.2589 |
| Strike cantado | 0.4388 | 0.3043 |
| Jonrón por lanzamiento | 0.0386 | 0.0179 |
| Contacto débil | 0.7695 | 1.1616 |
| Contacto duro | 1.3079 | 1.2058 |

Se añadió el ECE del control mediante una recomputación sin ajuste de modelos; se reprodujo su MSE original con tolerancia 10⁻¹². Los resultados anteriores a ese diagnóstico adicional permanecen en los artefactos. No cambió la selección ni el candidato.

| Inconsistencia, mismas filas de comprobación | Control | Modelo conjunto |
|---|---:|---:|
| P(fallo) > P(fallo dado swing) | 4,110 | 0 |
| P(jonrón) > P(bola en juego) | 392 | 0 |
| P(contacto débil) + P(contacto duro) > 1 | 33 | 0 |
| P(strike cantado) + P(fallo) + P(bola en juego) > 1 | 20 | 0 |

**No se sustituyó el modelo activo.** La arquitectura elimina las cuatro inconsistencias, pero degrada de forma clara las dos cabezas de contacto y no supera el criterio en otras salidas. Las ganancias de fallo por lanzamiento y carreras merecen seguimiento; no justifican reemplazar todas las probabilidades ni recalcular Stuff+/Pitching+ sin las auditorías correspondientes. No se ejecutaron auditorías adicionales de este candidato conjunto porque ya falló el criterio de avance global.

## Resultado del ensamble

El peso elegido en tune fue **75% CatBoost + 25% LightGBM**. LightGBM solo y los demás pesos tuvieron mayor error que ese candidato en tune. La comprobación inicial dio Brier **0.149788**, frente a **0.150160** del control, sobre **23,010 swings de 168 juegos**: reducción **0.2477%**, intervalo por juegos aproximadamente **0.159% a 0.336%** usando 1,000 remuestreos.

El peso quedó congelado antes de las auditorías:

| Auditoría | Swings / juegos | Reducción de Brier | Intervalo 95% | Criterio |
|---|---:|---:|---:|---|
| 2024 → 2025 | 119,384 / 839 | +0.0195% | −0.0151% a +0.0520% | No superado |
| Pitchers excluidos | 3,977 / 146 | +0.1331% | −0.0330% a +0.3008% | No superado |
| Harp excluido | 1,098 / 8 | +0.2754% | +0.0221% a +0.5568% | Superado |

La mejora media es positiva, pero no queda confirmada en las pruebas temporal y de pitchers nuevos. La muestra de Harp es pequeña. **El ensamble tampoco está activo** ni se cambió su peso después de ver estos resultados.

## Dictamen práctico

La idea de probabilidades conjuntas resuelve un problema real de coherencia. La prueba no respalda una sustitución global del motor. El ensamble ofrece una señal pequeña que se debilita fuera del esquema de desarrollo: tampoco satisface los criterios definidos.

Las líneas con evidencia más prometedora son fallo por lanzamiento y valor esperado en carreras del conjunto. Antes de integrarlas habría que contrastar versiones que conserven las buenas cabezas de contacto y realizar sus auditorías temporales/por grupos, sin presentar este resultado como precisión futura demostrada.

Los datos, el bundle activo y sus referencias no se modificaron. Las pruebas matemáticas y de categóricas pasaron; la evaluación real eliminó las cuatro inconsistencias en las filas de comprobación. Los controles de integridad verifican los hashes de origen y bundle. Los snapshots originales de código de las ejecuciones se conservan junto a los artefactos cuando se añadieron mejoras posteriores de compatibilidad o métricas.

Verificación final ejecutada: `python -m unittest test_coherent_events test_stuff_plus_v9 test_estadios_modelo_v9 -q`: **26 pruebas aprobadas**. También pasó `git diff --check`. Se comprobaron los hashes del Parquet y del bundle, el cierre de las tres auditorías del ensamble, las cuatro restricciones de coherencia y la ausencia de activación automática. No se modificó la interfaz durante estas pruebas.
