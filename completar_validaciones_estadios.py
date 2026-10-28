"""Ejecuta auditorias independientes del modelo por estadios y conserva cada log."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def main():
    common = [sys.executable, '-u', 'entrenar_stuff_plus_v9.py', '--parquet',
              'stuff_model_df_con_estadios.parquet', '--stadium-context',
              '--incremental-gate', '--iteraciones', '400', '--hilos', '6']
    for holdout, extra in [('pitcher', []), ('park', ['--grupo-excluido', 'Estadio Alfredo Harp Helu'])]:
        output = ROOT / f'stuff_plus_output_v9_estadios_{holdout}'
        if (output / 'metricas.json').exists():
            continue
        if output.exists() and any(output.iterdir()):
            raise RuntimeError(f'Ejecucion incompleta: revisar {output} antes de repetir')
        with (ROOT / f'validacion_estadios_{holdout}.log').open('w', encoding='utf-8') as log:
            subprocess.run(common + ['--holdout', holdout, '--salida', str(output)] + extra,
                           cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)

if __name__ == '__main__':
    main()
