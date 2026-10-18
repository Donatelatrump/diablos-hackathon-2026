"""Verifica grupos de auditoría, agregados, PDF y contenido del ZIP."""
from pathlib import Path
import json
import zipfile
import numpy as np
import pandas as pd
from pypdf import PdfReader
import entrenar_stuff_plus_v8 as v8
OUT=Path('entrega_v8')


def main():
    protocol=json.loads((OUT/'validacion_pitchers/protocolo.json').read_text(encoding='utf-8'))
    assert v8.v6.file_hash('validar_pitchers_v8.py')==protocol['script_sha256']
    assert v8.v6.file_hash('stuff_model_df.parquet')==protocol['source_sha256']
    assert v8.v6.file_hash('stuff_plus_output_v8/bundle.json')==protocol['v8_bundle_sha256']
    parts={name:v8.v5.read_parquet(OUT/f'validacion_pitchers/{name}_ids.parquet') for name in ['fit','stop','cal','test']}
    for i,(name,a) in enumerate(parts.items()):
        assert set(a.pitcher_anon_id)<=set(protocol['roles'][name])
        assert not a.PitchUID.duplicated().any()
        for b in list(parts.values())[i+1:]:
            assert not set(a.pitcher_anon_id)&set(b.pitcher_anon_id)
            assert not set(a.PitchUID)&set(b.PitchUID)
    assert all(x.year.le(2025).all() for k,x in parts.items() if k!='test')
    assert parts['test'].year.eq(2026).all()
    audit=json.loads((OUT/'validacion_pitchers/verificacion.json').read_text(encoding='utf-8'))
    for file,digest in audit['model_hashes'].items(): assert v8.v6.file_hash(OUT/'validacion_pitchers'/file)==digest
    predictions=v8.v5.read_parquet(OUT/'validacion_pitchers/predicciones.parquet')
    assert set(predictions.PitchUID)==set(parts['test'].PitchUID)
    tasks=json.loads((OUT/'validacion_pitchers/metricas.json').read_text(encoding='utf-8'))
    assert np.isfinite(predictions[[r['task'] for r in tasks]]).all().all()
    pitchers=pd.read_csv(OUT/'pitchers_v8.csv')
    scores=v8.v5.read_parquet('stuff_plus_output_v8/scores_pitch_v8.parquet')
    public=pd.read_csv(OUT/'scores_por_lanzamiento_v8.csv')
    assert len(public)==len(scores) and public.PitchUID.tolist()==scores.PitchUID.tolist()
    assert not set(public)&{'RelSpeed','SpinRate','ExitSpeed','PitchCall','is_whiff','Balls','Strikes'}
    np.testing.assert_allclose(public[['stuff_plus','location_plus','pitching_plus']],scores[['stuff_plus','location_plus','pitching_plus']])
    assert pitchers.n_pitches.sum()==scores.pitcher_anon_id.notna().sum()
    assert pitchers.loc[pitchers.n_games.eq(1),'ci_low'].isna().all()
    assert not pitchers.duplicated(['year','pitcher_anon_id','score_reference_id']).any()
    env=pd.read_csv(OUT/'entorno_ajustado.csv')
    assert (env.n_pitchers>=5).all() and (env.n_low>=3*env.n_matched_cells).all()
    assert (env.n_high>=3*env.n_matched_cells).all()
    cases=json.loads((OUT/'casos_scouting.json').read_text(encoding='utf-8'))
    assert len(cases)==3 and len({x['pitcher'] for x in cases})==3
    for case in cases:
        row=pitchers.loc[pitchers.pitcher_anon_id.eq(case['pitcher'])].iloc[0]
        assert int(row.n_pitches)==case['n_pitches']
        np.testing.assert_allclose(row.pitching_plus,case['pitching_plus'])
    pdf=PdfReader(OUT/'DOCUMENTO_TECNICO_V8.pdf')
    assert 6<=len(pdf.pages)<=10
    assert all(len(p.extract_text())>100 for p in pdf.pages)
    manifest=json.loads((OUT/'MANIFIESTO.json').read_text(encoding='utf-8'))
    for file,digest in manifest['files'].items(): assert v8.v6.file_hash(OUT/file)==digest,file
    with zipfile.ZipFile('ENTREGA_DIABLOS_V8.zip') as archive:
        assert archive.testzip() is None
        assert set(archive.namelist())==set(manifest['files'])|{'MANIFIESTO.json'}
        assert not any(Path(p).suffix in ['.parquet','.pkl','.rds','.cbm'] for p in archive.namelist())
        assert not any('stuff_model_df' in p for p in archive.namelist())
    result={'audit_groups_disjoint':True,'temporal_boundary':True,'model_hashes':True,'aggregate_counts':True,
            'cases_reproduced':True,'pdf_pages':len(pdf.pages),'zip_no_raw_data_or_models':True,
            'manifest_hashes':True,'benchmark_reused':True}
    v8.v6.json_write(OUT/'VERIFICACION_ENTREGA.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
