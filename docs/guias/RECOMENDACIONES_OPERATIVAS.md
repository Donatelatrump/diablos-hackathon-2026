> Documento historico de v3/v4. Para el modelo vigente, instrucciones y limites, consultar [README.md](../../README.md) y el [resultado v5](../../stuff_plus_output_v5/RESULTADO_MEJORA.md). Las afirmaciones de altitud y metricas de este documento no describen v5.

# Recomendaciones Operativas — Stuff+ Diablos Rojos (ISAC Hackathon 2026)

**Base:** modelo Stuff+ v3 entrenado con 635,002 lanzamientos de LMB (2024–2026)  
**Entorno:** Estadio Alfredo Harp Helú, CDMX (~2,240 msnm)

---

## 1. Qué perfiles de pitch ganan Stuff+ relativo en CDMX

### 1.1 Hallazgo principal

En altitud extrema (Harp Helú), el **Stuff+ medio es 100.99** vs. **98.32** a nivel del mar (+2.7 puntos). Esto significa que, en promedio, los lanzamientos en CDMX reciben una puntuación de Stuff+ ligeramente inflada respecto a estadios a nivel del mar. La razón física: la menor densidad del aire reduce el movimiento esperado (break), por lo que los modelos de Stuff+ entrenados con datos de nivel del mar subestiman el "stuff" necesario para tener éxito en CDMX.

### 1.2 Perfiles que GANAN valor relativo en altitud

Basado en el `perfil_ideal_diablos.json` (top 10% de Stuff+ en Harp Helú):

| Perfil | Característica | Por qué gana en CDMX |
|--------|---------------|---------------------|
| **Slider** | 13,868 pitches en elite (46% del top 10%) | Menor dependencia del efecto Magnus; el movimiento lateral se preserva mejor que el vertical en baja densidad |
| **Changeup** | 6,826 pitches en elite (23%) | Engaña por diferencial de velocidad vs. fastball, no por movimiento Magnus; responde menos a la altitud (H2 validada) |
| **Curveball** | 4,203 pitches en elite (14%) | Caída vertical reducida en altitud, pero sigue siendo efectivo como cambio de ojo |
| **Splitter** | 1,124 pitches en elite (4%) | Caída tardía, menos afectada por densidad del aire |

**Explicación física (H1 y H2):**
- La baja densidad reduce el efecto Magnus (responsable del break de ruptura). Los pitches que dependen menos del Magnus (changeup, splitter por diferencial de velocidad) mantienen o ganan Stuff+ relativo en CDMX.
- El slider, con movimiento principalmente horizontal, sufre menos degradación que el curveball (caída vertical pura).

### 1.3 Recomendación táctica

En Harp Helú, priorizar:
1. **Sliders** como pitch secundario principal (mayor presencia en elite).
2. **Changeups** con buen diferencial de velocidad vs. fastball (mínimo 8–10 mph de diferencia).
3. **Four-seam** con alta velocidad (93+ mph) — la velocidad se ve menos afectada por altitud que el movimiento.

---

## 2. Qué perfiles de pitch PIERDEN Stuff+ en altitud

### 2.1 Perfiles perjudicados

| Perfil | Por qué pierde en CDMX | Riesgo adicional |
|--------|----------------------|------------------|
| **Curveball de caída pura** | El break vertical se reduce ~20–25% por menor efecto Magnus | Más contactos elevados, mayor riesgo de jonrón |
| **Pitchers de fly ball** (alto GB% bajo) | Los fly balls viajan más lejos en baja densidad | Jonrones más frecuentes y más largos |
| **Pitches con movimiento vertical excesivo** (12–6 curve) | La caída esperada no se materializa; el bateador ajusta | Contacto sólido en zona alta |

### 2.2 Cuantificación del riesgo

Según la hipótesis H3 de la convocatoria y los datos observados:
- Los **groundball pitchers** son más valiosos en altitud: inducen rodados que evitan el costo del batazo elevado.
- En Harp Helú, un fly ball que sería out en nivel del mar tiene mayor probabilidad de convertirse en jonrón o doble.

**Recomendación:** Evitar fichar pitchers cuyo arsenal dependa principalmente de curveballs de caída grande o que tengan una tendencia natural a fly balls altos, a menos que complementen con slider o changeup de calidad.

---

## 3. Cómo perfilar un prospecto o agente libre para Diablos Rojos

### 3.1 Checklist de evaluación (usando Stuff+)

Al evaluar un pitcher para firmar o adquirir, revisar en este orden:

