#!/usr/bin/env python3
"""Release-pruning recipe applied to the expanded GSAS-II payload (Member B build recipe).

Two auditable, content-preserving edits, both required by RUNTIME_PACKAGING §2
and TEAM_ASSIGNMENT §5.1 (publish builds exclude pydiffax; the wxPython GUI is
not shipped):

1. GSASIIpwd.py: the guarded `import pydiffax as pyx` block is replaced by an
   equivalent `raise ImportError` so the module keeps its existing
   "not available" fallback (pydiffax stays undefined exactly as on platforms
   without the extension) without containing an import statement for an
   excluded component.
2. Every GSASII module whose own module level imports wx (or imports G2shapes,
   which only GUI code uses) is removed; the scriptable five-stage path never
   imports them. Verified afterwards with an AST scan: no remaining payload
   file contains a top-level import of any removed module.
"""
import ast
import os
import re
import sys
from pathlib import Path

BASE = Path(os.environ.get('GSAS_PAYLOAD_BASE', '/home/dax/gsas-payload'))
SITE = BASE / 'payload/runtime/lib/python3.12/site-packages'
G2 = SITE / 'GSASII'

pwd = G2 / 'GSASIIpwd.py'
text = pwd.read_text(encoding='utf-8')
patched = text.replace(
    "try:\n"
    "    if GSASIIpath.binaryPath:\n"
    "        import pydiffax as pyx\n"
    "    else:\n"
    "        from . import pydiffax as pyx\n"
    "except ImportError:\n",
    "try:\n"
    "    raise ImportError('pydiffax is excluded from distribution builds')\n"
    "except ImportError:\n",
)
if patched == text:
    if "pydiffax is excluded from distribution builds" in text:
        pass  # recipe already applied to this payload copy
    else:
        sys.exit('GSASIIpwd.py pydiffax block not found — upstream changed, re-audit')
else:
    pwd.write_text(patched, encoding='utf-8')


def top_level_imports(tree):
    out = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            out += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            out.append(node.module or '')
            out += [f'{node.module or ""}.{a.name}' for a in node.names]
    return out


removed = []
for f in sorted(G2.rglob('*.py')):
    try:
        tree = ast.parse(f.read_text(encoding='utf-8'))
    except SyntaxError:
        sys.exit(f'unparsable source {f}')
    mods = [m.lower() for m in top_level_imports(tree)]
    if any(m == 'wx' or m.startswith('wx.') or 'g2shapes' in m for m in mods):
        f.unlink()
        removed.append(f.relative_to(G2).as_posix())

stems = {Path(p).stem for p in removed}
rewrite_note = []
for f in sorted(SITE.rglob('*.py')):
    src = f.read_text(encoding='utf-8')
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)
    edits = {}
    for node in ast.walk(tree):
        names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
            ([node.module or ''] + [a.name for a in node.names]) if isinstance(node, ast.ImportFrom) else [])
        hit = [n for n in names if n in stems]
        if hit:
            # GUI-only dynamic import inside a guarded branch: replace the
            # import statement with a plain raise that keeps the surrounding
            # fallback in charge (same technique as the pydiffax block).
            ln = node.lineno - 1
            indent = lines[ln][:len(lines[ln]) - len(lines[ln].lstrip())]
            edits[ln] = f"{indent}raise ImportError('{hit[0]} is excluded from distribution builds')\n"
        for n in names:
            if 'pydiffax' in n.lower() or 'g2shapes' in n.lower() or 'fake_core' in n.lower():
                sys.exit(f'banned import still present: {f}')
    if edits:
        for ln, repl in edits.items():
            lines[ln] = repl
        f.write_text(''.join(lines), encoding='utf-8')
        rewrite_note.append(f'{f.relative_to(SITE).as_posix()}: {len(edits)} GUI import(s) neutralized')

# re-parse and re-scan after rewrites so the guarantee is checked on final bytes
for f in sorted(SITE.rglob('*.py')):
    tree = ast.parse(f.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
            ([node.module or ''] + [a.name for a in node.names]) if isinstance(node, ast.ImportFrom) else [])
        if any('pydiffax' in n.lower() or 'g2shapes' in n.lower() or 'fake_core' in n.lower() for n in names):
            sys.exit(f'banned import still present: {f}')
        for n in names:
            if n in stems:
                sys.exit(f'import of removed GUI module {n}: {f}')
for note in rewrite_note:
    print(note)

print('pruned GUI modules:', len(removed))
print('\n'.join(removed))
