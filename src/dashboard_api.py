"""Local HTTP adapter for the React dashboard; ML stays in the existing Python pipeline.

Run: python3 src/dashboard_api.py (no extra dependencies for saved reports).
"""
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import argparse
import csv
import json
import math
import mimetypes
import threading

from proyecto_io import bundle_ready, is_lfs_pointer

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/v9_estadios'
RUN_NAMES = ['stuff_plus_output_v9_estadios', 'stuff_plus_output_v9_incremental', 'stuff_plus_output_v9']
INFERENCE_LOCK = threading.Lock()
DOCUMENTS = {
    'recommendations': ('Recomendaciones actuales', REPORT / 'RECOMENDACIONES_ACTUALES.md'),
    'technical': ('Documento técnico', REPORT / 'DOCUMENTO_TECNICO_ESTADIOS.pdf'),
    'harp': ('Qué revisar para Harp Helú', REPORT / 'HARP_HELU.md'),
    'guide': ('Guía del proyecto', ROOT / 'docs/guias/GUIA_PROYECTO.md'),
    'v8-guide': ('Entrega histórica v8', ROOT / 'entrega_v8/README_ENTREGA.md'),
    'v8-technical': ('Documento técnico v8', ROOT / 'entrega_v8/DOCUMENTO_TECNICO_V8.pdf'),
}


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.is_file() and not is_lfs_pointer(path) else default


def read_csv(path):
    if not path.is_file() or is_lfs_pointer(path):
        return []
    with path.open(newline='', encoding='utf-8-sig') as handle:
        return list(csv.DictReader(handle))


def choose_run(name=None):
    if name is not None and name not in RUN_NAMES:
        raise ValueError('Versión desconocida.')
    for candidate in ([name] if name else RUN_NAMES):
        path = ROOT / candidate
        if bundle_ready(path):
            return path
    return None


def bootstrap():
    runs = []
    for name in RUN_NAMES:
        path = choose_run(name)
        if path:
            meta = read_json(path / 'bundle.json', {})
            runs.append({'id': name, 'profiles': meta.get('input_profiles', []),
                         'stadiums': read_csv(path / 'estadios.csv'),
                         'stadium_context': 'stadium_id' in meta.get('tasks', {}).get('environment_run_value', {}).get('features', []),
                         'pitchers': sorted({p['pitcher_anon_id'] for p in meta.get('profile', {}).get('fastballs', [])})})
    return {'runs': runs, 'documents': [{'id': key, 'title': title, 'markdown': path.suffix == '.md'}
            for key, (title, path) in DOCUMENTS.items() if path.is_file() and not is_lfs_pointer(path)]}


def table_path(key, run=None):
    output = choose_run(run)
    paths = {
        'pitchers': output / 'pitchers.csv' if output else REPORT / 'missing.csv',
        'arsenal': output / 'arsenal.csv' if output else REPORT / 'missing.csv',
        'movement': output / 'mapa_movimiento.csv' if output else REPORT / 'missing.csv',
        'integral': REPORT / 'complemento/season/pitchers_integrales.csv',
        'integral-arsenal': REPORT / 'complemento/season/arsenales_integrales.csv',
        'profiles': REPORT / 'perfiles_fisicos.csv',
        'support': REPORT / 'soporte_perfiles.csv',
        'deltas': REPORT / 'deltas_por_perfil.csv',
        'v8-arsenal': ROOT / 'stuff_plus_output_v8/arsenal_con_incertidumbre.csv',
    }
    if key not in paths:
        raise ValueError('Tabla desconocida.')
    return paths[key]


@lru_cache(maxsize=3)
def load_bundle(path, modified):
    from entrenar_stuff_plus_v9 import load_bundle as load
    return load(path)


