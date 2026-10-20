#!/usr/bin/env python3
"""Stage a NEW experiment without two orphan libraries; never release approval.

Keeps the source payload and all license texts. Rejects external DT_NEEDED,
ELF filename literals and Python/JSON filename references before copying.
Dynamic filename construction still requires device revalidation afterwards.
"""
import argparse
import concurrent.futures
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

SPEC = importlib.util.spec_from_file_location('prune_sbom', Path(__file__).with_name('Build-HapSbom.py'))
sbom = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sbom)

CANDIDATES = {'libscipy_openblas64_.so', 'libgfortran.so.5'}


def check_references(libraries, references):
    outside = [{'from': row['path'], 'needed': name} for row in libraries
               if Path(row['path']).name not in CANDIDATES
               for name in row['needed'] if name in CANDIDATES]
    if outside or references:
        raise ValueError('orphan removal blocked by external dependency or filename reference')


def stage(source, output, sdk):
    source, output = source.resolve(), output.resolve()
    if not source.is_dir() or output.exists() or source == output or source in output.parents or output in source.parents:
        raise ValueError('source and NEW output must be separate trees')
    files = sorted(p for p in source.rglob('*') if p.is_file())
    if any(p.is_symlink() for p in source.rglob('*')):
        raise ValueError('payload symlinks are not supported')
    paths = [source / 'libs' / name for name in sorted(CANDIDATES)]
    if not all(p.is_file() for p in paths):
        raise ValueError('both candidate libraries must exist at payload libs/')
    tool = sdk / 'native/llvm/bin/llvm-readelf'
    if not tool.is_file():
        raise ValueError('SDK llvm-readelf missing')
    hashes = {p.relative_to(source).as_posix(): sbom.rt.file_hash(p) for p in files}
    native = [p for p in files if p.parent == source / 'libs']
    def inspect(p):
        return {'path': p.relative_to(source).as_posix(), **sbom.elf_metadata(p, tool)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        libraries = list(pool.map(inspect, native))
    references = []
    for p in files:
        if p.name in CANDIDATES or p.relative_to(source).as_posix() == 'runtime/manifest.json':
            continue  # Generated index is replaced by Write-RuntimeManifest.
        if p in native or p.suffix in ('.py', '.json'):
            data = p.read_bytes()
            for name in sorted(CANDIDATES):
                if name.encode() in data:
                    references.append({'path': p.relative_to(source).as_posix(), 'name': name})
    check_references(libraries, references)
    removed = [{'path': p.relative_to(source).as_posix(), 'size': p.stat().st_size,
                'sha256': hashes[p.relative_to(source).as_posix()]} for p in paths]
    with tempfile.TemporaryDirectory(prefix='gsas-prune-stage-', dir=output.parent) as tmp:
        work = Path(tmp) / 'payload'
        shutil.copytree(source, work)
        for rel, digest in hashes.items():
            if sbom.rt.file_hash(source / rel) != digest or sbom.rt.file_hash(work / rel) != digest:
                raise ValueError('payload changed while copying')
        for row in removed:
            (work / row['path']).unlink()
        work.rename(output)
    return {'kind': 'orphan-removal-experiment', 'removed': removed,
            'uncompressedBytesRemoved': sum(r['size'] for r in removed),
            'externalNeededConsumers': [], 'externalFilenameReferences': [],
            'sourceTreeUnchanged': True, 'deviceValidated': False, 'releaseApproved': False,
            'scope': 'derived payload only; regenerate manifests, re-sign/audit actual HAP and validate on device'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--payload', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--receipt', type=Path, required=True, help='New receipt path outside both payload trees')
    p.add_argument('--sdk-root', type=Path, default=Path('/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony'))
    a = p.parse_args()
    try:
        receipt = a.receipt.resolve()
        if receipt.exists() or any(receipt == root.resolve() or root.resolve() in receipt.parents for root in (a.payload, a.output)):
            raise ValueError('receipt must be a new path outside payload trees')
        report = stage(a.payload, a.output, a.sdk_root)
        receipt.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(report))
    except (ValueError, OSError) as error:
        p.exit(1, f'Orphan experiment failed: {error}\n')


if __name__ == '__main__':
    main()
