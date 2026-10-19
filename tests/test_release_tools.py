"""Exercise corruption, unsafe payloads, incomplete delivery and package provenance."""
import copy
import importlib.util
import json
import os
import struct
import sys
import tempfile
import unittest
import warnings
import zipfile
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
from subprocess import CompletedProcess

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import release_tools as rt


def elf(machine=183):
    data = bytearray(64)
    data[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<HH', data, 16, 3, machine)
    return bytes(data)


def payload_fixture(root):
    """Synthetic, non-executable payload: never a scientific runtime or compliance evidence."""
    root.mkdir()
    m = {'schemaVersion': 1, 'status': 'ready', 'runtimeId': 'test-v1',
         'target': 'ohos-aarch64', 'components': [], 'files': []}
    for cid, version in rt.VERSIONS.items():
        license_target = f'resources/rawfile/licenses/runtime/{cid}/LICENSE'
        c = {'id': cid, 'version': version, 'license': 'LicenseRef-TestOnly',
             'sourceUrl': 'https://example.invalid/test', 'sourceCodeUrl': 'https://example.invalid/source',
             'licenseFiles': [license_target], 'dependsOn': [],
             'distributionReview': 'approved', 'reviewReference': 'test-only; not an approval'}
        if cid == 'gsas-ii':
            c['upstreamCommit'] = rt.GSAS_COMMIT
        m['components'].append(c)
        target = ('resources/rawfile/runtime/lib/python3.12/encodings/__init__.py' if cid == 'cpython'
                  else f'resources/rawfile/runtime/lib/python3.12/site-packages/{cid}/__init__.py')
        for source, dest, data in [(f'{cid}/LICENSE', license_target, b'test-only license\n'),
                                   (f'{cid}/__init__.py', target, b'# synthetic test only\n')]:
            p = root / source
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            m['files'].append({'source': source, 'target': dest, 'sha256': rt.digest(data),
                               'size': len(data), 'component': cid})
    native = root / 'libpython3.12.so'
    native.write_bytes(elf())
    m['files'].append({'source': native.name, 'target': 'libs/arm64-v8a/libpython3.12.so',
                       'sha256': rt.file_hash(native), 'size': native.stat().st_size, 'component': 'cpython'})
    return m


def base_hap(path, extra=None, omit=(), debug=False):
    content = {'module.json': json.dumps({'app': {'bundleName': 'com.gsasii.desktop',
                'debug': debug, 'buildMode': 'debug' if debug else 'release'}}).encode(),
               **{name: elf() for name in rt.BASE_LIBS}}
    for p in (rt.REPO / 'app/entry/src/main/resources/rawfile/licenses').iterdir():
        content['resources/rawfile/licenses/' + p.name] = p.read_bytes()
    content.update(extra or {})
    with zipfile.ZipFile(path, 'w') as z:
        for name, data in content.items():
            if name not in omit:
                z.writestr(name, data)


class ReleaseToolsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.payload = self.root / 'payload'
        self.manifest = payload_fixture(self.payload)
        self.manifest_path = self.root / 'manifest.json'
        self.save()

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        rt.write_json(self.manifest_path, self.manifest)

    def prepare(self):
        self.save()
        return rt.prepare_runtime(self.manifest_path, self.payload, self.root / 'prepared')

    def full_hap(self, **kwargs):
        extra = {f['target']: (self.payload / f['source']).read_bytes() for f in self.manifest['files']}
        path = self.root / 'full.hap'
        base_hap(path, extra, **kwargs)
        return path

    def test_prepare_install_and_exact_hap_inventory(self):
        self.prepare()
        app = self.root / 'app'
        app.mkdir()
        rt.install_prepared(self.root / 'prepared', app)
        self.assertEqual((app / 'entry/libs/arm64-v8a/libpython3.12.so').read_bytes(), elf())
        report = rt.audit_hap(self.full_hap(), self.manifest, 'release')
        self.assertTrue(report['contentChecksPassed'])
        self.assertFalse(report['releaseCandidateApproved'])
        self.assertEqual(report['runtimeId'], 'test-v1')
        self.assertEqual(sum('component' in x for x in report['files']), len(self.manifest['files']) + 3)

    def test_placeholder_and_missing_core_components_blocked(self):
        with self.assertRaises(rt.ReleaseError):
            rt.validate_manifest(rt.read_json(rt.REPO / 'packaging/runtime-manifest.example.json'))
        self.manifest['components'].pop()
        with self.assertRaises(rt.ReleaseError):
            self.prepare()
        self.assertFalse((self.root / 'prepared').exists())

    def test_corrupted_payload_never_creates_output(self):
        (self.payload / 'numpy/__init__.py').write_text('tampered')
        with self.assertRaises(rt.ReleaseError):
            self.prepare()
        self.assertFalse((self.root / 'prepared').exists())

    def test_missing_or_undeclared_payload_rejected(self):
        (self.payload / 'extra.py').write_text('pass')
        with self.assertRaises(rt.ReleaseError):
            self.prepare()
        (self.payload / 'extra.py').unlink()
        (self.payload / 'numpy/__init__.py').unlink()
        with self.assertRaises(rt.ReleaseError):
            self.prepare()

    def test_existing_revision_is_unchanged(self):
        self.prepare()
        before = rt.file_hash(self.root / 'prepared/runtime-receipt.json')
        with self.assertRaises(rt.ReleaseError):
            self.prepare()
        self.assertEqual(before, rt.file_hash(self.root / 'prepared/runtime-receipt.json'))

    def test_payload_symlink_rejected(self):
        p = self.payload / 'numpy/__init__.py'
        p.unlink()
        try:
            p.symlink_to(self.payload / 'scipy/__init__.py')
        except OSError:
            self.skipTest('symlink creation unavailable')
        with self.assertRaises(rt.ReleaseError):
            self.prepare()

    def test_manifest_paths_and_case_collisions(self):
        for value in ('../escape', '/absolute', 'C:/Windows/file', 'a\\b', 'a//b', 'a/./b',
                      'a/NUL.txt', 'a/name.', 'a/name '):
            with self.subTest(value=value), self.assertRaises(rt.ReleaseError):
                rt.relative_path(value)
        self.manifest['files'].append(copy.deepcopy(self.manifest['files'][0]))
        self.manifest['files'][-1]['target'] = self.manifest['files'][0]['target'].upper()
        with self.assertRaises(rt.ReleaseError):
            self.prepare()

    def test_source_and_license_provenance_required(self):
        for key, bad in [('sourceUrl', ''), ('sourceCodeUrl', 'file:///tmp/source'),
                         ('licenseFiles', ['resources/rawfile/licenses/runtime/missing']),
                         ('dependsOn', ['unlisted-library']), ('reviewReference', '')]:
            original = copy.deepcopy(self.manifest)
            self.manifest['components'][0][key] = bad
            with self.subTest(key=key), self.assertRaises(rt.ReleaseError):
                self.prepare()
            self.manifest = original

    def test_wrong_architecture_and_foreign_binaries(self):
        with self.assertRaises(rt.ReleaseError):
            rt.inspect_content('libs/arm64-v8a/libwrong.so', elf(62))
        with self.assertRaises(rt.ReleaseError):
            rt.inspect_content('resources/rawfile/runtime/extension.so', elf(62))
        with self.assertRaises(rt.ReleaseError):
            rt.inspect_content('resources/rawfile/runtime/foreign.dll', b'MZ')

    def test_excluded_files_imports_and_disguised_archives(self):
        for name, data in [('runtime/PyDiffAx.cpython-312.so', elf()),
                           ('runtime/G2shapes.py', b'pass'), ('runtime/fake_core.py', b'pass'),
                           ('runtime/dependency.whl', b'data'), ('runtime/opaque.bin', b'PK\x03\x04data'),
                           ('runtime/module.py', b'from bridge import fake_core'),
                           ('runtime/module.py', b'import bridge.fake_core as f'),
                           ('runtime/module.py', b'from .fake_core import Refiner'),
                           ('ets/modules.abc', b'dev MockCoreService'),
                           ('runtime/private.p12', b'secret')]:
            with self.subTest(name=name), self.assertRaises(rt.ReleaseError):
                rt.inspect_content(name, data)
        # Documentation of the excluded fake module is not an import.
        rt.inspect_content('runtime/engine.py', b'"""See bridge.fake_core for tests."""\npass\n')

    def test_failed_prepare_cleans_new_revision(self):
        p = self.payload / 'libpython3.12.so'
        p.write_bytes(elf(62))
        self.manifest['files'][-1]['sha256'] = rt.file_hash(p)
        with self.assertRaises(rt.ReleaseError):
            self.prepare()
        self.assertFalse((self.root / 'prepared').exists())

    def test_prepared_payload_tampering_and_collision(self):
        self.prepare()
        p = self.root / 'prepared/libs/arm64-v8a/libpython3.12.so'
        p.write_bytes(b'changed')
        with self.assertRaises(rt.ReleaseError):
            rt.install_prepared(self.root / 'prepared', self.root / 'app')

    def test_package_missing_or_mutated_runtime(self):
        hap = self.full_hap(omit=('libs/arm64-v8a/libpython3.12.so',))
        with self.assertRaises(rt.ReleaseError):
            rt.audit_hap(hap, self.manifest)
        (self.payload / 'numpy/__init__.py').write_bytes(b'# changed')
        with self.assertRaises(rt.ReleaseError):
            rt.audit_hap(self.full_hap(), self.manifest)

    def test_release_requires_runtime_approval_and_release_build(self):
        path = self.root / 'base.hap'
        base_hap(path)
        with self.assertRaises(rt.ReleaseError):
            rt.audit_hap(path, mode='release')
        self.manifest['components'][0]['distributionReview'] = 'pending'
        with self.assertRaises(rt.ReleaseError):
            rt.audit_hap(self.full_hap(), self.manifest, 'release')
        self.manifest['components'][0]['distributionReview'] = 'approved'
        with self.assertRaises(rt.ReleaseError):
            rt.audit_hap(self.full_hap(debug=True), self.manifest, 'release')

    def test_unowned_native_and_runtime_are_rejected(self):
        for name, data in [('libs/arm64-v8a/libunlisted.so', elf()),
                           ('resources/rawfile/runtime/hidden.py', b'pass')]:
            path = self.root / 'base.hap'
            base_hap(path, {name: data})
            with self.subTest(name=name), self.assertRaises(rt.ReleaseError):
                rt.audit_hap(path)

    def test_hap_traversal_symlink_and_duplicate_rejected(self):
        path = self.root / 'base.hap'
        unsafe_names = ['../escape', '/absolute']
        if os.sep == '\\':
            # ZipInfo normalizes the host separator before it is written, so
            # a backslash cannot be observed by audit_hap on Windows. The
            # direct relative_path test above still covers its rejection.
            self.assertEqual(zipfile.ZipInfo('a\\b').filename, 'a/b')
        else:
            unsafe_names.append('a\\b')
        for name in unsafe_names:
            base_hap(path, {name: b'x'})
            with self.subTest(name=name), self.assertRaises(rt.ReleaseError):
                rt.audit_hap(path)
        base_hap(path)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(path, 'a') as z:
                z.writestr('module.json', b'{}')
        with self.assertRaises(rt.ReleaseError):
            rt.audit_hap(path)
        base_hap(path)
        info = zipfile.ZipInfo('resources/link')
        info.create_system = 3
        info.external_attr = 0o120777 << 16
        with zipfile.ZipFile(path, 'a') as z:
            z.writestr(info, b'/outside')
        with self.assertRaises(rt.ReleaseError):
            rt.audit_hap(path)

    def test_missing_or_changed_baseline_licenses(self):
        name = 'resources/rawfile/licenses/GSAS-II-LICENSE.txt'
        path = self.root / 'base.hap'
        base_hap(path, omit=(name,))
        with self.assertRaises(rt.ReleaseError):
            rt.audit_hap(path)
        base_hap(path, {name: b'replaced'})
        with self.assertRaises(rt.ReleaseError):
            rt.audit_hap(path)

    def test_staging_excludes_secrets_and_cache_but_records_source(self):
        src = self.root / 'src'
        src.mkdir()
        (src / 'main.ets').write_text('source')
        (src / 'private.p12').write_text('secret')
        (src / 'build').mkdir()
        (src / 'build/result.hap').write_text('generated')
        files = rt.stage_app(src, self.root / 'staged')
        self.assertEqual([f['path'] for f in files], ['main.ets'])
        self.assertEqual(files[0]['sha256'], rt.file_hash(src / 'main.ets'))
        self.assertFalse((self.root / 'staged/private.p12').exists())

    def test_build_record_matches_archived_bytes(self):
        spec = importlib.util.spec_from_file_location('build_app', rt.REPO / 'scripts/Build-App.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        output = self.root / 'build-output'

        def run(command, cwd=None, **kwargs):
            if 'build' in command:
                target = Path(cwd) / 'entry/build/default/outputs/default'
                target.mkdir(parents=True)
                base_hap(target / 'entry.hap')
            return CompletedProcess(command, 0, stdout='test-version\n' if kwargs.get('text') else b'')

        with patch.object(sys, 'argv', ['Build-App.py', '--cli', 'test-cli', '--stage-root',
                                      str(self.root), '--output-dir', str(output)]), \
                patch.object(module.subprocess, 'run', side_effect=run):
            module.main()
        record = rt.read_json(output / 'build-record.json')
        self.assertEqual(record['artifacts'][0]['sha256'], rt.file_hash(output / 'entry.hap'))
        self.assertEqual(record['sourceFingerprintSha256'], rt.fingerprint(record['sourceFiles']))
        self.assertFalse(record['releaseCandidateApproved'])
        self.assertEqual(record['deviceRun'], 'not-requested')

    def test_build_rejects_source_mutation_before_publishing(self):
        spec = importlib.util.spec_from_file_location('build_app_mutation', rt.REPO / 'scripts/Build-App.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        output = self.root / 'bad-output'

        def run(command, cwd=None, **kwargs):
            if 'build' in command:
                (Path(cwd) / 'entry/src/main/ets/pages/Index.ets').write_text('changed during build')
            return CompletedProcess(command, 0, stdout='test-version' if kwargs.get('text') else b'')

        with patch.object(sys, 'argv', ['Build-App.py', '--cli', 'test-cli', '--stage-root',
                                      str(self.root), '--output-dir', str(output)]), \
                patch.object(module.subprocess, 'run', side_effect=run), self.assertRaises(SystemExit):
            module.main()
        self.assertFalse(output.exists())

    def test_windows_npm_entry_uses_node_without_shell_interpolation(self):
        spec = importlib.util.spec_from_file_location('build_windows', rt.REPO / 'scripts/Build-App.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        prefix = self.root / 'npm'
        package = prefix / 'node_modules/@deveco/deveco-cli'
        package.mkdir(parents=True)
        (package / 'package.json').write_text('{"bin":{"devecocli":"cli.js"}}')
        (package / 'cli.js').write_text('// test only')
        with patch.object(module, 'os', SimpleNamespace(name='nt')), \
                patch.object(module.shutil, 'which', return_value='node.exe'):
            args = module.cli_command(prefix / 'devecocli.cmd', ['run', '--device', 'PC & other'])
        self.assertEqual(args, ['node.exe', str((package / 'cli.js').resolve()), 'run', '--device', 'PC & other'])


if __name__ == '__main__':
    unittest.main()