def simulate(payload):
    output = choose_run(payload.get('run'))
    if output is None:
        raise ValueError('No hay un modelo v9 disponible en este equipo.')
    meta = read_json(output / 'bundle.json')
    profile = next((p for p in meta['input_profiles'] if p['type'] == payload.get('pitch') and p['hand'] == payload.get('hand')), None)
    if profile is None:
        raise ValueError('Elige un tipo de lanzamiento y una mano válidos.')
    row = {**profile['median'], 'AutoPitchType': profile['type'], 'PitcherThrows': profile['hand'],
           'pitcher_anon_id': 'unknown', 'PitchUID': 'react', 'BatterSide': 'Right',
           'PlateLocHeight': 2.5, 'PlateLocSide': 0., 'Balls': 0, 'Strikes': 0}
    measurements = payload.get('measurements', {})
    allowed = set(profile['median']) | {'PlateLocHeight', 'PlateLocSide', 'Balls', 'Strikes'}
    if not isinstance(measurements, dict) or set(measurements) - allowed:
        raise ValueError('Mediciones desconocidas.')
    for key, value in measurements.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'Medición inválida: {key}.')
        row[key] = value
    if any(row.get(key) is None for key in profile['median']):
        raise ValueError('Completa las mediciones del lanzamiento.')
    if row['RelSpeed'] <= 0 or row['Balls'] not in range(4) or row['Strikes'] not in range(3):
        raise ValueError('Revisa la velocidad y el conteo.')
    side = payload.get('batter', 'Right')
    known = {p['pitcher_anon_id'] for p in meta.get('profile', {}).get('fastballs', [])}
    pitcher = payload.get('pitcher', 'unknown')
    if side not in ('Right', 'Left') or pitcher not in known | {'unknown'}:
        raise ValueError('Contexto inválido.')
    row.update(BatterSide=side, pitcher_anon_id=pitcher)
    selected = payload.get('stadiums', [])
    if not isinstance(selected, list) or not 1 <= len(selected) <= 3 or any(not isinstance(x, str) for x in selected):
        raise ValueError('Selecciona entre uno y tres escenarios.')
    catalog = {r['stadium_id']: r for r in read_csv(output / 'estadios.csv')}
    stadium_context = 'stadium_id' in meta['tasks']['environment_run_value']['features']
    scenarios = []
    for i, value in enumerate(selected):
        context = {'altitude_category': value, 'stadium': value}
        if stadium_context:
            if value not in catalog:
                raise ValueError('Estadio desconocido.')
            context = {'stadium_id': value, 'stadium': catalog[value]['estadio'], 'altitude_category': catalog[value]['altitude_category']}
        elif value not in ('No Altitude', 'Medium Altitude', 'Extreme Altitude'):
            raise ValueError('Altitud desconocida.')
        scenarios.append({**row, **context, 'PitchUID': f'react-{i}'})
    import pandas as pd
    from precision_model import infer_dashboard
    with INFERENCE_LOCK:
        bundle = load_bundle(str(output), (output / 'bundle.json').stat().st_mtime_ns)
        result = infer_dashboard(pd.DataFrame(scenarios), bundle, output)
    records = json.loads(result.to_json(orient='records'))
    for record, scenario in zip(records, scenarios):
        record['stadium'] = scenario['stadium']
    outside = [key for key in profile['median'] if profile.get('p01', {}).get(key) is not None
               and profile.get('p99', {}).get(key) is not None and not profile['p01'][key] <= row[key] <= profile['p99'][key]]
    return {'results': records, 'outside': outside, 'reference': meta.get('reference', {})}


class Handler(BaseHTTPRequestHandler):
    def send(self, value, status=200, content_type='application/json; charset=utf-8', filename=None):
        data = json.dumps(value, allow_nan=False).encode() if content_type.startswith('application/json') else value
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        if filename:
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def file(self, path, download=False):
        if not path.is_file() or is_lfs_pointer(path):
            self.send({'error': 'Archivo no disponible.'}, 404)
            return
        mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        if mime == 'application/json':
            self.send(read_json(path), filename=path.name if download else None)
        else:
            self.send(path.read_bytes(), content_type=mime, filename=path.name if download else None)

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        run = query.get('run', [None])[0]
        try:
            if url.path == '/api/bootstrap':
                self.send(bootstrap())
            elif url.path == '/api/table':
                path = table_path(query.get('name', [''])[0], run)
                if 'download' in query:
                    self.file(path, True)
                else:
                    self.send({'rows': read_csv(path), 'source': str(path.relative_to(ROOT))})
            elif url.path == '/api/evidence':
                output = choose_run(run)
                self.send({mode: read_json(path, []) for mode, path in {
                    'season': (output / 'metricas.json') if output else REPORT / 'metricas.json',
                    'pitcher': REPORT / 'pitcher/metricas.json', 'park': REPORT / 'park/metricas.json',
                    'v8': ROOT / 'stuff_plus_output_v8/metricas.json'}.items()})
            elif url.path.startswith('/api/document/'):
                key = url.path.rsplit('/', 1)[-1]
                if key not in DOCUMENTS:
                    raise ValueError('Documento desconocido.')
                self.file(DOCUMENTS[key][1], 'download' in query)
            elif url.path.startswith('/assets/') or url.path.startswith('/imgs/'):
                path = (ROOT / url.path.lstrip('/')).resolve()
                if not any(path.is_relative_to(ROOT / folder) for folder in ('assets', 'imgs')):
                    raise ValueError('Ruta inválida.')
                self.file(path)
            else:
                dist = ROOT / 'frontend/dist'
                path = (dist / url.path.lstrip('/')).resolve()
                if not path.is_relative_to(dist):
                    raise ValueError('Ruta inválida.')
                self.file(path if path.is_file() else dist / 'index.html')
        except (BrokenPipeError, ConnectionResetError):
            pass  # Browsers cancel requests on navigation and React effect cleanup.
        except ValueError as error:
            self.send({'error': str(error)}, 400)
        except Exception:
            self.log_error('Failed to serve %s', url.path)
            self.send({'error': 'No se pudo leer el recurso.'}, 500)

    def do_POST(self):
        if urlparse(self.path).path != '/api/simulate':
            self.send({'error': 'Ruta desconocida.'}, 404)
            return
        # This local service deliberately exposes no cross-origin mutation API.
        origin = self.headers.get('Origin')
        if origin and urlparse(origin).netloc != self.headers.get('Host'):
            self.send({'error': 'Origen no permitido.'}, 403)
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 65536:
                raise ValueError('Solicitud inválida.')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('Solicitud inválida.')
            self.send(simulate(payload))
        except (BrokenPipeError, ConnectionResetError):
            pass
        except (ValueError, TypeError, KeyError) as error:
            self.send({'error': str(error)}, 400)
        except ImportError:
            self.send({'error': 'Instala las dependencias Python de requirements/requirements-entrega.txt para ejecutar los modelos.'}, 503)
        except Exception:
            import traceback
            traceback.print_exc()
            self.send({'error': 'No se pudo evaluar el lanzamiento. Revisa los modelos y el registro del servidor.'}, 500)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    print(f'Diablos API: http://{args.host}:{args.port}', flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
