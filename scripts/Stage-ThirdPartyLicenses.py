#!/usr/bin/env python3
"""Copy verified license texts into a NEW payload; never approve distribution."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

SPEC = importlib.util.spec_from_file_location('third_party_licenses', Path(__file__).with_name('Audit-ThirdParty.py'))
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)

OWNERS = {'libffi': 'cpython', 'GDBM': 'cpython', 'OpenSSL': 'cpython', 'SQLite': 'cpython',
          'bzip2': 'cpython', 'XZ/liblzma': 'cpython', 'ncurses': 'cpython', 'Expat': 'cpython',
          'libmpdec': 'cpython', 'OpenBLAS': 'scipy', 'GCC Runtime (libgfortran)': 'numpy',
          'GNU Readline': 'cpython', 'GNU gettext libintl': 'cpython'}


def stage(source, output, directory):
    source, output, directory = source.resolve(), output.resolve(), directory.resolve()
    if not source.is_dir() or output.exists() or source == output or source in output.parents or output in source.parents:
        raise ValueError('source and NEW output must be separate trees')
    receipts = review.license_receipts(directory)
    targets = {}
    for name, row in receipts.items():
        owner = OWNERS.get(row['component'])
        if not owner:
            raise ValueError('explicit payload license owner required: ' + row['component'])
        target = 'licenses/' + owner + '/' + name
        if (source / target).exists():
            raise ValueError('license already in source; no replacement allowed')
        targets[name] = (owner, target)
    if any(p.is_symlink() for p in source.rglob('*')):
        raise ValueError('payload symlinks are not supported')
    with tempfile.TemporaryDirectory(prefix='gsas-license-stage-', dir=output.parent) as temp:
        work = Path(temp) / 'payload'
        shutil.copytree(source, work)
        by_owner = {}
        for name, (owner, target) in targets.items():
            dest = work / target
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(directory / name, dest)
            # Re-check after copying; do not trust mutable input files.
            if review.rt.file_hash(dest) != receipts[name]['sha256']:
                raise ValueError('license changed while staging')
            by_owner.setdefault(owner, []).append(receipts[name])
        for owner, rows in by_owner.items():
            index = work / 'licenses' / owner / 'THIRD-PARTY-SOURCES.json'
            if index.exists():
                raise ValueError('existing third-party index cannot be overwritten')
            index.write_text(json.dumps({'scope': 'license texts only; parent component ownership is not license inheritance',
                'distributionReview': 'pending', 'sources': rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        work.rename(output)
    return {'licenseTextsStaged': len(targets), 'targets': [t for _, t in targets.values()],
            'distributionReview': 'pending', 'releaseApproved': False,
            'scope': 'derived payload only; regenerate device/packaging manifests and re-sign/re-audit the actual HAP before use'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--payload',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--license-dir',type=Path,default=Path(__file__).resolve().parents[1]/'packaging/licenses/third-party')
    a=p.parse_args()
    try:
        print(json.dumps(stage(a.payload,a.output,a.license_dir),ensure_ascii=False))
    except (ValueError,OSError,KeyError) as error:
        p.exit(1,f'License staging failed: {error}\n')


if __name__=='__main__':
    main()
