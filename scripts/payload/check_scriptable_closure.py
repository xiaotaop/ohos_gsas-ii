#!/usr/bin/env python3
"""Static import-closure check for the pruned GSAS-II payload.

Starts at GSASII/GSASIIscriptable.py and follows every module-level import
inside the GSASII package (relative and absolute). Every reached module must
exist on disk; function-local imports are resolved too and any miss is
reported separately (those are the neutralized GUI/interactive fallbacks).
"""
import ast
import os
import sys
from pathlib import Path

BASE = Path(os.environ.get('GSAS_PAYLOAD_BASE', '/home/dax/gsas-payload'))
ROOT = BASE / 'payload/runtime/lib/python3.12/site-packages'


def resolve(pkg_parts, mod):
    """Map (package parts, dotted module) to a file or package dir."""
    parts = list(pkg_parts) + [p for p in mod.split('.') if p]
    base = ROOT.joinpath(*parts)
    if base.with_suffix('.py').is_file():
        return base.with_suffix('.py')
    if (base / '__init__.py').is_file():
        return base / '__init__.py'
    return None


seen = set()
queue = [(('GSASII',), 'GSASIIscriptable')]
module_missing = []
local_missing = []

while queue:
    pkg, mod = queue.pop()
    key = '.'.join(pkg) + '.' + mod
    if key in seen:
        continue
    seen.add(key)
    path = resolve(pkg, mod)
    if path is None:
        module_missing.append(key)
        continue
    if path.name == '__init__.py':
        pkg = pkg + tuple(mod.split('.'))
        tree = ast.parse(path.read_text(encoding='utf-8'))
    else:
        tree = ast.parse(path.read_text(encoding='utf-8'))

    def targets(node):
        """Yield (package-parts, dotted-module) for imports in node."""
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == 'GSASII' or alias.name.startswith('GSASII.'):
                    parts = alias.name.split('.')
                    yield (('GSASII',), '.'.join(parts[1:])) if len(parts) > 1 else (('GSASII',), '')
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                depth = node.level - 1
                base = pkg[:len(pkg) - depth] if depth else pkg
                if node.module:
                    yield (base, node.module)
                else:
                    for alias in node.names:
                        yield (base, alias.name)
            elif node.module and (node.module == 'GSASII' or node.module.startswith('GSASII.')):
                parts = node.module.split('.')
                yield (('GSASII',), '.'.join(parts[1:]))

    body_ids = {id(n) for n in tree.body}
    for node in tree.body:
        for t in targets(node):
            if t[1]:
                queue.append(t)
    for node in ast.walk(tree):
        if id(node) in body_ids:
            continue
        for (pkg2, mod2) in targets(node):
            if mod2 and resolve(pkg2, mod2) is None:
                local_missing.append(f'{key} -> {".".join(pkg2)}.{mod2}')

print(f'reachable module-level import entries: {len(seen)}')
print('module-level missing:', module_missing or 'none')
print('function-local missing (neutralized GUI fallbacks):', len(set(local_missing)))
for m in sorted(set(local_missing)):
    print(' ', m)
sys.exit(1 if module_missing else 0)