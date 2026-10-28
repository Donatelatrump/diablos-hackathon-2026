import argparse
import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

import entrenar_stuff_plus_v9 as v9
from test_stuff_plus_v9 import synthetic_data


class StadiumModelTests(unittest.TestCase):
    def test_stadium_pipeline_reload_and_physical_invariance(self):
        frame = synthetic_data()
        frame['stadium_id'] = np.where(frame.altitude_category.eq('Extreme Altitude'), 'mexico_ahh', 'other')
        frame['estadio'] = frame.stadium_id
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.parquet'
            v9.v5.write_parquet(frame, source)
            args = argparse.Namespace(parquet=source, salida=root / 'run', test_year=2026,
                holdout='season', grupo_excluido=None, iteraciones=30, hilos=2,
                tasks=v9.CORE_TASKS + ['whiff'], incremental_gate=True, stadium_context=True)
            with contextlib.redirect_stdout(io.StringIO()):
                v9.train(args)
                v9.evaluate(args)
            bundle = v9.load_bundle(args.salida)
            self.assertIn('stadium_id', bundle[0]['tasks']['environment_run_value']['features'])
            self.assertNotIn('stadium_id', bundle[0]['tasks']['stuff_run_value']['features'])
            rows = frame.query('year == 2026').head(6)[v9.RAW_REQUIRED + ['stadium_id']].copy()
            before = v9.infer(rows, bundle)
            rows['stadium_id'] = 'unseen_park'
            after = v9.infer(rows, bundle)
            np.testing.assert_array_equal(before.stuff_plus, after.stuff_plus)
            self.assertTrue(np.isfinite(after.pitching_plus).all())
            with self.assertRaisesRegex(ValueError, 'stadium_id'):
                v9.infer(rows.drop(columns='stadium_id'), bundle)
            subprocess.run([sys.executable, str(Path(__file__).with_name('reportar_estadios_v9.py')),
                '--parquet', str(source), '--salida', str(args.salida)],
                check=True, capture_output=True, text=True)
            self.assertTrue((args.salida / 'HARP_HELU.md').exists())
            self.assertTrue((args.salida / 'escenarios_harp_helu_2026.parquet').exists())


if __name__ == '__main__':
    unittest.main()
