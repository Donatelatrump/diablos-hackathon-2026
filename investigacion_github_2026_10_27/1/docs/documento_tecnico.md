# Diablos Stuff+

### Calidad de lanzamiento ajustada por la altitud del Estadio Alfredo Harp Helú

**Hackathon ISAC 2026 · Reto Diablos Rojos del México**
635,002 lanzamientos · Liga Mexicana de Béisbol · temporadas 2024 a 2026

---

## Resumen

Los modelos Stuff+ califican qué tan difícil de batear es un lanzamiento a partir de su física. El
problema es que se construyeron en estadios a nivel del mar. El Harp Helú está a 2,240 metros, con
20 % menos aire, y ahí la pelota se mueve menos. Construimos un Stuff+ para la LMB en el que **la
altitud no es una variable del modelo sino una transformación física**. Lo hicimos en cuatro pasos.

1. **Le damos un valor a cada lanzamiento.** Cada lanzamiento cambia el conteo de bolas y strikes, y cada
   conteo vale cierto número de carreras para el bateador. La diferencia es cuántas carreras le quitó o le
   dio ese lanzamiento al rival. Eso es lo que el modelo aprende a predecir.
2. **Entrenamos un modelo que sólo ve la física.** Es un modelo de árboles de decisión (LightGBM) que recibe
   16 medidas de Trackman, como la velocidad, el giro, el movimiento y el punto de salida. No ve dónde cayó
   la pelota, ni el estadio, ni al bateador. Pasamos su predicción a una escala donde 100 es el promedio de
   la liga y cada 10 puntos es una desviación estándar. Eso es Stuff+.
3. **Lo probamos con lanzadores que no vio.** Partimos a los lanzadores en cuatro grupos, entrenamos con tres
   y calificamos al cuarto. Cada calificación sale de un modelo que nunca vio a ese lanzador, y la
   comparamos contra un modelo nulo que sólo conoce el conteo.
4. **Volamos el mismo lanzamiento en otro aire.** Medimos qué tan denso estaba el aire en cada juego con el
   frenado de la pelota, simulamos cómo habría volado cada lanzamiento con el aire del Harp Helú y lo
   calificamos otra vez. La diferencia entre las dos calificaciones es el efecto de la altitud.

Encontramos diferencias útiles para orientar el scouting.

- En la población completa por tipo, la recta pierde {{recta_delta}} puntos de Stuff+ y el cutter {{cutter_delta}}. Son estimaciones del modelo, bajo el supuesto de la misma salida de la mano.
- De {{pitchers_n}} lanzadores con muestra suficiente, {{aguantan}} pierden menos de media carrera estimada por cada 100 lanzamientos.
- H1 tiene respaldo físico. H2 y H3 tienen respaldo parcial. H4 no demuestra que el giro sea irrelevante.
- El bosque de entorno estima una diferencia promedio de {{cf_ate}} carreras por cada 100 lanzamientos. La interpretación causal exige controles suficientes y no se confirma la heterogeneidad individual.

## 1. Planteamiento

### 1.1 La pregunta del club

¿Qué lanzadores sufren más la altitud y cuáles son los más consistentes? De esa respuesta salen tus
fichajes, tu rotación en casa y el desarrollo de tus prospectos.

### 1.2 Por qué importa la altitud

Una pelota que gira desvía el aire hacia un lado, y el aire la empuja hacia el otro. Es el efecto
Magnus. Ese empuje produce el movimiento que engaña al bateador, y crece con la densidad del aire.
Con menos aire hay menos empuje, menos movimiento y menos engaño. A la vez, el aire frena menos y los
batazos llegan más lejos. Alan Nathan estima que en Coors Field, a 1,609 metros, un lanzamiento con 18
pulgadas de quiebre se mueve 14 o 15. El Harp Helú está 631 metros más arriba.

### 1.3 Las hipótesis del reto

| | Hipótesis | Cómo la probamos |
|---|---|---|
| H1 | La baja densidad reduce el movimiento que produce el giro | Física contra Nathan y pérdida de Stuff+ por tipo, con intervalos |
| H2 | Los lanzamientos de diferencial de velocidad ganan valor relativo | El cambio contra la recta del mismo lanzador |
| H3 | Los lanzadores de rodados valen más en altura | Pendiente de carreras contra rodados en cada entorno |
| H4 | El giro por sí solo no predice Stuff+ | Peso en el modelo y experimento controlado |

## 2. Datos y supuestos

ISAC entregó 635,002 lanzamientos medidos con Trackman en tres temporadas, con identificadores
anónimos de juego, lanzador, bateador y receptor. El conjunto **no dice en qué estadio se lanzó**. Sólo
trae una categoría de altitud con tres niveles (nivel del mar, altitud media y altitud extrema).

