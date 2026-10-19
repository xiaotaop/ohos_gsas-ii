"""Host-side release preparation. No downloads, device changes, or signing."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import stat
import struct
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[1]
GSAS_COMMIT = '2b4aba1bc44de63a3da9d4495944c3b99e389399'
VERSIONS = {'cpython': '3.12.9', 'numpy': '2.2.6', 'scipy': '1.16.3',
            'pycifrw': '5.0.1', 'gsas-ii': '2.0.0'}
BASE_LIBS = {
    'libs/arm64-v8a/libgsas_core.so',
    'libs/arm64-v8a/libgsas_fileio.so',
    'libs/arm64-v8a/libc++_shared.so',
}
IGNORED_DIRS = {'build', '.cxx', '.cache', '.hvigor', '.hvigor-user', 'oh_modules',
                'node_modules', '.idea', '.preview', '__pycache__'}
PRIVATE_SUFFIXES = {'.p12', '.p7b', '.cer', '.csr', '.keystore', '.pem', '.key'}
ARCHIVE_SUFFIXES = ('.zip', '.whl', '.tar', '.gz', '.bz2', '.xz', '.7z', '.hap', '.app')


class ReleaseError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ReleaseError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.record-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read_json(path):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, f'duplicate JSON key: {key}')
            out[key] = value
        return out
    with Path(path).open(encoding='utf-8') as stream:
        return json.load(stream, object_pairs_hook=unique)


def relative_path(value):
    require(isinstance(value, str) and value, 'empty/non-string relative path')
    parts = value.split('/')
    require(not any(p in ('', '.', '..') for p in parts)
            and not any(c in value for c in '\\:')
            and not any(ord(c) < 32 for c in value), f'unsafe path: {value!r}')
    require(not any(p.endswith((' ', '.')) or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])',
                    p.split('.')[0], re.I) for p in parts), f'nonportable path: {value!r}')
    return PurePosixPath(value)


def local_file(root, name):
    rel = relative_path(name)
    root = Path(root).absolute()
    require(not root.is_symlink() and root.is_dir(), 'payload root must be a real directory')
    current = root
    for part in rel.parts:
        current = current / part
        require(not current.is_symlink(), f'symlink not allowed: {name}')
    require(current.is_file(), f'missing regular file: {name}')
    return current


def forbidden(name):
    low = name.lower()
    parts = PurePosixPath(low).parts
    require(not any(word in low for word in ('pydiffax', 'g2shapes', 'fake_core', 'ui-mock')),
            f'excluded component: {name}')
    require(not any(p in ('node_modules', '__pycache__', '.git') for p in parts),
            f'development files not allowed: {name}')
    require(not low.endswith(('.pyd', '.pyc', '.pyo', '.dll', '.dylib', '.exe', '.a', '.o') + ARCHIVE_SUFFIXES),
            f'expand archives/remove foreign or bytecode payload: {name}')
    require(PurePosixPath(low).suffix not in PRIVATE_SUFFIXES, f'signing material: {name}')
    require(not re.search(r'core-events-(success|failed|cancelled)\.json$', low),
            f'mock event fixture: {name}')


def inspect_content(name, data):
    forbidden(name)
    if name.lower().endswith('.py'):
        try:
            tree = ast.parse(data, filename=name)
        except (SyntaxError, UnicodeError) as error:
            raise ReleaseError(f'invalid Python source: {name}') from error
        for node in ast.walk(tree):
            modules = ([a.name for a in node.names] if isinstance(node, ast.Import)
                       else [node.module or ''] if isinstance(node, ast.ImportFrom) else [])
            if isinstance(node, ast.ImportFrom):
                modules += [a.name for a in node.names]
            require(not any('fake_core' in m.lower() or 'pydiffax' in m.lower()
                            or 'g2shapes' in m.lower() for m in modules),
                    f'excluded Python import: {name}')
    if name.endswith('.abc'):
        require(b'MockCoreService' not in data and b'fake_core' not in data,
                f'development core marker in compiled ArkTS: {name}')
    require(not data.startswith((b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08', b'\x1f\x8b',
                                 b'BZh', b'\xfd7zXZ\x00', b'7z\xbc\xaf\x27\x1c'))
            and data[257:262] != b'ustar',
            f'nested compressed payload must be expanded: {name}')
    if name.startswith('libs/'):
        require(name.startswith('libs/arm64-v8a/') and len(PurePosixPath(name).parts) == 3,
                f'unsupported native target: {name}')
        require(re.search(r'\.so(?:\.\d+)*$', name) is not None,
                f'unsupported native library name: {name}')
    if name.startswith('libs/') or re.search(r'\.so(?:\.\d+)*$', name):
        require(len(data) >= 64 and data[:6] == b'\x7fELF\x02\x01',
                f'expected little-endian ELF64 shared library: {name}')
        require(struct.unpack_from('<HH', data, 16) == (3, 183),
                f'expected AArch64 ET_DYN: {name}')


def source_files(root):
    root = Path(root)
    found = []
    for folder, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS)
        for d in dirs:
            require(not (Path(folder) / d).is_symlink(), 'source directory symlink not supported')
        for name in sorted(files):
            p = Path(folder) / name
            if (p.suffix.lower() in PRIVATE_SUFFIXES or p.suffix in {'.hap', '.app', '.hqf', '.pyc', '.tsbuildinfo'}
                    or name in {'local.properties', 'signing-local.json'}):
                continue
            require(not p.is_symlink() and p.is_file(), 'source must be a regular file without symlinks')
            found.append({'path': p.relative_to(root).as_posix(), 'sha256': file_hash(p)})
    return sorted(found, key=lambda item: item['path'])


def fingerprint(files):
    return digest(json.dumps(files, separators=(',', ':'), ensure_ascii=False).encode())


def stage_app(source, destination):
    files = source_files(source)
    Path(destination).mkdir(parents=True, exist_ok=False)
    for item in files:
        src = Path(source) / item['path']
        dst = Path(destination) / item['path']
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        require(file_hash(dst) == item['sha256'], 'source changed while staging; retry build')
    return files


def validate_manifest(manifest):
    require(isinstance(manifest, dict) and type(manifest.get('schemaVersion')) is int
            and manifest['schemaVersion'] == 1, 'unsupported manifest schema')
    require(manifest.get('status') == 'ready', 'runtime payload not ready; obtain files and hashes from B')
    require(manifest.get('target') == 'ohos-aarch64', 'runtime must target ohos-aarch64')
    require(isinstance(manifest.get('runtimeId'), str)
            and re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,95}', manifest['runtimeId']),
            'invalid runtimeId')
    components = manifest.get('components')
    files = manifest.get('files')
    require(isinstance(components, list) and components and isinstance(files, list) and files,
            'components/files are required')
    by_id = {}
    for c in components:
        require(isinstance(c, dict), 'invalid component')
        cid = c.get('id', '')
        require(isinstance(cid, str) and re.fullmatch(r'[a-z0-9][a-z0-9._-]*', cid)
                and cid not in by_id, 'invalid/duplicate component ID')
        forbidden(cid)
        for key in ('version', 'license'):
            require(isinstance(c.get(key), str) and c[key].strip(), f'{cid}: missing {key}')
        for key in ('sourceUrl', 'sourceCodeUrl'):
            require(isinstance(c.get(key), str) and c[key].startswith('https://')
                    and len(c[key]) > 8, f'{cid}: missing HTTPS {key}')
        require(c.get('distributionReview') in ('pending', 'approved'), f'{cid}: missing distributionReview')
        if c['distributionReview'] == 'approved':
            require(isinstance(c.get('reviewReference'), str) and c['reviewReference'].strip(),
                    f'{cid}: approved review needs a reference')
        require(isinstance(c.get('licenseFiles'), list) and c['licenseFiles'], f'{cid}: missing licenseFiles')
        deps = c.get('dependsOn', [])
        require(isinstance(deps, list) and all(isinstance(x, str) for x in deps), f'{cid}: invalid dependsOn')
        by_id[cid] = c
    for cid, version in VERSIONS.items():
        require(cid in by_id and by_id[cid]['version'] == version, f'locked component required: {cid} {version}')
    require(by_id['gsas-ii'].get('upstreamCommit') == GSAS_COMMIT, 'GSAS-II upstream commit mismatch')
    for cid, c in by_id.items():
        require(all(d in by_id and d != cid for d in c.get('dependsOn', [])), f'{cid}: unresolved dependency')
    targets, sources = {}, set()
    for f in files:
        require(isinstance(f, dict), 'invalid file record')
        src, dst = f.get('source'), f.get('target')
        relative_path(src)
        relative_path(dst)
        require(src.casefold() not in sources and dst.casefold() not in targets,
                'duplicate/case-colliding source or target')
        sources.add(src.casefold())
        targets[dst.casefold()] = f
        require(dst.startswith(('libs/arm64-v8a/', 'resources/rawfile/runtime/',
                                'resources/rawfile/licenses/runtime/')), f'unsupported target: {dst}')
        require(dst.casefold() not in {p.casefold() for p in BASE_LIBS},
                'runtime cannot replace app/SDK native libraries')
        forbidden(src)
        forbidden(dst)
        require(isinstance(f.get('component'), str) and f['component'] in by_id, f'unowned file: {dst}')
        require(isinstance(f.get('sha256'), str) and re.fullmatch('[0-9a-f]{64}', f['sha256']),
                f'missing SHA-256: {dst}')
        require(type(f.get('size')) is int and f['size'] > 0, f'missing positive size: {dst}')
    exact_targets = {f['target']: f for f in files}
    require('libs/arm64-v8a/libpython3.12.so' in exact_targets, 'missing embedded libpython3.12.so')
    require('resources/rawfile/runtime/lib/python3.12/encodings/__init__.py' in exact_targets,
            'missing CPython encodings bootstrap')
    for name in ('libs/arm64-v8a/libpython3.12.so',
                 'resources/rawfile/runtime/lib/python3.12/encodings/__init__.py'):
        require(exact_targets[name]['component'] == 'cpython', 'CPython bootstrap ownership mismatch')
    for cid, c in by_id.items():
        require(any(f['component'] == cid and not f['target'].startswith('resources/rawfile/licenses/')
                    for f in files), f'{cid}: no runtime files')
        for name in c['licenseFiles']:
            relative_path(name)
            require(name.startswith('resources/rawfile/licenses/runtime/')
                    and name in exact_targets and exact_targets[name]['component'] == cid,
                    f'{cid}: license not owned/listed in files')
    return manifest


def prepare_runtime(manifest_path, payload, output):
    manifest = validate_manifest(read_json(manifest_path))
    payload, output = Path(payload).absolute(), Path(output).absolute()
    require(not output.exists() and not output.is_symlink(), 'output exists; use a new version directory')
    require(payload != output and payload not in output.parents, 'output must be outside payload')
    expected = {f['source'] for f in manifest['files']}
    actual = set()
    for folder, dirs, files in os.walk(payload, followlinks=False):
        for name in dirs + files:
            require(not (Path(folder) / name).is_symlink(), 'payload symlinks are not allowed')
        actual.update((Path(folder) / name).relative_to(payload).as_posix() for name in files)
    require(actual == expected, 'payload differs from manifest (missing or undeclared files)')
    for f in manifest['files']:
        src = local_file(payload, f['source'])
        require(src.stat().st_size == f['size'] and file_hash(src) == f['sha256'],
                f'payload hash/size mismatch: {f["source"]}')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    try:
        for f in manifest['files']:
            src = local_file(payload, f['source'])
            dst = output / f['target']
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            require(dst.stat().st_size == f['size'] and file_hash(dst) == f['sha256'],
                    'payload changed during copy')
            inspect_content(f['target'], dst.read_bytes())
        write_json(output / 'runtime-manifest.json', manifest)
        write_json(output / 'runtime-receipt.json', {
            'schemaVersion': 1, 'runtimeId': manifest['runtimeId'],
            'manifestSha256': file_hash(output / 'runtime-manifest.json'),
            'status': 'prepared-not-device-validated', 'files': manifest['files']})
    except Exception:
        shutil.rmtree(output)
        raise
    return manifest


def install_prepared(prepared, app):
    manifest = validate_manifest(read_json(Path(prepared) / 'runtime-manifest.json'))
    receipt = read_json(Path(prepared) / 'runtime-receipt.json')
    require(receipt.get('manifestSha256') == file_hash(Path(prepared) / 'runtime-manifest.json'),
            'prepared receipt/manifest mismatch')
    for f in manifest['files']:
        src = local_file(prepared, f['target'])
        require(src.stat().st_size == f['size'] and file_hash(src) == f['sha256'], 'prepared payload changed')
        rel = ('entry/src/main/' + f['target'] if f['target'].startswith('resources/')
               else 'entry/' + f['target'])
        dst = Path(app) / rel
        require(not dst.exists() and not dst.is_symlink(), f'app payload collision: {rel}')
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        require(file_hash(dst) == f['sha256'], 'staged runtime hash mismatch')
    return manifest


def audit_hap(hap, manifest=None, mode='development'):
    require(mode in ('development', 'release'), 'unknown audit mode')
    if manifest is not None:
        validate_manifest(manifest)
    require(mode != 'release' or manifest is not None, 'release audit requires a ready runtime manifest')
    if mode == 'release':
        require(all(c['distributionReview'] == 'approved' for c in manifest['components']),
                'release audit blocked by pending distribution reviews')
    expected = {f['target']: f for f in manifest['files']} if manifest else {}
    members, case_names, inventory, metadata = {}, set(), [], None
    with zipfile.ZipFile(hap) as archive:
        infos = archive.infolist()
        require(len(infos) <= 100000 and sum(i.file_size for i in infos) <= 4 * 1024**3,
                'HAP inventory exceeds audit limits')
        for info in infos:
            name = info.filename
            relative_path(name.rstrip('/') if info.is_dir() else name)
            require(name.casefold() not in case_names, 'duplicate/case-colliding HAP entry')
            case_names.add(name.casefold())
            require(not stat.S_ISLNK(info.external_attr >> 16), f'HAP symlink: {name}')
            require(not info.flag_bits & 1, 'encrypted HAP member')
            if info.is_dir():
                continue
            require(info.file_size <= 256 * 1024**2, f'oversized HAP member: {name}')
            data = archive.read(info)
            inspect_content(name, data)
            item = {'path': name, 'size': len(data), 'sha256': digest(data)}
            if name in expected:
                f = expected[name]
                require(item['size'] == f['size'] and item['sha256'] == f['sha256'],
                        f'packaged runtime mismatch: {name}')
                item['component'] = f['component']
            elif name.startswith(('resources/rawfile/runtime/', 'resources/rawfile/licenses/runtime/')):
                raise ReleaseError(f'undeclared runtime payload: {name}')
            elif name.startswith('libs/'):
                require(name in BASE_LIBS, f'unowned native library: {name}')
                if name.endswith('libgsas_core.so'):
                    item['component'] = 'app-core'
                elif name.endswith('libgsas_fileio.so'):
                    item['component'] = 'app-fileio'
                else:
                    item['component'] = 'sdk-libcxx'
            if name == 'module.json':
                metadata = json.loads(data)
            members[name] = item
            inventory.append(item)
    require(metadata is not None and isinstance(metadata.get('app'), dict), 'HAP module.json missing/invalid')
    require(metadata['app'].get('bundleName') == 'com.gsasii.desktop', 'unexpected bundleName')
    for name in expected:
        require(name in members, f'missing packaged runtime file: {name}')
    for name in BASE_LIBS:
        require(name in members, f'missing app library: {name}')
    licenses = REPO / 'app/entry/src/main/resources/rawfile/licenses'
    for name in ('GSAS-II-LICENSE.txt', 'GSAS-II-NOTICE.txt', 'LLVM-NOTICE.txt',
                 'libcxx-LICENSE.txt', 'libcxxabi-LICENSE.txt'):
        target = f'resources/rawfile/licenses/{name}'
        require(target in members and members[target]['sha256'] == file_hash(licenses / name),
                f'missing/changed bundled license: {name}')
    if mode == 'release':
        require(metadata['app'].get('debug') is False
                and metadata['app'].get('buildMode') == 'release', 'debug HAP cannot pass release audit')
    return {'schemaVersion': 1, 'kind': 'hap-content-inventory', 'auditMode': mode,
            'contentChecksPassed': True, 'releaseCandidateApproved': False,
            'hapSha256': file_hash(hap), 'hapSize': Path(hap).stat().st_size,
            'app': metadata['app'], 'runtimeId': manifest['runtimeId'] if manifest else None,
            'components': manifest['components'] if manifest else [],
            'files': sorted(inventory, key=lambda x: x['path']),
            'limits': ['Does not prove embedded CPython loading, numerical correctness, signing validity,',
                       'device compatibility, or complete static/dynamic dependency and license review.',
                       'Compiled code inspection is limited to known development markers.']}
