"""Exportación de todas las columnas con XML por lotes y ZIP64 para hojas grandes."""
from pathlib import Path
import math
import re
import zipfile
import datetime as dt
import sys

import pandas as pd
import xlsxwriter
from xlsxwriter.utility import xl_col_to_name

OUT=Path('clasificacion_estadios')
CONTROL=re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')

def text(value):
    value=CONTROL.sub(lambda m:f'_x{ord(m.group()):04X}_',str(value))
    return value.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def scalar(value):
    if value is None or value is pd.NA or value is pd.NaT: return None
    if isinstance(value,float) and not math.isfinite(value): return None if math.isnan(value) else str(value)
    if isinstance(value,(pd.Timestamp,dt.datetime)): return value.isoformat()
    return value

def main():
    df=pd.read_parquet(OUT/'stuff_model_df_con_estadios.parquet')
    front=['year','PitchUID','game_anon_id','fecha_partido','fecha_uuid_utc','fecha_uuid_mexico','estadio',
           'estado_clasificacion','stadium_id','mlb_game_pk','mlb_venue_id','referencia_harp_helu',
           'equipo_local','equipo_visitante','altitud_estadio_m']
    df=df[front+[c for c in df.columns if c not in front]]
    games=pd.read_csv(OUT/'juegos_clasificados.csv')
    readme=pd.DataFrame([
        ['Contenido','635,002 lanzamientos; 84 columnas originales y columnas adicionales.'],
        ['Clasificacion','2,009 juegos y 601,120 lanzamientos con estadio; 118 juegos pendientes.'],
        ['Harp Helu','117 juegos y 36,399 lanzamientos. Filtrar referencia_harp_helu.'],
        ['Metodo','UUID v1, calendario LMB y horas de jugadas de la misma media entrada. No es una llave oficial.'],
        ['Estados','Verificado por jugadas, por huella y jugadas o por huella parcial y jugadas; pendientes sin estadio.'],
        ['Criterios','Consultar README.md y AUDITORIA_CLASIFICACION.json para umbrales exactos y evidencia.'],
        ['Datos originales','Columnas y valores originales conservados; el Parquet original no se modifica.'],
        ['Fechas','fecha_uuid_utc es el timestamp codificado; fecha_uuid_mexico usa America/Mexico_City. fecha_partido es la fecha del calendario.'],
        ['Horarios','event_hour_correction contiene horas restadas solo para contrastar jugadas; no modifica los timestamps originales.'],
        ['Altitud','Se conserva la categoria original y se anade la altitud del catalogo local; faltantes sin inventar.'],
        ['Discrepancia conocida','game_001557, Oaxaca-Tabasco 26/04/2026, se jugo en Leon; conserva Medium Altitude original. Ver README.'],
        ['Uso','Datos de competencia locales. Los nombres comerciales pueden variar: usar stadium_id para agrupar.'],
    ],columns=['Tema','Detalle'])
    columns=['year','game_anon_id','estado_clasificacion','estadio','stadium_id','mlb_game_pk','mlb_venue_id',
             'fecha_partido','equipo_local','equipo_visitante','n_pitches','first_utc','last_utc',
             'altitude_category','event_match_ratio_30s','event_median_seconds','event_hour_correction',
             'estadio_candidato','source_url']
    small=[('LEEME',readme),('Resumen_estadios',pd.read_csv(OUT/'resumen_estadios.csv')),
           ('Juegos',games[columns]),('Pendientes',pd.read_csv(OUT/'pendientes_con_motivo.csv')),
           ('Lanzamientos',df.iloc[:0]),('Calendario_publico',pd.read_csv(OUT/'calendario_lmb_2024_2026.csv'))]
    template=OUT/'plantilla_excel.xlsx'
    with xlsxwriter.Workbook(template,{'constant_memory':True,'strings_to_urls':False,'use_zip64':True,'tmpdir':str(OUT)}) as book:
        header=book.add_format({'bg_color':'#A71930','font_color':'white','bold':True,'text_wrap':True})
        for name,frame in small:
            ws=book.add_worksheet(name);ws.freeze_panes(1,0);ws.set_row(0,32)
            ws.set_column(0,len(frame.columns)-1,17)
            for i,c in enumerate(frame.columns):
                if any(t in c.lower() for t in ['estadio','equipo','fuente','uuid','pitchuid']): ws.set_column(i,i,30)
            ws.write_row(0,0,list(frame.columns),header)
            for row,values in enumerate(frame.itertuples(index=False,name=None),1):
                ws.write_row(row,0,[scalar(v) for v in values])
            count=len(df) if name=='Lanzamientos' else len(frame)
            ws.autofilter(0,0,count,len(frame.columns)-1)
            if name=='LEEME':ws.set_column(1,1,115)
    target=OUT/'Lanzamientos_clasificados_por_estadio.xlsx'
    temporary=OUT/'Lanzamientos_clasificados_por_estadio.en_proceso.xlsx'
    letters=[xl_col_to_name(i) for i in range(len(df.columns))]
    with zipfile.ZipFile(template) as source, zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as dest:
        for info in source.infolist():
            if info.filename!='xl/worksheets/sheet5.xml':
                dest.writestr(info.filename,source.read(info.filename))
                continue
            xml=source.read(info.filename).decode('utf-8')
            prefix,rest=xml.split('<sheetData>',1)
            firstrow,suffix=rest.split('</sheetData>',1)
            prefix=re.sub(r'<dimension ref="[^"]+"',f'<dimension ref="A1:{letters[-1]}{len(df)+1}"',prefix)
            with dest.open(info.filename,'w',force_zip64=True) as stream:
                stream.write((prefix+'<sheetData>'+firstrow).encode('utf-8'))
                buffer=[]
                for n,row in enumerate(df.itertuples(index=False,name=None),2):
                    cells=[]
                    for col,v in zip(letters,row):
                        if v is None or v is pd.NA or v is pd.NaT: continue
                        ref=f'{col}{n}'
                        if isinstance(v,bool):cells.append(f'<c r="{ref}" t="b"><v>{int(v)}</v></c>')
                        elif isinstance(v,(int,float)):
                            if isinstance(v,float) and not math.isfinite(v): continue
                            cells.append(f'<c r="{ref}"><v>{v}</v></c>')
                        else: cells.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{text(v)}</t></is></c>')
                    buffer.append(f'<row r="{n}">'+''.join(cells)+'</row>')
                    if len(buffer)>=1000:
                        stream.write(('\n'.join(buffer)+'\n').encode('utf-8'));buffer.clear()
                    if (n-1)%100000==0:print(f'Excel ZIP64: {n-1:,}/{len(df):,}',flush=True)
                if buffer:stream.write(('\n'.join(buffer)+'\n').encode('utf-8'))
                stream.write(('</sheetData>'+suffix).encode('utf-8'))
    temporary.replace(target)
    print('Excel terminado',target,target.stat().st_size,flush=True)

