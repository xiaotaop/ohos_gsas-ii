"""Final review must not bless changed files, missing decisions or foreign evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('final_sbom', ROOT / 'scripts/Finalize-HapSbom.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def canonical(d):
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()


class FinalReviewTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inv = {'hapSha256': 'a' * 64, 'files': [
            {'path': 'LICENSE', 'sha256': 'b' * 64}]}
        self.bom = {'metadata': {'component': {'bom-ref': 'app', 'hashes': [
            {'alg': 'SHA-256', 'content': 'a' * 64}]}}, 'components': [
            {'bom-ref': 'component:a', 'name': 'a', 'type': 'library'},
            {'bom-ref': 'file:LICENSE', 'name': 'LICENSE', 'type': 'file',
             'hashes': [{'alg': 'SHA-256', 'content': 'b' * 64}]}],
            'dependencies': [{'ref': 'app', 'dependsOn': ['component:a']}]}
        self.report = {'hapSha256': 'a' * 64, 'findings': [{'id': 'version-observation'}]}
        acceptance = {'hapSha256': 'a' * 64, 'independentWindowsBaselineChecksPassed': 12,
            **{k: True for k in ['installationPassed', 'coreReadyPassed', 'realFiveStagePassed',
                'gpxJsonLogSystemPickerExportPassed', 'completedJobProcessRestartRecoveryPassed']}}
        p = self.root / 'acceptance.json'
        p.write_text(json.dumps(acceptance))
        self.decision = {'kind': 'C-hash-bound-engineering-review', 'hapSha256': 'a' * 64,
            'draftCanonicalSha256': canonical(self.bom), 'reportCanonicalSha256': canonical(self.report),
            'scope': 'specific internaltesting HAP only', 'acceptanceRecord': p.name,
            'publicDistributionApproved': False, 'releaseApproved': False,
            'evidence': [{'file': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}],
            'findingDispositions': [{'id': 'version-observation', 'status': 'accepted-observation',
                                     'reason': 'unverified version omitted, bytes remain fixed'}],
            'components': [{'ref': 'component:a', 'action': 'reviewed', 'reason': 'actual notice checked',
                'licenses': [{'license': {'id': 'MIT'}}],
                'licenseFiles': [{'path': 'LICENSE', 'sha256': 'b' * 64}]}]}

    def apply(self):
        return m.apply_review(self.bom, self.inv, self.report, self.decision, self.root)

    def test_complete_review_preserves_every_file_and_never_approves_store(self):
        result = self.apply()
        self.assertEqual(m.properties(result['metadata'])['gsas:publicDistributionApproved'], 'false')
        self.assertEqual(m.properties(result['metadata'])['gsas:engineeringReview'], 'complete')
        self.assertEqual(self.bom['components'][0].get('licenses'), None)
        self.assertEqual(next(r for r in result['components'] if r['type'] == 'file')['hashes'],
                         self.bom['components'][1]['hashes'])

    def test_declaration_merge_does_not_invent_dependency_on_parent(self):
        self.bom['components'].append({'type': 'library', 'name': 'duplicate', 'bom-ref': 'declaration:a'})
        self.bom['dependencies'] += [
            {'ref': 'component:a', 'dependsOn': ['file:LICENSE']},
            {'ref': 'file:LICENSE', 'dependsOn': ['declaration:a']}]
        self.decision['components'].append({'ref': 'declaration:a', 'action': 'merge',
            'into': 'component:a', 'declarationOnly': True, 'reason': 'duplicate container assertion'})
        self.decision['draftCanonicalSha256'] = canonical(self.bom)
        result = self.apply()
        edge = next(e for e in result['dependencies'] if e['ref'] == 'file:LICENSE')
        self.assertNotIn('component:a', edge['dependsOn'])
        self.assertNotIn('declaration:a', {c['bom-ref'] for c in result['components']})

    def test_changed_draft_report_or_evidence_is_rejected(self):
        for name in ['draftCanonicalSha256', 'reportCanonicalSha256']:
            with self.subTest(name=name):
                old = self.decision[name]
                self.decision[name] = 'c' * 64
                with self.assertRaisesRegex(ValueError, 'input changed'):
                    self.apply()
                self.decision[name] = old
        (self.root / 'acceptance.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'evidence bytes changed'):
            self.apply()

    def test_every_finding_and_component_needs_review(self):
        self.decision['findingDispositions'] = []
        with self.assertRaisesRegex(ValueError, 'every finding'):
            self.apply()
        self.setUp()
        self.decision['components'] = []
        with self.assertRaisesRegex(ValueError, 'every actual logical component'):
            self.apply()

    def test_license_hash_tampering_is_rejected(self):
        self.decision['components'][0]['licenseFiles'][0]['sha256'] = 'c' * 64
        with self.assertRaisesRegex(ValueError, 'license does not match'):
            self.apply()

    def test_final_file_omission_and_foreign_hap_are_rejected(self):
        self.bom['components'].pop()
        self.decision['draftCanonicalSha256'] = canonical(self.bom)
        with self.assertRaisesRegex(ValueError, 'file inventory differs'):
            self.apply()
        self.setUp()
        self.inv['hapSha256'] = 'c' * 64
        with self.assertRaisesRegex(ValueError, 'does not match actual HAP'):
            self.apply()

    def test_native_graph_preserves_actual_edges_and_marks_platform_excluded(self):
        path = 'libs/a.so'
        self.inv['files'].append({'path': path, 'sha256': 'd' * 64})
        self.bom['components'].append({'type': 'file', 'bom-ref': 'file:' + path, 'name': path,
            'hashes': [{'alg': 'SHA-256', 'content': 'd' * 64}]})
        self.decision['draftCanonicalSha256'] = canonical(self.bom)
        with self.assertRaisesRegex(ValueError, 'native dependency evidence required'):
            self.apply()
        native = {'hapSha256': 'a' * 64, 'unmatchedNames': [],
            'libraries': [{'path': path, 'sha256': 'd' * 64}],
            'edges': [{'from': path, 'needed': 'libc.so', 'status': 'sdk-filename-only'}]}
        p = self.root / 'native.json'
        p.write_text(json.dumps(native))
        self.decision['nativeDependencyRecord'] = p.name
        self.decision['evidence'].append({'file': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
        result = self.apply()
        platform = next(c for c in result['components'] if c['bom-ref'] == 'platform:libc.so')
        self.assertEqual(platform['scope'], 'excluded')
        self.assertNotIn('version', platform)
        edge = next(e for e in result['dependencies'] if e['ref'] == 'file:' + path)
        self.assertIn('platform:libc.so', edge['dependsOn'])
        native['libraries'][0]['sha256'] = 'e' * 64
        p.write_text(json.dumps(native))
        self.decision['evidence'][-1]['sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'library bytes changed'):
            self.apply()

    def test_unsafe_evidence_paths_and_unbound_acceptance_are_rejected(self):
        self.decision['evidence'][0]['file'] = '../acceptance.json'
        with self.assertRaisesRegex(ValueError, 'unsafe evidence'):
            self.apply()
        self.setUp()
        self.decision['evidence'] = []
        with self.assertRaisesRegex(ValueError, 'acceptance must be hash-bound'):
            self.apply()


class StoreCounterpartTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.device = self.root / 'device.hap'
        self.public = self.root / 'public.hap'
        self.embedded = self.root / 'embedded.hap'
        self.app = self.root / 'store.app'
        members = {'module.json': b'{"versionCode":3}', 'pack.info': b'{"a":1}',
                   '.pages.info': b'pages', 'libs/lib.so': b'unchanged'}
        for path, comment in ((self.device, b'device'), (self.public, b'public')):
            with zipfile.ZipFile(path, 'w') as z:
                for name, data in members.items():
                    z.writestr(name, data)
                z.comment = comment
        with zipfile.ZipFile(self.embedded, 'w') as z:
            for name, data in members.items():
                if name == '.pages.info':
                    continue
                z.writestr(name, b'{\n  "a": 1\n}' if name == 'pack.info' else data)
        with zipfile.ZipFile(self.app, 'w') as z:
            z.writestr('entry-default.hap', self.embedded.read_bytes())
        self.counterpart = {
            'deviceHapFile': self.device.name, 'publicHapFile': self.public.name,
            'storeAppFile': self.app.name,
            'deviceHapSha256': m.rt.file_hash(self.device),
            'publicHapSha256': m.rt.file_hash(self.public),
            'embeddedHapSha256': m.rt.file_hash(self.embedded),
            'storeAppSha256': m.rt.file_hash(self.app),
        }
        self.acceptance = {
            'result': 'critical-device-retest-passed-with-startup-warning',
            'deviceHapSha256': self.counterpart['deviceHapSha256'],
            'publicAppSha256': self.counterpart['storeAppSha256'],
            'newJob': {'independentNumericComparisonsPassed': 12, 'fiveStagesCompleted': True},
            'exports': {'allThreeVisibleOnPickerReopen': True},
            'restart': {'successfulResultAndArtifactsRestored': True},
            'upgrade': {'versionCodeAfter': 3},
        }
        self.decision = {'evidence': [{'file': p.name} for p in (self.device, self.public, self.app)],
                         'counterpart': self.counterpart}

    def test_public_and_embedded_equivalent_counterparts(self):
        for kind, path in (('public-standalone-hap', self.public),
                           ('store-embedded-hap', self.embedded)):
            with self.subTest(kind=kind):
                self.counterpart['kind'] = kind
                m.validate_equivalent_device_acceptance(
                    self.acceptance, {'hapSha256': m.rt.file_hash(path)}, self.decision, self.root)

    def test_changed_payload_or_absent_device_checks_are_rejected(self):
        self.counterpart['kind'] = 'public-standalone-hap'
        self.acceptance['newJob']['independentNumericComparisonsPassed'] = 11
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            m.validate_equivalent_device_acceptance(
                self.acceptance, {'hapSha256': m.rt.file_hash(self.public)}, self.decision, self.root)
        self.acceptance['newJob']['independentNumericComparisonsPassed'] = 12
        with zipfile.ZipFile(self.public, 'a') as z:
            z.writestr('extra.txt', b'not on device')
        self.counterpart['publicHapSha256'] = m.rt.file_hash(self.public)
        with self.assertRaisesRegex(ValueError, 'content differs'):
            m.validate_equivalent_device_acceptance(
                self.acceptance, {'hapSha256': m.rt.file_hash(self.public)}, self.decision, self.root)


if __name__ == '__main__':
    unittest.main()
