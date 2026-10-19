#!/usr/bin/env python3
"""Retarget OHOS CPython 3.12 consumers to the shipped interpreter filename.

Copies the input tree. Only exact DT_NEEDED libpython3.12.so.1.0 entries are
shortened, never a blind byte replacement, alias or second interpreter. Modified
ELFs MUST be stripped and signed again before Stage-NativeRuntime and manifest
freeze. This does not prove ABI compatibility: run actual target import/science.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct

OLD = b'libpython3.12.so.1.0'
NEW = b'libpython3.12.so'


def normalize(data):
    data = bytearray(data)
    def unpack(fmt, offset):
        if offset < 0 or offset + struct.calcsize(fmt) > len(data):
            raise ValueError('truncated ELF structure')
        return struct.unpack_from(fmt, data, offset)
    if len(data) < 64 or data[:6] != b'\x7fELF\x02\x01' or unpack('<HH', 16) != (3, 183):
        raise ValueError('expected AArch64 ELF64 shared library')
    phoff, = unpack('<Q', 32)
    phsize, count = unpack('<HH', 54)
    if phsize != 56 or not count or count > 1024:
        raise ValueError('invalid program header table')
    loads, dynamic = [], []
    for i in range(count):
        kind, _, off, address, _, size, _, _ = unpack('<IIQQQQQQ', phoff + i * phsize)
        if off + size > len(data):
            raise ValueError('segment outside ELF')
        if kind == 1:
            loads.append((address, off, size))
        elif kind == 2:
            dynamic.append((off, size))
    if len(dynamic) != 1:
        raise ValueError('expected one dynamic segment')
    start, size = dynamic[0]
    tags = []
    for offset in range(start, start + size, 16):
        tag, value = unpack('<QQ', offset)
        if tag == 0:
            break
        tags.append((tag, value))
    else:
        raise ValueError('unterminated dynamic table')
    addresses = [v for t, v in tags if t == 5]
    lengths = [v for t, v in tags if t == 10]
    if len(addresses) != 1 or len(lengths) != 1:
        raise ValueError('missing dynamic string table')
    bases = [off + addresses[0] - va for va, off, n in loads
             if va <= addresses[0] and addresses[0] + lengths[0] <= va + n]
    if len(bases) != 1:
        raise ValueError('invalid dynamic string range')
    base, length = bases[0], lengths[0]
    changes = []
    for tag, index in tags:
        if tag != 1:
            continue
        if index >= length:
            raise ValueError('DT_NEEDED outside dynamic strings')
        end = data.find(0, base + index, base + length)
        if end < 0:
            raise ValueError('unterminated dependency name')
        if data[base + index:end] == OLD:
            # Preserve layout and offsets, including the original trailing NUL.
            data[base + index:end] = NEW + b'\0' * (len(OLD) - len(NEW))
            changes.append({'offset': base + index, 'old': OLD.decode(), 'new': NEW.decode()})
    return bytes(data), changes


def prepare(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_dir() or output.exists() or source == output or source in output.parents or output in source.parents:
        raise ValueError('input and new output must be separate trees')
    if not (source / 'libs/libpython3.12.so').is_file():
        raise ValueError('canonical interpreter libs/libpython3.12.so is absent')
    records, edits = [], {}
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise ValueError('symlinks are not supported')
        if not path.is_file():
            continue
        original = path.read_bytes()
        if not original.startswith(b'\x7fELF'):
            continue
        data, changes = normalize(original)
        if changes:
            rel = path.relative_to(source).as_posix()
            edits[rel] = data
            records.append({'path': rel, 'beforeSha256': hashlib.sha256(original).hexdigest(),
                            'afterSha256': hashlib.sha256(data).hexdigest(), 'changes': changes})
    shutil.copytree(source, output)
    for rel, data in edits.items():
        (output / rel).write_bytes(data)
    # The old manifest describes the original bytes, never the derived tree.
    (output / 'runtime/manifest.json').unlink(missing_ok=True)
    return {'schemaVersion': 1, 'releaseApproved': False, 'requiresResigning': bool(records), 'files': records}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    args = p.parse_args()
    try:
        report = args.report.resolve()
        if report.exists() or any(report == root.resolve() or root.resolve() in report.parents for root in (args.input, args.output)):
            raise ValueError('receipt must be a new file outside payload trees')
        result = prepare(args.input, args.output)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({'modifiedConsumers': len(result['files']), 'requiresResigning': result['requiresResigning']}))
    except (OSError, ValueError) as error:
        p.exit(1, f'Normalization failed: {error}\n')


if __name__ == '__main__':
    main()
