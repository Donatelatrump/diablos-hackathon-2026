"""Verify the web adapter's validation, model delegation and local report access."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import dashboard_api as api


class DashboardApiTests(unittest.TestCase):
    def test_unknown_run_and_table_are_rejected(self):
        with self.assertRaises(ValueError):
            api.choose_run('../../etc')
        with self.assertRaises(ValueError):
            api.table_path('../../etc/passwd')

    def test_csv_lfs_pointer_is_not_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'data.csv'
            path.write_text('version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 12\n')
            self.assertEqual(api.read_csv(path), [])

    def test_reports_available_without_ml_imports(self):
        self.assertTrue(api.read_csv(api.table_path('integral')))
        self.assertTrue(api.read_json(api.REPORT / 'metricas.json'))

    def test_missing_models_fail_explicitly(self):
        with patch.object(api, 'choose_run', return_value=None):
            with self.assertRaisesRegex(ValueError, 'No hay un modelo'):
                api.simulate({})

    def test_preserves_physics_and_delegates_to_existing_inference(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            profile = {'type': 'Four-Seam', 'hand': 'Right', 'median': {'RelSpeed': 90, 'HorzBreak': 8, 'InducedVertBreak': 15}, 'p01': {'RelSpeed': 80}, 'p99': {'RelSpeed': 100}}
            meta = {'input_profiles': [profile], 'profile': {'fastballs': []}, 'tasks': {'environment_run_value': {'features': ['stadium_id']}}, 'reference': {}}
            (output / 'bundle.json').write_text(json.dumps(meta))
            (output / 'estadios.csv').write_text('stadium_id,estadio,altitude_category\na,Estadio A,Extreme Altitude\nb,Estadio B,No Altitude\n')
            captured = []
            def infer(frame, bundle, path):
                captured.extend(frame)
                return SimpleNamespace(to_json=lambda **kwargs: json.dumps([{'pitching_plus': 101}, {'pitching_plus': 101}]))
            payload = {'pitch': 'Four-Seam', 'hand': 'Right', 'measurements': {'RelSpeed': 105}, 'stadiums': ['a', 'b']}
            with patch.object(api, 'choose_run', return_value=output), patch.object(api, 'load_bundle', return_value=(meta, {})), patch.dict(sys.modules, {'pandas': SimpleNamespace(DataFrame=lambda rows: rows), 'precision_model': SimpleNamespace(infer_dashboard=infer)}):
                result = api.simulate(payload)
                self.assertEqual([row['RelSpeed'] for row in captured], [105, 105])
                self.assertEqual([row['altitude_category'] for row in captured], ['Extreme Altitude', 'No Altitude'])
                self.assertEqual(result['outside'], ['RelSpeed'])
                self.assertEqual([row['stadium'] for row in result['results']], ['Estadio A', 'Estadio B'])
                for invalid in [{'RelSpeed': float('nan')}, {'RelSpeed': -1}, {'Balls': 4}, {'unexpected': 1}]:
                    with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                        api.simulate({**payload, 'measurements': invalid})
                with self.assertRaises(ValueError):
                    api.simulate({**payload, 'stadiums': ['unknown']})


if __name__ == '__main__':
    unittest.main()
