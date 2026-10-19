"""Exercise installed extension resolution and collision-safe ELF staging.

Synthetic ELF headers below are inventory fixtures, never executable evidence.
Real application import results are collected separately on the OHOS device.
"""
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.native_loader import PackagedExtensionFinder, install, validate_map, validate_namespaces

spec = importlib.util.spec_from_file_location('stage_native_runtime', ROOT / 'scripts/ohos/Stage-NativeRuntime.py')
staging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(staging)
gate_spec = importlib.util.spec_from_file_location('gsas_native_gate', ROOT / 'scripts/payload/check_gsas_native.py')
gate = importlib.util.module_from_spec(gate_spec)
gate_spec.loader.exec_module(gate)


def elf(machine=183):
    header = bytearray(64)
    header[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<HH', header, 16, 3, machine)
    return bytes(header)


class NativeRuntimeLayoutTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = self.root / 'input'
        self.input.mkdir()
        self.components = [{'id': 'cpython', 'payloadPrefixes': ['libs', 'runtime/lib']},
                           {'id': 'scipy', 'payloadPrefixes': ['runtime/lib/python3.12/site-packages/scipy']},
                           {'id': 'bridge', 'payloadPrefixes': ['runtime/bridge']}]

    def write(self, rel, data):
        path = self.input / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_colliding_python_basenames_get_distinct_installed_targets(self):
        rels = ['runtime/lib/python3.12/site-packages/scipy/optimize/_zeros.cpython-312-aarch64-linux-ohos.so',
                'runtime/lib/python3.12/site-packages/scipy/optimize/cython_optimize/_zeros.cpython-312-aarch64-linux-ohos.so']
        for rel in rels:
            self.write(rel, elf())
        self.write('runtime/lib/libffi.so.8', elf())
        out = self.root / 'output'
        report = staging.stage(self.input, out, self.components, ROOT / 'bridge/native_loader.py')
        mapping = json.loads((out / 'runtime/bridge/native-module-map.json').read_text())
        modules = validate_map(mapping)
        self.assertEqual(set(modules), {'scipy.optimize._zeros', 'scipy.optimize.cython_optimize._zeros'})
        self.assertEqual(len(set(modules.values())), 2)
        self.assertEqual((out / 'libs/libffi.so.8').read_bytes(), elf())
        for row in report['libraries']:
            self.assertEqual((out / row['target']).read_bytes(), (self.input / row['source']).read_bytes())
            self.assertEqual(row['component'], 'scipy' if '/scipy/' in row['source'] else 'cpython')
        finder = PackagedExtensionFinder(out / 'libs', modules)
        self.assertEqual(Path(finder.find_spec('scipy.optimize._zeros').origin).parent, out / 'libs')
        self.assertIsNone(finder.find_spec('unmapped.module'))

    def test_empty_namespace_survives_archive_that_drops_directories(self):
        self.write('runtime/lib/python3.12/site-packages/scipy/native_only/x.cpython-312-aarch64-linux-ohos.so', elf())
        out = self.root / 'output'
        staging.stage(self.input, out, self.components, ROOT / 'bridge/native_loader.py')
        document = json.loads((out / 'runtime/bridge/native-module-map.json').read_text())
        modules = validate_map(document)
        namespaces = validate_namespaces(document, modules)
        self.assertIn('scipy.native_only', namespaces)
        # No namespace directory is needed in the installed HAP.
        finder = PackagedExtensionFinder(out / 'libs', modules, namespaces)
        spec = finder.find_spec('scipy.native_only', ['/nonexistent/runtime/scipy'])
        self.assertIsNone(spec.loader)
        self.assertEqual(spec.submodule_search_locations, [])
        self.assertIsNone(finder.find_spec('unrelated.namespace', []))
        with self.assertRaises(ImportError):
            validate_namespaces({'namespacePackages': ['unrelated']}, modules)

    def test_restage_preserves_existing_imports_and_merges_new_extensions(self):
        self.write('libs/old.so', elf())
        self.write('runtime/bridge/native-module-map.json', json.dumps(
            {'schemaVersion': 1, 'modules': {'numpy.old': 'old.so'}}).encode())
        self.write('runtime/lib/python3.12/site-packages/scipy/new.cpython-312-aarch64-linux-ohos.so', elf())
        out = self.root / 'output'
        staging.stage(self.input, out, self.components, ROOT / 'bridge/native_loader.py')
        mapping = validate_map(json.loads((out / 'runtime/bridge/native-module-map.json').read_text()))
        self.assertEqual(set(mapping), {'numpy.old', 'scipy.new'})
        self.assertEqual(mapping['numpy.old'], 'old.so')

    def test_restage_rejects_dangling_prior_import_before_copy(self):
        self.write('libs/other.so', elf())
        self.write('runtime/bridge/native-module-map.json', json.dumps(
            {'schemaVersion': 1, 'modules': {'numpy.old': 'missing.so'}}).encode())
        out = self.root / 'output'
        with self.assertRaisesRegex(ValueError, 'missing or non-ELF'):
            staging.stage(self.input, out, self.components, ROOT / 'bridge/native_loader.py')
        self.assertFalse(out.exists())

    def test_dependency_basename_collisions_are_rejected_before_copy(self):
        self.write('runtime/lib/one/libhelper.so', elf())
        self.write('runtime/lib/two/libhelper.so', elf())
        out = self.root / 'output'
        with self.assertRaisesRegex(ValueError, 'colliding dependency'):
            staging.stage(self.input, out, self.components, ROOT / 'bridge/native_loader.py')
        self.assertFalse(out.exists())

    def test_wrong_architecture_is_rejected_before_copy(self):
        self.write('libs/wrong.so', elf(machine=62))
        out = self.root / 'output'
        with self.assertRaisesRegex(ValueError, 'AArch64'):
            staging.stage(self.input, out, self.components, ROOT / 'bridge/native_loader.py')
        self.assertFalse(out.exists())

    def test_map_rejects_path_escape_and_case_collisions(self):
        for modules in [{'numpy._core.x': '../escape.so'}, {'numpy..x': 'x.so'},
                        {'one.x': 'same.so', 'two.x': 'SAME.so'}]:
            with self.subTest(modules=modules), self.assertRaises(ImportError):
                validate_map({'schemaVersion': 1, 'modules': modules})

    def test_install_is_idempotent_and_requires_every_declared_library(self):
        runtime, native = self.root / 'runtime', self.root / 'installed'
        (runtime / 'bridge').mkdir(parents=True)
        native.mkdir()
        index = runtime / 'bridge/native-module-map.json'
        index.write_text(json.dumps({'schemaVersion': 1, 'modules': {'example.extension': 'extension.so'}}))
        with self.assertRaisesRegex(ImportError, 'missing'):
            install(str(runtime), str(native))
        (native / 'extension.so').write_bytes(elf())
        old_meta = list(sys.meta_path)
        self.addCleanup(lambda: setattr(sys, 'meta_path', old_meta))
        self.assertEqual(install(str(runtime), str(native)), 1)
        finder = sys.meta_path[0]
        self.assertEqual(install(str(runtime), str(native)), 1)
        self.assertIs(sys.meta_path[0], finder)
        self.assertEqual(len(sys.meta_path), len(old_meta) + 1)

    def test_unmapped_host_runtime_retains_legacy_behavior(self):
        old_meta = list(sys.meta_path)
        self.assertEqual(install(str(self.root / 'no-map'), ''), 0)
        self.assertEqual(sys.meta_path, old_meta)

    def test_native_gate_checks_mapped_files_and_missing_targets(self):
        package = self.input / 'runtime/lib/python3.12/site-packages/GSASII'
        package.mkdir(parents=True)
        mapping = {}
        for name in gate.REQUIRED:
            filename = name + '.so'
            self.write('libs/' + filename, elf())
            mapping['GSASII.' + name] = filename
        self.write('runtime/bridge/native-module-map.json', json.dumps(
            {'schemaVersion': 1, 'modules': mapping}).encode())
        _, failures, _, found = gate.check(self.input)
        self.assertEqual(failures, [])
        self.assertEqual(set(found), set(gate.REQUIRED))
        (self.input / 'libs/pyspg.so').unlink()
        _, failures, _, found = gate.check(self.input)
        self.assertTrue(failures)
        self.assertNotIn('pyspg', found)

    def test_native_gate_rejects_map_escape_and_forbidden_module(self):
        (self.input / 'runtime/lib/python3.12/site-packages/GSASII').mkdir(parents=True)
        index = self.write('runtime/bridge/native-module-map.json', b'{}')
        for mapping in [{'GSASII.pyspg': '../escape.so'}, {'GSASII.pydiffax': 'renamed.so'}]:
            index.write_text(json.dumps({'schemaVersion': 1, 'modules': mapping}))
            _, failures, _, _ = gate.check(self.input)
            self.assertTrue(any('invalid native module map' in reason or 'forbidden' in reason
                                for reason in failures))


if __name__ == '__main__':
    unittest.main()
