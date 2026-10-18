#!/usr/bin/env python3
"""Generate a ready runtime manifest from an expanded OHOS aarch64 payload.

Member B expands the locked runtime (RUNTIME_PACKAGING.md §2) into a local
directory; this tool scans that tree, writes the device-side
``runtime/manifest.json`` consumed by RuntimeInstaller.ets on app start, and
assembles the release manifest (packaging/runtime-manifest.example.json
schema). It never downloads anything.

Expected payload layout (payload-relative):

    libs/<name>.so                  -> libs/arm64-v8a/<name>.so
    runtime/<relative>              -> resources/rawfile/runtime/<relative>
    licenses/<component-id>/<file>  -> resources/rawfile/licenses/runtime/<id>/<file>

The --components file is a JSON array of manifest component records
(id/version/sourceUrl/sourceCodeUrl/license/dependsOn/distributionReview/
upstreamCommit) plus ``payloadPrefixes``: payload-relative paths owned by
that component (longest match wins; license directories belong to their id
automatically). payloadPrefixes is tooling metadata and is stripped from the
generated manifest.

Member C's authoritative gates do the checking: release_tools.validate_manifest
(fields, locked versions, ownership, license coverage) and inspect_content
(excluded components, bytecode, archives, non-AArch64 ELF). The output is
accepted unchanged by Prepare-Runtime.py and Audit-Hap.py.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_tools as rt

DEVICE_MANIFEST = 'runtime/manifest.json'
RUNTIME_PREFIX = 'resources/rawfile/runtime/'
LICENSE_PREFIX = 'resources/rawfile/licenses/runtime/'
FULL_SCAN_LIMIT = 8 * 1024 * 1024
# Mirrors release_tools.inspect_content's magic table: large binaries are only
# header-sniffed here; Prepare-Runtime still reads every byte.
NESTED_MAGICS = (b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08', b'\x1f\x8b', b'BZh',
                 b'\xfd7zXZ\x00', b'7z\xbc\xaf\x27\x1c')
ELF_NAME = re.compile(r'\.so(?:\.\d+)*$')
RUNTIME_ID = re.compile(r'[a-z0-9][a-z0-9._-]{0,95}')


def classify(rel):
    """Map a payload-relative path to (target, forced owner or None)."""
    parts = rel.split('/')
    if parts[0] == 'libs':
        rt.require(len(parts) == 2 and parts[1].endswith('.so'),
                   f'native payload must be libs/<name>.so: {rel}')
        return f'libs/arm64-v8a/{parts[1]}', None
    if parts[0] == 'runtime':
        rt.require(len(parts) > 1, f'empty runtime path: {rel}')
        return RUNTIME_PREFIX + '/'.join(parts[1:]), None
    if parts[0] == 'licenses':
        rt.require(len(parts) == 3, f'license payload must be licenses/<component-id>/<file>: {rel}')
        return LICENSE_PREFIX + parts[1] + '/' + parts[2], parts[1]
    raise rt.ReleaseError(f'payload path outside the §2 layout: {rel}')


def walk_payload(payload):
    found = []
    for folder, dirs, names in os.walk(payload, followlinks=False):
        dirs[:] = sorted(dirs)
        for d in dirs:
            rt.require(not (Path(folder) / d).is_symlink(), 'payload directory symlink not supported')
        for name in sorted(names):
            p = Path(folder) / name
            rt.require(not p.is_symlink() and p.is_file(), f'payload entry must be a regular file: {p}')
            found.append(p.relative_to(payload).as_posix())
    return sorted(found)


def scan(payload):
    items = []
    for rel in walk_payload(payload):
        target, owner = classify(rel)
        data = (Path(payload) / rel).read_bytes()
        items.append({'rel': rel, 'target': target, 'owner': owner,
                      'sha256': rt.digest(data), 'size': len(data)})
    return items


def device_manifest_bytes(items, runtime_id):
    """The on-device index: every runtime-tree file except the index itself,
    ordered by path, with the exact §2 lowercase hash. Deterministic bytes so
    re-generation does not churn the registered hash."""
    files = [{'path': item['target'][len(RUNTIME_PREFIX):], 'sha256': item['sha256'], 'size': item['size']}
             for item in items if item['target'].startswith(RUNTIME_PREFIX) and item['rel'] != DEVICE_MANIFEST]
    files.sort(key=lambda entry: entry['path'])
    document = {'schemaVersion': 1, 'runtimeId': runtime_id, 'files': files}
    return (json.dumps(document, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')


def inspect_large(target, data):
    """Header-level stand-in for inspect_content on files over the read limit."""
    rt.forbidden(target)
    peek = data[:262]
    rt.require(not peek.startswith(NESTED_MAGICS) and peek[257:262] != b'ustar',
               f'nested compressed payload must be expanded: {target}')
    if target.startswith('libs/') or ELF_NAME.search(target):
        rt.require(len(data) >= 64 and data[:6] == b'\x7fELF\x02\x01',
                   f'expected little-endian ELF64 shared library: {target}')
        rt.require(struct.unpack_from('<HH', data, 16) == (3, 183), f'expected AArch64 ET_DYN: {target}')


def component_for(item, prefixes, known_ids):
    if item['owner'] is not None:
        rt.require(item['owner'] in known_ids, f'license directory names an unknown component: {item["owner"]}')
        return item['owner']
    if item['rel'] == DEVICE_MANIFEST:
        # The device index is part of the refinement distribution.
        rt.require('gsas-ii' in known_ids, 'device manifest requires the gsas-ii component')
        return 'gsas-ii'
    best, best_cid = '', None
    for cid, owned in prefixes.items():
        for prefix in owned:
            matched = item['rel'] == prefix or item['rel'].startswith(prefix + '/')
            if matched and len(prefix) > len(best):  # Longest (most specific) prefix wins.
                best, best_cid = prefix, cid
    rt.require(best_cid is not None, f'unmapped payload path (no component payloadPrefixes): {item["rel"]}')
    return best_cid


def generate(payload, components_path, runtime_id, output):
    payload = Path(payload)
    rt.require(payload.is_dir(), f'payload directory not found: {payload}')
    rt.require(RUNTIME_ID.fullmatch(runtime_id), 'invalid runtimeId (must match validate_manifest)')
    components = json.loads(Path(components_path).read_text(encoding='utf-8'))
    rt.require(isinstance(components, list) and components, '--components must be a JSON array of records')
    records, prefixes, known_ids = [], {}, set()
    for raw in components:
        rt.require(isinstance(raw, dict) and isinstance(raw.get('id'), str) and raw['id'],
                   f'invalid component record: {raw}')
        cid = raw['id']
        rt.require(cid not in known_ids, f'duplicate component id: {cid}')
        known_ids.add(cid)
        entry = dict(raw)
        owned = entry.pop('payloadPrefixes', [])
        rt.require(isinstance(owned, list) and all(isinstance(x, str) and x for x in owned),
                   f'{cid}: payloadPrefixes must be payload-relative paths')
        prefixes[cid] = [x.strip('/') for x in owned]
        records.append(entry)

    first = scan(payload)
    (payload / DEVICE_MANIFEST).parent.mkdir(parents=True, exist_ok=True)
    blob = device_manifest_bytes(first, runtime_id)
    runtime_entries = [item for item in first if item['target'].startswith(RUNTIME_PREFIX)
                       and item['rel'] != DEVICE_MANIFEST]
    rt.require(runtime_entries, 'payload has no runtime/ tree to activate')
    if not (payload / DEVICE_MANIFEST).exists() or (payload / DEVICE_MANIFEST).read_bytes() != blob:
        (payload / DEVICE_MANIFEST).write_bytes(blob)

    items = scan(payload)
    files = []
    for item in sorted(items, key=lambda entry: entry['target'].lower()):
        data = (payload / item['rel']).read_bytes()
        if len(data) <= FULL_SCAN_LIMIT:
            rt.inspect_content(item['target'], data)
        else:
            inspect_large(item['target'], data)
        files.append({'source': item['rel'], 'target': item['target'], 'sha256': item['sha256'],
                      'size': item['size'], 'component': component_for(item, prefixes, known_ids)})
    for record in files:  # Detect concurrent payload edits, as prepare does.
        now = rt.file_hash(payload / record['source'])
        rt.require(now == record['sha256'], f'payload changed while generating: {record["source"]}')
    for entry in records:
        entry['licenseFiles'] = sorted(item['target'] for item in files
                                       if item['component'] == entry['id']
                                       and item['target'].startswith(LICENSE_PREFIX))
    manifest = {'schemaVersion': 1, 'status': 'ready', 'runtimeId': runtime_id, 'target': 'ohos-aarch64',
                'components': records, 'files': files}
    rt.validate_manifest(manifest)
    rt.write_json(Path(output), manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload', required=True, help='Expanded B payload directory')
    parser.add_argument('--components', required=True, help='JSON array of component records with payloadPrefixes')
    parser.add_argument('--runtime-id', required=True)
    parser.add_argument('--output', required=True, help='Generated manifest; may live outside the payload')
    args = parser.parse_args()
    try:
        manifest = generate(args.payload, args.components, args.runtime_id, args.output)
    except (rt.ReleaseError, ValueError, OSError) as error:
        parser.exit(1, f'Runtime manifest failed: {error}\n')
    print(json.dumps({'runtimeId': manifest['runtimeId'], 'files': len(manifest['files']),
                      'components': [c['id'] for c in manifest['components']],
                      'deviceManifest': DEVICE_MANIFEST,
                      'status': 'manifest-generated; prepare/audit gates unchanged'}))


if __name__ == '__main__':
    main()
