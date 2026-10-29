# Cómo otros equipos del hackatón trataron los estadios

**Actualización posterior de nuestro proyecto:** se descubrieron timestamps en los `PitchUID` UUID v1 y se contrastaron con calendario y jugadas públicas. Ya existe una clasificación local de 2,009 juegos y 601,120 lanzamientos, con 118 juegos pendientes. Véase [resultado y metodología](../../clasificacion_estadios/README.md). La conclusión de esta investigación sobre lo encontrado en repositorios ajenos sigue siendo válida; la falta de una solución local quedó parcialmente resuelta con este nuevo cruce. El dashboard y sus auditorías anteriores no se han actualizado automáticamente.

Revisión: 27/10/2026. Búsqueda pública mediante GitHub REST API y lectura estática de código y documentación. Consultas: `diablos hackathon`, `stuff+ LMB`, `ISAC 2026 baseball` y `Harp Helu`. Se identificaron once candidatos relacionados: diez con archivos y uno vacío. Se excluyeron resultados de otros temas. No es un inventario exhaustivo de equipos; repositorios privados o sin términos identificables pueden quedar fuera.

## Conclusión

**No encontré una tabla ni un procedimiento verificable que vincule `game_anon_id` del dataset con un estadio real.** La revisión confirma que varios equipos enfrentaron la misma limitación. Sus soluciones permiten modelar o simular el entorno sin recuperar la identidad del estadio.

Distingo tres tareas diferentes:

1. **Identificar:** saber en qué estadio se observó cada juego anónimo. No se encontró resuelto en las fuentes revisadas.
2. **Representar el entorno:** asignar densidad estimada por trayectoria o valores representativos a una categoría. Varios equipos lo implementan.
3. **Simular un destino:** calcular qué ocurriría bajo un escenario físico de Harp Helú o de otro parque. Varios lo implementan con supuestos; no prueba dónde se jugó el lanzamiento original.

## Evidencia por repositorio

