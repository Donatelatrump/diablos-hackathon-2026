# Auditoria de requisitos del hackathon

**Diagnóstico previo a completar las mejoras.** Para el estado posterior de las
validaciones, interfaz y entrega, consultar `ESTADO_ENTREGA.md` en esta carpeta.

Fecha: 27 de octubre de 2026. Version revisada: `stuff_plus_output_v9_estadios`,
13 tareas, 400 iteraciones maximas, desarrollo 2024-2025 y evaluacion 2026.

## Dictamen

**Cumplimiento parcial. No consideraria la entrega actual completa.** Existe un
modelo operativo, reproducible y con evaluacion temporal, pero faltan evidencias
centrales de robustez por estadio, recomendaciones especificas de Harp Helu y una
entrega coherente con la version nueva. Entrenar con estadio no equivale a cumplir
todos los entregables ni a demostrar una mejora por altitud.

Fuente primaria: [convocatoria HTML archivada](../../2026%20ISAC%20Hackathon%20-%20Diablos%20Rojos_%20Stuff%20Plus%20Model,%20Calidad%20de%20Pitcheo%20Ajustada%20por%20Entorno.html).
Se leyeron sus apartados de objetivo, arquitectura, entregables, evaluacion,
equipo y restricciones. No se verificaron modificaciones posteriores de la convocatoria
ni el envio efectivo del equipo.

## Cinco entregables obligatorios

| Entregable | Estado | Evidencia y pendiente |
|---|---|---|
| Scores por pitch, pitcher y arsenal; comparacion CDMX vs otros parques | Parcial | Hay scores, agregados y escenario Harp Helu. Falta el informe de deltas por perfil frente a estadios a nivel del mar, con soporte e incertidumbre. |
| Perfil fisico ideal para Diablos | Pendiente en la version nueva | Los perfiles de entrada son medianas de entrenamiento, no perfiles recomendados para Harp Helu. Los perfiles descriptivos v8 no certifican este requisito para el modelo nuevo. Se necesitan rangos por tipo/mano y mezcla de arsenal apoyados en resultados y muestra. |
| Recomendaciones operativas | Parcial | Hay casos historicos v8 y v9. No estan actualizados al mapeo y modelo por estadios. Faltan perfiles que ganan/pierden, cambios de riesgo de HR/contacto duro y criterios de scouting para Harp Helu. |
| Dashboard simulador y mapa de movimiento | Funcional, cobertura parcial | Permite introducir fisica, comparar Harp Helu con Veracruz y otros estadios, mostrar probabilidades, mapa y SHAP fisico. Los scores no cambian entre estadios en el modelo seleccionado; debe explicarse y acompanarse con deltas de probabilidades y evidencia por perfil. |
| Documento tecnico de 6-10 paginas | Formato cumplido; contenido desactualizado | PDF v9 de ocho paginas, leido completo. Describe 300 iteraciones y ausencia de mapeo; la nueva ejecucion usa 400 e incorpora estadio. No documenta sus resultados ni las nuevas limitaciones y auditorias. |

## Criterios de evaluacion: cuatro bloques de 25%

### Calidad del modelo

Hay RMSE, Brier, AUC, log loss, ECE, baselines y seleccion/calibracion separadas por
juegos. La ejecucion de 2026 contiene 135,604 lanzamientos de 455 juegos.

- Modelo contextual/final: RMSE 0.213269 frente a baseline por conteo 0.216451.
  Reduccion de MSE: 2.9189%, IC95% por juegos [2.7621%, 3.0878%].
- Modelo fisico: RMSE 0.217595. Supera su media global, pero empeora 1.06% en MSE
  frente al baseline por conteo. Son conjuntos de informacion distintos; no debe
  confundirse la ganancia frente a media global con ganancia frente a conteo.
- Harp Helu: 6,005 lanzamientos y 19 juegos; RMSE contextual 0.227930 y reduccion
  de MSE 2.71% frente al baseline por conteo.

Existe evidencia de mejora contextual, de magnitud moderada. 2026 fue utilizado
en versiones previas: no es una prueba futura intacta. Las metricas de calibracion
existen, pero la grafica de calibracion archivada pertenece a la ejecucion anterior;
debe actualizarse para la nueva entrega.

### Robustez fuera de muestra

La nueva ejecucion solo reporta `holdout=season`: entrena con 2024-2025 y evalua
2026. Esto cumple una separacion temporal, aunque no una validacion cruzada con
varias temporadas de prueba.

La auditoria de pitchers en `reports/v9/pitcher/` corresponde al dataset anterior,
300 iteraciones y cuatro regresiones. No certifica los nueve clasificadores ni
la ejecucion actual con estadios.

`reports/v9/environment/` excluye una categoria de altitud; **no es park holdout**.
No se encontro una ejecucion completada que excluya un estadio del entrenamiento
y evalue ese estadio. Evaluar los 19 juegos de Harp Helu en 2026 despues de usar
Harp Helu en desarrollo es una prueba temporal en ese parque, no park holdout.

Falta ejecutar y reportar las auditorias por pitcher y parque para esta version,
con metricas por tarea y calibracion por estadio. El codigo ofrece esos modos,
pero su disponibilidad no equivale a evidencia ejecutada.

### Integracion de arsenal y altitud

