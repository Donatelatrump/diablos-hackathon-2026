import sys
sys.path.insert(0, r'C:\Users\Cesar Donnet\Desktop\Diablos - Hackathon 2026\entrega_v8\codigo')
import unittest
import test_entrega_v8
suite = unittest.TestLoader().loadTestsFromModule(test_entrega_v8)
runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)
print('Failures:', len(result.failures))
print('Errors:', len(result.errors))