| Limitación | Cómo la resolvimos |
|---|---|
| No hay estadio ni altitud | Medimos la densidad del aire en la trayectoria (sección 3.2) |
| No hay corredores en base | Valor de carrera sobre los 12 conteos posibles |
| No hay fecha ni número de lanzamiento | Reconstruimos el orden, el archivo viene cronológico por juego |
| `is_hit_by_pitch` vale cero en todas las filas | Lo reconstruimos desde `PitchCall` |
| Hay tipos de lanzamiento residuales | Los agrupamos en siete tipos estables |

Trabajamos con cuatro supuestos.
**S1.** Un lanzador suelta la pelota igual en cualquier estadio. La velocidad y las vueltas que le da no
dependen de la altura. Lo comprobamos comparando a cada lanzador consigo mismo. Entre nivel del mar y
altitud extrema sus vueltas cambian 0.5 %, su eficiencia de giro 0.3 % y su velocidad de salida 0.1 %.
**S2.** Entonces lo que cambia entre estadios es el camino de la pelota después de soltarla, y eso lo
decide el aire.
**S3.** Calificamos lo que se espera de un lanzamiento, no lo que pasó en esa jugada. Un mismo
lanzamiento puede terminar en ponche o en hit según el bateador y la suerte, así que medimos su valor
promedio en carreras según el conteo.
**S4.** El 100 es el promedio de la liga tal como lanzó, en sus tres tipos de estadio. Por eso a nivel del mar el lanzamiento típico queda arriba de 100 y en altura abajo.

## 3. Metodología

### 3.1 La idea en cuatro pasos

La decisión central es que **la altitud nunca entra como variable del modelo de calidad**. Si entrara,
su efecto se mezclaría con quién lanza dónde, porque los lanzadores de los equipos de altura no son una
muestra al azar. Y no podrías responder la pregunta que importa. ¿Cuánto valdría en el Harp Helú un
lanzamiento que nunca se ha tirado ahí? Los cuatro pasos del Resumen resuelven eso. Esta sección los
detalla. La forma de un lanzamiento es cómo se mueve en el camino, cuánto sube o cae y hacia qué lado se va.

### 3.2 La densidad del aire, medida en la trayectoria

Trackman reporta la aceleración de cada pelota. Le quitamos la gravedad y nos queda la parte
aerodinámica. La separamos en una componente paralela a la velocidad (el arrastre) y una perpendicular
(el Magnus).

$$\mathbf a_{\text{aero}} = \mathbf a - \mathbf g, \qquad \mathbf a_{\text{drag}} = (\mathbf a_{\text{aero}}\cdot\hat{\mathbf v})\,\hat{\mathbf v}, \qquad \mathbf a_{\text{M}} = \mathbf a_{\text{aero}} - \mathbf a_{\text{drag}}$$

El arrastre vale $\tfrac12 \rho\, C_d A\, v^2 / m$. Por eso el cociente $k_{\text{drag}} = \lVert \mathbf a_{\text{drag}} \rVert / v^2$
es proporcional a $\rho\, C_d$, y lo calculamos para cada lanzamiento. Su mediana por juego, normalizada
al nivel del mar, es el **índice de arrastre** $I$ de ese juego.

<!-- g:aire -->

**El arrastre no es la densidad.** A 2,240 metros la atmósfera estándar da $\rho/\rho_0 = 0.802$, pero
medimos un índice de 0.853. La causa es aerodinámica. Con menos aire baja el número de Reynolds y sube
el coeficiente de arrastre $C_d$. Anclamos un solo exponente $\beta$ a la altitud del Harp Helú.

$$I(h) = \rho_{\text{ISA}}(h)^{\beta}, \qquad \rho_{\text{ISA}}(h) = \left(1 - 2.25577\times 10^{-5}\, h\right)^{4.25588}, \qquad \beta = 0.7184$$

La prueba es independiente del ajuste. Con ese $\beta$, un estadio a la altura de Coors Field debería
dar $I = 0.8931$. La categoría de altitud media de la LMB nunca entró al ajuste y mide 0.8981.

**El movimiento cae más que el arrastre.** Dentro del mismo lanzador y tipo de lanzamiento (1,187
combinaciones en siete niveles de densidad), las dos fuerzas responden distinto.

$$k_{\text{drag}} \propto \rho^{0.96}, \qquad k_{\text{M}} \propto \rho^{1.39}$$

El Magnus responde casi 1.5 veces más fuerte que el arrastre. Como el lanzador le da las mismas vueltas a la
pelota en los dos estadios (S1), esa caída del empuje viene del aire.

### 3.3 Transferencia de forma, el mismo lanzamiento en otro aire

Para cada lanzamiento resolvemos su estado de salida (posición, velocidad y eje de giro) a partir de lo
que midió Trackman. Después integramos el vuelo desde la mano hasta el plato con Runge Kutta de cuarto
orden y pasos de 2 milisegundos.

