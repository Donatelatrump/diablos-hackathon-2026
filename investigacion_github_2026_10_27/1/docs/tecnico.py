"""Documento técnico: docs/documento_tecnico.md → entrega/documento_tecnico.html (y luego PDF con pdf.mjs)."""
import json, pathlib, re, subprocess, markdown

AQUI = pathlib.Path(__file__).parent
md = (AQUI / "documento_tecnico.md").read_text()
from cifras import renderizar
md = renderizar(md, AQUI.parent)

# Bloques condicionales. "<!-- si stuff_entrena=mar -->" ... "<!-- fin -->" sólo queda si los modelos se entrenaron
# así (artifacts/models.json). Así el texto nunca describe un modelo distinto del que produjo las cifras.
_mj = AQUI.parent / "artifacts" / "models.json"
_entrena = json.loads(_mj.read_text()).get("stuff_entrena", "todo") if _mj.exists() else "todo"
md = re.sub(r"<!-- si stuff_entrena=(\w+) -->\n(.*?)<!-- fin -->\n?",
            lambda m: m.group(2) if m.group(1) == _entrena else "", md, flags=re.S)


def anexo_robustez() -> str:
    """Anexo C, escrito desde app/public/data/robustez.json (sale de scripts/11_robustez.py). Si no existe, nada."""
    f = AQUI.parent / "app" / "public" / "data" / "robustez.json"
    if not f.exists():
        return ""
    R = json.loads(f.read_text())
    ok = lambda k: R.get(k) if isinstance(R.get(k), dict) and "error" not in R[k] else None

    def x(v, d=2, signo=False):
        if v is None:
            return "sin dato"
        t = f"{abs(v):,.{d}f}" if signo else f"{v:,.{d}f}"
        return (("+" if v > 0 else "−" if v < 0 else "") + t) if signo else t.replace("-", "−")

    def ic(i, d=2, signo=False, k=1.0):
        return "sin intervalo" if i is None or i[0] is None or i[1] is None else f"{x(i[0] * k, d, signo)} a {x(i[1] * k, d, signo)}"

    o = ["## Anexo C · Pruebas de robustez", "",
         "Estas pruebas responden las dudas que un jurado técnico tendría al ver un $R^2$ bajo o un efecto de la altura "
         "grande. Las predicciones excluyen las filas evaluadas del ajuste del calificador. Las tablas globales del objetivo y la preparación física limitan el aislamiento estadístico. Los intervalos de 95 % usan remuestreo por lanzador. "
         + ("Stuff+ se entrenó sólo con juegos a nivel del mar, para que la caída de velocidad de la pelota no le enseñe al "
            "modelo que un juego en altura da más carreras." if R.get("stuff_entrena") == "mar" else ""), ""]
    pq = ok("parque")
    if pq:
        p, i = pq["por_100"], pq["ic95_por_100"]
        o += ["**Holdout de categoría de altitud con física.** Entrenamos con nivel del mar y predijimos los "
              f"{pq['n']:,} lanzamientos de altitud extrema de {pq['lanzadores']} lanzadores que el modelo no vio, cada uno con "
              "su forma real y con la misma pelota volada a nivel del mar.", "",
              "| Por cada 100 lanzamientos en altura | Carreras | IC 95 % |", "|---|---|---|",
              f"| Exceso observado sobre lo que espera un modelo de nivel del mar | {x(p['total'], 2, True)} | {ic(i['total'], 2, True)} |",
              f"| Cambio predicho al transformar el vuelo | {x(p['fisica'], 2, True)} | {ic(i['fisica'], 2, True)} |",
              f"| Residuo sin atribución causal | {x(p['resto'], 2, True)} | {ic(i['resto'], 2, True)} |", "",
              f"La razón entre el cambio físico predicho y el exceso total es {x((p['fraccion'] or 0) * 100, 0)} % (IC {ic(i['fraccion'], 0, k=100)} %). "
              f"Es una descomposición dependiente del modelo, no una fracción causal identificada. Dentro de la altura la correlación es {x(pq['corr'], 3, True)} (IC {ic(pq['corr_ic95'], 3, True)}), "
              f"y su $R^2$ con el nivel corregido es {x(pq['r2_nivel_corregido'], 5)}."
              + ((f" Por tipo de lanzamiento, la pérdida que predice la física y el exceso observado dentro del mismo lanzador "
                  f"coinciden en orden con correlación de rangos {x(pq['por_tipo_spearman']['rho'], 2, True)} "
                  f"({pq['por_tipo_spearman']['tipos']} tipos)." if pq['por_tipo_spearman']['rho'] > 0.3 else
                  f" Por tipo de lanzamiento, el exceso observado no sigue el orden de la pérdida física (correlación de rangos "
                  f"{x(pq['por_tipo_spearman']['rho'], 2, True)}, {pq['por_tipo_spearman']['tipos']} tipos). El exceso por tipo "
                  f"también puede reflejar selección y calibración. En varios tipos hay pocos lanzadores.")
                 if pq.get("por_tipo_spearman") else ""), ""]
    di = ok("discriminacion")
    if di:
        o += ["**Discriminación en carreras.** Diferencia en carreras por cada 100 lanzamientos entre el 10 % peor y el 10 % mejor "
              "calificado, fuera de muestra.", "", "| Capa | Diferencia | IC 95 % |", "|---|---|---|"]
        o += [f"| {n} | {x(di[k]['brecha_100'], 2)} | {ic(di[k]['brecha_ic95'], 2)} |"
              for k, n in (("stuff", "Stuff+"), ("location", "Location+"), ("pitching", "Pitching+"))] + [""]
    co = ok("confiabilidad")
    if co:
        o += ["**Calidad contra mezcla de lanzamientos.** Repetibilidad entre dos mitades intercaladas del mismo historial, sin separación temporal. Correlación de los lanzamientos de cada "
              f"lanzador. Stuff+ tal cual {x(co['crudo']['r'], 3)}, contra el promedio de su tipo {x(co['sin_mezcla']['r'], 3)} "
              f"(IC {ic(co['sin_mezcla']['ic95'], 3)}), sólo rectas {x(co['solo_rectas']['r'], 3)}, sólo la mezcla de tipos "
              f"{x(co['solo_mezcla']['r'], 3)} y carreras reales {x(co['carreras']['r'], 3)}.", ""]
    fu = ok("futuro")
    if fu:
        c, w = fu["carreras"], fu["whiff"]
        o += [f"**Año siguiente, análisis retrospectivo.** {fu['pares']} pares de temporadas seguidas de {fu['lanzadores']} lanzadores.", "",
              "| Lo que mides este año | Carreras del siguiente | Swing fallido del siguiente |", "|---|---|---|"]
        o += [f"| {n} | {x(c[k]['r'], 3, True)} ({ic(c[k]['ic95'], 2, True)}) | {x(w[k]['r'], 3, True)} ({ic(w[k]['ic95'], 2, True)}) |"
              for k, n in (("stuff", "Stuff+"), ("carreras_pasadas", "Sus carreras"), ("whiff_pasado", "Su swing fallido"))]
        o += ["", f"Evaluada con regresiones fuera de muestra agrupadas por lanzador, sumar Stuff+ cambia el $R^2$ en "
                  f"{x(c['r2_incremental_stuff']['d'] * 100, 1)} puntos porcentuales (IC {ic(c['r2_incremental_stuff']['ic95'], 1, k=100)}). Las puntuaciones históricas originales usan modelos entrenados con otros lanzadores de todos los años. No es validación prospectiva del pipeline completo.", ""]
    cb = ok("combinacion")
    if cb:
        o += [f"**La combinación ponderada que sugiere el reto.** {len(cb['componentes'])} modelos de componente con las variables "
              "de Stuff+, incluida la probabilidad de out en el turno, combinados con pesos aprendidos por regresión fuera de muestra.", "",
              "| Versión | $R^2$ | RMSE | Diferencia 10 % | Mitades |", "|---|---|---|---|---|"]
        o += [f"| {n} | {x(cb[k]['r2'], 5)} | {x(cb[k]['rmse'], 5)} | {x(cb[k]['brecha_100'], 2)} | {x(cb[k]['mitades'], 3)} |"
              for k, n in (("directo", "Directo en carreras"), ("combinado", "Combinación ponderada"))]
        o += ["", f"Las dos versiones correlacionan {x(cb['corr_entre_ellos'], 2)} entre sí.", ""]
    es = ok("especificaciones")
    if es:
        v = es["variantes"]
        tipos = list(v["produccion"]["por_tipo"])
        otra = es.get("otra", "todos_los_juegos")
        nom = "sólo nivel del mar" if otra == "solo_mar" else "con todos los juegos"
        o += ["**Sensibilidad a la caída de velocidad.** Pérdida de Stuff+ al pasar a altitud extrema con tres versiones del modelo.", "",
              f"| Tipo | La que usamos | Sin frenado | {nom.capitalize()} |", "|---|---|---|---|"]
        o += [f"| {t} | {x(v['produccion']['por_tipo'].get(t), 1, True)} | {x(v['sin_frenado']['por_tipo'].get(t), 1, True)} | "
              f"{x(v[otra]['por_tipo'].get(t), 1, True)} |" for t in tipos]
        o += ["", f"El orden de los tipos coincide con correlación de rangos {x(es['orden_igual']['sin_frenado'], 2)} sin frenado y "
                  f"{x(es['orden_igual'][otra], 2)} {'entrenando sólo a nivel del mar' if otra == 'solo_mar' else 'con todos los juegos'}.", ""]
    mj = R.get("mejoras")
    if isinstance(mj, dict) and "actual" in mj:
        nombres = (("actual", "La que usamos"), ("xrv", "Batazo por calidad de contacto"),
                   ("arsenal", "Arsenal contra la recta dentro de Stuff+"), ("xrv_arsenal", "Contacto y arsenal"),
                   ("frenado_relativo", "Frenado relativo al aire del juego"), ("brazo", "Movimiento en dirección del brazo"),
                   ("desfase_eje", "Desfase del eje de giro"), ("consistencia_salida", "Consistencia del punto de salida"),
                   ("todas", "Las cuatro de física juntas"))
        o += ["**Mejoras que probamos y no cambian el resultado.** Calificamos cada batazo por lo que se espera de su "
              "velocidad de salida y su ángulo, no por si fue hit, metimos dentro de Stuff+ las diferencias contra la recta "
              "del mismo lanzador, dividimos el frenado entre el aire del juego y sumamos variables de física (movimiento en "
              "dirección del brazo, desfase entre el eje de giro y el movimiento, consistencia del punto de salida). Misma "
              "validación por lanzador, todo medido contra las carreras reales.", "",
              "| Versión | $R^2$ | Diferencia 10 % | Mitades | Año siguiente |", "|---|---|---|---|---|"]
        o += [f"| {nom} | {x(mj[k]['r2_vs_rv'], 5)} | {x(mj[k]['brecha_100'], 2)} | {x(mj[k]['mitades'], 3)} | {x(mj[k]['futuro_stuff'], 3)} |"
              for k, nom in nombres if k in mj]
        o += ["", "Estas pruebas exploratorias no justifican sustituir el modelo servido. La diferencia del 10 % (dirección del brazo) "
              "queda dentro del intervalo de producción. La comparación no identifica un techo de capacidad predictiva. Sus métricas temporales son retrospectivas y comparten los límites de preparación de objetivos.", ""]
    return "\n".join(o) + "\n"


