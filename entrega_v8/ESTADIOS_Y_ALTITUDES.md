# Estadios, altitudes y vínculo con los lanzamientos

Investigación del 20/10/2026. `estadios_altitudes.csv` es un catálogo de referencia LMB, no una identificación de los estadios presentes en el dataset ni una lista certificada de todas las visitas de Diablos.

## Fuentes y alcance

- [Directorio oficial de Diablos](https://www.diablos.com.mx/equipos): nombres y domicilios de sedes. Los nombres comerciales cambian; no implican cambios de ubicación.
- [Infografía LMB/MLB de altitudes](https://pbs.twimg.com/media/GStYK1XX0AE5jf-?format=jpg&name=large), reproducida en [Mediotiempo, 4/6/2025](https://www.mediotiempo.com/beisbol/a-estos-metros-sobre-el-nivel-del-mar-juegan-los-equipos-de-lmb-y-mlb): valores publicados para equipos/sedes de 2025. Son referencia publicada, no levantamiento topográfico de cada campo. La imagen muestra 154 m para Tecos; no se extiende ese valor a Nuevo Laredo.
- [Guía con infografía de la LMB](https://cdnc.heyzine.com/files/uploaded/v2/3c071ee909cba381ab7c0767eca9afb5d4e05b9d.pdf): distingue Laredo (154 m) de Nuevo Laredo (127 m). Sus valores son referencias de ciudad/sede de esa edición, no mediciones nuevas.
- [Calendario oficial Diablos 2024](https://www.diablos.com.mx/noticias/datos-mas-importantes-calendario-2024): 93 juegos programados, 45 en casa, apertura en Puebla y rivales. Programación no equivale a partido efectivamente disputado, por reprogramaciones.
- [Calendario LMB 2025](https://www.milb.com/news/lmb-calendario-oficial-de-la-temporada-2025-de-la-liga-mexicana-de-beisbol) y [calendario Diablos 2026](https://lmb.com.mx/noticias/listo-el-calendario-lmb-2026-para-los-diablos-rojos): contexto de temporadas. No contienen una equivalencia con los IDs anónimos locales.
- [Sede temporal de Leones en 2024](https://www.milb.com/news/leones-sede-para-la-temporada-2024) y [Diablos en Kanasín el 1/8/2024](https://www.leones.mx/finaliza-la-ultima-serie-de-la-temporada-regular-leones-a-rugir-en-playoffs/): prueban que asignar Kukulcán a todo juego de Yucatán sería erróneo. Altitud del Víctor Cervera Pacheco no verificada; se conserva vacía.
- [Nueva sede de Guerreros 2026](https://guerreros.mx/estadio-pase-belico/) y [juego en YU’VA, agosto de 2026](https://lmb.com.mx/noticias/leones-se-impone-en-emocionante-juego-de-12-innings-en-oaxaca): no se transfiere automáticamente la altitud publicada para la sede anterior.

## Comparación posible

`visitas_diablos_documentadas.csv` reúne ejemplos comprobados en fuentes primarias: Kanasín (crónica de Leones), Torreón y León (crónicas de Diablos), Campeche y Zapopan (boxscores oficiales LMB 809728 y 810032). Distingue fecha de partido de fecha de publicación. Es una muestra documentada, no una lista exhaustiva, y no vincula esos partidos públicos a los IDs anónimos del dataset.

La referencia de Harp Helú es 2,232 m en la infografía 2025. Puebla figura con 2,192 m; ambos son altos y una categoría gruesa no los distingue. Campeche figura con 3 m y Cancún con 7 m; tampoco una categoría baja identifica uno de esos parques. La convocatoria usa aproximadamente 2,240 m para Harp Helú; la diferencia de 8 m entre fuentes no cambia la conclusión de identificación.

El dashboard muestra diferencias de altitud entre sedes y resultados predictivos por categorías por separado. No convierte metros en categorías de entrenamiento: el diccionario no proporciona umbrales. Tampoco presenta la diferencia de altitud como un efecto estimado sobre Stuff+.

## Identificación de cada lanzamiento

El archivo local tiene 635,002 pitches, 2,127 IDs de juego y tres temporadas (2024–2026). No contiene fecha de partido, equipo local/visitante, estadio o altitud numérica. Tener el catálogo y el calendario no permite vincular de manera única esos IDs con partidos públicos. No se reconstruyen nombres de personas ni identidades a partir de resultados deportivos.

`AUDITORIA_ESTADIOS.json` registra cobertura, categorías y faltantes. `estadios_v8.py` genera una tabla local por juego con estadio sin identificar y admite un mapeo explícito documentado. El campo `stadium_status=mapeo_documentado` indica procedencia declarada; la URL debe revisarse y no certifica por sí sola la veracidad de una asignación.

Para usar un mapeo autorizado, preparar CSV con `year,game_anon_id,stadium_id,source_url` y ejecutar `python estadios_v8.py --mapeo ruta.csv`. Se rechazan juegos desconocidos, duplicados, estadios fuera del catálogo o evidencia vacía. La unión exacta por año/ID puede aplicarse luego a todos los pitches de ese juego sin alterar el dataset original. Para adjudicar estadios reales hace falta la tabla de correspondencia de la organización o una clave pública equivalente. La validación por parque solo procede después de verificar esa tabla.