$$\frac{d\mathbf v}{dt} = -\,k_d\, I\,\lVert\mathbf v\rVert\,\mathbf v \;+\; M\, I^{\gamma}\,\frac{\lVert\mathbf v\rVert^{2}}{\lVert\mathbf v_0\rVert^{2}}\;\frac{\hat{\boldsymbol\omega}\times\mathbf v}{\lVert\hat{\boldsymbol\omega}\times\mathbf v\rVert} \;+\; \mathbf g$$

Aquí $k_d = 0.001588$ es la mediana de la LMB a nivel del mar y $M$ es la magnitud de Magnus que
reproduce la forma medida. Los exponentes $\gamma_v = 1.7$ (vertical) y $\gamma_h = 2.2$ (lateral) los
calibramos fuera de muestra (sección 4.1). El eje de giro $\hat{\boldsymbol\omega}$ se conserva y la
fuerza queda perpendicular a la velocidad todo el vuelo.

**Usamos el simulador sólo para medir diferencias.** No le pedimos que adivine cómo se movió la pelota,
eso ya lo midió Trackman. Le pedimos cuánto cambiaría el movimiento al pasar de un aire a otro, y ese
cambio se lo sumamos a la medición real.

$$\text{forma}_{\text{HH}} = \text{forma}_{\text{Trackman}} + \big[f(I_{\text{HH}}) - f(I_{\text{obs}})\big]$$

Así siempre partimos de lo que midió Trackman, y el único error posible está en cuánto cambia la forma.

### 3.4 El valor en carreras de cada lanzamiento

Sin corredores en base, el estado del turno es el conteo, con 12 combinaciones de bolas y strikes. El
valor de un conteo $V(c)$ es el promedio de las carreras de los turnos que pasan por él. Los eventos
finales usan pesos lineales (sencillo 0.70, doble 1.00, jonrón 1.65, ponche $-0.27$), recentrados para
que el turno promedio de la LMB valga cero. El valor de un lanzamiento es cuánto mueve el turno.

$$\text{RV} = V(c_{\text{después}}) - V(c_{\text{antes}})$$

### 3.5 Stuff+, Location+ y Pitching+

Las tres capas predicen el mismo objetivo, el valor esperado en carreras $\widehat{\text{RV}}$, con
gradient boosting en LightGBM. Sólo cambia lo que ve cada una.

| Capa | Variables | Qué ve |
|---|---|---|
| Stuff+ | 16 | Sólo física. Velocidad, quiebres, giro, eje, punto de salida, extensión, tiempo de vuelo y eficiencia de giro |
| Location+ | 23 | Además, dónde llegó la pelota, el conteo y el lado del bateador |
| Pitching+ | 33 | Además, el arsenal del lanzador y la secuencia con el lanzamiento anterior |

**Los ángulos de salida y de llegada no entran en ninguna capa**, aunque Trackman los mida en el release. El
ángulo con que sale la pelota también dice a dónde va, así que con ellos el modelo aprende puntería en lugar
de física. Lo medimos. Con los cuatro ángulos, Stuff+ correlacionaba $-0.70$ con la distancia al centro de la
zona, más que el propio Location+ ($-0.53$), y la ubicación en el plato predecía el 58 % de su varianza. Sin
ellos, $-0.03$ y prácticamente nada. El reto define Stuff+ como física pura, y la ubicación entra en Location+.

Location+ y Pitching+ usan 500 árboles, tasa de aprendizaje 0.05, 96 hojas, al menos 400 lanzamientos por hoja
y regularización $L_2 = 5$. **Stuff+ va mucho más regularizado** (400 árboles, tasa 0.03, 31 hojas, al menos
4,000 lanzamientos por hoja, $L_2 = 50$). Sin ubicación, lo único que le queda para separar lanzamientos es la
física, y el punto de salida es casi una firma de cada lanzador. Con hojas chicas el modelo memoriza lanzadores
y, con lanzadores nuevos, queda peor que el promedio.

<!-- si stuff_entrena=mar -->
**Stuff+ aprende sólo de juegos a nivel del mar.** Su variable más pesada es cuánta velocidad pierde la pelota en
el camino, y en altura la pelota frena menos. Si el modelo viera juegos de altura, aprendería que frenar poco
anuncia un juego de altura y que esos juegos dan más carreras, y parte de lo que llamamos pérdida de Stuff+ sería
el entorno de bateo y no el lanzamiento. A nivel del mar el aire es uno solo, así que esa variable sólo cambia por
la pelota y el lanzamiento, y la pérdida al volar la pelota en otro aire sale entera de la física. La escala sigue
midiendo contra todos los lanzamientos de la liga.
<!-- fin -->

**De dónde sale cada calificación.** Medimos con SHAP cuánto aporta cada grupo de variables a la predicción.
Stuff+ es 100 % física, y sus variables más pesadas son cuánta velocidad pierde la pelota en el vuelo, el
quiebre vertical, la elevación y el giro. En Location+ la ubicación y el conteo explican el 62 % y la física
el 38 %. En Pitching+ la ubicación y el conteo explican el 55 %, la física el 26 % y el arsenal con la
secuencia el 19 %.

