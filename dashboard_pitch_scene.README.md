# Escena 3D del lanzamiento

`dashboard_pitch_scene.js` contiene la escena Three.js y los controles de cámara.
`dashboard_pitch_scene.bundle.js` es el archivo compilado, con Three.js y OrbitControls incluidos: el navegador no necesita conectarse a un CDN.
`dashboard_pitch_animation.py` inserta el archivo compilado y las mediciones numéricas en el HTML del visor.

La animación es una representación estilizada, con movimiento amplificado. No reconstruye la trayectoria física completa, ni el gesto de un jugador, ni las condiciones del estadio elegido. El modelo de evaluación no utiliza esta curva.

El modo opcional de laboratorio usa `pitch_altitude_lab.py`: escala IVB y HB por la razón de densidades de una atmósfera estándar, manteniendo velocidad y tiempo de vuelo. Las altitudes de origen y destino se eligen explícitamente, independientemente del selector predictivo de estadio. La línea azul representa las mediciones de origen y la roja la hipótesis de destino. No modela arrastre ni cambios de giro o costuras; no está calibrado con vuelos reales y no alimenta los índices del modelo. Las pruebas comprueban identidad, reversibilidad, dirección, densidad y aislamiento del scoring, no exactitud empírica.

`dashboard_pitch_trajectory.mjs` define la curva con una dirección inicial común, caída dependiente de la velocidad y movimiento inducido amplificado 2.5 veces. Los lanzamientos no se fuerzan a terminar en el centro del plato. La línea punteada compara con una referencia de 90 mph sin movimiento inducido. La vista inicial desde el catcher facilita observar el movimiento lateral y vertical.

## Reconstruir después de editar el JavaScript

Desde la raíz del proyecto:

```powershell
npm.cmd install --prefix tmp/pitch-3d-tools --no-save three@0.180.0 esbuild@0.25.11
node -e "require('./tmp/pitch-3d-tools/node_modules/esbuild').buildSync({entryPoints:['dashboard_pitch_scene.js'],outfile:'dashboard_pitch_scene.bundle.js',bundle:true,minify:true,format:'iife',target:'es2020',nodePaths:[require('path').resolve('tmp/pitch-3d-tools/node_modules')],legalComments:'inline'})"
```

Se incluye la licencia MIT de Three.js en `dashboard_pitch_scene.LICENSE.txt`.

## Verificación

```powershell
node --check dashboard_pitch_scene.bundle.js
node --test test_dashboard_pitch_trajectory.mjs
.venv/Scripts/python.exe -m unittest test_dashboard_pitch_animation test_dashboard_inicio test_dashboard_estadios_v9 -q
```

En navegador: comprobar las tres cámaras, arrastrar para girar, pausa/repetición, cámara lenta, cambio de lanzamiento y mano, ancho móvil y preferencia de movimiento reducido. La vista 3D requiere WebGL2; si no está disponible se muestra un mensaje dentro del visor.
