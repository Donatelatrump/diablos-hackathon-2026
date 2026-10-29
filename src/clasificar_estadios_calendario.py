"""Recupera fechas UUID y contrasta juegos con fuentes públicas; conserva el origen."""
import argparse
import datetime as dt
import json
from pathlib import Path
import uuid
import numpy as np
import subprocess

import pandas as pd
import pyarrow.parquet as pq

OUT = Path('clasificacion_estadios')

def get_json(url, path):
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    result=subprocess.run(['curl.exe','-L','-s','--fail','--max-time','30',url],capture_output=True,check=True)
    data=json.loads(result.stdout)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    return data

def timestamp(value):
    try:
        u = uuid.UUID(value)
        if u.version == 1:
            return pd.Timestamp((u.time - 122192928000000000) * 100, unit='ns', tz='UTC')
    except (ValueError, TypeError, OverflowError):
        pass
    return pd.NaT

def prepare():
    OUT.mkdir(exist_ok=True)
    cols = ['year', 'PitchUID', 'game_anon_id', 'altitude_category', 'Inning', 'Top/Bottom', 'Outs', 'RunsScored', 'pitcher_anon_id']
    df = pq.read_table('stuff_model_df.parquet', columns=cols).to_pandas()
    df['fecha_uuid_utc'] = pd.to_datetime(df.PitchUID.map(timestamp), utc=True)
    df.to_parquet(OUT/'fechas_lanzamientos.parquet', index=False)
    rows=[]
    for (year, game), sub in df.groupby(['year', 'game_anon_id'], observed=True):
        times = sub.fecha_uuid_utc.dropna().sort_values()
        rows.append(dict(year=int(year), game_anon_id=game, n_pitches=len(sub), n_uuid_dates=len(times),
                         first_utc=times.iloc[0], last_utc=times.iloc[-1],
                         altitude_category=next(iter(sub.altitude_category.dropna()), None),
                         max_inning=float(sub.Inning.max()),
                         runs=float(sub.RunsScored.sum())))
    games=pd.DataFrame(rows)
    games.to_parquet(OUT/'juegos_fechas.parquet', index=False)
    print(games.groupby('year').agg(games=('game_anon_id','size'),first=('first_utc','min'),last=('last_utc','max')).to_string())

def schedules():
    rows=[]
    for year in [2024, 2025, 2026]:
        url=f'https://statsapi.mlb.com/api/v1/schedule?sportId=23&startDate={year}-03-01&endDate={year}-11-30&hydrate=venue(location),linescore,gameInfo'
        data=get_json(url, OUT/'fuentes'/f'calendario_{year}.json')
        for day in data.get('dates',[]):
            for g in day.get('games',[]):
                teams=g.get('teams',{}); info=g.get('gameInfo',{}); venue=g.get('venue',{})
                rows.append(dict(year=year, gamePk=g['gamePk'], officialDate=g.get('officialDate',day['date']),
                                 scheduled_utc=g.get('gameDate'), firstPitch=info.get('firstPitch'),
                                 duration_minutes=info.get('gameDurationMinutes'),venue_id=venue.get('id'),
                                 stadium=venue.get('name'),city=venue.get('location',{}).get('city'),
                                 home=teams.get('home',{}).get('team',{}).get('name'),
                                 away=teams.get('away',{}).get('team',{}).get('name'),
                                 home_runs=teams.get('home',{}).get('score'),away_runs=teams.get('away',{}).get('score'),
                                 status=g.get('status',{}).get('detailedState'),gameNumber=g.get('gameNumber'),
                                 source_url=f'https://statsapi.mlb.com/api/v1.1/game/{g["gamePk"]}/feed/live'))
    cal=pd.DataFrame(rows).drop_duplicates('gamePk')
    cal.to_csv(OUT/'calendario_lmb_2024_2026.csv',index=False,encoding='utf-8-sig')
    print(cal.groupby('year').size().to_string())
    print(cal.head(2).to_string(index=False))

