"""
06_dashboard.py — Dashboard simulador como narrativa de una página (HTML autocontenido).
Variante offline (plotly inline) para el entregable y variante CDN para publicar.
"""
import json, os, sys
sys.path.insert(0, '/home/claude/stuffplus/src')
import plotly, pandas as pd
OUT = '/home/claude/stuffplus/out'; DEL = '/home/claude/stuffplus/deliverables'
models = json.load(open(f'{OUT}/models/compact_models.json'))
scale = json.load(open(f'{OUT}/scale.json'))
trans = json.load(open(f'{OUT}/translation_factors.json'))
presets = json.load(open(f'{OUT}/dash_presets.json'))
for f in presets:
    for k in presets[f]: presets[f][k] = round(presets[f][k]) if k == 'SpinRate' else round(presets[f][k], 1)
movement = json.load(open(f'{OUT}/dash_movement.json'))
comparables = json.load(open(f'{OUT}/dash_comparables.json'))
fd = pd.read_csv(f'{OUT}/family_delta.csv', index_col=0)
fam_delta = {f: dict(delta_cf=round(r.delta_cf, 1), delta_obs=None if pd.isna(r.delta_obs) else round(r.delta_obs, 1), stuff_sea=round(r.stuff_sea, 1), stuff_cdmx=round(r.stuff_cdmx_cf, 1),
                     whiff_sea=round(r.whiff_sea, 3), whiff_cdmx=round(r.whiff_cdmx, 3), hr_sea=round(r.hr_sea, 3), hr_cdmx=round(r.hr_cdmx, 3)) for f, r in fd.iterrows()}
summary = json.load(open(f'{OUT}/altitude_summary.json'))
eff = pd.read_csv(f'{OUT}/altitude_effects.csv')
FAMILY_ES = {'Fastball-Ride': 'Recta con ride', 'Fastball-Run': 'Recta con run', 'Fastball-Cut': 'Recta con cut', 'Sinker': 'Sinker', 'Cutter': 'Cutter', 'Changeup': 'Changeup', 'Slider-Gyro': 'Slider gyro', 'Sweeper': 'Sweeper', 'Slurve': 'Slurve', 'Curveball': 'Curva'}
FAMILY_ORDER = [f for f in ['Fastball-Ride', 'Fastball-Run', 'Fastball-Cut', 'Sinker', 'Cutter', 'Changeup', 'Slider-Gyro', 'Sweeper', 'Slurve', 'Curveball'] if f in presets]
ext = eff[eff.level == 'Extreme Altitude']
fam_phys = {f: dict(ivb=float(ext[(ext.family == f) & (ext['var'] == 'InducedVertBreak')].delta.iloc[0]), hb=float(ext[(ext.family == f) & (ext['var'] == 'hb_arm')].delta.iloc[0]), tot=float(ext[(ext.family == f) & (ext['var'] == 'total_break')].pct.iloc[0])) for f in FAMILY_ORDER if (ext.family == f).any()}
o = summary['outcomes']
story = dict(break_pct=round(100 * (1 - summary['Extreme Altitude']['break_ratio_obs'])), fb_dist=round(summary['fb_distance_controlled']['Extreme Altitude']['mean'] - summary['fb_distance_controlled']['No Altitude']['mean']),
             hr_bip_sea=o['No Altitude']['hr_per_bip'], hr_bip_ext=o['Extreme Altitude']['hr_per_bip'], whiff_sea=o['No Altitude']['whiff_per_swing'], whiff_ext=o['Extreme Altitude']['whiff_per_swing'],
             mean_delta=round(fd.delta_cf.mean(), 1), n_pitches=625650, n_pitchers=1039)
DATA = dict(models=models, scale=scale, trans=trans, presets=presets, movement=movement, comparables=comparables, fam_delta=fam_delta, fam_phys=fam_phys, FAMILY_ES=FAMILY_ES, FAMILY_ORDER=FAMILY_ORDER, story=story)

