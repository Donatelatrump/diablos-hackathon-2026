"""07_report.py — Reporte técnico HTML (y PDF vía Chromium). Versión compacta: cuerpo ≤10 páginas + anexo."""
import json, numpy as np, pandas as pd, os, sys
sys.path.insert(0, '/home/claude/stuffplus/src')
from report_lib import fig, table, shell
import plotly
OUT = '/home/claude/stuffplus/out'; DEL = '/home/claude/stuffplus/deliverables'
TEAM = 'Data Divas'
FE = {'Fastball-Ride': 'Recta con ride', 'Fastball-Run': 'Recta con run', 'Fastball-Cut': 'Recta con cut', 'Sinker': 'Sinker', 'Cutter': 'Cutter', 'Changeup': 'Changeup', 'Slider-Gyro': 'Slider gyro', 'Sweeper': 'Sweeper', 'Slurve': 'Slurve', 'Curveball': 'Curva'}
ORDER = ['Fastball-Ride', 'Fastball-Run', 'Fastball-Cut', 'Sinker', 'Changeup', 'Slider-Gyro', 'Sweeper', 'Slurve', 'Curveball']
meta = json.load(open(f'{OUT}/pipeline_meta.json')); alt = json.load(open(f'{OUT}/altitude_summary.json')); lw = json.load(open(f'{OUT}/linear_weights.json'))
metrics = json.load(open(f'{OUT}/metrics.json')); dec = json.load(open(f'{OUT}/deciles.json')); stab = json.load(open(f'{OUT}/stability.json')); sens = json.load(open(f'{OUT}/sensitivity_summary.json'))
eff = pd.read_csv(f'{OUT}/altitude_effects.csv'); fam = pd.read_csv(f'{OUT}/family_delta.csv', index_col=0); prof = pd.read_csv(f'{OUT}/ideal_profile.csv', index_col=0)
val = pd.read_csv(f'{OUT}/validation_table.csv'); heads = pd.read_csv(f'{OUT}/heads_table.csv'); shap_t = pd.read_csv(f'{OUT}/shap_importance.csv', index_col=0)
senst = pd.read_csv(f'{DEL}/sensibilidad_altitud_por_pitcher.csv', index_col=0); h3 = pd.read_csv(f'{OUT}/h3_rv_by_hittype.csv'); comp = pd.read_csv(f'{OUT}/arsenal_composition_by_quartile.csv', index_col=0)
o = alt['outcomes']; E, M, N = 'Extreme Altitude', 'Medium Altitude', 'No Altitude'
ext_eff = eff[eff.level == E].pivot(index='family', columns='var', values=['base_mean', 'delta', 'pct', 'n_pairs', 'se'])
fb_dist = alt['fb_distance_controlled']; hr_ctrl = alt['hr_rate_controlled_95_110_20_40']
h3p = h3.pivot(index='hit_type', columns='altitude_category', values='mean')
gap_sea = h3p.loc['FlyBall', N] - h3p.loc['GroundBall', N]; gap_ext = h3p.loc['FlyBall', E] - h3p.loc['GroundBall', E]
mean_delta = fam.delta_cf.mean(); fam_rel = (fam.delta_cf - mean_delta).round(1)
best_fam, worst_fam = fam_rel.idxmax(), fam_rel.idxmin()
v = lambda layer, scheme, k: metrics[f'{layer}_{scheme}'][k]
break_pct = abs(100 * (1 - alt[E]['break_ratio_obs'])); rho_pct = abs(100 * (1 - alt[E]['rho_rel_pred']))
ride_ivb = ext_eff.loc['Fastball-Ride', ('delta', 'InducedVertBreak')]; curve_ivb = ext_eff.loc['Curveball', ('delta', 'InducedVertBreak')]
n_pairs_cal = int(ext_eff[('n_pairs', 'RelSpeed')].sum())

# ---------- tablas ----------
t_eff = pd.DataFrame({'Familia': [FE[f] for f in ext_eff.index], 'IVB mar (in)': ext_eff[('base_mean', 'InducedVertBreak')].values, 'Δ IVB': ext_eff[('delta', 'InducedVertBreak')].values, 'HB mar (in)': ext_eff[('base_mean', 'hb_arm')].values, 'Δ HB': ext_eff[('delta', 'hb_arm')].values,
                      'Δ movimiento total': ext_eff[('pct', 'total_break')].values, 'Δ pérdida de velocidad (mph)': ext_eff[('delta', 'SpeedDrop')].values, 'Pares pitcher': ext_eff[('n_pairs', 'InducedVertBreak')].values.astype(int)}).set_index('Familia')
t_eff = t_eff.loc[[FE[f] for f in ORDER if FE[f] in t_eff.index]]
t_out = pd.DataFrame({'Nivel del mar': [o[N]['whiff_per_swing'], o[N]['gb'], o[N]['hard'], o[N]['hr_per_bip'], fb_dist[N]['mean'], hr_ctrl[N]['mean']], 'Altitud media': [o[M]['whiff_per_swing'], o[M]['gb'], o[M]['hard'], o[M]['hr_per_bip'], fb_dist[M]['mean'], hr_ctrl[M]['mean']],
                      'Harp Helú': [o[E]['whiff_per_swing'], o[E]['gb'], o[E]['hard'], o[E]['hr_per_bip'], fb_dist[E]['mean'], hr_ctrl[E]['mean']]},
                     index=['Swings fallidos por swing', 'Rollings por bola en juego', 'Contacto duro (≥95 mph) por bola en juego', 'Jonrones por bola en juego', 'Distancia de un batazo de 90–110 mph y 20–35° (ft)', 'Probabilidad de jonrón con 95–110 mph y 20–40°'])