La función de pérdida es el error cuadrático (L2) sobre el valor en carreras. Pitching+ incluye las
variables relacionales de arsenal que pide el reto, todas contra la recta principal del lanzador en esa
temporada. Diferencia de velocidad, de elevación y de movimiento lateral, similitud de túnel (qué tan
parecido sale de la mano), uso de cada lanzamiento, tamaño del arsenal, lanzamiento anterior y vuelta al
orden.

Stuff+ nunca ve ubicación, conteo, bateador ni estadio. Por eso lo puedes transferir. Para saber qué
vale un lanzamiento en otro aire, le das la forma transferida y lo vuelves a calificar. La escala sigue
la convención sabermétrica.

$$\text{Stuff+} = 100 + 10\, z\!\left(-\widehat{\text{RV}}\right)$$

Aquí $z$ estandariza con la media y la desviación estándar de la liga. 100 es el promedio y cada 10
puntos son una desviación estándar. El signo se invierte porque menos carreras es mejor para el
lanzador. El reto propone que la calificación final sea una combinación ponderada de varios objetivos (swing
fallido, persecución, strike cantado, contacto débil, rodado, contacto duro, valor en carreras). Elegimos
predecir directo el valor esperado en carreras porque ya es esa combinación, ponderada por lo que cada
resultado vale en el marcador, y así no tienes que inventar pesos. Los ocho modelos de componente sí los
entrenamos, y explican de dónde sale cada calificación, pero no entran en el cálculo de Stuff+.

### 3.6 Validación fuera de muestra

Las predicciones de validación excluyen del ajuste las filas evaluadas. Las tablas del objetivo y del modelo nulo, y la calibración física, se prepararon globalmente antes de esos cortes. Por eso la validación de producción no aísla todo el pipeline. La auditoría independiente del repositorio reajusta objetivo y baseline dentro del entrenamiento y obtiene una mejora pequeña, no un salto de calidad.

**Holdout de lanzador.** Validación cruzada de 4 pliegues agrupada por lanzador. Ningún lanzador está en
entrenamiento y prueba a la vez.

**Holdout de temporada.** Entrenamos con 2024 y 2025 y probamos con 2026.

**Holdout de categoría de altitud.** Entrenamos sin altitud extrema y probamos sólo en esa categoría. No es un holdout de estadio, porque no tenemos su identificador.

**Modelo nulo.** El promedio del valor en carreras por conteo, lo mínimo que sabes sin mirar el
lanzamiento.

**Calibración.** Agrupamos los lanzamientos por su Stuff+ fuera de muestra y comparamos lo predicho con
las carreras que pasaron.

### 3.7 Pruebas de hipótesis

Los intervalos de las comparaciones agregadas usan **bootstrap por lanzador** de 2,000 remuestreos. Remuestreamos
lanzadores completos y no lanzamientos sueltos, porque los lanzamientos de un mismo lanzador se
parecen entre sí y no cuentan como pruebas independientes.

**H1.** Para cada tipo de lanzamiento $t$ calculamos la pérdida media, ponderada por número de
lanzamientos, sobre las combinaciones de lanzador y tipo con al menos 40 lanzamientos.

$$\bar\Delta_t = \frac{\sum_i n_{it}\,\Delta_{it}}{\sum_i n_{it}}, \qquad \Delta_{it} = \text{Stuff+}_{it}^{\,\text{HH}} - \text{Stuff+}_{it}^{\,\text{mar}}$$

Además comparamos el integrador con la cifra de Nathan.

**H2.** Usamos un diseño pareado dentro del lanzador. Para quien tira cambio y recta calculamos

$$D_i = \Delta_{i,\text{cambio}} - \Delta_{i,\text{recta}}$$

Al comparar contra la recta del mismo lanzador se
controlan diferencias fijas del lanzador. El contraste sigue dependiendo de la transferencia física y del modelo de calificación. Si $D > 0$, el
cambio pierde menos que la recta.

**H3.** Tomamos los 333 lanzadores que tiraron al menos 120 veces en cada entorno. Estimamos por mínimos
cuadrados ponderados la pendiente de carreras contra rodados en cada entorno $e$.

$$R_{ie} = a_e + b_e\, \text{GB}_i + \varepsilon_{ie}, \qquad H_3 \Leftrightarrow b_{\text{alt}} - b_{\text{mar}} < 0$$

El peso de cada lanzador es $w_i = 2\,(1/n_{i,\text{alt}} + 1/n_{i,\text{mar}})^{-1}$, la precisión de una diferencia.