_anexo_c = anexo_robustez()
if _anexo_c:
    _cierre = md.rfind("\n*Usamos los datos")
    md = md[:_cierre] + "\n" + _anexo_c + md[_cierre:] if _cierre > 0 else md + "\n" + _anexo_c

# Las fórmulas se sacan antes del Markdown (que se comería los _ y los *) y se componen con KaTeX.
FORMULAS = []
def guardar(m, display):
    FORMULAS.append({"tex": m.group(1).strip(), "display": display})
    return f"@@F{len(FORMULAS) - 1}@@"
md = re.sub(r"\$\$(.+?)\$\$", lambda m: guardar(m, True), md, flags=re.S)
md = re.sub(r"(?<![\\$])\$([^$\n]+?)\$", lambda m: guardar(m, False), md)
html_f = json.loads(subprocess.run(["node", str(AQUI / "katex.mjs")], input=json.dumps(FORMULAS),
                                   capture_output=True, text=True, check=True).stdout)
cuerpo = markdown.markdown(md, extensions=["tables", "fenced_code"])
cuerpo = re.sub(r"<p>@@F(\d+)@@</p>", lambda m: f'<div class="ecuacion">{html_f[int(m.group(1))]}</div>', cuerpo)
cuerpo = re.sub(r"@@F(\d+)@@", lambda m: html_f[int(m.group(1))], cuerpo)
# los anexos empiezan en página nueva
cuerpo = cuerpo.replace("<h2>Anexo A", '<h2 class="anexo">Anexo A', 1)
# las columnas numéricas se alinean a la derecha; las de texto, no
NUM = re.compile(r"^(<strong>)?[\s+\-−–\d.,%→ ]+(in|mph|ft)?(</strong>)?$")
def alinear(t):
    filas = re.findall(r"<tr>(.*?)</tr>", t, re.S)
    cuerpo_f = [re.findall(r"<td>(.*?)</td>", f, re.S) for f in filas[1:]]
    ncol = max((len(c) for c in cuerpo_f), default=0)
    num = [i > 0 and all(NUM.match(c[i].strip()) for c in cuerpo_f if len(c) > i) for i in range(ncol)]
    def celda(tag):
        k = [0]
        def f(m):
            i = k[0]; k[0] += 1
            return f'<{tag} class="n">' if i < len(num) and num[i] else f"<{tag}>"
        return f
    out = []
    for fila in re.split(r"(<tr>.*?</tr>)", t, flags=re.S):
        if fila.startswith("<tr>"):
            fila = re.sub(r"<td>", celda("td"), fila); fila = re.sub(r"<th>", celda("th"), fila)
        out.append(fila)
    return "".join(out)
