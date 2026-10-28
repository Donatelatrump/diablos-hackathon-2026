"""
Genera public/reporte.html a partir de los resultados del pipeline. Las cifras se leen de los JSON de
resultados; las de la verificacion fisica (seccion 6.2) vienen de verificacion_sin_etiquetas.py.
Uso: python3 gen_reporte.py <raiz del repo>
"""
import json, sys, os
R = sys.argv[1] if len(sys.argv) > 1 else ".."
J = lambda p: json.load(open(p))
meta = J(f"{R}/public/data/meta.json"); av = J(f"{R}/public/data/arsenal_validation.json")
pv = meta["projection_validation"]; cal = meta["calibration"]; lev = meta["levers"]; V = meta["validation"]
rob = J("robustez.json"); con = J("contacto.json"); tp = J("target_params.json")
EQUIPO = os.environ.get("EQUIPO", "[EQUIPO: nombres de los integrantes]")
TIPOS = ["Four-Seam", "Sinker", "Slider", "Changeup", "Curveball", "Cutter"]
ES = {"Four-Seam": "Recta 4 costuras", "Sinker": "Sinker", "Slider": "Slider", "Changeup": "Cambio",
      "Curveball": "Curva", "Cutter": "Cutter"}
f1 = lambda x: f"{x:.1f}"; f2 = lambda x: f"{x:.2f}"; sg = lambda x, d=1: f"{x:+.{d}f}".replace("-", "−")
num = lambda x, d=0: f"{x:,.{d}f}"
pct = lambda x: f"{x:.0f}%"
def cls(x, t=0.05): return ' class="pos"' if x > t else (' class="neg"' if x < -t else "")

ds = meta["dataset"]; P = meta["physics"]; per = meta["perfil"]; pm = meta["perdida_mov_tipo"]
alt_m = {k: v["h"] for k, v in meta["sedes"].items()}
ss = V["small_sample"]; ss25 = next(r for r in ss if r["N"] == 25)
yy = V["year_to_year"]; lad = V["ladder"]
c10 = cal["por_10_puntos"]
robp = rob["pitcher_holdout"]; pe = rob["park_holdout_estricto"]
pe_sin = sum(v["corr_sin_ver_sede"] for v in pe.values()) / 3; pe_con = sum(v["corr_viendo_sede"] for v in pe.values()) / 3
shap = {k: v for k, v in rob["shap"]["global"].items() if k != "alt"}
LAB = {"RelSpeed": "velocidad", "ivb": "mov. vertical (IVB)", "hb_arm": "mov. horizontal (HB)", "SpinRate": "giro",
       "spin_axis_m": "eje de giro", "Extension": "extensión", "RelHeight": "altura de liberación",
       "rel_side_arm": "lado de liberación", "fb_relspeed": "velocidad de la recta", "fb_ivb": "IVB de la recta",
       "d_velo": "Δ velocidad vs. recta", "d_ivb": "Δ IVB vs. recta", "d_hb": "Δ HB vs. recta", "d_axis": "Δ eje vs. recta"}
shap_rank = list(shap); spin_rank = shap_rank.index("SpinRate") + 1
tot = con["total"][0]; h3 = con["h3"]; gbfb = h3["elevado_menos_rodado"]; h3c = h3["corr_rodados_vs_carreras"]
ct = {r["tipo"]: r for r in con["por_tipo"]}; ride = {r["perfil"]: r for r in con["recta_por_ride"]}
dproj = {r["tipo"]: r["delta"] for r in meta["delta_tipo_proyectado"]}
dobs = {r["tipo"]: (r["mean"], r["size"]) for r in meta["delta_tipo_observado"]}
vr = pv["vs_resultado_real"]; avr = av["vs_resultado_real"]

def bars(rows, maxv, legend=None):
    h = '<div class="bars">'
    for lab, val, txt, c in rows:
        h += f'<span>{lab}</span><div class="track"><div class="fill {c}" style="width:{100*abs(val)/maxv:.1f}%"></div></div><span>{txt}</span>'
    return h + "</div>" + (f'<div class="legend">{legend}</div>' if legend else "")

