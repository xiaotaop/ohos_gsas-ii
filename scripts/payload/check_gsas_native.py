#!/usr/bin/env python3
"""Release gate: a payload must ship the GSAS-II native extensions.

The pinned GSAS-II 2.0.0 commit needs its compiled modules to create even the
simplest phase: without ``pyspg``, ``GSASIIobj.SetNewPhase`` raises
``NameError: name 'P1SGData' is not defined`` and ``add_phase`` fails for every
CIF/phase file, so the five-stage refinement cannot run at all. A payload
assembled from the pure Python source tree therefore passes the manifest and
``Prepare-Runtime`` byte/hash gates while being functionally unusable.

This checker closes that gap: it looks for each required extension next to the
GSAS-II package or through the declared HAP native-module map, verifies that the file is an AArch64 shared object, and refuses
``pydiffax`` (no downstream distribution basis yet). Run it on every release
payload; ``--allow-missing`` is only for development payloads used to bring up
the loader, and it marks the result as not release-ready.

Exit codes: 0 all checks passed (or --allow-missing), 2 a check failed,
3 the GSAS-II directory could not be located.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

# Compiled modules that phase 2 built and imported on the device. pydiffax is
# deliberately absent: it is forbidden until its downstream licence is cleared.
REQUIRED = (
    "pyspg",
    "pypowder",
    "pytexture",
    "fmask",
    "histogram2d",
    "pack_f",
    "unpack_cbf",
    "kvec_general",
)
FORBIDDEN = ("pydiffax",)
EM_AARCH64 = 183
ET_DYN = 3


def find_gsasii(payload: Path) -> Path | None:
    """Return the GSASII package directory inside an expanded payload."""
    preferred = payload / "runtime/lib/python3.12/site-packages/GSASII"
    if preferred.is_dir():
        return preferred
    matches = sorted(p for p in payload.rglob("GSASII") if p.is_dir())
    return matches[0] if matches else None


def elf_problem(path: Path) -> str | None:
    """Describe why *path* is not an AArch64 shared object, or None if it is."""
    try:
        head = path.read_bytes()[:64]
    except OSError as exc:
        return f"unreadable: {exc}"
    if len(head) < 64 or head[:4] != b"\x7fELF":
        return "not an ELF file"
    if head[4] != 2:
        return "not ELF64"
    if head[5] != 1:
        return "not little-endian"
    e_type, e_machine = struct.unpack_from("<HH", head, 16)
    if e_type != ET_DYN:
        return f"not a shared object (e_type={e_type})"
    if e_machine != EM_AARCH64:
        return f"not AArch64 (e_machine={e_machine})"
    return None


def check(payload: Path, required=REQUIRED, forbidden=FORBIDDEN):
    """Return (gsasii_dir, failures, warnings, found) without touching disk."""
    gsasii = find_gsasii(payload)
    if gsasii is None:
        return None, ["GSASII package directory not found under payload"], [], {}
    failures: list[str] = []
    warnings: list[str] = []
    found: dict[str, str] = {}
    module_map = {}
    map_path = payload / "runtime/bridge/native-module-map.json"
    if map_path.is_file():
        try:
            document = json.loads(map_path.read_text(encoding="utf-8"))
            module_map = document["modules"]
            if type(document.get("schemaVersion")) is not int or document.get("schemaVersion") != 1 or not isinstance(module_map, dict):
                raise ValueError("invalid map shape")
            native_names = set()
            for module, filename in module_map.items():
                if (not isinstance(module, str) or not isinstance(filename, str)
                    or not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", module)
                    or not re.fullmatch(r"[A-Za-z0-9_.-]+\.so", filename)):
                    raise ValueError("invalid module or native filename")
                if filename.casefold() in native_names:
                    raise ValueError("colliding native filenames")
                native_names.add(filename.casefold())
                if any(module.split(".")[-1].lower().startswith(name) for name in forbidden):
                    failures.append(f"forbidden extension present in native map: {module}")
        except (OSError, ValueError, KeyError, TypeError) as error:
            return gsasii, [f"invalid native module map: {error}"], warnings, found
    for name in required:
        mapped = module_map.get(f"GSASII.{name}")
        candidates = ([payload / "libs" / mapped] if mapped is not None
                      else sorted(gsasii.glob(f"{name}*.so")))
        if not candidates:
            failures.append(f"missing native extension: {name}*.so")
            continue
        problem = elf_problem(candidates[0])
        if problem:
            failures.append(f"invalid native extension {candidates[0].name}: {problem}")
        else:
            found[name] = str(candidates[0].relative_to(payload))
    for name in forbidden:
        matches = sorted(gsasii.glob(f"{name}*.so"))
        if matches:
            failures.append(f"forbidden extension present: {matches[0].name}")
    if not required:
        warnings.append("no extensions requested; nothing was verified")
    return gsasii, failures, warnings, found


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--payload", required=True, type=Path,
                        help="expanded payload root (contains runtime/lib/...)")
    parser.add_argument("--allow-missing", action="store_true",
                        help="development payload: report gaps, exit 0, mark not release-ready")
    parser.add_argument("--json", type=Path, help="write the result as JSON")
    args = parser.parse_args(argv)

    gsasii, failures, warnings, found = check(args.payload)
    release_ready = not failures
    if gsasii is None:
        print(f"GSAS-II directory not found under {args.payload}")
        return 3

    print(f"GSAS-II directory: {gsasii}")
    print(f"required: {', '.join(REQUIRED)}")
    print(f"forbidden: {', '.join(FORBIDDEN)}")
    for name, rel in found.items():
        print(f"PASS {name}: {rel}")
    for warning in warnings:
        print(f"WARN {warning}")
    for failure in failures:
        print(f"FAIL {failure}")

    if args.json:
        args.json.write_text(json.dumps({
            "payload": str(args.payload),
            "gsasii": str(gsasii),
            "required": list(REQUIRED),
            "found": found,
            "failures": failures,
            "warnings": warnings,
            "releaseReady": release_ready,
        }, indent=2) + "\n", encoding="utf-8")

    if not failures:
        print(f"all {len(found)} native extensions present and AArch64")
        return 0
    if args.allow_missing:
        print("DEV-ONLY: payload is not release-ready; rebuild the extensions "
              "(scripts/ohos, flang 20.1.0) or reuse the signed phase-2 modules")
        return 0
    print("payload rejected: GSAS-II cannot create a phase without these modules")
    return 2


if __name__ == "__main__":
    sys.exit(main())