for c in t_out.columns: t_out[c] = [f'{x:.1%}' if i != 4 else f'{x:.0f}' for i, x in enumerate(t_out[c])]
t_lw = pd.DataFrame({'Evento': ['Sencillo', 'Doble', 'Triple', 'Jonrón', 'Base por bolas', 'Golpeado', 'Ponche', 'Out en jugada'], 'LMB (este trabajo)': [lw['relative'][k] for k in ['1B', '2B', '3B', 'HR', 'BB', 'HBP', 'K', 'OUT']], 'Referencia MLB': [0.47, 0.77, 1.04, 1.40, 0.33, 0.34, -0.27, -0.27]}).set_index('Evento')
t_val = val.copy(); t_val['Mejora vs. nulo'] = t_val.Mejora_pct.map(lambda x: f'{x:+.1f}%'); t_val['Sesgo (carreras/pitch)'] = t_val.Sesgo.map(lambda x: '—' if pd.isna(x) else f'{x:+.4f}')
t_val = t_val[['Modelo', 'Esquema', 'RMSE_modelo', 'RMSE_nulo', 'Mejora vs. nulo', 'r', 'Sesgo (carreras/pitch)']].rename(columns={'RMSE_modelo': 'RMSE modelo', 'RMSE_nulo': 'RMSE nulo', 'r': 'r por pitch'})
t_heads = heads.copy(); t_heads['Mejora log-loss'] = t_heads.Mejora_pct.map(lambda x: f'{x:+.1f}%'); t_heads['Tasa base'] = t_heads.Tasa_base.map(lambda x: f'{x:.1%}')
t_heads = t_heads[['Target', 'AUC', 'LogLoss', 'LogLoss_nulo', 'Mejora log-loss', 'Tasa base', 'n']].rename(columns={'LogLoss_nulo': 'LogLoss nulo'}).set_index('Target')
t_fam = pd.DataFrame({'Familia': [FE[f] for f in fam.index], 'Stuff+ nivel del mar': fam.stuff_sea, 'Stuff+ Harp Helú': fam.stuff_cdmx_cf, 'Δ': fam.delta_cf, 'Δ vs. promedio': fam_rel.values, 'Δ observado': fam.delta_obs,
                      'Swing fallido': [f'{a:.1%} → {b:.1%}' for a, b in zip(fam.whiff_sea, fam.whiff_cdmx)], 'Rolling': [f'{a:.0%} → {b:.0%}' for a, b in zip(fam.gb_sea, fam.gb_cdmx)], 'Jonrón si hay contacto': [f'{a:.1%} → {b:.1%}' for a, b in zip(fam.hr_sea, fam.hr_cdmx)]}).set_index('Familia')
cols_s = {'stuff_sea': 'Stuff+ mar', 'stuff_cdmx': 'Stuff+ CDMX', 'delta_stuff': 'Δ observado', 'delta_expected': 'Δ esperado por arsenal', 'resilience': 'Resiliencia', 'arsenal': 'Arsenal'}
top = senst.head(8)[list(cols_s)].rename(columns=cols_s); bot = senst.tail(8).iloc[::-1][list(cols_s)].rename(columns=cols_s)
pr = prof.loc[[f for f in ORDER if f in prof.index]]
t_prof = pd.DataFrame({'Familia': [FE[f] for f in pr.index], 'Velocidad (p25–p75)': [f'{a:.1f}–{b:.1f}' for a, b in zip(pr.velo_top_p25, pr.velo_top_p75)], 'Velo liga': pr.velo_league_p50.map('{:.1f}'.format),
                       'IVB': [f'{a:.1f}–{b:.1f}' for a, b in zip(pr.ivb_top_p25, pr.ivb_top_p75)], 'IVB liga': pr.ivb_league_p50.map('{:.1f}'.format), 'HB': [f'{a:.1f}–{b:.1f}' for a, b in zip(pr.hb_top_p25, pr.hb_top_p75)], 'HB liga': pr.hb_league_p50.map('{:.1f}'.format),
                       'Spin': [f'{a:.0f}–{b:.0f}' for a, b in zip(pr.spin_top_p25, pr.spin_top_p75)], 'Stuff+ top / liga': [f'{a:.0f} / {b:.0f}' for a, b in zip(pr.stuff_top, pr.stuff_league)], 'Swing fallido top / liga': [f'{a:.0%} / {b:.0%}' for a, b in zip(pr.whiff_top, pr.whiff_league)], 'Rolling top / liga': [f'{a:.0%} / {b:.0%}' for a, b in zip(pr.gb_top, pr.gb_league)]}).set_index('Familia')
t_comp = (100 * comp.loc[['Q4 (mejor)', 'Q1 (peor)']][[c for c in ORDER if c in comp.columns]]).rename(columns=FE); t_comp.index = ['Cuartil superior en casa', 'Cuartil inferior en casa']

