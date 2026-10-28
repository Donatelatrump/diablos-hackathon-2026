"""Etapa 6: documento tecnico (entregable 5).

El texto vive aqui y las cifras se inyectan desde artifacts/, para que el documento no
pueda desincronizarse de los modelos que lo respaldan.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ART = ROOT / "artifacts"
DOCS = ROOT / "docs"


def f(x, n=2):
    return "—" if x is None else f"{x:,.{n}f}".replace(",", " ")


def main() -> None:
    ph = json.loads((ART / "physics.json").read_text())
    mo = json.loads((ART / "models.json").read_text())
    de = json.loads((ART / "deliverables.json").read_text())
    ad = json.loads((ART / "altitude_deltas.json").read_text())

    mae = ph["mae_holdout"]
    hp = mo["holdout_pitcher"]
    comp = mo["componentes"]
    abl = mo.get("ablacion_whiff", {})
    tipo = de["por_tipo"]
    riesgo = de["riesgo_contacto"]
    rfb = de["riesgo_fly_balls"]
    perfil = de["perfil_ideal"]
    mez = de.get("mezcla_top_1pct", {})
    qt = de.get("delta_por_quintil", {})
    q4s = qt.get("Four-Seam", {})
    qall = qt.get("TODOS", {})
    tabla_quintil = "\n".join(
        f"| {i+1} | {f(v['plus_mar'],1)} | {f(v['plus_alt'],1)} | **{v['delta']:+.2f}** | "
        f"{f(qall[k]['delta'],2) if k in qall else '—'} |"
        for i, (k, v) in enumerate(q4s.items())
    )

    sea, ext = "No Altitude", "Extreme Altitude"
    d_ivb = ad["ivb"]

    orden = sorted(tipo.items(), key=lambda kv: kv[1]["delta"], reverse=True)
    tabla_tipo = "\n".join(
        f"| {k} | {v['n']:,} | {f(v['stuff_mar'],1)} | {f(v['stuff_alt'],1)} | "
        f"{v['delta']:+.2f} | {v.get('delta_vs_recta', 0):+.2f} | {f(v['whiff']*100,1)} % |".replace(",", " ")
        for k, v in orden if k != "Other"
    )
    mez = de.get("mezcla_top_1pct", {})
    qt = de.get("delta_por_quintil", {})
    q4s = qt.get("Four-Seam", {})
    qall = qt.get("TODOS", {})
    tabla_quintil = "\n".join(
        f"| {i+1} | {f(v['plus_mar'],1)} | {f(v['plus_alt'],1)} | **{v['delta']:+.2f}** | "
        f"{f(qall[k]['delta'],2) if k in qall else '—'} |"
        for i, (k, v) in enumerate(q4s.items())
    )
    tabla_mezcla = "\n".join(
        f"| {k} | {f(v['liga']*100,1)} % | {f(v['top_nivel_mar']*100,1)} % | {f(v['top_altitud']*100,1)} % |"
        for k, v in sorted(mez.items(), key=lambda kv: kv[1]['top_altitud'] - kv[1]['top_nivel_mar'], reverse=True)
        if k != "Other"
    )
    tabla_delta = "\n".join(
        f"| {k} | {v['observado']:+.2f} | {v['predicho']:+.2f} | {v['n']} |"
        for k, v in sorted(d_ivb.items(), key=lambda kv: kv[1]["observado"])
    )
    tabla_comp = "\n".join(
        f"| `{k[2:]}` | {v['n']:,} | {f(v['brier'],5)} | {v['skill']:+.4f} |".replace(",", " ")
        for k, v in comp.items()
    )
    tabla_perfil = "\n".join(
        f"| {k} | {f(v['optimo_nivel_mar'])} | {f(v['optimo_altitud'])} | "
        f"{v['diferencia']:+.2f} | {f(v['liga_mediana'])} |"
        for k, v in perfil.items()
    )

    doc = f"""# Stuff+ calibrado a 2,240 metros

### Un modelo de calidad de lanzamiento para el Estadio Alfredo Harp Helú

**Hackathon ISAC 2026 · Diablos Rojos del México**
{ph['n_pitches']:,} lanzamientos · Liga Mexicana de Béisbol · temporadas 2024–2026

---

## 1. Marco teórico

