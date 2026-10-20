"""Derived payload license assembly must preserve accepted input bytes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('stage_licenses',ROOT/'scripts/Stage-ThirdPartyLicenses.py')
staging=importlib.util.module_from_spec(spec)
spec.loader.exec_module(staging)


class StageLicenseTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source=self.root/'accepted'
        self.source.mkdir()
        (self.source/'runtime').mkdir()
        (self.source/'runtime/code.py').write_bytes(b'x=1\n')
        self.licenses=self.root/'licenses'
        self.licenses.mkdir()
        self.data=b'Copyright\r\nConditions\r\n'
        self.receipt={'file':'libffi-LICENSE.txt','component':'libffi','bytes':len(self.data),
                      'sha256':hashlib.sha256(self.data).hexdigest()}
        (self.licenses/self.receipt['file']).write_bytes(self.data)
        (self.licenses/'SOURCES.json').write_text(json.dumps([self.receipt]))

    def test_copies_exact_license_bytes_to_new_payload_without_approval(self):
        output=self.root/'derived'
        result=staging.stage(self.source,output,self.licenses)
        self.assertEqual((output/'licenses/cpython/libffi-LICENSE.txt').read_bytes(),self.data)
        self.assertEqual((output/'runtime/code.py').read_bytes(),b'x=1\n')
        self.assertFalse((self.source/'licenses').exists())
        self.assertFalse(result['releaseApproved'])
        index=json.loads((output/'licenses/cpython/THIRD-PARTY-SOURCES.json').read_text())
        self.assertEqual(index['distributionReview'],'pending')
        with self.assertRaisesRegex(ValueError,'NEW output'):
            staging.stage(self.source,output,self.licenses)

    def test_unknown_owner_or_tampered_license_leaves_output_absent(self):
        self.receipt['component']='unreviewed-library'
        (self.licenses/'SOURCES.json').write_text(json.dumps([self.receipt]))
        output=self.root/'rejected'
        with self.assertRaisesRegex(ValueError,'owner required'):
            staging.stage(self.source,output,self.licenses)
        self.assertFalse(output.exists())
        self.receipt['component']='libffi'
        (self.licenses/'SOURCES.json').write_text(json.dumps([self.receipt]))
        (self.licenses/self.receipt['file']).write_bytes(b'altered license')
        with self.assertRaisesRegex(ValueError,'actual bytes'):
            staging.stage(self.source,output,self.licenses)
        self.assertFalse(output.exists())

    def test_nested_output_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'separate trees'):
            staging.stage(self.source,self.source/'derived',self.licenses)
        self.assertFalse((self.source/'derived').exists())


if __name__=='__main__':
    unittest.main()