**H4.** Hicimos dos pruebas. Primero medimos el peso de cada grupo de variables dentro de Stuff+, como la
ganancia total de los árboles que las usan. Después corrimos un experimento controlado con el
simulador. Movimos una sola perilla (giro o movimiento) y dejamos fijo todo lo demás, algo que los datos
de la cancha no permiten. Cada punto es el promedio de 49 variaciones chicas del mismo lanzamiento, y
cada variación vuela con un arrastre sacado de la dispersión real entre pelotas, como en el pipeline,
donde cada lanzamiento vuela con su propio arrastre medido.

### 3.8 Modelo secundario, un Causal Forest

Stuff+ valora lanzamientos. Un Causal Forest responde otra cosa, preguntas de qué hubiera pasado. Lo usamos
para dos, con Double Machine Learning (Chernozhukov y coautores, 2018) y un bosque causal honesto (Wager y
Athey, 2018).

$$Y = \theta(X)\,T + g(X, W) + \varepsilon, \qquad T = m(X, W) + \eta$$

Dos modelos de árboles predicen el resultado $Y$ y la decisión $T$ a partir de los controles $W$, y el
bosque estima el efecto $\theta(X)$ sobre lo que esos modelos no explican.

**La pregunta táctica, la que plantea el reto.** ¿Qué hubiera pasado si el pitcher lanzaba slider en vez de
cambio en este conteo, contra este bateador? Cada lanzamiento de dos tipos (por ejemplo slider o cambio) es
una observación. $T$ es elegir el primero, $Y$ es su valor en carreras, $X$ es el conteo, si el bateador es del
mismo lado, el entorno (nivel del mar o altitud extrema) y si el lanzamiento anterior fue recta. $W$ controla
lo que confunde la elección, la calidad del lanzador, cuánto usa cada tipo, la vuelta al orden, las manos y
la velocidad de su recta. El resultado es una tabla por conteo, lado del bateador y entorno que orienta qué lanzamiento probar, sujeta a los controles y al soporte de los datos. Contrastamos slider contra cambio, slider contra recta, cambio
contra recta y curva contra slider.

**La pregunta de entorno.** ¿Cuánto cuesta la altura en carreras reales, y le cuesta distinto a cada
lanzador? Cada lanzador con al menos 120 lanzamientos en cada entorno aparece dos veces y se compara consigo
mismo. $T$ es lanzar en altura, $Y$ son sus carreras por cada 100 lanzamientos, y $X$ son sus rasgos (Stuff+,
velocidad, swings fallidos, rodados, extensión, mano y uso de cada tipo). Para no engañarnos, a cada lanzador
le damos el efecto de un bosque que no lo vio y aplicamos la prueba GATES (Chernozhukov y coautores, 2018).
Agrupamos por efecto predicho y comprobamos si el castigo observado sube de grupo en grupo.

## 4. Validación

### 4.1 La transferencia de forma

444 lanzadores tiraron en ambos entornos. Calibramos los exponentes con la mitad y dejamos la otra mitad
**sin tocar**. En esas 436 combinaciones predecimos lo que el lanzador tiró en altura a partir de lo que
tiró a nivel del mar.

<!-- g:transfer -->

Si escalas todo sólo por la densidad del aire, sin la corrección de Reynolds, subestimas el efecto en
cerca de un tercio.

### 4.2 Calidad y robustez

**Qué demuestra el $R^2$.** Stuff+ explica una fracción pequeña de la variación del resultado por lanzamiento. La ubicación añade capacidad predictiva en Location+ y Pitching+. Las variantes ensayadas no establecen un techo teórico. Evaluamos también calibración, separación entre grupos y repetibilidad, sin sustituir con ellas la validación predictiva.

| Prueba | Capa | Variables | RMSE | $R^2$ | Correlación |
|---|---|---|---|---|---|
| Modelo nulo, promedio por conteo | | | 0.26810 | 0.0000 | 0.005 |
| Holdout de lanzador | Stuff+ | 16 | 0.26797 | 0.0010 | 0.036 |
| Holdout de lanzador | Location+ | 23 | 0.26235 | 0.0425 | 0.207 |
| Holdout de lanzador | Pitching+ | 33 | 0.26225 | 0.0432 | 0.208 |
| Holdout de temporada | Stuff+ | 16 | 0.26626 | 0.0009 | 0.035 |
| Holdout de altitud | Stuff+ | 16 | 0.27707 | $-0.0005$ | 0.022 |

{{auditoria}}

Las tres capas de la evaluación original vencen al modelo nulo con lanzadores que nunca vieron. Stuff+ tiene el $R^2$ más bajo de las tres
porque no ve la ubicación, y así debe ser. Location+ y Pitching+ suben porque suman dónde llegó la pelota y el conteo.

**Transferencia entre entornos.** El $R^2$ de altitud es negativo y la correlación positiva es pequeña. El desfase puede contener aire, composición de bateadores, conteos y calibración. La descomposición del Anexo C depende del modelo y no identifica qué fracción del costo de la altura es causal.

