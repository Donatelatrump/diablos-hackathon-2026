# Análisis del diseño general y siguientes mejoras

Revisión del 28/10/2026. Alcance: código actual, estilos, ejecución headless de cuatro estados de la app y capturas aportadas durante la conversación. En esta revisión no se cambió la interfaz.

## Diagnóstico

La página ya tiene una identidad coherente: papel claro, títulos condensados, acento Diablos y una escena 3D propia. El siguiente avance debe concentrarse en lectura, jerarquía de resultados y continuidad entre pantallas. Añadir más adornos o bloques introductorios probablemente aumentaría el esfuerzo antes de llegar a una evaluación.

Hay dos planos que deben mantenerse claros: el lanzamiento ilustrado por el visor y la estimación del modelo para el contexto elegido. Su cercanía visual puede sugerir una conexión ambiental que el visor no implementa. El diseño debe aclararlo antes de que el usuario interprete el resultado.

## Hallazgos priorizados

| Prioridad | Hallazgo y evidencia | Mejora propuesta | Cómo comprobarla |
|---|---|---|---|
| P0 | Textos útiles de 9–11 px y gris tenue: menú 4.06:1, etiquetas de escala 3.49:1 y nota del visor 3.82:1, según los colores declarados. | Texto de controles de 14–16 px; ayuda de 12–14 px; colores de texto con contraste suficiente. Reservar tamaños muy pequeños para información verdaderamente secundaria. | Medir contraste de todos los estados y revisar lectura con zoom de 200%, fondo real y fuentes cargadas. |
| P0 | El menú se construye con radios personalizados y una cabecera fija. La captura del usuario mostró una zona superior no clicable. Ya se ajustaron separación y eventos, pero no hubo verificación de puntero en navegador. | Consolidar un menú con área completa clicable, foco visible y estado seleccionado inequívoco. Evitar que la apariencia dependa de ocultar partes internas de widgets. | Pulsar centro y extremos de cada opción, usar teclado y comprobar que ningún overlay intercepte eventos en escritorio y móvil. |
| P1 | El `100` introductorio tiene 104 px declarados; el resultado real usa 44 px. La referencia visual puede confundirse con la evaluación del lanzamiento. | Convertir la referencia en una ayuda compacta junto al resultado. Dar mayor protagonismo al valor calculado y a su explicación. | Antes de calcular, no debe aparecer ningún número que parezca resultado. Después, una persona debe identificar qué se evaluó, en qué contexto y cuál fue la evaluación. |
| P1 | La portada, su referencia, una segunda introducción y los ejemplos preceden a la herramienta. El resultado se inserta después del bloque completo del visor. | Acortar la portada y crear una zona estable para el resultado: selección → visualización → evaluación. Tras enviar, señalar claramente dónde apareció el resultado. | Revisar a 1280×720 y en móvil que el cálculo produzca un cambio visible y que no haya que buscar su salida. |
| P1 | El menú principal mezcla acciones, explicación e histórico. Dentro de «Análisis detallado» aparecen otras cuatro pestañas; la primera es «Qué revisar para Harp Helú». | Navegación orientada a tareas: Simulador, Lanzadores, Comparar estadios y Ayuda. Evidencia e histórico en un nivel secundario identificado. El acceso «comparar» debería abrir la comparación. | Pedir a una persona nueva que llegue a un lanzador y a una comparación de estadios sin explicarle las pestañas. |
| P1 | El estadio está junto a la escena, pero la curva 3D no recibe el estadio. Su aclaración está al final del iframe. | Etiqueta visible junto al título: «Movimiento ilustrado · no cambia con el estadio». Diferenciar visualmente ilustración y evaluación. | Cambiar de estadio y comprobar que el usuario entiende qué cambió y qué conserva las mismas mediciones. |
| P1 | En análisis avanzado se generan 24 métricas, 14 campos numéricos y 12 desplegables de detalle, repartidos entre pestañas y expansores. | Resumen inicial con tres resultados prioritarios, comparación alineada y una lectura breve. Mostrar probabilidades adicionales y metodología por demanda. | Que el usuario pueda explicar la conclusión principal sin leer todas las tarjetas; mantener disponibles las cifras originales. |
| P2 | Hay cuatro botones rápidos y otro selector de tipo que vuelve a mostrar esas mismas opciones. En la tarjeta estrecha el tipo y la mano comparten una fila. | Botones rápidos para los tipos principales y un acceso claro a otros tipos. Dar suficiente ancho al nombre del lanzamiento; mano como elección sencilla con etiqueta completa. | Verificar nombres sin cortes a 390, 768 y 1280 px; cambiar tipo/mano sin perder qué perfil está activo. |
| P2 | La escena tiene controles y advertencias con tamaños propios, algunos de 10–11 px; sus botones se reducen a 36 px de alto. | Unificar tipografía y escala de controles con la página. Usar 44 px como objetivo práctico para acciones principales y táctiles, preservando pausa y cámaras accesibles por teclado. | Medir áreas reales y separación; operar sin arrastrar, usando los selectores; probar movimiento reducido. |
| P2 | La ayuda comienza con contexto, criterios del reto, tablas técnicas y reproducción. El usuario debe decidir qué necesita leer. | Primera ayuda basada en cuatro preguntas: qué significa el resultado, qué datos cambiar, por qué no cambia entre estadios y qué representa la animación. Mantener documentación técnica más abajo. | Una persona debe encontrar esas respuestas sin conocer Stuff+, holdout o calibración. |
| P2 | Se acumulan estilos del sistema anterior, del primer rediseño y de la capa editorial. Hay reglas repetidas para cabecera, títulos, radios y formularios. | Consolidar colores, tamaños y componentes compartidos; separar reglas del inicio de las generales y del iframe. | Comprobar que una corrección del menú no cambie la ayuda o los formularios de análisis. Evitar reglas generales que afecten elementos invisibles o cabeceras fijas. |