def ic(r):
    lo, hi = r["hr_ic95"]
    return f"{sg(r['hr_riesgo_pct'],0)}% <span class=\"note\">[{sg(lo,0)}, {sg(hi,0)}]</span>"

def palancas(t, n=3):
    L = lev["efecto"]["2"][t]; out = []
    T = {"RelSpeed": lambda c: f"{abs(c):g} mph {'más rápido' if c > 0 else 'más lento'}",
         "ivb": lambda c: f"{abs(c):g} in {'más de elevación' if c > 0 else 'más de caída'}",
         "hb_arm": lambda c: f"{abs(c):g} in hacia el lado {'del brazo' if c > 0 else 'del guante'}",
         "SpinRate": lambda c: f"{abs(c):g} rpm {'más' if c > 0 else 'menos'} de giro",
         "spin_axis_m": lambda c: f"eje {sg(c,0)}°", "Extension": lambda c: f"{abs(c):g} ft más de extensión"}
    for k, st in lev["pasos"].items():
        up = L[k]["mas"] >= L[k]["menos"]; g = max(L[k]["mas"], L[k]["menos"])
        if k == "Extension" and not up: continue
        out.append((g, T[k](st if up else -st)))
    return sorted(out, reverse=True)[:n]

css = open("reporte_css.css").read()
H = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Stuff+ calibrado por altitud · Reporte técnico</title><style>{css}</style></head><body><main>

<p class="tag">ISAC 2026 · Reto Diablos Rojos · Documento técnico</p>
<h1>Stuff+ calibrado por altitud para la Liga Mexicana de Béisbol</h1>
<p class="sub">{EQUIPO} · Dashboard: stuffplus-lmb.vercel.app · Datos Trackman LMB {ds['temporadas'][0]}–{ds['temporadas'][-1]} (pitchers anónimos)</p>

<div class="box"><p class="lead"><b>En una frase:</b> en la Ciudad de México el aire delgado le quita en promedio una cuarta parte del movimiento a cada lanzamiento, pero no a todos por igual. Construimos un Stuff+ que entiende esa física y un simulador que anticipa cómo rendirá en el Estadio Alfredo Harp Helú cualquier lanzamiento o arsenal, validado con pitchers que el modelo nunca vio.</p></div>

<div class="kpis">
<div class="kpi"><b>{num(ds['lanzamientos'])}</b><span>lanzamientos de {num(ds['pitchers'])} pitchers en {num(ds['juegos'])} juegos</span></div>
<div class="kpi"><b>{sg(pm['observado_promedio'],1)}%</b><span>movimiento perdido en altitud extrema, mismo pitcher y lanzamiento</span></div>
<div class="kpi"><b>{pct(pv['reduccion_error_pct'])}</b><span>menos error al anticipar el Stuff+ de un pitcher en altitud</span></div>
<div class="kpi"><b>{ss25['stuff']/ss25['rv']:.1f}×</b><span>mejor que el resultado real con solo 25 lanzamientos</span></div>
</div>

<h2 class="keep">1. Resumen para la toma de decisiones</h2>
<p><b>Qué es.</b> Stuff+ califica qué tan difícil de batear es un lanzamiento solo por cómo sale de la mano y cómo se mueve. 100 es el promedio de la liga en ese tipo de sede; cada 10 puntos son una desviación estándar. En el campo, <b>10 puntos equivalen a {sg(c10['whiff_pct'])} puntos porcentuales de fallos por swing y {f1(cal['carreras_por_1000_lanz_por_10_puntos'])} carreras menos por cada 1,000 lanzamientos</b>.</p>
<p><b>Qué cambia en la CDMX.</b> Todos los lanzamientos pierden movimiento; la pregunta útil es quién pierde menos. La recta de cuatro costuras pierde terreno relativo ({sg(dproj['Four-Seam'])} puntos proyectados); slider y cutter lo ganan ({sg(dproj['Slider'])} y {sg(dproj['Cutter'])}), y la proyección física coincide con lo observado. Además, en altitud un batazo elevado cuesta casi el triple que un rodado y los jonrones por bola en juego suben {sg(tot['hr_riesgo_pct'],0)}%.</p>
<p><b>Cómo usarlo.</b> Para firmar o reforzar, ordenar candidatos por su <b>Stuff+ proyectado en el Harp Helú</b>: con solo sus lanzamientos a nivel del mar, el simulador anticipa sus resultados en altitud tan bien como si ya lo hubiéramos visto lanzar allá. Para un pitcher nuevo, confiar en Stuff+ desde los primeros 25–50 lanzamientos.</p>

