"""Comprueba el Excel terminado, cobertura y conservación del origen."""
from pathlib import Path
import hashlib
import json
import re
import zipfile
import xml.etree.ElementTree as ET
import xml.parsers.expat

import pandas as pd
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parent

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()

def main():
    audit=json.loads((ROOT/'AUDITORIA_CLASIFICACION.json').read_text(encoding='utf-8'))
    source=ROOT.parent/'stuff_model_df.parquet'
    enriched=ROOT/'stuff_model_df_con_estadios.parquet'
    workbook=ROOT/'Lanzamientos_clasificados_por_estadio.xlsx'
    assert sha(source)==audit['source_sha256']
    metadata=pq.ParquetFile(enriched)
    assert metadata.metadata.num_rows==audit['source_rows']==635002
    assert set(audit['original_columns_preserved']).issubset(metadata.schema_arrow.names)
    games=pd.read_csv(ROOT/'juegos_clasificados.csv')
    assigned=games.loc[games.estadio.notna()]
    assert len(assigned)==2009 and assigned.mlb_game_pk.nunique()==2009
    assert games.game_anon_id.nunique()==2127
    assert int(games.n_pitches.sum())==635002
    assert int(assigned.n_pitches.sum())==601120
    assert games.loc[games.estado_clasificacion.eq('pendiente'),'estadio'].isna().all()
    with zipfile.ZipFile(workbook) as z:
        row_count=0
        for info in z.infolist():
            if info.filename=='xl/worksheets/sheet5.xml':
                buffer=b''
                prefix=None
                with z.open(info.filename) as f:
                    for chunk in iter(lambda:f.read(4*1024*1024),b''):
                        buffer+=chunk
                        if prefix is None:
                            start=buffer.find(b'<row ')
                            if start<0:continue
                            prefix=buffer[:start]
                            buffer=buffer[start:]
                        end=buffer.rfind(b'</row>')
                        if end>=0:
                            batch=buffer[:end+6]
                            buffer=buffer[end+6:]
                            row_count+=batch.count(b'<row ')
                            # Bounded batches avoid this Expat build's cumulative 2 GiB input limit.
                            parser=xml.parsers.expat.ParserCreate()
                            parser.Parse(b'<root>'+batch+b'</root>',True)
                ET.fromstring(prefix+buffer)
            else:
                data=z.read(info.filename)
                if info.filename.endswith(('.xml','.rels')):ET.fromstring(data)
        assert row_count==635003,row_count
        book=ET.fromstring(z.read('xl/workbook.xml'))
        ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        sheets=[s.attrib['name'] for s in book.findall('m:sheets/m:sheet',ns)]
        assert sheets==['LEEME','Resumen_estadios','Juegos','Pendientes','Lanzamientos','Calendario_publico']
        with z.open('xl/worksheets/sheet5.xml') as f:
            head=f.read(32768).decode('utf-8')
        dimension=re.search(r'<dimension ref="([^"]+)"',head).group(1)
        assert dimension.endswith('635003'),dimension
    result={'xlsx_valid_crc':True,'xlsx_sheets':sheets,'xlsx_pitch_sheet_dimension':dimension,
            'xlsx_pitch_rows':row_count-1,'xlsx_xml_well_formed':True,
            'xlsx_bytes':workbook.stat().st_size,'xlsx_sha256':sha(workbook),
            'parquet_rows':metadata.metadata.num_rows,'parquet_columns':len(metadata.schema_arrow.names),
            'original_source_hash_unchanged':True,'original_values_checked_during_export':True,
            'assigned_games':len(assigned),'assigned_pitches':int(assigned.n_pitches.sum()),
            'pending_games':int(games.estadio.isna().sum())}
    (ROOT/'VERIFICACION_ARCHIVOS.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__':
    main()