La sabermetría moderna evalúa el lanzamiento, no el resultado. Un *slider* que induce un
swing fallido y uno que termina en jonrón pueden ser físicamente idénticos: la diferencia
está en el bateador, el parque y el azar. Los modelos tipo Stuff+ separan la calidad del
lanzamiento de su desenlace observado, estimando el valor esperado a partir de las
propiedades físicas del envío.

Esa separación depende de un supuesto que en la LMB no se sostiene: que la relación entre
la física del lanzamiento y su resultado es la misma en todos los estadios. Los modelos
Stuff+ de MLB se entrenaron casi enteramente con parques cercanos al nivel del mar. El
Harp Helú está a 2,240 metros, más alto que Coors Field (1,609 m), el estadio más
favorable al bateo de las Grandes Ligas.

El mecanismo es directo. El movimiento de un lanzamiento lo produce el aire: la fuerza de
Magnus, que desvía la pelota, es proporcional a la densidad del aire. Con menos aire hay
menos fuerza y menos movimiento. Alan Nathan estima que en Coors Field un lanzamiento con
18 pulgadas de quiebre puede moverse 14 o 15. La pregunta de este trabajo es cuánto, y
para qué formas de lanzamiento, en las condiciones específicas de la LMB.

## 2. Datos

El conjunto entregado por ISAC contiene {ph['n_pitches']:,} lanzamientos rastreados con
Trackman a lo largo de tres temporadas, con identificadores anonimizados de juego,
lanzador, bateador y receptor.

La limitación central para este reto es que **el conjunto no identifica el estadio ni su
altitud**: sólo trae `altitude_category`, una variable de tres niveles. La sección 3
explica cómo se recupera una medida continua de la densidad del aire a partir de la propia
trayectoria.

Otras limitaciones y su tratamiento:

| Limitación | Tratamiento |
|---|---|
| Sin estado de corredores (24 estados base-out) | Valor de carrera sobre la cadena de 12 estados de conteo |
| Sin fecha ni número de lanzamiento | Orden reconstruido del archivo; las filas vienen cronológicas y contiguas por juego |
| `is_hit_by_pitch` viene en cero en las {ph['n_pitches']:,} filas | Reconstruido de `PitchCall`; es el único de catorce flags derivados con este problema |
| `AutoPitchType` con clases residuales | Colapsadas a un vocabulario estable de siete tipos |

## 3. La densidad del aire, medida en la trayectoria

Restando la gravedad, la aceleración medida en el release se descompone en dos partes
ortogonales: una paralela a la velocidad, que es el arrastre, y una perpendicular, que es
Magnus.

    a_aero  = a_medida − g
    a_drag  = (a_aero · v̂) v̂
    a_magnus = a_aero − a_drag

Como el arrastre va con ρ·C_d·v², el cociente **k_drag = |a_drag| / v²** es proporcional a
la densidad del aire y se puede calcular para cada lanzamiento. Su mediana por juego da un
índice estable, con variación día a día dentro de cada estadio:

| Categoría | Índice de arrastre (mediana) |
|---|---|
| Nivel del mar | {f(ph['rho_por_cubeta'].get(sea), 4)} |
| Altitud media | {f(ph['rho_por_cubeta'].get('Medium Altitude'), 4)} |
| Altitud extrema | {f(ph['rho_por_cubeta'].get(ext), 4)} |

### 3.1 El arrastre no es la densidad

El índice mide ρ·C_d, no ρ. A 2,240 metros la atmósfera estándar da una densidad de 0.802,
pero el arrastre medido cae sólo a {f(ph['rho_altitud_extrema'], 4)}. La diferencia es el
coeficiente de arrastre: el número de Reynolds baja con la densidad y C_d sube.

Ajustando un solo exponente que ancle el índice medido a la altitud del Harp Helú se
obtiene {f(ph.get('altitud_a_indice_arrastre', {}).get('exponente'), 4)}. La verificación es
independiente: con ese exponente, un estadio a la altura de Coors Field debería dar
{f(ph.get('altitud_a_indice_arrastre', {}).get('verificacion_cubeta_intermedia', {}).get('predicho'), 4)},
y la cubeta intermedia de la LMB mide
{f(ph.get('altitud_a_indice_arrastre', {}).get('verificacion_cubeta_intermedia', {}).get('medido'), 4)}.

