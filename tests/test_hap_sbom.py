"""Synthetic fixtures only: graph/hash checks are not scientific evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
from test_release_tools import payload_fixture, base_hap
import release_tools as rt

spec = importlib.util.spec_from_file_location('hap_sbom', ROOT / 'scripts/Build-HapSbom.py')
sbom = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sbom)


class HapSbomTest(unittest.TestCase):
    def test_third_party_report_requires_exact_hap_native_and_license_hashes(self):
        inv = rt.audit_hap(self.hap, self.manifest)
        inv['files'] += [{'path': 'libs/arm64-v8a/readline.so', 'sha256': 'a' * 64,
                          'size': 64, 'component': 'cpython'},
                         {'path': 'resources/rawfile/licenses/runtime/cpython/READLINE.txt',
                          'sha256': 'b' * 64, 'size': 100, 'component': 'cpython'}]
        row = {'id': 'readline', 'declaredVersion': '8.3', 'declaredLinkMode': 'static',
               'bindings': [], 'consumers': [{'path': 'libs/arm64-v8a/readline.so', 'sha256': 'a' * 64}],
               'licenseDeclaration': {'spdx': 'GPL-3.0-or-later'},
               'licenseText': {'sha256': 'b' * 64, 'actualHapTargets': ['resources/rawfile/licenses/runtime/cpython/READLINE.txt']}}
        report = {'kind': 'actual-HAP-third-party-review', 'hapSha256': inv['hapSha256'],
                  'releaseApproved': False, 'components': [row]}
        bom = sbom.build_bom(inv)
        sbom.add_third_party_review(bom, inv, report)
        added = next(c for c in bom['components'] if c['bom-ref'] == 'third-party:readline')
        self.assertIn({'name': 'gsas:distributionReview', 'value': 'pending'}, added['properties'])
        self.assertNotIn('licenses', added)  # Declaration is retained as a pending property.
        report['hapSha256'] = 'c' * 64
        with self.assertRaisesRegex(ValueError, 'bound'):
            sbom.add_third_party_review(sbom.build_bom(inv), inv, report)
        report['hapSha256'] = inv['hapSha256']
        row['bindings'] = [{'actualPath': 'libs/arm64-v8a/readline.so', 'actualSha256': 'c' * 64}]
        with self.assertRaisesRegex(ValueError, 'native binding'):
            sbom.add_third_party_review(sbom.build_bom(inv), inv, report)
        row['bindings'] = []
        row['licenseText']['sha256'] = 'c' * 64
        with self.assertRaisesRegex(ValueError, 'license differs'):
            sbom.add_third_party_review(sbom.build_bom(inv), inv, report)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = self.root / 'payload'
        self.manifest = payload_fixture(self.payload)
        self.hap = self.root / 'fixture.hap'
        base_hap(self.hap, {f['target']: (self.payload / f['source']).read_bytes()
                            for f in self.manifest['files']})

    def test_every_actual_file_has_hash_and_resolvable_owner(self):
        inv = rt.audit_hap(self.hap, self.manifest)
        bom = sbom.build_bom(inv)
        files = [c for c in bom['components'] if c['type'] == 'file']
        self.assertEqual({c['name']: c['hashes'][0]['content'] for c in files},
                         {f['path']: f['sha256'] for f in inv['files']})
        refs = [c['bom-ref'] for c in bom['components']] + [bom['metadata']['component']['bom-ref']]
        self.assertEqual(len(refs), len(set(refs)))
        for edge in bom['dependencies']:
            self.assertIn(edge['ref'], refs)
            self.assertTrue(set(edge['dependsOn']) <= set(refs))
        self.assertTrue({'component:app-core', 'component:app-fileio', 'component:sdk-libcxx'} <= set(refs))

    def test_embedded_library_does_not_inherit_parent_license_or_approval(self):
        inv = rt.audit_hap(self.hap, self.manifest)
        inv['files'].append({'path': 'libs/arm64-v8a/libffi.so.8', 'size': 64,
                             'sha256': 'a' * 64, 'component': 'cpython'})
        bom = sbom.build_bom(inv)
        ffi = next(c for c in bom['components'] if c['name'] == 'embedded-libffi')
        self.assertNotIn('licenses', ffi)
        self.assertIn({'name': 'gsas:distributionReview', 'value': 'pending'}, ffi['properties'])

    def test_tampered_runtime_cannot_produce_sbom(self):
        invalid = copy.deepcopy(self.manifest)
        invalid['files'][0]['sha256'] = 'a' * 64
        output = self.root / 'output'
        with self.assertRaisesRegex(rt.ReleaseError, 'packaged runtime mismatch'):
            sbom.generate(self.hap, invalid, self.root / 'no-sdk-needed', output)
        self.assertFalse(output.exists())

    def test_missing_license_and_unknown_owner_are_rejected(self):
        inv = rt.audit_hap(self.hap, self.manifest)
        inv = copy.deepcopy(inv)
        inv['components'][0]['licenseFiles'] = ['absent/LICENSE']
        with self.assertRaisesRegex(ValueError, 'license file absent'):
            sbom.build_bom(inv)
        inv = rt.audit_hap(self.hap, self.manifest)
        inv['files'][0]['component'] = 'unknown'
        with self.assertRaisesRegex(ValueError, 'unknown file owner'):
            sbom.build_bom(inv)

    def test_static_runtime_provenance_requires_all_actual_module_hashes(self):
        inv = rt.audit_hap(self.hap, self.manifest)
        required = ['pyspg', 'pypowder', 'pytexture', 'fmask', 'histogram2d', 'pack_f', 'unpack_cbf', 'kvec_general']
        receipt = {'kind': 'locally-built-ohos-native-extensions', 'target': 'aarch64-linux-ohos',
                   'fortranRuntime': {'version': '20.1.8', 'license': 'Apache-2.0 WITH LLVM-exception'},
                   'files': [{'module': name, 'path': 'runtime/lib/python3.12/site-packages/GSASII/'
                              + name + '.cpython-312-aarch64-linux-ohos.so', 'sha256': 'a' * 64}
                             for name in required]}
        for row in receipt['files']:
            inv['files'].append({'path': 'libs/arm64-v8a/' + Path(row['path']).name, 'sha256': row['sha256'],
                                 'size': 64, 'component': 'gsas-ii'})
        inv['files'].append({'path': 'resources/rawfile/licenses/runtime/gsas-ii/LLVM-FortranRuntime-20.1.8-LICENSE.txt',
                             'sha256': 'b' * 64, 'size': 100, 'component': 'gsas-ii'})
        bom = sbom.build_bom(inv)
        sbom.add_native_provenance(bom, inv, receipt)
        self.assertTrue(any(c['bom-ref'] == 'component:llvm-fortran-runtime' for c in bom['components']))
        receipt['files'][0]['sha256'] = 'c' * 64
        with self.assertRaisesRegex(ValueError, 'does not match HAP'):
            sbom.add_native_provenance(sbom.build_bom(inv), inv, receipt)
        receipt['files'][0]['sha256'] = 'a' * 64
        receipt['files'][0]['path'] = 'unrelated/pyspg.cpython-312-aarch64-linux-ohos.so'
        with self.assertRaisesRegex(ValueError, 'source path'):
            sbom.add_native_provenance(sbom.build_bom(inv), inv, receipt)

    def test_soname_alone_and_sdk_names_are_not_runtime_proof(self):
        libraries = [
            {'path': 'libs/libpython3.12.so', 'needed': ['libc.so'], 'soname': ['libpython3.12.so.1.0']},
            {'path': 'libs/ext.so', 'needed': ['libpython3.12.so.1.0', 'libpython3.12.so'], 'soname': []},
        ]
        report = sbom.dependency_report(libraries, {'libc.so'})
        self.assertEqual(report['unmatchedNames'], ['libpython3.12.so.1.0'])
        self.assertEqual(report['sdkNameOnly'], ['libc.so'])
        self.assertEqual(report['edges'][-1]['status'], 'packaged-filename')
        self.assertFalse(report['releaseApproved'])


if __name__ == '__main__':
    unittest.main()
