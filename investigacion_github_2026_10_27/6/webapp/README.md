# Web app · Diablos Stuff+

La web app que presenta los resultados: el Stuff+ ajustado por altitud en cada parque de la LMB.

![Flujo de datos](../flujo_datos.png)

Tiene dos piezas:

- **`backend/` (el traductor):** Python + FastAPI + Polars. No tiene datos ni modelo propios: pide los pitcheos al API 1 y los resultados al API 2, y los convierte en lo que necesita cada pantalla.
- **`frontend/`:** React. La versión ya compilada está en `frontend/dist/` y el backend la sirve directamente, así que **para la demo no hace falta Node**.

## Pantallas

| Pantalla | Ruta | Para quién | Qué muestra |
|---|---|---|---|
| **Explorar** (portada) | `/` | Todos | Mapa de los 20 parques, buscador, calendario de los Diablos y los mejores agentes libres |
| **Hoy** | `/hoy` | Coach | El juego del día y la serie, el parque en una frase, los mejores lanzadores de la liga ahí y la recomendación de bullpen |
| **Estadio** | `/estadio/:id` | Coach | Zona de strike vista desde el cátcher, gráfica de movimiento, modo 3D de las trayectorias reales y el ranking de lanzadores por Stuff+ en ese parque |
| **Lanzador** | `/lanzador/:id` | Todos | Arsenal, Stuff+ en los 20 parques, dónde usarlo y dónde no, carga de trabajo y la P(whiff) de BayesBall a nivel del mar y en Harp Helú |
| **Fichajes** | `/agentes-libres` | Reclutador | Agentes libres con veredicto (Fichar, Prometedor, Vigilar o No), comparados contra los de su mismo rol |
| **¿Y si…?** | `/y-si` | Reclutador y coach | Cómo le iría a un lanzador real en cualquier parque |
| **Metodología** | `/metodologia` | Jurado | Estudio de altitud, métricas de validación de Stuff+ y BayesBall, y link al paper |

- Todas las pantallas tienen botón **ES / EN**.
- El detalle del rediseño (decisiones, usuarios y fases) está en [`docs/BRIEF_REDISENO.md`](docs/BRIEF_REDISENO.md).

## Correrla

**Lo normal:** desde la raíz del repo, `bash apis/instalar.sh` (una vez) y `bash apis/iniciar_todo.sh`. Prende los dos APIs y esta app juntos. Ver [`apis/README.md`](../apis/README.md).

**A mano** (Python 3.10 o más nuevo, con los dos APIs ya prendidos):

```bash
cd webapp/backend
python3 -m pip install -r requirements.txt
cp .env.example .env          # y pon las llaves (ver abajo)
python3 -m uvicorn app.main:app --port 8002
```

Abre **http://localhost:8002**.

### Configuración (`backend/.env`)

`instalar.sh` lo crea solo. Si lo haces a mano:

| Variable | Valor |
|---|---|
| `API1_URL` / `API1_KEY` | `http://localhost:8000` y la misma llave que `apis/api/.env` |
| `API2_URL` / `API2_KEY` | `http://localhost:8001` y la llave de **lectura** del API 2 (`API_KEY` de `apis/api2/.env`), no la de escritura |
| `PAPER_URL` | Opcional: link al paper para la página de Metodología |

## Qué pasa si algo está apagado

| Situación | Qué hace la app |
|---|---|
| Los modelos todavía no suben sus resultados | Usa un **Stuff+ provisional** (pesos a mano, sin entrenar) y lo dice en el encabezado |
| Un modelo acaba de subir su tabla | Los notebooks avisan solos. A mano: `POST http://localhost:8002/api/admin/reload` o reiniciar la app |
| El API 1 está apagado al arrancar | Usa la última copia guardada en `backend/data/cache/`, que se crea sola y nunca se sube |
| BayesBall no ha subido su tabla | La columna de BayesBall no aparece y Metodología dice que está pendiente |

## Cómo se conecta con los modelos

