#!/usr/bin/env python3
"""Observe original SciPy ELF provenance and bind it to an audited HAP.

Never executes a library or infers a runtime from DT_NEEDED absence. Original
FILE symbols/compiler comments are observations, not complete build recipes.
"""
import argparse
import concurrent.futures
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

HERE = Path(__file__).parent
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

review = module('scientific_review', HERE / 'Audit-ThirdParty.py')
normalize = module('scientific_needed', HERE / 'ohos/Normalize-PythonNeeded.py')


def symbol_observations(text, comment):
    rows = [line.split() for line in text.splitlines() if len(line.split()) >= 8]
    defined = sorted({r[7] for r in rows if r[3] == 'FUNC' and r[6] not in ('UND', 'UNDEF')
                      and r[7].startswith(('_FortranA', '_gfortran_'))})
    files = sorted({r[7] for r in rows if r[3] == 'FILE'})
    return {'definedLLVMFortranFunctions': [n for n in defined if n.startswith('_FortranA')],
            'definedGNUFortranFunctions': [n for n in defined if n.startswith('_gfortran_')],
            'compilerFlangVersions': sorted(set(re.findall(r'flang version ([0-9]+\.[0-9]+\.[0-9]+)', comment))),
            'sourceFileCount': len(files),
            'sourceSuffixCounts': {suffix: sum(Path(n).suffix.lower() == suffix for n in files)
                                   for suffix in sorted({Path(n).suffix.lower() for n in files})},
            'runtimeSourceFiles': [n for n in files if n in ('ISO_Fortran_binding.cpp', 'assign.cpp',
                'decimal-to-binary.cpp', 'binary-to-decimal.cpp', 'descriptor.cpp', 'io-api.cpp')],
            'lapackCSourceExamples': [n for n in files if n in ('dgeev.c', 'dgesdd.c', 'zgeev.c', 'zpotrf.c')]}


def generate(hap, manifest, archives, sdk, output):
    if output.exists():
        raise ValueError('output must be new')
    inventory = review.rt.audit_hap(hap, manifest, 'development')
    lock = json.loads((HERE / 'ohos/local-cross/sources.lock.json').read_text())
    locked = next(r for r in lock['runtimeInputs'] if r['component'] == 'scipy')
    wheel = archives / locked['name']
    if review.rt.file_hash(wheel) != locked['sha256']:
        raise ValueError('SciPy wheel differs from locked hash')
    tool = sdk / 'native/llvm/bin/llvm-readelf'
    if not tool.is_file():
        raise ValueError('SDK llvm-readelf missing')
    with zipfile.ZipFile(hap) as packaged, zipfile.ZipFile(wheel) as original, tempfile.TemporaryDirectory(prefix='gsas-scientific-') as tmp:
        mapping = json.loads(packaged.read('resources/rawfile/runtime/bridge/native-module-map.json'))['modules']
        work = []
        for name in original.namelist():
            if not name.endswith('.so'):
                continue
            if name.startswith('scipy.libs/'):
                target = Path(name).name
            else:
                qualified = name.split('.cpython-', 1)[0].replace('/', '.')
                target = mapping.get(qualified)
                if target is None:
                    continue  # Original wheel tests absent from the actual payload.
            actual_path = 'libs/arm64-v8a/' + target
            data = original.read(name)
            expected, edits = normalize.normalize(data)
            actual = packaged.read(actual_path)
            if review.allocated_sections(expected) != review.allocated_sections(actual):
                raise ValueError('unexpected allocated-section changes: ' + name)
            path = Path(tmp) / str(len(work))
            path.write_bytes(data)
            work.append((name, path, actual_path, review.rt.digest(data), review.rt.digest(actual), edits))
        def inspect(row):
            name, path, target, source_hash, actual_hash, edits = row
            symbols = subprocess.run([str(tool), '-Ws', str(path)], capture_output=True, text=True, check=True, timeout=30).stdout
            comment = subprocess.run([str(tool), '-p', '.comment', str(path)], capture_output=True, text=True, check=True, timeout=30).stdout
            return {'sourceMember': name, 'sourceSha256': source_hash, 'actualHapTarget': target,
                    'actualHapSha256': actual_hash, 'allocatedSectionsMatchAfterExactPythonNeededNormalization': True,
                    'neededEdits': edits, **symbol_observations(symbols, comment)}
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            records = list(pool.map(inspect, work))
    report = {'schemaVersion': 1, 'kind': 'actual-HAP-original-SciPy-ELF-observations',
              'hapSha256': inventory['hapSha256'], 'scipyWheelSha256': locked['sha256'],
              'records': records, 'llvmFortranConsumers': [r['actualHapTarget'] for r in records if r['definedLLVMFortranFunctions']],
              'scope': 'original symbol/compiler observations bound to actual HAP allocated sections; no exact static archive hash or complete source/build proof',
              'releaseApproved': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    review.rt.write_json(output, report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hap', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--prebuilt-dir', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--sdk-root', type=Path, default=Path('/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony'))
    a = p.parse_args()
    try:
        r = generate(a.hap, json.loads(a.manifest.read_text()), a.prebuilt_dir, a.sdk_root, a.output)
        print(json.dumps({'librariesBound': len(r['records']), 'llvmFortranConsumers': len(r['llvmFortranConsumers']), 'releaseApproved': False}))
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        p.exit(1, f'Scientific audit failed: {error}\n')


if __name__ == '__main__':
    main()
