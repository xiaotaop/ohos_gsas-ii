#!/usr/bin/env python3
"""Check that every versioned JSON (contracts, PoC results, packaging) is valid."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEARCH_ROOTS = (ROOT / "contracts", ROOT / "poc" / "results", ROOT / "packaging")


def main() -> int:
    files = sorted(
        path
        for search_root in SEARCH_ROOTS
        for path in search_root.rglob("*.json")
    )
    if not files:
        print("FAIL no JSON files found", file=sys.stderr)
        return 1

    failures: list[str] = []
    for path in files:
        relative = path.relative_to(ROOT)
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            failures.append(f"{relative}: {exc}")
            continue
        print(f"PASS {relative.as_posix()}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1

    print(f"All {len(files)} JSON files are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
