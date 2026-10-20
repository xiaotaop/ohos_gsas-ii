"""Keep the committed handoff internally consistent without requiring a private HAP."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'packaging/reviews/1190b1d5-final'


class FrozenReviewTest(unittest.TestCase):
    def test_frozen_files_licenses_and_native_relations_match_review(self):
        summary = json.loads((ROOT / 'review-summary.json').read_text())
        seen = set()
        for row in summary['snapshotFiles']:
            path = PurePosixPath(row['path'])
            self.assertFalse(path.is_absolute() or '..' in path.parts)
            self.assertNotIn(row['path'], seen)
            seen.add(row['path'])
            data = (ROOT / path).read_bytes()
            self.assertEqual(len(data), row['size'])
            self.assertEqual(hashlib.sha256(data).hexdigest(), row['sha256'])
        bom_data = (ROOT / summary['sbomFile']).read_bytes()
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
        decision = json.loads((ROOT / 'review-decisions.json').read_text())
        self.assertEqual(decision['hapSha256'], summary['hapSha256'])
        for row in decision['components']:
            if row['action'] == 'reviewed':
                for license in row['licenseFiles']:
                    self.assertEqual(files[license['path']]['hashes'][0]['content'], license['sha256'])
        native = json.loads((ROOT / 'evidence/native-dependencies.json').read_text())
        self.assertEqual(len(native['edges']), summary['nativeNeededEdges'])
        for edge in native['edges']:
            target = ('file:' + edge['packagedTarget'] if edge['status'] == 'packaged-filename'
                      else 'platform:' + edge['needed'])
            self.assertIn(target, edges['file:' + edge['from']])
        for name in ['gdbm', 'readline', 'gettext-libintl', 'gfortran']:
            self.assertNotIn('third-party:' + name, refs)
        self.assertTrue(summary['step2EngineeringDeliveryComplete'])
        self.assertFalse(summary['publicDistributionApproved'])


if __name__ == '__main__':
    unittest.main()