cuerpo = re.sub(r"<table>.*?</table>", lambda m: alinear(m.group(0)), cuerpo, flags=re.S)
# Mantener el título con su tabla y evitar un párrafo breve partido entre columnas.
cuerpo = re.sub(r"(<h3>1\.3.*?</h3>\s*<table.*?</table>)",
                r'<section class="bloque-ancho">\1</section>', cuerpo, count=1, flags=re.S)
cuerpo = re.sub(r"(<h2>9\. Reproducción</h2>\s*<p>.*?</p>)",
                r'<section class="bloque-ancho">\1</section>', cuerpo, count=1, flags=re.S)
cuerpo = re.sub(r"(<p><strong>H2\.</strong>.*?</p>\s*<div class=\"ecuacion\">.*?</div>)",
                r'<div class="bloque-local">\1</div>', cuerpo, count=1, flags=re.S)
# Gráficas en lugar de tablas. Se reusan las funciones SVG del reporte, así las dos piezas dibujan igual.
import runpy
R_ = runpy.run_path(str(AQUI / "reporte.py"))
_h1, _h2, _h3, _h4 = R_["h1"], R_["h2"], R_["h3"], R_["h4"]
_mae, _nat, _PH = R_["mae"], R_["nat"], R_["PH"]
_AZ, _RO, _AM, _VE, _CE = R_["AZUL"], R_["ROJO"], R_["AMBAR"], R_["VERDE"], R_["CENIZA"]
_barras_original, _bosque = R_["barras_h"], R_["bosque_svg"]
def _barras(*args, **kwargs):
    # Más aire para la cifra y su unidad en las columnas estrechas del documento.
    return _barras_original(*args, valor_w=94, **kwargs)