def add_row_newlines():
    """Mantiene celdas intactas y limita la longitud de línea del XML para lectores SAX."""
    target=OUT/'Lanzamientos_clasificados_por_estadio.xlsx'
    temporary=OUT/'Lanzamientos_clasificados_por_estadio.compatible.xlsx'
    with zipfile.ZipFile(target) as source,zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as dest:
        for info in source.infolist():
            if info.filename!='xl/worksheets/sheet5.xml':
                dest.writestr(info.filename,source.read(info.filename));continue
            carry=b'';total=0;reported=0
            with source.open(info.filename) as reader,dest.open(info.filename,'w',force_zip64=True) as writer:
                for chunk in iter(lambda:reader.read(4*1024*1024),b''):
                    data=carry+chunk
                    head,sep,carry=data.rpartition(b'</row>')
                    if sep:writer.write(head.replace(b'</row>',b'</row>\n')+sep+b'\n')
                    else:carry=data
                    total+=len(chunk)
                    if total//(500*1024*1024)>reported:
                        reported=total//(500*1024*1024);print('Compatibilidad XML:',reported*500,'MiB',flush=True)
                if carry:writer.write(carry)
    temporary.replace(target)
    print('Excel compatible completado',target.stat().st_size,flush=True)

if __name__=='__main__':
    if '--newlines-only' in sys.argv:add_row_newlines()
    else:main()
