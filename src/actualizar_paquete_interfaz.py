"""Crea una revisión del ZIP existente sin reentrenar ni incluir el dataset original."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'ENTREGA_ESTADIOS_ACTUALIZADA.zip'
TARGET = ROOT / 'ENTREGA_ESTADIOS_REVISION_USABILIDAD.zip'
UPDATES = [
    'app.py',
    'src/dashboard_stuff_plus.py', 'src/dashboard_stuff_plus_v9.py', 'src/dashboard_perfiles_estadios.py',
    'tests/__init__.py', 'tests/test_dashboard_navigation_helpers.py',
    'tests/test_dashboard_estadios_v9.py', 'tests/test_dashboard_stuff_plus_v9.py',
    'src/actualizar_paquete_interfaz.py',
    'reports/v9_estadios/MEJORAS_2026-10-28.md',
    'reports/v9_estadios/REVISION_INTERFAZ_2026-10-28.json',
]


def main():
    with ZipFile(BASE) as archive:
        if archive.testzip() is not None:
            raise ValueError('El ZIP base no pasa la comprobación CRC')
        manifest = json.loads(archive.read('MANIFIESTO.json'))
        if set(archive.namelist()) != set(manifest) | {'MANIFIESTO.json'}:
            raise ValueError('Inventario del ZIP base distinto de su manifiesto')
        payload = {name: archive.read(name) for name in manifest}
    for name, digest in manifest.items():
        if hashlib.sha256(payload[name]).hexdigest() != digest:
            raise ValueError(f'Hash base incorrecto: {name}')
    for name in UPDATES:
        payload[name] = (ROOT / name).read_bytes()
    for folder in ['src', 'assets', 'imgs']:
        for path in (ROOT / folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in {'.pyc', '.pyo'}:
                payload[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    payload['README_PRIMERO.md'] = (
        '# Entrega revisada: comparación en Harp\n\n'
        'Con Python 3.12 instalado, abrir ABRIR_DASHBOARD.bat. La primera apertura requiere '
        'internet para instalar dependencias. Mantener su ventana abierta durante el uso. '
        'No se necesita el dataset original para inferencia.\n\n'
        'El inicio abre Comparar en Harp. Elegir tipo, mano y estadio de referencia; revisar '
        'mediciones y contexto; pulsar Comparar en Harp. Las entradas iniciales son un ejemplo '
        'con medianas, no un lanzamiento observado. Después de editar, volver a pulsar el botón.\n\n'
        'Revisar un pitcher conserva una selección para ficha, mapa y arsenal. Perfiles para '
        'scouting compara grupos; permite trasladar tipo y mano al simulador. Evidencia y '
        'entrega reúne validaciones y pendientes.\n\n'
        'Consultar reports/v9_estadios/MEJORAS_2026-10-28.md para el recorrido actualizado. '
        'Esta nota sustituye las instrucciones de navegación del PDF técnico de nueve páginas. '
        'Sus definiciones y resultados de modelos se conservan.\n\n'
        'No hay mejora incremental de carreras por estadio confirmada ni un arsenal óptimo '
        'demostrado para Harp. Las probabilidades y el índice complementario pueden cambiar; '
        'el contraste mantiene fija la física y no prueba efectos causales. 2026 es reutilizado.\n\n'
        'Uso exclusivo de la competencia. Completar nombres y correos del equipo y confirmar '
        'envío por el canal autorizado. Este script no envía ni publica el paquete.\n'
    ).encode('utf-8')
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(payload.items())}
    payload['MANIFIESTO.json'] = json.dumps(manifest, indent=2).encode('utf-8')
    with ZipFile(TARGET, 'w', ZIP_DEFLATED) as archive:
        for name, data in sorted(payload.items()):
            archive.writestr(name, data)
    with ZipFile(TARGET) as archive:
        assert archive.testzip() is None
        for name, digest in manifest.items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest, name
    print(json.dumps({'package': TARGET.name, 'files': len(manifest),
                      'hashes_verified': True, 'base_preserved': BASE.name}, indent=2))


if __name__ == '__main__':
    main()
