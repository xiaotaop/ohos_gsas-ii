#!/usr/bin/env python3
"""Assemble the Member-B expanded OHOS aarch64 runtime payload (RUNTIME_PACKAGING §2).

Every binary here comes from a hash-verified download recorded in the commit
message of this branch; this script only copies and prunes. No interpreter,
build tool or code from the payload runs here.
"""
import os
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

BASE = Path(os.environ.get('GSAS_PAYLOAD_BASE', '/home/dax/gsas-payload'))
PY = BASE / 'extract/python-3.12.9-ohos-aarch64'
GSAS_SRC = Path(os.environ.get('GSAS_II_SRC', '/mnt/d/vscode_projects/GSAS-II'))
REPO = Path(os.environ.get('GSAS_REPO', '/home/dax/ohos_gsas-ii'))
SP = 'runtime/lib/python3.12/site-packages'

payload = BASE / 'payload'
if payload.exists():
    shutil.rmtree(payload)


def prune_bytecode(root):
    removed = 0
    for dirpath, dirnames, filenames in os.walk(root):
        if os.path.basename(dirpath) == '__pycache__':
            shutil.rmtree(dirpath)
            dirnames[:] = []
            removed += 1
            continue
        for name in filenames:
            if name.endswith(('.pyc', '.pyo')):
                os.remove(os.path.join(dirpath, name))
                removed += 1
    return removed


def ensure_parent(dst):
    Path(dst).parent.mkdir(parents=True, exist_ok=True)


def copy(resolved_src, dst):
    ensure_parent(dst)
    if os.path.isdir(resolved_src):
        shutil.copytree(resolved_src, dst, symlinks=False)
    else:
        shutil.copy2(resolved_src, dst, follow_symlinks=True)


# 1. CPython: top-level libpython, stdlib tree, bundled shared objects.
copy(PY / 'lib/libpython3.12.so', payload / 'libs/libpython3.12.so')
stdlib = payload / 'runtime/lib/python3.12'
# test/idle_test: not needed by the runtime; ensurepip + config-3.12-*: ship
# wheel/static-archive content that RUNTIME_PACKAGING §2 rejects outright.
shutil.copytree(PY / 'lib/python3.12', stdlib, symlinks=False,
                ignore=shutil.ignore_patterns(
                    'test', 'idle_test', 'ensurepip', 'distutils-precedence.pth',
                    'config-3.12-aarch64-linux-ohos'))
prune_bytecode(stdlib)
# the interpreter's bundled pip is dead weight offline and brings .whl files
for drop in ('pip', 'pip-24.3.1.dist-info'):
    target = stdlib / 'site-packages' / drop
    if target.exists():
        shutil.rmtree(target) if target.is_dir() else target.unlink()
for so in ('libffi.so.8', 'libgdbm.so.6'):
    src = (PY / 'lib' / so).resolve()
    if src.exists():
        copy(src, payload / 'runtime/lib' / so)

# 2. NumPy / SciPy wheels, expanded; bytecode-free by construction (verified).
for whl in ('numpy-2.2.6-cp312-cp312-ohos_aarch64.whl',
            'scipy-1.16.3-cp312-cp312-ohos_aarch64.whl'):
    with zipfile.ZipFile(BASE / 'downloads' / whl) as z:
        for member in z.namelist():
            if member.endswith('/'):
                continue
            if member.endswith(('.pyc', '.pyo')) or '__pycache__' in member:
                raise SystemExit(f'unexpected bytecode in wheel: {whl}!{member}')
            if '/' not in member:
                continue  # wheel-root README/.pth would collide across wheels
            target = payload / SP / member
            ensure_parent(target)
            target.write_bytes(z.read(member))

# 3. PyCifRW 5.0.1 pure-Python modules (package_dir {'CifFile':'src'}; the
#    optional StarScan C accelerator stays unbuilt — Phase 2 proved the core
#    PoC passes without it, so only .py files are copied here).
pc = BASE / 'extract/pycifrw-full/pycifrw-5.0.1'
dst = payload / SP / 'CifFile'
for name in ('__init__.py', 'CifFile_module.py', 'StarFile.py', 'TypeContentsParser.py',
             'YappsStarParser_1_0.py', 'YappsStarParser_1_1.py', 'YappsStarParser_2_0.py',
             'YappsStarParser_STAR2.py', 'yapps3_compiled_rt.py', 'cif_files_validator.py'):
    copy(pc / 'src' / name, dst / name)