<h2>2. Marco teórico e hipótesis</h2>
<p><b>Sabermetría.</b> El valor de un lanzamiento se mide en carreras: cuánto cambia la expectativa de carreras del turno al mover el conteo o terminarlo (Tango, Lichtman y Dolphin, 2007). Un modelo de "stuff" predice ese valor solo con las propiedades físicas del lanzamiento, separándolo de la ubicación, el bateador y el azar.</p>
<p><b>Física.</b> El giro de la pelota empuja el aire (fuerza de Magnus) y la curva; con menos aire, hay menos curva y menos arrastre (Nathan; SABR, "High altitude offense"). Según la atmósfera estándar, el aire del Harp Helú ({num(alt_m['Harp Helu'])} m) es {100*(1-meta['sedes']['Harp Helu']['rho']/1.225):.0f}% menos denso que a nivel del mar.</p>
<p><b>La LMB.</b> El dataset no identifica estadios sino tres categorías de altitud definidas por Diablos; con su tabla de sedes, sus altitudes promedio son {num(alt_m['No Altitude'])}, {num(alt_m['Medium Altitude'])} y {num(alt_m['Extreme Altitude'])} m. La CDMX está en la categoría extrema junto con León, Durango, Puebla, Aguascalientes y Querétaro.</p>
<div class="tw"><table>
<tr><th class="l">Hipótesis de la convocatoria</th><th class="l">Veredicto con datos de la LMB</th></tr>
<tr><td class="l">H1. La baja densidad reduce el movimiento inducido por giro</td><td class="l"><b>Confirmada y más fuerte de lo esperado:</b> {sg(pm['observado_promedio'],1)}% de movimiento contra {sg(pm['lineal_densidad'],1)}% que predice la densidad sola; la fuerza que curva la pelota cae como densidad<sup>{P['p_magnus_global']:.2f}</sup> (sección 6).</td></tr>
<tr><td class="l">H2. Los lanzamientos de diferencial de velocidad (cambio) mantienen o ganan Stuff+</td><td class="l"><b>Se mantiene, no gana:</b> el cambio es el que más movimiento pierde ({sg(pm['observado']['Changeup'])}%), pero su recta pierde también y su Stuff+ relativo queda estable ({sg(dproj['Changeup'])} proyectado, {sg(dobs['Changeup'][0])} observado). Cuando lo batean, su riesgo de jonrón sube {sg(ct['Changeup']['hr_riesgo_pct'],0)}%.</td></tr>
<tr><td class="l">H3. Los pitchers de rodados valen más en altitud</td><td class="l"><b>Respaldada:</b> un elevado cuesta {f2(gbfb['extrema'])} carreras más que un rodado en altitud extrema contra {f2(gbfb['mar'])} a nivel del mar; el % de rodados de un pitcher predice las carreras que permite en altitud (correlación {f2(h3c['extrema']['corr'])}, IC95 {f2(h3c['extrema']['ic95'][0])}–{f2(h3c['extrema']['ic95'][1])}) pero no a nivel del mar ({f2(h3c['mar']['corr'])}, IC95 {f2(h3c['mar']['ic95'][0])}–{f2(h3c['mar']['ic95'][1])}).</td></tr>
<tr><td class="l">H4. El giro (rpm) solo es insuficiente; importa la forma</td><td class="l"><b>Confirmada:</b> el giro es la variable física número {spin_rank} por contribución SHAP; dominan el movimiento y las diferencias contra la recta. La etiqueta de tipo de lanzamiento se descarta porque la propia altitud la contamina (sección 6.2).</td></tr>
</table></div>

