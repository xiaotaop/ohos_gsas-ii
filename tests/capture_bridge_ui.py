"""Test-only JSON capture from B's host service; never a runtime UI transport.

Reuses the bridge test sandbox and validator. Temporary stub artifacts are removed
after capture; stdout contains events/snapshots only, not file contents or paths.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bridge.fake_core import FakeFiveStageRefiner
from bridge.tests.test_python_bridge import SandboxMixin, make_request


class Capture(unittest.TestCase, SandboxMixin):
    def capture(self, scenario):
        job_id = f"job_ui_bridge_{scenario}"
        service = self.make_service(FakeFiveStageRefiner(stage_delay=0, boom=scenario == "failed"))
        events, snapshots, acks = [], [], []

        def observe(event):
            events.append(event)
            snapshots.append(service.get_job_snapshot(job_id))
            if (scenario == "cancelled" and event["type"] == "job.progress"
                    and event["payload"]["state"] == "running" and event["payload"]["stage"] == "cells"):
                acks.append(service.cancel_job(job_id))

        off = service.on_event(observe)
        self.addCleanup(off)
        accepted = service.start_refinement(json.dumps(make_request(job_id)))
        self.assertTrue(service.wait_idle(timeout=5), "host bridge did not finish")
        self.validate(events, f"ui-{scenario}")
        return {"accepted": accepted, "events": events, "snapshots": snapshots,
                "snapshot": service.get_job_snapshot(job_id), "acks": acks}


if __name__ == "__main__":
    captures = {}
    for scenario in ("success", "failed", "cancelled"):
        case = Capture()
        try:
            captures[scenario] = case.capture(scenario)
        finally:
            case.doCleanups()
    print(json.dumps(captures, ensure_ascii=True))
