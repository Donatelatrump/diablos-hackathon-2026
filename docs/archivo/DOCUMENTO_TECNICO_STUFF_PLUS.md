> Documento historico de v3/v4. Para el modelo vigente, instrucciones y limites, consultar [README.md](../../README.md) y el [resultado v5](../../stuff_plus_output_v5/RESULTADO_MEJORA.md). Las afirmaciones de altitud y metricas de este documento no describen v5.

# Documento Técnico — Stuff+ Model para Diablos Rojos (ISAC Hackathon 2026)

**Equipo:** Diablos Hackathon 2026  
**Fecha:** 15 de octubre de 2026  
**Versión:** 3.0  
**Estado:** Histórico; no entregar. Documento vigente: [PDF v8](../../entrega_v8/DOCUMENTO_TECNICO_V8.pdf).

---

## 1. Introducción y marco teórico

### 1.1 Objetivo del reto

El hackatón ISAC 2026, presentado por Diablos Rojos del México, pide construir un **Stuff+ Model**: un sistema de evaluación pitch-by-pitch que estime la calidad esperada de cada lanzamiento considerando sus características físicas, su ubicación, su relación con el arsenal del pitcher y el entorno atmosférico de la Liga Mexicana de Béisbol (LMB).

La escala Stuff+ sigue la convención sabermétrica clásica (ERA+, OPS+, wRC+):

- **100** = promedio de la liga, ajustado por temporada y estadio.
- **110** = una desviación estándar mejor que el promedio.
- **120+** = elite (percentil ~97).
- **80** = por debajo de reemplazo.

El modelo responde: *¿qué tan bueno es este pitch específico, dado quién lo lanza, cómo lo lanza y dónde se lanza?*

### 1.2 Hipótesis físicas validadas

El entorno de la LMB, y en particular el Estadio Alfredo Harp Helú en la Ciudad de México (~2,240 msnm), introduce un efecto físico medible:

- **Menor densidad del aire** (≈20% inferior al nivel del mar) reduce la resistencia aerodinámica y el efecto Magnus.
- Un pitch con 18 pulgadas de break a nivel del mar puede moverse apenas 14–15 pulgadas en Coors Field (1,609 m). A 2,240 m en Harp Helú el efecto podría ser mayor (Alan Nathan, SABR).
- Los fly balls viajan más lejos; los jonrones y el contacto elevado se vuelven más costosos.
- Los groundball pitchers ganan valor relativo en altitud (H3 de la convocatoria).

Nuestro modelo cuantifica este efecto empíricamente con datos de LMB, no asume supuestos de MLB.

---

## 2. Arquitectura del modelo

### 2.1 Descomposición en tres sub-modelos

Siguiendo el marco de FanGraphs (Stuff+, Location+, Pitching+), construimos tres capas separadas:

| Sub-modelo | Pregunta que responde | Features principales |
|------------|----------------------|---------------------|
| **Stuff+** | ¿Qué tan bueno es el pitch por sus propiedades físicas en el release? | RelSpeed, SpinRate, SpinAxis, RelHeight, RelSide, Extension, VertBreak, InducedVertBreak, HorzBreak, EffectiveVelo, AutoPitchType, PitcherThrows |
| **Location+** | ¿Qué tan bien fue ubicado para maximizar el resultado esperado? | PlateLocHeight, PlateLocSide, Balls, Strikes, BatterSide + Stuff+ features |
| **Pitching+** | Combinación final de stuff + ubicación + arsenal + entorno | Promedio ponderado de Stuff+ y Location+, ajustado por altitud y arsenal |

Esta separación evita que la ubicación contamine la evaluación de la calidad física pura del lanzamiento, requisito explícito de la convocatoria.

### 2.2 Features de arsenal relacional (requisito obligatorio 25%)

Cada pitch se evalúa en relación con el repertorio completo del pitcher. Calculamos, por `pitcher_anon_id`:

- `velo_diff_vs_fb`: RelSpeed del pitch − RelSpeed medio del fastball primario del pitcher.
- `ivb_diff_vs_fb`: InducedVertBreak del pitch − IVB medio del fastball primario.
- `hb_diff_vs_fb`: HorzBreak del pitch − HB medio del fastball primario.
- `tunnel_similarity`: distancia euclidiana del punto de release vs. el fastball del mismo pitcher (efecto túnel).
- `pitch_usage_pct`: frecuencia de uso del tipo de pitcheo dentro del arsenal del pitcher.
- `prev_pitch_type`: tipo del pitch anterior del mismo pitcher (secuenciación).

El fastball primario se identifica como Four-Seam o Sinker, el más usado por cada pitcher.

### 2.3 Features de entorno y altitud

- `altitude_meters`: altitud del estadio en metros (mapeo: No Altitude ≈ 100 m, Medium ≈ 800 m, Extreme ≈ 2,240 m Harp Helú).
- `altitude_category`: bucket categórico.
- `altitude_stadium`: nombre representativo del estadio LMB.

### 2.4 Targets multi-objetivo

| Target | Descripción | Tipo |
|--------|-------------|------|
| `is_whiff` | Swing y miss | Clasificación |
| `is_whiff_given_swing` | Whiff condicionado al swing | Clasificación |
| `is_ball_in_play` | Bola en juego | Clasificación |
| `is_weak_contact` | Contacto débil (velocidad de salida baja o tipo débil) | Clasificación |
| `is_barrel_or_hard_contact` | Contacto duro / barril (ExitSpeed ≥ 95, ángulo 25–35°) | Clasificación |
| `is_called_strike` | Strike cantado | Clasificación |
| `swung_outside_strike_zone` | Chase (swing fuera de zona) | Clasificación |
| `is_groundball` | Rodado dado contacto | Clasificación |
| `home_run` | Jonrón por pitch | Clasificación |
| `ExitSpeed` | Velocidad de salida | Regresión |
| `run_value` | Valor esperado de carrera por pitch | Regresión |

### 2.5 Algoritmo y función de pérdida

Usamos **CatBoost** (gradient boosting sobre árboles de decisión) por las siguientes razones:

- Captura interacciones no lineales entre velocidad, movimiento y arsenal sin imponer forma funcional.
- Maneja nativamente características categóricas (AutoPitchType, PitcherThrows, BatterSide, altitude_category, prev_pitch_type).
- Soporta validación por grupos (pitcher holdout, game holdout) sin fuga de datos.
- Es interpretable con SHAP values, esencial para comunicar al pitching coach qué features impulsan cada score.

Funciones de pérdida:
- Clasificación: `Logloss`.
- Regresión: `RMSE`.

Hiperparámetros (desarrollo): `iterations=120`, `depth=5`, `learning_rate=0.05`, `l2_leaf_reg=5.0`, `thread_count=-1` (CPU). Para producción final se recomienda `iterations=400`, `depth=7`.

### 2.6 Ingeniería de características

- `SpinAxis` → `SpinAxis_sin`, `SpinAxis_cos` (evita discontinuidad en 0°/360°).
- `SpinEfficiency` proxy: `SpinRate × |sin(SpinAxis)| / RelSpeed`.
- `VeloSpinRatio`: `RelSpeed / SpinRate`.
- Interacciones implícitas por pitch type: `AutoPitchType × RelSpeed`, `AutoPitchType × InducedVertBreak`, `AutoPitchType × SpinRate` (como strings categóricas para CatBoost).

---

## 3. Definición formal de la escala Stuff+

### 3.1 Normalización por temporada

Para cada temporada `y` y cada componente `c` ∈ {stuff, location, pitching}, calculamos:

```
z_{i,c,y} = (score_{i,c,y} − μ_{c,y}) / σ_{c,y}
```

donde `μ_{c,y}` y `σ_{c,y}` son la media y desviación estándar del componente en la temporada `y`.

La escala final es:

```
Stuff+_i = 100 + 10 × z_{i,stuff,y}
Location+_i = 100 + 10 × z_{i,location,y}
Pitching+_i = 100 + 10 × z_{i,pitching,y}
```

Esto garantiza que 100 sea siempre el promedio de la liga para esa temporada, y que los scores sean comparables entre temporadas.

### 3.2 Composición de los scores compuestos

