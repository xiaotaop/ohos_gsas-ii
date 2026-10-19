#!/usr/bin/env python3
"""Copy an ARM64 payload, strip its ELF libraries, and apply development self-signatures.

Uses the installed DevEco SDK. No account, certificate, private key or network is
used. This is not release signing. Generate runtime manifests AFTER this step.
Keep signed prebuilt libraries out of Hvigor's later strip pass.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv: list[str]) -> str:
    result = subprocess.run(argv, capture_output=True, text=True, timeout=90)
    output = result.stdout + result.stderr
    if result.returncode:
        raise ValueError(f'{Path(argv[0]).name} exit {result.returncode}: {output[-3000:]}')
    return output


def elf_info(path: Path, readelf: Path) -> dict:
    header = path.read_bytes()[:64]
    if len(header) < 64 or header[:6] != b'\x7fELF\x02\x01':
        raise ValueError(f'not ELF64 little-endian: {path}')
    kind, machine = struct.unpack_from('<HH', header, 16)
    if kind != 3 or machine != 183:
        raise ValueError(f'not AArch64 ET_DYN: {path}')
    dynamic = run([str(readelf), '-d', str(path)])
    return {'machine': machine, 'elfType': kind,
            'needed': re.findall(r'\(NEEDED\).*?\[([^\]]+)\]', dynamic),
            'soname': re.findall(r'\(SONAME\).*?\[([^\]]+)\]', dynamic)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='New directory; input stays untouched')
    parser.add_argument('--report', required=True, type=Path, help='JSON receipt outside the payload directories')
    parser.add_argument('--sdk-root', type=Path,
                        default=Path('/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony'))
    parser.add_argument('--java', type=Path)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--development-self-sign', action='store_true', required=True)
    args = parser.parse_args()
    src, dst, receipt = args.input.resolve(), args.output.resolve(), args.report.resolve()
    report = {'schemaVersion': 1, 'kind': 'development-ELF-signing-receipt',
              'releaseApproved': False, 'input': str(src), 'output': str(dst), 'files': []}
    try:
        if not src.is_dir() or dst.exists() or receipt.exists():
            raise ValueError('input must exist; output and report must be new')
        if src in dst.parents or dst in src.parents or src == dst:
            raise ValueError('input and output must be separate trees')
        if src in receipt.parents or dst in receipt.parents:
            raise ValueError('report must be outside input/output payloads')
        if not 1 <= args.jobs <= 8:
            raise ValueError('jobs must be between 1 and 8')
        suffix = '.exe' if sys.platform == 'win32' else ''
        tools = {key: args.sdk_root / 'native/llvm/bin' / ('llvm-' + key + suffix)
                 for key in ('strip', 'objcopy', 'readelf')}
        jar = args.sdk_root / 'toolchains/lib/binary-sign-tool.jar'
        bundled_java = Path('/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home/bin/java')
        java = args.java or (bundled_java if bundled_java.is_file() else Path(shutil.which('java') or ''))
        for tool in [*tools.values(), jar, java]:
            if not tool.is_file():
                raise ValueError(f'missing tool: {tool}')
        entries, before = [], {}
        # Inspect all inputs first: an invalid architecture cannot produce a
        # partially signed tree that appears to have passed preflight.
        for path in sorted(src.rglob('*')):
            if path.is_symlink():
                raise ValueError(f'symlink not supported: {path}')
            if not path.is_file():
                continue
            with path.open('rb') as stream:
                magic = stream.read(4)
            if magic != b'\x7fELF':
                continue
            rel = path.relative_to(src).as_posix()
            entries.append(rel)
            before[rel] = {'size': path.stat().st_size, 'sha256': digest(path),
                           **elf_info(path, tools['readelf'])}
        if not entries:
            raise ValueError('no ELF libraries found')
        report['tooling'] = {'sdkRoot': str(args.sdk_root), 'java': str(java),
                             'javaVersion': run([str(java), '-version']).strip(),
                             'binarySignToolSha256': digest(jar),
                             'stripMode': '--strip-all', 'selfSign': True}
        shutil.copytree(src, dst)

        def sign(rel: str) -> dict:
            path = dst / rel
            mode = path.stat().st_mode & 0o777
            commands = [[str(tools['strip']), '--strip-all', str(path)],
                        [str(tools['objcopy']), '--remove-section=.codesign', str(path)],
                        [str(java), '-jar', str(jar), 'sign', '-inFile', str(path),
                         '-outFile', str(path), '-selfSign', '1']]
            logs = [run(command) for command in commands]
            os.chmod(path, mode)
            after = elf_info(path, tools['readelf'])
            if before[rel]['needed'] != after['needed'] or before[rel]['soname'] != after['soname']:
                raise ValueError(f'ELF dependency identity changed: {rel}')
            if not re.search(r'\s\.codesign\s', run([str(tools['readelf']), '-S', str(path)])):
                raise ValueError(f'signature section absent: {rel}')
            signature = run([str(java), '-jar', str(jar), 'display-sign', '-inFile', str(path)])
            if 'code signature is self-sign' not in signature or 'display-sign success' not in signature:
                raise ValueError(f'signing tool did not recognize self-signature: {rel}')
            if digest(src / rel) != before[rel]['sha256']:
                raise ValueError(f'input changed during signing: {rel}')
            return {'path': rel, 'before': before[rel],
                    'after': {'size': path.stat().st_size, 'sha256': digest(path), **after},
                    'codesignSection': True, 'signToolRecognized': True,
                    'commands': commands, 'signLog': ''.join(logs), 'displaySignLog': signature}

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            for index, row in enumerate(executor.map(sign, entries), 1):
                report['files'].append(row)
                if index % 25 == 0 or index == len(entries):
                    print(f'Signed {index}/{len(entries)} ELF libraries', flush=True)
        report['status'] = 'development-self-signatures-created'
        report['count'] = len(entries)
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'Receipt: {receipt}', flush=True)
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        report['status'] = 'failed'
        report['error'] = str(error)
        # Never overwrite a pre-existing report, even on a rejected invocation.
        if not receipt.exists() and src not in receipt.parents and dst not in receipt.parents:
            receipt.parent.mkdir(parents=True, exist_ok=True)
            receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'Development signing failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