body = f"""
<div class="cover">
  <div class="brand"><i>S+</i> Sports Analytics Hackathon 2026 · ISAC · presentado por Diablos Rojos del México</div>
  <h1>Stuff+ calibrado para el Harp Helú</h1>
  <div class="lead">Un sistema que mide la calidad física de cada lanzamiento de la LMB, la traduce entre ambientes y cuantifica, con datos de la propia liga, qué pierde cada forma de pitch a 2,240 metros.</div>
  <div class="meta"><b>Equipo {TEAM}</b> · Reporte técnico · {meta['n_final']:,} lanzamientos Trackman, temporadas 2024–2026, {meta['n_pitchers']:,} pitchers anonimizados · Acompañado del dashboard simulador (HTML autocontenido)</div>
</div>

<h2 id="resumen">Resumen ejecutivo</h2>
<div class="kpis">
  <div class="kpi"><div class="v">−{break_pct:.0f}%</div><div class="k">de movimiento pierde el mismo pitcher con el mismo pitch en el Harp Helú</div></div>
  <div class="kpi"><div class="v">{mean_delta:+.0f}</div><div class="k">puntos de Stuff+ le quita el ambiente al pitch promedio; entre {fam.delta_cf.min():+.0f} y {fam.delta_cf.max():+.0f} según la forma</div></div>
  <div class="kpi"><div class="v">{gap_ext/gap_sea:.1f}×</div><div class="k">más caro un elevado respecto a un rolling en el Harp Helú que a nivel del mar</div></div>
</div>
<p><b>Qué construimos.</b> Tres modelos en capas (Stuff+, Location+, Pitching+) entrenados con {meta['n_final']:,} lanzamientos de la LMB. El objetivo es el valor esperado en carreras de cada pitch, calculado con pesos derivados de la propia liga. Para aislar el efecto del aire comparamos al mismo pitcher con el mismo pitch en distintos estadios. El índice resultante usa la escala 100 ± 10 por desviación estándar, es comparable entre ambientes y es más estable que el rendimiento observado: correlaciona {stab['stuff']:.2f} de un año al siguiente, contra {stab['rv_obs']:.2f} del run value.</p>
<p><b>Tres hallazgos.</b></p>
<ol>
<li><b>La altitud quita más movimiento del que predice la densidad del aire.</b> El mismo pitcher pierde {break_pct:.0f}% de movimiento en el Harp Helú (la física simple predice {rho_pct:.0f}%), mientras su velocidad y su spin no cambian. Una recta con ride pierde {abs(ride_ivb):.1f}" de elevación; una curva cae {curve_ivb:.1f}" menos.</li>
<li><b>Todas las formas pierden Stuff+ en casa, pero no por igual.</b> El slider gyro es el que menos pierde ({fam.loc['Slider-Gyro','delta_cf']:+.1f}) porque no depende del efecto Magnus. Las rectas con ride y run son las que más pierden ({fam.loc['Fastball-Ride','delta_cf']:+.1f} y {fam.loc['Fastball-Run','delta_cf']:+.1f}). El modelo anticipa la caída de cada pitcher a partir de su arsenal con r = {sens['corr_delta_expected']:.2f}.</li>
<li><b>El rolling vale más en casa porque el elevado cuesta más.</b> Un elevado en juego cuesta {h3p.loc['FlyBall', E]:.3f} carreras en el Harp Helú y {h3p.loc['FlyBall', N]:.3f} a nivel del mar. La misma pelota bateada viaja {fb_dist[E]['mean']-fb_dist[N]['mean']:.0f} ft más y la probabilidad de jonrón con buen contacto sube de {hr_ctrl[N]['mean']:.0%} a {hr_ctrl[E]['mean']:.0%}.</li>
</ol>
<p><b>Tres decisiones que cambian.</b> <b>Reclutamiento:</b> priorizar velocidad y pitches que no dependan del Magnus (slider gyro, cutter) sobre rectas de mucho ride y velocidad media. <b>Táctica en casa:</b> terminar turnos con slider gyro y changeup con caída; usar la curva para robar strikes. <b>Roles:</b> usar el índice de sensibilidad a la altitud para decidir quién lanza en casa; entre el pitcher más y menos afectado hay {abs(sens['delta_p10']-sens['delta_p90']):.0f} puntos de Stuff+ de diferencia.</p>

<h2 id="marco">1. Marco teórico</h2>
<p><b>Sabermetría.</b> Los índices de FanGraphs separan tres preguntas: qué tan bueno es un lanzamiento por su física en el release (Stuff+), qué tan bien está ubicado dado ese pitch, el conteo y el bateador (Location+), y cuánto vale la combinación (Pitching+). Todos se calibran contra un resultado esperado y no contra el observado, porque el resultado de un solo pitch es casi puro azar. Lo que sirve para decidir es un índice estable que predice.</p>
<p><b>Física.</b> Dos fuerzas aerodinámicas actúan sobre la pelota: el arrastre, que la frena, y la fuerza de Magnus, que la desvía según su spin. Ambas son proporcionales a la densidad del aire. A 2,240 m la densidad estándar es 0.80 de la de nivel del mar, así que la hipótesis base es que el movimiento por spin cae ~20%. Nathan estimó para Coors Field (1,609 m) que un pitch de 18" se mueve 14–15"; SABR documenta el exceso de carreras en estadios de altura. Faltaba medirlo en la LMB.</p>
<p><b>Por qué la LMB.</b> La liga tiene estadios en tres niveles de altitud bien poblados y sus pitchers lanzan en todos dentro de la misma temporada. Eso permite comparar el mismo brazo y el mismo pitch con distinto aire. Ningún dataset de MLB ofrece eso con un parque a 2,240 m.</p>

<h2 id="datos">2. Datos y calibración</h2>
<p>El dataset contiene {meta['n_raw']:,} lanzamientos Trackman de 2024–2026 con identificadores anonimizados y una categoría de altitud por juego: nivel del mar ({meta['alt_counts']['No Altitude']:,}), media ({meta['alt_counts']['Medium Altitude']:,}) y extrema ({meta['alt_counts']['Extreme Altitude']:,}). No hay columna de estadio, así que trabajamos con esos tres niveles. Después de filtrar categorías inválidas, tipos residuales, registros sin física y valores imposibles (velocidad fuera de 60–105 mph, spin fuera de 300–3,600 rpm, movimiento mayor a 30"), quedan <b>{meta['n_final']:,} lanzamientos</b> ({meta['dropped_pct']}% descartados) de {meta['n_pitchers']:,} pitchers. El movimiento horizontal, el lado del release y el eje de spin se reflejan para zurdos, de modo que "HB positivo" siempre significa "hacia el lado del brazo".</p>
<p><b>Chequeo de calibración.</b> Antes de atribuir nada a la altitud hay que descartar que el radar mida distinto en cada estadio. El test es físico: lo que el pitcher controla (velocidad de salida, spin, release) no debe cambiar entre ambientes; lo que el aire controla (pérdida de velocidad en el trayecto, movimiento) sí. La figura 1 compara al mismo pitcher con la misma familia de pitch en nivel del mar y altitud extrema ({n_pairs_cal:,} pares con al menos 25 lanzamientos en cada ambiente). La velocidad y el spin no cambian; la pérdida de velocidad cae 1.3 mph en las rectas. El tracking es consistente y el efecto que sigue es atmosférico.</p>
{fig('alt_calibration_check', 'Mismo pitcher, misma familia, dos ambientes. La velocidad de salida y el spin no cambian (diferencias menores a 0.5 mph y 40 rpm); la pérdida de velocidad entre el release y el plato sí.')}

<h2 id="altitud">3. El efecto altitud, cuantificado</h2>
<h3>3.1 Movimiento</h3>
{table(t_eff, 'Tabla 1. Cambio de movimiento del mismo pitcher al lanzar en altitud extrema, respecto a nivel del mar. HB en pulgadas hacia el lado del brazo. Para la curva, IVB negativo es caída: un Δ positivo significa menos caída.', fmt={'IVB mar (in)': '{:.1f}', 'Δ IVB': '{:+.1f}', 'HB mar (in)': '{:.1f}', 'Δ HB': '{:+.1f}', 'Δ movimiento total': '{:+.0f}%', 'Δ pérdida de velocidad (mph)': '{:+.2f}', 'Pares pitcher': '{:d}'})}
{fig('alt_delta_movement', 'Δ IVB y Δ HB por familia, con intervalos de confianza al 95%. Las rectas pierden ride y run; las rupturas pierden sweep; la curva pierde caída.')}
<p>Tres lecturas. El efecto es <b>proporcional</b>: cada familia pierde entre 23% y 32% de su movimiento, así que los pitches con más movimiento pierden más pulgadas. Es <b>monótono</b>: la altitud media pierde {abs(100*(1-alt[M]['break_ratio_obs'])):.0f}% y la extrema {break_pct:.0f}%. Y <b>supera la predicción simple por densidad</b> ({abs(100*(1-alt[M]['rho_rel_pred'])):.0f}% y {rho_pct:.0f}%), mientras que el arrastre sí la sigue casi exactamente ({alt[E]['speeddrop_ratio_obs']:.2f} observado contra {alt[E]['rho_rel_pred']:.2f} predicho). Las explicaciones probables son la no linealidad del coeficiente de sustentación, el aire caliente y húmedo de los parques costeros y que la categoría "media" agrupa parques de 1,500–2,100 m. El modelo no depende de resolverlo: usa los factores medidos por familia y nivel. El prior físico sirve de ancla: si los datos hubieran dicho −5% o −50%, habríamos buscado un error.</p>
{fig('alt_physics_ratio', 'Movimiento total y pérdida de velocidad respecto a nivel del mar, en los tres niveles, contra la predicción proporcional a la densidad del aire. El arrastre sigue la física; el movimiento la supera.')}
<p>Una consecuencia táctica: al perder ride, las rectas llegan con un ángulo más empinado ({ext_eff.loc['Fastball-Ride', ('delta','VertApprAngle')]:+.2f}° para la recta con ride) y las curvas con uno más plano ({ext_eff.loc['Curveball', ('delta','VertApprAngle')]:+.2f}°). La recta que "se levanta" en Veracruz es una recta ordinaria en CDMX.</p>
<h3>3.2 Bateo</h3>
{table(t_out, 'Tabla 2. Resultados del bateo por nivel de altitud. Las dos últimas filas controlan por la calidad del contacto y aíslan el efecto del aire sobre la pelota bateada.')}
<p>Con menos movimiento hay menos engaño: los swings fallidos bajan de {o[N]['whiff_per_swing']:.1%} a {o[E]['whiff_per_swing']:.1%}. El contacto duro sube y, sobre todo, la pelota bien bateada sale del parque con más frecuencia: {hr_ctrl[N]['mean']:.0%} → {hr_ctrl[E]['mean']:.0%} con velocidad de salida de 95–110 mph y ángulo de 20–40°. La tasa de rollings es <i>mayor</i> en altitud ({o[E]['gb']:.1%} contra {o[N]['gb']:.1%}) porque las rectas sin ride se batean hacia abajo, pero eso no compensa: el daño del elevado crece más que el beneficio del rolling.</p>
{fig('h3_rv_hittype', 'Costo en carreras de cada tipo de batazo por nivel de altitud (perspectiva del bateador: más alto es peor para el pitcher).')}
<p>La brecha de carreras entre un elevado y un rolling pasa de {gap_sea:.3f} a nivel del mar a {gap_ext:.3f} en el Harp Helú. A nivel de pitcher, sin embargo, la correlación entre tasa de rolling y jonrones permitidos se debilita en altitud (r = {alt['H3_gb_corr'][N]['corr_gb_hr']:.2f} contra {alt['H3_gb_corr'][E]['corr_gb_hr']:.2f}): en casa hasta los pitchers de rolling ven salir sus pocos elevados. El perfil de rolling protege, pero no inmuniza; la velocidad y el swing fallido siguen siendo la defensa principal.</p>

<h2 id="modelo">4. Modelo</h2>
<h3>4.1 Familias de pitch: forma sobre etiqueta</h3>
<p>La etiqueta de Trackman describe lo que el pitcher cree que tira; el bateador reacciona a lo que la pelota hace. Ajustamos una mezcla gaussiana de 12 componentes sobre la forma de cada pitch relativa a la recta primaria del pitcher (diferencial de velocidad, IVB, HB, velocidad, eje de spin, movimiento por rpm) y nombramos los componentes por su centroide físico en <b>nueve familias</b>: recta con ride, con run y con cut, sinker, changeup, slider gyro, sweeper, slurve y curva. Etiqueta y forma coinciden en el 70% de los casos. Las discrepancias importan: 27,810 de 137,835 "sliders" tienen forma de slurve o curva, y 24,459 de 109,206 "sinkers" se mueven como changeups. Todas las comparaciones por tipo usan la familia.</p>
<h3>4.2 Objetivo: xRunValue con pesos de la LMB</h3>
<p>Derivamos los <i>linear weights</i> por regresión de las carreras de cada media entrada completa ({lw['n_half_innings']:,} medias entradas) sobre sus eventos, centrados en el turno promedio. Se parecen a los de MLB, con menos valor por extrabase, como corresponde a una liga más ofensiva.</p>
{table(t_lw, 'Tabla 3. Linear weights derivados de la LMB (carreras sobre el turno promedio) y referencia MLB.', fmt={'LMB (este trabajo)': '{:+.3f}', 'Referencia MLB': '{:+.2f}'})}
<p>Con ellos calculamos la run expectancy por conteo (un 3-0 vale +0.16 carreras para el bateador; un 0-2, −0.10) y el run value de cada pitch: cambio de expectativa para bolas, strikes y fouls, y valor del evento para pitches que terminan el turno. Para bolas en juego sustituimos el resultado real por su valor esperado dado velocidad de salida, ángulo, dirección y altitud (modelo auxiliar, R² = 0.51); así un sencillo de suerte y una línea atrapada valen lo mismo. Ese <b>xRunValue</b> reduce la desviación estándar del objetivo de 0.198 a 0.150 carreras por pitch. El objetivo se expresa desde la perspectiva del pitcher: positivo es bueno.</p>
<h3>4.3 Tres capas</h3>
<ul>
<li><b>Stuff+:</b> solo física en el release y ambiente: velocidad, spin, eje, IVB, HB, movimiento total, movimiento por rpm, altura y lado de release, extensión, mano, nivel de altitud. Sin ubicación, conteo ni bateador.</li>
<li><b>Location+:</b> ubicación continua y por zona, conteo, lado del bateador, familia de pitch, mano, altitud.</li>
<li><b>Pitching+:</b> todo lo anterior más el arsenal: diferenciales de velocidad, IVB y HB respecto a la recta primaria (calculados en el mismo ambiente para que la altitud no contamine el diferencial), distancia del release y del ángulo de salida respecto a la recta (túnel), uso del pitch, tamaño del repertorio, pitch anterior en el turno y número de pitch.</li>
</ul>
<p><b>Algoritmo.</b> LightGBM (400 árboles, 63 hojas, tasa 0.05, mínimo 300 observaciones por hoja, submuestreo 0.8, L2 = 5) con pérdida cuadrática sobre xRunValue, más ocho modelos binarios con pérdida logística para los targets multi-objetivo: swing, swing fallido, chase, strike cantado y, condicionales a bola en juego, rolling, contacto duro, barril y jonrón. Gradient boosting captura las interacciones no lineales entre velocidad, movimiento y eje sin imponer una forma, y SHAP lo hace explicable. No usamos identificadores de pitcher ni de bateador: el modelo debe funcionar con brazos que no ha visto.</p>
<h3>4.4 Escala</h3>
<div class="eq">score(p)  = f̂(x_p)                        valor esperado en carreras dado el vector físico x_p y el ambiente
Stuff+(p) = 100 + 10 · (score − μ_mar) / σ_mar   escala absoluta; μ y σ sobre todos los pitches a nivel del mar, 2024–2026
Stuff+adj = 100 + 10 · (score − μ_año,nivel) / σ_año,nivel   100 = promedio de ese año en ese ambiente</div>
<p>La escala absoluta cuantifica el efecto altitud: el mismo pitch vale 104 en Veracruz y 92 en casa. La ajustada compara a un pitcher con sus pares en el mismo aire. El dashboard muestra ambas. Para evaluar "el mismo pitch" en el Harp Helú a partir de una medición a nivel del mar, multiplicamos IVB y HB por los factores de su familia (tabla 1), recalculamos el movimiento total y fijamos el nivel de altitud en extremo.</p>

<h2 id="validacion">5. Validación fuera de muestra</h2>
<p>Tres esquemas contra el baseline nulo de la convocatoria (xRunValue promedio por conteo): <b>pitcher holdout</b> (5 particiones; ningún pitcher del test está en entrenamiento), <b>season holdout</b> (entrenar con 2024–2025, predecir 2026) y <b>park holdout</b> en dos variantes: entrenar sin altitud extrema y predecir CDMX, y entrenar sin altitud media y predecirla.</p>
{table(t_val, 'Tabla 4. RMSE de xRunValue (carreras por pitch) y correlación por pitch. Sesgo = media predicha menos media real en el estadio excluido.', index=False)}
<p>Pitching+ y Location+ reducen el error 2–3% en todos los esquemas y correlacionan 0.20–0.23 por pitch, en línea con los modelos públicos: el resultado de un pitch individual es casi todo ruido. Stuff+ puro apenas mueve el error por pitch porque la física no sabe si el pitch fue bola; su valor aparece al ordenar y al agregar (figuras 6 y 7). El park holdout es el dato clave: un modelo que nunca vio CDMX predice allí con sesgo de {v('stuff','park_holdout_extreme','bias_mean_pred_minus_actual')*100:+.2f} carreras por 100 pitches, es decir, sobreestima la calidad del pitcheo en casa. Con datos de CDMX el sesgo desaparece. Ese es el costo de usar un Stuff+ entrenado a nivel del mar para decidir en altura.</p>
{fig('deciles', 'Discriminación en pitcher holdout. Del decil 1 al 10 del Stuff+, el xRunValue real pasa de ' + f'{dec["Stuff+"]["xrv_d1"]:+.2f}' + ' a ' + f'{dec["Stuff+"]["xrv_d10"]:+.2f}' + ' carreras por 100 pitches y el swing fallido de ' + f'{dec["Stuff+"]["whiff_d1"]:.0%}' + ' a ' + f'{dec["Stuff+"]["whiff_d10"]:.0%}' + '. Pitching+ abre la brecha a ' + f'{dec["Pitching+"]["xrv_d1"]:+.1f}' + ' / ' + f'{dec["Pitching+"]["xrv_d10"]:+.1f}' + '.')}
<p>Los modelos de probabilidad están calibrados por deciles (anexo, tabla A1): swing fallido con AUC 0.76, chase 0.91, strike cantado 0.88; rolling y contacto duro 0.64–0.66, ruidosos por naturaleza pero por encima del nulo.</p>
{fig('stability', 'Correlación año a año por pitcher (al menos 300 pitches cada año, ' + f'{stab["n_pairs"]}' + ' pares). El Stuff+ fuera de muestra es 3.5 veces más estable que el run value observado.')}
<p>Un índice debe medir talento, no suerte. El Stuff+ fuera de muestra correlaciona {stab['stuff']:.2f} consigo mismo al año siguiente; el run value observado, {stab['rv_obs']:.2f}. Y predice mejor el futuro: el Stuff+ de este año anticipa el run value del próximo con r = {stab['stuff_a_vs_rvobs_b']:.2f} (Pitching+: {stab['pitching_a_vs_rvobs_b']:.2f}), mientras que el run value solo se predice a sí mismo con {stab['rvobs_a_vs_rvobs_b']:.2f}.</p>

<h2 id="delta">6. Δ Stuff+ por forma de pitch y sensibilidad por pitcher</h2>
{fig('family_delta_stuff', 'Δ Stuff+ por familia: el mismo pitch trasladado al Harp Helú por el modelo (azul) y lo observado en los pitchers que lanzaron en ambos ambientes (naranja). La coincidencia valida el método.')}
{table(t_fam, 'Tabla 5. Stuff+ del mismo pitch a nivel del mar y en el Harp Helú, por familia, con la descomposición en probabilidades. Δ vs. promedio: positivo = la forma resiste mejor que el promedio (' + f'{mean_delta:+.1f}' + ').', fmt={'Stuff+ nivel del mar': '{:.1f}', 'Stuff+ Harp Helú': '{:.1f}', 'Δ': '{:+.1f}', 'Δ vs. promedio': '{:+.1f}', 'Δ observado': '{:+.1f}'})}
<p>El ambiente le quita {abs(mean_delta):.0f} puntos al pitch promedio, el mismo número para el abridor estrella y para el relevista de emergencia. Lo que cambia entre formas es menor pero decide el repertorio de casa. <b>{FE[best_fam]}</b> resiste mejor ({fam_rel[best_fam]:+.1f} respecto al promedio): tiene poco movimiento Magnus que perder y su engaño viene del eje y la velocidad. <b>{FE[worst_fam]}</b> y la recta con ride son las más castigadas: viven de 16–17" de elevación que en CDMX se convierten en 12–13", y el bateador las ve como rectas planas. El changeup conserva su diferencial de velocidad pero pierde más HB que cualquier recta, así que queda en el promedio: la hipótesis H2 se cumple solo en relación con las rectas.</p>
{fig('sensitivity_scatter', 'Stuff+ del mismo pitcher a nivel del mar y en el Harp Helú (' + f'{sens["n_pitchers"]}' + ' pitchers con al menos 150 pitches en ambos). La distancia a la diagonal es su sensibilidad.')}
<p>Entre {sens['n_pitchers']} pitchers con muestra suficiente en ambos ambientes, la caída media es {sens['delta_mean']:+.1f} puntos y va de {sens['delta_p10']:+.1f} (percentil 10) a {sens['delta_p90']:+.1f} (percentil 90). El modelo anticipa la caída individual a partir del arsenal medido a nivel del mar con r = {sens['corr_delta_expected']:.2f}: sabe de antemano quién va a sufrir en casa. La diferencia entre lo observado y lo esperado (resiliencia) señala a quienes se adaptan mejor o peor de lo que su repertorio predice. Los más consistentes se apoyan en slider gyro, recta con cut y sinker; los más afectados dependen de changeups y rectas con mucho run. El ranking completo está en <i>sensibilidad_altitud_por_pitcher.csv</i> y en el mapa del dashboard.</p>

<h2 id="perfil">7. Perfil físico ideal para Diablos Rojos</h2>
{fig('shap_importance', 'Importancia SHAP del modelo Stuff+, calculada por separado sobre pitches a nivel del mar y en altitud extrema.')}
<p>El nivel de altitud es la variable más influyente, seguida de velocidad, IVB, HB y eje de spin. En CDMX la velocidad y el eje ganan peso y el movimiento total lo pierde: cuando el aire recorta el movimiento de todos, lo que separa a un pitch de otro es la velocidad, que el aire no toca, y la orientación del eje, que decide en qué dirección se gasta el poco Magnus que queda.</p>
{fig('pdp_curves', 'Curvas de respuesta del Stuff+ en los dos ambientes. La pendiente en velocidad es igual o mayor en altitud; la pendiente en IVB es menor: cada pulgada de ride vale menos en CDMX.')}
<p>El decil superior de Stuff+ en el Harp Helú (anexo, tabla A2) dibuja el perfil:</p>
<ul>
<li><b>Rectas:</b> ~3 mph más que la mediana ({pr.loc['Fastball-Ride','velo_top_p50']:.1f} contra {pr.loc['Fastball-Ride','velo_league_p50']:.1f}) y 1.5–2.5" más de IVB ya en CDMX. La recta ideal combina 94+ mph con ride suficiente para seguir "levantándose" después de perder 4". La recta con cut es la que mejor resiste.</li>
<li><b>Sinker:</b> velocidad ({pr.loc['Sinker','velo_top_p50']:.1f} contra {pr.loc['Sinker','velo_league_p50']:.1f}) y más run; su valor en casa es el rolling ({pr.loc['Sinker','gb_top']:.0%} en el decil superior), no el swing fallido.</li>
<li><b>Changeup:</b> los mejores en CDMX tienen <b>menos</b> movimiento que la mediana (IVB {pr.loc['Changeup','ivb_top_p50']:.1f}" contra {pr.loc['Changeup','ivb_league_p50']:.1f}"): cambios con caída y diferencial de {pr.loc['Changeup','vdiff_top_p50']:+.1f} mph que no dependen del Magnus.</li>
<li><b>Slider gyro:</b> la familia con mejor Stuff+ en casa ({pr.loc['Slider-Gyro','stuff_top']:.0f} en el decil superior). {pr.loc['Slider-Gyro','velo_top_p50']:.1f}+ mph, poco movimiento en ambas direcciones, {pr.loc['Slider-Gyro','vdiff_top_p50']:+.1f} mph respecto a la recta.</li>
<li><b>Sweeper, slurve y curva:</b> llegan al decil superior solo las que conservan {abs(pr.loc['Sweeper','hb_top_p50']):.0f}"+ de sweep o {abs(pr.loc['Curveball','ivb_top_p50']):.0f}"+ de caída después de perder un cuarto del movimiento; es decir, las que a nivel del mar son excepcionales.</li>
</ul>
<p>Comparamos también el repertorio de los pitchers del cuartil superior e inferior de Pitching+ en casa: la diferencia es pequeña ({100*comp.loc['Q4 (mejor)','Slider-Gyro']:.0f}% contra {100*comp.loc['Q1 (peor)','Slider-Gyro']:.0f}% de slider gyro; {100*comp.loc['Q4 (mejor)','Sinker']:.0f}% contra {100*comp.loc['Q1 (peor)','Sinker']:.0f}% de sinker). No existe una receta de arsenal que compense pitches mediocres; existe un perfil físico por pitch que resiste mejor, y el repertorio se construye con pitches que lo cumplan.</p>

<h2 id="recomendaciones">8. Recomendaciones operativas</h2>
<p><b>Lo que gana en CDMX.</b> El slider gyro duro ({fam_rel['Slider-Gyro']:+.1f} respecto al promedio) y la recta con cut ({fam_rel['Fastball-Cut']:+.1f}), porque su movimiento depende poco del Magnus, y la velocidad en cualquier familia, porque el aire no la toca y gana peso cuando el movimiento se iguala hacia abajo.</p>
<p><b>Lo que pierde, y cuánto riesgo añade.</b> Las rectas con run y con ride de velocidad media ({fam_rel['Fastball-Run']:+.1f} y {fam_rel['Fastball-Ride']:+.1f}): su swing fallido cae de {fam.loc['Fastball-Ride','whiff_sea']:.1%} a {fam.loc['Fastball-Ride','whiff_cdmx']:.1%} y su jonrón por contacto sube de {fam.loc['Fastball-Ride','hr_sea']:.1%} a {fam.loc['Fastball-Ride','hr_cdmx']:.1%}; una recta de 90 mph con 17" de ride en Veracruz es un pitch promedio en casa. El sinker con mucho run pierde 4" de HB. Sweeper y curva como pitch principal pierden 25–30% de su forma: sirven para robar strikes, no para terminar turnos. Para el pitch promedio, el contacto duro sube {100*(o[E]['hard']-o[N]['hard']):+.1f} puntos y el jonrón por elevado pasa de {o[N]['hr_per_fb']:.1%} a {o[E]['hr_per_fb']:.1%}: un pitcher con 35% de elevados permite en casa {100*0.35*(o[E]['hr_per_fb']-o[N]['hr_per_fb']):.1f} jonrones más por cada 100 bolas en juego, solo por el aire.</p>
<p><b>Cómo perfilar un prospecto o agente libre.</b></p>
<ol>
<li>Pedir la medición Trackman o Rapsodo y el ambiente donde se tomó. El dashboard traslada el movimiento al Harp Helú con los factores de la tabla 1.</li>
<li>Evaluar cada pitch en la escala ajustada de CDMX: 105 o más es un activo; 95 o menos es un pasivo aunque luzca en la costa.</li>
<li>Exigir al menos un pitch de out que no dependa del Magnus (slider gyro, cutter, changeup con caída) y una recta de 93+ mph. Si la recta es de 90–92, pedir 16"+ de IVB a nivel del mar o un sinker que genere rolling.</li>
<li>Descontar las rupturas de mucho movimiento un 25–30% antes de valorarlas. ¿Este sweeper de 16" sigue siendo bueno con 11"? El perfilador del dashboard responde con comparables reales.</li>
<li>Usar el índice de sensibilidad para asignar roles: pitchers de Δ pequeño para cerrar y abrir en casa; pitchers de Δ grande para series fuera, o en casa con secuencias que escondan la pérdida.</li>
</ol>
<div class="callout"><b>En una frase para el pitching coach:</b> en el Harp Helú la velocidad y el eje gyro son lo único que el aire no se lleva. Construye el repertorio de casa alrededor de eso, usa las rupturas de mucho movimiento para robar strikes y acepta que el rolling protege menos de lo que parece.</div>

<h2 id="fronteras">9. Alcance y fronteras</h2>
<ul>
<li><b>Tres niveles de altitud, no estadios.</b> El dataset entrega una categoría por juego, sin estadio ni temperatura. Con estadio y clima, la densidad del aire sería una variable continua y el traslado sería por partido.</li>
<li><b>Sin eficiencia de spin medida.</b> Usamos movimiento por rpm como aproximación; el seam-shifted wake, que no depende del Magnus, no es observable directamente.</li>
<li><b>Secuencia aproximada.</b> No hay número de pitch dentro del turno; reconstruimos el orden por la progresión del conteo.</li>
<li><b>El run value por pitch es ruidoso por naturaleza.</b> Las correlaciones por pitch de 0.05–0.23 son el techo del problema, no del modelo; la utilidad del índice está en su estabilidad y poder predictivo a nivel pitcher.</li>
<li><b>No es un modelo causal.</b> Describe qué pitches rinden; no dice qué pasaría si un pitcher cambiara su agarre. Un causal forest táctico es la extensión natural.</li>
<li><b>Sin datos personales.</b> Todo el análisis es de rendimiento físico con identificadores anonimizados, para uso del cuerpo técnico.</li>
</ul>

<h2 id="anexo">Anexo</h2>
<h3>A. Tablas y figuras complementarias</h3>
{table(t_heads, 'Tabla A1. Modelos de probabilidad (features de Pitching+, pitcher holdout). Swing, chase y strike cantado se predicen muy bien porque dependen de la ubicación; los de contacto son ruidosos pero superan al nulo, salvo el barril, cuya tasa base deja poco margen.', fmt={'AUC': '{:.3f}', 'LogLoss': '{:.3f}', 'LogLoss nulo': '{:.3f}', 'n': '{:,}'})}
{table(t_prof, 'Tabla A2. Perfil físico del decil superior de Stuff+ en altitud extrema (rango p25–p75) y mediana de la liga en el mismo ambiente. Movimiento ya en condiciones de CDMX.')}
<h3>B. Entregables</h3>
<ul>
<li><b>dashboard_stuff_plus_lmb.html:</b> simulador autocontenido, sin servidor. Mismo pitch a nivel del mar y en el Harp Helú con descomposición en probabilidades, qué pierde cada forma, mapa de movimiento de la liga y perfilador de prospectos con comparables reales.</li>
<li><b>stuff_plus_por_pitch.csv.gz:</b> Stuff+, Location+, Pitching+ (absolutos y ajustados), xRunValue, probabilidades y Stuff+ contrafactual en CDMX por lanzamiento. <b>stuff_plus_por_pitcher_familia.csv</b>, <b>arsenales_harp_helu.csv</b> y <b>sensibilidad_altitud_por_pitcher.csv:</b> agregados por pitcher.</li>
<li><b>Código</b> (Python, LightGBM, scikit-learn, Plotly): limpieza y clustering, efecto altitud, linear weights y targets, entrenamiento y validación, scores y perfil, dashboard y reporte. Semillas fijas; ejecución completa en ~20 minutos.</li>
</ul>
<p class="small">Referencias: Nathan, A., <i>The Physics of Baseball</i> y notas sobre Coors Field; SABR, <i>High Altitude Offense</i>; FanGraphs, Stuff+/Location+/Pitching+ (Sarris y Bay); Tango, Lichtman y Dolphin, <i>The Book</i>; Huang y Hsu (2021); Ke et al. (2017), LightGBM; Lundberg y Lee (2017), SHAP; atmósfera estándar ISO 2533.</p>
"""
html = shell('Stuff+ calibrado para el Harp Helú · Reporte técnico · Data Divas', body)
plotly_path = os.path.join(os.path.dirname(plotly.__file__), 'package_data', 'plotly.min.js')
open(f'{DEL}/reporte_tecnico_stuff_plus_lmb.html', 'w').write(html.replace('<script src="__PLOTLY__"></script>', '<script>' + open(plotly_path).read() + '</script>'))
open(f'{OUT}/report_cdn.html', 'w').write(html.replace('__PLOTLY__', 'https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.35.2/plotly.min.js'))
print('report MB', round(os.path.getsize(f'{DEL}/reporte_tecnico_stuff_plus_lmb.html') / 1e6, 2))