def match_games():
    """Coteja huella de carreras por media entrada, hora y duración; no usa altitud."""
    games=pd.read_parquet(OUT/'juegos_fechas.parquet')
    raw=pd.read_parquet(OUT/'fechas_lanzamientos.parquet')
    halves=raw.groupby(['game_anon_id','Inning','Top/Bottom'],observed=True).RunsScored.sum()
    signatures={}
    for (game, inning, side), runs in halves.items():
        signatures.setdefault(game,{})[(int(inning),side)]=float(runs)
    public=[]
    for year in [2024,2025,2026]:
        data=json.loads((OUT/'fuentes'/f'calendario_{year}.json').read_text(encoding='utf-8'))
        for day in data['dates']:
            for game in day['games']:
                sig={}
                for inning in game.get('linescore',{}).get('innings',[]):
                    for side,key in [('Top','away'),('Bottom','home')]:
                        if 'runs' in inning.get(key,{}):
                            sig[(inning['num'],side)]=float(inning[key]['runs'])
                start=game.get('gameInfo',{}).get('firstPitch') or game.get('gameDate')
                public.append((game,pd.Timestamp(start),sig))
    candidates=[]; classifications=[]
    for row in games.itertuples():
        signature=signatures[row.game_anon_id]
        eligible=[]
        for game,start,sig in public:
            delta=(row.first_utc-start).total_seconds()/60
            if abs(delta)>12*60:
                continue
            overlap=signature.keys() & sig.keys()
            if not overlap:
                continue
            err=sum(abs(signature[k]-sig[k]) for k in overlap)
            missing=len(signature.keys()-sig.keys())
            hours=round(delta/60)
            residual=abs(delta-hours*60)
            duration=game.get('gameInfo',{}).get('gameDurationMinutes')
            duration_error=abs((row.last_utc-row.first_utc).total_seconds()/60-duration) if duration is not None else 999.
            rank=err*30+missing*50+min(residual,15)*2+min(duration_error,120)/4
            e=dict(year=row.year,game_anon_id=row.game_anon_id,gamePk=game['gamePk'],
                   stadium=game.get('venue',{}).get('name'),venue_id=game.get('venue',{}).get('id'),
                   home=game['teams']['home']['team']['name'],away=game['teams']['away']['team']['name'],
                   officialDate=game.get('officialDate'),public_start_utc=start.isoformat(),
                   score_error=err,missing_halves=missing,compared_halves=len(overlap),
                   nonzero_halves=sum(signature[k]>0 for k in overlap),hour_offset=hours,
                   time_residual_minutes=residual,duration_error_minutes=duration_error,rank=rank,
                   source_url=f'https://statsapi.mlb.com/api/v1.1/game/{game["gamePk"]}/feed/live')
            eligible.append(e)
        eligible.sort(key=lambda x:x['rank'])
        unique={}
        for item in eligible:
            unique.setdefault(item['gamePk'],item)
        eligible=list(unique.values())
        for i,e in enumerate(eligible[:3]): candidates.append({**e,'candidate_rank':i+1})
        if not eligible:
            classifications.append(dict(year=row.year,game_anon_id=row.game_anon_id,status='sin_calendario_cercano'))
            continue
        best=eligible[0]; margin=eligible[1]['rank']-best['rank'] if len(eligible)>1 else 999.
        exact=(best['score_error']==0 and best['missing_halves']==0 and best['compared_halves']>=10 and best['nonzero_halves']>=2)
        temporal=best['time_residual_minutes']<=3 and best['duration_error_minutes']<=5 and abs(best['hour_offset'])<=3
        # A unique complete scoring fingerprint with temporal consistency supports a reproducible link.
        accepted=exact and temporal and margin>=15
        status='coincidencia_alta' if accepted else 'por_revisar'
        classifications.append({**best,'status':status,'margin':margin,'exact_signature':exact,'temporal_match':temporal})
    out=pd.DataFrame(classifications)
    dup=out.loc[out.status.eq('coincidencia_alta'),'gamePk'].duplicated(keep=False)
    duplicate_ids=out.loc[out.status.eq('coincidencia_alta')].loc[dup,'gamePk']
    out.loc[out.gamePk.isin(duplicate_ids),'status']='conflicto_multiples_juegos'
    out.to_csv(OUT/'cruce_juegos_preliminar.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(candidates).to_csv(OUT/'candidatos_calendario.csv',index=False,encoding='utf-8-sig')
    print(out.status.value_counts().to_string())
    print(out.groupby('status')[['score_error','time_residual_minutes','duration_error_minutes']].median().to_string())
    print(out.loc[~out.status.eq('coincidencia_alta')].head(15).to_string(index=False))

FEED_FIELDS='gamePk,gameData,venue,id,name,liveData,plays,allPlays,about,inning,halfInning,startTime,endTime,playEvents,isPitch'

def feeds():
    candidates=pd.read_csv(OUT/'candidatos_calendario.csv').sort_values('rank').drop_duplicates(['game_anon_id','gamePk'])
    # Initially verify each best candidate; alternatives remain visible in the audit.
    selected=candidates.loc[candidates.candidate_rank.eq(1)]
    ids=sorted(selected.gamePk.astype(int).unique())
    target_dir=OUT/'fuentes'/'jugadas'
    target_dir.mkdir(parents=True,exist_ok=True)
    pending=[]
    for pk in ids:
        p=target_dir/f'{pk}.json'
        try:
            data=json.loads(p.read_text(encoding='utf-8'))
            if data.get('gamePk')!=pk: pending.append(pk)
        except (OSError,json.JSONDecodeError): pending.append(pk)
    config=OUT/'descarga_jugadas.curl'
    lines=[]
    for pk in pending:
        url=f'https://statsapi.mlb.com/api/v1.1/game/{pk}/feed/live?fields={FEED_FIELDS}'
        path=(target_dir/f'{pk}.json').resolve().as_posix()
        lines.extend([f'url = "{url}"',f'output = "{path}"'])
    config.write_text('\n'.join(lines),encoding='utf-8')
    if pending:
        print(f'Descargando {len(pending)} registros públicos pendientes',flush=True)
        result=subprocess.run(['curl.exe','--parallel','--parallel-immediate','--parallel-max','32','-L','-s','--fail','--max-time','30','--retry','2','--config',str(config)],capture_output=True)
        if result.stderr: print(result.stderr.decode(errors='replace')[:1000],flush=True)
    failures=[{'gamePk':pk,'error':'archivo ausente'} for pk in ids if not (target_dir/f'{pk}.json').exists()]
    (OUT/'errores_descarga.json').write_text(json.dumps(failures,indent=2),encoding='utf-8')
    print('Descargas completadas',len(ids)-len(failures),'errores',len(failures),flush=True)

def validate_feeds():
    raw=pd.read_parquet(OUT/'fechas_lanzamientos.parquet')
    candidates=pd.read_csv(OUT/'candidatos_calendario.csv').sort_values('rank').drop_duplicates(['game_anon_id','gamePk'])
    raw_groups={}
    raw_counts=raw.groupby('game_anon_id',observed=True).fecha_uuid_utc.count().to_dict()
    for (game,inning,side),sub in raw.groupby(['game_anon_id','Inning','Top/Bottom'],observed=True):
        raw_groups.setdefault(game,{})[(int(inning),side)]=sub.fecha_uuid_utc.dropna().astype('int64').to_numpy()/1e9
    feed_cache={}
    def events(pk):
        if pk in feed_cache: return feed_cache[pk]
        p=OUT/'fuentes'/'jugadas'/f'{pk}.json'
        if not p.exists(): return None
        try:
            data=json.loads(p.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            return None
        grouped={}
        for play in data.get('liveData',{}).get('plays',{}).get('allPlays',[]):
            about=play.get('about',{}); inning=about.get('inning'); half=about.get('halfInning','').title()
            key=(inning,half)
            for event in play.get('playEvents',[]):
                if event.get('isPitch'):
                    for field in ['startTime','endTime']:
                        val=event.get(field)
                        if val: grouped.setdefault(key,[]).append(pd.Timestamp(val).value/1e9)
        grouped={k:np.unique(v) for k,v in grouped.items()}
        feed_cache[pk]=grouped
        return grouped
    records=[]
    for row in candidates.itertuples():
        ev=events(int(row.gamePk))
        if not ev: continue
        sub=raw_groups[row.game_anon_id]
        nvalid=int(raw_counts[row.game_anon_id])
        best=None
        for hour in [-2,-1,0,1,2]:
            distances=[]
            for key,observed_times in sub.items():
                target=ev.get(key)
                times=observed_times-hour*3600
                if target is None or not len(times): continue
                ix=np.searchsorted(target,times)
                right=target[np.minimum(ix,len(target)-1)]
                left=target[np.maximum(ix-1,0)]
                distances.extend(np.minimum(abs(times-left),abs(times-right)))
            ds=np.asarray(distances)
            if not len(ds): continue
            item=dict(game_anon_id=row.game_anon_id,gamePk=int(row.gamePk),
                      event_matches_15s=int((ds<=15).sum()),event_matches_30s=int((ds<=30).sum()),
                      event_coverage=len(ds)/nvalid,event_match_ratio_15s=float((ds<=15).sum()/nvalid),
                      event_match_ratio_30s=float((ds<=30).sum()/nvalid),
                      event_median_seconds=float(np.median(ds)),event_hour_correction=hour,
                      n_uuid_dates=nvalid)
            if best is None or (item['event_match_ratio_15s'],-item['event_median_seconds'])>(best['event_match_ratio_15s'],-best['event_median_seconds']): best=item
        if best: records.append(best)
    evidence=pd.DataFrame(records)
    evidence.to_csv(OUT/'validacion_horas_jugadas.csv',index=False,encoding='utf-8-sig')
    print(evidence[['event_match_ratio_15s','event_match_ratio_30s','event_median_seconds','event_coverage']].describe().to_string())
    print('>=.75 within15s',int(evidence.event_match_ratio_15s.ge(.75).sum()),'of',len(evidence))
    print(evidence.sort_values('event_match_ratio_15s').head(20).to_string(index=False))

VENUE_CATALOG={5340:'mexico_ahh',2869:'puebla_serdan',2929:'aguascalientes_romo',5321:'durango_villa',
               5320:'leon_santana',6070:'queretaro_conspiradores',2953:'saltillo_madero',4710:'jalisco_panamericano',
               3210:'chihuahua_monumental',2956:'torreon_revolucion',2950:'monclova_beisbol',2701:'monterrey_beisbol',
               5330:'laredo_unitrade',3410:'nuevo_laredo_junta',2957:'tijuana_mobil',2955:'tabasco_centenario',
               2958:'veracruz_avila',2959:'merida_kukulcan',3929:'cancun_avila',2949:'campeche_barrera',6081:'kanasin_cervera'}

def export():
    import hashlib
    import xlsxwriter
    from collections import Counter
    source=Path('stuff_model_df.parquet')
    source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    original=pd.read_parquet(source)
    dates=pd.read_parquet(OUT/'fechas_lanzamientos.parquet')
    preliminary=pd.read_csv(OUT/'cruce_juegos_preliminar.csv')
    candidates=pd.read_csv(OUT/'candidatos_calendario.csv').sort_values('rank').drop_duplicates(['game_anon_id','gamePk'])
    evidence=pd.read_csv(OUT/'validacion_horas_jugadas.csv').drop_duplicates(['game_anon_id','gamePk'])
    game_dates=pd.read_parquet(OUT/'juegos_fechas.parquet')
    catalog=pd.read_csv('entrega_v8/estadios_altitudes.csv').set_index('stadium_id')
    choices=[]
    for game,group in evidence.groupby('game_anon_id'):
        ordered=group.sort_values(['event_match_ratio_30s','event_median_seconds'],ascending=[False,True])
        best=ordered.iloc[0]
        rival=ordered.iloc[1].event_match_ratio_30s if len(ordered)>1 else 0.
        accepted=(best.event_match_ratio_30s>=.85 and best.event_median_seconds<=15 and
                  best.event_coverage>=.85 and best.event_matches_30s>=50 and
                  best.event_match_ratio_30s-rival>=.15)
        prior=preliminary.loc[preliminary.game_anon_id.eq(game)].iloc[0]
        corroborated=(prior.status=='coincidencia_alta' and prior.gamePk==best.gamePk and
                      best.event_match_ratio_30s>=.65 and best.event_median_seconds<=20 and
                      best.event_coverage>=.85 and best.event_matches_30s>=50 and
                      best.event_match_ratio_30s-rival>=.15)
        candidate=candidates.loc[candidates.game_anon_id.eq(game)&candidates.gamePk.eq(best.gamePk)].iloc[0]
        near_fingerprint=(candidate.score_error<=1 and candidate.missing_halves==0 and
                          candidate.compared_halves>=10 and candidate.nonzero_halves>=2 and
                          candidate.time_residual_minutes<=3 and candidate.duration_error_minutes<=5 and
                          abs(candidate.hour_offset)<=3 and prior.gamePk==best.gamePk and prior.margin>=15 and
                          best.event_match_ratio_30s>=.70 and best.event_median_seconds<=15 and
                          best.event_coverage>=.90 and best.event_matches_30s>=50 and
                          best.event_match_ratio_30s-rival>=.15)
        choices.append({**best.to_dict(),'accepted':accepted or corroborated or near_fingerprint,
                        'acceptance_method':'jugadas' if accepted else ('huella_y_jugadas' if corroborated else ('huella_parcial_y_jugadas' if near_fingerprint else 'pendiente')),
                        'rival_ratio_30s':rival})
    choice=pd.DataFrame(choices)
    selected=choice.merge(candidates.drop(columns=['year']),on=['game_anon_id','gamePk'],how='left',validate='one_to_one')
    joined=game_dates.merge(selected,on='game_anon_id',how='left',validate='one_to_one',suffixes=('','_candidate'))
    joined['estado_clasificacion']=np.where(joined.accepted.eq(True),'verificado_'+joined.acceptance_method.fillna(''), 'pendiente')
    accepted=joined.estado_clasificacion.str.startswith('verificado_')
    # Conflicting one-to-many matches are never silently accepted.
    repeated=joined.loc[accepted,'gamePk'].duplicated(keep=False)
    conflicts=set(joined.loc[accepted].loc[repeated,'gamePk'])
    joined.loc[joined.gamePk.isin(conflicts),'estado_clasificacion']='conflicto'
    accepted=joined.estado_clasificacion.str.startswith('verificado_')
    joined['estadio_candidato']=joined['stadium']
    joined['estadio']=joined.stadium.where(accepted)
    joined['mlb_game_pk']=joined.gamePk.where(accepted).astype('Int64')
    joined['mlb_venue_id']=joined.venue_id.where(accepted).astype('Int64')
    joined['fecha_partido']=joined.officialDate.where(accepted)
    joined['equipo_local']=joined.home.where(accepted)
    joined['equipo_visitante']=joined.away.where(accepted)
    joined['fuente_estadio']=joined.source_url.where(accepted)
    joined['stadium_id']=joined.mlb_venue_id.map(VENUE_CATALOG)
    oaxaca=joined.mlb_venue_id.eq(2951).fillna(False)
    joined.loc[oaxaca & joined.year.le(2025),'stadium_id']='oaxaca_vasconcelos'
    joined.loc[oaxaca & joined.year.ge(2026),'stadium_id']='oaxaca_yuva'
    joined['altitud_estadio_m']=joined.stadium_id.map(catalog.altitude_m)
    joined['fuente_altitud']=joined.stadium_id.map(catalog.altitude_source)
    joined['referencia_harp_helu']=np.where(accepted,np.where(joined.mlb_venue_id.eq(5340).fillna(False),'Harp Helu','Otro estadio'),'Sin identificar')
    joined.to_csv(OUT/'juegos_clasificados.csv',index=False,encoding='utf-8-sig')
    mapping=joined.loc[accepted & joined.stadium_id.notna(),['year','game_anon_id','stadium_id','fuente_estadio']].rename(columns={'fuente_estadio':'source_url'})
    mapping.to_csv(OUT/'mapeo_juego_estadio.csv',index=False,encoding='utf-8-sig')
    cols=['game_anon_id','estado_clasificacion','estadio','stadium_id','mlb_game_pk','mlb_venue_id','fecha_partido',
          'equipo_local','equipo_visitante','altitud_estadio_m','fuente_altitud','referencia_harp_helu','fuente_estadio',
          'event_match_ratio_30s','event_median_seconds','event_hour_correction']
    enriched=original.merge(joined[cols],on='game_anon_id',how='left',validate='many_to_one',sort=False)
    assert enriched.PitchUID.tolist()==original.PitchUID.tolist()
    pd.testing.assert_frame_equal(original,enriched[original.columns],check_exact=True)
    enriched['fecha_uuid_utc']=dates.fecha_uuid_utc.dt.strftime('%Y-%m-%d %H:%M:%S.%fZ').where(dates.fecha_uuid_utc.notna())
    enriched['fecha_uuid_mexico']=dates.fecha_uuid_utc.dt.tz_convert('America/Mexico_City').dt.strftime('%Y-%m-%d %H:%M:%S.%f').where(dates.fecha_uuid_utc.notna())
    enriched.to_parquet(OUT/'stuff_model_df_con_estadios.parquet',index=False)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
    summary=joined.groupby(['year','estado_clasificacion','estadio','mlb_venue_id'],dropna=False).agg(juegos=('game_anon_id','size'),lanzamientos=('n_pitches','sum')).reset_index()
    summary.to_csv(OUT/'resumen_estadios.csv',index=False,encoding='utf-8-sig')
    counts=dict(Counter(joined.estado_clasificacion))
    audit={'source_sha256':source_hash,'source_rows':len(original),'output_rows':len(enriched),'original_columns_preserved':list(original.columns),
           'games':len(joined),'status_games':counts,'classified_pitches':int(enriched.estadio.notna().sum()),
           'pending_pitches':int(enriched.estadio.isna().sum()),'harp_helu_games':int(joined.mlb_venue_id.eq(5340).sum()),
           'harp_helu_pitches':int(enriched.mlb_venue_id.eq(5340).sum()),'no_source_modification':True,
           'method':'UUID v1 timestamps + public LMB schedule + same-inning pitch event timestamps; no altitude used for identification',
           'thresholds':{'minimum_fraction_within_30_seconds':.85,'maximum_median_seconds':15,'minimum_temporal_coverage':.85,'minimum_matching_pitches':50,'minimum_candidate_margin':.15,
                         'alternative_with_exact_inning_signature':{'fraction_within_30_seconds':.65,'maximum_median_seconds':20,'calendar_duration_error_minutes':5,'calendar_start_residual_minutes':3},
                         'alternative_with_near_inning_signature':{'maximum_run_difference':1,'minimum_compared_halves':10,'fraction_within_30_seconds':.70,'maximum_median_seconds':15,'minimum_temporal_coverage':.90,'calendar_duration_error_minutes':5,'calendar_start_residual_minutes':3}},
           'not_official_identity_key':True,'created_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
    (OUT/'AUDITORIA_CLASIFICACION.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in audit.items() if k!='original_columns_preserved'},ensure_ascii=False,indent=2),flush=True)
    readme=pd.DataFrame([
        ['Contenido','Todos los lanzamientos originales con columnas adicionales; fuente original conservada.'],
        ['Metodo','Fechas UUID v1, calendario LMB y proximidad a jugadas públicas dentro de la misma media entrada.'],
        ['Verificado','Al menos 85% de horas a <=30 s; mediana <=15 s; cobertura >=85%; >=50 coincidencias; margen >=15 puntos frente a otro candidato comprobado.'],
        ['Verificado huella y jugadas','Alternativa: huella exacta de carreras por media entrada, hora y duración coherentes, >=65% de horas a <=30 s y mediana <=20 s; misma cobertura, mínimo y margen.'],
        ['Verificado huella parcial y jugadas','Máximo una carrera de diferencia en >=10 medias entradas; hora y duración coherentes; >=70% de horas a <=30 s, mediana <=15 s y cobertura >=90%; candidato único con margen.'],
        ['Pendientes','Sin estadio asignado. El candidato solo se muestra en Juegos y Pendientes; no equivale a identificación.'],
        ['Fechas','fecha_uuid_utc es el tiempo codificado; fecha_uuid_mexico es su conversión UTC-6. fecha_partido procede del calendario para juegos verificados.'],
        ['Correccion horaria','event_hour_correction indica horas restadas al UUID para cotejar jugadas. No se corrigen las columnas originales.'],
        ['Estadios','Nombres y venue IDs proceden de la API pública; cambios de nombre comercial pueden compartir venue ID.'],
        ['Altitud','Se adjunta el catálogo local con su fuente. No se usa altitud para decidir el estadio; sedes sin altitud verificada conservan vacío.'],
        ['Limitacion','Cruce inferido y reproducible, no llave oficial entregada por la organización. Revisar pendientes antes de validación por parque.'],
        ['Origen','stuff_model_df.parquet; SHA256 '+source_hash],
        ['Lanzamientos',str(len(enriched))],['Juegos',str(len(joined))],['Juegos verificados',str(int(accepted.sum()))],
        ['Datos','Uso local de competencia. Este Excel contiene el dataset original y no se añade al ZIP público de resultados.'],
    ],columns=['Tema','Detalle'])
    path=OUT/'Lanzamientos_clasificados_por_estadio.xlsx'
    options={'constant_memory':True,'strings_to_urls':False,'nan_inf_to_errors':False,'use_zip64':True}
    with xlsxwriter.Workbook(path,options) as book:
        header=book.add_format({'bg_color':'#A71930','font_color':'white','bold':True,'text_wrap':True})
        def sheet(name,frame):
            ws=book.add_worksheet(name); ws.freeze_panes(1,0);ws.set_row(0,32)
            ws.write_row(0,0,list(frame.columns),header)
            ws.set_column(0,len(frame.columns)-1,16)
            for i,c in enumerate(frame.columns):
                if any(token in c.lower() for token in ['estadio','equipo','fuente','uuid','pitchuid']): ws.set_column(i,i,30)
            for n,row in enumerate(frame.itertuples(index=False,name=None),1):
                values=[]
                for value in row:
                    if value is None or value is pd.NA or value is pd.NaT: values.append(None)
                    elif isinstance(value,float): values.append(value if np.isfinite(value) else (None if np.isnan(value) else str(value)))
                    elif isinstance(value,(pd.Timestamp,dt.datetime)): values.append(value.isoformat())
                    else: values.append(value)
                ws.write_row(n,0,values)
                if n%50000==0: print(f'Excel {name}: {n:,}/{len(frame):,} filas',flush=True)
            ws.autofilter(0,0,len(frame),len(frame.columns)-1)
            return ws
        ws=sheet('LEEME',readme);ws.set_column(1,1,115)
        sheet('Resumen_estadios',summary)
        game_columns=['year','game_anon_id','estado_clasificacion','estadio','stadium_id','mlb_game_pk','mlb_venue_id','fecha_partido','equipo_local','equipo_visitante','n_pitches','first_utc','last_utc','altitude_category','event_match_ratio_30s','event_median_seconds','event_hour_correction','estadio_candidato','source_url']
        sheet('Juegos',joined[game_columns])
        sheet('Pendientes',joined.loc[~accepted,game_columns])
        front=['year','PitchUID','game_anon_id','fecha_partido','fecha_uuid_utc','fecha_uuid_mexico','estadio','estado_clasificacion','stadium_id','mlb_game_pk','mlb_venue_id','referencia_harp_helu','equipo_local','equipo_visitante','altitud_estadio_m']
        sheet('Lanzamientos',enriched[front+[c for c in enriched.columns if c not in front]])
        sheet('Calendario_publico',pd.read_csv(OUT/'calendario_lmb_2024_2026.csv'))
    print('Excel completado',path,path.stat().st_size,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('step',choices=['prepare','schedules','match','feeds','validate','export'])
    args=parser.parse_args()
    if args.step=='prepare': prepare()
    elif args.step=='schedules': schedules()
    elif args.step=='match': match_games()
    elif args.step=='feeds': feeds()
    elif args.step=='validate': validate_feeds()
    else: export()