<h2>3. Decisiones de modelado</h2>
<h3>3.1 Objetivo: valor de carrera de cada lanzamiento (xRunValue)</h3>
<p>RV = valor del estado después del lanzamiento − valor del conteo antes. Los valores de los 12 conteos se obtienen resolviendo la cadena de transiciones de conteo con las probabilidades observadas en la LMB (de {sg(tp['V_02'],3)} carreras en 0-2 a {sg(tp['V_30'],3)} en 3-0). Los eventos finales usan pesos lineales escalados al ambiente ofensivo de la LMB ({tp['escala_lmb']:.2f}× el de Grandes Ligas). Cada bola en juego se valora por su <b>valor esperado según velocidad de salida, ángulo y altitud</b>, no por dónde cayó: se quita la suerte del fildeo y se conserva que en altitud el mismo contacto vale más.</p>
<h3>3.2 Variables</h3>
<p><b>Ve (15):</b> velocidad, giro, eje, movimiento vertical inducido (IVB) y horizontal (HB), extensión, altura y lado de liberación; velocidad e IVB de la recta principal; diferencias de velocidad, IVB, HB y eje contra esa recta; categoría de altitud. Para zurdos, lo horizontal se expresa hacia el lado del brazo. <b>No ve, a propósito:</b> ubicación, conteo y bateador (son Location+), ni la etiqueta de tipo de lanzamiento, que la altitud contamina. Las diferencias contra la recta se calculan dentro de la misma temporada y categoría de altitud: el bateador ve ambos lanzamientos en el mismo aire.</p>
<h3>3.3 Arquitectura, función de pérdida e interpretabilidad</h3>
<p>LightGBM (gradient boosting) con 500 árboles de hasta 31 hojas, tasa de aprendizaje 0.03, mínimo de 800 lanzamientos por hoja y regularización L2. <b>Función de pérdida: error cuadrático medio</b> sobre el valor de carrera de cada lanzamiento; con 627 mil lanzamientos y un objetivo continuo, minimizar el error cuadrático estima directamente el valor esperado. La interpretación usa valores SHAP nativos del modelo; las variables que más mueven el Stuff+ son {", ".join(LAB[k] for k in shap_rank[:5])}. La categoría de altitud aporta sobre todo un cambio de nivel que la normalización por sede retira.</p>

<h2>4. La escala Stuff+</h2>
<p style="text-align:center"><code>Stuff+ = 100 + 10 × (μ<sub>sede</sub> − RV predicho) / σ<sub>sede</sub></code></p>
<p>μ y σ son la media y la desviación estándar de los promedios pitcher × lanzamiento (al menos 100 lanzamientos) <b>dentro de cada categoría de altitud</b>, el equivalente más fino de "100 por estadio" sin identificador de estadio. Así 110 es una desviación estándar mejor que el lanzamiento típico en ese tipo de sede y 120 son dos (percentil ~97.7, élite según la convocatoria). La escala se verificó contra lo que ocurrió en el campo, con calificaciones de pitchers que el modelo no había visto:</p>
<div class="tw"><table><tr><th class="l">Stuff+</th><th>Carreras / 100 lanz. vs. promedio</th><th>Fallos por swing</th><th>Strikes cantados + fallos</th><th>Contacto fuerte</th></tr>
{"".join(f'<tr><td>{r["nivel"]}</td><td>{sg(r["carreras_100"],2)}</td><td>{f1(r["whiff_pct"])}%</td><td>{f1(r["csw_pct"])}%</td><td>{f1(r["contacto_fuerte_pct"])}%</td></tr>' for r in cal["tabla"])}
</table></div>