### 3.2 El movimiento cae más que la densidad

Si arrastre y Magnus fueran ambos proporcionales a ρ, el movimiento caería en la misma
proporción que el frenado. No ocurre. Midiendo la respuesta **dentro de cada lanzador**
—1,187 combinaciones lanzador × tipo, siete cubetas de densidad, respuesta monótona—:

    k_drag ~ ρ^0.96          k_magnus ~ ρ^1.39

El Magnus responde alrededor de 1.45 veces más fuerte que el arrastre. Verificado que **no
es el giro**: entre nivel del mar y altitud extrema, dentro del mismo lanzador, la
frecuencia de giro cambia +0.5 %, el *spin factor* +0.3 % y la velocidad de salida +0.1 %.
Es el aire.

## 4. Arquitectura

La decisión central es que **la altitud no entra al modelo Stuff+ como variable**.
Introducirla como indicador dejaría su efecto confundido con qué lanzadores tiran dónde, e
impediría responder la pregunta operativa: ¿cuánto valdría este lanzamiento, que nunca se
ha tirado en altura, en el Harp Helú? En su lugar, dos etapas donde la altitud queda
identificada por física:

**Etapa 1 — transferencia de forma.** Con el punto de salida y el giro fijos, se reintegra
la trayectoria escalando arrastre por el cociente de densidades y Magnus por ese cociente
elevado a los exponentes calibrados (vertical {ph['magnus_gamma_vertical']},
horizontal {ph['magnus_gamma_horizontal']}). El integrador es Runge-Kutta de cuarto orden
anclado en el punto real de salida (y = 60.5 − extensión), con el eje de giro conservado y
la fuerza de Magnus perpendicular a la velocidad en todo el vuelo.

Se usa por diferencias: el integrador no predice la forma, sólo su *cambio* entre dos
densidades, y ese cambio se suma a la medición real de Trackman. Así los niveles coinciden
con Trackman por construcción y el único error que queda es el diferencial.

**Etapa 2 — Stuff+ sobre forma pura.** Un modelo de *gradient boosting* que ve únicamente
la física del envío: velocidad, quiebres, giro, punto y ángulos de salida, extensión,
ángulos de aproximación. Nunca ve ubicación, conteo, bateador ni estadio. Por eso es
transferible: para saber qué vale el mismo lanzamiento en otro aire, se le pasa la forma
transferida y se vuelve a puntuar.

Sobre esa base, Location+ agrega ubicación y conteo, y Pitching+ agrega arsenal y
secuencia.

### 4.1 Función de pérdida y escala

El objetivo es el valor de carrera del lanzamiento, construido sobre la cadena de conteos:

    RV(lanzamiento) = valor(estado después) − valor(estado antes)

donde el valor de un conteo es el valor de carrera esperado de los turnos que pasan por él
y el de un evento terminal es su peso lineal, recentrado con las frecuencias de la LMB. La
escala sigue la convención sabermétrica:

    Stuff+ = 100 + 10 × z(−xRV)

100 es el promedio de la liga y cada 10 puntos es una desviación estándar; el signo se
invierte porque un valor de carrera bajo favorece al lanzador.

## 5. Validación fuera de muestra

### 5.1 La transferencia de forma

La prueba decisiva: tomar los lanzamientos de un lanzador **a nivel del mar**, transferirlos
al aire de altitud, y comparar contra lo que ese mismo lanzador realmente tiró allá.
{ph['pitchers_cruce']} lanzadores tiraron en ambos entornos; la mitad se usó para calibrar
los exponentes y la otra mitad **nunca**. Sobre esas {ph['celdas_holdout']} celdas de
evaluación:

| Magnitud | Sin transferir | Sólo densidad | Modelo calibrado | Reducción |
|---|---|---|---|---|
| Quiebre vertical (in) | {f(mae['sin_transferir']['ivb'],3)} | {f(mae['solo_densidad']['ivb'],3)} | **{f(mae['calibrado']['ivb'],3)}** | {f((1-mae['calibrado']['ivb']/mae['sin_transferir']['ivb'])*100,1)} % |
| Quiebre horizontal (in) | {f(mae['sin_transferir']['hb'],3)} | {f(mae['solo_densidad']['hb'],3)} | **{f(mae['calibrado']['hb'],3)}** | {f((1-mae['calibrado']['hb']/mae['sin_transferir']['hb'])*100,1)} % |
| Velocidad al plato (mph) | {f(mae['sin_transferir']['zone_speed'],3)} | {f(mae['solo_densidad']['zone_speed'],3)} | **{f(mae['calibrado']['zone_speed'],3)}** | {f((1-mae['calibrado']['zone_speed']/mae['sin_transferir']['zone_speed'])*100,1)} % |