**Stuff+** (propiedades físicas, release only):

```
stuff_raw = z(p_whiff_given_swing) − z(pred_exit_speed_given_in_play) + z(p_groundball_per_pitch)
```

donde `p_groundball_per_pitch = p_ball_in_play × p_groundball_given_in_play` y `expected_exit_speed_per_pitch = p_ball_in_play × pred_exit_speed_given_in_play`.

**Location+** (ubicación):

```
location_raw = z(p_called_strike) + z(p_chase)
```

**Pitching+** (combinado):

```
pitching_raw = (stuff_raw + location_raw) / 2
```

Los pesos son iguales (1.0) como punto de partida; la convocatoria indica que deben revisarse con el staff técnico. Se pueden aprender mediante regresión de xRunValue sobre los componentes estandarizados.

---

## 4. Validación fuera de muestra

### 4.1 Estrategia de splits

Implementamos cuatro niveles de validación para cumplir con el criterio de robustez (25% de la nota):

| Split | Train | Test | Propósito |
|-------|-------|------|-----------|
| `season_holdout_2025` | 2024 | 2025 | Validación temporal estricta |
| `season_holdout_2026` | 2024+2025 | 2026 | Validación temporal estricta |
| `pitcher_holdout_20pct` | 80% pitchers | 20% pitchers | Generalización a lanzadores no vistos |
| `game_holdout_20pct` | 80% juegos | 20% juegos | Generalización a juegos no vistos |
| `park_holdout_extreme_altitude` | No Altitude + Medium | Extreme Altitude (Harp Helú) | **Calibración separada por estadio** |

El `park_holdout` es crítico: entrenamos sin datos de Harp Helú y probamos en CDMX para aislar el efecto altitud y validar que el modelo generaliza al entorno del hogar de Diablos.

### 4.2 Métricas reportadas

Para clasificación: ROC AUC, Brier score, Brier skill score, ECE (10 bins), Average Precision, Precision@Top10%, Lift@Top10%.
Para regresión: MAE, RMSE, R², RMSE skill vs. baseline de media de entrenamiento.

Se reportan también tasas base (train rate) para contextualizar el rendimiento en eventos raros (home_run ≈ 0.7%).

### 4.3 Resultados principales (v3, season_holdout_2026)

| Task | ROC AUC / R² | Brier | Brier Skill |
|------|-------------|-------|-------------|
| called_strike | 0.871 | 0.0998 | +0.274 |
| chase | 0.909 | 0.1029 | +0.404 |
| whiff | 0.623 | 0.0982 | +0.019 |
| groundball | 0.626 | 0.2387 | +0.045 |
| exit_speed | R² 0.135 | — | rmse_skill +0.135 |
| home_run | 0.576 | 0.0068 | +0.0005 |
| xRunValue | R² 0.023 | — | rmse_skill +0.023 |
| weak_contact | 0.568 | 0.2003 | +0.0098 |
| barrel_or_hard | 0.559 | 0.0314 | +0.0013 |

**Interpretación:**
- Location+ (called_strike, chase) tiene excelente discriminación (AUC > 0.87).
- Stuff+ puro (whiff, groundball) tiene AUC moderada (0.62–0.63) porque excluimos intencionalmente variables de plato/trayectoria que no son parte de Stuff+. Esto es correcto conceptualmente.
- Home run es evento raro (0.7%); el modelo captura señal débil pero útil (lift top 10% ≈ 1.5x).
- xRunValue tiene R² bajo (0.023) pero supera el baseline constante; es un buen punto de partida para el modelo de valor de carreras.

### 4.4 Efecto de altitud (park holdout)

El `park_holdout_extreme_altitude` muestra que el modelo generaliza razonablemente a Harp Helú (AUC whiff 0.629, chase 0.894), confirmando que las features de altitud capturan parte del efecto del entorno.

El resumen por altitud confirma el efecto Harp Helú:

| Altitud | Stuff+ medio | Location+ medio | Pitching+ medio |
|---------|-------------|-----------------|-----------------|
| Extreme (Harp Helú) | 100.99 | 99.96 | 100.48 |
| Medium | 100.01 | 100.08 | 100.05 |
| No Altitude | 98.32 | 100.03 | 99.18 |

