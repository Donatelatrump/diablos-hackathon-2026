"""Publish completed audit metrics without training or changing fitted model artifacts.

Run from any directory with python scripts/13_validation_audit.py. Requires the
completed evaluations/codex_review_2026_10_22 audit and its original file manifest.
"""
from pathlib import Path
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / 'evaluations' / 'codex_review_2026_10_22'


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    source = AUDIT / 'results.json'
    results = json.loads(source.read_text())
    manifest = json.loads((AUDIT / 'original_files.json').read_text())
    reconstructed = json.loads((AUDIT / 'target_reconstruction_check.json').read_text())
    if not reconstructed.get('passed') or reconstructed.get('max_abs_rv_error_full_lookup') != 0:
        raise ValueError('Audit target reconstruction parity check did not pass')
    if len(results['folds']) != 4 or any(f['pitcher_overlap'] != 0 for f in results['folds']):
        raise ValueError('Expected four disjoint pitcher validation folds')
    if sum(f['test'] for f in results['folds']) != results['grouped']['current']['n']:
        raise ValueError('Audit fold row counts do not reconcile')
    files = sorted((ROOT / 'artifacts').glob('model_*.txt'))
    files += [ROOT / 'artifacts' / n for n in ('scale.json', 'models.json', 'oof_rv.npy')]
    checked = {}
    for file in files:
        key = str(file.relative_to(ROOT))
        expected = manifest.get(key, {}).get('sha256')
        actual = sha256(file)
        if expected is None or expected != actual:
            raise ValueError(f'Production model provenance changed or missing: {key}')
        checked[key] = actual
    if not any(Path(p).name == 'model_stuff.txt' for p in checked):
        raise ValueError('Missing shipped Stuff+ model')
    for scores in [results['grouped']] + [x['metrics'] for x in results['chronological'].values()]:
        for row in scores.values():
            if not math.isfinite(row['rmse']) or not math.isfinite(row['r2']):
                raise ValueError('Non-finite audit metric')
    legacy = json.loads((ROOT / 'artifacts' / 'models.json').read_text())
    export = {
        'schema_version': 1,
        'status': 'completed_reproducible_audit',
        'model_status': 'Existing fitted production model, scale and OOF arrays unchanged.',
        'scope': 'Separate re-fits of the current model specification and exploratory candidates; not a re-evaluation of the exact shipped fitted booster.',
        'protocol': results['protocol'],
        'grouped': results['grouped'],
        'chronological': results['chronological'],
        'legacy_benchmark': {
            'label': 'Original benchmark with globally fitted target/count tables.',
            'stuff': legacy['holdout_pitcher']['stuff'],
            'baseline': legacy['baseline_nulo_por_conteo'],
        },
        'target_lookup_sensitivity': results['target_lookup_sensitivity'],
        'provenance': {
            'source': str(source.relative_to(ROOT)),
            'source_sha256': sha256(source),
            'evaluation_script_sha256': sha256(AUDIT / 'evaluate.py'),
            'target_reconstruction_check': reconstructed,
            'versions': results['versions'],
            'unchanged_fitted_files_sha256': checked,
        },
    }
    text = json.dumps(export, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    destinations = [ROOT / 'artifacts' / 'validation_audit.json', ROOT / 'app/public/data/validation_audit.json']
    for file in destinations:
        file.write_text(text)
    print(json.dumps({'outputs': [str(f.relative_to(ROOT)) for f in destinations],
                      'source_sha256': export['provenance']['source_sha256'],
                      'unchanged_fitted_files': len(checked), 'bytes_each': len(text.encode())}, indent=2))


if __name__ == '__main__':
    main()