<h2>5. Validación fuera de muestra</h2>
<div class="tw"><table><tr><th class="l">Prueba</th><th class="l">Qué ve el modelo</th><th>Resultado</th></tr>
<tr><td class="l"><b>Baseline nulo</b> (xRunValue promedio por conteo)</td><td class="l">Pitchers no vistos</td><td>Error cuadrático {sg(robp['mejora_mse_vs_nulo_pct'],2)}%; lo supera también en las 3 pruebas por sede</td></tr>
<tr><td class="l"><b>Pitcher holdout</b> (5 grupos de pitchers)</td><td class="l">Nunca al pitcher evaluado</td><td>Correlación {f2(V['oof_corr'])} con su valor de carrera real ({num(V['oof_n'])} pitcher × lanzamiento)</td></tr>
<tr><td class="l"><b>Season holdout</b></td><td class="l">2024–2025, evalúa 2026</td><td>{f2(V['temporal_corr'])}; solo debutantes de 2026: {f2(V['temporal_new_corr'])}</td></tr>
<tr><td class="l"><b>Park holdout</b> (por categoría de altitud)</td><td class="l">Ni la sede ni los pitchers evaluados</td><td>Correlación promedio {f2(pe_sin)} contra {f2(pe_con)} viendo la sede; supera al nulo en las 3</td></tr>
<tr><td class="l"><b>Estabilidad</b> año contra año</td><td class="l">Mismo pitcher y lanzamiento</td><td>{f2(yy[0]['estab_stuff'])} / {f2(yy[1]['estab_stuff'])} (resultado real: {f2(yy[0]['estab_rv'])} / {f2(yy[1]['estab_rv'])})</td></tr>
</table></div>
<p>El error por lanzamiento individual baja poco frente al nulo porque el resultado de un solo lanzamiento es casi todo ruido (ubicación, bateador, azar); la señal aparece al agregar. Agregar información de forma mejora el ordenamiento capa por capa: solo velocidad {f2(lad[1]['corr_pitcher_tipo'])}, más movimiento y giro {f2(lad[2]['corr_pitcher_tipo'])}, más liberación y arsenal {f2(lad[3]['corr_pitcher_tipo'])}. <b>¿Cuándo creerle?</b> Con N lanzamientos de un pitcher, ¿qué predice mejor el resto de su temporada?</p>
{bars([(f"{r['N']} lanz.", r['stuff'], f2(r['stuff']), 'a') for r in ss] , 0.4, '<i style="background:var(--accent)"></i>Stuff+') }
{bars([(f"{r['N']} lanz.", r['rv'], f2(r['rv']), 'b') for r in ss], 0.4, '<i style="background:var(--bar)"></i>Resultado real (valor de carrera)')}
<p class="note">Con 25 lanzamientos Stuff+ anticipa el rendimiento {ss25['stuff']/ss25['rv']:.1f} veces mejor; hacia los 150–200 el resultado real lo alcanza porque incorpora el comando, que Stuff+ ignora por diseño.</p>
<h3>5.1 ¿El simulador predice cómo rinde un pitcher en altitud?</h3>
<p>Con {pv['n_pitchers']} pitchers que lanzaron el mismo lanzamiento a nivel del mar y en altitud extrema ({pv['n']} combinaciones), entrenamos <b>sin cada pitcher</b>, trasladamos sus lanzamientos de nivel del mar a 1,968 m y comparamos contra lo que pasó allá. Error medio: {f1(pv['proyeccion']['mae'])} puntos contra {f1(pv['ingenuo']['mae'])} de suponer que rinde igual (<b>{pct(pv['reduccion_error_pct'])} menos</b>, IC95 {pct(pv['reduccion_error_ic95'][0])}–{pct(pv['reduccion_error_ic95'][1])}); predice el cambio de cada pitcher con correlación {f2(pv['cambio_corr'])}. <b>Contra las carreras reales</b> en altitud: Stuff+ a nivel del mar {f2(vr['ingenuo'])}, proyectado {f2(vr['proyeccion'])}, el de sus lanzamientos reales en altitud {f2(vr['techo'])}; la mejora es significativa (IC95 {sg(vr['mejora_ic95'][0],3)} a {sg(vr['mejora_ic95'][1],3)}). <b>A nivel de arsenal completo</b> ({av['n_pitchers']} pitchers): {pct(av['reduccion_error_pct'])} menos error; contra carreras reales apunta igual ({f2(avr['proyeccion'])} contra {f2(avr['ingenuo'])}) pero aún no es concluyente (IC95 {sg(avr['mejora_ic95'][0],3)} a {sg(avr['mejora_ic95'][1],3)}).</p>
<p class="note">Los exponentes físicos (uno por tipo) se estimaron con todos los pitchers; el modelo de Stuff+, que es lo que podría memorizar a un pitcher, no lo vio.</p>