HTML = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Stuff+ para el Harp Helú</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700;800&family=Barlow:ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">
<style>
:root{
  --paper:#ffffff; --wash:#f4f4f2; --ink:#000000; --ink-2:#4d4d4d; --muted:#8c8c8c; --rule:#e4e4e1; --rule-2:#cfcfcb;
  --sea:#2e6fd8; --sea-soft:#dce8fa; --home:#c8102e; --home-soft:#f9dfe3; --home-deep:#8c0b20; --gain:#1a7f3c;
  --display:"Barlow Condensed", "Arial Narrow", Impact, system-ui, sans-serif; --body:"Barlow", system-ui, -apple-system, "Segoe UI", sans-serif;
  color-scheme:light;
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){
  --paper:#121212; --wash:#1c1c1c; --ink:#f3f3f1; --ink-2:#bdbdb8; --muted:#8c8c8c; --rule:#2b2b2a; --rule-2:#3c3c3a;
  --sea:#5a93e8; --sea-soft:#1b2c48; --home:#e5304c; --home-soft:#3d1118; --home-deep:#ff6b80; --gain:#4cc26f; color-scheme:dark; }}
:root[data-theme="dark"]{
  --paper:#121212; --wash:#1c1c1c; --ink:#f3f3f1; --ink-2:#bdbdb8; --muted:#8c8c8c; --rule:#2b2b2a; --rule-2:#3c3c3a;
  --sea:#5a93e8; --sea-soft:#1b2c48; --home:#e5304c; --home-soft:#3d1118; --home-deep:#ff6b80; --gain:#4cc26f; color-scheme:dark; }
*{box-sizing:border-box}
input,select,button{min-width:0;max-width:100%}
.hero>*,.zones>*,.probs>*,.sl>*,.pitch .r1>*,.pitch .r2>*,.prof>*,.maprow>*,.fams>*,.fam>*,.story>*,.fit>*,.guide>*{min-width:0}
.top nav{min-width:0}
html{scroll-behavior:smooth}
@media (prefers-reduced-motion: reduce){ html{scroll-behavior:auto} .trail circle{animation:none !important;opacity:1 !important} }
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 var(--body)}
a{color:inherit}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px}
/* nav */
.top{position:sticky;top:0;z-index:20;background:var(--paper);border-bottom:1px solid var(--rule)}
.top::before{content:"";display:block;height:4px;background:var(--home)}
.top .wrap{display:flex;align-items:center;gap:18px;height:56px}
.brand{font-family:var(--display);font-weight:700;font-size:22px;letter-spacing:.01em;text-decoration:none;display:flex;align-items:center;gap:10px}
.brand b{display:inline-block;background:var(--home);color:#fff;padding:0 7px;border-radius:3px;font-weight:800}
.brand .team{font-family:var(--body);font-weight:500;font-size:13px;color:var(--ink-2);margin-left:6px}
@media (max-width:560px){.brand .team{display:none}}
.top nav{margin-left:auto;display:flex;gap:4px;overflow-x:auto;-webkit-overflow-scrolling:touch}
.top nav a{text-decoration:none;color:var(--ink-2);padding:8px 10px;font-size:15px;white-space:nowrap;border-bottom:2px solid transparent}
.top nav a.on{color:var(--ink);border-bottom-color:var(--home)}
.top nav a:focus-visible,button:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--sea);outline-offset:2px}
/* sections */
section{padding:56px 0;border-bottom:1px solid var(--rule)}
section:last-of-type{border-bottom:0}
h1{font-family:var(--display);font-weight:800;font-size:clamp(40px,6vw,72px);line-height:.95;letter-spacing:-.01em;margin:0 0 16px;max-width:14ch}
h2{font-family:var(--display);font-weight:700;font-size:clamp(30px,4vw,44px);line-height:1;margin:0 0 10px;letter-spacing:-.005em}
h3{font-family:var(--display);font-weight:600;font-size:22px;margin:0 0 8px;letter-spacing:.005em}
.lead{font-size:19px;line-height:1.45;color:var(--ink-2);max-width:62ch;margin:0 0 28px}
.lead strong{color:var(--ink);font-weight:600}
p{max-width:68ch}
.note{font-size:14px;color:var(--ink-2);max-width:72ch}
.sea-t{color:var(--sea);font-weight:600} .home-t{color:var(--home);font-weight:600}
/* hero layout */
.hero{display:grid;grid-template-columns:1fr 340px;gap:40px;align-items:start}
@media (max-width:960px){.hero{grid-template-columns:1fr}}
.zones{display:grid;grid-template-columns:1fr 1fr;gap:24px}
@media (max-width:560px){.zones{grid-template-columns:1fr}}
.zone{position:relative}
.zone h3{display:flex;align-items:baseline;justify-content:space-between;gap:8px;border-bottom:3px solid;padding-bottom:6px;margin-bottom:10px}
.zone.sea h3{border-color:var(--sea)} .zone.home h3{border-color:var(--home)}
.zone h3 small{font-family:var(--body);font-weight:400;font-size:13px;color:var(--ink-2)}
.zone svg{width:100%;height:auto;display:block;background:var(--wash);border-radius:6px}
.big{font-family:var(--display);font-weight:800;font-size:88px;line-height:.9;letter-spacing:-.02em;margin:12px 0 2px}
.zone.sea .big{color:var(--sea)} .zone.home .big{color:var(--home)}
.big small{font-family:var(--body);font-weight:500;font-size:14px;color:var(--ink-2);letter-spacing:0;margin-left:8px}
.sub{font-size:14px;color:var(--ink-2);line-height:1.4}
.sub b{color:var(--ink);font-weight:600}
.verdict{margin-top:18px;padding:14px 16px;border-left:4px solid var(--home);background:var(--wash);font-size:16px;max-width:none}
.verdict .d{font-family:var(--display);font-weight:800;font-size:34px;line-height:1;margin-right:8px;vertical-align:-4px}
.verdict .d.neg{color:var(--home)} .verdict .d.pos{color:var(--gain)}
/* controls */
.controls{position:sticky;top:72px}
@media (max-width:960px){.controls{position:static}}
.ctl{margin-bottom:14px}
.ctl label{display:block;font-size:13px;color:var(--ink-2);margin-bottom:4px}
.seg{display:flex;border:1px solid var(--rule-2);border-radius:6px;overflow:hidden}
.seg button{flex:1;background:transparent;border:0;color:var(--ink-2);padding:8px 6px;cursor:pointer;font:inherit;font-size:14px}
.seg button.on{background:var(--ink);color:var(--paper)}
select,input[type=number]{font:inherit;background:var(--paper);color:var(--ink);border:1px solid var(--rule-2);border-radius:6px;padding:7px 9px;width:100%}
.sl{display:grid;grid-template-columns:1fr 86px;gap:8px;align-items:center}
.sl label{grid-column:1/-1;margin-bottom:0}
input[type=range]{width:100%;accent-color:var(--ink);margin:0}
.sl input[type=number]{padding:5px 6px;font-variant-numeric:tabular-nums;text-align:right;font-family:var(--display);font-size:17px}
.ctl-group{padding-top:12px;margin-top:12px;border-top:1px solid var(--rule)}
.ctl-group .t{font-family:var(--display);font-size:17px;font-weight:600;margin-bottom:8px}
/* probabilities */
.probs{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;margin-top:28px}
@media (max-width:960px){.probs{grid-template-columns:repeat(3,1fr)}}
@media (max-width:560px){.probs{grid-template-columns:repeat(2,1fr)}}
.prob{border-top:1px solid var(--rule-2);padding-top:8px}
.prob .l{font-size:13px;color:var(--ink-2);min-height:34px;line-height:1.25}
.prob .v{font-family:var(--display);font-size:24px;font-weight:700;line-height:1;margin-top:6px;display:flex;align-items:baseline;gap:5px;white-space:nowrap}
.prob .v .s{color:var(--sea)} .prob .v .h{color:var(--home)}
.prob .v .arrow{font-size:16px;color:var(--muted);font-family:var(--body)}
.prob .bars{height:6px;position:relative;margin-top:8px;background:var(--wash);border-radius:3px;overflow:hidden}
.prob .bars i{position:absolute;left:0;top:0;bottom:0;border-radius:3px}
.prob .bars i.s{background:var(--sea);opacity:.55} .prob .bars i.h{background:var(--home)}
/* family bars */
.fams{display:grid;grid-template-columns:1fr;gap:4px;margin-top:28px;max-width:820px}
.fam{display:grid;grid-template-columns:150px 1fr 56px;gap:12px;align-items:center;cursor:pointer;padding:5px 6px;border-radius:6px}
@media (max-width:560px){.fam{grid-template-columns:110px 1fr 50px}}
.fam:hover,.fam.on{background:var(--wash)}
.fam .n{font-family:var(--display);font-size:19px;font-weight:600}
.fam .bar{height:12px;background:var(--wash);border-radius:3px;position:relative;overflow:hidden}
.fam .bar i{position:absolute;right:0;top:0;bottom:0;background:var(--home);border-radius:3px}
.fam .bar i.avg{right:auto;width:2px;background:var(--ink);opacity:.5}
.fam .v{font-family:var(--display);font-size:22px;font-weight:700;color:var(--home);text-align:right}
.fam-detail{margin-top:18px;padding:16px 18px;background:var(--wash);border-radius:8px;display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
@media (max-width:760px){.fam-detail{grid-template-columns:1fr 1fr}}
.fam-detail .k{font-size:13px;color:var(--ink-2)} .fam-detail .v{font-family:var(--display);font-size:26px;font-weight:700}
.story{display:grid;grid-template-columns:repeat(3,1fr);gap:28px;margin-top:28px}
@media (max-width:760px){.story{grid-template-columns:1fr}}
.story .n{font-family:var(--display);font-size:clamp(40px,4.6vw,60px);font-weight:800;line-height:.95;color:var(--home);white-space:nowrap}
.story .n.blue{color:var(--sea)}
.story p{font-size:15px;color:var(--ink-2);margin:8px 0 0}
/* map */
.filters{display:flex;gap:22px;flex-wrap:wrap;align-items:flex-end;margin:18px 0 8px}
.filters .ctl{margin:0;min-width:220px}
.filters .seg button{white-space:nowrap;padding:8px 12px}
.pills{display:flex;flex-wrap:wrap;gap:6px}
.pill{border:1px solid var(--rule-2);border-radius:999px;padding:4px 11px;font-size:14px;cursor:pointer;background:transparent;color:var(--ink-2);font:inherit}
.pill.on{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.plot{min-height:300px}
.maprow{display:grid;grid-template-columns:1fr 360px;gap:28px;align-items:start}
@media (max-width:960px){.maprow{grid-template-columns:1fr}}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{padding:7px 8px;border-bottom:1px solid var(--rule);text-align:right;font-variant-numeric:tabular-nums;vertical-align:top}
th{color:var(--ink-2);font-weight:500;font-size:13px}
td:first-child,th:first-child{text-align:left}
td .id{font-family:var(--display);font-size:16px;font-weight:600}
td .meta{font-size:12.5px;color:var(--ink-2)}
.tbl-t{font-family:var(--display);font-size:19px;font-weight:600;margin:0 0 6px}
/* profiler */
.prof{display:grid;grid-template-columns:400px 1fr;gap:36px;align-items:start}
@media (max-width:960px){.prof{grid-template-columns:1fr}}
.pitch{border:1px solid var(--rule-2);border-radius:8px;padding:12px;margin-top:10px;background:var(--paper)}
.pitch .r1{display:grid;grid-template-columns:1fr 84px 34px;gap:8px;align-items:end}
.pitch .r2{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:8px}
.pitch label{font-size:12px;color:var(--ink-2);display:block;margin-bottom:3px}
.pitch input{padding:6px 7px;font-family:var(--display);font-size:16px;text-align:right}
.btn{background:var(--ink);color:var(--paper);border:0;border-radius:6px;padding:10px 16px;cursor:pointer;font:inherit;font-weight:600}
.btn.ghost{background:transparent;color:var(--ink);border:1px solid var(--rule-2)}
.btn.home{background:var(--home);color:#fff}
.fit{display:grid;grid-template-columns:1fr 1fr 1fr;gap:18px;margin-bottom:18px}
@media (max-width:560px){.fit{grid-template-columns:1fr}}
.fit .k{font-size:13px;color:var(--ink-2)} .fit .v{font-family:var(--display);font-size:52px;font-weight:800;line-height:.95}
.fit .v.sea{color:var(--sea)} .fit .v.home{color:var(--home)}
.flag{padding:12px 14px;border-left:4px solid var(--rule-2);margin-top:10px;font-size:15px;background:var(--wash)}
.flag.risk{border-color:var(--home)} .flag.good{border-color:var(--gain)}
.flag b{display:block;font-family:var(--display);font-size:19px;font-weight:600}
.verdict-line{font-family:var(--display);font-size:30px;font-weight:700;line-height:1.05;margin:0 0 6px}
/* guide */
.guide{display:grid;grid-template-columns:1fr 1fr;gap:28px 48px}
@media (max-width:760px){.guide{grid-template-columns:1fr}}
.guide p{margin:0 0 8px;font-size:15px;color:var(--ink-2)}
.guide h3{margin-top:4px}
.scale{display:flex;gap:0;margin:8px 0 16px;border-radius:6px;overflow:hidden;font-family:var(--display);font-weight:600;font-size:16px}
.scale div{flex:1;padding:8px 10px;color:#fff;text-align:center}
footer{padding:28px 0 48px;color:var(--muted);font-size:13px}
@media (max-width:760px){ table{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch} .top .wrap{height:auto;flex-wrap:wrap;padding-top:8px;padding-bottom:4px} .top nav{margin-left:0;width:100%} }
</style>
</head>
<body>
<div class="top"><div class="wrap">
  <a class="brand" href="#aire"><b>S+</b> Stuff+ para el Harp Helú <span class="team">Data Divas</span></a>
  <nav><a href="#aire" class="on">El aire</a><a href="#formas">Qué pierde cada forma</a><a href="#mapa">La liga</a><a href="#prospecto">Prospecto</a><a href="#guia">Cómo leerlo</a></nav>
</div></div>

<!-- ============ 1. EL AIRE / SIMULADOR ============ -->
<section id="aire"><div class="wrap">
  <h1>El mismo pitch no llega igual al Harp Helú.</h1>
  <p class="lead">A 2,240 metros el aire es un 20% menos denso. Comparamos a los mismos pitchers lanzando en la costa y en casa, <strong>__N_PITCHES__ lanzamientos</strong> de la LMB, y entrenamos un modelo que mide la calidad física de cada pitch en los dos ambientes. Esta es la vista del catcher: ajusta el pitch y mira qué pasa con su movimiento y con su valor.</p>
  <div class="hero">
    <div>
      <div class="zones">
        <div class="zone sea"><h3>Nivel del mar <small>Veracruz, Mérida, Tabasco…</small></h3>
          <svg id="svg-sea" viewBox="0 0 300 300" role="img" aria-label="Zona de strike con el movimiento del pitch a nivel del mar"></svg>
          <div class="big" id="sp-sea">—<small>Stuff+</small></div><div class="sub" id="sub-sea"></div></div>
        <div class="zone home"><h3>Harp Helú <small>2,240 m</small></h3>
          <svg id="svg-home" viewBox="0 0 300 300" role="img" aria-label="Zona de strike con el movimiento del pitch en el Harp Helú"></svg>
          <div class="big" id="sp-home">—<small>Stuff+</small></div><div class="sub" id="sub-home"></div></div>
      </div>
      <div class="verdict" id="verdict"></div>
      <div class="probs" id="probs"></div>
      <p class="note" style="margin-top:14px">Las estelas muestran cuánto se desvía el pitch respecto a una trayectoria sin spin (sólo gravedad), vista desde atrás del plato. Las probabilidades salen del modelo físico (características en el release más ambiente); rolling, contacto duro y jonrón son condicionales a bola en juego.</p>
    </div>
    <div class="controls">
      <div class="ctl"><label>Familia del pitch</label><select id="family"></select></div>
      <div class="ctl"><label>Mano del pitcher</label><div class="seg" id="hand"><button class="on" data-v="1">Derecho</button><button data-v="0">Zurdo</button></div></div>
      <div class="ctl"><label>Estas medidas se tomaron…</label><div class="seg" id="measured"><button class="on" data-v="0">A nivel del mar</button><button data-v="2">En el Harp Helú</button></div></div>
      <div class="ctl-group"><div class="t">Velocidad y spin</div><div id="sl-a"></div></div>
      <div class="ctl-group"><div class="t">Movimiento</div><div id="sl-b"></div><div class="note" style="margin-top:6px">HB positivo = hacia el lado del brazo del pitcher.</div></div>
      <div class="ctl-group"><div class="t">Punto de liberación</div><div id="sl-c"></div></div>
    </div>
  </div>
</div></section>

<!-- ============ 2. QUÉ PIERDE CADA FORMA ============ -->
<section id="formas"><div class="wrap">
  <h2>Todas las formas pierden en casa. No todas pierden igual.</h2>
  <p class="lead">Tomamos cada pitch lanzado a nivel del mar, lo trasladamos al aire de CDMX con lo que medimos en los mismos pitchers y lo volvimos a evaluar. El ambiente le quita <strong>__MEAN_DELTA__ puntos de Stuff+</strong> al pitch promedio (10 puntos = una desviación estándar). Lo que cambia entre formas es lo que decide el repertorio de casa.</p>
  <div class="story">
    <div><div class="n">−__BREAK_PCT__%</div><p>de movimiento pierde el mismo pitcher con el mismo pitch en el Harp Helú. Su velocidad y su spin no cambian: el aire se lleva el efecto Magnus.</p></div>
    <div><div class="n">+__FB_DIST__ ft</div><p>viaja la misma pelota bateada (90–110 mph, 20–35°) en CDMX. Un elevado en juego cuesta cuatro veces más carreras que en la costa.</p></div>
    <div><div class="n blue">__WHIFF_SEA__% → __WHIFF_EXT__%</div><p>cae la tasa de swings fallidos. Con menos movimiento hay menos engaño, y el contacto que llega sale más caliente.</p></div>
  </div>
  <div class="fams" id="fams"></div>
  <div class="fam-detail" id="fam-detail"></div>
  <p class="note" style="margin-top:12px">La barra es el Δ Stuff+ al trasladar el mismo pitch; la marca vertical es el promedio de todas las formas. Toca una familia para ver el detalle. Validación: el Δ que el modelo predice coincide con el observado en los pitchers que lanzaron en ambos ambientes.</p>
</div></section>

<!-- ============ 3. MAPA ============ -->
<section id="mapa"><div class="wrap">
  <h2>Dónde vive cada pitch de la liga.</h2>
  <p class="lead">Cada punto es un pitcher con una familia de pitch en un ambiente: su movimiento promedio real y qué tan bueno es comparado con lo que se lanza en ese mismo aire. Cambia el ambiente y mira cómo el mapa entero se encoge hacia el centro.</p>
  <div class="filters">
    <div class="ctl"><label>Ambiente</label><div class="seg" id="map-alt"><button data-v="0">Nivel del mar</button><button data-v="1">Altitud media</button><button class="on" data-v="2">Harp Helú</button></div></div>
    <div class="ctl"><label>Mano</label><div class="seg" id="map-hand"><button class="on" data-v="all">Ambas</button><button data-v="Right">Derechos</button><button data-v="Left">Zurdos</button></div></div>
    <div class="ctl"><label>Color</label><div class="seg" id="map-color"><button class="on" data-v="stuff_plus">Stuff+</button><button data-v="pitching_plus">Pitching+</button><button data-v="delta_cf">Δ en casa</button></div></div>
    <div class="ctl" style="flex:1"><label>Familias</label><div class="pills" id="map-fams"></div></div>
  </div>
  <div class="maprow">
    <div id="map-plot" class="plot" style="min-height:560px"></div>
    <div id="map-tables"></div>
  </div>
  <p class="note">Puntos con ≥25 lanzamientos; tamaño = volumen. El color se centra en el promedio del ambiente elegido, así que rojo es "mejor que lo que se lanza aquí" y azul "peor". Pasa el cursor sobre un punto para el detalle.</p>
</div></section>

<!-- ============ 4. PROSPECTO ============ -->
<section id="prospecto"><div class="wrap">
  <h2>¿Le sirve a Diablos?</h2>
  <p class="lead">Captura el arsenal de un prospecto o agente libre con sus mediciones Trackman. Trasladamos cada pitch al aire del Harp Helú, lo calificamos contra los pitchers reales que han lanzado ahí y te decimos qué resiste, qué se cae y a quién se parece.</p>
  <div class="prof">
    <div>
      <div class="ctl"><label>Mano</label><div class="seg" id="p-hand"><button class="on" data-v="1">Derecho</button><button data-v="0">Zurdo</button></div></div>
      <div class="ctl"><label>Las medidas se tomaron…</label><div class="seg" id="p-measured"><button class="on" data-v="0">A nivel del mar</button><button data-v="2">En el Harp Helú</button></div></div>
      <div class="pitch" style="margin-top:0"><div class="r2" style="margin-top:0"><div><label>Altura release (ft)</label><input type="number" id="p-relh" value="5.8" step="0.1"></div><div><label>Lado release (ft)</label><input type="number" id="p-rels" value="1.8" step="0.1"></div><div><label>Extensión (ft)</label><input type="number" id="p-ext" value="6.0" step="0.1"></div></div></div>
      <div id="p-pitches"></div>
      <div style="display:flex;gap:8px;margin-top:12px"><button class="btn ghost" id="p-add">Agregar pitch</button><button class="btn home" id="p-run">Evaluar para Diablos</button></div>
    </div>
    <div>
      <div id="p-verdict"></div>
      <div class="fit" id="p-fit"></div>
      <div id="p-flags"></div>
      <h3 style="margin-top:26px">Pitch por pitch en el Harp Helú</h3>
      <div id="p-table"></div>
      <h3 style="margin-top:26px">A quién se parece (pitchers reales en casa)</h3>
      <div id="p-comps"></div>
      <p class="note">Pitcher-temporadas anonimizados con ≥200 lanzamientos en altitud extrema, ordenados por similitud física del arsenal. Stuff+ y Pitching+ ajustados al ambiente (100 = promedio en CDMX). xRV/100 = carreras evitadas por cada 100 pitches; positivo es bueno para el pitcher.</p>
    </div>
  </div>
</div></section>

<!-- ============ 5. GUÍA ============ -->
<section id="guia"><div class="wrap">
  <h2>Cómo leerlo.</h2>
  <div class="guide">
    <div>
      <h3>La escala</h3>
      <div class="scale"><div style="background:#8c8c8c">80 reemplazo</div><div style="background:#5c5c5c">90</div><div style="background:#000">100 promedio</div><div style="background:#8c0b20">110</div><div style="background:#c8102e">120 élite</div></div>
      <p>Stuff+ = 100 + 10 × z. Cien es el pitch promedio de la LMB a nivel del mar; cada 10 puntos son una desviación estándar. Más alto siempre es mejor, sin importar el tipo de pitch.</p>
      <p>El número grande del Harp Helú está en la misma escala que el de nivel del mar: la diferencia entre ambos es el efecto del aire sobre ese pitch. Como el ambiente le quita ~14 puntos a todo, debajo aparece el Stuff+ ajustado al ambiente (100 = promedio de lo que se lanza en CDMX), que es el que sirve para comparar a un pitcher con sus pares en casa.</p>
      <h3>Qué mide</h3>
      <p>El valor esperado en carreras de cada lanzamiento, con linear weights calculados con datos de la propia LMB, a partir de sus características físicas en el release: velocidad, spin, eje, movimiento, punto de liberación y extensión, más el ambiente. No usa ubicación, conteo ni resultado observado; eso vive en Location+ y Pitching+, dentro del reporte técnico.</p>
    </div>
    <div>
      <h3>Cómo traslada un pitch</h3>
      <p>Si capturas medidas de nivel del mar, el simulador reduce el IVB y el HB con los factores empíricos de su familia (estimados comparando a los mismos pitchers en ambos ambientes) antes de evaluarlo en el Harp Helú. Si las medidas son de CDMX, hace la operación inversa.</p>
      <h3>Qué no hace</h3>
      <p>No conoce al bateador, la secuencia ni la ubicación. Un pitch con Stuff+ alto y mal comando sigue siendo un problema de comando. Tampoco es causal: describe qué pitches rinden, no qué pasaría si un pitcher cambiara su agarre.</p>
      <h3>Datos y modelo</h3>
      <p>__N_PITCHES__ lanzamientos Trackman de la LMB (2024–2026), __N_PITCHERS__ pitchers, tres niveles de altitud, identificadores anonimizados. Gradient boosting (LightGBM) validado con holdout por pitcher, por temporada y por estadio; el modelo completo se evalúa en tu navegador y nada sale de esta página.</p>
    </div>
  </div>
</div></section>
<footer class="wrap">Equipo Data Divas · Sports Analytics Hackathon ISAC 2026, presentado por Diablos Rojos del México.</footer>

__PLOTLY__
<script id="data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
__LGB__
const S = D.scale, FE = D.FAMILY_ES, PHYS = D.fam_phys;
const toPlus = rv => 100 + 10*(rv - S.stuff.mu_sea)/S.stuff.sd_sea;
const adjS = (sp,alt)=>100+10*(sp-S['stuff_dist_alt'+alt].mean)/S['stuff_dist_alt'+alt].sd;
const adjP = (sp,alt)=>100+10*(sp-S['pitching_dist_alt'+alt].mean)/S['pitching_dist_alt'+alt].sd;
function pctile(sp, alt){ const p = S['stuff_dist_alt'+alt].pct; if (sp<=p[0]) return 0; if (sp>=p[20]) return 100; for(let i=0;i<20;i++){ if (sp<p[i+1]) return Math.round(5*(i + (sp-p[i])/(p[i+1]-p[i]))); } return 100; }
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const fmt1 = x => (x>=0?'+':'−')+Math.abs(x).toFixed(1);
const plotBase = () => ({paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)', font:{family:'Barlow, system-ui, sans-serif', size:13, color:css('--ink')},
  xaxis:{gridcolor:css('--rule'), zerolinecolor:css('--rule-2'), linecolor:css('--rule'), tickfont:{color:css('--ink-2')}, title:{font:{color:css('--ink-2')}}},
  yaxis:{gridcolor:css('--rule'), zerolinecolor:css('--rule-2'), linecolor:css('--rule'), tickfont:{color:css('--ink-2')}, title:{font:{color:css('--ink-2')}}},
  margin:{l:56,r:20,t:10,b:50}, hoverlabel:{font:{family:'Barlow, system-ui, sans-serif'}}, legend:{font:{color:css('--ink-2')}, bgcolor:'rgba(0,0,0,0)'}});

function features(p, alt){ const rad = p.axis*Math.PI/180; const tb = Math.hypot(p.ivb, p.hb);
  return {RelSpeed:p.velo, SpinRate:p.spin, axis_sin:Math.sin(rad), axis_cos:Math.cos(rad), InducedVertBreak:p.ivb, hb_arm:p.hb, total_break:tb, break_per_krpm: tb/(p.spin/1000), bauer:p.spin/p.velo, RelHeight:p.relh, rel_side_arm:p.rels, Extension:p.ext, is_rhp:p.rhp, alt_level:alt}; }
function translate(p, fam, from, to){ const t = D.trans[fam] || {ivb_ratio:0.76, hb_ratio:0.74, medium:{ivb_ratio:0.82,hb_ratio:0.82}};
  const r = lvl => lvl===0 ? {i:1,h:1} : lvl===2 ? {i:t.ivb_ratio,h:t.hb_ratio} : {i:(t.medium||{}).ivb_ratio||0.82, h:(t.medium||{}).hb_ratio||0.82};
  const a = r(from), b = r(to); return Object.assign({}, p, {ivb: p.ivb*b.i/a.i, hb: p.hb*b.h/a.h}); }
function evaluate(p, fam, measured){ const pSea = translate(p, fam, measured, 0), pCd = translate(p, fam, measured, 2); const fSea = features(pSea,0), fCd = features(pCd,2);
  const out = {sea:{sp: toPlus(lgbPredict(D.models.stuff_rv, fSea)), p:pSea}, cdmx:{sp: toPlus(lgbPredict(D.models.stuff_rv, fCd)), p:pCd}};
  for (const h of ['whiff','called_strike','chase','gb','hard','hr']){ const m = D.models['stuff_'+h]; if(!m) continue; out.sea[h]=lgbPredict(m,fSea); out.cdmx[h]=lgbPredict(m,fCd); } return out; }
function seg(id, cb){ const el=document.getElementById(id); el.querySelectorAll('button').forEach(b=>b.onclick=()=>{el.querySelectorAll('button').forEach(x=>x.classList.remove('on'));b.classList.add('on');cb(b.dataset.v);}); }

/* ---------- nav highlight ---------- */
const navLinks=[...document.querySelectorAll('.top nav a')];
const io=new IntersectionObserver(es=>{es.forEach(e=>{ if(e.isIntersecting){ navLinks.forEach(a=>a.classList.toggle('on', a.getAttribute('href')==='#'+e.target.id)); }});},{rootMargin:'-40% 0px -55% 0px'});
document.querySelectorAll('section').forEach(s=>io.observe(s));

/* ---------- strike zone drawing ---------- */
// Vista del catcher. 1 in = 5 px. Zona 17" x 24" centrada. Punto fantasma = dónde cruzaría sin spin; la estela va del fantasma a la posición real.
function drawZone(svgId, p, color, rhp, animate){
  const svg=document.getElementById(svgId); const PX=5, cx=150, cy=165;
  const hbCatcher = (rhp? -1 : 1) * p.hb; // lado del brazo del derecho = hacia la derecha del pitcher = izquierda del catcher
  const gx=cx, gy=cy+40; // fantasma, un poco bajo (gravedad)
  const ex=gx+hbCatcher*PX, ey=gy-p.ivb*PX;
  const steps=7; let dots='';
  for(let i=1;i<=steps;i++){ const t=i/steps; const x=gx+(ex-gx)*t*t, y=gy+(ey-gy)*t*t; const r=4+9*t; const op=0.18+0.82*t;
    dots+=`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r}" fill="${i===steps?color:color}" opacity="${op.toFixed(2)}" style="${animate?`animation:pop .5s ${(i*0.07).toFixed(2)}s both`:''}"></circle>`; }
  const rule=css('--rule-2'), ink2=css('--ink-2'), wash=css('--wash');
  svg.innerHTML=`<style>@keyframes pop{from{opacity:0;transform:scale(.4);transform-origin:center;transform-box:fill-box}to{transform:scale(1)}}</style>
    <rect x="0" y="0" width="300" height="300" fill="${wash}"/>
    <rect x="${cx-8.5*PX}" y="${cy-12*PX}" width="${17*PX}" height="${24*PX}" fill="none" stroke="${ink2}" stroke-width="1.5"/>
    <line x1="${cx-8.5*PX}" y1="${cy-4*PX}" x2="${cx+8.5*PX}" y2="${cy-4*PX}" stroke="${rule}"/><line x1="${cx-8.5*PX}" y1="${cy+4*PX}" x2="${cx+8.5*PX}" y2="${cy+4*PX}" stroke="${rule}"/>
    <line x1="${cx-8.5*PX/3}" y1="${cy-12*PX}" x2="${cx-8.5*PX/3}" y2="${cy+12*PX}" stroke="${rule}"/><line x1="${cx+8.5*PX/3}" y1="${cy-12*PX}" x2="${cx+8.5*PX/3}" y2="${cy+12*PX}" stroke="${rule}"/>
    <path d="M${cx-8.5*PX} 292 L${cx+8.5*PX} 292 L${cx+8.5*PX} 297 L${cx} 300 L${cx-8.5*PX} 297 Z" fill="${ink2}" opacity=".5"/>
    <circle cx="${gx}" cy="${gy}" r="6" fill="none" stroke="${ink2}" stroke-dasharray="2 2"/>
    <line x1="${gx}" y1="${gy}" x2="${ex}" y2="${ey}" stroke="${color}" stroke-width="1" stroke-dasharray="3 3" opacity=".6"/>
    <g class="trail">${dots}</g>
    <text x="10" y="18" font-family="Barlow, system-ui" font-size="11" fill="${ink2}">${(rhp?'lado del guante':'lado del brazo')}</text>
    <text x="290" y="18" text-anchor="end" font-family="Barlow, system-ui" font-size="11" fill="${ink2}">${(rhp?'lado del brazo':'lado del guante')}</text>
    <text x="${ex + (ex>150? -16 : 16)}" y="${ey+5}" text-anchor="${ex>150?'end':'start'}" font-family="Barlow Condensed, system-ui" font-size="15" font-weight="700" fill="${color}">${Math.hypot(p.ivb,p.hb).toFixed(0)}" de movimiento</text>`;
}

/* ---------- simulador ---------- */
const SL = {a:[['velo','Velocidad (mph)',70,100,0.1],['spin','Spin (rpm)',1000,3400,10],['axis','Eje de spin (°, 180 = backspin puro)',0,360,1]],
            b:[['ivb','Movimiento vertical inducido, IVB (in)',-22,25,0.1],['hb','Movimiento horizontal, HB (in)',-22,25,0.1]],
            c:[['relh','Altura (ft)',4,7.5,0.05],['rels','Lado (ft)',-1,4.5,0.05],['ext','Extensión (ft)',4.5,7.8,0.05]]};
const sim = {rhp:1, fam:'Fastball-Ride', measured:0};
const famSel = document.getElementById('family');
D.FAMILY_ORDER.forEach(f=>{const o=document.createElement('option');o.value=f;o.textContent=FE[f];famSel.appendChild(o);});
for (const g of ['a','b','c']){ const host=document.getElementById('sl-'+g);
  SL[g].forEach(([k,lab,lo,hi,st])=>{ const d=document.createElement('div'); d.className='ctl sl'; d.innerHTML=`<label>${lab}</label><input type="range" id="r-${k}" min="${lo}" max="${hi}" step="${st}" aria-label="${lab}"><input type="number" id="n-${k}" step="${st}" aria-label="${lab}">`; host.appendChild(d);
    const r=d.querySelector('input[type=range]'), n=d.querySelector('input[type=number]'); r.oninput=()=>{n.value=r.value;sim[k]=+r.value;update(false);}; n.onchange=()=>{r.value=n.value;sim[k]=+n.value;update(false);}; }); }
function loadPreset(f){ const p=D.presets[f]; const map={velo:p.RelSpeed,spin:p.SpinRate,axis:p.SpinAxis,ivb:p.InducedVertBreak,hb:p.hb_arm,relh:p.RelHeight,rels:p.rel_side_arm,ext:p.Extension}; for(const k in map){sim[k]=+map[k]; document.getElementById('r-'+k).value=map[k]; document.getElementById('n-'+k).value=map[k];} }
famSel.onchange=()=>{sim.fam=famSel.value; loadPreset(sim.fam); update(true); selectFam(sim.fam);};
seg('hand', v=>{sim.rhp=+v; update(true);}); seg('measured', v=>{sim.measured=+v; update(true);});
const HEADS=[['whiff','Swing y falla'],['called_strike','Strike cantado'],['chase','Swing fuera de zona'],['gb','Rolling, si hay contacto'],['hard','Contacto duro, si hay contacto'],['hr','Jonrón, si hay contacto']];
function update(animate){
  const r = evaluate(sim, sim.fam, sim.measured); const a=r.sea.sp, b=r.cdmx.sp, d=b-a;
  document.getElementById('sp-sea').innerHTML=`${a.toFixed(0)}<small>Stuff+</small>`; document.getElementById('sp-home').innerHTML=`${b.toFixed(0)}<small>Stuff+</small>`;
  document.getElementById('sub-sea').innerHTML=`Percentil <b>${pctile(a,0)}</b> entre todo lo que se lanza a nivel del mar.<br>IVB <b>${r.sea.p.ivb.toFixed(1)}"</b>, HB <b>${r.sea.p.hb.toFixed(1)}"</b>.`;
  document.getElementById('sub-home').innerHTML=`Percentil <b>${pctile(b,2)}</b> entre lo que se lanza en casa; ajustado al ambiente, <b>${adjS(b,2).toFixed(0)}</b>.<br>IVB <b>${r.cdmx.p.ivb.toFixed(1)}"</b>, HB <b>${r.cdmx.p.hb.toFixed(1)}"</b>.`;
  drawZone('svg-sea', r.sea.p, css('--sea'), sim.rhp===1, animate); drawZone('svg-home', r.cdmx.p, css('--home'), sim.rhp===1, animate);
  const ph=PHYS[sim.fam]||{}; const fdl=D.fam_delta[sim.fam]; const lost=Math.hypot(r.sea.p.ivb,r.sea.p.hb)-Math.hypot(r.cdmx.p.ivb,r.cdmx.p.hb);
  let verdict = d<-12 ? 'Pierde más que el pitch promedio: su engaño depende del movimiento que el aire se lleva.' : d<-9 ? 'Pierde lo mismo que el pitch promedio.' : d<-5 ? 'Resiste mejor que el promedio: no depende tanto del efecto Magnus.' : 'Casi inmune al aire: lo que lo hace bueno no es el movimiento.';
  document.getElementById('verdict').innerHTML=`<span class="d ${d<0?'neg':'pos'}">${fmt1(d)}</span> Stuff+ al trasladarlo al Harp Helú. ${verdict} Pierde <b>${lost.toFixed(1)}"</b> de movimiento${fdl?` (la familia ${FE[sim.fam].toLowerCase()} pierde ${Math.abs(fdl.delta_cf).toFixed(1)} en promedio)`:''} y llega ~${Math.abs(D.trans[sim.fam]?.speeddrop_delta||1.1).toFixed(1)} mph más rápido al plato porque también hay menos drag.`;
  const probs=document.getElementById('probs'); probs.innerHTML='';
  HEADS.forEach(([h,lab])=>{ if(r.sea[h]===undefined) return; const s=r.sea[h], c=r.cdmx[h]; const mx=(h==='hr')?0.2:(h==='gb'||h==='hard')?0.8:0.6;
    probs.innerHTML+=`<div class="prob"><div class="l">${lab}</div><div class="v"><span class="s">${(100*s).toFixed(0)}%</span><span class="arrow">→</span><span class="h">${(100*c).toFixed(0)}%</span></div><div class="bars"><i class="s" style="width:${Math.min(100,100*s/mx)}%"></i><i class="h" style="width:${Math.min(100,100*c/mx)}%;top:3px;height:3px"></i></div></div>`; });
}
loadPreset(sim.fam); update(true);

/* ---------- familias ---------- */
const famsEl=document.getElementById('fams'); const fams=D.FAMILY_ORDER.filter(f=>D.fam_delta[f]);
const dmin=Math.min(...fams.map(f=>D.fam_delta[f].delta_cf)); const davg=fams.reduce((s,f)=>s+D.fam_delta[f].delta_cf,0)/fams.length;
fams.sort((a,b)=>D.fam_delta[b].delta_cf-D.fam_delta[a].delta_cf).forEach(f=>{ const d=D.fam_delta[f].delta_cf; const el=document.createElement('div'); el.className='fam'; el.dataset.f=f;
  el.innerHTML=`<div class="n">${FE[f]}</div><div class="bar"><i style="width:${100*d/dmin}%"></i><i class="avg" style="left:${100-100*davg/dmin}%"></i></div><div class="v">${fmt1(d)}</div>`;
  el.onclick=()=>{ selectFam(f); famSel.value=f; sim.fam=f; loadPreset(f); update(true); document.getElementById('aire').scrollIntoView({behavior:'smooth'}); }; famsEl.appendChild(el); });
function selectFam(f){ document.querySelectorAll('.fam').forEach(e=>e.classList.toggle('on', e.dataset.f===f)); const d=D.fam_delta[f], ph=PHYS[f]||{};
  document.getElementById('fam-detail').innerHTML=`<div><div class="k">${FE[f]}: Stuff+ nivel del mar → Harp Helú</div><div class="v"><span class="sea-t">${d.stuff_sea.toFixed(0)}</span> → <span class="home-t">${d.stuff_cdmx.toFixed(0)}</span></div></div>
    <div><div class="k">Movimiento perdido (IVB, HB)</div><div class="v">${fmt1(ph.ivb||0)}", ${fmt1(ph.hb||0)}"</div></div>
    <div><div class="k">Swing y falla</div><div class="v">${(100*d.whiff_sea).toFixed(1)}% → ${(100*d.whiff_cdmx).toFixed(1)}%</div></div>
    <div><div class="k">Jonrón si hay contacto</div><div class="v">${(100*d.hr_sea).toFixed(1)}% → ${(100*d.hr_cdmx).toFixed(1)}%</div></div>`; }
selectFam('Fastball-Ride');

/* ---------- mapa ---------- */
const mapState={alt:'2',hand:'all',color:'stuff_plus',fams:new Set(D.FAMILY_ORDER)};
seg('map-alt',v=>{mapState.alt=v;drawMap();}); seg('map-hand',v=>{mapState.hand=v;drawMap();}); seg('map-color',v=>{mapState.color=v;drawMap();});
const mf=document.getElementById('map-fams'); D.FAMILY_ORDER.forEach(f=>{const b=document.createElement('button');b.className='pill on';b.textContent=FE[f];b.onclick=()=>{if(mapState.fams.has(f)){mapState.fams.delete(f);b.classList.remove('on');}else{mapState.fams.add(f);b.classList.add('on');}drawMap();};mf.appendChild(b);});
let mapDrawn=false;
function drawMap(){
  let pts=D.movement.filter(m=>m.alt===+mapState.alt && mapState.fams.has(m.pitch_family) && (mapState.hand==='all'||m.PitcherThrows===mapState.hand));
  const key=mapState.color; if(key==='delta_cf') pts=pts.filter(m=>m.delta_cf!==null && m.delta_cf!==undefined);
  const isDelta=key==='delta_cf'; const alt=+mapState.alt;
  const colorOf = m => isDelta? m.delta_cf : key==='stuff_plus'? adjS(m.stuff_plus,alt) : adjP(m.pitching_plus,alt);
  const vals=pts.map(colorOf); const envMean = isDelta? davg : 100;
  const span=isDelta?6:14; const cmin=envMean-span, cmax=envMean+span;
  const scale=[[0,css('--sea')],[0.5,css('--rule')],[1,css('--home')]];
  const tr=[{x:pts.map(m=>m.hb),y:pts.map(m=>m.ivb),mode:'markers',type:'scatter',marker:{size:pts.map(m=>Math.max(6,Math.min(18,Math.sqrt(m.n)/1.6))),color:vals,colorscale:scale,cmin:cmin,cmax:cmax,showscale:true,colorbar:{title:{text:isDelta?'Δ Stuff+ en casa':(key==='stuff_plus'?'Stuff+ ajustado':'Pitching+ ajustado'),font:{color:css('--ink-2')}},tickfont:{color:css('--ink-2')},thickness:10,len:0.5,outlinewidth:0},line:{width:1,color:css('--paper')},opacity:.92},
    customdata:pts.map(m=>[m.pitcher_anon_id,FE[m.pitch_family],m.n,m.velo,m.spin,m.stuff_plus,m.pitching_plus,m.delta_cf==null?'—':fmt1(m.delta_cf),(100*m.whiff_rate).toFixed(0),(100*(m.gb_rate||0)).toFixed(0),(100*(m.hard_rate||0)).toFixed(0), adjS(m.stuff_plus,+mapState.alt).toFixed(0)]),
    hovertemplate:'<b>%{customdata[0]}</b> · %{customdata[1]} (%{customdata[2]} pitches)<br>%{customdata[3]:.1f} mph · %{customdata[4]:.0f} rpm · IVB %{y:.1f}" · HB %{x:.1f}"<br>Stuff+ %{customdata[5]:.1f} (ajustado %{customdata[11]}) · Pitching+ %{customdata[6]:.1f} · Δ en casa %{customdata[7]}<br>Whiff %{customdata[8]}% · rolling %{customdata[9]}% · duro %{customdata[10]}%<extra></extra>'}];
  const L=plotBase(); L.xaxis.title.text='Movimiento horizontal, hacia el lado del brazo (in)'; L.yaxis.title.text='Movimiento vertical inducido, IVB (in)'; L.height=560; L.xaxis.range=[-25,25]; L.yaxis.range=[-25,25]; L.margin.t=10; L.margin.r=10;
  L.annotations=[{x:17,y:22,text:'ride y run',showarrow:false,font:{color:css('--muted'),size:12}},{x:-16,y:-17,text:'ruptura hacia el guante',showarrow:false,font:{color:css('--muted'),size:12}},{x:17,y:-10,text:'caída hacia el brazo',showarrow:false,font:{color:css('--muted'),size:12}}];
  Plotly.react('map-plot',tr,L,{displayModeBar:false,responsive:true}); mapDrawn=true;
  const sorted=[...pts].filter(m=>m.n>=40).sort((a,b)=>colorOf(b)-colorOf(a));
  const row=m=>`<tr><td><span class="id">${m.pitcher_anon_id}</span><br><span class="meta">${FE[m.pitch_family]} · ${m.PitcherThrows==='Right'?'derecho':'zurdo'} · ${m.n} pitches</span></td><td>${m.velo.toFixed(1)}</td><td>${m.ivb.toFixed(1)}</td><td>${m.hb.toFixed(1)}</td><td><b>${m[key]==null?'—':(isDelta?fmt1(m[key]):(key==='stuff_plus'?adjS(m[key],+mapState.alt):adjP(m[key],+mapState.alt)).toFixed(0))}</b></td></tr>`;
  const hdr=`<tr><th>Pitcher y pitch</th><th>mph</th><th>IVB</th><th>HB</th><th>${isDelta?'Δ':key==='stuff_plus'?'Stuff+ aj.':'Pitching+ aj.'}</th></tr>`;
  document.getElementById('map-tables').innerHTML=`<div class="tbl-t">${isDelta?'Los que menos pierden en casa':'Los mejores de este ambiente'}</div><table>${hdr}${sorted.slice(0,8).map(row).join('')}</table><div class="tbl-t" style="margin-top:22px">${isDelta?'Los que más pierden en casa':'Los que más sufren'}</div><table>${hdr}${sorted.slice(-8).reverse().map(row).join('')}</table>`;
}
new IntersectionObserver(es=>{ if(es[0].isIntersecting && !mapDrawn) drawMap(); },{rootMargin:'200px'}).observe(document.getElementById('map-plot'));

/* ---------- perfilador ---------- */
const prof={rhp:1,measured:0,pitches:[]};
seg('p-hand',v=>{prof.rhp=+v;}); seg('p-measured',v=>{prof.measured=+v;});
function addPitch(fam, usage){ const p=D.presets[fam]; prof.pitches.push({fam:fam,usage:usage,velo:p.RelSpeed,spin:p.SpinRate,axis:p.SpinAxis,ivb:p.InducedVertBreak,hb:p.hb_arm}); renderPitches(); }
function renderPitches(){ const c=document.getElementById('p-pitches'); c.innerHTML='';
  prof.pitches.forEach((p,i)=>{ const d=document.createElement('div'); d.className='pitch';
    d.innerHTML=`<div class="r1"><div><label>Pitch ${i+1}</label><select data-i="${i}" data-k="fam">${D.FAMILY_ORDER.map(f=>`<option value="${f}" ${f===p.fam?'selected':''}>${FE[f]}</option>`).join('')}</select></div><div><label>Uso %</label><input type="number" data-i="${i}" data-k="usage" value="${p.usage}" step="5" min="0" max="100"></div><div><button class="btn ghost" data-del="${i}" title="Quitar este pitch" aria-label="Quitar este pitch" style="padding:8px 0;width:100%">×</button></div></div>
      <div class="r2"><div><label>mph</label><input type="number" data-i="${i}" data-k="velo" value="${p.velo}" step="0.1"></div><div><label>rpm</label><input type="number" data-i="${i}" data-k="spin" value="${p.spin}" step="10"></div><div><label>IVB (in)</label><input type="number" data-i="${i}" data-k="ivb" value="${p.ivb}" step="0.1"></div><div><label>HB (in)</label><input type="number" data-i="${i}" data-k="hb" value="${p.hb}" step="0.1"></div></div>`;
    c.appendChild(d); });
  c.querySelectorAll('select,input').forEach(el=>el.onchange=()=>{ const i=+el.dataset.i,k=el.dataset.k; if(k==='fam'){ const pr=D.presets[el.value]; prof.pitches[i]={fam:el.value,usage:prof.pitches[i].usage,velo:pr.RelSpeed,spin:pr.SpinRate,axis:pr.SpinAxis,ivb:pr.InducedVertBreak,hb:pr.hb_arm}; renderPitches(); } else prof.pitches[i][k]=+el.value; });
  c.querySelectorAll('button[data-del]').forEach(b=>b.onclick=()=>{prof.pitches.splice(+b.dataset.del,1);renderPitches();});
}
document.getElementById('p-add').onclick=()=>{ if(prof.pitches.length<5) addPitch('Changeup',15); };
addPitch('Fastball-Ride',55); addPitch('Slider-Gyro',30); addPitch('Changeup',15);
document.getElementById('p-run').onclick=runProfile;
function runProfile(){
  const relh=+document.getElementById('p-relh').value, rels=+document.getElementById('p-rels').value, ext=+document.getElementById('p-ext').value;
  const tot=prof.pitches.reduce((s,p)=>s+p.usage,0)||1;
  const rows=prof.pitches.map(p=>{ const r=evaluate(Object.assign({},p,{relh,rels,ext,rhp:prof.rhp}),p.fam,prof.measured); return Object.assign({w:p.usage/tot},p,{r}); });
  const wsea=rows.reduce((s,x)=>s+x.w*x.r.sea.sp,0), wcd=rows.reduce((s,x)=>s+x.w*x.r.cdmx.sp,0);
  const gb=rows.reduce((s,x)=>s+x.w*x.r.cdmx.gb,0), hard=rows.reduce((s,x)=>s+x.w*x.r.cdmx.hard,0), hr=rows.reduce((s,x)=>s+x.w*x.r.cdmx.hr,0);
  const comps=D.comparables.map(c=>c.stuff).sort((a,b)=>a-b); const pct=Math.round(100*comps.filter(v=>v<wcd).length/comps.length);
  const line = pct>=80?'Perfil hecho para el Harp Helú.':pct>=60?'Buen encaje para casa.':pct>=40?'Encaje promedio: depende de cuál sea su rol.':'Encaje débil: en casa pierde más de lo que aporta.';
  document.getElementById('p-verdict').innerHTML=`<div class="verdict-line">${line}</div><p class="note">Mejor que el ${pct}% de los ${comps.length} pitcher-temporadas reales que han lanzado en altitud extrema.</p>`;
  document.getElementById('p-fit').innerHTML=`<div><div class="k">Stuff+ del arsenal a nivel del mar</div><div class="v sea">${wsea.toFixed(0)}</div></div><div><div class="k">En el Harp Helú, misma escala</div><div class="v home">${wcd.toFixed(0)}</div></div><div><div class="k">Ajustado al ambiente de casa</div><div class="v">${adjS(wcd,2).toFixed(0)}</div></div>`;
  const flags=[];
  const fb=rows.filter(x=>x.fam.startsWith('Fastball')); const fbUse=fb.reduce((s,x)=>s+x.w,0); const fbIvb=fb.length?fb.reduce((s,x)=>s+x.w*x.ivb,0)/Math.max(fbUse,1e-6):0; const fbVelo=fb.length?fb.reduce((s,x)=>s+x.w*x.velo,0)/Math.max(fbUse,1e-6):0;
  if(fb.length && fbIvb>=16 && fbVelo<92) flags.push(`<div class="flag risk"><b>Su recta vive del ride y no de la velocidad</b>IVB ${fbIvb.toFixed(1)}" a ${fbVelo.toFixed(1)} mph. En casa pierde ~4" y el modelo castiga más la pérdida de IVB de lo que premia el spin. Compensa con velocidad (93+) o con un sinker o cambio que genere rolling.</div>`);
  if(fb.length && fbVelo>=93.5) flags.push(`<div class="flag good"><b>La velocidad viaja bien</b>${fbVelo.toFixed(1)} mph. El aire no toca la velocidad y la bola llega ~1.3 mph más rápida al plato en altitud.</div>`);
  const gbFam=rows.filter(x=>['Sinker','Changeup','Fastball-Run'].includes(x.fam)).reduce((s,x)=>s+x.w,0);
  if(gbFam>=0.35) flags.push(`<div class="flag good"><b>Perfil de rolling</b>${(100*gbFam).toFixed(0)}% del repertorio son pitches con caída hacia el brazo. En casa un elevado cuesta 0.14 carreras contra 0.03 en la costa: convertir elevados en rollings vale 2.5 veces más.</div>`);
  const curve=rows.filter(x=>['Curveball','Slurve','Sweeper'].includes(x.fam)).reduce((s,x)=>s+x.w,0);
  if(curve>=0.25) flags.push(`<div class="flag risk"><b>Depende de rupturas de mucho movimiento</b>${(100*curve).toFixed(0)}% de uso. Son las que más forma pierden en altitud (25–30% menos). Sirven para robar strikes; como pitch de out, exigir que sigan siendo buenas con un cuarto menos de movimiento.</div>`);
  const gyro=rows.filter(x=>['Slider-Gyro','Cutter','Fastball-Cut'].includes(x.fam)).reduce((s,x)=>s+x.w,0);
  if(gyro>=0.25) flags.push(`<div class="flag good"><b>Tiene un pitch que el aire no se lleva</b>${(100*gyro).toFixed(0)}% de slider gyro, cutter o recta con cut: las formas que menos pierden en casa porque no dependen del efecto Magnus.</div>`);
  if(hr>0.06) flags.push(`<div class="flag risk"><b>Riesgo de jonrón alto</b>Probabilidad de HR cuando hay contacto: ${(100*hr).toFixed(1)}% en casa (liga en CDMX ≈ 4.3%).</div>`);
  document.getElementById('p-flags').innerHTML=flags.join('');
  document.getElementById('p-table').innerHTML=`<table><tr><th>Pitch</th><th>Uso</th><th>Stuff+ mar</th><th>Stuff+ casa</th><th>Δ</th><th>Whiff</th><th>Rolling</th><th>Duro</th></tr>${rows.map(x=>`<tr><td><span class="id">${FE[x.fam]}</span><br><span class="meta">${x.velo} mph · IVB ${x.r.sea.p.ivb.toFixed(1)}→${x.r.cdmx.p.ivb.toFixed(1)} · HB ${x.r.sea.p.hb.toFixed(1)}→${x.r.cdmx.p.hb.toFixed(1)}</span></td><td>${(100*x.w).toFixed(0)}%</td><td class="sea-t">${x.r.sea.sp.toFixed(0)}</td><td class="home-t">${x.r.cdmx.sp.toFixed(0)}</td><td>${fmt1(x.r.cdmx.sp-x.r.sea.sp)}</td><td>${(100*x.r.cdmx.whiff).toFixed(0)}%</td><td>${(100*x.r.cdmx.gb).toFixed(0)}%</td><td>${(100*x.r.cdmx.hard).toFixed(0)}%</td></tr>`).join('')}</table>`;
  const hand=prof.rhp?'Right':'Left';
  const scored=D.comparables.filter(c=>c.hand===hand).map(c=>{ let d=0, wsum=0; rows.forEach(x=>{ const m=c.pitches.filter(q=>q.fam===x.fam).sort((a,b)=>b.n-a.n)[0]; if(!m){d+=x.w*3;wsum+=x.w;return;} const pc=x.r.cdmx.p; d+=x.w*Math.sqrt(((m.velo-x.velo)/2.5)**2+((m.ivb-pc.ivb)/3)**2+((m.hb-pc.hb)/3)**2); wsum+=x.w; }); return Object.assign({d:d/wsum},c); }).sort((a,b)=>a.d-b.d).slice(0,5);
  document.getElementById('p-comps').innerHTML=`<table><tr><th>Pitcher</th><th>Arsenal en casa</th><th>Stuff+ aj.</th><th>Pitching+ aj.</th><th>xRV/100</th><th>Rolling</th><th>HR/BIP</th><th>Whiff</th></tr>${scored.map(c=>`<tr><td><span class="id">${c.id}</span><br><span class="meta">${c.year} · ${c.n} pitches</span></td><td style="text-align:left;font-size:13px;white-space:nowrap">${c.pitches.map(q=>`${FE[q.fam]} ${(100*q.usage).toFixed(0)}% (${q.velo} mph)`).join('<br>')}</td><td>${adjS(c.stuff,2).toFixed(0)}</td><td>${adjP(c.pitching,2).toFixed(0)}</td><td class="${c.xrv100>0?'sea-t':'home-t'}">${c.xrv100>=0?'+':''}${c.xrv100}</td><td>${(100*c.gb).toFixed(0)}%</td><td>${(100*c.hr_bip).toFixed(1)}%</td><td>${(100*c.whiff).toFixed(0)}%</td></tr>`).join('')}</table>`;
}
runProfile();
</script>
</body>
</html>
"""
LGB_JS = r"""
function lgbPredict(model, x){ const feats = model.features; let s = 0;
  for (const tr of model.trees){ const [F,T,L,R,V,D] = tr; let i = 0;
    while (F[i] !== -1){ const v = x[feats[F[i]]]; if (v === undefined || v === null || Number.isNaN(v)) i = D[i] ? L[i] : R[i]; else i = (v <= T[i]) ? L[i] : R[i]; }
    s += V[i]; }
  if (model.objective.startsWith('binary')) return 1/(1+Math.exp(-s)); return s; }
"""
html = HTML.replace('__N_PITCHES__', f'{story["n_pitches"]:,}').replace('__N_PITCHERS__', f'{story["n_pitchers"]:,}').replace('__MEAN_DELTA__', f'{abs(story["mean_delta"]):.0f}').replace('__BREAK_PCT__', str(story['break_pct'])).replace('__FB_DIST__', str(story['fb_dist'])).replace('__WHIFF_SEA__', f'{100*story["whiff_sea"]:.0f}').replace('__WHIFF_EXT__', f'{100*story["whiff_ext"]:.0f}')
data_json = json.dumps(DATA, separators=(',', ':')).replace('</', '<\\/')
plotly_path = os.path.join(os.path.dirname(plotly.__file__), 'package_data', 'plotly.min.js')
offline = html.replace('__PLOTLY__', '<script>' + open(plotly_path).read() + '</script>').replace('__DATA__', data_json).replace('__LGB__', LGB_JS)
open(f'{DEL}/dashboard_stuff_plus_lmb.html', 'w').write(offline)
cdn = html.replace('__PLOTLY__', '<script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.35.2/plotly.min.js"></script>').replace('__DATA__', data_json).replace('__LGB__', LGB_JS)
open(f'{OUT}/dashboard_cdn.html', 'w').write(cdn)
print('offline MB', round(os.path.getsize(f'{DEL}/dashboard_stuff_plus_lmb.html') / 1e6, 2), '| cdn MB', round(os.path.getsize(f'{OUT}/dashboard_cdn.html') / 1e6, 2))