Los pitchers en Harp Helú tienen Stuff+ ~2.7 puntos superior a nivel del mar, consistente con la hipótesis de que la menor densidad del aire afecta el movimiento esperado y por ende la evaluación de Stuff+.

---

## 5. Entregables generados

| Entregable | Archivo | Descripción |
|------------|---------|-------------|
| 1. Stuff+ Scores por pitch, pitcher y arsenal | `stuff_plus_output_v3/scores_pitch_v3_enriquecido.parquet` | Score individual por lanzamiento con Stuff+, Location+, Pitching+ |
| | `stuff_plus_output_v3/stuff_plus_por_pitcher.csv` | Ranking de 1,082 pitchers con delta Stuff+ Harp Helú vs. nivel del mar |
| | `stuff_plus_output_v3/stuff_plus_por_altitud.csv` | Efecto de altitud por estadio |
| 2. Perfil físico ideal Diablos | `stuff_plus_output_v3/perfil_ideal_diablos.json` | Características del top 10% de Stuff+ en Harp Helú |
| 3. Dashboard simulador | `dashboard_stuff_plus.py` | App Streamlit para el pitching coach |
| 4. Documento técnico | Este documento | Marco teórico, modelado, validación, alcance |
| 5. Modelos entrenados | `stuff_plus_output_v3/modelos/*.cbm` | 11 modelos CatBoost (11 tareas) |
| 6. Métricas de validación | `stuff_plus_output_v3/metricas_validacion_v3.json` | Métricas out-of-sample por split y tarea |

---

## 6. Alcance y fronteras del modelo

### 6.1 Limitaciones

1. **Datos anonimizados**: `game_anon_id` y `pitcher_anon_id` impiden mapear exactamente a estadios reales sin fechas. El mapeo altitud→estadio es aproximado por bucket.
2. **Sin fechas de juego**: La única columna temporal es `ZoneTime`; no se puede hacer holdout por fecha exacta ni validar efectos de temperatura/humedad.
3. **Stuff+ es predictivo, no causal**: El modelo estima calidad esperada, no el efecto causal de cambiar un pitch específico. El Causal Forest (opcional en la convocatoria) quedaría como capa táctica futura.
4. **Pesos iguales en el compuesto**: Los pesos del score Stuff+/Location+ son iguales (1.0). Se recomienda aprenderlos mediante regresión de xRunValue observado.
5. **Sampleo de temporada**: Solo 3 temporadas (2024–2026) limitan la estabilidad de los splits season_holdout.

### 6.2 Fronteras éticas y de uso

- Los datos son de rendimiento deportivo, sin PII. IDs anonimizados.
- El output es para análisis de rendimiento y scouting, no para apuestas (según disclaimer de ISAC).
- Los parámetros internos de scouting permanecen fuera del dataset público.

---

## 7. Conclusiones y próximos pasos

El modelo Stuff+ v3 cumple con los requisitos obligatorios de la convocatoria:

- ✅ Tres sub-modelos (Stuff+, Location+, Pitching+) separados.
- ✅ Features de arsenal relacional incorporadas.
- ✅ Efecto de altitud cuantificado empíricamente (Harp Helú vs. nivel del mar).
- ✅ Validación fuera de muestra: pitcher holdout, season holdout, park holdout.
- ✅ Calibración (Brier, ECE) reportada para todas las tareas.
- ✅ Baselines xRunValue por conteo calculados.
- ✅ Dashboard simulador para el pitching coach.
- ✅ Documento técnico y recomendaciones operativas.

**Próximos pasos recomendados:**
1. Aprender pesos óptimos del compuesto Stuff+/Location+ mediante regresión de xRunValue.
2. Añadir `scale_pos_weight` o focal loss para home_run y otros eventos raros.
3. Validación rolling origin (2024 → 2025; 2024+2025 → 2026) en lugar de un solo holdout.
4. Integrar SHAP values para interpretabilidad ante el coaching staff.
5. Ejecutar el dashboard en Streamlit Cloud o servidor local para uso del staff de Diablos.
