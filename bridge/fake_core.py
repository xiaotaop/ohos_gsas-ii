"""Scripted stand-in refiner (docs/PHASE3_HANDOFF.md §7.2 step 2).

``FakeFiveStageRefiner`` satisfies the exact same refiner protocol as
:mod:`bridge.core`, so the full pipeline — request validation, file
resolution, contract events, stage-boundary cancellation, error mapping and
artifact writing — runs on any stdlib-only Python without NumPy, SciPy or
GSAS-II.  The "computation" is a short sleep per stage that returns the
pinned PbSO4 baseline numbers; artifacts are stub files.

This is the core member B hands to member A for UI integration before the
embedded runtime is ready, and it is what the bridge self-test exercises.
It must never be shipped into a release HAP.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from bridge.core import EXPECTED_PO, EXPECTED_RWP, RECIPE_ID, STAGES, UPSTREAM_COMMIT
from bridge.core import validate_instrument, validate_phase

_FAKE_GPX_STUB = b"<?xml version='1.0'?>\n<!-- fake-core stub; not a real GSAS-II project -->\n"


class FakeSession:
    def __init__(self, cycle_count: int, gpx_path: Path, stage_delay: float, boom: bool):
        self.cycle_count = cycle_count
        self.gpx_path = gpx_path
        self.stage_delay = stage_delay
        self.boom = boom

    def run_stage(self, stage: str) -> dict[str, float]:
        if self.boom and stage == "cells":
            raise RuntimeError("simulated GSAS-II internal failure (fake core)")
        time.sleep(self.stage_delay)
        print(f"[fake-core] stage {stage} computed with cycles={self.cycle_count}")
        xray, neutron = EXPECTED_RWP[stage]
        return {"xray": float(xray), "neutron": float(neutron)}

    def check_baseline(self, stage: str, rwp: dict[str, float]) -> None:
        return None  # values are exact by construction

    def finish(self) -> dict[str, float]:
        return {"C(2,0)": EXPECTED_PO[0], "C(2,2)": EXPECTED_PO[1]}


class FakeFiveStageRefiner:
    recipe_id = RECIPE_ID
    upstream_commit = UPSTREAM_COMMIT
    stages = STAGES
    validate_instrument = staticmethod(validate_instrument)
    validate_phase = staticmethod(validate_phase)

    def __init__(self, stage_delay: float = 0.05, boom: bool = False):
        self.stage_delay = stage_delay
        self.boom = boom

    def prepare(self, paths: dict[str, Any], workdir: Path, request: dict[str, Any]) -> FakeSession:
        histograms = request["inputs"]["histograms"]
        if {hist["role"] for hist in histograms} != {"xray", "neutron"} or len(histograms) != 2:
            from bridge.errors import BridgeError

            raise BridgeError(
                "INVALID_REQUEST",
                "powder-five-stage-v1 当前仅接受一支 X 射线与一支中子直方图的标准组合",
            )
        gpx_path = workdir / request["output"]["projectName"]
        gpx_path.write_bytes(_FAKE_GPX_STUB)
        return FakeSession(
            cycle_count=request["options"]["cycleCount"],
            gpx_path=gpx_path,
            stage_delay=self.stage_delay,
            boom=self.boom,
        )