La app busca en el API 2 la tabla `stuff_plus_por_pitcher_tipo` y, si existe, `bayesball_por_pitcher_tipo`. El formato exacto está en **[CONTRATO_API2.md](CONTRATO_API2.md)**.

En resumen: un renglón por pitcher × temporada × tipo de pitcheo, con el Stuff+ en tres niveles de altitud (`stuff_plus_nivel_mar`, `stuff_plus_media` y `stuff_plus_cdmx`). Cada parque toma la columna de su nivel, según los rangos de altitud de la competencia: `No Altitude` (0–700 m) toma `stuff_plus_nivel_mar`, `Medium Altitude` (800–1,600 m) toma `stuff_plus_media` y `Extreme Altitude` (1,800 m o más) toma `stuff_plus_cdmx`. Los umbrales están en `niveles_altitud` de `backend/data/reference/app_config.json`.

## Archivos del backend (`backend/app/`)

En el orden en que fluyen los datos:

| Archivo | Qué hace |
|---|---|
| `fuentes.py` | Habla con el API 1 y el API 2, y guarda la copia local de los pitcheos |
| `preparar.py` | Convierte los pitcheos en tablas: arsenal por pitcher y tipo, rol SP/RP y estudio de altitud |
| `store.py` | Junta todo en memoria: la física de cada pitcheo en cada parque y el Stuff+ por nivel |
| `physics.py` | Densidad del aire, Magnus, arrastre y trayectorias |
| `services.py` | Arma la respuesta de cada pantalla |
| `bullpen.py` | La recomendación de bullpen ("el diablo") |
| `main.py` | Recibe las peticiones del frontend (`/api/...`) y sirve `frontend/dist` |
| `model.py` | El Stuff+ provisional, que solo se usa mientras no exista la tabla en el API 2 |

Otros archivos del backend:

- `data/reference/`: configuración de la app, estadios con su altitud y nombres de columnas.
- `data/schedule/2026.csv`: el calendario de la temporada (dato público).
- `scripts/fetch_schedule.py`: baja el calendario de la LMB desde la API pública de estadísticas de MLB (`statsapi.mlb.com`), que también tiene los datos de la LMB. Con él se generó `2026.csv`.
- `tests/`: pruebas automáticas con datos sintéticos.

## Editar el diseño (frontend)

Necesitas Node 18 o más nuevo. Con el backend prendido en el 8002, en otra Terminal:

```bash
cd webapp/frontend
npm install
npm run dev          # http://localhost:5173, se recarga sola con cada cambio
```

- Estilos: `src/styles.css`. Textos en español e inglés: `src/i18n.tsx`. Pantallas: `src/pages/`.
- **Al terminar, corre `npm run build`.** Eso actualiza `frontend/dist`, que es lo que se ve en la demo.

## Pruebas

```bash
cd webapp/backend && python3 -m pytest
```

Son 12 pruebas (unos 10 segundos). Simulan el API 1 y el API 2 con datos sintéticos, así que no hace falta tener nada prendido. Cubren el API 2 vacío, el API 2 con la tabla del modelo, la tabla sin `stuff_plus_media`, BayesBall con y sin su tabla, y datos anonimizados como los reales.

## Notas

- **Los datos actuales están anonimizados:** no traen equipos ni fechas. Por eso los pitchers aparecen como "Equipo ?", el bullpen explica que todavía no sabe quién es del staff, y el estudio de altitud se agrupa por `altitude_category`.
- **Calendario (provisional):** por ahora la app usa el calendario 2026 de la LMB, descargado de la API de estadísticas de MLB. Tiene 99 partidos de los Diablos: 97 jugados (48 en casa y 49 de visita) y 2 pospuestos. Cuando salga el calendario 2027, se puede actualizar desde `webapp/backend/` con `python3 scripts/fetch_schedule.py --season 2027`, que crea `data/schedule/2027.csv`.
- **Altitudes:** las de los 20 estadios son oficiales, del equipo de Diablos Rojos, y están en `stadiums.json`.
- **Física:** el Magnus y el arrastre cambian con la densidad del aire. La humedad no se toma en cuenta.