La columna «sólo densidad» es un modelo que escala todo por la densidad del aire, sin la
corrección de Reynolds. Subestima el castigo de la altitud en cerca de un tercio.

### 5.2 Delta de forma por tipo de lanzamiento

Medido dentro del mismo lanzador y el mismo tipo, en pulgadas de quiebre vertical:

| Lanzamiento | Observado | Predicho | Celdas |
|---|---|---|---|
{tabla_delta}

### 5.3 Las tres capas, holdout de lanzador

Validación cruzada agrupada: ningún lanzador aparece a la vez en entrenamiento y prueba.

| Capa | Variables | RMSE | R² |
|---|---|---|---|
| Modelo nulo (promedio por conteo) | — | {f(mo['baseline_nulo_por_conteo']['rmse'],5)} | {f(mo['baseline_nulo_por_conteo']['r2'],5)} |
| Stuff+ | {hp['stuff']['n_features']} | {f(hp['stuff']['rmse'],5)} | {f(hp['stuff']['r2'],5)} |
| Location+ | {hp['location']['n_features']} | {f(hp['location']['rmse'],5)} | {f(hp['location']['r2'],5)} |
| Pitching+ | {hp['pitching']['n_features']} | {f(hp['pitching']['rmse'],5)} | {f(hp['pitching']['r2'],5)} |

El R² a nivel de lanzamiento individual es bajo por construcción: el desenlace de un envío
suelto lo domina el azar. Lo relevante es la comparación contra el modelo nulo que pide la
rúbrica, y la estabilidad al agregar por lanzador.

**Holdout de temporada** (entrena 2024–2025, prueba 2026):
RMSE {f(mo['holdout_temporada']['stuff']['rmse'],5)}, R² {f(mo['holdout_temporada']['stuff']['r2'],5)}.

**Holdout de parque** (entrena sin altitud extrema, prueba en altitud extrema):
RMSE {f(mo['holdout_parque']['stuff']['rmse'],5)}, R² {f(mo['holdout_parque']['stuff']['r2'],5)}.
La degradación frente al holdout de lanzador es exactamente el fenómeno que este trabajo
mide: un modelo entrenado a nivel del mar no traslada limpio a la altura.

### 5.4 Modelos de componente

| Objetivo | n | Brier | Skill sobre tasa base |
|---|---|---|---|
{tabla_comp}

El barril es el caso honesto de límite del modelo: con una tasa base de 2.5 %, la calidad
del contacto depende mucho más del bateador que del lanzamiento, y la habilidad predictiva
desde la física del envío es marginal.

### 5.5 Aporte del arsenal

Sobre el valor de carrera agregado el arsenal aporta poco, porque la varianza de un
lanzamiento suelto la dominan la ubicación y el conteo. Donde sí se ve es en el swing
fallido, que es el mecanismo que el arsenal explica —diferencial de velocidad y túnel—:

| Capa | Brier | Skill |
|---|---|---|
{chr(10).join(f"| {k} | {f(v['brier'],5)} | {v['skill']:+.4f} |" for k, v in abl.items()) if abl else "| — | — | — |"}

## 6. Resultados

### 6.1 Efecto de la altitud por tipo de lanzamiento

Cada lanzamiento del conjunto se transfirió a las dos densidades y se puntuó con el mismo
modelo. Como Stuff+ sólo ve forma, la diferencia es atribuible al aire.

| Lanzamiento | n | Stuff+ nivel del mar | Stuff+ Harp Helú | Δ | Δ vs. recta | Whiff observado |
|---|---|---|---|---|---|---|
{tabla_tipo}

**Todo pierde.** El promedio de la liga cae {de['delta_promedio_liga']:+.2f} puntos. Pero la
pérdida está ordenada, y el orden tiene un mecanismo: **la altitud es un impuesto sobre el
efecto Magnus, y cada lanzamiento paga en proporción a cuánto de su valor viene de ahí.**

