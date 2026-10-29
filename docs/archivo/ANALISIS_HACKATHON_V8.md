# Revisión del reto frente al proyecto v8

Revisión: 17 de octubre de 2026. Se consultaron la convocatoria vigente y los artefactos locales. Este documento es un diagnóstico y plan; no cambia modelos ni envía comunicaciones.

## Requisitos verificados

La evaluación asigna 25% a cada área: calidad del modelo, robustez fuera de muestra, integración de arsenal/altitud y aplicabilidad. Solicita scores por pitch, pitcher y arsenal; perfil ideal; recomendaciones; simulador con comparación de entornos y mapa de movimiento; documento técnico de 6–10 páginas. Incluye validación por pitcher, temporada y parque, y comparación contra promedio de carreras por conteo. La entrega publicada es el 22 de octubre de 2026, por correo, incluyendo los correos del equipo. Los equipos son de 2–4 estudiantes de licenciatura o maestría. Se permiten presentar resultados, no el dataset original. [Convocatoria oficial](https://www.isac-app.com/competition-details/hackathon-diablos-rojos.html).

## Diagnóstico propio

V8 tiene una base técnica defendible, pero el paquete de entrega está incompleto. No asigno una calificación estimada: no sería una evaluación del jurado. Mi prioridad sería cerrar las brechas de producto y evidencia antes de otra búsqueda extensa de hiperparámetros.

| Área | Evidencia actual | Brecha |
|---|---|---|
| Modelo | 42 pruebas, auditoría reproducible, mejoras de Brier/AUC en tres tareas | La mejora de probabilidades no ha mejorado el índice de carreras; ECE empeora en dos tareas |
| Robustez | Particiones por juegos y evaluación anual heredada; 2026 explícitamente reutilizado | Falta evaluación específica v8 con pitchers excluidos del ajuste; no hay identificación de parques |
| Arsenal/entorno | Diferenciales históricos respecto a recta primaria, uso histórico y buckets de altitud | Falta demostrar el aporte incremental del arsenal y cuantificar asociaciones de entorno por perfil |
| Uso deportivo | Simulador, ranking por pitcher/tipo, intervalos | Faltan mapa de movimiento, comparación simultánea de entornos, fichas de scouting y casos defendibles |
| Documentación | README y reportes por versión | Documento técnico y recomendaciones principales siguen siendo históricos de v3/v4 |

### 1. Resolver el alcance del entorno

El dataset local tiene `altitude_category`, no un identificador de estadio. No permite identificar Harp Helú de forma validada ni hacer un verdadero park holdout. `Extreme Altitude` no debe renombrarse automáticamente como ese estadio.

Acción propuesta: solicitar un mapeo oficial juego–estadio–altitud, fechas y aclaración del alcance esperado con los datos entregados. Mientras tanto, comparar buckets con controles por tipo, temporada, mano y pitcher; priorizar pitchers presentes en varios entornos, informar soporte muestral y usar intervalos por juegos. Esas diferencias serán asociaciones ajustadas, no efectos causales ni resultados exclusivos de Harp Helú. Un holdout por bucket tampoco equivale a uno por parque.

### 2. Evaluar pitchers no vistos

Los juegos disjuntos pueden compartir pitchers. Propongo reservar grupos de pitchers, impedir que sus filas entren al ajuste y a la construcción de perfiles usados por ese ajuste, y elegir parámetros sin usar el grupo de prueba. Evaluar por tarea, familia y tamaño de muestra, con incertidumbre agrupada por pitcher.

Conviene separar dos casos: pitcher completamente nuevo sin historial y pitcher excluido del ajuste con un historial anterior disponible para construir su arsenal. Son escenarios distintos; el segundo debe documentar qué información estaría disponible en scouting.

### 3. Conectar el modelo con una decisión

Preparar una ficha por pitcher con repertorio, tamaños de muestra, tres índices, probabilidades, intervalos, historial disponible y comparación dentro de familia/mano. Agregar una explicación local de qué variables impulsan la predicción; las atribuciones no son efectos causales.

Seleccionar tres casos reales anonimizados: un candidato para revisar, uno que requiere cautela y uno con información insuficiente. Cada caso debe mostrar evidencia a favor, evidencia en contra y qué información adicional cambiaría la recomendación. Evitar umbrales universales de contratación no validados.

Completar exportación agregada por pitcher para v8. Ya existe el agregado pitcher/tipo en `arsenal_con_incertidumbre.csv`; los agregados anteriores no deben presentarse como si se hubieran regenerado con v8.

### 4. Completar el dashboard

Añadir un mapa HB–IVB con mano normalizada, tipo, velocidad y color por predicción; permitir seleccionar pitcher y comparar su recta con sus secundarios. Mostrar soporte muestral y evitar que combinaciones sintéticas lejanas a los datos parezcan recomendaciones fiables.

Añadir dos columnas de entorno con el mismo pitch: probabilidades contextuales y Pitching+ junto a Stuff+ físico. Cambiar solamente la categoría de altitud no modifica automáticamente el movimiento. Un transporte físico entre entornos requiere un modelo adicional de movimiento con incertidumbre. Mantener esta distinción en el producto.

### 5. Alinear definiciones y evidencia

V8 añade ZoneSpeed, SpeedDrop y ZoneTime a predictores de outcomes. Son mediciones del trayecto, por lo que conviene distinguirlos de la interpretación estricta de calidad al release. El índice Stuff+ no cambió en v8 porque la alternativa de carreras fue rechazada. No presentar la mejora de AUC de whiff como mejora demostrada de Stuff+.

El baseline de conteo sí existe en los reportes v5. En 2026, el modelo físico tuvo MSE skill aproximadamente -1.09% frente a él, mientras el modelo contextual con entorno obtuvo +3.09%. Los modelos de carreras se conservaron hasta v8. La comparación debe explicar la información disponible: el baseline conoce conteo y el modelo físico no. Recalcular y presentar una tabla consolidada para la entrega; no ocultar el resultado físico.

La referencia actual de los índices es fija e histórica. No equivale a una calibración demostrada por estadio y temporada. Reportar desviaciones de la referencia sin recentrar la muestra de evaluación para forzar un promedio de 100.

Para probar la utilidad del arsenal, comparar sobre los mismos juegos un modelo sin diferenciales ni uso histórico contra el completo. La similitud de release puede estudiarse como proxy geométrico; no llamarla tunneling real sin reconstrucción de trayectoria y una definición validada. No fabricar secuencias desde IDs.

### 6. Preparar un paquete coherente

`DOCUMENTO_TECNICO_STUFF_PLUS.md` y `RECOMENDACIONES_OPERATIVAS.md` están marcados como históricos, pero contienen afirmaciones de altitud, perfiles y métricas incompatibles con el modelo vigente. El primero conserva incluso una etiqueta antigua de listo para entrega. Crear documentos finales nuevos vinculados a v8 y apartar explícitamente los históricos del paquete.

Propuesta de estructura técnica de ocho páginas: problema y alcance; datos; tres capas; arsenal y entorno; validación y baselines; resultados e incertidumbre; casos deportivos; límites y reproducción. Adjuntar un manifiesto que identifique versión, modelos y tablas utilizados. No incluir el parquet original en una publicación o demo pública.

## Orden de trabajo recomendado

1. Hoy: resolver dudas sobre estadios/fechas y fijar el contenido de entrega; preparar una tabla única de cumplimiento y métricas.
2. Siguiente bloque: evaluación de pitchers no vistos y análisis de entorno con el alcance realmente identificable.
3. Después: mapa, fichas y comparación de escenarios; exportar agregados actuales.
4. Cierre: documento técnico, recomendaciones basadas en evidencia y ensayo de una demostración con tres decisiones deportivas.

Evitaría iniciar otra arquitectura compleja antes de completar estas tareas. V8 ya aporta una mejora comprobable en discriminación; la principal oportunidad para el hackathon está en explicar dónde funciona, qué decisión permite tomar y qué todavía no puede afirmar.

## Preguntas preparadas para la organización

- ¿Pueden facilitar el mapeo de juegos a estadios y confirmar cuáles corresponden a Harp Helú?
- ¿Existen fechas, orden de pitches, identificadores de PA y ocupación de bases adicionales?
- ¿Cómo esperan evaluar comparación por estadio cuando solo se proporcionan buckets de altitud?
- ¿El whiff esperado corresponde a swing y fallo? La tabla pública mezcla foul y miss; el proyecto usa `is_whiff` del dataset. Documentar la definición acordada.

Estas preguntas están preparadas, no enviadas.

Fuentes locales: código y reportes v5–v8, dashboard vigente, diccionario de datos, revisión de entregables histórica y documentos técnicos históricos. Fuente externa principal: [bases del reto Diablos Rojos](https://www.isac-app.com/competition-details/hackathon-diablos-rojos.html), consultadas en esta revisión; [anuncio ITAM](https://eventos.itam.mx/es/evento/hackathon-isac-2026) como contexto del evento.