<h2>6. El efecto de la altitud</h2>
<h3>6.1 Cuánto movimiento se pierde</h3>
{bars([(ES[t], pm['observado'][t], f"{sg(pm['observado'][t])}%", 'obs') for t in sorted(TIPOS, key=lambda t: pm['observado'][t])], 32,
      '<i style="background:var(--accent)"></i>Altitud extrema vs. sin altitud, mismo pitcher y lanzamiento. La densidad sola predeciría ' + sg(pm['lineal_densidad']) + '%.')}
<h3>6.2 Tres verificaciones</h3>
<p><b>El sensor está bien calibrado:</b> lo que pone la mano no cambia con la altitud (velocidad +0.14 mph, extensión +0.07 ft, giro +10 rpm). <b>La etiqueta de tipo está contaminada:</b> el clasificador decide el tipo con el movimiento, que es lo que la altitud cambia; reclasificando solo con velocidad, giro y eje, la discrepancia sube de 17.8% a 25.1% en altitud, y corregirla aumenta el efecto medido. <b>El tiempo de vuelo no lo explica:</b> un simulador de trayectoria muestra que la pelota llega 0.65% antes pero más rápido, y ambos efectos se cancelan.</p>
<h3>6.3 La ley que lo explica, validada fuera de muestra</h3>
<p>Separando la aceleración medida en arrastre y Magnus, la fuerza que curva la pelota cae como densidad<sup>{P['p_magnus_global']:.2f}</sup> y el arrastre como densidad<sup>{P['p_drag_global']:.2f}</sup>. Con exponentes estimados solo en altitud extrema predijimos, sin reajustar, la altitud media: 5 de 6 tipos dentro de su intervalo (la curva no). La densidad sola explica {pm['densidad_sola_explica_pct']}% de la pérdida; con la ley ajustada, {pm['modelo_fisico_explica_pct']}%.</p>
<div class="tw"><table><tr><th class="l">Lanzamiento</th><th>Exponente (IC95)</th><th>Δ Stuff+ proyectado al Harp Helú</th><th>Δ Stuff+ observado en altitud extrema</th><th>Jonrones por bola en juego en altitud (IC95)</th><th>Contacto fuerte</th></tr>
{"".join(f'<tr><td>{ES[t]}</td><td>{P["p_magnus_tipo"][t]:.2f} <span class="note">({P["ic95_tipo"][t][0]:.2f}–{P["ic95_tipo"][t][1]:.2f}){"" if P["valida_medium"][t] else " ✗"}</span></td><td{cls(dproj[t],1)}>{sg(dproj[t])}</td><td{cls(dobs[t][0],1)}>{sg(dobs[t][0])} <span class="note">(n={dobs[t][1]})</span></td><td>{ic(ct[t])}</td><td>{sg(ct[t]["duro_dif_pp"])} pp</td></tr>' for t in TIPOS)}
</table></div>
<p class="note">Δ Stuff+: cambio de la posición relativa (Stuff+ se normaliza por sede). Riesgo: pitchers que lanzaron en ambas sedes; ✗ = exponente no validado en altitud media. En conjunto, los jonrones por bola en juego suben {sg(tot['hr_riesgo_pct'],0)}% (IC95 {sg(tot['hr_ic95'][0],0)} a {sg(tot['hr_ic95'][1],0)}%) y el contacto fuerte {sg(tot['duro_dif_pp'])} puntos.</p>
<p><b>Lectura.</b> Slider y cutter ganan posición porque generan fallos aun con menos movimiento, pero cuando los batean el slider sube su riesgo de jonrón ({sg(ct['Slider']['hr_riesgo_pct'],0)}%). Entre las rectas, las de poco "ride" (IVB menor a {f1(con['ride_cortes_in'][0])} in a nivel del mar) suben su riesgo de jonrón {sg(ride['ride bajo']['hr_riesgo_pct'],0)}% (IC95 {sg(ride['ride bajo']['hr_ic95'][0],0)} a {sg(ride['ride bajo']['hr_ic95'][1],0)}%); las de mucho ride no muestran aumento.</p>

