"""Source bundle trust boundaries; no device/science claims."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('source_companion', ROOT / 'scripts/Build-SourceCompanion.py')
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)


def tar_bytes(names):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w') as archive:
        for name, content in names.items():
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    return output.getvalue()


class SourceCompanionTest(unittest.TestCase):
    def test_archive_traversal_and_source_links_rejected(self):
        for name in ('../secret', '/etc/passwd', 'safe/../../secret', 'bad\\name'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'unsafe'):
                source.read_archive(tar_bytes({name: b'bad'}))
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode='w') as archive:
            link = tarfile.TarInfo('root/sources/leak')
            link.type = tarfile.SYMTYPE
            link.linkname = '/etc/passwd'
            archive.addfile(link)
        with self.assertRaisesRegex(ValueError, 'links/special'):
            source.read_archive(output.getvalue(), True)

    def test_explicit_commit_excludes_private_working_changes_and_is_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / 'repo'
            repo.mkdir()
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=repo, stderr=subprocess.DEVNULL).decode().strip()
            git('init')
            archive = tar_bytes({'up/LICENSE': b'copyright', 'up/GSASII/GSASIIpath.py': b'x = 1\n',
                                 'up/sources/meson.build': b'module', 'up/meson.build': b'build',
                                 'up/sources/DIFFaX/DIFFaX.for': b'excluded',
                                 'up/GSASII/G2shapes.py': b'excluded'})
            upstream = root / 'upstream.tar'
            upstream.write_bytes(archive)
            lock_path = repo / 'scripts/ohos/local-cross/sources.lock.json'
            lock_path.parent.mkdir(parents=True)
            lock_path.write_text(json.dumps({'gsas': {'commit': 'b' * 40,
                'sha256': hashlib.sha256(archive).hexdigest()}}))
            (repo / 'README').write_text('committed source')
            git('add', '.')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                'commit', '-m', 'fixture')
            commit = git('rev-parse', 'HEAD')
            (repo / 'README').write_text('dirty credentials must not enter archive')
            (repo / 'private.p12').write_bytes(b'private material')
            first, second = root / 'first.tar.gz', root / 'second.tar.gz'
            a = source.generate(repo, upstream, commit, first)
            b = source.generate(repo, upstream, commit, second)
            self.assertEqual(a['sha256'], b['sha256'])
            with tarfile.open(first) as bundle:
                self.assertEqual(bundle.extractfile('port/README').read(), b'committed source')
                self.assertFalse(any('private.p12' in n or 'diffax' in n.lower() or 'G2shapes.py' in n
                                     for n in bundle.getnames()))
                inventory = json.load(bundle.extractfile('source-inventory.json'))
                for entry in inventory['files']:
                    self.assertEqual(entry['sha256'], hashlib.sha256(bundle.extractfile(entry['path']).read()).hexdigest())
            with self.assertRaisesRegex(ValueError, 'new file'):
                source.generate(repo, upstream, commit, first)
            upstream.write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'SHA-256 differs'):
                source.generate(repo, upstream, commit, root / 'bad.tar.gz')
            self.assertFalse((root / 'bad.tar.gz').exists())


if __name__ == '__main__':
    unittest.main()
