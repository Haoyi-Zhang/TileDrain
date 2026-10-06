"""The pure finite checks must not require the POSIX runner's resource module."""
import builtins
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(SRC))


class PortableControlTests(unittest.TestCase):
    def test_finite_functions_import_and_controls_run_without_resource(self):
        original_import = builtins.__import__

        def without_resource(name, *args, **kwargs):
            if name == 'resource':
                raise ModuleNotFoundError('resource deliberately unavailable')
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=without_resource):
            # Load fresh module objects so a prior import cannot hide the fault.
            for name in ('mutations', 'experiment', 'capacity_audit', 'weighted_exhaustive'):
                spec = importlib.util.spec_from_file_location('portable_' + name, SRC / (name + '.py'))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if name == 'mutations':
                    self.assertEqual(len(module.run_controls()), 31)


if __name__ == '__main__':
    unittest.main()