En un extremo, el *cutter* casi no paga ({tipo['Cutter']['delta']:+.2f}): se mueve poco y su
engaño está en salir igual que la recta. En el otro, la curva paga más que nadie
({tipo['Curveball']['delta']:+.2f}): es movimiento puro, y el movimiento es justo lo que el
aire delgado se lleva. La recta de cuatro costuras, que vive de su elevación, pierde
{f(abs(d_ivb['Four-Seam']['observado']),2)} pulgadas de quiebre vertical, más que ningún otro
tipo.

### 6.2 La composición del talento cambia

Si en vez de promediar se mira **qué lanzamientos componen el 1 % mejor puntuado** en cada
entorno, el desplazamiento es más elocuente que cualquier delta:

| Lanzamiento | Toda la liga | Top 1 % a nivel del mar | Top 1 % en el Harp Helú |
|---|---|---|---|
{tabla_mezcla}

El *slider* pasa de {f(mez['Slider']['top_nivel_mar']*100,1)} % a
{f(mez['Slider']['top_altitud']*100,1)} % de la élite: casi se triplica. La recta cae de
{f(mez['Four-Seam']['top_nivel_mar']*100,1)} % a {f(mez['Four-Seam']['top_altitud']*100,1)} % y
el *sinker* se parte a la mitad, de {f(mez['Sinker']['top_nivel_mar']*100,1)} % a
{f(mez['Sinker']['top_altitud']*100,1)} %.

### 6.3 El castigo es regresivo

El promedio esconde lo más importante. Partiendo los lanzamientos en quintiles según su
Stuff+ **a nivel del mar**, el castigo de la altitud no se reparte parejo:

| Quintil de calidad | Stuff+ nivel del mar | Stuff+ Harp Helú | Δ recta 4C | Δ todos |
|---|---|---|---|---|
{tabla_quintil}

La recta del quintil más bajo **no pierde nada: gana {q4s['q1']['delta']:+.2f}**. La del
quintil más alto pierde {q4s['q5']['delta']:+.2f}, y pasa de
{f(q4s['q5']['plus_mar'],1)} —élite— a {f(q4s['q5']['plus_alt'],1)}, apenas por encima del
promedio de la liga.

**La altitud no daña al lanzamiento malo. Borra la ventaja del bueno.** Es un efecto de
compresión: el aire delgado se lleva el movimiento, y el movimiento es precisamente aquello
en lo que un lanzamiento de élite se distingue de uno mediocre. Quien no tenía nada
excepcional que perder, no pierde nada.

Esto reencuadra por completo la pregunta de reclutamiento, y es el resultado con más
consecuencias prácticas de todo el trabajo (sección 7).

### 6.4 El riesgo al otro lado del bate

| Entorno | Velocidad de salida | Distancia | HR por bola en juego | Tasa de rodado |
|---|---|---|---|---|
| Nivel del mar | {f(riesgo[sea]['exit_speed'],1)} mph | {f(riesgo[sea]['distancia'],0)} ft | {f(riesgo[sea]['hr_por_bip']*100,2)} % | {f(riesgo[sea]['gb_rate']*100,1)} % |
| Altitud extrema | {f(riesgo[ext]['exit_speed'],1)} mph | {f(riesgo[ext]['distancia'],0)} ft | {f(riesgo[ext]['hr_por_bip']*100,2)} % | {f(riesgo[ext]['gb_rate']*100,1)} % |

Restringido a elevados, que es donde la altitud cobra:

| Entorno | Distancia media | HR por elevado |
|---|---|---|
| Nivel del mar | {f(rfb[sea]['distancia'],1)} ft | {f(rfb[sea]['hr_por_fb']*100,1)} % |
| Altitud extrema | {f(rfb[ext]['distancia'],1)} ft | {f(rfb[ext]['hr_por_fb']*100,1)} % |

Un elevado viaja **{f(rfb[ext]['distancia']-rfb[sea]['distancia'],1)} pies más** y su
probabilidad de salir del parque sube de {f(rfb[sea]['hr_por_fb']*100,1)} % a
{f(rfb[ext]['hr_por_fb']*100,1)} %.

### 6.5 Perfil físico ideal para el Harp Helú

