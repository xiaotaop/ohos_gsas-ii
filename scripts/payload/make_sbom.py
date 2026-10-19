#!/usr/bin/env python3
"""Generate the draft CycloneDX 1.5 SBOM from the payload component manifest.

This is member B's input for member C's release SBOM: it records component
identity, licence and source references. It deliberately contains no file
hashes (those come from the runtime manifest built from the real payload) and
keeps ``distributionReview`` as recorded, so ``pending`` stays visible.
Regenerate it from the final signed HAP before release.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPONENTS = ROOT / "scripts/payload/components.json"
OUT = ROOT / "packaging/sbom.draft.cdx.json"
SPDX_IDS = {"PSF-2.0", "BSD-3-Clause", "MIT"}
APP_REF = "pkg:ohos/com.gsasii.desktop@0.1.0"


def build(components: list[dict]) -> dict:
    refs = {c["id"]: f"pkg:generic/{c['id']}@{c['version']}" for c in components}
    entries = []
    for c in components:
        license_entry = {"id": c["license"]} if c["license"] in SPDX_IDS else {"name": c["license"]}
        entries.append({
            "type": "library",
            "bom-ref": refs[c["id"]],
            "name": c["id"],
            "version": c["version"],
            "licenses": [{"license": license_entry}],
            "externalReferences": [
                {"type": "distribution", "url": c["sourceUrl"]},
                {"type": "vcs", "url": c["sourceCodeUrl"]},
            ],
            "properties": [{"name": "distributionReview", "value": c["distributionReview"]}],
        })
    dependencies = [
        {"ref": refs[c["id"]], "dependsOn": [refs[d] for d in c.get("dependsOn", [])]}
        for c in components
    ]
    dependencies.append({"ref": APP_REF, "dependsOn": list(refs.values())})
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "bom-ref": APP_REF,
                "name": "GSAS-II Desktop",
                "version": "0.1.0",
            },
            "properties": [
                {"name": "draft", "value": "true"},
                {"name": "note", "value": (
                    "Generated from scripts/payload/components.json. No file hashes; "
                    "distributionReview values are pending. Regenerate from the signed "
                    "HAP and complete the licence review before release."
                )},
                {"name": "staticallyLinked", "value": (
                    "LLVM FortranRuntime 20.1.0 (Apache-2.0 WITH LLVM-exception, "
                    "https://github.com/llvm/llvm-project) is statically linked into the "
                    "GSAS-II native extensions; include it in the final SBOM and licence bundle."
                )},
            ],
        },
        "components": entries,
        "dependencies": dependencies,
    }


def main() -> int:
    components = json.loads(COMPONENTS.read_text(encoding="utf-8"))
    bom = build(components)
    OUT.write_text(json.dumps(bom, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(bom['components'])} components)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())