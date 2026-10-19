"""Real GSAS-II refiner for the ``powder-five-stage-v1`` recipe.

Stage semantics and tolerances are migrated 1:1 from
``poc/core_refinement.py`` (itself adapted from upstream
``tests/test_scriptref.py`` at the pinned commit).  All heavy imports
(``GSASII``, ``numpy``) are deferred into methods so this module loads
inside an embedded interpreter before those packages are on ``sys.path``.

The release build of the embedded runtime must not contain ``pydiffax``
(docs/PHASE3_HANDOFF.md §10.1); nothing here imports it, and the bridge
self-test asserts no bridge source references it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bridge.errors import BridgeError

UPSTREAM_COMMIT = "2b4aba1bc44de63a3da9d4495944c3b99e389399"
RECIPE_ID = "powder-five-stage-v1"
STAGES = (
    "before_fitting",
    "scale_and_background",
    "cells",
    "microstrain_displacement_atoms",
    "preferred_orientation",
)
# (xray, neutron) Rwp expected per stage — rtol=1e-4, atol=1e-7.
EXPECTED_RWP = {
    "before_fitting": (96.681098, 99.748994),
    "scale_and_background": (45.811562, 17.864834),
    "cells": (32.475886, 15.02412),
    "microstrain_displacement_atoms": (13.40599, 6.36131),
    "preferred_orientation": (13.16483, 6.38230),
}
EXPECTED_PO = (0.127404, 0.09406)  # C(2,0), C(2,2) — rtol=1e-3
RTOL = 1e-4
ATOL = 1e-7
PO_RTOL = 1e-3

# role -> (limits, background coefficient count), from poc/core_refinement.py
_ROLE_CONFIG = {
    "xray": ([16.0, 110.0], 6),
    "neutron": ([19.0, 120.0], 3),
    "other": ([16.0, 110.0], 6),
}


def validate_instrument(path: Path) -> None:
    """Light-weight header check, shared with the fake core.

    GSAS instrument parameter files begin with the column ruler line
    ``1234567890…``; anything else cannot be a readable .prm.
    """
    try:
        first = path.read_bytes().split(b"\n", 1)[0].lstrip()
    except OSError as exc:
        raise BridgeError("INVALID_INSTRUMENT_FILE", "仪器参数文件无法读取", detail=str(exc), cause=exc) from exc
    if not first.startswith(b"1234567890"):
        raise BridgeError(
            "INVALID_INSTRUMENT_FILE",
            "仪器参数文件不是可识别的 GSAS 参数格式",
            detail=f"首行特征缺失: {path.name}",
        )


def validate_phase(path: Path) -> None:
    try:
        head = path.read_text(encoding="utf-8", errors="replace").splitlines()[:30]
    except OSError as exc:
        raise BridgeError("INVALID_PHASE_FILE", "相文件无法读取", detail=str(exc), cause=exc) from exc
    # CIF may be prefixed by comment/blank lines; the data block must start
    # with a `data_<name>` tag within the file head.
    if not any(line.lstrip().lower().startswith("data_") for line in head):
        raise BridgeError(
            "INVALID_PHASE_FILE",
            "相文件不是可识别的 CIF 格式",
            detail=f"首行特征缺失: {path.name}",
        )


class FiveStageSession:
    """One job's GSAS-II project with the frozen five-stage schedule.

    The MVP recipe requires exactly the standard pairing: one X-ray and one
    neutron histogram (the PbSO4 acceptance set).  Any other histogram mix
    would change the numerical semantics and is rejected instead of being
    silently degraded.
    """

    def __init__(self, project: Any, hists: dict[str, Any], phase: Any, cycle_count: int, gpx_path: Path):
        self.project = project
        self.hists = hists
        self.phase = phase
        self.cycle_count = cycle_count
        self.gpx_path = gpx_path
        self._preferred_orientation: dict[str, float] | None = None
        self._np = None

    def run_stage(self, stage: str) -> dict[str, float]:
        import numpy as np

        self._np = np
        xray = self.hists["xray"]
        neutron = self.hists["neutron"]
        if stage == "before_fitting":
            self.project.set_Controls("cycles", 0)
            self.project.refine(makeBack=True)
        elif stage == "scale_and_background":
            for role, hist in self.hists.items():
                limits, coeffs = _ROLE_CONFIG[role]
                hist.set_refinements({"Limits": list(limits)})
                hist.set_refinements({"Background": {"no. coeffs": coeffs, "refine": True}})
            self.project.set_Controls("cycles", self.cycle_count)
            self.project.refine(makeBack=True)
        elif stage == "cells":
            self.phase.set_refinements({"Cell": True})
            self.phase.set_HAP_refinements({"HStrain": True}, [neutron])
            self.project.refine(makeBack=True)
        elif stage == "microstrain_displacement_atoms":
            self.phase.set_HAP_refinements({"Mustrain": {"refine": True}}, [xray])
            xray.set_refinements({"Sample Parameters": {"Shift": True}})
            neutron.set_refinements({"Sample Parameters": ["DisplaceX", "DisplaceY"]})
            self.phase.set_refinements({"Atoms": {"all": "XU"}})
            self.project.refine(makeBack=True)
        elif stage == "preferred_orientation":
            self.phase.HAPvalue("PO", 2, [xray])
            self.phase.set_HAP_refinements({"Pref.Ori.": True})
            self.project.refine(makeBack=True)
            values = self.phase.HAPvalue("PO", targethistlist=[xray])[5]
            self._preferred_orientation = {"C(2,0)": float(values["C(2,0)"]), "C(2,2)": float(values["C(2,2)"])}
        else:  # pragma: no cover — engine only walks refiner.stages
            raise BridgeError("INTERNAL_ERROR", f"未知阶段 {stage!r}")
        return {hist_id: float(hist.residuals["wR"]) for hist_id, hist in self.hists.items()}

    def check_baseline(self, stage: str, rwp: dict[str, float]) -> None:
        np = self._np
        expected = EXPECTED_RWP[stage]
        for hist_id, value in (("xray", rwp["xray"]), ("neutron", rwp["neutron"])):
            target = expected[0] if hist_id == "xray" else expected[1]
            if not np.allclose(value, target, rtol=RTOL, atol=ATOL):
                raise BridgeError(
                    "REFINEMENT_FAILED",
                    f"阶段 {stage} 的 {hist_id} Rwp={value:.5f} 超出基线容差（期望 {target:.5f}）",
                    detail="rtol=1e-4, atol=1e-7",
                )
        if stage == "preferred_orientation":
            po = self._preferred_orientation or {}
            actual = (po.get("C(2,0)", float("nan")), po.get("C(2,2)", float("nan")))
            if not np.allclose(actual, EXPECTED_PO, rtol=PO_RTOL, atol=ATOL):
                raise BridgeError(
                    "REFINEMENT_FAILED",
                    "择优取向系数超出基线容差",
                    detail=f"expected {EXPECTED_PO}, got {actual}",
                )

    def finish(self) -> dict[str, float] | None:
        return self._preferred_orientation


class FiveStageRefiner:
    """Refiner object consumed by :class:`bridge.engine.CoreRuntime`."""

    recipe_id = RECIPE_ID
    requires_gsasii = True
    upstream_commit = UPSTREAM_COMMIT
    stages = STAGES
    validate_instrument = staticmethod(validate_instrument)
    validate_phase = staticmethod(validate_phase)

    def prepare(self, paths: dict[str, Any], workdir: Path, request: dict[str, Any]) -> FiveStageSession:
        try:
            import GSASII.GSASIIscriptable as g2sc
        except ImportError as exc:
            raise BridgeError(
                "CORE_NOT_READY",
                "GSAS-II 运行时不可用",
                detail=type(exc).__name__,
                cause=exc,
            ) from exc

        histograms = request["inputs"]["histograms"]
        if {hist["role"] for hist in histograms} != {"xray", "neutron"} or len(histograms) != 2:
            raise BridgeError(
                "INVALID_REQUEST",
                "powder-five-stage-v1 当前仅接受一支 X 射线与一支中子直方图的标准组合",
            )
        gpx_path = workdir / request["output"]["projectName"]
        project = g2sc.G2Project(newgpx=str(gpx_path))
        hists: dict[str, Any] = {}
        for hist in histograms:
            entry = paths[hist["id"]]
            hists[hist["role"]] = project.add_powder_histogram(
                str(entry["data"]), str(entry["instrument"]), fmthint=entry["formatHint"]
            )
        phase_entry = paths["phase"]
        phase = project.add_phase(
            str(phase_entry["file"]),
            phasename=phase_entry["name"],
            histograms=list(hists.values()),
        )
        return FiveStageSession(
            project,
            hists,
            phase,
            cycle_count=request["options"]["cycleCount"],
            gpx_path=gpx_path,
        )


def make_refiner() -> FiveStageRefiner:
    return FiveStageRefiner()