Caracterización del 1 % de lanzamientos **reales** mejor puntuados en cada entorno,
restringido a lanzadores derechos para que el quiebre horizontal no se cancele al promediar.

Se buscó dentro de los envíos observados y no sobre una rejilla libre de los ejes físicos:
una rejilla produce combinaciones que nunca ocurren —una recta de 100 mph con quiebre de
curva— y ahí un modelo de árboles extrapola cualquier cosa. La respuesta tiene que quedarse
sobre lo que un brazo humano puede realmente hacer.

| Variable | Élite a nivel del mar | Élite en altitud | Diferencia | Mediana de la liga |
|---|---|---|---|---|
{tabla_perfil}

Dos renglones cargan el hallazgo. El **movimiento total** de la élite baja de
{f(perfil['movement_total']['optimo_nivel_mar'],1)} a
{f(perfil['movement_total']['optimo_altitud'],1)} pulgadas, y la **eficiencia de giro** baja de
{f(perfil['spin_efficiency']['optimo_nivel_mar'],2)} a
{f(perfil['spin_efficiency']['optimo_altitud'],2)}.

La eficiencia de giro es la fracción del giro que se convierte en movimiento. Que la élite
de altura la tenga *más baja* significa que el giro de tipo giroscópico —el que no produce
Magnus— gana valor relativo. Es coherente: si el aire delgado grava el Magnus, conviene no
depender de él.

## 7. Recomendaciones operativas

**Lo primero, porque cambia el cálculo de cualquier contratación: no pague sobreprecio por
una recta de élite para lanzar en el Harp Helú.** No la va a recibir. Una recta del quintil
superior llega a 2,240 metros valiendo {f(q4s['q5']['plus_alt'],1)} en vez de
{f(q4s['q5']['plus_mar'],1)}, mientras que una del quintil inferior llega igual o levemente
mejor. La prima que el mercado le cobra por esa recta se paga a nivel del mar y se cobra en
un estadio donde no existe. El mismo dinero rinde más en un brazo cuyo valor no dependa del
movimiento.

La regla que resume el resto: **en el Harp Helú, no apueste al Magnus.**

**Qué gana valor relativo.** El *cutter* y el *slider*. Pierden
{tipo['Cutter']['delta']:+.2f} y {tipo['Slider']['delta']:+.2f} puntos contra
{tipo['Four-Seam']['delta']:+.2f} de la recta, y entre los dos pasan de
{f((mez['Slider']['top_nivel_mar']+mez['Cutter']['top_nivel_mar'])*100,1)} % a
{f((mez['Slider']['top_altitud']+mez['Cutter']['top_altitud'])*100,1)} % de la élite. El
mecanismo no es que se muevan más, sino que nunca dependieron de moverse mucho: su engaño
está en salir indistinguibles de la recta y romper tarde y poco. El giro giroscópico no
produce Magnus, así que el aire delgado no tiene qué quitarle.

**Qué pierde.** La curva y la recta de cuatro costuras, por la misma razón opuesta: son
movimiento puro. La recta pierde {f(abs(d_ivb['Four-Seam']['observado']),2)} pulgadas de
elevación, y una recta alta que llega con menos elevación de la que el bateador anticipa no
produce el swing por debajo: produce el elevado. En el Harp Helú ese elevado viaja
{f(rfb[ext]['distancia']-rfb[sea]['distancia'],1)} pies más y sale del parque
{f(rfb[ext]['hr_por_fb']*100,1)} % de las veces contra {f(rfb[sea]['hr_por_fb']*100,1)} % a
nivel del mar. El *sinker* pierde parecido y su participación en la élite se parte a la mitad.

**Sobre la hipótesis del cambio de velocidad.** El planteamiento del reto (H2) propone que
el cambio gane valor relativo porque engaña por diferencial de velocidad y no por Magnus.
Los datos lo sostienen, pero **débilmente**: el cambio pierde
{tipo['Changeup']['delta']:+.2f} puntos, apenas {tipo['Changeup']['delta_vs_recta']:+.2f}
mejor que la recta contra la que juega, muy por debajo del
{tipo['Cutter']['delta_vs_recta']:+.2f} del *cutter*. La razón es que el cambio sí tiene
mucho movimiento horizontal —{f(abs(ad['hb']['Changeup']['observado']),1)} pulgadas de las
cuales pierde una parte importante— y ese componente sí paga el impuesto. El ganador de la
altitud no es el que engaña por velocidad: es el que nunca dependió del movimiento.

