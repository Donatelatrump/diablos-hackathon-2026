"""Aplica las correspondencias auditadas a un CSV, XLSX o Parquet antiguo."""
import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
CAMPOS = [
    'estado_clasificacion', 'estadio', 'stadium_id', 'mlb_game_pk',
    'mlb_venue_id', 'fecha_partido', 'equipo_local', 'equipo_visitante',
    'fuente_estadio', 'altitud_estadio_m', 'fuente_altitud', 'referencia_harp_helu',
]


def actualizar(original, juegos):
    claves = ['year', 'game_anon_id']
    for clave in claves:
        if clave not in original:
            raise ValueError(f'Falta la columna obligatoria {clave}')
    colisiones = set(CAMPOS) & set(original.columns)
    if colisiones:
        raise ValueError(f'El archivo ya contiene campos de estadio: {sorted(colisiones)}')
    # Normalizar solo las llaves auxiliares; conservar los valores originales.
    def llaves(frame):
        return pd.DataFrame({
            'year': pd.to_numeric(frame.year, errors='raise').astype('Int64'),
            'game_anon_id': frame.game_anon_id.astype('string').str.strip(),
        }).reset_index(drop=True)
    mapa = llaves(juegos)
    mapa[CAMPOS] = juegos[CAMPOS].reset_index(drop=True)
    if mapa[claves].isna().any().any() or mapa.duplicated(claves).any():
        raise ValueError('El mapeo contiene llaves vacias o duplicadas')
    resultado = llaves(original).merge(mapa, on=claves, how='left',
                                       sort=False, validate='many_to_one')
    resultado['estado_clasificacion'] = resultado.estado_clasificacion.fillna('sin_correspondencia')
    salida = original.reset_index(drop=True).copy()
    salida[CAMPOS] = resultado[CAMPOS]
    return salida


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('entrada', type=Path)
    parser.add_argument('--salida', type=Path, required=True)
    parser.add_argument('--hoja', default='0', help='Nombre de hoja XLSX; por defecto la primera')
    parser.add_argument('--separador', default=',', help='Separador del CSV de entrada y salida')
    parser.add_argument('--mapeo', type=Path, default=ROOT / 'clasificacion_estadios/juegos_clasificados.csv')
    args = parser.parse_args()
    if args.salida.exists() or args.entrada.resolve() == args.salida.resolve():
        parser.error('La salida debe ser un archivo nuevo; no se sobrescriben archivos')
    extension = args.entrada.suffix.lower()
    if extension == '.csv':
        original = pd.read_csv(args.entrada, sep=args.separador, low_memory=False)
    elif extension == '.xlsx':
        hoja = int(args.hoja) if args.hoja.isdigit() else args.hoja
        original = pd.read_excel(args.entrada, sheet_name=hoja)
    elif extension == '.parquet':
        original = pd.read_parquet(args.entrada)
    else:
        parser.error('Entrada admitida: .csv, .xlsx o .parquet')
    salida = actualizar(original, pd.read_csv(args.mapeo))
    extension = args.salida.suffix.lower()
    if extension == '.csv':
        salida.to_csv(args.salida, index=False, encoding='utf-8-sig', sep=args.separador)
    elif extension == '.parquet':
        salida.to_parquet(args.salida, index=False)
    elif extension == '.xlsx':
        if len(salida) > 1048575:
            parser.error('Demasiadas filas para Excel; use CSV o Parquet')
        with pd.ExcelWriter(args.salida, engine='xlsxwriter', engine_kwargs={
            'options': {'strings_to_formulas': False, 'strings_to_urls': False, 'use_zip64': True}
        }) as writer:
            salida.to_excel(writer, sheet_name='Lanzamientos', index=False)
    else:
        parser.error('Salida admitida: .csv, .xlsx o .parquet')
    print(f'Guardado: {args.salida} | {len(salida):,} filas | '
          f'{salida.estadio.notna().sum():,} con estadio')


if __name__ == '__main__':
    main()
