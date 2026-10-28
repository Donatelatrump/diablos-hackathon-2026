"""Descarga fuentes públicas seleccionadas para revisión estática; no las ejecuta."""
import concurrent.futures
import json
from pathlib import Path
import urllib.request

ROOT = Path('investigacion_github_2026_10_27')
REPOS = ['noelBanda/Hackathon-Diablos', 'dulongski/diablos-hackathon',
         'AriadnaPA/Diablos-Hackathon-2026', 'JaavRJ/hackathon_isac2026_diablosrojos',
         'ariadnaquijano/-Hackathon-Diablos-Rojos-2026', 'militomtzc-lang/stuffplus-harp-helu',
         'FerArGo56/diablos-rojos-WARROOM-stuffplus', 'MVelascoWS/stuffplus-lmb',
         'Trazeure/isac26-stuff-altitud', 'JorgeCroda/NeuroPower_Hackathon2026']

def fetch(item):
    i, repo, sha, path = item
    target = ROOT / str(i) / path
    if target.exists():
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    url = f'https://raw.githubusercontent.com/{repo}/{sha}/{urllib.parse.quote(path)}'
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'hackathon-research'})
        with urllib.request.urlopen(request, timeout=30) as response:
            target.write_bytes(response.read())
        return None
    except Exception as exc:
        return f'{repo}/{path}: {exc}'

def main():
    tasks = []
    index = []
    for i, repo in enumerate(REPOS):
        tree = json.loads(Path(f'github_tree_{i}.json').read_text(encoding='utf-8'))
        index.append({'repo': repo, 'sha': tree['sha']})
        for entry in tree.get('tree', []):
            p = entry['path']
            if entry['type'] != 'blob' or entry.get('size', 0) > 200000:
                continue
            selected = (p.endswith('.py') and not p.startswith(('tests/', 'evaluations/', 'delivery_checks/')))
            selected |= p in ['README.md', 'src/stuffplus/constants.py', 'src/stuffplus/physics.py', 'docs/documento_tecnico.md', 'docs/05_pasaporte_altitud.md', 'docs/06_fisica_densidad.md', 'docs/01_limpieza.md', 'docs/decisiones.md', 'PROJECT_CONTEXT.md', 'webapp/backend/data/reference/stadiums.json', 'webapp/backend/data/reference/column_map.json', 'webapp/README.md', 'modelos/stuff_plus/StuffPlus.ipynb', 'reports/altitude/relabeling_audit.csv', 'reportes/etapa_06_validacion_estadio.json', 'outputs/translation_factors.json', 'artifacts/physics.json']
            selected |= p in ['NeuroPower_Code.ipynb', 'clima_publico/constantes.json', 'clima_publico/clima_resumen_estadio.csv']
            if selected:
                tasks.append((i, repo, tree['sha'], p))
    ROOT.mkdir(exist_ok=True)
    (ROOT / 'repos.json').write_text(json.dumps(index, indent=2), encoding='utf-8')
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        errors = [r for r in pool.map(fetch, tasks) if r]
    print(json.dumps({'requested': len(tasks), 'errors': errors}, indent=2))

if __name__ == '__main__':
    main()
