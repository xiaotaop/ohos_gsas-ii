#!/usr/bin/env python3
"""Create a reproducible source companion; never bundle private working files.

The port is read with git archive at an explicit immutable commit. The GSAS-II
archive must match sources.lock.json. This closes source delivery packaging,
not third-party license approval or byte-identical binary reproducibility.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def excluded(name):
    parts = PurePosixPath(name.lower()).parts
    return any('diffax' in part or part == 'g2shapes.py' for part in parts)


def read_archive(data, strip_root=False):
    files = {}
    roots = set()
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or '\\' in member.name:
                raise ValueError('unsafe source archive path')
            if member.isdir():
                continue
            roots.add(path.parts[0])
            name = '/'.join(path.parts[1:]) if strip_root else path.as_posix()
            # Upstream rendered documentation has directory symlinks; it is
            # outside the build-source scope. Never follow any archive link.
            if strip_root and name.startswith('docs/'):
                continue
            if not member.isfile():
                raise ValueError('source archive links/special files are not supported')
            if not name or name in files:
                raise ValueError('empty or duplicate source path')
            if not excluded(name):
                files[name] = archive.extractfile(member).read()
    if strip_root and len(roots) != 1:
        raise ValueError('expected one upstream archive root')
    return files


def generate(repo, upstream, commit, output):
    if output.exists():
        raise ValueError('output must be a new file')
    resolved = subprocess.check_output(['git', 'rev-parse', '--verify', commit + '^{commit}'],
                                       cwd=repo, text=True).strip()
    port_data = subprocess.check_output(['git', 'archive', '--format=tar', resolved], cwd=repo)
    port = read_archive(port_data)
    lock = json.loads(port['scripts/ohos/local-cross/sources.lock.json'])['gsas']
    upstream_data = upstream.read_bytes()
    if sha(upstream_data) != lock['sha256']:
        raise ValueError('upstream archive SHA-256 differs from locked build input')
    gsas = read_archive(upstream_data, strip_root=True)
    for required in ('LICENSE', 'GSASII/GSASIIpath.py', 'sources/meson.build', 'meson.build'):
        if required not in gsas:
            raise ValueError('missing relevant upstream source: ' + required)
    files = {'port/' + k: v for k, v in port.items()}
    files.update({'upstream-gsas-ii/' + k: v for k, v in gsas.items()})
    files['README.txt'] = (f'''GSAS-II HarmonyOS source companion
Port commit: {resolved}
Upstream GSAS-II commit: {lock['commit']}
Upstream archive SHA-256: {lock['sha256']}

Contains tracked port sources, licenses/NOTICE, the relevant locked GSAS-II
sources and the OHOS patch/build recipes under port/scripts/ohos/local-cross/.
Apply gsas-ohos.patch to upstream-gsas-ii for the native module build.
DIFFaX and G2shapes.py are excluded from this distribution scope.
Build-Extensions.sh documents the original /work container layout; adapt the
paths without changing the locked sources. Read local-cross/README.md first.
Generated f2py wrappers and local binary/library build receipts are separate
build evidence, not a replacement for the corresponding upstream sources.

This companion does not claim to contain corresponding sources for the
prebuilt CPython/NumPy/SciPy OHOS distribution or its embedded dependencies.
Their source/version/license review remains a separate delivery prerequisite.
Keep this archive alongside the HAP and its final audit records.
''').encode()
    manifest = {'schemaVersion': 1, 'kind': 'gsas-port-source-companion',
                'portCommit': resolved, 'upstreamCommit': lock['commit'],
                'upstreamArchiveSha256': lock['sha256'], 'releaseApproved': False,
                'files': [{'path': k, 'size': len(v), 'sha256': sha(v)} for k, v in sorted(files.items())]}
    files['source-inventory.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    # Stable gzip/tar headers; same explicit commit and archive produce same bytes.
    with output.open('xb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode='w', format=tarfile.PAX_FORMAT) as archive:
            for name, data in sorted(files.items()):
                entry = tarfile.TarInfo(name)
                entry.size = len(data)
                entry.mode = 0o644
                archive.addfile(entry, io.BytesIO(data))
    return {'path': output.name, 'sha256': sha(output.read_bytes()), 'size': output.stat().st_size,
            'sourceFiles': len(manifest['files']), 'portCommit': resolved,
            'upstreamCommit': lock['commit'], 'releaseApproved': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--upstream-archive', type=Path, required=True)
    p.add_argument('--source-commit', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    try:
        print(json.dumps(generate(Path(__file__).resolve().parents[1], args.upstream_archive,
                                  args.source_commit, args.output)))
    except (OSError, ValueError, KeyError, tarfile.TarError, subprocess.SubprocessError) as error:
        p.exit(1, f'Source companion failed: {error}\n')


if __name__ == '__main__':
    main()
