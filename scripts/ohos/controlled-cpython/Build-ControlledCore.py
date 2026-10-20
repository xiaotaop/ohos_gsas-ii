#!/usr/bin/env python3
"""Experimental macOS -> OHOS core-only build; no signing, installation or release approval."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tarfile

REPO = Path(__file__).resolve().parents[3]
TRACE = REPO / 'packaging/reviews/community-source-trace-20261020.json'
PATCH = Path(__file__).with_name('cross-configure.patch')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, cwd, log, env=None):
    with log.open('w') as stream:
        subprocess.run([str(a) for a in args], cwd=cwd, env=env, stdout=stream,
                       stderr=subprocess.STDOUT, check=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-archive', type=Path, required=True)
    p.add_argument('--community-repo', type=Path, required=True)
    p.add_argument('--sdk', type=Path, required=True, help='OpenHarmony SDK root')
    p.add_argument('--output', type=Path, required=True, help='NEW separate directory')
    p.add_argument('--prepare-only', action='store_true')
    a = p.parse_args()
    a.source_archive = a.source_archive.resolve()
    a.community_repo = a.community_repo.resolve()
    a.sdk = a.sdk.resolve()
    a.output = a.output.resolve()
    trace = json.loads(TRACE.read_text())['cpython']
    if a.output.exists():
        p.error('output must not exist')
    if sha(a.source_archive) != trace['upstreamArchive']['sha256']:
        p.error('official source archive hash mismatch')
    if sha(PATCH) != '81e9aea2ee8f5ecee253dce818cec94aeba53eb6ad25aeba52d31aba17ea48a1':
        p.error('controlled configure patch hash mismatch')
    if not (a.sdk / 'native/llvm/bin/clang').is_file():
        p.error('SDK clang missing')
    a.output.mkdir(parents=True)
    # Source tar is digest pinned. The data filter rejects unsafe paths/links.
    for directory in ('host', 'target'):
        dest = a.output / directory
        dest.mkdir()
        with tarfile.open(a.source_archive) as archive:
            archive.extractall(dest, filter='data')
    host = a.output / 'host/Python-3.12.9'
    target = a.output / 'target/Python-3.12.9'
    commit = trace['patchRepository']['commit']
    patches = a.output / 'patches'
    patches.mkdir()
    for index, row in enumerate(trace['patchApplication']['patches']):
        data = subprocess.check_output(['git', '-C', str(a.community_repo), 'show', commit + ':' + row['path']])
        if hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('community patch hash mismatch: ' + row['path'])
        if not row['applied']:
            continue  # Explicitly skipped venv patch, matching the documented prototype.
        patch = patches / (str(index) + '.patch')
        patch.write_bytes(data)
        run(['git', 'apply', '--recount', '-C1', '--ignore-whitespace', patch], target,
            a.output / ('patch-' + str(index) + '.log'))
    run(['git', 'apply', PATCH], target, a.output / 'controlled-patch.log')
    # data filter removes executable bits; restore only source scripts required by configure.
    for source in (host, target):
        for name in ('configure', 'config.guess', 'config.sub', 'install-sh'):
            (source / name).chmod(0o755)
    receipt = {'kind': 'controlled-cpython-core-build', 'version': '3.12.9',
        'sourceArchiveSha256': sha(a.source_archive), 'communityPatchCommit': commit,
        'appliedPatches': 81, 'skippedPatch': '0125-Lib-venv-realpath-base-executable.patch',
        'configurePatchSha256': sha(PATCH), 'built': False, 'deviceValidated': False,
        'scope': 'core library only; no claim to rebuild retained community stdlib extensions'}
    if not a.prepare_only:
        run(['./configure', '--without-ensurepip', '--disable-test-modules', 'CC=/usr/bin/clang'], host, a.output / 'host-configure.log')
        # APFS may be case insensitive: "make python" can mistake Python/ for its output.
        run(['make', '-j4', 'python.exe', 'pybuilddir.txt'], host, a.output / 'host-build.log')
        llvm = a.sdk / 'native/llvm'
        wrapper = a.output / 'ohos-cc'
        wrapper.write_text('#!/bin/sh\nexec ' + shlex.quote(str(llvm / 'bin/clang')) +
            ' --target=aarch64-linux-ohos --sysroot=' + shlex.quote(str(a.sdk / 'native/sysroot')) + ' -D__OHOS__ "$@"\n')
        wrapper.chmod(0o755)
        builtins = llvm / 'lib/clang/15.0.4/lib/aarch64-linux-ohos/libclang_rt.builtins.a'
        if not builtins.is_file():
            raise ValueError('recipe pins SDK compiler-rt 15.0.4; review a different SDK explicitly')
        env = dict(os.environ, CC=str(wrapper), AR=str(llvm / 'bin/llvm-ar'), RANLIB=str(llvm / 'bin/llvm-ranlib'),
            CFLAGS='-fPIC -O2', LDFLAGS='-nostdlib -fuse-ld=lld -L' + shlex.quote(str(llvm / 'lib/aarch64-linux-ohos')) + ' ' + shlex.quote(str(builtins)) + ' -lc -lm',
            MACHDEP='ohos', ac_cv_header_libintl_h='no', ac_cv_lib_intl_textdomain='no',
            ac_cv_file__dev_ptmx='yes', ac_cv_file__dev_ptc='no', ac_cv_buggy_getaddrinfo='no',
            ac_cv_little_endian_double='yes', ac_cv_func_textdomain='no',
            ac_cv_func_bindtextdomain='no', ac_cv_func_bind_textdomain_codeset='no')
        build = a.output / 'build'
        build.mkdir()
        platform = subprocess.check_output(['sh', str(host / 'config.guess')], text=True).strip()
        run([target / 'configure', '--prefix=/gsas-controlled-python', '--build=' + platform,
            '--host=aarch64-unknown-linux-ohos', '--with-build-python=' + str(host / 'python.exe'),
            '--enable-shared', '--without-static-libpython', '--without-ensurepip',
            '--disable-test-modules', '--with-pkg-config=no'], build, a.output / 'target-configure.log', env)
        run(['make', '-j4', 'libpython3.12.so', 'BLDSHARED=' + str(wrapper) + ' -shared',
             'LDSHARED=' + str(wrapper) + ' -shared'], build, a.output / 'target-build.log', env)
        run(['make', 'pybuilddir.txt'], build, a.output / 'sysconfig.log', env)
        receipt.update(built=True, unsignedCoreSha256=sha(build / 'libpython3.12.so'),
                       compilerRtArchiveSha256=sha(builtins), compilerSha256=sha(llvm / 'bin/clang'))
    (a.output / 'build-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
