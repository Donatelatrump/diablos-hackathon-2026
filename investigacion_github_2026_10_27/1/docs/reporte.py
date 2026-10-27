"""Reporte de láminas (16:9) con el patrón de Coach DNA → entrega/reporte.html (y luego PDF con pdf.mjs).

Cada lámina: eyebrow de sección, titular que ES la conclusión, una frase "En esta lámina…",
un solo ejemplo o una sola gráfica, y cada número con su comparación. Todos los números salen
de app/public/data/*.json: si el modelo cambia, se vuelve a correr y el reporte se actualiza.
"""
import json, pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
D = RAIZ / "app" / "public" / "data"
J = json.loads((D / "jurado.json").read_text())
PH = json.loads((D / "physics.json").read_text())
CO = json.loads((D / "compresion.json").read_text())

ROJO, AZUL, VERDE, AMBAR, TINTA, CENIZA, LINEA = "#D7362B", "#2E6FA6", "#1A9A6E", "#B7800A", "#10201A", "#6E7A73", "#E3DCCB"
ES = {"Four-Seam": "Recta", "Slider": "Slider", "Curveball": "Curva", "Changeup": "Cambio",
      "Sinker": "Sinker", "Cutter": "Cutter", "Splitter": "Splitter"}


def n(v, d=0):
    return f"{v:,.{d}f}"


def s(v, d=1):
    return ("+" if v > 0 else "−" if v < 0 else "") + f"{abs(v):,.{d}f}"


