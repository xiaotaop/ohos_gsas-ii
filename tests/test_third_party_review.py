"""Trust boundaries for review evidence; no fixture is scientific acceptance."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('third_party_review', ROOT / 'scripts/Audit-ThirdParty.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def elf(text=b'code', debug=b'debug', signature=b'signature'):
    names = b'\0.shstrtab\0.text\0.debug_info\0.codesign\0'
    data = bytearray(64 + 5 * 64)
    data[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<HH', data, 16, 3, 183)
    struct.pack_into('<Q', data, 40, 64)
    struct.pack_into('<HHH', data, 58, 64, 5, 1)
    for i, (name, content, flags) in enumerate([('.shstrtab', names, 0), ('.text', text, 6),
                                               ('.debug_info', debug, 0), ('.codesign', signature, 2)], 1):
        offset = len(data)
        data.extend(content)
        struct.pack_into('<IIQQQQIIQQ', data, 64 + i * 64, names.index(name.encode()),
                         1, flags, 0, offset, len(content), 0, 0, 1, 0)
    return bytes(data)


class ThirdPartyReviewTest(unittest.TestCase):
    def test_license_receipts_preserve_bytes_and_reject_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = b'Copyright\r\nConditions\r\n'
            row = {'file': 'LICENSE.txt', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            (root / 'LICENSE.txt').write_bytes(data)
            (root / 'SOURCES.json').write_text(json.dumps([row]))
            self.assertEqual(review.license_receipts(root)['LICENSE.txt'], row)
            (root / 'LICENSE.txt').write_bytes(data.replace(b'\r\n', b'\n'))
            with self.assertRaisesRegex(ValueError, 'actual bytes'):
                review.license_receipts(root)
            row['file'] = '../LICENSE.txt'
            (root / 'SOURCES.json').write_text(json.dumps([row]))
            with self.assertRaisesRegex(ValueError, 'unsafe'):
                review.license_receipts(root)

    def test_undefined_or_nonfunction_symbols_are_not_bundled_implementation(self):
        symbols = ('1: 0001 64 FUNC GLOBAL DEFAULT 9 libintl_gettext\n'
                   '2: 0000 0 FUNC GLOBAL DEFAULT UND libintl_dgettext\n'
                   '3: 0001 8 OBJECT GLOBAL DEFAULT 9 libintl_version\n')
        self.assertEqual(review.defined_intl_symbols(symbols), ['libintl_gettext'])

    def test_basename_collisions_are_rejected_instead_of_guessing(self):
        actual = [{'path': 'libs/a/libffi.so.8', 'sha256': 'a' * 64}]
        self.assertEqual(review.bind_filename('runtime/lib/libffi.so.8', actual), actual[0])
        actual.append({'path': 'libs/b/libffi.so.8', 'sha256': 'b' * 64})
        with self.assertRaisesRegex(ValueError, 'expected one'):
            review.bind_filename('libffi.so.8', actual)

    def test_only_debug_and_codesign_differences_are_ignored(self):
        self.assertEqual(review.allocated_sections(elf()),
                         review.allocated_sections(elf(debug=b'other', signature=b'new-signature')))
        self.assertNotEqual(review.allocated_sections(elf()),
                            review.allocated_sections(elf(text=b'changed code')))
        for malformed in (b'not ELF', elf()[:100]):
            with self.assertRaises(ValueError):
                review.allocated_sections(malformed)

    def test_locked_archive_alias_is_bound_to_actual_hap_and_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = elf()
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode='w:gz') as archive:
                real = tarfile.TarInfo('root/lib/libpython3.12.so.1.0')
                real.size = len(original)
                archive.addfile(real, io.BytesIO(original))
                alias = tarfile.TarInfo('root/lib/libpython3.12.so')
                alias.type = tarfile.SYMTYPE
                alias.linkname = 'libpython3.12.so.1.0'
                archive.addfile(alias)
            archive_path = root / 'python.tar.gz'
            archive_path.write_bytes(buf.getvalue())
            lock = {'runtimeInputs': [{'name': archive_path.name, 'component': 'cpython',
                                      'sha256': hashlib.sha256(buf.getvalue()).hexdigest()}]}
            declarations = {'components': [{'files': [{'path': 'libs/libpython3.12.so',
                'bytes': len(original), 'sha256': hashlib.sha256(original).hexdigest()}]}]}
            hap = root / 'test.hap'
            with zipfile.ZipFile(hap, 'w') as archive:
                archive.writestr('libs/arm64-v8a/libpython3.12.so', elf(debug=b'stripped', signature=b'new'))
            result = review.prebuilt_bindings(declarations, lock, root, hap)
            self.assertTrue(result[0]['matchesBHash'])
            self.assertTrue(result[0]['allocatedSectionsSameExceptCodesign'])
            self.assertEqual(result[0]['sourceAliasTarget'], 'root/lib/libpython3.12.so.1.0')
            archive_path.write_bytes(b'not the locked archive')
            with self.assertRaisesRegex(ValueError, 'locked hash'):
                review.prebuilt_bindings(declarations, lock, root, hap)


if __name__ == '__main__':
    unittest.main()
