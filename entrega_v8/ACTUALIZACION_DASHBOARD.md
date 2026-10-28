# Actualización de la demo local — 20/10/2026

- Simulador: nueve probabilidades, etiquetas de denominadores, riesgos de contacto fuerte y HR, explicación SHAP del Stuff+ que reconstruye el score mostrado.
- Escenarios: tres categorías con física fija, diferencias de índices, carreras proxy y riesgos. Sin transporte físico entre estadios.
- Mapa: referencia de color 100, comparación de perfiles de mayor/menor efectividad y filtro de muestra mínima.
- Evidencia: baseline por conteo, métricas temporales y de pitchers reentrenados separadas, advertencias sobre referencia histórica y benchmark reutilizado.
- Scouting: contrastes ajustados por familia/entorno y selección de perfil físico.
- Descargas: scores por pitch, pitcher y arsenal, recomendaciones y PDF de ocho páginas.
- Geografía: catálogo de 23 sedes; 21 referencias publicadas de altitud y dos pendientes. Incluye fuentes y cambios de sede. Una referencia de equipo/ciudad no certifica altitud topográfica del campo.

El dataset contiene 635,002 lanzamientos, 2,127 juegos anónimos y 3,020 lanzamientos sin categoría de altitud. No contiene fecha de juego, equipos, estadio o altitud numérica. No se asignaron estadios por categorías ni por similitud: hace falta una correspondencia documentada con los IDs de juego. `estadios_v8.py` prepara esa unión exacta y rechaza duplicados, claves desconocidas y evidencia vacía. El CSV de juegos identificados se conserva localmente fuera del ZIP.

Sigue pendiente validar por parque y demostrar un perfil óptimo específico para Harp Helú. Las referencias geográficas y los deltas predictivos por categoría tienen alcances distintos. La interfaz no anuncia cumplimiento completo del reto.

Validación: pruebas de dashboard, reconstrucción SHAP y mapeo seguro; comprobación integral de tablas, documento, manifiesto y ZIP tras regenerarlos. No se reentrenaron modelos ni se publicaron datos.