shutil.copytree(pc / 'src/drel', dst / 'drel')

# 4. GSAS-II 2.0.0 at the locked commit: full GSASII/ tree minus excluded and
#    DIFFaX material; G2shapes.py removal is the RUNTIME_PACKAGING license gate.
g2 = payload / SP / 'GSASII'
EXCLUDED_NAMES = {'G2shapes.py'}
EXCLUDED_DIRS = {'DIFFaXsubs', '__pycache__', 'help', 'install'}  # GUI help/installer assets


def g2_ignore(dir, names):
    ignored = set()
    for n in names:
        low = n.lower()
        if 'pydiffax' in low or 'diffax' in low or n in EXCLUDED_NAMES or n in EXCLUDED_DIRS:
            ignored.add(n)
        if n.endswith(('.pyc', '.pyo')):
            ignored.add(n)
    return ignored


shutil.copytree(GSAS_SRC / 'GSASII', g2, symlinks=False, ignore=g2_ignore)
leftover = subprocess.run(['grep', '-ril', 'pydiffax', str(g2)], capture_output=True, text=True)
print('GSAS-II pydiffax textual refs (meson wiring only if any):',
      [l for l in leftover.stdout.splitlines()][:4])

# 5. Production bridge (§8 runtime), minus dev-only fake_core.py and tests.
bdst = payload / 'runtime/bridge'
for name in ('__init__.py', 'core.py', 'engine.py', 'errors.py', 'events.py', 'files.py',
             'request.py', 'service.py'):
    copy(REPO / 'bridge' / name, bdst / name)

# 6. License texts (one directory per component id).
lic = payload / 'licenses'
with tarfile.open(BASE / 'downloads/Python-3.12.9.tgz') as t:
    member = next(m for m in t.getmembers() if m.name.endswith('/LICENSE') and m.name.count('/') == 1)
    ensure_parent(lic / 'cpython/LICENSE')
    (lic / 'cpython/LICENSE').write_bytes(t.extractfile(member).read())
for comp, src in (
        ('numpy', payload / SP / 'numpy-2.2.6.dist-info/LICENSE.txt'),
        ('scipy', payload / SP / 'scipy-1.16.3.dist-info/LICENSE.txt'),
        ('pycifrw', pc / 'LICENSE'),
        ('gsas-ii', GSAS_SRC / 'LICENSE'),
        ('bridge', REPO / 'LICENSE')):
    copy(src, lic / comp / Path(src).name)

# 7. RUNTIME_PACKAGING §2 rejects archives and bytecode anywhere in the tree:
#    drop wheel-shipped static libs, compressed test data and test suites the
#    runtime never imports (numpy.testing is a separate directory and stays).
ARCHIVE_SUFFIXES = ('.a', '.gz', '.zip', '.whl', '.tar', '.bz2', '.xz', '.7z')
def in_scientific_tree(path):
    try:
        parts = Path(path).relative_to(payload / SP).parts
    except ValueError:
        return False
    return bool(parts) and parts[0] in ('numpy', 'scipy')


for dirpath, dirnames, filenames in os.walk(payload, topdown=True):
    if 'tests' in dirnames and in_scientific_tree(dirpath):
        shutil.rmtree(Path(dirpath) / 'tests')
        dirnames.remove('tests')
    for name in filenames:
        if name.endswith(ARCHIVE_SUFFIXES):
            os.remove(os.path.join(dirpath, name))

# scipy's Sobol direction numbers ship as a compressed .npz (a ZIP container),
# which RUNTIME_PACKAGING §2 rejects. _sobol.pyx loads it lazily, only when the
# QMC Sobol engine is constructed; scipy.stats itself and every routine GSAS-II
# imports are unaffected. Sobol QMC is therefore not available in this payload.
npz = payload / SP / 'scipy/stats/_sobol_direction_numbers.npz'
if npz.exists():
    npz.unlink()

print('payload tree:')
os.system(f"find {payload} -maxdepth 3 | sort | head -30")
print('bytes:', sum(f.stat().st_size for f in payload.rglob('*') if f.is_file()))