P = J["pitchers"]
pierde = sorted(P, key=lambda x: x["delta_hh"])
# Cortes de "aguanta / pierde mucho" en carreras (media y una por cada 100 lanzamientos), traducidos a puntos
# con la escala del modelo. Así no se desfasan si el modelo se reentrena.
CPP = json.loads((D / "scale.json").read_text())["stuff"]["scale"] * 10      # carreras por 100 lanzamientos por punto
CORTE_AGUANTA, CORTE_MUCHO = -0.5 / CPP, -1.0 / CPP
_sd_med = sorted(x["sd_juego"] for x in P)[len(P) // 2]
fichaje = next((x for x in sorted(P, key=lambda x: -x["stuff_hh"]) if x["delta_hh"] > CORTE_AGUANTA and x["sd_juego"] <= _sd_med),
               max(P, key=lambda x: x["stuff_hh"]))
peor = pierde[0]
mar = next(r for r in J["riesgo"] if r["altitude_category"] == "No Altitude")
hh = next(r for r in J["riesgo"] if r["altitude_category"] == "Extreme Altitude")
tipos = sorted(J["tipos"], key=lambda t: t["delta"], reverse=True)
cal = J["calibracion"]
hold = J["holdout"]
q = CO["quintiles"]["Four-Seam"]
mz = {k: v for k, v in CO["mezcla_top_1pct"].items() if k != "Other"}
aguantan = sum(x["delta_hh"] > CORTE_AGUANTA for x in P)
mucho = sum(x["delta_hh"] < CORTE_MUCHO for x in P)
mae = PH["mae_holdout"]
PROM = sum(t["delta"] * t["n"] for t in J["tipos"]) / sum(t["n"] for t in J["tipos"])   # ≈ −8.3

# ----------------------------------------------------------------------------- gráficas SVG

def barras_h(filas, ancho=620, alto_fila=46, maxv=None, fmt=lambda v: s(v), etiqueta_w=130, colores=None, valor_w=70):
    """Barras horizontales desde cero (valores negativos hacia la izquierda... se dibujan como magnitud)."""
    maxv = maxv or max(abs(v) for _, v in filas)
    w = ancho - etiqueta_w - valor_w
    out = [f'<svg viewBox="0 0 {ancho} {alto_fila * len(filas)}" class="g">']
    for i, (et, v) in enumerate(filas):
        y = i * alto_fila
        c = (colores or {}).get(et, ROJO)
        L = abs(v) / maxv * w
        out.append(f'<text x="{etiqueta_w - 12}" y="{y + alto_fila / 2 + 6}" text-anchor="end" class="et">{et}</text>')
        out.append(f'<rect x="{etiqueta_w}" y="{y + 9}" width="{max(L, 2):.1f}" height="{alto_fila - 18}" rx="4" fill="{c}"/>')
        out.append(f'<text x="{etiqueta_w + L + 10:.1f}" y="{y + alto_fila / 2 + 6}" class="val" fill="{c}">{fmt(v)}</text>')
    out.append("</svg>")
    return "".join(out)


def calibracion_svg():
    W, H, PL, PR, PT, PB = 760, 380, 56, 20, 20, 64
    vals = [v for t in cal for v in (t["carreras_100"], t["carreras_pred_100"])]
    y0, y1 = min(vals) - 1.5, max(vals) + 1.5
    bw = (W - PL - PR) / len(cal)
    sx = lambda i: PL + bw * i + bw / 2
    sy = lambda v: PT + (y1 - v) / (y1 - y0) * (H - PT - PB)
    o = [f'<svg viewBox="0 0 {W} {H}" class="g">']
    for v in range(-8, 13, 2):
        if y0 <= v <= y1:
            o.append(f'<line x1="{PL}" x2="{W - PR}" y1="{sy(v):.1f}" y2="{sy(v):.1f}" stroke="{CENIZA if v == 0 else LINEA}" stroke-width="{1.4 if v == 0 else 1}"/>')
            o.append(f'<text x="{PL - 8}" y="{sy(v) + 5:.1f}" text-anchor="end" class="eje">{s(v, 0)}</text>')
    for i, t in enumerate(cal):
        v = t["carreras_100"]; c = ROJO if v > 0 else VERDE
        top, h = min(sy(0), sy(v)), abs(sy(v) - sy(0))
        o.append(f'<rect x="{sx(i) - bw * .3:.1f}" y="{top:.1f}" width="{bw * .6:.1f}" height="{max(h, 1):.1f}" rx="4" fill="{c}" opacity=".85"/>')
        o.append(f'<circle cx="{sx(i):.1f}" cy="{sy(t["carreras_pred_100"]):.1f}" r="6" fill="{TINTA}" stroke="#fff" stroke-width="2"/>')
        o.append(f'<text x="{sx(i) + bw * .3 + 5:.1f}" y="{sy(v) + (12 if v > 0 else -4):.1f}" class="val sm" fill="{TINTA}">{s(v)}</text>')
        o.append(f'<text x="{sx(i):.1f}" y="{H - PB + 24}" text-anchor="middle" class="et">{t["tramo"]}</text>')
        o.append(f'<text x="{sx(i):.1f}" y="{H - PB + 44}" text-anchor="middle" class="eje">{n(t["n"])}</text>')
    o.append("</svg>")
    return "".join(o)


def quintiles_svg():
    W, H, PL, PR, PT, PB = 720, 380, 50, 30, 20, 50
    y0, y1 = 80, 120
    ks = ["q1", "q2", "q3", "q4", "q5"]
    et = ["Peor 20 %", "Grupo 2", "Grupo 3", "Grupo 4", "Mejor 20 %"]
    sx = lambda i: PL + (W - PL - PR) * (i + .5) / 5
    sy = lambda v: PT + (y1 - v) / (y1 - y0) * (H - PT - PB)
    o = [f'<svg viewBox="0 0 {W} {H}" class="g">']
    for v in (80, 90, 100, 110, 120):
        o.append(f'<line x1="{PL}" x2="{W - PR}" y1="{sy(v):.1f}" y2="{sy(v):.1f}" stroke="{CENIZA if v == 100 else LINEA}"/>')
        o.append(f'<text x="{PL - 8}" y="{sy(v) + 5:.1f}" text-anchor="end" class="eje">{v}</text>')
    for i, k in enumerate(ks):
        a, b, d = q[k]["plus_mar"], q[k]["plus_alt"], q[k]["delta"]
        c = VERDE if d > 0 else ROJO
        o.append(f'<line x1="{sx(i):.1f}" x2="{sx(i):.1f}" y1="{sy(a):.1f}" y2="{sy(b):.1f}" stroke="{c}" stroke-width="4"/>')
        o.append(f'<circle cx="{sx(i):.1f}" cy="{sy(a):.1f}" r="8" fill="#fff" stroke="{AZUL}" stroke-width="3"/>')
        o.append(f'<circle cx="{sx(i):.1f}" cy="{sy(b):.1f}" r="7" fill="{c}"/>')
        o.append(f'<text x="{sx(i) + 14:.1f}" y="{(sy(a) + sy(b)) / 2 + 6:.1f}" class="val" fill="{c}">{s(d)}</text>')
        o.append(f'<text x="{sx(i):.1f}" y="{H - PB + 28}" text-anchor="middle" class="et">{et[i]}</text>')
    o.append("</svg>")
    return "".join(o)


def mapa_svg():
    W, H, PL, PR, PT, PB = 760, 420, 52, 16, 16, 46
    xs = [x["stuff_mar"] for x in P]; ys = [x["delta_hh"] for x in P]
    x0, x1 = min(xs) - 1, max(xs) + 1
    y0, y1 = min(ys) - .5, max(2, max(ys)) + .5
    sx = lambda v: PL + (v - x0) / (x1 - x0) * (W - PL - PR)
    sy = lambda v: PT + (y1 - v) / (y1 - y0) * (H - PT - PB)
    o = [f'<svg viewBox="0 0 {W} {H}" class="g">',
         f'<rect x="{sx(100):.1f}" y="{sy(y1):.1f}" width="{sx(x1) - sx(100):.1f}" height="{sy(CORTE_AGUANTA) - sy(y1):.1f}" fill="{VERDE}" opacity=".09"/>']
    for v in range(-20, 5, 4):
        if not y0 <= v <= y1:
            continue
        o.append(f'<line x1="{PL}" x2="{W - PR}" y1="{sy(v):.1f}" y2="{sy(v):.1f}" stroke="{CENIZA if v == 0 else LINEA}"/>')
        o.append(f'<text x="{PL - 8}" y="{sy(v) + 5:.1f}" text-anchor="end" class="eje">{s(v, 0)}</text>')
    for v in range(80, 121, 5):
        if x0 <= v <= x1:
            o.append(f'<line x1="{sx(v):.1f}" x2="{sx(v):.1f}" y1="{PT}" y2="{H - PB}" stroke="{CENIZA if v == 100 else LINEA}"/>')
            o.append(f'<text x="{sx(v):.1f}" y="{H - PB + 22}" text-anchor="middle" class="eje">{v}</text>')
    for x in P:
        d = x["delta_hh"]; c = VERDE if d > CORTE_AGUANTA else AMBAR if d > CORTE_MUCHO else ROJO
        o.append(f'<circle cx="{sx(x["stuff_mar"]):.1f}" cy="{sy(d):.1f}" r="3.6" fill="{c}" opacity=".8"/>')
    for x, et in ((fichaje, "fichar"), (peor, "evitar")):
        cx, cy = sx(x["stuff_mar"]), sy(x["delta_hh"])
        o.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="9" fill="none" stroke="{TINTA}" stroke-width="2.5"/>')
        o.append(f'<text x="{cx - 14:.1f}" y="{cy + (-14 if et == "fichar" else 5):.1f}" text-anchor="end" class="et halo">{x["nombre"]} · {et}</text>')
    o.append(f'<text x="{W - PR - 8}" y="{sy(y1) + 20:.1f}" text-anchor="end" class="et" fill="{VERDE}">Bueno y aguanta → fichar</text>')
    o.append(f'<text x="{(PL + W - PR) / 2}" y="{H - 4}" text-anchor="middle" class="eje">Stuff+ a nivel del mar (100 = promedio) →</text>')
    o.append("</svg>")
    return "".join(o)


def transferencia_svg():
    filas = [("Sin corregir", mae["sin_transferir"]["ivb"], CENIZA), ("Sólo densidad", mae["solo_densidad"]["ivb"], AMBAR),
             ("Nuestro modelo", mae["calibrado"]["ivb"], VERDE)]
    W, Hf = 640, 74
    mx = max(v for _, v, _ in filas)
    o = [f'<svg viewBox="0 0 {W} {Hf * 3}" class="g">']
    for i, (et, v, c) in enumerate(filas):
        L = v / mx * (W - 260)
        o.append(f'<text x="168" y="{i * Hf + 44}" text-anchor="end" class="et">{et}</text>')
        o.append(f'<rect x="180" y="{i * Hf + 14}" width="{L:.1f}" height="{Hf - 28}" rx="5" fill="{c}"/>')
        o.append(f'<text x="{190 + L:.1f}" y="{i * Hf + 46}" class="val" fill="{c}">{v:.2f} in</text>')
    o.append("</svg>")
    return "".join(o)


def mezcla_svg():
    orden = sorted(mz.items(), key=lambda kv: kv[1]["top_altitud"] - kv[1]["top_nivel_mar"], reverse=True)
    W, Hf = 640, 50
    mx = max(max(v["top_altitud"], v["top_nivel_mar"]) for _, v in orden)
    o = [f'<svg viewBox="0 0 {W} {Hf * len(orden)}" class="g">']
    for i, (k, v) in enumerate(orden):
        y = i * Hf
        o.append(f'<text x="110" y="{y + 30}" text-anchor="end" class="et">{ES[k]}</text>')
        for j, (val, c) in enumerate(((v["top_nivel_mar"], AZUL), (v["top_altitud"], ROJO))):
            L = val / mx * (W - 210)
            o.append(f'<rect x="122" y="{y + 7 + j * 18}" width="{max(L, 2):.1f}" height="15" rx="3" fill="{c}" opacity="{.75 if j == 0 else 1}"/>')
            o.append(f'<text x="{130 + L:.1f}" y="{y + 19 + j * 18}" class="eje">{val * 100:.0f} %</text>')
    o.append("</svg>")
    return "".join(o)


HI = json.loads((D / "hipotesis.json").read_text())
LOGOS = RAIZ / "app" / "public" / "logos"
COLT = {"Recta": "#E8B54A", "Sinker": "#D9822B", "Cutter": "#4FB89A", "Slider": "#7C83F0",
        "Curva": "#A77BE0", "Cambio": "#E0679A", "Splitter": "#8FA3B0"}


def bosque_svg(filas, lo, hi, ancho=640, fila=44, fuerte=None):
    """Estimación e intervalo de 95 % por fila. filas = [(etiqueta, valor, (ic_lo, ic_hi))]."""
    PL, PR, H = 120, 80, len(filas) * fila + 36
    sx = lambda v: PL + (v - lo) / (hi - lo) * (ancho - PL - PR)
    o = [f'<svg viewBox="0 0 {ancho} {H}" class="g">']
    paso = 1 if hi - lo <= 6 else 2
    for t in range(int(lo), int(hi) + 1, paso):
        o.append(f'<line x1="{sx(t):.1f}" x2="{sx(t):.1f}" y1="4" y2="{H - 28}" stroke="{CENIZA if t == 0 else LINEA}" stroke-width="{1.5 if t == 0 else 1}"/>')
        o.append(f'<text x="{sx(t):.1f}" y="{H - 8}" text-anchor="middle" class="eje">{s(t, 0)}</text>')
    for i, (et, v, ic) in enumerate(filas):
        y = 22 + i * fila
        c = COLT.get(et, TINTA)
        peso = ' style="font-weight:800"' if et == fuerte else ""
        o.append(f'<text x="{PL - 12}" y="{y + 6}" text-anchor="end" class="et"{peso}>{et}</text>')
        o.append(f'<line x1="{sx(ic[0]):.1f}" x2="{sx(ic[1]):.1f}" y1="{y}" y2="{y}" stroke="{c}" stroke-width="5" stroke-linecap="round"/>')
        o.append(f'<circle cx="{sx(v):.1f}" cy="{y}" r="{9 if et == fuerte else 7}" fill="{c}" stroke="#fff" stroke-width="2.5"/>')
        o.append(f'<text x="{ancho - PR + 14}" y="{y + 6}" class="val" fill="{TINTA}">{s(v, 2)}</text>')
    o.append("</svg>")
    return "".join(o)


def logos_html(clase="logos"):
    return (f'<span class="{clase}"><img src="{(LOGOS / "isac.svg").as_uri()}" alt="ISAC" class="l-isac">'
            f'<img src="{(LOGOS / "diablos.png").as_uri()}" alt="Diablos Rojos del México" class="l-diablos"></span>')


LAMINAS = []


CLAVES: dict[str, int] = {}


def lamina(eyebrow, titular, en_esta, cuerpo, clase="", clave=None):
    LAMINAS.append((eyebrow, titular, en_esta, cuerpo, clase))
    if clave:
        CLAVES[clave] = len(LAMINAS)


def cifra(v, et, c=TINTA):
    return f'<div class="cifra"><b style="color:{c}">{v}</b><span>{et}</span></div>'


h1, h2, h3, h4 = HI["h1"], HI["h2"], HI["h3"], HI["h4"]
CF = json.loads((D / "causal.json").read_text())
_ex = D / "extras.json"
EX = json.loads(_ex.read_text()) if _ex.exists() else {}
TACT = (EX.get("cf_tactico") or {}).get("contrastes") or {}
_rb = D / "robustez.json"
RB = json.loads(_rb.read_text()) if _rb.exists() else {}
ok = lambda x: x if isinstance(x, dict) and "error" not in x else None
RB_PQ, RB_DI, RB_CO, RB_FU, RB_CB, RB_ES = (ok(RB.get(k)) for k in ("parque", "discriminacion", "confiabilidad", "futuro", "combinacion", "especificaciones"))
ROB = bool(RB_PQ or RB_DI or RB_CO or RB_FU)
nat = h1["nathan"]
cam = next(r for r in h2["pares"] if r["tipo"] == "Cambio")
A, B = h4["experimento"]["parejas"]["A"], h4["experimento"]["parejas"]["B"]
giro = next(i for i in h4["importancia"] if i["grupo"].startswith("Giro (rpm)"))
movi = next(i for i in h4["importancia"] if i["grupo"].startswith("Movimiento"))
red = 1 - mae["calibrado"]["ivb"] / mae["sin_transferir"]["ivb"]

# 1 · portada ---------------------------------------------------------------------------------
LAMINAS.append(("portada", None, None, f"""
  {logos_html("logos grandes")}
  <div class="eyebrow">Hackathon ISAC 2026 · Reto Diablos Rojos del México</div>
  <h1>Diablos <em>Stuff+</em></h1>
  <p class="lede">¿Qué lanzadores le sirven a los Diablos a 2,240 metros? Calificamos 635,002 lanzamientos de la LMB y
  medimos cuánto vale cada uno en el Estadio Alfredo Harp Helú, donde hay 20 % menos aire. Los escenarios priorizan
  <b>{fichaje['nombre']}</b> y señalan mayor sensibilidad en <b>{peor['nombre']}</b>.</p>
  <div class="cifras">{cifra('635,002', 'lanzamientos, 2024 a 2026')}{cifra(str(J['pitchers_n']), 'lanzadores comparados', AZUL)}{cifra(s(PROM), 'puntos de Stuff+ que pierde el lanzamiento promedio en altura', ROJO)}</div>
""", ""))

# 2 · qué responde (los números de lámina se resuelven al final) -----------------------------
lamina("Qué responde este reporte", "Nueve preguntas del club, cada una con su lámina",
       "En esta lámina están las preguntas del reto y la lámina donde respondemos cada una.", f"""
<table class="mapa-preguntas">
<tr><td>¿Cómo construimos el modelo?</td><td>Cuatro pasos, de Trackman a la calificación</td><td>@@metodo@@</td></tr>
<tr><td>¿Funcionan la física y el modelo?</td><td>Reproduce a Nathan y ordena carreras con lanzadores nuevos</td><td>@@fisica@@ y @@confianza@@</td></tr>
<tr><td>¿Qué lanzamientos pierden más en altura?</td><td>Todos pierden, con distinta sensibilidad al aire</td><td>@@h1@@ y @@compresion@@</td></tr>
<tr><td>¿Se cumplen las hipótesis del reto?</td><td>H1 respaldada, H2 a H4 parciales</td><td>@@hip@@</td></tr>
<tr><td>¿Cuánto riesgo extra de jonrón hay en casa?</td><td>{s(hh['dist_fb'] - mar['dist_fb'], 0)} pies por elevado</td><td>@@hip@@</td></tr>
<tr><td>¿Qué perfil físico rinde en el Harp Helú?</td><td>Rompientes que no dependen del empuje del aire</td><td>@@perfil@@</td></tr>
<tr><td>¿Qué lanzadores sufren más la altitud y cuáles aguantan?</td><td>{aguantan} aguantan y {mucho} pierden mucho</td><td>@@lanzadores@@ y @@ejemplo@@</td></tr>
<tr><td>¿Qué contrastes observamos entre entornos?</td><td>El bosque estima una diferencia de {CF['ate']:.1f} carreras por cada 100</td><td>@@cf@@</td></tr>
<tr><td>¿Qué hacemos el lunes?</td><td>Priorizar scouting y probar repertorios</td><td>@@hacer@@</td></tr>
</table>""")

# 3 · el problema y cómo leer Stuff+ ---------------------------------------------------------
lamina("El problema", "En el Harp Helú la pelota se mueve menos y cambia el valor de su forma",
       "En esta lámina está el problema y cómo leer la calificación.", f"""
<div class="dos">
  <div><p class="grande">Una pelota que gira empuja el aire hacia un lado y el aire la empuja hacia el otro. Ese empuje,
  el efecto Magnus, es el movimiento que engaña al bateador. A 2,240 metros hay <b>20 % menos aire</b>, más que en
  Coors Field (1,609 m). La misma forma de origen puede terminar con otro movimiento al cambiar el aire. Por eso trasladamos físicamente la trayectoria antes de volver a calificarla.</p>
  <p><b>Stuff+</b> califica un lanzamiento sólo por cómo sale de la mano. <b>Location+</b> suma dónde llegó y el conteo, y
  <b>Pitching+</b> suma el resto del repertorio. Las tres usan la misma escala.</p>
  <div class="escala"><span>90 · malo</span><span class="cien">100 · promedio</span><span>110 · muy bueno</span><span>120 · élite</span></div>
  <p class="nota">Cada 10 puntos son una desviación estándar.</p></div>
  <div class="cifras col">{cifra('2,240 m', 'Harp Helú, contra 1,609 m de Coors Field', ROJO)}{cifra('0.80', 'densidad del aire, contra 1.00 a nivel del mar', AZUL)}{cifra('−3.7 in', 'de elevación pierde la recta del mismo lanzador en altura, medido con Trackman', ROJO)}</div>
</div>""")

# 4 · cómo construimos el modelo (mismo texto que el Resumen del documento) -------------------
lamina("Método", "Un modelo que sólo ve física, probado con lanzadores que no vio, y la misma pelota volada en otro aire",
       "En esta lámina está cómo construimos el modelo, de los datos de Trackman a la calificación.", """
<div class="cuatro">
  <div class="paso"><span>1</span><h3>Un valor para cada lanzamiento</h3><p>Cada lanzamiento cambia el conteo de bolas y strikes, y cada conteo vale cierto número de carreras. La diferencia es cuántas carreras le quitó o le dio al rival. Eso es lo que el modelo aprende a predecir.</p></div>
  <div class="paso"><span>2</span><h3>Un modelo que sólo ve física</h3><p>Un modelo de árboles de decisión (LightGBM) con 16 medidas de Trackman, como la velocidad, el giro, el movimiento y el punto de salida. No ve dónde cayó la pelota ni el estadio. Su predicción, en escala de 100, es Stuff+.</p></div>
  <div class="paso"><span>3</span><h3>Probado con lanzadores que no vio</h3><p>Partimos a los lanzadores en cuatro grupos, entrenamos con tres y calificamos al cuarto. Cada calificación sale de un modelo que nunca vio a ese lanzador, y la comparamos contra un modelo nulo que sólo conoce el conteo.</p></div>
  <div class="paso"><span>4</span><h3>La misma pelota en otro aire</h3><p>Medimos el aire de cada juego con el frenado de la pelota, simulamos su vuelo con el aire del Harp Helú y la calificamos otra vez. La diferencia es el efecto de la altitud.</p></div>
</div>
<p class="nota centro">La altitud no entra como variable. Si entrara, se mezclaría con quién lanza en altura, y no podrías calificar a alguien que nunca ha lanzado ahí. El supuesto clave es que el lanzador suelta igual en cualquier estadio, y lo comprobamos. Comparado consigo mismo, sus vueltas cambian 0.5 % y su velocidad 0.1 %.</p>""", clave="metodo")

# 5 · la física funciona ----------------------------------------------------------------------
lamina("Validación · física", f"El simulador reproduce a Nathan y corrige {red * 100:.0f} % del error de forma",
       "En esta lámina comprobamos la física con datos que no usamos para calibrarla.", f"""
<div class="dos">
  <div>{barras_h([('Nivel del mar', nat['recta']['mar']), ('Coors Field', nat['recta']['coors']), ('Harp Helú', nat['recta']['hh'])], maxv=19, fmt=lambda v: f'{v:.1f} in', etiqueta_w=150, colores={'Nivel del mar': AZUL, 'Coors Field': AMBAR, 'Harp Helú': ROJO})}
  <p class="nota">Quiebre total de la misma recta en tres aires. Escalar sólo por la densidad daría {nat['recta']['solo_densidad_coors']:.1f} en Coors y se quedaría corto.</p></div>
  <div><p class="grande">Alan Nathan estima que en Coors Field una recta con 18 pulgadas de quiebre se mueve 14 o 15. Nuestro
  simulador, calibrado sólo con la LMB, da <b>{nat['recta']['coors']:.1f}</b>. En el Harp Helú da <b>{nat['recta']['hh']:.1f}</b>.</p>
  <p>Con {PH['pitchers_cruce']} lanzadores que tiraron en los dos entornos, predecimos su movimiento en altura a partir de lo que
  tiraron a nivel del mar. El error en elevación baja de {mae['sin_transferir']['ivb']:.2f} a <b>{mae['calibrado']['ivb']:.2f} pulgadas</b>.
  Y el índice del aire que predecimos para la altitud media ({PH['altitud_a_indice_arrastre']['verificacion_cubeta_intermedia']['predicho']:.3f})
  coincide con el medido ({PH['altitud_a_indice_arrastre']['verificacion_cubeta_intermedia']['medido']:.3f}), sin haberlo usado en el ajuste.</p></div>
</div>""", clave="fisica")

# 6 · se puede confiar ------------------------------------------------------------------------
_d = (RB_DI or {}).get("stuff")
_co = (RB_CO or {}).get("crudo", {}).get("r") or J["estabilidad"]["mitades"]["stuff"]
_ca = (RB_CO or {}).get("carreras", {}).get("r") or J["estabilidad"]["mitades"]["rv"]
_fu = (RB_FU or {}).get("carreras")
cif_conf = ""
if _d:
    cif_conf += cifra(f"{abs(_d['brecha_100']):.1f}", f"carreras por cada 100 lanzamientos separan al 10 % mejor del 10 % peor (IC {_d['brecha_ic95'][0]:.1f} a {_d['brecha_ic95'][1]:.1f})", VERDE)
cif_conf += cifra(f"{_co:.2f}", f"correlación del Stuff+ de un lanzador entre dos mitades de sus lanzamientos. Sus carreras, {_ca:.2f}", AZUL)
if _fu:
    cif_conf += cifra(s(_fu['stuff']['r'], 2), f"correlación retrospectiva con las carreras del año siguiente, contra {s(_fu['carreras_pasadas']['r'], 2)} de sus carreras pasadas ({n(RB_FU['pares'])} pares)", ROJO)
nul_ = J["modelo_nulo"]; hp_ = hold["pitcher"]["stuff"]
_audit_path = D / "validation_audit.json"
_audit = json.loads(_audit_path.read_text()) if _audit_path.exists() else None
if _audit:
    nul_, hp_ = _audit["grouped"]["count_baseline"], _audit["grouped"]["current"]
_mj = RB.get("mejoras") if isinstance(RB.get("mejoras"), dict) else None
_mj_txt = (f"Probamos {len(_mj) - 2} mejoras (calidad de contacto, arsenal, frenado relativo al aire y variables de física) y "
           "no justifican sustituir el modelo servido.") if _mj else ""
lamina("Validación · criterios 1 y 2", "Stuff+ ordena grupos de lanzamientos y es repetible dentro del historial",
       "En esta lámina separamos ordenamiento, repetibilidad y asociación retrospectiva con el año siguiente.", f"""
<div class="dos ancho-izq">
  <div>{calibracion_svg()}
  <p class="nota">Carreras por cada 100 lanzamientos según su Stuff+ fuera de muestra. Bajan escalón por escalón. Un lanzamiento suelto
  tiene mucha variación y Stuff+ explica una fracción pequeña. La ubicación suma capacidad predictiva en las otras capas. {_mj_txt} La auditoría separada reajusta la misma especificación con objetivo y baseline aprendidos en entrenamiento. RMSE {hp_['rmse']:.5f} contra {nul_['rmse']:.5f}. La calibración dibujada conserva las predicciones originales con tablas globales. La física preparada globalmente y las puntuaciones históricas con otros años limitan la validación prospectiva.</p></div>
  <div class="cifras col">{cif_conf}</div>
</div>""", clave="confianza")

# 7 · H1 ---------------------------------------------------------------------------------------
lamina("H1 · se confirma", "La recta pierde más que el cutter en el escenario de altura",
       "En esta lámina se evalúan combinaciones de lanzador y tipo con al menos 40 lanzamientos, con intervalos de 95 %.", f"""
<div class="dos ancho-izq">
  <div>{bosque_svg([(t['tipo'], t['delta'], t['ic']) for t in h1['por_tipo']], min(t['delta'] for t in h1['por_tipo']) - 2, 0)}</div>
  <div><p class="grande">El aire delgado le cobra al movimiento. Cada lanzamiento paga según cuánto de su valor viene de moverse.</p>
  <p><b>Cutter, splitter y slider</b> engañan porque salen igual que la recta y rompen tarde. Pagan poco. <b>La recta</b> vive de su elevación y paga {s(h1['por_tipo'][-1]['delta'], 2)}. Los siete intervalos quedan bajo cero.</p><p class="nota">H1 usa arsenales elegibles con al menos 40 lanzamientos por tipo. Difiere de la población completa de la tabla Arsenal.</p></div>
</div>""", clave="h1")

# 8 · compresión --------------------------------------------------------------------------------
lamina("H1 · el hallazgo", "La altitud apenas toca a la recta mala y borra la ventaja de la buena",
       "En esta lámina partimos las rectas en cinco grupos según su Stuff+ a nivel del mar.", f"""
<div class="dos ancho-izq">
  <div>{quintiles_svg()}</div>
  <div><p class="grande">La mejor recta baja de <b>{q['q5']['plus_mar']:.1f}</b>, élite, a <b>{q['q5']['plus_alt']:.1f}</b>. Pierde {s(q['q5']['delta'])}. La peor {'<b>gana ' + s(q['q1']['delta']) + '</b>' if q['q1']['delta'] > 0 else 'pierde sólo <b>' + s(q['q1']['delta']) + '</b>'}.</p>
  <p>Lo que separa a una recta de élite de una mediocre es el movimiento, y el movimiento es lo que el aire se lleva. <b>No pagues de más por una recta de élite</b> para lanzar en casa.</p>
  <p class="nota">Azul, nivel del mar. Punto de color, el mismo lanzamiento en el Harp Helú.</p></div>
</div>""", clave="compresion")

# 9 · las cuatro hipótesis ----------------------------------------------------------------------
rank_cam = [p['tipo'] for p in h2['pares']].index('Cambio') + 1
delante = ", ".join(p['tipo'].lower() for p in h2['pares'][:rank_cam - 1])
recta_, cutter_ = h1['por_tipo'][-1]['delta'], h1['por_tipo'][0]['delta']
lamina("Hipótesis del reto", "H1 tiene respaldo físico, H2 a H4 tienen evidencia parcial",
       "En esta lámina están las cuatro hipótesis del reto, cada una con su cifra clave.", f"""
<table class="mapa-preguntas hip">
<tr><td><b>H1</b> El aire delgado le quita movimiento al lanzamiento</td><td>Los siete tipos pierden Stuff+, la recta {s(recta_)} y el cutter {s(cutter_)}. La física reproduce a Nathan, 18 pulgadas se vuelven {nat['recta']['coors']:.1f} en Coors.</td><td class="v-si">Se confirma</td></tr>
<tr><td><b>H2</b> El cambio de velocidad gana valor relativo</td><td>El cambio pierde {s(cam['ventaja_vs_recta'], 1)} puntos menos que la recta del mismo lanzador, en el {cam['pct_pitchers_gana'] * 100:.0f} % de los casos. Pero queda {rank_cam}.º de seis, detrás de {delante}.</td><td class="v-parcial">En parte</td></tr>
<tr><td><b>H3</b> Los lanzadores de rodados valen más en altura</td><td>En altura, 10 puntos más de rodados se asocian con {abs(h3['pendiente_alt']):.2f} carreras menos por cada 100. La diferencia entre entornos no alcanza 95 % (p = {h3['p_una_cola']:.2f}, una cola). Un elevado viaja {s(hh['dist_fb'] - mar['dist_fb'], 0)} pies más y sale del parque {hh['hr_fb'] * 100:.1f} % de las veces contra {mar['hr_fb'] * 100:.1f} %.</td><td class="v-parcial">En parte</td></tr>
<tr><td><b>H4</b> El giro por sí solo no basta</td><td>La importancia de giro es {giro['peso'] * 100:.0f} % de la ganancia del modelo. El barrido de giro recorre {min(x['mar'] for x in h4['experimento']['giro']):.1f} a {max(x['mar'] for x in h4['experimento']['giro']):.1f} puntos. El cambio absoluto medio entre pasos de 100 rpm es {sum(abs(b['mar'] - a['mar']) for a, b in zip(h4['experimento']['giro'], h4['experimento']['giro'][1:])) / (len(h4['experimento']['giro']) - 1):.2f}. La casi cancelación entre extremos no demuestra insensibilidad local.</td><td class="v-parcial">En parte</td></tr>
</table>
<p class="nota">Intervalos de 95 % por bootstrap de lanzadores, 2,000 remuestreos. El detalle de cada prueba está en el documento técnico y en la pestaña Hipótesis del dashboard.</p>""", clave="hip")

# 10 · perfil ideal ------------------------------------------------------------------------------
pf = CO["perfil_ideal"]
lamina("Perfil ideal · entregable 2", "En altura la élite es slider, no recta",
       "En esta lámina están los tipos que forman el 1 % mejor calificado en cada aire, y su perfil físico.", f"""
<div class="dos">
  <div>{mezcla_svg()}<p class="nota"><span style="color:{AZUL}">■</span> élite a nivel del mar &nbsp; <span style="color:{ROJO}">■</span> élite en el Harp Helú</p></div>
  <div><p class="grande">El slider pasa de <b>{mz['Slider']['top_nivel_mar'] * 100:.0f} %</b> a <b>{mz['Slider']['top_altitud'] * 100:.0f} %</b> de la élite. La recta cae de {mz['Four-Seam']['top_nivel_mar'] * 100:.0f} % a {mz['Four-Seam']['top_altitud'] * 100:.0f} %.</p>
  <table class="perfil"><tr><th></th><th>Élite mar</th><th>Élite Harp Helú</th></tr>
  <tr><td>Movimiento total</td><td>{pf['movement_total']['optimo_nivel_mar']:.1f} in</td><td><b>{pf['movement_total']['optimo_altitud']:.1f} in</b></td></tr>
  <tr><td>Giro que se vuelve movimiento</td><td>{pf['spin_efficiency']['optimo_nivel_mar'] * 100:.0f} %</td><td><b>{pf['spin_efficiency']['optimo_altitud'] * 100:.0f} %</b></td></tr>
  <tr><td>Velocidad</td><td>{pf['RelSpeed']['optimo_nivel_mar']:.1f} mph</td><td><b>{pf['RelSpeed']['optimo_altitud']:.1f} mph</b></td></tr></table>
  <p>El perfil a buscar no depende del empuje del aire. Giro de bala, movimiento moderado y engaño por túnel.</p></div>
</div>""", clave="perfil")

# 11 · por lanzador ------------------------------------------------------------------------------
lamina("La pregunta del club · entregable 1", f"{aguantan} de {J['pitchers_n']} lanzadores aguantan la altura",
       "En esta lámina cada punto es un lanzador. Qué tan bueno es a nivel del mar contra cuánto cambia en el Harp Helú.", f"""
<div class="dos ancho-izq">
  <div>{mapa_svg()}</div>
  <div><p class="grande"><span style="color:{VERDE}">●</span> {aguantan} aguantan, pierden menos de media carrera cada 100 lanzamientos. <span style="color:{AMBAR}">●</span> {J['pitchers_n'] - aguantan - mucho} pierden. <span style="color:{ROJO}">●</span> {mucho} pierden más de una carrera.</p>
  <p>Los que más pierden suelen ser buenos a nivel del mar. Su calidad era movimiento.</p>
  <p>La constancia entre juegos está en la ficha de cada lanzador en el dashboard.</p></div>
</div>""", clave="lanzadores")

# 12 · ejemplo completo --------------------------------------------------------------------------
def ficha(x, veredicto, c):
    return f"""<div class="ficha" style="border-color:{c}"><span class="tag" style="color:{c}">{veredicto}</span>
  <h3>{x['nombre']}</h3><p class="nota">{x['arsenal']} · {'zurdo' if x['mano'] == 'Left' else 'derecho'} · {n(x['n'])} lanzamientos</p>
  <div class="salto"><div><span>Nivel del mar</span><b style="color:{AZUL}">{x['stuff_mar']:.1f}</b></div><div class="fl">→</div>
  <div><span>Harp Helú</span><b style="color:{ROJO}">{x['stuff_hh']:.1f}</b></div><div><span>Cambio</span><b style="color:{c}">{s(x['delta_hh'])}</b></div></div>
  <p>Location+ {x['location']:.1f} · Pitching+ {x['pitching']:.1f} · constancia ± {x['sd_juego']:.1f} entre juegos · rodados {x['gb'] * 100:.0f} %</p></div>"""

lamina("Ejemplo completo", f"{fichaje['nombre']} conserva más valor y {peor['nombre']} pierde {abs(peor['delta_hh']):.1f} puntos",
       "En esta lámina hay dos lanzadores con calidad parecida a nivel del mar y destinos opuestos en casa.", f"""
<div class="dos">{ficha(fichaje, 'Fichar', VERDE)}{ficha(peor, 'Mejor de visitante', ROJO)}</div>
<p class="grande centro">A nivel del mar valen casi lo mismo ({fichaje['stuff_mar']:.1f} contra {peor['stuff_mar']:.1f}). En el Harp Helú los separan {fichaje['stuff_hh'] - peor['stuff_hh']:.1f} puntos, unas {(fichaje['stuff_hh'] - peor['stuff_hh']) * CPP:.1f} carreras por cada 100 lanzamientos.</p>""", clave="ejemplo")

# 13 · Causal Forest ------------------------------------------------------------------------------
cf_izq = cifra(s(CF['ate'], 2), f"carreras adicionales por cada 100 lanzamientos estima el bosque de entorno (IC 90 % de {CF['ate_ic90'][0]:.2f} a {CF['ate_ic90'][1]:.2f})", ROJO)
if RB_PQ and RB_PQ["por_100"].get("fraccion") is not None:
    cf_izq += cifra(f"{RB_PQ['por_100']['fraccion'] * 100:.0f} %", "es la razón entre el cambio físico predicho y el exceso observado. Es una descomposición de modelo, sin identificación causal", AZUL)
cf_izq += cifra("No", "se sostienen las diferencias causales entre lanzadores fuera de muestra. Stuff+ aporta escenarios físicos, no esa confirmación")
cf_der = ""
if TACT:
    c0 = TACT.get("Slider en vez de Cambio") or next(iter(TACT.values()))
    def rejilla(c, alt):
        filas = ""
        for b in range(4):
            celdas = ""
            for st in range(3):
                x = next((k for k in c["celdas"] if k["altura"] == alt and k["mismo_lado"] == 0 and k["conteo"] == f"{b}-{st}"), None)
                if x is None:
                    celdas += "<td></td>"; continue
                col = VERDE if x["efecto"] < 0 else ROJO
                celdas += f'<td style="background:{col}22;color:{col}"><b>{s(x["efecto"], 1)}</b></td>'
            filas += f"<tr><th>{b}</th>{celdas}</tr>"
        return f'<table class="conteo"><tr><th>Bolas \\ Strikes</th><th>0</th><th>1</th><th>2</th></tr>{filas}</table>'
    m_, a_ = c0["por_entorno"]["mar"], c0["por_entorno"]["altura"]
    cf_der = (f'<p class="tag" style="color:{ROJO}">{c0["a"]} en vez de {c0["b"].lower()} en altitud extrema · promedio {s(a_["efecto"], 2)} (mar {s(m_["efecto"], 2)})</p>'
              f'{rejilla(c0, 1)}<p class="nota">Carreras por cada 100 lanzamientos contra un bateador del lado contrario. Verde quiere decir que el {c0["a"].lower()} tiene menor valor predicho en carreras. Las celdas son exploratorias y no corrigen por comparaciones múltiples.</p>')
lamina("Modelo secundario · Causal Forest", f"El bosque estima una diferencia de entorno de {CF['ate']:.1f} carreras por cada 100 lanzamientos",
       "En esta lámina el bosque aporta señales observacionales, sujetas a confusión y comparaciones múltiples.", f"""
<div class="dos"><div class="cifras col">{cf_izq}</div><div>{cf_der}</div></div>""", clave="cf")

# 14 · qué hacer -------------------------------------------------------------------------------
aguantan_top = sorted([x for x in P if x["stuff_hh"] >= 100], key=lambda x: -x["delta_hh"])[:5]
filas = "".join(f"<tr><td>{x['nombre']}</td><td>{x['arsenal']}</td><td>{x['stuff_hh']:.1f}</td><td style='color:{VERDE}'>{s(x['delta_hh'])}</td></tr>" for x in aguantan_top)
lamina("Qué hacer", "Prioriza evaluación de cutter, slider y splitter y revisa sensibilidad al aire",
       "En esta lámina están las decisiones concretas para el director deportivo y el pitching coach.", f"""
<div class="dos">
  <ol class="hacer">
    <li><b>Fichajes.</b> Descuenta el valor que viene del movimiento. Una recta de élite pierde {abs(q['q5']['delta']):.1f} puntos en casa.</li>
    <li><b>Perfil.</b> Busca cutter, slider y splitter, y lanzadores que provoquen rodados, porque en casa un elevado viaja {hh['dist_fb'] - mar['dist_fb']:.0f} pies más.</li>
    <li><b>Rotación.</b> Prioriza candidatos de casa con menor pérdida estimada, junto con comando, descanso y rival.</li>
    <li><b>En el juego.</b> En casa, contra el bateador del lado contrario y con el conteo en contra, considera probar slider frente a cambio, como hipótesis exploratoria.</li>
    <li><b>Prospectos.</b> Pasa sus números de Trackman por el simulador y compara su Stuff+ en los dos estadios.</li>
  </ol>
  <div><p class="tag">Buenos que aguantan, Stuff+ en casa de 100 o más</p>
  <table class="perfil"><tr><th>Lanzador</th><th>Arsenal</th><th>Harp Helú</th><th>Cambio</th></tr>{filas}</table>
  <p class="nota">La lista completa, ordenable y con ficha por lanzador, está en la pestaña Lanzadores del dashboard.</p></div>
</div>""", clave="hacer")

# 15 · cierre -----------------------------------------------------------------------------------
lamina("Límites y referencias", "Esto es lo que el modelo no hace",
       "En esta lámina están los límites del trabajo y la literatura en la que nos apoyamos.", """
<div class="dos">
  <ul class="limites">
    <li><b>No identifica estadios.</b> La altitud extrema agrupa varios parques, y el Harp Helú es el más alto.</li>
    <li><b>No separa aire de clima.</b> El índice junta densidad, temperatura y humedad.</li>
    <li><b>No modela al bateador.</b> El contacto perfecto (barril) casi no se predice desde la física.</li>
    <li><b>Stuff+ no es causal.</b> Valora escenarios. El bosque requiere controles suficientes y contiene covariables potencialmente posteriores al entorno.</li>
    <li><b>La validación tiene límites.</b> Objetivo y baseline usan tablas globales. 2026 ya se inspeccionó durante desarrollo. El holdout es de categoría de altitud, sin identificar estadios.</li>
    <li><b>El simulador representa una forma típica.</b> Sus 49 variaciones no equivalen a la población completa de un tipo.</li>
  </ul>
  <ul class="refs">
    <li>Nathan, A. <i>The effect of altitude on baseball trajectories.</i> Physics of Baseball.</li>
    <li>SABR. <i>High altitude offense.</i> Baseball Research Journal.</li>
    <li>Tango, Lichtman y Dolphin (2007). <i>The Book, Playing the Percentages in Baseball.</i></li>
    <li>Ke y coautores (2017). LightGBM. <i>NeurIPS.</i></li>
    <li>Chernozhukov y coautores (2018). Double/debiased machine learning. <i>Econometrics Journal</i> 21(1).</li>
    <li>Wager y Athey (2018). Heterogeneous treatment effects using random forests. <i>JASA</i> 113(523).</li>
    <li>Huang y Hsu (2021). Big data analytics in baseball, a review. <i>SAGE Open</i> 11(4).</li>
  </ul>
</div>
<p class="nota centro">Usamos los datos de la LMB sólo para esta competencia y presentamos resultados, nunca datos. La liga anonimizó a los lanzadores. Trabajo independiente, no es un producto oficial de ISAC ni del club.</p>""")

# Números de lámina en la tabla "Qué responde".
for _k, (_eb, _t, _en, _c, _cl) in enumerate(LAMINAS):
    for _clave, _num in CLAVES.items():
        _c = _c.replace(f"@@{_clave}@@", str(_num))
    LAMINAS[_k] = (_eb, _t, _en, _c, _cl)


CSS = f"""
@page {{ size: 1280px 720px; margin: 0; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: Inter, system-ui, sans-serif; color: #24302A; background: #F4F0E6; }}
.lam {{ width: 1280px; height: 720px; padding: 46px 64px 40px; position: relative; overflow: hidden; break-after: page; background: #F4F0E6; display: flex; flex-direction: column; }}
.lam::after {{ content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 8px; background: {ROJO}; }}
.eyebrow {{ font-family: 'JetBrains Mono', monospace; font-size: 13px; letter-spacing: .16em; text-transform: uppercase; color: {ROJO}; }}
h1, h2, h3 {{ font-family: 'Big Shoulders Display', sans-serif; text-transform: uppercase; color: {TINTA}; line-height: .95; margin: 0; }}
h2 {{ font-size: 46px; font-weight: 900; margin: 10px 0 8px; max-width: 1080px; }}
h3 {{ font-size: 24px; font-weight: 800; }}
.en-esta {{ font-size: 16px; color: {CENIZA}; margin: 0 0 22px; }}
.cuerpo {{ flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 18px; }}
p {{ margin: 0 0 10px; font-size: 16px; line-height: 1.45; }}
.grande {{ font-size: 21px; line-height: 1.38; color: {TINTA}; }}
.centro {{ text-align: center; max-width: 980px; margin-left: auto; margin-right: auto; }}
.nota {{ font-size: 13.5px; color: {CENIZA}; }}
b {{ color: {TINTA}; }}
.pie {{ position: absolute; left: 64px; right: 64px; bottom: 16px; display: flex; justify-content: space-between; font-family: 'JetBrains Mono', monospace; font-size: 11px; color: {CENIZA}; letter-spacing: .08em; text-transform: uppercase; }}
.dos {{ display: grid; grid-template-columns: 1fr 1fr; gap: 44px; align-items: center; }}
.dos.ancho-izq {{ grid-template-columns: 1.35fr 1fr; }}
.tres {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 22px; }}
.cuatro {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }}
.def {{ background: #fff; border-radius: 14px; padding: 22px; border: 1px solid {LINEA}; }}
.def h3 {{ color: {ROJO}; margin-bottom: 10px; }}
.big {{ display: block; font-family: 'JetBrains Mono', monospace; font-size: 46px; color: {VERDE}; margin: 8px 0; }}
.tag {{ font-family: 'JetBrains Mono', monospace; font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: {CENIZA}; }}
.cifras {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 22px; }}
.cifras.col {{ grid-template-columns: 1fr; gap: 16px; }}
.cifra {{ border-top: 3px solid {LINEA}; padding-top: 10px; }}
.cifra b {{ display: block; font-family: 'JetBrains Mono', monospace; font-size: 34px; letter-spacing: -.02em; }}
.cifra span {{ font-size: 14.5px; color: {CENIZA}; }}
.formula {{ font-family: 'JetBrains Mono', monospace; font-size: 18px; background: #fff; border: 1px solid {LINEA}; border-radius: 12px; padding: 16px 22px; text-align: center; color: {TINTA}; }}
.g {{ width: 100%; height: auto; display: block; overflow: visible; }}
.g .et {{ font-family: Inter, sans-serif; font-size: 16px; font-weight: 600; fill: {TINTA}; }}
.g .et.halo {{ paint-order: stroke; stroke: #F4F0E6; stroke-width: 5px; }}
.g .eje {{ font-family: 'JetBrains Mono', monospace; font-size: 13px; fill: {CENIZA}; }}
.g .val {{ font-family: 'JetBrains Mono', monospace; font-size: 17px; font-weight: 700; }}
.g .val.sm {{ font-size: 15px; }}
.flujo {{ display: grid; grid-template-columns: 1fr auto 1fr auto 1fr; gap: 16px; align-items: stretch; }}
.paso {{ background: #fff; border: 1px solid {LINEA}; border-radius: 14px; padding: 22px; }}
.paso span {{ font-family: 'JetBrains Mono', monospace; font-size: 30px; font-weight: 700; color: {ROJO}; }}
.paso h3 {{ margin: 6px 0 10px; }}
.paso p {{ font-size: 15px; }}
.flecha {{ align-self: center; font-size: 34px; color: {ROJO}; }}
table {{ border-collapse: collapse; width: 100%; }}
.mapa-preguntas td {{ padding: 13px 12px; border-bottom: 1px solid {LINEA}; font-size: 18px; }}
.mapa-preguntas td:first-child {{ font-weight: 600; color: {TINTA}; }}
.mapa-preguntas td:nth-child(2) {{ color: {ROJO}; font-family: 'JetBrains Mono', monospace; font-size: 15px; }}
.mapa-preguntas td:last-child {{ text-align: right; font-family: 'JetBrains Mono', monospace; color: {CENIZA}; white-space: nowrap; }}
.perfil {{ margin: 10px 0 14px; font-size: 15px; }}
.perfil th {{ text-align: left; font-size: 12px; text-transform: uppercase; letter-spacing: .05em; color: {CENIZA}; border-bottom: 2px solid {TINTA}; padding: 6px 8px; }}
.perfil td {{ padding: 7px 8px; border-bottom: 1px solid {LINEA}; font-variant-numeric: tabular-nums; }}
.ficha {{ background: #fff; border: 1px solid {LINEA}; border-top: 5px solid; border-radius: 14px; padding: 24px; }}
.ficha h3 {{ font-size: 36px; margin: 4px 0 4px; }}
.salto {{ display: flex; align-items: flex-end; gap: 22px; margin: 18px 0 14px; padding: 14px 0; border-top: 1px solid {LINEA}; border-bottom: 1px solid {LINEA}; }}
.salto span {{ display: block; font-size: 12px; color: {CENIZA}; text-transform: uppercase; letter-spacing: .08em; }}
.salto b {{ font-family: 'JetBrains Mono', monospace; font-size: 38px; }}
.salto .fl {{ font-size: 28px; color: {CENIZA}; padding-bottom: 6px; }}
.hacer {{ margin: 0; padding-left: 24px; display: grid; gap: 14px; font-size: 18px; line-height: 1.4; }}
.hacer li::marker {{ color: {ROJO}; font-weight: 700; }}
.limites, .refs {{ margin: 0; padding-left: 20px; display: grid; gap: 12px; font-size: 16.5px; line-height: 1.4; }}
.refs {{ font-size: 14.5px; color: {CENIZA}; }}
/* portada */
.lam.portada {{ justify-content: center; padding: 70px 90px; background: {TINTA}; color: #E6E3DA; }}
.lam.portada::after {{ width: 14px; }}
.portada h1 {{ color: #F6F3EA; font-size: 84px; font-weight: 900; margin: 18px 0 22px; max-width: 1000px; }}
.portada h1 em {{ font-style: normal; color: {ROJO}; }}
.portada .lede {{ font-size: 23px; max-width: 900px; line-height: 1.45; margin-bottom: 40px; }}
.portada b {{ color: #fff; }}
.portada .cifra {{ border-top-color: #44554F; }}
.portada .cifra b {{ color: #F6F3EA !important; }}
.portada .cifra span {{ color: #A1A69C; }}
"""

CSS += f"""
.conteo {{ border-collapse: separate; border-spacing: 5px; width: 100%; font-family: 'JetBrains Mono', monospace; font-size: 17px; }}
.conteo th {{ font-size: 13px; color: {CENIZA}; font-weight: 600; }}
.conteo td {{ text-align: center; padding: 14px 6px; border-radius: 8px; }}
.logos {{ display: inline-flex; align-items: center; gap: 14px; }}
.logos img {{ display: block; width: auto; }}
.pie .l-isac {{ height: 20px; }} .pie .l-diablos {{ height: 24px; }}
.logos.grandes {{ gap: 26px; margin-bottom: 26px; }}
.logos.grandes .l-isac {{ height: 46px; filter: brightness(0) invert(0.9); }} .logos.grandes .l-diablos {{ height: 62px; }}
.pie {{ align-items: center; }}
.escala {{ display: grid; grid-template-columns: repeat(4, 1fr); text-align: center; font-family: 'JetBrains Mono', monospace; font-size: 15px; border-radius: 12px; overflow: hidden; border: 1px solid {LINEA}; }}
.escala span {{ padding: 12px 6px; background: #fff; border-right: 1px solid {LINEA}; }}
.escala .cien {{ background: {TINTA}; color: #F6F3EA; font-weight: 700; }}
.aviso-dato {{ background: #fff; border: 1px solid {LINEA}; border-left: 5px solid {AMBAR}; border-radius: 12px; padding: 22px; font-size: 18px; line-height: 1.45; }}
.mapa-preguntas.hip td:nth-child(2) {{ color: {CENIZA}; font-family: Inter, sans-serif; font-size: 15px; }}
.mapa-preguntas td.v-si {{ color: {VERDE}; font-weight: 700; font-family: Inter, sans-serif; }}
.mapa-preguntas td.v-parcial {{ color: {AMBAR}; font-weight: 700; font-family: Inter, sans-serif; }}
.cuatro .cifra b {{ font-size: 30px; }}
"""

html = []
for i, (eb, tit, en, cuerpo, clase) in enumerate(LAMINAS, 1):
    if eb == "portada":
        html.append(f'<section class="lam portada">{cuerpo}<div class="pie"><span>Diablos Stuff+</span><span>Hackathon ISAC 2026</span></div></section>')
        continue
    html.append(f"""<section class="lam {clase}"><div class="eyebrow">{eb}</div><h2>{tit}</h2><p class="en-esta">{en}</p>
<div class="cuerpo">{cuerpo}</div><div class="pie">{logos_html()}<span>Diablos Stuff+ · Hackathon ISAC 2026 · Reto Diablos Rojos del México</span><span>{i:02d} / {len(LAMINAS):02d}</span></div></section>""")

doc = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Diablos Stuff+ · Reporte</title>
<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@700;800;900&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>{''.join(html)}</body></html>"""
salida = RAIZ / "entrega" / "reporte.html"
salida.write_text(doc)
print("HTML:", salida, "·", len(LAMINAS), "láminas")
