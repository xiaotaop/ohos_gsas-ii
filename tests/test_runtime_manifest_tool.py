"""Synthetic-payload checks for the manifest generator: §2 layout mapping,
deterministic device manifest, reuse of member C's authoritative gates, and
the rejections a real B payload must never smuggle past them."""
import importlib.util
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import release_tools as rt

_spec = importlib.util.spec_from_file_location(
    'write_runtime_manifest', Path(__file__).resolve().parents[1] / 'scripts/Write-RuntimeManifest.py')
wrm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wrm)


def elf(machine=183):
    data = bytearray(64)
    data[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<HH', data, 16, 3, machine)
    return bytes(data)


def components_fixture():
    """Synthetic, non-executable records: never scientific data or approval evidence."""
    return [
        {'id': 'cpython', 'version': '3.12.9', 'license': 'LicenseRef-TestOnly',
         'sourceUrl': 'https://example.invalid/cpython', 'sourceCodeUrl': 'https://example.invalid/cpython-src',
         'dependsOn': [], 'distributionReview': 'pending',
         'payloadPrefixes': ['libs/libpython3.12.so', 'runtime/lib/python3.12']},
        {'id': 'numpy', 'version': '2.2.6', 'license': 'LicenseRef-TestOnly',
         'sourceUrl': 'https://example.invalid/numpy', 'sourceCodeUrl': 'https://example.invalid/numpy-src',
         'dependsOn': ['cpython'], 'distributionReview': 'pending',
         'payloadPrefixes': ['runtime/lib/python3.12/site-packages/numpy']},
        {'id': 'scipy', 'version': '1.16.3', 'license': 'LicenseRef-TestOnly',
         'sourceUrl': 'https://example.invalid/scipy', 'sourceCodeUrl': 'https://example.invalid/scipy-src',
         'dependsOn': ['numpy'], 'distributionReview': 'pending',
         'payloadPrefixes': ['runtime/lib/python3.12/site-packages/scipy']},
        {'id': 'pycifrw', 'version': '5.0.1', 'license': 'LicenseRef-TestOnly',
         'sourceUrl': 'https://example.invalid/pycifrw', 'sourceCodeUrl': 'https://example.invalid/pycifrw-src',
         'dependsOn': ['cpython'], 'distributionReview': 'pending',
         'payloadPrefixes': ['runtime/lib/python3.12/site-packages/pycifrw']},
        {'id': 'gsas-ii', 'version': '2.0.0', 'upstreamCommit': rt.GSAS_COMMIT, 'license': 'LicenseRef-TestOnly',
         'sourceUrl': 'https://example.invalid/gsas-ii', 'sourceCodeUrl': 'https://example.invalid/gsas-ii-src',
         'dependsOn': ['numpy', 'scipy', 'pycifrw'], 'distributionReview': 'pending',
         'payloadPrefixes': ['runtime/GSASII.py', 'runtime/bridge',
                             'runtime/lib/python3.12/site-packages/GSASIIIPR']},
    ]


def write(root, rel, data):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def payload_fixture(root):
    write(root, 'libs/libpython3.12.so', elf())
    write(root, 'runtime/lib/python3.12/encodings/__init__.py', b'# stub only\n')
    for cid in ('numpy', 'scipy', 'pycifrw'):
        write(root, f'runtime/lib/python3.12/site-packages/{cid}/__init__.py', b'# synthetic test only\n')
    write(root, 'runtime/GSASII.py', b'# synthetic test only\n')
    write(root, 'runtime/bridge/__init__.py', b'# synthetic test only\n')
    for cid in rt.VERSIONS:
        write(root, f'licenses/{cid}/LICENSE', b'test-only license\n')


class RuntimeManifestToolTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.payload = self.root / 'payload'
        payload_fixture(self.payload)
        self.components_path = self.root / 'components.json'
        self.components_path.write_text(json.dumps(components_fixture()), encoding='utf-8')
        self.output = self.root / 'runtime-manifest.json'

    def tearDown(self):
        self.temp.cleanup()

    def generate(self, runtime_id='test-v1'):
        return wrm.generate(self.payload, self.components_path, runtime_id, self.output)

    def test_manifest_passes_c_gates_and_prepares(self):
        manifest = self.generate()
        self.assertEqual(rt.validate_manifest(rt.read_json(self.output)), manifest)
        # Prepare-Runtime re-hashes every source from the same payload.
        prepared = rt.prepare_runtime(self.output, self.payload, self.root / 'prepared')
        self.assertEqual(prepared['runtimeId'], 'test-v1')

    def test_device_manifest_matches_installer_expectations(self):
        self.generate()
        document = json.loads((self.payload / wrm.DEVICE_MANIFEST).read_text(encoding='utf-8'))
        self.assertEqual(document['schemaVersion'], 1)
        self.assertEqual(document['runtimeId'], 'test-v1')
        paths = [entry['path'] for entry in document['files']]
        self.assertEqual(paths, sorted(paths))
        self.assertNotIn('manifest.json', paths)
        self.assertIn('lib/python3.12/encodings/__init__.py', paths)
        for entry in document['files']:
            actual = (self.payload / 'runtime' / entry['path']).read_bytes()
            self.assertEqual(entry['sha256'], rt.digest(actual))
            self.assertEqual(entry['size'], len(actual))
            self.assertEqual(len(entry['sha256']), 64)
            self.assertEqual(entry['sha256'], entry['sha256'].lower())

    def test_generation_is_deterministic(self):
        self.generate()
        first_manifest = self.output.read_bytes()
        first_device = (self.payload / wrm.DEVICE_MANIFEST).read_bytes()
        self.generate()
        self.assertEqual(self.output.read_bytes(), first_manifest)
        self.assertEqual((self.payload / wrm.DEVICE_MANIFEST).read_bytes(), first_device)

    def test_unmapped_payload_path_rejected(self):
        write(self.payload, 'runtime/tools/helper.py', b'x = 1\n')
        with self.assertRaises(rt.ReleaseError):
            self.generate()

    def test_license_directory_outside_layout_rejected(self):
        write(self.payload, 'licenses/cpython/deep/LICENSE', b'x\n')
        with self.assertRaises(rt.ReleaseError):
            self.generate()

    def test_license_for_unknown_component_rejected(self):
        write(self.payload, 'licenses/ghostpkg/LICENSE', b'x\n')
        with self.assertRaises(rt.ReleaseError):
            self.generate()

    def test_bytecode_and_archives_rejected(self):
        for rel in ('runtime/lib/python3.12/encodings/loop.pyc', 'runtime/bundle.zip',
                    'runtime/lib/python3.12/__pycache__/x.py'):
            write(self.payload, rel, b'not expanded\n')
            with self.subTest(rel=rel), self.assertRaises(rt.ReleaseError):
                self.generate()
            (self.payload / rel).unlink()

    def test_excluded_components_rejected(self):
        write(self.payload, 'runtime/lib/python3.12/site-packages/GSASIIIPR/pydiffax.py', b'# banned\n')
        with self.assertRaises(rt.ReleaseError):
            self.generate()

    def test_foreign_arch_rejected(self):
        write(self.payload, 'libs/libpython3.12.so', elf(machine=62))
        with self.assertRaises(rt.ReleaseError):
            self.generate()

    def test_missing_license_record_rejected(self):
        (self.payload / 'licenses/cpython/LICENSE').unlink()
        with self.assertRaises(rt.ReleaseError):
            self.generate()

    def test_component_without_runtime_files_rejected(self):
        import shutil as _shutil
        _shutil.rmtree(self.payload / 'runtime/lib/python3.12/site-packages/numpy')
        with self.assertRaises(rt.ReleaseError):
            self.generate()

    def test_cli_round_trip(self):
        script = Path(__file__).resolve().parents[1] / 'scripts' / 'Write-RuntimeManifest.py'
        result = subprocess.run([sys.executable, str(script), '--payload', str(self.payload),
                                 '--components', str(self.components_path),
                                 '--runtime-id', 'test-v1', '--output', str(self.output)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary['runtimeId'], 'test-v1')
        self.assertTrue(rt.read_json(self.output)['status'] == 'ready')


if __name__ == '__main__':
    unittest.main()