**Repetibilidad dentro del historial.** Entre dos mitades intercaladas de cada lanzador, Stuff+ correlaciona 0.988 y sus carreras 0.293. Las mitades comparten periodo y mezcla de lanzamientos. Esto mide consistencia de la calificación, no estabilidad temporal prospectiva ni certeza sobre carreras futuras.

**Año siguiente, análisis retrospectivo.** Las correlaciones entre temporadas y la comparación incremental aparecen en el Anexo C. La regresión incremental se evalúa fuera de muestra por lanzador. Sin embargo, las puntuaciones históricas originales se aprendieron con resultados de otros lanzadores de todos los años. Además 2026 ya se usó en el desarrollo. La prueba no demuestra que una evaluación anterior a la temporada anticipe mejor el rendimiento de un prospecto.


**Calibración.** La escala ordena carreras cuando agregas lanzamientos, que es donde importa.

<!-- g:calib -->

La relación baja en los seis tramos, sin excepción. De un extremo al otro hay unas 4.3 carreras por
cada 100 lanzamientos, sólo por la forma. Entre 80 y 120 está el 95 % de los lanzamientos, y ahí lo
predicho queda a menos de 0.7 carreras de lo observado. En los extremos el modelo exagera un poco, en
la dirección correcta.

## 5. Hipótesis

### 5.1 H1 · La baja densidad reduce el movimiento. Se confirma

**La física reproduce a Nathan.** Tomamos una recta con 18.0 pulgadas de quiebre a nivel del mar y la
volamos en otros aires con el integrador, calibrado sólo con datos de la LMB.

<!-- g:nathan -->

Una curva típica de 78 mph y 12.4 pulgadas de quiebre total cae 1.4 pulgadas menos en Coors y 2.0 menos
en el Harp Helú. Su quiebre total baja 2.5 y 3.4 pulgadas.

**Todos los tipos pierden Stuff+.** En H1 sólo entran combinaciones de lanzador y tipo con al menos 40 lanzamientos. En los siete tipos el intervalo de 95 % queda bajo cero. La población difiere de la tabla general de Arsenal y del resumen.

<!-- g:h1 -->

Entre los arsenales elegibles de H1, la recta pierde {{recta_rv}} carreras estimadas por cada 100 lanzamientos. La curva cae menos al reducirse su quiebre. El contraste físico y la pérdida del modelo apuntan al mismo mecanismo, sin convertir la simulación en un experimento de campo.

### 5.2 H2 · El cambio gana valor relativo. Se confirma en parte

<!-- g:h2 -->

El cambio pierde {{cambio_ventaja}} puntos menos que la recta del mismo lanzador y ocupa el lugar {{cambio_rango}} entre seis alternativas. Ganar valor relativo no significa mejorar en términos absolutos. La ventaja depende del movimiento y del repertorio del lanzador.

### 5.3 H3 · Los lanzadores de rodados valen más en altura. Se confirma en parte

<!-- g:h3 -->

En altura, una mayor tasa de rodados se asocia con menos carreras. A nivel del mar el efecto no se distingue de
cero. La diferencia va en la dirección de la hipótesis ($p = 0.08$, una cola), pero no llega al 95 %. Por tercios, los lanzadores con pocos rodados (34 %) permiten 1.76 carreras más por
cada 100 lanzamientos en altura, y los de muchos rodados (50 %) sólo 1.37. En los batazos de la liga, el
rodado sube de 40.5 % a 44.8 % en altitud extrema y el jonrón por elevado sube de 12.4 % a 16.3 %.

### 5.4 H4 · El giro solo no basta. Evidencia parcial

<!-- g:h4 -->

El giro representa {{giro_peso}} % de la ganancia de los árboles. Esa importancia no mide causalidad y se reparte entre variables correlacionadas. En el barrido controlado del simulador, la curva de Stuff+ recorre {{giro_min}} a {{giro_max}} puntos a nivel del mar. El cambio absoluto medio entre pasos contiguos de 100 rpm es {{giro_local}} puntos. La diferencia entre extremos casi se cancela, pero eso no prueba insensibilidad local.

Las rectas de ejemplo conservan su orden en ambos entornos. B aventaja a A en {{pareja_mar}} puntos a nivel del mar y {{pareja_hh}} en altura. Son formas reconstruidas bajo los supuestos del simulador, no una identificación independiente del efecto del giro.

## 6. Lo que significa para el club

### 6.1 La altitud borra la ventaja del bueno

Partimos las rectas en quintiles por su Stuff+ a nivel del mar. El quintil inferior pasa de {{q1_mar}} a {{q1_alt}}, una pérdida de {{q1_delta}} puntos. El superior pasa de {{q5_mar}} a {{q5_alt}}, una pérdida de {{q5_delta}}. La mayor calidad inicial viene acompañada de mayor sensibilidad estimada al aire.

**Tres entornos, no tres estadios identificados.** El mismo lanzamiento vuela con el aire representativo de cada categoría.

