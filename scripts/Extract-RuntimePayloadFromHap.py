#!/usr/bin/env python3
"""Recover the exact manifest-declared runtime payload from a reviewed HAP.

This does not copy the HAP signature, sign a new package, or grant release
approval. It is only a verified input for a fresh local source build.
"""
import argparse
from pathlib import Path
import zipfile

import release_tools as rt


def extract(hap, manifest_path, output):
    manifest = rt.validate_manifest(rt.read_json(manifest_path))
    output = Path(output).resolve()
    rt.require(not output.exists(), 'output exists; choose a new directory')
    output.mkdir(parents=True)
    with zipfile.ZipFile(hap) as archive:
        for row in manifest['files']:
            target = row['target']
            try:
                data = archive.read(target)
            except KeyError as error:
                raise rt.ReleaseError(f'missing HAP runtime member: {target}') from error
            rt.require(len(data) == row['size'] and rt.digest(data) == row['sha256'],
                       f'HAP runtime member differs from manifest: {target}')
            source = output / rt.relative_path(row['source'])
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(data)
    print(f'Verified and extracted {len(manifest["files"])} runtime files to {output}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hap', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    extract(args.hap, args.manifest, args.output)


if __name__ == '__main__':
    main()
