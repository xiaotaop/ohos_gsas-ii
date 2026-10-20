"""Removal guard tests; fixtures cannot establish runtime functionality."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('prune_runtime', ROOT / 'scripts/Prune-RuntimeOrphans.py')
prune = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prune)


class PruneRuntimeTest(unittest.TestCase):
    def test_external_needed_or_literal_reference_blocks_removal(self):
        libraries = [{'path': 'libs/libscipy_openblas64_.so', 'needed': ['libgfortran.so.5']}]
        prune.check_references(libraries, [])
        libraries.append({'path': 'libs/active.so', 'needed': ['libgfortran.so.5']})
        with self.assertRaisesRegex(ValueError, 'blocked'):
            prune.check_references(libraries, [])
        with self.assertRaisesRegex(ValueError, 'blocked'):
            prune.check_references([], [{'path': 'runtime/loader.py', 'name': 'libgfortran.so.5'}])

    def test_new_copy_only_removes_two_files_and_keeps_licenses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, output, sdk = root / 'input', root / 'output', root / 'sdk'
            (source / 'libs').mkdir(parents=True)
            (source / 'licenses').mkdir()
            (source / 'licenses/COPYING.txt').write_bytes(b'license bytes')
            for name in sorted(prune.CANDIDATES | {'active.so'}):
                (source / 'libs' / name).write_bytes(b'ELF-fixture')
            tool = sdk / 'native/llvm/bin/llvm-readelf'
            tool.parent.mkdir(parents=True)
            tool.touch()
            before = {p.relative_to(source).as_posix(): p.read_bytes() for p in source.rglob('*') if p.is_file()}
            with patch.object(prune.sbom, 'elf_metadata', return_value={'needed': []}):
                result = prune.stage(source, output, sdk)
            self.assertEqual(before, {p.relative_to(source).as_posix(): p.read_bytes() for p in source.rglob('*') if p.is_file()})
            self.assertFalse(result['deviceValidated'])
            self.assertEqual((output / 'licenses/COPYING.txt').read_bytes(), b'license bytes')
            self.assertEqual({p.name for p in (output / 'libs').iterdir()}, {'active.so'})
            with self.assertRaisesRegex(ValueError, 'NEW output'):
                prune.stage(source, output, sdk)
            (source / 'loader.py').write_text("name = 'libgfortran.so.5'")
            blocked = root / 'blocked'
            with patch.object(prune.sbom, 'elf_metadata', return_value={'needed': []}):
                with self.assertRaisesRegex(ValueError, 'blocked'):
                    prune.stage(source, blocked, sdk)
            self.assertFalse(blocked.exists())


if __name__ == '__main__':
    unittest.main()