{{tabla_entornos}}

La categoría extrema aproxima el entorno del Harp Helú. No identifica por separado todos sus efectos de parque ni los del clima.

### 6.2 El perfil físico ideal

Promediamos el 1 % mejor calificado en cada aire, sólo lanzadores derechos y sólo lanzamientos reales.
Una rejilla libre produciría combinaciones que ningún lanzador hace.

{{tabla_perfil}}

La élite de altura es de rompientes que caen y cortan hacia el guante, no de rectas que suben. Gira casi
lo mismo que la otra, pero convierte mucho menos de ese giro en movimiento. No depende del empuje del aire,
que es justo lo que la altura le quita.

### 6.3 Por lanzador

Analizamos {{pitchers_n}} lanzadores con al menos 300 lanzamientos. {{aguantan}} pierden menos de {{corte_aguanta}} puntos, equivalente a media carrera estimada por cada 100. {{mucho}} pierden más de {{corte_mucho}}, equivalente a una carrera.

{{peor_nombre}} presenta la mayor pérdida estimada y pasa de {{peor_mar}} a {{peor_hh}}. Como candidato de scouting, {{fichaje_nombre}} pasa de {{fichaje_mar}} a {{fichaje_hh}}, con repertorio {{fichaje_arsenal}} y dispersión entre juegos de {{fichaje_sd}} puntos. La selección combina calidad en altura, pérdida y constancia. No sustituye evaluación médica, comando ni oposición enfrentada.

### 6.4 Lo que dice el Causal Forest

**Diferencia promedio de entorno.** El bosque estima {{cf_ate}} carreras adicionales por cada 100 lanzamientos, con intervalo de 90 % de {{cf_lo}} a {{cf_hi}}. Es una estimación observacional. Sus covariables incluyen tasas de rodados y swings fallidos agregadas sobre los dos entornos, que pueden ser posteriores al tratamiento. Por ello no la presentamos como confirmación causal independiente.

La prueba de altitud del Anexo C compara resultados observados con predicciones de un modelo de nivel del mar. La razón entre la transformación física y el exceso total es una descomposición dependiente del modelo. El resto incluye bateo, selección y error de calibración. No puede atribuirse íntegramente al batazo.

**Las diferencias entre lanzadores no se sostienen.** El bosque no supera la prueba GATES de heterogeneidad fuera de muestra. La incertidumbre de sus diferencias individuales impide usarlas como política de rotación. El bosque secundario se recalculó con los insumos físicos corregidos. Su diagnóstico no valida por sí solo el nuevo ranking físico.

La física permite construir escenarios comparables. La evidencia disponible no confirma el tamaño del castigo causal individual de cada lanzador.

**La pregunta táctica, señales exploratorias.** Contrastamos slider contra cambio, slider contra recta, cambio contra recta y curva contra slider. Las tablas del dashboard separan conteo, lado del bateador y entorno, y muestran el contraste y su intervalo. La señal de slider frente a cambio orienta una prueba de repertorio. No identifica por sí sola una política óptima. Al evaluar 48 celdas por par con intervalos de 90 %, se esperan alrededor de cinco intervalos que excluyan cero bajo una hipótesis nula global. No aplicamos corrección por multiplicidad. Las diferencias entre entornos pueden contener selección de lanzamientos y confusión residual.

## 7. Recomendaciones

**Fichajes.** Revisa la sensibilidad al aire antes de pagar una prima por movimiento. El quintil superior de rectas pasa de {{q5_mar}} a {{q5_alt}} en el escenario de altura. Úsalo para priorizar observaciones y pruebas del lanzador.

**Perfil.** Busca arsenales de cutter, slider y splitter, y lanzadores que provoquen rodados. En altura un
elevado viaja 31 pies más (de 292 a 323) y sale del parque 16.3 % de las veces contra 12.4 %.

**Rotación.** Usa la pestaña Lanzadores para evaluar candidatos de casa y visitante junto con comando, salud, descanso y rival. La pérdida simulada no garantiza resultados individuales.

**En el juego.** En casa, cuando el pitcher va atrás en el conteo contra un bateador del lado contrario,
considera probar el slider frente al cambio. Las celdas del bosque son exploratorias y no tienen corrección por comparaciones múltiples.

**Prospectos.** Hazte cinco preguntas, en este orden.
1. ¿Cuánto de su valor es movimiento? Si su Stuff+ está en el quintil más alto por su quiebre, esa
   ventaja no viaja a la Ciudad de México.
2. ¿Cuánto de su giro se vuelve movimiento? La eficiencia alta ayuda a nivel del mar y te expone en
   altura. Consulta el perfil actualizado de la sección 6.2.
3. ¿Su arsenal se apoya en cutter, slider o splitter, o en recta y curva? El primero pierde poco y el
   segundo llega devaluado.
