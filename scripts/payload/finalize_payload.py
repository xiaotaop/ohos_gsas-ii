#!/usr/bin/env python3
"""Last pipeline step: make the payload satisfy the RUNTIME_PACKAGING §2 gates.

Two normalizations, both content-preserving:

1. Zero-byte files are rejected by the manifest schema (size must be > 0).
   Upstream ships empty package markers (email/mime/__init__.py,
   urllib/__init__.py, py.typed, empty .pyi stubs). A single newline is valid
   Python, a no-op marker for py.typed and harmless in a stub; keeping the file
   preserves regular-package semantics.
2. Assert that no file still starts with an archive magic: nested compressed
   payloads must be expanded, not shipped.

Run after prune_release_payload.py; idempotent.
"""
import os
from pathlib import Path

PAYLOAD = Path(os.environ.get('GSAS_PAYLOAD_BASE', '/home/dax/gsas-payload')) / 'payload'
MAGICS = (b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08', b'\x1f\x8b', b'BZh',
          b'\xfd7zXZ\x00', b'7z\xbc\xaf\x27\x1c')

empty = 0
for f in PAYLOAD.rglob('*'):
    if f.is_file() and f.stat().st_size == 0:
        f.write_bytes(b'\n')
        empty += 1

nested = []
for f in PAYLOAD.rglob('*'):
    if not f.is_file():
        continue
    with f.open('rb') as fh:
        head = fh.read(300)
    if head.startswith(MAGICS) or head[257:262] == b'ustar':
        nested.append(f.relative_to(PAYLOAD).as_posix())

print('normalized empty files:', empty)
print('nested archives:', nested or 'none')
if nested:
    raise SystemExit('nested compressed payload must be expanded')