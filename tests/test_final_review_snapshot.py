"""Keep the committed handoff internally consistent without requiring a private HAP."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import unittest

REVIEWS = Path(__file__).resolve().parents[1] / 'packaging/reviews'


class FrozenReviewTest(unittest.TestCase):
    def test_frozen_files_licenses_and_native_relations_match_review(self):
        snapshots = sorted(REVIEWS.glob('*-final'))
        self.assertTrue(snapshots)
        for root in snapshots:
            with self.subTest(snapshot=root.name):
                self.verify_snapshot(root)

    def verify_snapshot(self, root):
        summary = json.loads((root / 'review-summary.json').read_bytes())
        if 'publicHapFinalSbomSha256' in summary:
            self.verify_store_snapshot(root, summary)
            return
        seen = set()
        for row in summary['snapshotFiles']:
            path = PurePosixPath(row['path'])
            self.assertFalse(path.is_absolute() or '..' in path.parts)
            self.assertNotIn(row['path'], seen)
            seen.add(row['path'])
            data = (root / path).read_bytes()
            self.assertEqual(len(data), row['size'])
            self.assertEqual(hashlib.sha256(data).hexdigest(), row['sha256'])
        bom_data = (root / summary['sbomFile']).read_bytes()
        self.assertEqual(hashlib.sha256(bom_data).hexdigest(), summary['sbomSha256'])
        bom = json.loads(bom_data)
        files = {c['name']: c for c in bom['components'] if c['type'] == 'file'}
        self.assertEqual(len(files), summary['hapFiles'])
        self.assertEqual(sum(p.startswith('libs/') for p in files), summary['nativeELFs'])
        refs = {c['bom-ref'] for c in bom['components']} | {bom['metadata']['component']['bom-ref']}
        edges = {e['ref']: set(e['dependsOn']) for e in bom['dependencies']}
        for ref, targets in edges.items():
            self.assertIn(ref, refs)
            self.assertLessEqual(targets, refs)
        decision = json.loads((root / 'review-decisions.json').read_bytes())
        self.assertEqual(decision['hapSha256'], summary['hapSha256'])
        for row in decision['components']:
            if row['action'] == 'reviewed':
                for license in row['licenseFiles']:
                    self.assertEqual(files[license['path']]['hashes'][0]['content'], license['sha256'])
        native = json.loads((root / 'evidence/native-dependencies.json').read_bytes())
        self.assertEqual(len(native['edges']), summary['nativeNeededEdges'])
        for edge in native['edges']:
            target = ('file:' + edge['packagedTarget'] if edge['status'] == 'packaged-filename'
                      else 'platform:' + edge['needed'])
            self.assertIn(target, edges['file:' + edge['from']])
        for name in ['gdbm', 'readline', 'gettext-libintl', 'gfortran']:
            self.assertNotIn('third-party:' + name, refs)
        self.assertTrue(summary['step2EngineeringDeliveryComplete'])
        self.assertFalse(summary['publicDistributionApproved'])

    def verify_store_snapshot(self, root, summary):
        packages = (
            ('public-hap', 'publicHapSha256', 'publicHapFinalSbomSha256',
             'publicHapReviewDecisionsSha256', 'publicHapFiles'),
            ('store-app-embedded-hap', 'storeEmbeddedHapSha256',
             'storeEmbeddedHapFinalSbomSha256',
             'storeEmbeddedHapReviewDecisionsSha256', 'storeEmbeddedHapFiles'),
        )
        for name, hap_key, sbom_key, decision_key, files_key in packages:
            with self.subTest(package=name):
                decision_data = (root / f'{name}-review-decisions.json').read_bytes()
                self.assertEqual(hashlib.sha256(decision_data).hexdigest(),
                                 summary[decision_key])
                decision = json.loads(decision_data)
                self.assertEqual(decision['hapSha256'], summary[hap_key])
                self.assertEqual(decision['acceptanceMode'], 'equivalent-device-counterpart')
                bom_data = (root / f'{name}-sbom.cdx.json').read_bytes()
                self.assertEqual(hashlib.sha256(bom_data).hexdigest(), summary[sbom_key])
                bom = json.loads(bom_data)
                self.assertEqual(bom['metadata']['component']['hashes'][0]['content'],
                                 summary[hap_key])
                files = {c['name']: c for c in bom['components'] if c['type'] == 'file'}
                self.assertEqual(len(files), summary[files_key])
                self.assertEqual(sum(p.startswith('libs/') for p in files),
                                 summary['nativeELFs'])
                properties = {p['name']: p['value'] for p in bom['metadata']['properties']}
                self.assertEqual(properties['gsas:engineeringReview'], 'complete')
                self.assertEqual(properties['gsas:publicDistributionApproved'], 'false')
        self.assertTrue(summary['deviceCriticalRetestPassed'])
        self.assertEqual(summary['deviceNumericComparisonsPassed'],
                         summary['deviceNumericComparisonsTotal'])
        self.assertFalse(summary['platformSubmitted'])
        self.assertFalse(summary['publicDistributionApproved'])


if __name__ == '__main__':
    unittest.main()