El entrenamiento incorpora diferenciales historicos respecto a la recta primaria,
uso del arsenal, confiabilidad de historia, categoria de altitud y `stadium_id`.
Las identidades de pitcher/juego no se usan como predictores.

Las decisiones congeladas conservan ubicacion para arsenal y entorno: sus modelos
no confirmaron mejora incremental en desarrollo. Las ablaciones exportadas tienen
ganancia cero para esos dos bloques por herencia. Esto es una decision estadistica
defendible; no demuestra que no exista un efecto fisico de la altitud.

Comprobacion directa: mismos 100 lanzamientos, fisica y ubicacion fijas, primero
Harp Helu (`mexico_ahh`, Extreme Altitude) y despues Veracruz (`veracruz_avila`,
No Altitude). Diferencia absoluta maxima en Stuff+, Location+, Pitching+ y carreras
esperadas: **0**. Varias probabilidades contextuales si cambian. Esta comprobacion
es funcional; no estima el efecto poblacional del estadio.

La convocatoria pide deltas por pitch shape con evidencia de LMB. Falta producir
ese analisis por tipo/mano/perfil con intervalos, soporte y tamanos de muestra,
conservando el resultado nulo del score donde corresponda. No se debe forzar un
efecto positivo ni atribuir causalidad a una comparacion predictiva.

Los escenarios mantienen el movimiento medido: no simulan su cambio aerodinamico.
El mapeo cubre 601,120 de 635,002 lanzamientos y es inferido/auditado, no oficial;
las filas pendientes mantienen estadio ausente.

### Aplicabilidad deportiva

Hay interfaz para el coach, comparaciones de escenarios, mapa y explicaciones
SHAP del indice fisico. Se guardan agregados de arsenal contextualizados en Harp
Helu. Sin embargo, los rankings no sustituyen una propuesta de perfil fisico y
arsenal ni recomendaciones con cuantificacion del riesgo y limites de soporte.

## Diferencias adicionales respecto al enunciado

- La formula 100 + 10*z esta implementada con referencia fija de calibracion.
  No se realiza una normalizacion explicita separada por temporada y estadio,
  como describe la escala de la convocatoria. Debe justificarse o implementarse
  una referencia adecuada sin usar etiquetas del conjunto de prueba.
- El score final deriva de la prediccion de carreras; los clasificadores son
  auxiliares. No es literalmente la combinacion ponderada de targets que describe
  el enunciado. Debe justificarse esta eleccion y mostrar como cumple su objetivo.
- No existe P(out dentro de PA). Se reporta contacto duro, permitido como alternativa
  a barrel. Whiff sigue el diccionario de swing y fallo; la convocatoria mezcla
  foul/miss y esa diferencia debe permanecer explicitada.
- Hay posicion continua en plato en lugar de una codificacion explicita de nueve
  zonas. Esto puede ser una decision razonable de modelado, no un incumplimiento
  automatico. Altitud exacta, secuencia, estados de bases y tunneling real no
  forman parte del modelo actual y sus limites deben declararse.
- Causal Forest es opcional; su ausencia no constituye un pendiente obligatorio.

## Estado del paquete y requisitos administrativos

El ZIP existente `ENTREGA_DIABLOS_V8.zip` contiene 53 archivos, un PDF tecnico v8
y codigo/documentacion historicos; no incluye el modelo nuevo ni los reportes v9
por estadios. El README de entrega tambien conserva limitaciones ya superadas por
el mapeo. No es un paquete coherente con la version recien entrenada.

La convocatoria pide equipo de 2-4 estudiantes de licenciatura/maestria, envio por
correo con correos de todos los integrantes y evidencia de inscripcion para los
ganadores. Esos puntos no se pueden confirmar inspeccionando el modelo.
Tambien exige limitar el uso de los datos a la competencia y presentar resultados,
no publicar el dataset original. Esta auditoria no certifica la privacidad del
repositorio remoto ni el contenido de archivos enviados externamente.

## Orden recomendado para completar la entrega

1. Ejecutar pitcher holdout y park holdout de esta version, sin confundirlos con
   resultados historicos; reportar calibracion y metricas por estadio/tarea.
2. Analizar deltas Harp Helu vs parques a nivel del mar por perfil y arsenal,
   incluyendo probabilidades, incertidumbre y el delta cero del score seleccionado.
3. Elaborar perfiles recomendados y acciones de scouting/coaching con rangos,
   muestras minimas y riesgos de HR/contacto duro; evitar presentar optimos causales.
4. Resolver/documentar las decisiones de targets y normalizacion frente al enunciado.
5. Actualizar el PDF de 6-10 paginas, recomendaciones, graficas y paquete unico;
   comprobar reproduccion en una instalacion limpia y completar datos del equipo.

## Evidencia inspeccionada

- [Resultados actuales](RESULTADOS.md), [metricas](metricas.json), [protocolo](protocolo.json)
  y [ablaciones](ablaciones.json).
- [Evaluacion Harp Helu](HARP_HELU.md) y [metricas por tarea](metricas_harp_helu.json).
- [PDF v9 anterior](../v9/DOCUMENTO_TECNICO_V9.pdf), ocho paginas leidas completas.
- [Auditorias historicas](../v9/auditorias.csv) y sus protocolos por pitcher/entorno.
- [Recomendaciones anteriores](../v9/RECOMENDACIONES_V9.md), README y ZIP de entrega v8.
- Codigo de entrenamiento, generacion de scores, reporte y simulador.
