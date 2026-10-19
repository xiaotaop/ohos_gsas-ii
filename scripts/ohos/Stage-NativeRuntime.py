#!/usr/bin/env python3
"""Copy a signed runtime and move its ELF libraries to HAP native targets.

Keeps each library's bytes intact. Names of dependency libraries are preserved;
only colliding Python-extension names are disambiguated, with an import map.
Produces a derived component manifest so ownership and hashes stay auditable.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bridge.native_loader import validate_map, validate_namespaces


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage(source, destination, components, loader):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_dir() or destination.exists() or source == destination:
        raise ValueError('input must exist and output must be a new directory')
    if source in destination.parents or destination in source.parents:
        raise ValueError('input and output must be separate trees')
    if not any(component.get('id') == 'bridge' for component in components):
        raise ValueError('bridge component is required for the native import map')
    previous = source / 'runtime/bridge/native-module-map.json'
    try:
        prior_document = json.loads(previous.read_text(encoding='utf-8')) if previous.exists() else {'schemaVersion': 1, 'modules': {}}
        prior_modules = validate_map(prior_document)
        namespaces = set(validate_namespaces(prior_document, prior_modules))
    except (ImportError, ValueError) as error:
        raise ValueError(f'invalid existing native map: {error}') from error
    prior_by_file = {filename: module for module, filename in prior_modules.items()}
    records, discarded = [], []
    for item in sorted(source.rglob('*')):
        if item.is_symlink():
            raise ValueError('symlinks are not supported')
        if not item.is_file():
            continue
        with item.open('rb') as stream:
            header = stream.read(64)
        if header[:4] != b'\x7fELF':
            continue
        rel = item.relative_to(source).as_posix()
        if len(header) < 64 or header[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<HH', header, 16) != (3, 183):
            raise ValueError(f'not an AArch64 ELF64 shared library: {rel}')
        if rel.endswith('.so.t') and (source / rel[:-2]).is_file():
            discarded.append({'source': rel, 'sha256': sha(item), 'reason': 'non-importable temporary .so.t duplicate'})
            continue
        if not re.search(r'\.so(?:\.\d+)*$', item.name):
            raise ValueError(f'unclassified ELF filename: {rel}')
        module = prior_by_file.get(item.name) if item.parent == source / "libs" else None
        if '/site-packages/' in rel and '.cpython-' in item.name:
            module_path = rel.split('/site-packages/', 1)[1].split('.cpython-', 1)[0]
            module = module_path.replace('/', '.')
            if not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*', module):
                raise ValueError(f'invalid extension module path: {rel}')
        matches = [(len(prefix), component) for component in components
                   for prefix in component['payloadPrefixes']
                   if rel == prefix or rel.startswith(prefix.rstrip('/') + '/')]
        if not matches:
            raise ValueError(f'no component owns {rel}')
        owner = max(matches, key=lambda pair: pair[0])[1]['id']
        records.append({'source': rel, 'name': item.name, 'module': module,
                        'component': owner, 'sha256': sha(item), 'size': item.stat().st_size})
    seen_prior = {row['module'] for row in records if row['source'].startswith('libs/')}
    if set(prior_modules) - seen_prior:
        raise ValueError('existing native map references missing or non-ELF libraries')
    if not records:
        raise ValueError('no ELF libraries to stage')
    names = Counter(row['name'].casefold() for row in records)
    modules, targets = {}, set()
    for row in records:
        name = row['name']
        if names[name.casefold()] > 1:
            if row['module'] is None:
                raise ValueError(f'colliding dependency identity: {name}')
            name = 'libgsas_pyext_' + hashlib.sha256(row['source'].encode()).hexdigest()[:20] + '.so'
        target = 'libs/' + name
        if target.casefold() in targets:
            raise ValueError('colliding native target')
        targets.add(target.casefold())
        row['target'] = target
        if row['module'] is not None:
            if row['module'] in modules:
                raise ValueError('duplicate extension module')
            modules[row['module']] = name
    site = source / 'runtime/lib/python3.12/site-packages'
    for module in modules:
        parts = module.split('.')
        for count in range(1, len(parts)):
            package = site.joinpath(*parts[:count])
            if package.is_dir() and not (package / '__init__.py').is_file():
                namespaces.add('.'.join(parts[:count]))
    shutil.copytree(source, destination)
    for row in discarded:
        (destination / row['source']).unlink()
    by_id = {component['id']: component for component in components}
    for row in records:
        src, dst = destination / row['source'], destination / row['target']
        if src != dst:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src, dst)
        if sha(dst) != row['sha256']:
            raise ValueError('library bytes changed during relocation')
        prefixes = by_id[row['component']]['payloadPrefixes']
        if row['target'] not in prefixes:
            prefixes.append(row['target'])
    (destination / 'runtime/bridge').mkdir(parents=True, exist_ok=True)
    (destination / 'runtime/bridge/native-module-map.json').write_text(
        json.dumps({'schemaVersion': 1, 'modules': modules, 'namespacePackages': sorted(namespaces)}, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
    shutil.copyfile(loader, destination / 'runtime/bridge/native_loader.py')
    return {'schemaVersion': 1, 'kind': 'HAP-native-runtime-layout', 'releaseApproved': False,
            'input': str(source), 'output': str(destination), 'libraries': records,
            'mappedPythonExtensions': len(modules), 'discarded': discarded,
            'nativeLibBuildOption': {'collectAllLibs': True, 'debugSymbol': {'strip': True,
                'exclude': ['**/' + row['target'].split('/')[-1] for row in records]}}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--components', type=Path, required=True)
    parser.add_argument('--components-output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.components_output.resolve() == args.report.resolve():
            raise ValueError('component output and receipt must be different files')
        for path in (args.components_output, args.report):
            resolved = path.resolve()
            if (path.exists() or resolved in (args.input.resolve(), args.output.resolve())
                    or args.output.resolve() in resolved.parents or args.input.resolve() in resolved.parents):
                raise ValueError('component output and report must be new, outside payload trees')
        components = json.loads(args.components.read_text(encoding='utf-8'))
        receipt = stage(args.input, args.output, components, ROOT / 'bridge/native_loader.py')
        args.components_output.parent.mkdir(parents=True, exist_ok=True)
        args.components_output.write_text(json.dumps(components, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'nativeLibraries': len(receipt['libraries']),
                          'mappedPythonExtensions': receipt['mappedPythonExtensions'],
                          'discardedTemporaryFiles': len(receipt['discarded']),
                          'releaseApproved': False}))
        return 0
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f'Native runtime staging failed: {error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
