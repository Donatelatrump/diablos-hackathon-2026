"""Verificaciones de integridad, holdouts y contenido del paquete actual."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import duckdb
import numpy as np

import entrenar_stuff_plus_v9 as v9

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/v9_estadios'


def read(path):
    with duckdb.connect() as con:
        return con.execute('SELECT * FROM read_parquet(?)',[str(path)]).fetchdf()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paquete',action='store_true')
    args=parser.parse_args()
    results={}
    source=ROOT/'stuff_model_df_con_estadios.parquet'
    source_hash=v9.v6.file_hash(source)
    development=v9.read_rows(source,2026,True)
    games=development[['year','game_anon_id','stadium']].drop_duplicates()
    assert not games.duplicated(['year','game_anon_id']).any()
    for mode,suffix in [('season',''),('pitcher','_pitcher'),('park','_park')]:
        folder=ROOT/('stuff_plus_output_v9_estadios'+suffix)
        protocol=json.loads((folder/'protocolo.json').read_text())
        assert protocol['source_sha256']==source_hash
        assert protocol['holdout']==mode
        assert len(json.loads((folder/'metricas.json').read_text()))==13
        assert (folder/'bundle.json').read_bytes()==(folder/'seleccion_congelada.json').read_bytes()
        for name,digest in protocol['code_hashes'].items():
            assert v9.v6.file_hash(ROOT/name)==digest
        meta,models=v9.load_bundle(folder)
        assert len(models)==13
        parts=read(folder/'particiones.parquet')
        assert parts.year.lt(2026).all()
        assert parts.groupby(['year','game_anon_id']).partition.nunique().max()==1
        assert not parts.PitchUID.duplicated().any()
        scores=read(folder/'scores_pitch_v9.parquet')
        assert scores.year.eq(2026).all()
        assert set(parts.PitchUID).isdisjoint(scores.PitchUID)
        values=scores.select_dtypes('number')
        assert np.isfinite(values).all().all()
        for column in scores.columns:
            if column.startswith('p_'):
                assert scores[column].between(0,1).all()
        if mode=='pitcher':
            assert parts.pitcher_anon_id.notna().all()
            assert not parts.pitcher_anon_id.map(v9.held_pitcher).any()
            assert scores.pitcher_anon_id.map(v9.held_pitcher).all()
            assert set(parts.pitcher_anon_id).isdisjoint(scores.pitcher_anon_id)
            assert all(not v9.held_pitcher(r['pitcher_anon_id']) for r in meta['profile']['fastballs'])
        if mode=='park':
            merged=parts.merge(games,on=['year','game_anon_id'],validate='many_to_one')
            assert not merged.stadium.eq('Estadio Alfredo Harp Helu').any()
            assert scores.stadium.eq('Estadio Alfredo Harp Helu').all()
            assert len(scores)==6005
        results[mode]=dict(models=len(models),development_rows=len(parts),test_rows=len(scores),
            model_hashes=True,source_hash=True,code_hashes=True,whole_games=True,held_groups_excluded=True,
            finite_scores=True,probability_bounds=True)
    supplement=REPORT/'complemento'
    if supplement.exists():
        for mode,suffix in [('season',''),('pitcher','_pitcher'),('park','_park')]:
            folder=supplement/mode
            meta=json.loads((folder/'out_pa.json').read_text())
            assert meta['source_sha256']==source_hash
            assert meta['code_sha256']==v9.v6.file_hash(ROOT/'src/completar_targets_pa.py')
            assert meta['model_sha256']==v9.v6.file_hash(folder/'out_pa.cbm')
            base=ROOT/('stuff_plus_output_v9_estadios'+suffix)
            assert meta['base_bundle_sha256']==v9.v6.file_hash(base/'bundle.json')
            ref=json.loads((folder/'indice_integral.json').read_text())
            assert ref['pa_metadata_sha256']==v9.v6.file_hash(folder/'out_pa.json')
            scores=read(folder/'scores_integrales.parquet')
            assert scores.p_out_within_pa.between(0,1).all()
            assert np.isfinite(scores.select_dtypes('number')).all().all()
            refs=json.loads((folder/'referencias_temporada_estadio.json').read_text())
            for item in refs:
                if item['reference']=='season_park' and item['std']>1e-8:
                    values=scores.loc[scores.stadium_id.eq(item['stadium_id']),item['score']+'_temporada_estadio']
                    assert abs(values.mean()-100)<1e-8
                    assert abs(values.std(ddof=0)-10)<1e-8
            results[mode]['pa_and_integral_verified']=True
    if args.paquete:
        package=ROOT/'entrega_estadios'
        manifest=json.loads((package/'MANIFIESTO.json').read_text())
        for name,digest in manifest.items():
            assert v9.v6.file_hash(package/name)==digest,name
        with ZipFile(ROOT/'ENTREGA_ESTADIOS_ACTUALIZADA.zip') as archive:
            assert archive.testzip() is None
            assert set(archive.namelist())==set(manifest)|{'MANIFIESTO.json'}
            for name in archive.namelist():
                assert 'stuff_model_df' not in name and not name.endswith(('.pkl','.rds'))
                if name in manifest:
                    assert hashlib.sha256(archive.read(name)).hexdigest()==manifest[name]
        for path in package.rglob('*.parquet'):
            columns=set(read(path).columns)
            assert not columns & {'RelSpeed','ExitSpeed','PitchCall','play_result','SpinRate','PlateLocHeight'}
        results['package']=dict(manifest_hashes=True,zip_integrity=True,no_raw_pitch_columns=True,
            files=len(manifest),bytes=(ROOT/'ENTREGA_ESTADIOS_ACTUALIZADA.zip').stat().st_size)
    (REPORT/'VERIFICACION_ACTUAL.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(results,indent=2),flush=True)


if __name__=='__main__':
    main()
