#!/usr/bin/env python3
"""Expand PyCifRW's pure-Python dependency wheels into the payload.

CifFile imports prettytable at module level; its drel dialect layer imports
ply. prettytable declares wcwidth. All three are py3-none-any wheels, so the
expanded files are platform-free Python source; hashes were checked against
the PyPI JSON digests before this script ran.
"""
import os
import zipfile
from pathlib import Path

BASE = Path(os.environ.get('GSAS_PAYLOAD_BASE', '/home/dax/gsas-payload'))
SP = BASE / 'payload/runtime/lib/python3.12/site-packages'
WHEELS = (
    ('prettytable-3.18.0-py3-none-any.whl', 'prettytable'),
    ('ply-3.11-py2.py3-none-any.whl', 'ply'),
    ('wcwidth-0.9.2-py3-none-any.whl', 'wcwidth'),
)

for whl, cid in WHEELS:
    with zipfile.ZipFile(BASE / 'downloads' / whl) as z:
        for member in z.namelist():
            if member.endswith('/') or '/' not in member:
                continue  # wheel-root README/.pth would collide across wheels
            if member.endswith(('.pyc', '.pyo')) or '__pycache__' in member:
                raise SystemExit(f'unexpected bytecode in wheel: {whl}!{member}')
            target = SP / member
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(member))
        lic = [n for n in z.namelist() if 'dist-info/' in n and '/licenses/' in n]
        out = BASE / 'payload/licenses' / cid
        out.mkdir(parents=True, exist_ok=True)
        if lic:
            (out / Path(lic[0]).name).write_bytes(z.read(lic[0]))
        else:
            # ply 3.11 ships no licence file; the full BSD text is the header
            # comment of ply/lex.py in the 3.11 sdist (extracted verbatim).
            src = (BASE / 'extract/ply-3.11/ply/lex.py').read_text(encoding='utf-8')
            block = '\n'.join(line[2:] if line.startswith('# ') else line.lstrip('#')
                              for line in src.splitlines()[:32])
            (out / 'LICENSE').write_text(block + '\n', encoding='utf-8')
print('expanded:', ', '.join(c for _, c in WHEELS))