_comp = R_["J"]["holdout"]["componentes"]
_NOMC = {"y_called_strike": "Strike cantado", "y_swing": "Swing", "y_chase": "Persecución", "y_whiff": "Swing fallido",
         "y_weak_contact": "Contacto débil", "y_groundball": "Rodado", "y_hard_contact": "Contacto duro", "y_barrel": "Barril"}
def _fig(svg, pie):
    return f'<figure class="g-fig">{svg}<figcaption>{pie}</figcaption></figure>'
_rc = _PH["rho_por_cubeta"]
GRAF = {
    "aire": _fig(_barras([("Nivel del mar", _rc["No Altitude"]), ("Altitud media", _rc["Medium Altitude"]), ("Altitud extrema", _rc["Extreme Altitude"])],
                         ancho=460, alto_fila=40, maxv=1.05, fmt=lambda v: f"{v:.3f}", etiqueta_w=150,
                         colores={"Nivel del mar": _AZ, "Altitud media": _AM, "Altitud extrema": _RO}),
                 "Índice de arrastre por categoría (mediana por juego). 1.000 es el nivel del mar."),
    "transfer": _fig(_barras([("Sin transferir", _mae["sin_transferir"]["ivb"]), ("Sólo densidad", _mae["solo_densidad"]["ivb"]), ("Nuestro modelo", _mae["calibrado"]["ivb"])],
                             ancho=460, alto_fila=40, fmt=lambda v: f"{v:.2f} in", etiqueta_w=150,
                             colores={"Sin transferir": _CE, "Sólo densidad": _AM, "Nuestro modelo": _VE}),
                     f"Error medio en elevación, en combinaciones de lanzador y tipo que no usamos para calibrar. En movimiento lateral "
                     f"baja de {_mae['sin_transferir']['hb']:.2f} a {_mae['calibrado']['hb']:.2f} pulgadas, y en velocidad al plato de "
                     f"{_mae['sin_transferir']['zone_speed']:.2f} a {_mae['calibrado']['zone_speed']:.2f} mph."),
    "calib": _fig(R_["calibracion_svg"](), "Carreras por cada 100 lanzamientos según el Stuff+ fuera de muestra. Barras, lo observado. "
                  "Puntos, lo predicho."),
    "nathan": _fig(_barras([("Nivel del mar", _nat["recta"]["mar"]), ("Coors Field", _nat["recta"]["coors"]), ("Harp Helú", _nat["recta"]["hh"]),
                            ("Coors, sólo densidad", _nat["recta"]["solo_densidad_coors"])], ancho=460, alto_fila=40, maxv=19,
                           fmt=lambda v: f"{v:.1f} in", etiqueta_w=170,
                           colores={"Nivel del mar": _AZ, "Coors Field": _AM, "Harp Helú": _RO, "Coors, sólo densidad": _CE}),
                   "Quiebre total de una recta de 18 pulgadas a nivel del mar, volada en otros aires. Nathan estima 14 a 15 en Coors."),
    "h1": _fig(_bosque([(t["tipo"], t["delta"], t["ic"]) for t in _h1["por_tipo"]], min(t["delta"] for t in _h1["por_tipo"]) - 2, 0, ancho=480, fila=34),
               "Cambio medio por tipo en combinaciones de lanzador y tipo con al menos 40 lanzamientos. Intervalo de 95 % por bootstrap de lanzadores. Esta muestra difiere de la población completa de Arsenal."),
    "h2": _fig(_bosque([(t["tipo"], t["ventaja_vs_recta"], t["ic"]) for t in _h2["pares"]], 0, 10, ancho=480, fila=34, fuerte="Cambio"),
               "Cuántos puntos menos pierde cada tipo que la recta del mismo lanzador, con su intervalo de 95 %."),
    "h3": _fig(_bosque([("En altura", _h3["pendiente_alt"], _h3["ic_alt"]), ("A nivel del mar", _h3["pendiente_mar"], _h3["ic_mar"]),
                        ("Diferencia", _h3["diferencia"], _h3["ic_dif"])], -1, 1, ancho=480, fila=34),
               "Carreras por cada 100 lanzamientos por cada 10 puntos más de rodados, con su intervalo de 95 %. Negativo indica asociación con menos carreras."),
    "h4": _fig(_barras([(i["grupo"].replace(" (eficiencia)", "").replace("Giro que se vuelve movimiento", "Eficiencia de giro"), i["peso"] * 100)
                        for i in _h4["importancia"] if i["peso"] > 0.01], ancho=460, alto_fila=34, fmt=lambda v: f"{v:.0f} %", etiqueta_w=190,
                       colores={"Giro (rpm)": _RO, "Movimiento (quiebres)": _VE}),
               "Peso de cada grupo de variables dentro de Stuff+ (ganancia total de los árboles)."),
    "anexoA": _fig(_barras([(_NOMC[k], v["skill"] * 100) for k, v in sorted(_comp.items(), key=lambda kv: -kv[1]["skill"]) if k in _NOMC],
                           ancho=460, alto_fila=32, fmt=lambda v: f"{v:+.1f} %", etiqueta_w=150, colores={n: _AZ for n in _NOMC.values()}),
                   "Habilidad de cada modelo de componente, cuánto mejora su Brier sobre la tasa base, con lanzadores que no vio."),
}
cuerpo = re.sub(r"<!-- g:(\w+) -->", lambda m: GRAF[m.group(1)], cuerpo)

