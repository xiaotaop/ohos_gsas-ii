import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('scientific_audit', ROOT / 'scripts/Audit-ScientificRuntime.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class ScientificAuditTest(unittest.TestCase):
    def test_only_defined_functions_and_file_symbols_establish_observations(self):
        symbols = ('1: 0000 0 FUNC GLOBAL DEFAULT UND _gfortran_error\n'
                   '2: 0100 8 FUNC GLOBAL DEFAULT 9 _FortranAioBeginClose\n'
                   '3: 0100 8 OBJECT GLOBAL DEFAULT 9 _FortranAobject\n'
                   '4: 0000 0 FILE LOCAL DEFAULT ABS dgeev.c\n'
                   '5: 0000 0 FILE LOCAL DEFAULT ABS ISO_Fortran_binding.cpp\n'
                   '6: 0100 8 FUNC GLOBAL DEFAULT 9 _FortranAioBeginClose\n')
        result = audit.symbol_observations(symbols, 'Homebrew flang version 22.1.8')
        self.assertEqual(result['definedLLVMFortranFunctions'], ['_FortranAioBeginClose'])
        self.assertEqual(result['definedGNUFortranFunctions'], [])
        self.assertEqual(result['compilerFlangVersions'], ['22.1.8'])
        self.assertEqual(result['sourceSuffixCounts'], {'.c': 1, '.cpp': 1})
        self.assertEqual(result['lapackCSourceExamples'], ['dgeev.c'])

    def test_empty_symbols_do_not_prove_runtime_absence_or_a_version(self):
        result = audit.symbol_observations('', 'Linker: LLD 15.0.4')
        self.assertEqual(result['compilerFlangVersions'], [])
        self.assertEqual(result['sourceFileCount'], 0)
        self.assertNotIn('runtimeAbsent', result)


if __name__ == '__main__':
    unittest.main()