No se ha medido el tiempo que un usuario real tarda en completar estas tareas. Los problemas de jerarquía y navegación son inferencias del código y del recorrido, que necesitan confirmación con uso real.

## Legibilidad: resultados cuantificados

Ratios calculados con luminancia relativa sRGB sobre los pares declarados en el CSS:

| Elemento | Texto | Fondo | Contraste |
|---|---|---|---:|
| Menú no seleccionado, pero habilitado | `#727a72` | `#f7f5ef` | 4.06:1 |
| Encabezado pequeño de referencia | `#83887e` | `#f7f5ef` | 3.33:1 |
| Etiquetas de la escala | `#7d857b` | `#f7f5ef` | 3.49:1 |
| Explicación de índices | `#7d8376` | `#f7f5ef` | 3.58:1 |
| Nota del visor | `#7f8473` | `#fffef9` | 3.82:1 |
| Acento rojo | `#c82c38` | `#f7f5ef` | 4.97:1 |
| Texto principal | `#202b26` | `#f7f5ef` | 13.42:1 |

WCAG 2.2 establece al menos 4.5:1 para texto normal y 3:1 para texto grande, con excepciones definidas. Estos textos pequeños no deben evaluarse con el umbral de texto grande. El cálculo no es una certificación de accesibilidad: falta comprobar los estilos finales, estados, superposiciones y el resto de la aplicación. [W3C: contraste mínimo](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).

La propuesta de controles de 44 px es una decisión de comodidad, no el mínimo AA de WCAG 2.2. El criterio 2.5.8 establece 24×24 CSS px o las condiciones de separación/excepción correspondientes. Un botón de 36 px no falla ese criterio solo por su altura; el problema observado del menú era una zona de clic tapada. [W3C: tamaño mínimo del objetivo](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html).

## Orden visual recomendado

### Escritorio

1. Cabecera compacta y navegación estable.
2. Una frase de propósito, con un acceso directo al ejemplo.
3. Área de trabajo: controles legibles a la izquierda, escena al centro y resumen de evaluación a la derecha o inmediatamente debajo cuando el ancho no alcance.
4. Comparación y datos adicionales en una segunda sección.
5. Ayuda y fuentes accesibles desde el contexto, sin competir con la evaluación.

Antes de calcular, el espacio del resultado debe decir «Listo para evaluar» y explicar la acción siguiente. Después, debe mostrar el lanzamiento, la mano, el estadio y la evaluación calculada. Conservar una salida anterior requiere identificarla como tal con suficiente prominencia, no solo en una nota tenue.

### Móvil

Una sola columna en el orden: elegir lanzamiento → ver movimiento → elegir contexto y evaluar → leer resultado. Mantener títulos cortos, nombres completos y una acción principal fácil de localizar. Probar el recorrido con zoom antes de añadir elementos fijos, porque pueden tapar controles o contenido.

No conviene mantener el bloque grande de referencia encima de todo en móvil: retrasa aún más el comienzo de la tarea.

## Reglas visuales que conviene fijar

- Una fuente de lectura para texto y controles; la condensada para titulares y cifras destacadas.
- Escala consistente de texto: cuerpo legible, ayuda secundaria suficientemente grande y títulos con jerarquía clara.
- Rojo para identidad/selección y azul para comparación, con etiquetas explícitas. Si se usan verde/ámbar para desempeño o cautela, acompañarlos de texto; no depender solo del color.
- Una conclusión breve por bloque; unidades siempre cerca de los números.
- La cifra principal debe pertenecer al resultado activo. Las referencias y ejemplos educativos deben reconocerse como tales.
- Una sola forma de indicar selección, foco, carga y resultado pendiente en todas las pantallas.
- La ubicación física de una advertencia debe corresponder a lo que limita: la aclaración del visor junto al visor; la incertidumbre de una predicción junto a esa predicción.

## Evidencia de ejecución

Se ejecutó `streamlit.testing.v1.AppTest` sobre cuatro estados, sin excepciones:

| Estado | Métricas generadas | Campos numéricos | Selectores | Pestañas | Expansores |
|---|---:|---:|---:|---:|---:|
| Inicio | 0 | 4 | 3 | 0 | 2 |
| Inicio con evaluación | 3 | 4 | 3 | 0 | 3 |
| Análisis detallado | 24 | 14 | 9 | 4 | 12 |
| Ayuda | 1 | 0 | 0 | 4 | 6 |

Los conteos incluyen componentes de pestañas o expansores no activos: no significa que todos estén visibles simultáneamente. Sirven como inventario de complejidad, no como medida directa de carga cognitiva. Los tiempos headless del archivo adjunto no representan rendimiento percibido en navegador.

Datos: [auditoria.json](reports/diseno_2026_10_28/auditoria.json). Archivos revisados: `dashboard_inicio.py`, `dashboard_stuff_plus.py`, `dashboard_stuff_plus_v9.py`, `dashboard_perfiles_estadios.py`, `dashboard_guia.py`, `dashboard_editorial.css`, `dashboard_style.py` y el HTML del visor.

## Próxima iteración prioritaria

Primero corregir legibilidad y comprobar la navegación con puntero/teclado. Después reducir la portada y colocar el resultado en un lugar predecible. A continuación simplificar las vistas avanzadas y aclarar el vínculo entre estadio, ilustración y evaluación. Finalmente consolidar los estilos y verificar escritorio, móvil y zoom.

No se cambiaron modelos, cálculos, estilos ni navegación en esta revisión. Una comparación visual nueva en navegador y una prueba con usuarios sin experiencia tecnológica siguen pendientes.