# el aviso final de datos ya está en la portada
cuerpo = re.sub(r"<hr />\s*<p><em>Los datos de la LMB.*?</p>\s*$", "", cuerpo, flags=re.S)
# el título y subtítulo van en la portada, no en el cuerpo
cuerpo = re.sub(r"^<h1>.*?</h1>\s*<h3>.*?</h3>\s*<p>.*?</p>\s*<hr />", "", cuerpo, count=1, flags=re.S)

CSS = """
@page { size: Letter; margin: 15mm 16mm 15mm; @bottom-right { content: counter(page); } }
:root { --rojo:#D7362B; --azul:#2E6FA6; --tinta:#10201A; --texto:#24302A; --ceniza:#6E7A73; --linea:#E3DCCB; --fondo:#FBF9F4; }
* { box-sizing: border-box; }
body { font-family: Inter, system-ui, sans-serif; font-size: 9.25pt; line-height: 1.43; color: var(--texto); margin: 0; }
h1, h2, h3 { font-family: 'Big Shoulders Display', sans-serif; text-transform: uppercase; color: var(--tinta); line-height: 1; letter-spacing: .005em; }
h2 { font-size: 18pt; font-weight: 800; line-height: 1.08; margin: 15pt 0 7pt; padding-top: 9pt; border-top: 2px solid var(--rojo); break-after: avoid; }
h3 { font-size: 12.5pt; font-weight: 700; line-height: 1.1; margin: 15pt 0 6pt; break-after: avoid; }
p { margin: 0 0 6.5pt; orphans: 3; widows: 3; }
strong { color: var(--tinta); }
table { width: 100%; border-collapse: collapse; margin: 8pt 0 11pt; font-size: 8.4pt; break-inside: avoid; }
th { text-align: left; font-weight: 600; color: var(--ceniza); font-size: 7.6pt; text-transform: uppercase; letter-spacing: .03em; border-bottom: 1.5px solid var(--tinta); padding: 4pt 5pt; }
td { padding: 4pt 5pt; border-bottom: 1px solid var(--linea); font-variant-numeric: tabular-nums; }
td.n, th.n { text-align: right; }
pre { background: var(--fondo); border: 1px solid var(--linea); border-radius: 5pt; padding: 7pt 10pt; font-size: 8.2pt; break-inside: avoid; }
code { font-family: 'JetBrains Mono', monospace; font-size: .92em; }
ul, ol { margin: 0 0 8pt; padding-left: 16pt; } li { margin-bottom: 3pt; }
hr { border: none; border-top: 1px solid var(--linea); margin: 14pt 0; }
.portada { height: 245mm; display: flex; flex-direction: column; justify-content: space-between; break-after: page; }
.portada .eyebrow { font-family: 'JetBrains Mono', monospace; font-size: 8.5pt; letter-spacing: .16em; text-transform: uppercase; color: var(--ceniza); }
.portada h1 { font-size: 54pt; font-weight: 900; margin: 14pt 0 10pt; }
.portada h1 em { color: var(--rojo); font-style: normal; }
.portada .sub { font-size: 14pt; color: var(--texto); max-width: 34em; }
.cifras { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10pt; margin-top: 26pt; }
.cifras div { border-top: 2px solid var(--rojo); padding-top: 7pt; }
.cifras div:nth-child(2) { border-top-color: var(--azul); }
.cifras b { display: block; font-family: 'JetBrains Mono', monospace; font-size: 20pt; color: var(--tinta); }
.cifras span { font-size: 8.5pt; color: var(--ceniza); }
.logos-portada { display: flex; align-items: center; gap: 22pt; margin-bottom: 34pt; }
.l-isac { height: 34pt; } .l-diablos { height: 46pt; }
.ecuacion { margin: 8pt 0 10pt; overflow-x: auto; }
.katex { font-size: 1.06em; } .katex-display { margin: 0; }
h2.anexo { break-before: page; }
.dos-col { column-count: 2; column-gap: 8mm; column-fill: auto; }
.dos-col h2 { column-span: all; }
.dos-col table, .dos-col pre { column-span: all; }
.dos-col .ecuacion { column-span: none; font-size: 7.8pt; margin: 7pt 0 9pt; overflow: hidden; break-inside: avoid; }
.dos-col .ecuacion .katex-display { text-align: left; }
.dos-col .ecuacion .katex-display > .katex { text-align: left; white-space: normal; }
.dos-col table.angosta { column-span: none; }
.bloque-ancho { column-span: all; break-inside: avoid; }
.bloque-ancho h3 { margin-top: 10pt; }
.bloque-local { break-inside: avoid; }
p code, li code { overflow-wrap: anywhere; }
.g-fig { margin: 6pt 0 12pt; break-inside: avoid; }
.g-fig figcaption { font-size: 8pt; color: var(--ceniza); margin-top: 5pt; line-height: 1.4; }
.g { width: 100%; height: auto; display: block; overflow: visible; }
.g .et { font-family: Inter, sans-serif; font-size: 16px; font-weight: 600; fill: var(--tinta); }
.g .et.halo { paint-order: stroke; stroke: #fff; stroke-width: 5px; }
.g .eje { font-family: 'JetBrains Mono', monospace; font-size: 13px; fill: var(--ceniza); }
.g .val { font-family: 'JetBrains Mono', monospace; font-size: 17px; font-weight: 700; }
.pie { font-size: 8pt; color: var(--ceniza); border-top: 1px solid var(--linea); padding-top: 8pt; }
"""

