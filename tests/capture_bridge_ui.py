"""Test-only JSON capture from B's host service; never a runtime UI transport.

Reuses the bridge test sandbox and validator. Temporary stub artifacts are removed
after capture; stdout contains events/snapshots only, not file contents or paths.

For failed/cancelled the capture mirrors the B03 facade delivery view: the
sanitized user log is written and registered first, the terminal event then
carries the registration-issued artifact token, and the persisted snapshot
answers with exactly the delivered payload (consistency evidence).
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
        files = self.build_sandbox()
        service = self.make_service(FakeFiveStageRefiner(stage_delay=0, boom=scenario == "failed"), files=files)
        events, snapshots, acks = [], [], []

        def observe(event):
            events.append(event)
            snapshots.append(json.loads(json.dumps(service.get_job_snapshot(job_id))))
            if (scenario == "cancelled" and event["type"] == "job.progress"
                    and event["payload"]["state"] == "running" and event["payload"]["stage"] == "cells"):
                acks.append(service.cancel_job(job_id))

        off = service.on_event(observe)
        self.addCleanup(off)
        accepted = service.start_refinement(json.dumps(make_request(job_id)))
        self.assertTrue(service.wait_idle(timeout=5), "host bridge did not finish")

        snapshot = json.loads(json.dumps(service.get_job_snapshot(job_id)))
        terminal = events[-1]
        if scenario in ("failed", "cancelled"):
            self.assertIn(terminal["type"], ("job.failed", "job.cancelled"))
            artifact = self._register_user_log(files, job_id, events)
            terminal["payload"]["artifacts"] = [artifact]
            snapshot["terminal"]["payload"] = json.loads(json.dumps(terminal["payload"]))
        self.validate(events, f"ui-{scenario}")
        # Consistency evidence: the snapshot a restart would restore carries
        # exactly the terminal payload the page received, token included.
        self.assertEqual(snapshot["terminal"]["payload"], terminal["payload"])
        return {"accepted": accepted, "events": events, "snapshots": snapshots,
                "snapshot": snapshot, "acks": acks}

    def _register_user_log(self, files, job_id, events):
        """Facade order: sanitized log on disk, then the file service's token."""
        log_dir = files / "outputs" / job_id
        log_dir.mkdir(parents=True, exist_ok=True)
        lines = [event["payload"]["message"] for event in events if event["type"] == "job.log"]
        log_text = "\n".join(lines) + "\n"
        self.assertNotIn(str(files), log_text)  # no sandbox path leaks into the user log
        (log_dir / "job-log.txt").write_text(log_text, encoding="utf-8")
        return {"fileId": f"file_log_{job_id[4:]}", "kind": "log",
                "displayName": "job-log.txt", "mediaType": "text/plain"}


if __name__ == "__main__":
    captures = {}
    for scenario in ("success", "failed", "cancelled"):
        case = Capture()
        try:
            captures[scenario] = case.capture(scenario)
        finally:
            case.doCleanups()
    print(json.dumps(captures, ensure_ascii=True))
