"""Cifras del texto técnico, calculadas desde los JSON que alimentan el dashboard."""
import json
from pathlib import Path


def renderizar(texto: str, raiz: Path) -> str:
    d = raiz / 'app/public/data'
    leer = lambda n: json.loads((d / f'{n}.json').read_text())
    j, co, h, ex, sc, cf = (leer(n) for n in ('jurado', 'compresion', 'hipotesis', 'extras', 'scale', 'causal'))
    cpp = sc['stuff']['scale'] * 10
    p = j['pitchers']; sd = sorted(x['sd_juego'] for x in p)[len(p)//2]
    fichaje = next((x for x in sorted(p,key=lambda x:-x['stuff_hh']) if x['delta_hh'] > -.5/cpp and x['sd_juego'] <= sd), max(p,key=lambda x:x['stuff_hh']))
    peor = min(p,key=lambda x:x['delta_hh']); q = co['quintiles']['Four-Seam']
    tipos = {x['tipo']:x for x in h['h1']['por_tipo']}
    poblacion = {x['tipo']:x for x in j['tipos']}
    exp = h['h4']['experimento']; giro = exp['giro']; curva = [x['mar'] for x in giro]
    f = lambda v,n=1:f'{abs(v):,.{n}f}'
    vals = dict(pitchers_n=str(j['pitchers_n']),aguantan=str(sum(x['delta_hh']>-.5/cpp for x in p)),mucho=str(sum(x['delta_hh']<-1/cpp for x in p)),
                corte_aguanta=f(.5/cpp),corte_mucho=f(1/cpp),recta_delta=f(poblacion['Recta']['delta']),cutter_delta=f(poblacion['Cutter']['delta']),recta_rv=f(tipos['Recta']['delta']*cpp),
                cambio_ventaja=f(h['h2']['cambio']['ventaja_vs_recta']),cambio_rango=str(next(i+1 for i,x in enumerate(h['h2']['pares']) if x['tipo']=='Cambio')),
                giro_peso=f(next(x['peso'] for x in h['h4']['importancia'] if x['grupo'].startswith('Giro (rpm)'))*100),
                giro_min=f(min(curva)),giro_max=f(max(curva)),giro_local=f(sum(abs(b-a) for a,b in zip(curva,curva[1:]))/(len(curva)-1),2),
                pareja_mar=f(exp['parejas']['B']['mar']-exp['parejas']['A']['mar']),pareja_hh=f(exp['parejas']['B']['hh']-exp['parejas']['A']['hh']),
                cf_ate=f(cf['ate'],2),cf_lo=f(cf['ate_ic90'][0],2),cf_hi=f(cf['ate_ic90'][1],2))
    for k in ('q1','q5'):
        for suf,key in (('mar','plus_mar'),('alt','plus_alt'),('delta','delta')): vals[f'{k}_{suf}']=f(q[k][key])
    for nom,x in (('peor',peor),('fichaje',fichaje)):
        vals.update({f'{nom}_nombre':x['nombre'],f'{nom}_mar':f(x['stuff_mar']),f'{nom}_hh':f(x['stuff_hh']),f'{nom}_arsenal':x['arsenal'],f'{nom}_sd':f(x['sd_juego'])})
    te = ex['tres_entornos']; filas=[('| | Nivel del mar | Altitud media | Altitud extrema |'),('|---|---|---|---|')]
    for nom,x,n in [('Índice de aire',te['indice_aire'],3),('Stuff+ de la liga',te['liga'],1)]+[(x['tipo'],x,1) for x in te['por_tipo'] if x['tipo'] in ('Recta','Cutter')]:
        keys=('mar','media','extrema');filas.append('| '+nom+' | '+' | '.join(f'{x[k]:.{n}f}' for k in keys)+' |')
    vals['tabla_entornos']='\n'.join(filas)
    filas=['| Variable | Élite a nivel del mar | Élite en altura | Mediana de la liga |','|---|---|---|---|']
    for key,nom,n in [('RelSpeed','Velocidad (mph)',1),('InducedVertBreak','Elevación (in)',1),('HorzBreak','Movimiento lateral (in)',1),('movement_total','Movimiento total (in)',1),('spin_efficiency','Eficiencia de giro',2),('SpinRate','Giro (rpm)',0)]:
        x=co['perfil_ideal'][key];filas.append('| '+nom+' | '+' | '.join(f'{x[k]:,.{n}f}'.replace('-','−') for k in ('optimo_nivel_mar','optimo_altitud','liga_mediana'))+' |')
    vals['tabla_perfil']='\n'.join(filas)
    audit_path = d / 'validation_audit.json'
    if audit_path.exists():
        au = json.loads(audit_path.read_text()); current = au['grouped']['current']; base = au['grouped']['count_baseline']
        vals['auditoria'] = (f"Como comprobación separada, reajustamos la especificación actual en cuatro pliegues de lanzador con tablas del objetivo y baseline aprendidas sólo en entrenamiento. RMSE de {current['rmse']:.5f} frente a {base['rmse']:.5f} del baseline, y R² de {current['r2']:.5f}. La reducción de MSE frente al baseline es {current['skill_vs_training_count_baseline'] * 100:.3f} %. Esta prueba evalúa nuevos ajustes de la especificación, no el booster exacto servido. La preparación física permanece global. Los cortes 2025 y 2026 son retrospectivos.")
    else:
        vals['auditoria'] = 'La evaluación aislada conserva resultados y protocolos en evaluations/codex_review_2026_10_22.'
    import re
    return re.sub(r'\{\{(\w+)\}\}',lambda m:vals[m.group(1)],texto)