PORTADA = """
<section class="portada">
  <div>
    <div class="logos-portada"><img src="{isac}" alt="ISAC" class="l-isac"><img src="{diablos}" alt="Diablos Rojos del México" class="l-diablos"></div>
    <div class="eyebrow">Hackathon ISAC 2026 · Reto Diablos Rojos del México · Documento técnico</div>
    <h1>Diablos <em>Stuff+</em></h1>
    <p class="sub">Calidad de lanzamiento ajustada por la altitud del Estadio Alfredo Harp Helú. Qué lanzadores
    sufren los 2,240 metros, cuáles aguantan y qué perfil te conviene buscar.</p>
    <div class="cifras">
      <div><b>635,002</b><span>lanzamientos de la LMB, 2024 a 2026, medidos con Trackman</span></div>
      <div><b>561</b><span>lanzadores comparados entre el nivel del mar y el Harp Helú</span></div>
      <div><b>{aguantan}</b><span>lanzadores aguantan la altura, pierden menos de media carrera por cada 100 lanzamientos</span></div>
    </div>
  </div>
  <p class="pie">Trabajo independiente de los participantes. No es un producto oficial de ISAC ni del club. Usamos los datos de la
  LMB sólo para esta competencia y aquí presentamos resultados, no datos. La liga anonimizó a los lanzadores.</p>
</section>
"""

KATEX_CSS = (AQUI.parent / "app" / "node_modules" / "katex" / "dist" / "katex.min.css").as_uri()
LOGOS = AQUI.parent / "app" / "public" / "logos"
html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Diablos Stuff+ · Documento técnico</title>
<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@700;800;900&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{KATEX_CSS}">
<style>{CSS}</style></head><body>{PORTADA.format(isac=(LOGOS / 'isac.svg').as_uri(), diablos=(LOGOS / 'diablos.png').as_uri(), aguantan=R_['aguantan'])}<div class="dos-col">{cuerpo}</div></body></html>"""
salida = AQUI.parent / "entrega" / "documento_tecnico.html"
salida.write_text(html)
print("HTML:", salida)