<h2>7. Perfil físico ideal para el Harp Helú</h2>
<p>Qué separa al cuartil superior de Stuff+ del promedio en altitud extrema, y qué cambio pequeño sube más el Stuff+ (efecto promedio sobre miles de lanzamientos reales de cada tipo en altitud).</p>
<div class="tw"><table><tr><th class="l">Lanzamiento</th><th class="l">Los mejores en altitud extrema (top vs. promedio)</th><th class="l">Palancas de desarrollo (puntos de Stuff+)</th></tr>
<tr><td>{ES['Four-Seam']}</td><td class="l">Velocidad ({f1(per['Four-Seam']['extrema']['RelSpeed']['top'])} vs. {f1(per['Four-Seam']['extrema']['RelSpeed']['avg'])} mph), ride ({f1(per['Four-Seam']['extrema']['ivb']['top'])} vs. {f1(per['Four-Seam']['extrema']['ivb']['avg'])} in), giro alto</td><td class="l">{"; ".join(f"{a} ({sg(g)})" for g, a in palancas('Four-Seam'))}</td></tr>
<tr><td>{ES['Sinker']}</td><td class="l">Velocidad ({f1(per['Sinker']['extrema']['RelSpeed']['top'])} vs. {f1(per['Sinker']['extrema']['RelSpeed']['avg'])} mph): el corrimiento se pierde, la velocidad no</td><td class="l">{"; ".join(f"{a} ({sg(g)})" for g, a in palancas('Sinker'))}</td></tr>
<tr><td>{ES['Slider']}</td><td class="l">Duro ({f1(per['Slider']['extrema']['RelSpeed']['top'])} vs. {f1(per['Slider']['extrema']['RelSpeed']['avg'])} mph), giro alto ({num(per['Slider']['extrema']['SpinRate']['top'])} rpm); a nivel del mar gana el barrido, en altitud la velocidad</td><td class="l">{"; ".join(f"{a} ({sg(g)})" for g, a in palancas('Slider'))}</td></tr>
<tr><td>{ES['Changeup']}</td><td class="l">Caída (IVB {f1(per['Changeup']['extrema']['ivb']['top'])} vs. {f1(per['Changeup']['extrema']['ivb']['avg'])} in) y diferencial con la recta ({f1(per['Changeup']['extrema']['d_velo']['top'])} mph)</td><td class="l">{"; ".join(f"{a} ({sg(g)})" for g, a in palancas('Changeup'))}</td></tr>
<tr><td>{ES['Curveball']}</td><td class="l">Dura ({f1(per['Curveball']['extrema']['RelSpeed']['top'])} vs. {f1(per['Curveball']['extrema']['RelSpeed']['avg'])} mph), giro alto</td><td class="l">{"; ".join(f"{a} ({sg(g)})" for g, a in palancas('Curveball'))}</td></tr>
<tr><td>{ES['Cutter']}</td><td class="l">Giro alto, corte al lado del guante</td><td class="l">{"; ".join(f"{a} ({sg(g)})" for g, a in palancas('Cutter'))}</td></tr>
</table></div>
<div class="box"><p><b>El pitcher ideal para la CDMX:</b> velocidad en todo el repertorio; un slider o cutter duro y de giro alto como arma de fallos; un cambio que caiga (no que corra) con 8 mph o más de diferencia con su recta; una recta con ride (o, si no lo tiene, que viva abajo de la zona); y, a igual stuff, un perfil de rodados.</p></div>
<p class="note">Las palancas son asociaciones aprendidas por el modelo, no experimentos: indican hacia dónde dirigir el desarrollo; su factibilidad depende de cada pitcher.</p>

