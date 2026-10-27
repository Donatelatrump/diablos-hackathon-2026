"""Verifica coherencia de la entrega sin datos crudos ni entrenamiento.

Ejecutar desde cualquier directorio con python scripts/14_delivery_check.py.
"""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'app/public/data'; A=ROOT/'artifacts'
def read(p):
    return json.loads(p.read_text(),parse_constant=lambda value:(_ for _ in ()).throw(ValueError('JSON no finito: '+value)))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
checks=[]
def passed(name,detail): checks.append({'check':name,'passed':True,'detail':detail})
for p in D.glob('*.json'): read(p)
passed('json_finito',len(list(D.glob('*.json'))))
for name in ['causal','jurado','extras','hipotesis','robustez','scale','models','validation_audit']:
    assert read(D/f'{name}.json')==read(A/f'{name}.json'),name
passed('copias_canonicas',8)
phys=read(A/'physics.json'); exported=read(D/'physics.json')
assert all(exported[k]==v for k,v in phys.items())
passed('fisica_exportada','Todos los parámetros canónicos se conservan')
for p in D.glob('*.json'):
    assert sha(p)==sha(ROOT/'app/dist/data'/p.name),p.name
passed('build_con_datos_finales',13)
audit=read(D/'validation_audit.json')
for name,expected in audit['provenance']['unchanged_fitted_files_sha256'].items():
    assert sha(ROOT/name)==expected,name
passed('modelo_escala_oof_sin_cambios',len(audit['provenance']['unchanged_fitted_files_sha256']))
j=read(D/'jurado.json'); scale=read(D/'scale.json')['stuff']['scale']; cpp=scale*10
hold=sum(x['delta_hh']>-.5/cpp for x in j['pitchers']); lose=sum(x['delta_hh']<-1/cpp for x in j['pitchers'])
assert len(j['pitchers'])==561 and hold==7 and lose==422
passed('seleccion_lanzadores',{'total':561,'aguantan':hold,'pierden_mas_de_una_carrera':lose})
es={'Four-Seam':'Recta','Sinker':'Sinker','Cutter':'Cutter','Slider':'Slider','Curveball':'Curva','Changeup':'Cambio','Splitter':'Splitter'}
types={x['tipo']:x for x in j['tipos']}; ars=read(D/'arsenal.json')
for t in ars['tipos']:
    assert abs(t['delta_plus']-types[es[t['tipo']]]['delta'])<.011
    assert abs((t['alt']['plus']-t['mar']['plus'])-t['delta_plus'])<.106  # Los dos niveles se redondean a 0.1 y el delta a 0.01
passed('arsenal_vs_tabla_general','Siete tipos, misma población y transferencia')
for t in read(D/'extras.json')['tres_entornos']['por_tipo']:
    assert abs((t['extrema']-t['mar'])-types[t['tipo']]['delta'])<.02
passed('tres_entornos_vs_tabla_general','Mismas medias por tipo')
for name in ['documento_tecnico','reporte']:
    html=(ROOT/'entrega'/f'{name}.html').read_text()
    assert not re.search(r'\{\{\w+\}\}',html),'Cifra sin resolver'
    assert (ROOT/'entrega'/f'{name}.pdf').stat().st_size>100_000
passed('documentos_generados','Sin tokens de cifras pendientes y PDF presentes')
standalone=(ROOT/'entrega/dashboard.html').read_text()
embedded=read_json=None
m=re.search(r'<script id="dashboard-data" type="application/json">(.*?)</script>',standalone,re.S)
assert m
embedded=json.loads(m.group(1))
assert set(embedded)=={p.name for p in D.glob('*.json')}
assert all(embedded[p.name]==read(p) for p in D.glob('*.json'))
passed('html_autonomo_estructura','13 JSON idénticos al build; ejecución file no verificada por política del navegador')
meta={'status':'passed_with_documented_limits','checks':checks,'browser_qa':{
 'home':'−9.3, 7 de 561, +1.56 observacional',
 'validation':'Auditoría visible, RMSE 0.267997 vs 0.268111',
 'simulator':'A nivel del mar ambos scores99.9 y cambio0.0; render 3D visible',
 'section_smoke':['Inicio','Metodología','Validación','Lanzadores','Arsenal y perfil','Hipótesis','Causal Forest','Simulador','Anexo'],
 'invalid_number_or_console_error_observed':False,
 'coverage_limits':'Inspección de escritorio y controles representativos; no todas las combinaciones, no responsive móvil, no ejecución directa file del HTML autónomo.'},
 'publication':{'existing_url':'https://claude.ai/artifact/1HXhuyBtkDd6szvLv9M7xo','updated':False,'reason':'Usuario solicitó preparar archivos para el enlace existente. No hay carga directa en los controles de propietario y la sesión Claude está al límite.'}}
out=ROOT/'delivery_checks/final_checks.json'; out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(meta,indent=2,ensure_ascii=False))
print(json.dumps({'status':meta['status'],'checks':len(checks),'models_unchanged':True,'pitchers':561,'survive':hold},ensure_ascii=False))