| Repositorio | Qué hace realmente | ¿Identifica estadios del dataset? |
|---|---|---|
| [dulongski/diablos-hackathon](https://github.com/dulongski/diablos-hackathon) | Descompone aceleración en arrastre y componente perpendicular; calcula `k_drag`, mediana por juego y densidad relativa. Añade transferencia física de trayectoria. Su README reconoce que categoría no equivale a estadio. | No. Estima aire por juego. |
| [JaavRJ/hackathon_isac2026_diablosrojos](https://github.com/JaavRJ/hackathon_isac2026_diablosrojos) | AeroVision calcula `rho_hat` con desaceleración, suavizado por categoría y referencia de baja altitud. Usa la mediana de `Extreme Altitude` como escenario CDMX. | No. El README aclara que Extreme agrupa varios parques. |
| [FerArGo56/diablos-rojos-WARROOM-stuffplus](https://github.com/FerArGo56/diablos-rojos-WARROOM-stuffplus) | Catálogo de 20 parques, IDs públicos y alias. Si hubiera columna de estadio, la reconoce. Sin ella conserva `stadium_id` nulo. La app asigna a cada parque un score de los tres niveles de altitud. | No. Presenta proyecciones por parque usando niveles compartidos. |
| [Trazeure/isac26-stuff-altitud](https://github.com/Trazeure/isac26-stuff-altitud) | Consulta calendario LMB vía MLB Stats API y clima ERA5 vía Open-Meteo; combina datos públicos por estadio y hora para obtener densidades medias. Aplica promedios por categoría al dataset anónimo. | No. Enriquece el escenario ambiental; no une los IDs anónimos con `gamePk`. |
| [AriadnaPA/Diablos-Hackathon-2026](https://github.com/AriadnaPA/Diablos-Hackathon-2026) | Mapea categorías a 50, 1,450 y 2,240 m; contrasta movimiento dentro de pitcher/familia y estima altitud implícita. | No. Son altitudes representativas asignadas. |
| [ariadnaquijano/-Hackathon-Diablos-Rojos-2026](https://github.com/ariadnaquijano/-Hackathon-Diablos-Rojos-2026) | Estima pérdidas por categoría y aplica física de densidad. La validación denominada por estadio excluye toda la categoría extrema, además de pitchers de prueba. | No. Es una exclusión por categoría, aunque partes del texto la llamen park holdout. |
| [militomtzc-lang/stuffplus-harp-helu](https://github.com/militomtzc-lang/stuffplus-harp-helu) | Simula transferencia desde 0 a 2,240 m con atmósfera estándar y modelos de movimiento por categoría. | No. Harp Helú es un destino de simulación. |
| [MVelascoWS/stuffplus-lmb](https://github.com/MVelascoWS/stuffplus-lmb) | Modela los tres niveles y añade simulación de densidad. `13b_park_estricto.py` excluye categoría y pitchers. | No. La unidad ambiental del holdout es la categoría. |
| [JorgeCroda/NeuroPower_Hackathon2026](https://github.com/JorgeCroda/NeuroPower_Hackathon2026) | Codifica categorías ordinales y documenta explícitamente Extreme como proxy del holdout de estadio. Imputa faltantes por juego, después pitcher/año y moda global. | No. Imputar una categoría tampoco identifica un parque. |
| [noelBanda/Hackathon-Diablos](https://github.com/noelBanda/Hackathon-Diablos/tree/noel_rama) | Rama predeterminada con extracción, filtrado, estandarización y baseline. | No encontré resolución de estadios en sus archivos públicos revisados. |
| [paooCaar/Hackathon_DiablosRojos](https://github.com/paooCaar/Hackathon_DiablosRojos) | GitHub reporta tamaño cero en la consulta. | Sin implementación revisable. |

## Las soluciones más útiles para nuestro proyecto

### WARROOM: parece unión por estadio, pero es asignación de escenario

En [preparar.py, líneas 146–180](https://github.com/FerArGo56/diablos-rojos-WARROOM-stuffplus/blob/5b066b59770ac002d187792f99222570f40a8170/webapp/backend/app/preparar.py#L146), construyen alias del catálogo y los utilizan solo si existe una columna de estadio. Si no existe, `stadium_id` queda nulo; la altitud se completa con una representación de la categoría.

En [app_config.json](https://github.com/FerArGo56/diablos-rojos-WARROOM-stuffplus/blob/5b066b59770ac002d187792f99222570f40a8170/webapp/backend/data/reference/app_config.json), los representantes son 50, 1,600 y 2,212 m. La propia nota indica ajustar esos valores si se conoce la composición de los grupos. Para mostrar resultados por parque, cada estadio toma `stuff_plus_nivel_mar`, `stuff_plus_media` o `stuff_plus_cdmx`.

El [README de la app](https://github.com/FerArGo56/diablos-rojos-WARROOM-stuffplus/blob/5b066b59770ac002d187792f99222570f40a8170/webapp/README.md#L59) explica esa operación. Esto permite una interfaz deportiva con nombres de parques; no produce validación observada específica de cada uno.

El repositorio atribuye sus altitudes al equipo Diablos y llama oficiales a ciertos rangos. Esas son atribuciones de ese repositorio: no se encontró allí un documento de la organización que certifique la correspondencia categoría–juego–estadio. No adoptar esos umbrales como oficiales solo por esa afirmación. Su catálogo también incluye alias que juntan sedes históricas distintas; para nuestro histórico conviene conservar vigencias por temporada.

### Trazeure: calendario y clima públicos sin desanonimizar

Es el enfoque externo más elaborado de los revisados. [clima_lmb.py](https://github.com/Trazeure/isac26-stuff-altitud/blob/486a37cc94900918b5076ee8718c37dff26067ba/src/clima_lmb.py) obtiene juegos públicos, sede, hora, clima y elevación; genera medias ambientales por parque y categoría.

Pero [config.py, líneas 133–152](https://github.com/Trazeure/isac26-stuff-altitud/blob/486a37cc94900918b5076ee8718c37dff26067ba/src/config.py#L133) reconoce que el diccionario no especifica los parques de cada categoría. Propone una composición contrastando proporciones de juegos del dataset con el calendario y la pérdida de velocidad. Sus valores representativos resultan 158, 1,462 y 1,981 m; Extreme reúne seis sedes propuestas, no solo Harp Helú.

El [README](https://github.com/Trazeure/isac26-stuff-altitud/blob/486a37cc94900918b5076ee8718c37dff26067ba/README.md#L166) aclara que el archivo no tiene fecha ni estadio y que se aplica densidad promedio por categoría. Esto es una hipótesis de composición agregada; coincidencias aproximadas de proporciones y señales físicas no identifican cada juego ni prueban una composición única. No reproduje sus consultas meteorológicas ni validé sus cifras de clima; comprobé su metodología publicada.

Podemos reproducir la idea de referencias ambientales públicas y presentar una simulación física para Harp Helú, manteniendo explícitos los supuestos y sin declarar un mapeo de juegos que no existe.

### dulongski y AeroVision: estimar el aire directamente

[dulongski/physics.py, líneas 1–28 y 112–139](https://github.com/dulongski/diablos-hackathon/blob/c5a7fa97790f730fa7bcfb82e85d5319f74269ce/src/stuffplus/physics.py#L112) proyecta la aceleración aerodinámica en la dirección de la velocidad y usa el arrastre dividido por velocidad al cuadrado. La mediana por juego reduce ruido y se normaliza con la referencia `No Altitude`.

[AeroVision/density.py](https://github.com/JaavRJ/hackathon_isac2026_diablosrojos/blob/3be8c69a523624903a7ee9efac5428dfdbeda3d9/src/physics/density.py#L81) usa un proxy `ay0 / (vx0² + vy0² + vz0²)`, respaldo con pérdida de velocidad, mediana por juego y suavizado de peso 30 hacia la categoría. Son aproximaciones diferentes; no deben tratarse como idénticas.

En ambos casos la idea útil es **juego → estimación ambiental**, no juego → nombre del parque. El arrastre también depende del coeficiente aerodinámico, pelota, costuras y medición; una densidad relativa estimada no es una altitud medida ni una identificación de estadio. AeroVision también imputa categorías ausentes hacia baja altitud en algunos casos; no trasladaría ese comportamiento a nuestra auditoría de cobertura.

### Otros equipos: representantes y holdout por categoría

[AriadnaPA/01_pipeline.py, líneas 38–44](https://github.com/AriadnaPA/Diablos-Hackathon-2026/blob/f061d7b656d29553929a368a009584f386ee19f3/src/01_pipeline.py#L38) asigna explícitamente metros por categoría. [militomtzc/simulate_altitude.py](https://github.com/militomtzc-lang/stuffplus-harp-helu/blob/7b531efbd82790a9402cef859b4e68dfe27a97f8/simulate_altitude.py#L38) fija origen y destino de simulación como parámetros.

[ariadnaquijano/validacion_estadio.py, líneas 48–62](https://github.com/ariadnaquijano/-Hackathon-Diablos-Rojos-2026/blob/e17644e0ac438d607ca2b4b92c2d8da6d3fa8102/src/validacion_estadio.py#L48) y [MVelascoWS/13b_park_estricto.py](https://github.com/MVelascoWS/stuffplus-lmb/blob/b01e227c6b76b7ab494a8b99d7898740e20e76f0/pipeline/13b_park_estricto.py#L24) dejan fuera categorías completas. Eso puede aportar evidencia de extrapolación ambiental, pero no certifica por separado un estadio nominal.

[NeuroPower_Code.ipynb](https://github.com/JorgeCroda/NeuroPower_Hackathon2026/blob/9ee8fb4124164483c7b2e4efe30382801d7027ce/NeuroPower_Code.ipynb) denomina explícitamente su prueba de altitud/estadio como proxy de Extreme. Su imputación por pitcher/año o moda global puede inventar ambiente en juegos totalmente desconocidos; conservaría esos registros sin identificar en nuestro proyecto.

## Qué cambia en nuestro diagnóstico

La falta de una llave oficial sigue vigente. Sin embargo, **podemos avanzar más en simulación ambiental sin esperar esa llave**: otros equipos añaden una capa física o estiman aire por juego para trasladar movimiento, no solo cambian la etiqueta de categoría con física fija.

Recomiendo dos vías con entregables distintos:

1. **Escenario físico validado:** construir y comparar un modelo de transporte de HB/IVB/velocidad en plato con incertidumbre. Estimar densidad relativa desde trayectorias donde haya soporte; usar referencias públicas o supuestos declarados para el destino. Evaluar reconstrucción, identidad al conservar ambiente y transferencia fuera de muestra por pitcher/juego. Fijar referencias, hiperparámetros y correcciones dentro de entrenamiento; no estimarlos con todo el test. Exponerlo como escenario de Harp Helú, no como resultado observado en ese parque.
2. **Vinculación real:** mantener `game_anon_id → stadium_id` exclusivamente para coincidencias respaldadas por una llave compartida/documentación. Solicitar a la organización la correspondencia o metadatos suficientes. El catálogo y calendario públicos serán útiles al disponer de fecha/equipos/ID público, pero por sí solos no resuelven los IDs anónimos.

Para la interfaz podemos mostrar un selector de estadio de destino. Debe indicar si el resultado usa física continua o comparte una categoría con otros parques. Dos estadios que usan el mismo nivel no deben aparentar tener estimaciones independientes.

**No recomiendo importar un mapeo de estos repositorios como verdad:** no se encontró tal mapeo documentado. Sí recomiendo estudiar sus capas físicas y referencias ambientales como alternativas de implementación propias.

## Alcance y reproducibilidad de la investigación

Se descargaron 236 archivos seleccionados de código/documentación/resultados pequeños de los diez repositorios con contenido. La selección final tuvo cero errores de descarga. No se descargó el dataset de competencia ni se ejecutó el código externo. No se reentrenaron ni modificaron nuestros modelos o dashboard.

Las revisiones están fijadas a SHA en los enlaces anteriores y en `investigacion_github_2026_10_27/repos.json`; el árbol completo consultado queda en `github_tree_0.json` a `github_tree_9.json`. La búsqueda original y ampliada se conserva en `github_search_*.json`. `investigar_repos_github.py` reproduce la selección de fuentes. No se inspeccionó cada archivo de cada repositorio ni se certifica validez de sus resultados: las conclusiones se refieren a los mecanismos de identidad/entorno comprobados en las fuentes citadas.
