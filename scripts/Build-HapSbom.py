#!/usr/bin/env python3
"""Draft a byte-verified, post-build CycloneDX 1.5 SBOM. Never release approval.

Uses the existing HAP audit, then reads ELF metadata with SDK llvm-readelf;
does not execute a packaged library. SDK filenames are observations only,
not proof that a device loader exposes those libraries or their symbols.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

import release_tools as rt

EMBEDDED = {
    'libffi.so.8': 'libffi', 'libgdbm.so.6': 'gdbm',
    'libgfortran.so.5': 'gfortran-runtime',
    'libscipy_openblas64_.so': 'numpy-openblas',
    'libscipy_openblas-80d8b5fa.so': 'scipy-openblas',
}


def props(**values):
    return [{'name': 'gsas:' + k, 'value': str(v)} for k, v in values.items()]


def elf_metadata(path, tool):
    result = subprocess.run([str(tool), '-h', '-d', '-S', str(path)],
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError('readelf failed: ' + result.stderr[-1000:])
    text = result.stdout
    if not re.search(r'Machine:\s+AArch64', text) or not re.search(r'Type:\s+DYN', text):
        raise ValueError('not an AArch64 shared object: ' + path.name)
    return {'needed': re.findall(r'\(NEEDED\).*?\[([^\]]+)\]', text),
            'soname': re.findall(r'\(SONAME\).*?\[([^\]]+)\]', text),
            'searchPaths': re.findall(r'\((?:RUNPATH|RPATH)\).*?\[([^\]]*)\]', text),
            'signatureSectionPresent': bool(re.search(r'\s\.codesign\s', text))}


def dependency_report(libraries, sdk_names):
    """Exact filenames only; a differing SONAME is not a shipped filename."""
    names = {Path(row['path']).name: row['path'] for row in libraries}
    edges = []
    for row in libraries:
        for name in row['needed']:
            status = ('packaged-filename' if name in names else
                      'sdk-filename-only' if name in sdk_names else 'unmatched')
            edges.append({'from': row['path'], 'needed': name, 'status': status,
                          'packagedTarget': names.get(name)})
    return {'releaseApproved': False, 'scope': 'static filenames, not device resolution or ABI proof',
            'libraries': libraries, 'edges': edges,
            'unmatchedNames': sorted({e['needed'] for e in edges if e['status'] == 'unmatched'}),
            'sdkNameOnly': sorted({e['needed'] for e in edges if e['status'] == 'sdk-filename-only'})}


def build_bom(inventory):
    files = inventory['files']
    owners = {c['id']: c for c in inventory['components']}
    for cid in ('app-core', 'app-fileio', 'sdk-libcxx', 'app-resources'):
        owners[cid] = {'id': cid, 'distributionReview': 'pending'}
    file_owners = {}
    for item in files:
        owner = item.get('component', 'app-resources')
        embedded = EMBEDDED.get(Path(item['path']).name)
        if embedded and item['path'].startswith('libs/'):
            owner = 'embedded-' + embedded
            owners[owner] = {'id': owner, 'distributionReview': 'pending',
                             'unverifiedParentContainer': item.get('component', '')}
        if owner not in owners:
            raise ValueError('unknown file owner: ' + owner)
        file_owners[item['path']] = owner
    refs = {cid: 'component:' + cid for cid in owners}
    entries, dependencies = [], []
    for cid, c in sorted(owners.items()):
        entry = {'type': 'library' if cid != 'app-resources' else 'application',
                 'bom-ref': refs[cid], 'name': cid,
                 'properties': props(distributionReview=c['distributionReview'])}
        if 'version' in c:
            entry['version'] = c['version']
        if c.get('license'):
            # Preserve the supplied declaration, without interpreting/approving it.
            entry['licenses'] = [{'license': {'name': c['license']}}]
            entry['properties'] += props(licenseEvidence='manifest declaration; review pending')
        else:
            entry['properties'] += props(licenseEvidence='unresolved; no parent license inherited')
        if c.get('unverifiedParentContainer'):
            entry['properties'] += props(parentContainer=c['unverifiedParentContainer'])
        if c.get('sourceCodeUrl'):
            entry['externalReferences'] = [{'type': 'vcs', 'url': c['sourceCodeUrl']}]
        for target in c.get('licenseFiles', []):
            if target not in file_owners:
                raise ValueError('license file absent from audited HAP: ' + target)
            entry['properties'] += props(licenseFile=target)
        entries.append(entry)
        deps = [refs[d] for d in c.get('dependsOn', [])]
        deps += ['file:' + p for p, owner in file_owners.items() if owner == cid]
        dependencies.append({'ref': refs[cid], 'dependsOn': sorted(deps)})
    for item in files:
        entries.append({'type': 'file', 'bom-ref': 'file:' + item['path'], 'name': item['path'],
                        'hashes': [{'alg': 'SHA-256', 'content': item['sha256']}],
                        'properties': props(size=item['size'], owner=file_owners[item['path']])})
    app = inventory['app']
    app_ref = 'application:' + app['bundleName']
    dependencies.append({'ref': app_ref, 'dependsOn': sorted(refs.values())})
    return {'bomFormat': 'CycloneDX', 'specVersion': '1.5', 'version': 1,
            'metadata': {'lifecycles': [{'phase': 'post-build'}],
                         'component': {'type': 'application', 'bom-ref': app_ref,
                                       'name': app['bundleName'], 'version': app.get('versionName', 'unknown'),
                                       'hashes': [{'alg': 'SHA-256', 'content': inventory['hapSha256']}]},
                         'properties': props(draft='true', releaseApproved='false',
                                             runtimeId=inventory.get('runtimeId', ''),
                                             scope='actual HAP bytes; source/license/ABI/signing reviews remain')},
            'components': entries, 'dependencies': dependencies}


def add_native_provenance(bom, inventory, receipt):
    """Bind static LLVM obligations to the eight audited extension hashes."""
    required = {'pyspg', 'pypowder', 'pytexture', 'fmask', 'histogram2d', 'pack_f', 'unpack_cbf', 'kvec_general'}
    rows = receipt.get('files', [])
    if (receipt.get('kind') != 'locally-built-ohos-native-extensions'
            or receipt.get('target') != 'aarch64-linux-ohos'
            or len(rows) != len(required) or {r.get('module') for r in rows} != required):
        raise ValueError('invalid native build receipt')
    actual = {row['path']: row for row in inventory['files']}
    for row in rows:
        expected_source = ('runtime/lib/python3.12/site-packages/GSASII/'
                           + row['module'] + '.cpython-312-aarch64-linux-ohos.so')
        if row.get('path') != expected_source:
            raise ValueError('invalid native build receipt source path: ' + str(row.get('path')))
        target = 'libs/arm64-v8a/' + Path(row['path']).name
        if (target not in actual or actual[target]['sha256'] != row['sha256']
                or actual[target].get('component') != 'gsas-ii'):
            raise ValueError('native build receipt does not match HAP bytes: ' + target)
    runtime = receipt['fortranRuntime']
    version = runtime['version']
    if not re.fullmatch(r'20\.1\.\d+', version) or runtime['license'] != 'Apache-2.0 WITH LLVM-exception':
        raise ValueError('unsupported FortranRuntime provenance')
    license_target = 'resources/rawfile/licenses/runtime/gsas-ii/LLVM-FortranRuntime-' + version + '-LICENSE.txt'
    if license_target not in actual:
        raise ValueError('static FortranRuntime license absent from HAP')
    ref = 'component:llvm-fortran-runtime'
    bom['components'].append({'type': 'library', 'bom-ref': ref, 'name': 'LLVM FortranRuntime and FortranDecimal',
        'version': version, 'licenses': [{'license': {'name': runtime['license']}}],
        'externalReferences': [{'type': 'vcs', 'url': 'https://github.com/llvm/llvm-project/tree/llvmorg-' + version + '/flang'}],
        'properties': props(linkage='static; referenced archive members only', distributionReview='pending',
                            licenseFile=license_target, provenance='build receipt matched to actual extension hashes')})
    owner = next((edge for edge in bom['dependencies'] if edge['ref'] == 'component:gsas-ii'), None)
    if owner is None:
        raise ValueError('GSAS-II component missing from SBOM')
    owner['dependsOn'].append(ref)
    bom['dependencies'].append({'ref': ref, 'dependsOn': []})


def generate(hap, manifest, sdk, output, native_receipt=None):
    if output.exists():
        raise ValueError('output must be a new directory')
    # Re-audit actual bytes, never trust a cached inventory.
    inventory = rt.audit_hap(hap, manifest, 'development')
    bom = build_bom(inventory)
    if native_receipt is not None:
        add_native_provenance(bom, inventory, native_receipt)
    tool = sdk / 'native/llvm/bin/llvm-readelf'
    if not tool.is_file():
        raise ValueError('SDK llvm-readelf missing')
    libs = []
    with tempfile.TemporaryDirectory(prefix='gsas-sbom-elf-') as directory, zipfile.ZipFile(hap) as archive:
        work = []
        for item in inventory['files']:
            data = archive.read(item['path'])
            if data[:4] != b'\x7fELF':
                continue
            path = Path(directory) / str(len(work))
            path.write_bytes(data)
            work.append((item, path))
        def inspect(pair):
            item, path = pair
            return {**item, **elf_metadata(path, tool)}
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            libs = list(pool.map(inspect, work))
    sdk_names = {p.name for p in (sdk / 'native/sysroot/usr/lib/aarch64-linux-ohos').glob('*.so')}
    report = dependency_report(libs, sdk_names)
    report['hapSha256'] = inventory['hapSha256']
    report['readelfSha256'] = hashlib.sha256(tool.read_bytes()).hexdigest()
    output.mkdir(parents=True)
    for name, value in [('hap-sbom.draft.cdx.json', bom), ('hap-native-dependencies.json', report),
                        ('hap-inventory.json', inventory)]:
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'fileCount': len(inventory['files']), 'nativeELFs': len(libs),
            'unmatchedNames': report['unmatchedNames'], 'releaseApproved': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hap', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--native-build-receipt', type=Path, help='Exact native-modules.json for static LLVM obligations')
    parser.add_argument('--sdk-root', type=Path,
                        default=Path('/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony'))
    args = parser.parse_args()
    try:
        print(json.dumps(generate(args.hap, json.loads(args.manifest.read_text()), args.sdk_root, args.output,
                                  json.loads(args.native_build_receipt.read_text()) if args.native_build_receipt else None)))
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f'SBOM generation failed: {error}\n')


if __name__ == '__main__':
    main()
