#!/usr/bin/env python3
"""Verify the byte-for-byte integrity of the checked-in PbSO4 fixtures."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIRECTORY = ROOT / "tests" / "fixtures"
EXPECTED = {
    "PBSO4.XRA": "CA2DA02FC7E17D2FC912DE22A979F8101BA6140F2E8104F9D3AA64F030CA58BB",
    "INST_XRY.PRM": "E59413059BC3B12A51F1C6EEBC5D581470320D05A31F11A41DBB32E16D1D16B9",
    "PBSO4.CWN": "59462BA6D7C72C9800B0B6BF41903F9933ED5AC5ADAB101D27022D5D25CF18BA",
    "inst_d1a.prm": "A1031174A9B509F889377752F5C095A1DAD49A25FB0A72C057F184F7B321FCEA",
    "PbSO4-Wyckoff.cif": "22CBA0B64FB6BF89178FE828FDF63570BFFEBED1485313E78C50C2918A47A970",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def main() -> int:
    failures: list[str] = []
    for name, expected in EXPECTED.items():
        path = FIXTURE_DIRECTORY / name
        if not path.is_file():
            failures.append(f"Missing fixture: {name}")
            continue

        actual = sha256(path)
        if actual != expected:
            failures.append(
                f"Hash mismatch: {name}; expected {expected}, got {actual}"
            )
            continue
        print(f"PASS {name}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1

    print("All fixture SHA-256 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