**Cómo perfilar un prospecto.** Cuatro preguntas, en este orden:

1. *¿Cuánto de su valor está en el percentil alto de movimiento?* Es la pregunta que más
   dinero decide. Si su Stuff+ a nivel del mar está en el quintil superior y ese Stuff+
   viene del quiebre, el diferencial que lo hace caro no viaja a la Ciudad de México.

2. *¿Cuánto de su valor viene del Magnus?* No es cuántas revoluciones, sino qué fracción
   del giro se convierte en pulgadas. Eficiencia de giro alta es una virtud a nivel del
   mar y una exposición en altura: la élite de altura la tiene en
   {f(perfil['spin_efficiency']['optimo_altitud'],2)} contra
   {f(perfil['spin_efficiency']['optimo_nivel_mar'],2)} de la élite a nivel del mar.
3. *¿Su arsenal se apoya en cortadas y sliders o en curvas y sinkers?* El primer perfil
   llega al Harp Helú prácticamente intacto; el segundo llega devaluado.
4. *¿Induce rodados?* La tasa de rodado sube de {f(riesgo[sea]['gb_rate']*100,1)} % a
   {f(riesgo[ext]['gb_rate']*100,1)} % en altitud, y el rodado es el único batazo al que el
   aire no le hace nada. Es la contrapartida: la altitud castiga al lanzador en el
   movimiento, pero le devuelve algo en el tipo de contacto.

El simulador incluido permite evaluar cualquier combinación física en los dos entornos sin
necesidad de servidor.

## 8. Alcance y fronteras

Lo que este modelo **no** hace, dicho explícitamente:

- **No identifica estadios.** La cubeta de «altitud extrema» agrupa varios parques. Los
  resultados se leen como el contraste entre un entorno de altitud de la LMB y uno a nivel
  del mar, con el Harp Helú como caso más extremo, no como una estimación específica de
  ese estadio.
- **No separa aire de clima.** El índice de arrastre recoge densidad, temperatura y
  humedad juntas. Es lo correcto para predecir movimiento, pero no permite atribuir el
  efecto sólo a la altitud.
- **No modela al bateador.** Sin identidad de bateador como variable, la calidad del
  contacto queda en el límite de lo predecible (sección 5.4).
- **No es causal.** Stuff+ es un modelo de valoración. La pregunta contrafactual táctica
  («¿qué habría pasado con un slider en vez del cambio?») requiere otro instrumento.
- **El exponente de Reynolds es empírico.** Está calibrado fuera de muestra y corroborado
  por una medición independiente dentro de lanzador, pero no derivado de primeros
  principios.

## 9. Reproducción

```bash
uv venv && uv pip install -e .
python scripts/01_physics.py       # densidad del aire y transferencia de forma
python scripts/02_features.py      # secuencia, arsenal, objetivos
python scripts/03_models.py        # las tres capas y sus holdouts
python scripts/04_export.py        # modelo y tablas al simulador
python scripts/05_deliverables.py  # entregables 1, 2 y 3
python scripts/06_report.py        # este documento
cd app && npm install && npm test && npm run dev
```

## 10. Referencias

- Nathan, A. *The effect of altitude on baseball trajectories.* Physics of Baseball.
- SABR. *High altitude offense.* Baseball Research Journal.
- Tango, T., Lichtman, M. & Dolphin, A. (2007). *The Book: Playing the Percentages in Baseball.*
- Huang, G. & Hsu, M. (2021). Big data analytics in baseball: a review. *SAGE Open*, 11(4).
- Deshpande, S. K. & Wyner, A. J. (2017). A hierarchical Bayesian model of pitch framing. arXiv:1704.00823.

---

*Los datos de la LMB se usaron únicamente para esta competencia. Este documento presenta
resultados, no datos.*
"""
    DOCS.mkdir(exist_ok=True)
    out = DOCS / "documento_tecnico.md"
    out.write_text(doc)
    palabras = len(doc.split())
    print(f"escrito {out.relative_to(ROOT)} — {palabras:,} palabras (~{palabras/500:.1f} paginas)")


if __name__ == "__main__":
    main()
