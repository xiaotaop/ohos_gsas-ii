#!/usr/bin/env python3
"""Bind B's dependency declarations to actual audited HAP bytes.

This is a review report, not distribution approval. It does not run an ELF,
change a HAP, treat missing DT_NEEDED as absence of static code, or inherit a
container's license for bundled third-party libraries.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import struct
import tarfile
import tempfile
import zipfile

import release_tools as rt

SPEC = importlib.util.spec_from_file_location('hap_sbom_review', Path(__file__).with_name('Build-HapSbom.py'))
sbom = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sbom)


def license_receipts(directory):
    rows = json.loads((directory / 'SOURCES.json').read_text(encoding='utf-8'))
    receipts = {}
    for row in rows:
        name = row['file']
        if not isinstance(name, str) or PurePosixPath(name).name != name or '\\' in name or name in receipts:
            raise ValueError('unsafe or duplicate license filename')
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('license must be a regular file: ' + name)
        data = path.read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('license receipt differs from actual bytes: ' + name)
        receipts[name] = row
    return receipts


def bind_filename(source, actual):
    """A layout candidate, not proof of provenance; always retain both hashes."""
    name = PurePosixPath(source).name
    matches = [f for f in actual if f['path'].startswith('libs/') and PurePosixPath(f['path']).name == name]
    if len(matches) != 1:
        raise ValueError('expected one actual native filename: ' + name)
    return matches[0]


def defined_intl_symbols(text):
    found = set()
    for line in text.splitlines():
        cells = line.split()
        # Num Value Size Type Bind Vis Ndx Name. Undefined imports do not
        # establish bundled implementation; only defined FUNC symbols count.
        if (len(cells) >= 8 and cells[3] == 'FUNC' and cells[6] not in ('UND', 'UNDEF')
                and cells[7].startswith('libintl_')):
            found.add(cells[7])
    return sorted(found)


def allocated_sections(data):
    """Compare allocated section bytes, not addresses/debug data or signatures.

    This does not verify source patches, relocation semantics or signatures.
    The only ignored allocated section is the explicitly named .codesign.
    """
    def unpack(fmt, offset):
        if offset < 0 or offset + struct.calcsize(fmt) > len(data):
            raise ValueError('truncated ELF section table')
        return struct.unpack_from(fmt, data, offset)
    if len(data) < 64 or data[:6] != b'\x7fELF\x02\x01' or unpack('<HH', 16) != (3, 183):
        raise ValueError('expected AArch64 ELF64 shared library')
    start, = unpack('<Q', 40)
    size, count, strings_index = unpack('<HHH', 58)
    if size != 64 or not count or strings_index >= count:
        raise ValueError('invalid ELF section table')
    rows = [unpack('<IIQQQQIIQQ', start + i * size) for i in range(count)]
    def contents(row):
        offset, length = row[4:6]
        if offset + length > len(data):
            raise ValueError('ELF section outside file')
        return data[offset:offset + length]
    names = contents(rows[strings_index])
    result = {}
    for row in rows:
        if row[0] >= len(names):
            raise ValueError('ELF section name outside string table')
        end = names.find(b'\0', row[0])
        if end < 0:
            raise ValueError('unterminated ELF section name')
        name = names[row[0]:end].decode('ascii')
        if row[2] & 2 and name != '.codesign':
            if name in result:
                raise ValueError('duplicate allocated section name')
            result[name] = {'type': row[1], 'flags': row[2], 'size': row[5],
                            'sha256': None if row[1] == 8 else rt.digest(contents(row))}
    if not result:
        raise ValueError('ELF has no allocated sections')
    return result


def prebuilt_bindings(declarations, lock, directory, hap):
    wanted = {}
    for component in declarations['components']:
        for file in component.get('files', []):
            name = PurePosixPath(file['path']).name
            if name in wanted and file['sha256'] != wanted[name]['sha256']:
                raise ValueError('conflicting declared original hash: ' + name)
            wanted[name] = file
    result, seen = [], set()
    with zipfile.ZipFile(hap) as packaged:
        for item in lock['runtimeInputs']:
            if item['component'] not in ('cpython', 'numpy', 'scipy'):
                continue
            path = directory / item['name']
            if rt.file_hash(path) != item['sha256']:
                raise ValueError('prebuilt archive differs from locked hash: ' + item['name'])
            members = []
            if path.suffix == '.whl':
                with zipfile.ZipFile(path) as archive:
                    members = [(n, archive.read(n), None) for n in archive.namelist()
                               if PurePosixPath(n).name in wanted]
            else:
                with tarfile.open(path) as archive:
                    for member in archive:
                        if PurePosixPath(member.name).name not in wanted:
                            continue
                        source = member
                        if member.issym():
                            target = PurePosixPath(member.name).parent / member.linkname
                            if target.is_absolute() or '..' in target.parts:
                                raise ValueError('unsafe source alias')
                            source = archive.getmember(target.as_posix())
                        if not source.isfile():
                            raise ValueError('source library must resolve to a regular archive member')
                        members.append((member.name, archive.extractfile(source).read(),
                                        source.name if source.name != member.name else None))
            for member, data, alias in members:
                name = PurePosixPath(member).name
                if name in seen:
                    raise ValueError('duplicate original library across archives: ' + name)
                seen.add(name)
                declaration = wanted[name]
                if rt.digest(data) != declaration['sha256'] or len(data) != declaration['bytes']:
                    raise ValueError('B declared hash differs from locked original archive: ' + name)
                target = 'libs/arm64-v8a/' + name
                actual = packaged.read(target)
                original_sections, actual_sections = allocated_sections(data), allocated_sections(actual)
                result.append({'name': name, 'archive': item['name'], 'archiveSha256': item['sha256'],
                    'sourceMember': member, 'sourceAliasTarget': alias,
                    'sourceSha256': rt.digest(data), 'matchesBHash': True,
                    'actualHapTarget': target, 'actualHapSha256': rt.digest(actual),
                    'allocatedSectionsSameExceptCodesign': original_sections == actual_sections,
                    'differingSections': sorted(k for k in set(original_sections) | set(actual_sections)
                                               if original_sections.get(k) != actual_sections.get(k)),
                    'scope': 'locked prebuilt-to-HAP allocated section comparison; not corresponding source or license approval'})
    if seen != set(wanted):
        raise ValueError('declared original libraries missing from archives: ' + ', '.join(sorted(set(wanted) - seen)))
    return result


def generate(hap, manifest, declarations, directory, sdk, output, prebuilt_dir=None):
    if output.exists():
        raise ValueError('output must be a new directory')
    receipts = license_receipts(directory)
    inventory = rt.audit_hap(hap, manifest, 'development')
    actual = inventory['files']
    tool = sdk / 'native/llvm/bin/llvm-readelf'
    if not tool.is_file():
        raise ValueError('SDK llvm-readelf missing')
    components, findings, versions, extra = [], [], [], []
    with zipfile.ZipFile(hap) as archive, tempfile.TemporaryDirectory(prefix='gsas-third-party-elf-') as tmp:
        libraries, paths, blobs = [], {}, {}
        for f in actual:
            if f['path'].startswith('libs/'):
                data = archive.read(f['path'])
                if data[:4] != b'\x7fELF':
                    continue
                path = Path(tmp) / str(len(paths))
                path.write_bytes(data)
                paths[f['path']] = path
                blobs[f['path']] = data
                libraries.append(f)
        def inspect(f):
            return {**f, **sbom.elf_metadata(paths[f['path']], tool)}
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            libraries = list(pool.map(inspect, libraries))
        sdk_names = {p.name for p in (sdk / 'native/sysroot/usr/lib/aarch64-linux-ohos').glob('*.so')}
        graph = sbom.dependency_report(libraries, sdk_names)
        for comp in declarations['components']:
            row = {'id': comp['id'], 'declaredVersion': comp['version'],
                   'declaredLinkMode': comp['linkMode'], 'declaredStatus': comp['status'],
                   'distributionReview': 'pending', 'sourceDeclaration': comp.get('source', {}),
                   'bindings': [], 'consumers': []}
            for file in comp.get('files', []):
                target = bind_filename(file['path'], actual)
                row['bindings'].append({'declaredPath': file['path'], 'declaredSha256': file['sha256'],
                    'declaredSize': file['bytes'], 'actualPath': target['path'],
                    'actualSha256': target['sha256'], 'actualSize': target['size'],
                    'byteIdentical': file['sha256'] == target['sha256'] and file['bytes'] == target['size'],
                    'scope': 'basename layout association only; transformation provenance not approved'})
            for name in comp.get('consumers', []):
                candidates = [f for f in libraries if PurePosixPath(f['path']).name == name]
                row['consumers'] += [{'path': f['path'], 'sha256': f['sha256']} for f in candidates]
            declaration = comp.get('license', {})
            text_name = PurePosixPath(declaration.get('text', '')).name
            if text_name in receipts:
                receipt = receipts[text_name]
                targets = [f['path'] for f in actual if f['sha256'] == receipt['sha256'] and f['size'] == receipt['bytes']]
                row['licenseText'] = {'file': text_name, 'sha256': receipt['sha256'],
                    'matchesBReceipt': True, 'actualHapTargets': targets,
                    'scope': 'repository text matches SOURCES.json; not proof of prebuilt-library source/patches'}
                if not targets:
                    findings.append({'id': 'license-not-in-hap', 'component': comp['id'],
                                     'file': text_name, 'status': 'open'})
            components.append(row)
        libpython = bind_filename('libpython3.12.so', actual)
        symbols = subprocess.run([str(tool), '-Ws', str(paths[libpython['path']])],
                                 capture_output=True, text=True, check=True, timeout=30).stdout
        intl = defined_intl_symbols(symbols)
        if intl:
            extra.append({'id': 'gettext-libintl', 'consumer': libpython['path'],
                'consumerSha256': libpython['sha256'], 'definedFunctionSymbols': intl,
                'version': 'unverified', 'distributionReview': 'pending'})
            findings.append({'id': 'gettext-source-license-incomplete', 'status': 'open',
                'evidence': 'actual libpython defines libintl functions, not undefined imports; no DT_NEEDED cannot exclude static code'})
        readline = bind_filename('readline.cpython-312-aarch64-linux-ohos.so', actual)
        if b'EditLine wrapper' in blobs[readline['path']]:
            extra.append({'id': 'libedit', 'consumer': readline['path'],
                          'consumerSha256': readline['sha256'], 'marker': 'EditLine wrapper',
                          'version': 'unverified', 'distributionReview': 'pending'})
            if not any(c['id'] == 'libedit' and c.get('license', {}).get('spdx') != 'NOASSERTION' for c in declarations['components']):
                findings.append({'id': 'libedit-source-license-incomplete', 'status': 'open',
                                 'evidence': 'actual readline extension identifies EditLine; exact version/source/license not supplied'})
        for name, marker in [('openssl', b'OpenSSL 1.1.1w  11 Sep 2023'), ('sqlite', b'3.49.1\x00'),
                             ('bzip2', b'1.0.8, 13-Jul-2019'), ('xz', b'5.8.2\x00'),
                             ('ncurses', b'ncurses 6.6.20251230'), ('expat', b'expat_2.6.4'),
                             ('libmpdec', b'2.5.1\x00')]:
            component = next(c for c in components if c['id'] == name)
            observed = [f for f in component['consumers'] if marker in blobs[f['path']]]
            versions.append({'id': name, 'literalVersionMarker': marker.rstrip(b'\0').decode(),
                             'observedIn': observed, 'scope': 'literal bytes only; not complete build or patch provenance'})
        candidates = {'libscipy_openblas64_.so', 'libgfortran.so.5'}
        outside = [e for e in graph['edges'] if e['needed'] in candidates and PurePosixPath(e['from']).name not in candidates]
        references = []
        for f in actual:
            if f['path'].startswith('resources/rawfile/runtime/') and f['path'].endswith(('.py', '.json')):
                data = archive.read(f['path'])
                for name in candidates:
                    if name.encode() in data:
                        references.append({'path': f['path'], 'name': name, 'sha256': f['sha256']})
        removal = {'candidateNames': sorted(candidates), 'externalNeededConsumers': outside,
                   'exactPythonJsonReferences': references, 'removalApproved': False,
                   'scope': 'static experiment evidence only; no deletion, re-signing or device revalidation performed'}
        findings.append({'id': 'prebuilt-source-build-patch-evidence-incomplete', 'status': 'open',
                         'evidence': 'B explicitly records unprovided community prebuilt build recipes/patches'})
        findings.append({'id': 'scipy-static-fortran-runtime-unresolved', 'status': 'open',
                         'evidence': 'NEEDED libc only does not identify a statically linked runtime or its version/license'})
    original_bindings = prebuilt_bindings(declarations, json.loads((Path(__file__).parent / 'ohos/local-cross/sources.lock.json').read_text()), prebuilt_dir, hap) if prebuilt_dir else []
    report = {'prebuiltOriginalBindings': original_bindings, 'schemaVersion': 1, 'kind': 'actual-HAP-third-party-review',
              'hapSha256': inventory['hapSha256'], 'declarationsCanonicalJsonSha256': rt.digest(json.dumps(declarations, sort_keys=True).encode()),
              'licenseReceiptsVerified': len(receipts), 'nativeELFs': len(libraries),
              'components': components, 'versionObservations': versions,
              'additionalEmbeddedCandidates': extra, 'removalEvidence': removal,
              'unmatchedNames': graph['unmatchedNames'], 'findings': findings,
              'releaseApproved': False, 'step2Complete': False}
    output.mkdir(parents=True)
    rt.write_json(output / 'third-party-review.json', report)
    rt.write_json(output / 'native-dependencies.json', graph)
    return report


def main():
    repo = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hap', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--declarations', type=Path, default=repo / 'packaging/third-party.dependencies.json')
    p.add_argument('--license-dir', type=Path, default=repo / 'packaging/licenses/third-party')
    p.add_argument('--sdk-root', type=Path, default=Path('/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony'))
    p.add_argument('--prebuilt-dir', type=Path, help='Optional directory of locked original CPython/NumPy/SciPy archives')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    try:
        report = generate(a.hap, json.loads(a.manifest.read_text()), json.loads(a.declarations.read_text()),
                          a.license_dir, a.sdk_root, a.output, a.prebuilt_dir)
        print(json.dumps({'reportGenerated': True, 'licenseReceiptsVerified': report['licenseReceiptsVerified'],
                          'findings': sorted({f['id'] for f in report['findings']}), 'releaseApproved': False}))
    except (ValueError, OSError, KeyError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        p.exit(1, f'Third-party review failed: {error}\n')


if __name__ == '__main__':
    main()