4. ¿Provoca rodados? Es el único batazo que el aire no ayuda.
5. Pasa sus números de Trackman por el simulador. Te da su Stuff+ en los dos estadios.

## 8. Límites

- **No identificamos estadios.** La altitud extrema agrupa varios parques, y el Harp Helú es el más alto.
- **No separamos aire de clima.** El índice de arrastre junta densidad, temperatura y humedad. Sirve para
  predecir movimiento, no para atribuirlo sólo a la altitud.
- **No modelamos al bateador.** Desde la física, el barril casi no se puede predecir (1 % de habilidad).
- **Stuff+ no es causal.** Es un modelo de valoración. Para las preguntas de qué hubiera pasado usamos el
  Causal Forest como análisis observacional con supuestos de ausencia de confusión y soporte común, que no confirma diferencias individuales.
- **El exponente de Reynolds es empírico.** Lo calibramos y verificamos fuera de muestra, pero no sale de
  primeros principios.
- **Stuff+ ve la caída de velocidad, que también refleja el aire.** El Anexo C muestra la sensibilidad al retirar las tres variables de frenado y al entrenar sólo a nivel del mar. Las pérdidas absolutas dependen de esa especificación.
- **La validación no es anidada de todo el pipeline.** Objetivos y baseline de producción usan tablas globales. Hay 6,346 turnos reconstruidos sin evento terminal entre 171,020, cuyo tratamiento puede afectar esas tablas. No se completó una sensibilidad por turnos íntegros.
- **Producción y evaluación son distintos.** Las tablas descriptivas y el simulador usan el modelo final ajustado con todos los datos. Las métricas de validación usan predicciones fuera de muestra. Un ranking de producción no es validación independiente.
- **El simulador representa una forma típica.** Sus 49 variaciones no equivalen a la población completa de un tipo. Las diferencias con las medias exportadas se deben revisar como discrepancias de representación, sin ajustar la dispersión para forzar coincidencia.

## 9. Reproducción

El código, los modelos entrenados y los pasos para correr todo están en
[la rama de entrega del repositorio](https://github.com/dulongski/diablos-hackathon/tree/main). El dashboard corre completo en el navegador.

## Referencias

- Athey, S., Tibshirani, J. y Wager, S. (2019). Generalized random forests. *Annals of Statistics*, 47(2).
- Chernozhukov, V. y coautores (2018). Double/debiased machine learning for treatment and structural parameters. *The Econometrics Journal*, 21(1).
- Chernozhukov, V., Demirer, M., Duflo, E. y Fernández Val, I. (2018). Generic machine learning inference on heterogeneous treatment effects in randomized experiments. NBER Working Paper 24678.
- Efron, B. (1979). Bootstrap methods, another look at the jackknife. *Annals of Statistics*, 7(1).
- Huang, G. y Hsu, M. (2021). Big data analytics in baseball, a review. *SAGE Open*, 11(4).
- Ke, G. y coautores (2017). LightGBM, a highly efficient gradient boosting decision tree. *NeurIPS*.
- Nathan, A. *The effect of altitude on baseball trajectories.* The Physics of Baseball.
- SABR. *High altitude offense.* Baseball Research Journal.
- Tango, T., Lichtman, M. y Dolphin, A. (2007). *The Book, Playing the Percentages in Baseball.*
- Wager, S. y Athey, S. (2018). Estimation and inference of heterogeneous treatment effects using random forests. *JASA*, 113(523).

## Anexo A · Modelos de componente

Estos modelos explican de dónde sale el valor y no entran en Stuff+. La habilidad mide cuánto mejoran
sobre la tasa base, con holdout de lanzador.

<!-- g:anexoA -->

El arsenal se nota donde actúa su mecanismo, en el swing fallido. Ahí la habilidad sube de 4.5 % con
sólo la física a 18.9 % con ubicación y a 19.4 % con arsenal y secuencia.

## Anexo B · Glosario

| Término | Qué significa |
|---|---|
| Stuff+ | Calidad del lanzamiento por cómo sale de la mano. 100 es el promedio y 10 puntos son una desviación estándar |
| Location+ y Pitching+ | La misma escala, sumando ubicación y conteo, y después arsenal y secuencia |
| Elevación | Cuánto cae menos una recta de lo que caería sin giro |
| Eficiencia de giro | La parte del giro que produce movimiento |
| Rodado y elevado | Batazo por el suelo y batazo por el aire |
| Arsenal | Los tipos que un lanzador usa al menos 8 % de las veces |
| Tipos de lanzamiento | Recta, sinker, cutter, slider, curva, cambio y splitter. El anexo del dashboard dibuja el vuelo de cada uno, de la mano al plato |
| Intervalo de confianza de 95 % | Rango de incertidumbre de un procedimiento de remuestreo. No incorpora sesgos de medición, selección o especificación |

*Usamos los datos de la LMB sólo para esta competencia. Este documento presenta resultados, no datos.*
