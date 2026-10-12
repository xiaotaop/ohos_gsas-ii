#!/usr/bin/env python3
"""Run the GSAS-II headless PbSO4 refinement portability probe.

This is an adaptation of upstream tests/test_scriptref.py from the pinned
GSAS-II commit. It adds fixture integrity checks and machine-readable output.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


UPSTREAM_COMMIT = "2b4aba1bc44de63a3da9d4495944c3b99e389399"
RTOL = 1e-4
ATOL = 1e-7

FIXTURES = {
    "PBSO4.XRA": "CA2DA02FC7E17D2FC912DE22A979F8101BA6140F2E8104F9D3AA64F030CA58BB",
    "INST_XRY.PRM": "E59413059BC3B12A51F1C6EEBC5D581470320D05A31F11A41DBB32E16D1D16B9",
    "PBSO4.CWN": "59462BA6D7C72C9800B0B6BF41903F9933ED5AC5ADAB101D27022D5D25CF18BA",
    "inst_d1a.prm": "A1031174A9B509F889377752F5C095A1DAD49A25FB0A72C057F184F7B321FCEA",
    "PbSO4-Wyckoff.cif": "22CBA0B64FB6BF89178FE828FDF63570BFFEBED1485313E78C50C2918A47A970",
}

EXPECTED_STAGES = (
    ("before_fitting", (96.681098, 99.748994)),
    ("scale_and_background", (45.811562, 17.864834)),
    ("cells", (32.475886, 15.02412)),
    ("microstrain_displacement_atoms", (13.40599, 6.36131)),
    ("preferred_orientation", (13.16483, 6.38230)),
)

_DLL_HANDLES: list[Any] = []


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def validate_fixtures(fixture_dir: Path) -> list[dict[str, Any]]:
    records = []
    for name, expected in FIXTURES.items():
        path = fixture_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"Missing fixture: {path}")
        actual = sha256(path)
        if actual != expected:
            raise ValueError(
                f"Fixture hash mismatch for {name}: expected {expected}, got {actual}"
            )
        records.append({"name": name, "bytes": path.stat().st_size, "sha256": actual})
    return records


def configure_dll_search(dll_dirs: list[Path]) -> None:
    if os.name != "nt":
        return
    for directory in dll_dirs:
        resolved = directory.resolve()
        if not resolved.is_dir():
            raise FileNotFoundError(f"DLL directory does not exist: {resolved}")
        _DLL_HANDLES.append(os.add_dll_directory(str(resolved)))


def distribution_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def run_refinement(fixture_dir: Path) -> tuple[list[dict[str, Any]], dict[str, float]]:
    import numpy as np

    native_modules = ("GSASII.pyspg", "GSASII.pypowder", "GSASII.pytexture")
    for module_name in native_modules:
        importlib.import_module(module_name)

    import GSASII.GSASIIscriptable as G2sc

    actual_stages: list[dict[str, Any]] = []
    expected_by_name = dict(EXPECTED_STAGES)

    def record(name: str, h1: Any, h2: Any) -> None:
        actual = (float(h1.residuals["wR"]), float(h2.residuals["wR"]))
        expected = expected_by_name[name]
        passed = bool(np.allclose(actual, expected, rtol=RTOL, atol=ATOL))
        actual_stages.append(
            {
                "name": name,
                "expected_rwp": list(expected),
                "actual_rwp": list(actual),
                "passed": passed,
            }
        )
        if not passed:
            raise AssertionError(
                f"{name}: expected Rwp {expected}, got {actual} "
                f"(rtol={RTOL}, atol={ATOL})"
            )

    fixture = lambda name: str(fixture_dir / name)
    with tempfile.TemporaryDirectory(prefix="ohos-gsas-ii-poc-") as temp_dir:
        project = G2sc.G2Project(newgpx=str(Path(temp_dir) / "test_scripting.gpx"))
        h1 = project.add_powder_histogram(
            fixture("PBSO4.XRA"), fixture("INST_XRY.PRM"), fmthint="GSAS powder"
        )
        h2 = project.add_powder_histogram(
            fixture("PBSO4.CWN"), fixture("inst_d1a.prm"), fmthint="GSAS powder"
        )
        phase = project.add_phase(
            fixture("PbSO4-Wyckoff.cif"), phasename="PbSO4", histograms=[h1, h2]
        )

        project.set_Controls("cycles", 0)
        project.refine(makeBack=True)
        record("before_fitting", h1, h2)

        h1.set_refinements({"Limits": [16.0, 110.0]})
        h2.set_refinements({"Limits": [19.0, 120.0]})
        project.set_Controls("cycles", 3)
        h1.set_refinements({"Background": {"no. coeffs": 6, "refine": True}})
        h2.set_refinements({"Background": {"no. coeffs": 3, "refine": True}})
        project.refine(makeBack=True)
        record("scale_and_background", h1, h2)

        phase.set_refinements({"Cell": True})
        phase.set_HAP_refinements({"HStrain": True}, [h2])
        project.refine(makeBack=True)
        record("cells", h1, h2)

        phase.set_HAP_refinements({"Mustrain": {"refine": True}}, [h1])
        h1.set_refinements({"Sample Parameters": {"Shift": True}})
        h2.set_refinements({"Sample Parameters": ["DisplaceX", "DisplaceY"]})
        phase.set_refinements({"Atoms": {"all": "XU"}})
        project.refine(makeBack=True)
        record("microstrain_displacement_atoms", h1, h2)

        phase.HAPvalue("PO", 2, [h1])
        phase.set_HAP_refinements({"Pref.Ori.": True})
        project.refine(makeBack=True)
        po_values = phase.HAPvalue("PO", targethistlist=[h1])[5]
        orientation = {
            "C(2,0)": float(po_values["C(2,0)"]),
            "C(2,2)": float(po_values["C(2,2)"]),
        }
        expected_orientation = (0.127404, 0.09406)
        actual_orientation = (orientation["C(2,0)"], orientation["C(2,2)"])
        if not np.allclose(actual_orientation, expected_orientation, rtol=1e-3, atol=ATOL):
            raise AssertionError(
                f"Preferred-orientation coefficients: expected {expected_orientation}, "
                f"got {actual_orientation}"
            )
        record("preferred_orientation", h1, h2)

    return actual_stages, orientation


def write_result(path: Path | None, result: dict[str, Any]) -> None:
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path is None:
        print(rendered, end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    print(f"PoC result written to {path}")


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=repo_root / "tests" / "fixtures",
        help="Directory containing the five pinned PbSO4 fixtures",
    )
    parser.add_argument(
        "--dll-dir",
        type=Path,
        action="append",
        default=[],
        help="Additional Windows native DLL directory; may be repeated",
    )
    parser.add_argument("--output", type=Path, help="Write structured result JSON here")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started = time.perf_counter()
    base_result: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "upstream_commit": UPSTREAM_COMMIT,
        "environment": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "gsas_ii": distribution_version("GSAS-II"),
            "numpy": distribution_version("numpy"),
            "scipy": distribution_version("scipy"),
            "pycifrw": distribution_version("PyCifRW"),
        },
    }
    try:
        configure_dll_search(args.dll_dir)
        base_result["fixtures"] = validate_fixtures(args.fixtures.resolve())
        stages, orientation = run_refinement(args.fixtures.resolve())
        base_result["stages"] = stages
        base_result["preferred_orientation"] = orientation
        base_result["passed"] = all(stage["passed"] for stage in stages)
    except Exception as exc:
        base_result["passed"] = False
        base_result["error"] = {"type": type(exc).__name__, "message": str(exc)}
        traceback.print_exc()
    finally:
        base_result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        write_result(args.output, base_result)
    return 0 if base_result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