#### Paso 1: Stuff+ general y por altitud
- Consultar `stuff_plus_por_pitcher.csv` para ver su Stuff+ medio general.
- Revisar `delta_stuff_plus_extreme_vs_no_altitude`: si es negativo, el pitcher pierde calidad en CDMX.
- Umbral sugerido: Stuff+ ≥ 105 para titulares, ≥ 100 para relevistas.

#### Paso 2: Arsenal adecuado a altitud
Verificar que el pitcher tenga al menos uno de estos:
- Slider con Stuff+ alto (efectivo en altitud).
- Changeup con diferencial de velocidad ≥ 8 mph vs. fastball.
- Fastball de 93+ mph.

#### Paso 3: Perfil físico ideal (top 10% en Harp Helú)

| Feature | Rango ideal (elite CDMX) |
|---------|-------------------------|
| Velocidad | 84+ mph (media elite: 84.2 mph) |
| Spin rate | ~2,200 rpm (media elite: 2,243 rpm) |
| IVB | 0.48+ pulgadas |
| HB | 0.69+ pulgadas |
| Extensión | 5.8+ ft |
| Release height | 5.7+ ft |

**Nota:** La velocidad media del elite (84.2 mph) es inferior al promedio de MLB porque LMB tiene velocidades generalmente más bajas. El diferencial relativo importa más que el absoluto.

#### Paso 4: Mano lanzadora
- El top 10% en Harp Helú se compone de 81% diestros / 19% zurdos (24,241 vs 5,740 pitches). Esto refleja la distribución de lanzadores en LMB, no necesariamente una ventaja inherente. No usar como filtro excluyente.

### 3.2 Ejemplo de decisión de fichaje

| Candidato | Stuff+ general | Delta CDMX | Slider Stuff+ | Changeup diff | Recomendación |
|-----------|---------------|------------|---------------|---------------|---------------|
| Pitcher A | 112 | +3.5 | 118 | 10 mph | **Fichar** — gana en altitud, arsenal ideal |
| Pitcher B | 108 | −2.0 | 102 | 6 mph | **Evitar** — pierde en CDMX, cambio débil |
| Pitcher C | 100 | +1.0 | 115 | 9 mph | **Considerar** como relevista — slider elite compensa |

---

## 4. Plan de implementación para el staff de Diablos

### 4.1 Integración al workflow diario

1. **Pre-juego:** El pitching coach usa el dashboard (`dashboard_stuff_plus.py`) para simular cómo se comportarán los pitches de los abridores rivales en Harp Helú vs. estadio del rival.
2. **Post-juego:** Revisar Stuff+ real vs. esperado para identificar pitches que bajo-rendieron por ubicación (Location+) vs. por calidad física (Stuff+).
3. **Scouting:** Al evaluar agentes libres o prospectos, filtrar por `stuff_plus_por_pitcher.csv` y verificar `delta_stuff_plus_extreme_vs_no_altitude`.

### 4.2 Métricas de seguimiento recomendadas

| Métrica | Objetivo | Frecuencia |
|---------|----------|------------|
| Stuff+ medio del staff | ≥ 105 | Mensual |
| % de pitches con Stuff+ ≥ 110 | ≥ 25% | Por serie |
| Delta Stuff+ Harp Helú vs. mar | ≥ 0 (no penalizar en casa) | Por homestand |
| Groundball rate de pitchers de fly ball | Monitorear reducción | Por pitcher |

### 4.3 Limitaciones a comunicar al staff

- Stuff+ es una estimación de calidad física, no garantiza resultado (un pitch con Stuff+ 120 puede ser conectado).
- Los pesos del compuesto son iguales por ahora; deben revisarse con el staff técnico antes de usar en decisiones críticas.
- El modelo no incluye efectos de temperatura, humedad o viento específicos de cada juego.

---

## 5. Archivos de referencia para el staff

| Archivo | Uso |
|---------|-----|
| `dashboard_stuff_plus.py` | Ejecutar con `streamlit run app.py` para simular pitches |
| `stuff_plus_por_pitcher.csv` | Ranking y comparación de pitchers por altitud |
| `perfil_ideal_diablos.json` | Perfil físico objetivo para fichajes |
| `stuff_plus_output_v3/modelos/*.cbm` | Modelos CatBoost para integración en sistemas internos |
| `DOCUMENTO_TECNICO_STUFF_PLUS.md` | Documentación completa de metodología |

---

**Fin del documento.**  
ISAC Hackathon 2026 — Diablos Rojos del México
