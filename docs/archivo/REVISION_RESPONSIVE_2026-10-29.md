# Revisión responsive · 29 de octubre de 2026

Se revisó la aplicación local en Chromium con emulación táctil y capturas reales del navegador. Se aplicó la skill local `streamlit-visual-redesign` conservando cálculos, datos, estados y claves de los controles.

## Correcciones

- Menú en dos columnas en celulares y tres en tamaños intermedios, con nombres completos y texto que puede ocupar dos líneas.
- Encabezado y formulario apilados hasta 1000 px. El formulario de tableta antes quedaba demasiado estrecho y recortaba el lanzamiento y la mano.
- Botones de ejemplos de al menos 48 px de alto; controles del visor de al menos 44 px.
- Velocidad del lanzamiento separada del título en el visor pequeño, y selectores de cámara y velocidad en filas completas.
- Scroll vertical permitido sobre el lienzo 3D, corrigiendo el `touch-action:none` que establece OrbitControls. Un gesto táctil emulado sobre el campo desplazó la página 145 px.
- Fondo sólido para la barra de Streamlit, evitando que sus controles se mezclen con el texto durante el desplazamiento.
- Tamaño de texto de 16 px en entradas móviles y selectores del visor.

## Verificación ejecutada

| Ventana | Resultado |
| --- | --- |
| 320 × 740 | Sin desbordamiento horizontal; formulario y visor completos |
| 360 × 800 | Sin desbordamiento horizontal; formulario y visor completos |
| 390 × 844 | Sin desbordamiento horizontal; interacción táctil y navegación |
| 430 × 932 | Sin desbordamiento horizontal; formulario y visor completos |
| 844 × 390 | Orientación horizontal, controles táctiles y formulario apilado |
| 768 × 1024 | Tableta con formulario ancho y menú legible |
| 1440 × 1000 | Escritorio conserva el formulario junto al visor |

Se comprobaron ausencia de superposición entre nombre y velocidad, nota explicativa dentro del iframe, WebGL disponible y ausencia de errores JavaScript en los siete tamaños. Las tablas y pestañas conservan su desplazamiento horizontal local.

A 390 px se ejecutaron: reproducir/pausar/repetir, cambiar cámara y velocidad, deslizar sobre el campo, elegir Curva, cambiar a Derecho, calcular evaluación y visitar Comparar estadios, Lanzadores, Confianza, Ayuda y Simulador. No se detectaron excepciones de Streamlit ni desbordamiento de página al navegar.

Pruebas Python: 13 casos, 11 aprobados y 2 omitidos por la suite. Comando:

```powershell
.venv/Scripts/python.exe -m unittest test_dashboard_inicio test_dashboard_decisiones test_dashboard_estadios_v9 test_dashboard_stuff_plus_v9 test_dashboard_pitch_animation -q
```

Trayectorias: `node --test test_dashboard_pitch_trajectory.mjs`, 5 aprobadas. `git diff --check` sin errores.

## Archivos y reproducción

Cambios de interfaz: `dashboard_editorial.css`, `dashboard_inicio.py`, `dashboard_pitch_animation.html`, `dashboard_pitch_scene.js` y su bundle regenerado. Se añadió `verificar_responsive.cjs` para repetir la comprobación.

Con la aplicación en `http://127.0.0.1:8501`:

```powershell
npm.cmd install --prefix tmp/responsive-qa --no-save --ignore-scripts --no-audit --no-fund playwright@1.64.1
# Si no hay Chromium instalado en la caché de Playwright:
node tmp/responsive-qa/node_modules/playwright/cli.js install chromium
node verificar_responsive.cjs
```

Para iniciar la aplicación: `.venv/Scripts/python.exe -m streamlit run app.py --server.port 8501`.

Capturas y mediciones: `reports/responsive_2026_10_29/final/`, incluidos `audit.json`, `phone-interactions.json`, `phone-viewer-top.png` y `phone-result.png`. La carpeta `baseline/` conserva la primera revisión.

Límite: emulación Chromium; no se probó en un teléfono físico ni en Safari/iOS. No se midió rendimiento en hardware móvil.