<h2>8. Recomendaciones operativas</h2>
<div class="rec"><span class="tag">Adquisición</span><h3>Ordenar candidatos por su Stuff+ proyectado en el Harp Helú</h3><p>La tabla de pitchers del dashboard lo da para 601 lanzadores de la LMB; el evaluador de candidatos lo da para cualquier pitcher con datos de Trackman de cualquier liga, sin nombre: arsenal completo, lugar frente a la liga, palancas de su lanzamiento más débil y comparación de hasta tres candidatos. Hay pitchers promedio a nivel del mar que se proyectan muy arriba en la CDMX, y estrellas de costa que se proyectan a la baja.</p></div>
<div class="rec"><span class="tag">Plan de juego en casa</span><h3>Apoyarse más en slider y cutter; cuidar las rectas sin ride y los cambios en la zona</h3><p>Slider y cutter ganan posición relativa en casa; la recta de cuatro costuras la pierde. El cambio mantiene su valor pero castiga más cuando lo batean ({sg(ct['Changeup']['hr_riesgo_pct'],0)}% de jonrones por bola en juego) y las rectas de poco ride suben su riesgo de jonrón {sg(ride['ride bajo']['hr_riesgo_pct'],0)}%: son lanzamientos para atacar fuera de la zona alta.</p></div>
<div class="rec"><span class="tag">Composición del staff</span><h3>A igual Stuff+, preferir al pitcher de rodados</h3><p>En altitud un elevado cuesta {f2(gbfb['extrema'])} carreras más que un rodado (a nivel del mar, {f2(gbfb['mar'])}), y el % de rodados solo predice las carreras permitidas en altitud.</p></div>
<div class="rec"><span class="tag">Desarrollo y evaluación</span><h3>Velocidad sobre barrido en el slider, caída sobre corrimiento en el cambio; evaluar desde 25 lanzamientos</h3><p>Usar las palancas de la sección 7 como objetivos. Para refuerzos y prospectos, Stuff+ es la mejor señal antes de que los resultados se estabilicen; pasados 150–200 lanzamientos, combinarlo con resultados. Nunca comparar movimiento crudo entre sedes: una recta con 14 in de IVB medida en la CDMX equivale a unas 19 a nivel del mar; el simulador hace la conversión.</p></div>

<h2>9. Alcance y fronteras</h2>
<ul>
<li><b>Qué es y qué no:</b> Stuff+ mide la calidad física del lanzamiento. No mide comando ni ubicación; Location+ y Pitching+ se pueden construir sobre la misma infraestructura (objetivo, escala, validación) agregando ubicación y conteo.</li>
<li><b>El Harp Helú no se puede aislar:</b> sin identificador de estadio, la CDMX se mezcla con otras cinco sedes de altitud. La ley física se validó entre {num(alt_m['No Altitude'])} y {num(alt_m['Extreme Altitude'])} m; aplicarla a {num(alt_m['Harp Helu'])} m es una extrapolación de {num(alt_m['Harp Helu']-alt_m['Extreme Altitude'])} m.</li>
<li><b>Sin fecha ni clima:</b> con temperatura y humedad, la altitud entraría como densidad del aire por juego.</li>
<li><b>Por qué la pelota "muerde" menos el aire</b> (exponente 1.5): es consistente con efectos de capa límite y con pelotas que se resecan en altitud; separarlos requiere datos de humedad o almacenamiento de pelotas.</li>
<li><b>Simulador:</b> promedia cada predicción sobre la mitad de la variación natural de ejecución (por ejemplo ±0.6 mph, ±1.2 in, ±50 rpm) para que un cambio mínimo no mueva la calificación por un umbral del modelo.</li>
<li><b>Con más tiempo:</b> objetivos por componente (fallos, contacto, rodados) para explicar por qué un lanzamiento es bueno; ajuste bayesiano para muestras chicas; validar las palancas siguiendo a pitchers que ajustaron su arsenal; pesos de eventos con estados base-out cuando haya corredores en los datos.</li>
</ul>
<p class="note">Reproducibilidad: pipeline en Python (pandas, LightGBM) en el repositorio; el dashboard evalúa el mismo modelo en el navegador, verificado contra Python con casos de referencia. Datos: {num(ds['lanzamientos'])} lanzamientos tras depurar 1.3% sin mano, sede o seguimiento completo. Los datos pertenecen a Diablos Rojos y se usaron solo para esta competencia.</p>
</main></body></html>"""
open(f"{R}/public/reporte.html", "w").write(H)
print("reporte.html generado")
