# Mejoras aplicadas tras el análisis general

Se aplica la revisión de `ANALISIS_DISENO_GENERAL_2026-10-28.md` al flujo existente, manteniendo los modelos, sus escalas y los cálculos.

## Navegación

- Menú con botones nativos completos: Simulador, Comparar estadios, Lanzadores y Ayuda.
- Estado compartido en `main_navigation` para menú y accesos internos; se conserva la navegación por callback.
- Comparar estadios abre la pestaña del lanzamiento y entorno; Lanzadores abre la de pitchers y movimiento.
- El histórico v8 pasa al apartado de documentación del panel lateral.
- Se retiran 11 reglas CSS del antiguo menú de radios, incluida la que ocultaba elementos internos.
- Botones con altura mínima de 46 px, foco visible y anuncio de la vista actual para lectores de pantalla.

## Inicio y resultados

- Portada compacta, con una sola frase de propósito. Se elimina el 100 gigante que podía confundirse con una evaluación.
- Ejemplos rápidos de los tipos principales; el selector completo queda dentro de «Ver todos los tipos de lanzamiento».
- Nombre del lanzamiento seleccionado visible y control de mano con ancho completo.
- Área estable del resultado en la columna de controles; antes del cálculo indica «Listo para evaluar».
- El valor calculado tiene protagonismo. La referencia histórica de 100 aparece junto a él, con su interpretación.
- El resultado anterior indica expresamente que corresponde a la última evaluación enviada y que editar requiere volver a evaluar.
- La jerarquía móvil conserva componentes nativos apilables: controles y evaluación se agrupan, seguidos del visor. El orden debe verificarse con un navegador real antes de ajustar más la composición.

## Lectura y ayuda

- Etiquetas de widgets y botones de al menos 14 px; ayudas compartidas de 13–14 px, con gris más oscuro.
- El iframe usa su propia escala equivalente: texto de 13 px y controles de 44 px.
- La aclaración «Movimiento ilustrado · Esta animación no cambia con el estadio» está junto al título del visor.
- Se mantienen las diferencias físicas de la animación y sus controles, sin cambiar el cálculo de trayectorias.
- La guía abre con cuatro preguntas: significado del resultado, datos editables, igualdad entre estadios y alcance del visor.
- En comparación aparecen tres índices principales por entorno; índice integral, probabilidad de out y tabla de probabilidades quedan disponibles en expansores.

## Archivos

`dashboard_navigation.py`, `dashboard_stuff_plus.py`, `dashboard_inicio.py`, `dashboard_stuff_plus_v9.py`, `dashboard_guia.py`, `dashboard_editorial.css`, `dashboard_style.py`, `dashboard_pitch_animation.py` y `dashboard_pitch_animation.html`. Se adaptaron las pruebas al menú real y se añadió un helper de navegación para ellas.

## Comprobación

```powershell
.venv/Scripts/python.exe -m unittest test_dashboard_inicio test_dashboard_estadios_v9 test_dashboard_stuff_plus_v9 test_dashboard_pitch_animation -q
node --test test_dashboard_pitch_trajectory.mjs
```

Se comprueban selección de ejemplos, cálculo, cambio de estadio, navegación a lanzadores, ayuda e histórico, así como las diferencias de trayectoria entre recta y curva. Los colores declarados se muestrean con luminancia sRGB en `reports/diseno_2026_10_28/auditoria_aplicada.json`, conservando la auditoría anterior para comparación.

Las pruebas headless no verifican áreas de clic ni layout real de escritorio/móvil. Sigue pendiente esa comprobación en un navegador conectado; no se afirma certificación de accesibilidad ni revisión visual. Para abrir: `http://localhost:8501`.

## Revisión adicional de interfaz · 29 de octubre

- La evaluación del inicio ocupa ahora todo el ancho debajo del simulador. La cifra principal y su explicación aparecen juntas; la comparación de cinco filas deja de estar comprimida en la columna de controles.
- El flujo se identifica con los pasos 01 (lanzamiento), 02 (escenario) y 03 (evaluación), con un estado inicial explicativo y textos más breves. Se eliminaron repeticiones de la referencia de 100 puntos.
- Las pruebas experimentales de comparación aparecen después de los resultados habituales. En Confianza, la investigación requiere una acción explícita y la tabla técnica de error/calibración queda plegada; las limitaciones principales siguen visibles.
- La página de lanzadores tiene una introducción propia y no muestra el tutorial de preparación de un lanzamiento. El filtro y el orden están agrupados; la tabla completa queda disponible en un expansor, dando prioridad a la ficha y al mapa.
- Los identificadores se presentan como «Lanzador 00002» en el selector y la ficha. Se conserva el ID real, visible en la ficha y en las tablas, y los valores de sesión no cambian.
- El mapa muestra nombres de lanzamientos y entornos en español, unidades en ejes/tooltip y una escala verde continua con contornos. Conserva los puntos, métricas, tamaños de muestra y normalización por mano originales.
- Se corrigió el corte de renderizado al vaciar la selección de estadios: la comparación solicita una selección y las vistas de lanzadores/evidencia siguen disponibles. Una prueba de navegación reproduce esa secuencia.

Archivos de esta revisión: `dashboard_inicio.py`, `dashboard_stuff_plus_v9.py`, `dashboard_decisiones.py`, `dashboard_editorial.css`, `test_dashboard_estadios_v9.py` y `test_dashboard_decisiones.py`. Se conservan los cálculos, claves, callbacks y modelos. El hash del bundle activo coincide con el del experimento anterior y los candidatos siguen inactivos.

Verificación final ejecutada:

```powershell
.venv/Scripts/python.exe -m unittest test_dashboard_inicio test_dashboard_decisiones test_dashboard_estadios_v9 test_dashboard_stuff_plus_v9 test_precision_features -q
```

Resultado: **18 casos, 16 aprobados y 2 omitidos por artefactos opcionales ausentes**. También pasó `git diff --check`; la salud HTTP de localhost:8501 respondió `ok`.

La herramienta de navegador sigue devolviendo `apps: []` y `browsers: []`: quedan pendientes la inspección visual real, el ancho móvil y las áreas de clic. Las reglas responsive se añadieron en CSS, sin afirmar que se hayan visto en pantalla.

Para abrir la versión local: http://localhost:8501. Si el servidor se detiene: `.venv/Scripts/python.exe -m streamlit run dashboard_stuff_plus.py --server.port 8501`.
