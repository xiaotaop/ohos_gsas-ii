"""DT_NEEDED parsing fixtures; these are not runnable target libraries."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('python_needed', ROOT / 'scripts/ohos/Normalize-PythonNeeded.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fixture(name=mod.OLD):
    data = bytearray(512)
    data[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<HH', data, 16, 3, 183)
    struct.pack_into('<Q', data, 32, 64)
    struct.pack_into('<HH', data, 54, 56, 2)
    struct.pack_into('<IIQQQQQQ', data, 64, 1, 4, 0, 0x1000, 0, len(data), len(data), 1)
    struct.pack_into('<IIQQQQQQ', data, 120, 2, 4, 192, 0x10c0, 0, 64, 64, 8)
    for index, pair in enumerate([(5, 0x1140), (10, 64), (1, 0), (0, 0)]):
        struct.pack_into('<QQ', data, 192 + index * 16, *pair)
    data[320:320 + len(name)] = name
    data[420:420 + len(mod.OLD)] = mod.OLD  # unrelated bytes MUST remain untouched
    return bytes(data)


class PythonNeededTest(unittest.TestCase):
    def test_rewrites_only_exact_dynamic_dependency_and_preserves_layout(self):
        original = fixture()
        result, changes = mod.normalize(original)
        self.assertEqual(len(result), len(original))
        self.assertEqual(result[320:337], mod.NEW + b'\0')
        self.assertEqual(result[420:420 + len(mod.OLD)], mod.OLD)
        self.assertEqual(len(changes), 1)
        again, edits = mod.normalize(result)
        self.assertEqual(again, result)
        self.assertEqual(edits, [])

    def test_similar_dependency_name_is_not_rewritten(self):
        original = fixture(mod.OLD + b'.extra')
        result, changes = mod.normalize(original)
        self.assertEqual(result, original)
        self.assertEqual(changes, [])

    def test_malformed_or_other_architecture_fails_closed(self):
        for original in [b'', fixture()[:100], fixture()[:16] + b'\x03\x00\x3e\x00' + fixture()[20:]]:
            with self.subTest(size=len(original)), self.assertRaises(ValueError):
                mod.normalize(original)

    def test_copy_requires_provider_and_removes_stale_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / 'source'; source.mkdir()
            with self.assertRaisesRegex(ValueError, 'interpreter'):
                mod.prepare(source, root / 'output')
            (source / 'libs').mkdir()
            (source / 'libs/libpython3.12.so').write_bytes(fixture(b'libc.so'))
            (source / 'libs/consumer.so').write_bytes(fixture())
            (source / 'runtime').mkdir()
            (source / 'runtime/manifest.json').write_text('stale')
            report = mod.prepare(source, root / 'output')
            self.assertTrue(report['requiresResigning'])
            self.assertEqual(len(report['files']), 1)
            self.assertEqual((source / 'libs/consumer.so').read_bytes(), fixture())
            self.assertFalse((root / 'output/runtime/manifest.json').exists())


if __name__ == '__main__':
    unittest.main()
