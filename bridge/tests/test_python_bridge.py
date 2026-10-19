"""Bridge self-test for docs/TEAM_ASSIGNMENT.md §5.3 acceptance criteria.

Stdlib-only for the fake-core scenarios; the real GSAS-II scenario runs
only when ``GSASII.GSASIIscriptable`` and ``numpy`` import cleanly (use the
baseline-rerun interpreter, e.g. ``D:\\miniconda3\\envs\\gsas-poc\\python.exe``).

Generated event streams are validated with the very same semantic checks
the group lead gates on (functions imported from
``scripts/Validate-CoreContracts.py``), so passing here means passing the
contract gate.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_contract_validator():
    spec = importlib.util.spec_from_file_location(
        "g2_contract_validator", REPO_ROOT / "scripts" / "Validate-CoreContracts.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


contract = _load_contract_validator()

from bridge.core import FiveStageRefiner  # noqa: E402
from bridge.engine import CoreRuntime, gsas_native_problem  # noqa: E402
from bridge.errors import BridgeError  # noqa: E402
from bridge.fake_core import FakeFiveStageRefiner  # noqa: E402
from bridge.files import FIXTURE_SHA256, FileCatalog  # noqa: E402
from bridge.request import parse_request  # noqa: E402
from bridge.service import LocalCoreService  # noqa: E402

FIXTURES = {
    "file_pbso4_xra_001": "PBSO4.XRA",
    "file_inst_xry_001": "INST_XRY.PRM",
    "file_pbso4_cwn_001": "PBSO4.CWN",
    "file_inst_d1a_001": "inst_d1a.prm",
    "file_pbso4_cif_001": "PbSO4-Wyckoff.cif",
}


def make_request(job_id: str, recipe_id: str = "powder-five-stage-v1") -> dict:
    return {
        "schemaVersion": "1.0",
        "jobId": job_id,
        "operation": "powder-refinement",
        "recipeId": recipe_id,
        "inputs": {
            "histograms": [
                {
                    "id": "xray",
                    "role": "xray",
                    "dataFileId": "file_pbso4_xra_001",
                    "instrumentFileId": "file_inst_xry_001",
                    "formatHint": "GSAS powder",
                },
                {
                    "id": "neutron",
                    "role": "neutron",
                    "dataFileId": "file_pbso4_cwn_001",
                    "instrumentFileId": "file_inst_d1a_001",
                    "formatHint": "GSAS powder",
                },
            ],
            "phase": {"id": "pbso4", "name": "PbSO4", "fileId": "file_pbso4_cif_001"},
        },
        "options": {"cycleCount": 3, "validateAgainstBaseline": True},
        "output": {"projectName": "PbSO4-refined.gpx", "overwrite": False},
    }


class SandboxMixin:
    def build_sandbox(self) -> Path:
        root = Path(tempfile.mkdtemp(prefix="bridge-sandbox-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        files = root / "files"
        for name in ("runtime", "jobs", "outputs", "imports"):
            (files / name).mkdir(parents=True, exist_ok=True)
        for file_id, fixture in FIXTURES.items():
            directory = files / "imports" / file_id
            directory.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO_ROOT / "tests" / "fixtures" / fixture, directory / fixture)
        return files

    def config_for(self, files: Path) -> dict:
        return {
            "schemaVersion": "1.0",
            "runtimeRoot": str(files / "runtime"),
            "workspaceRoot": str(files / "jobs"),
            "outputRoot": str(files / "outputs"),
            "maxConcurrentJobs": 1,
            "logLevel": "info",
        }

    def make_service(self, refiner=None, files=None) -> LocalCoreService:
        files = files or self.build_sandbox()
        runtime = CoreRuntime(refiner or FakeFiveStageRefiner(stage_delay=0.05))
        service = LocalCoreService(runtime)
        service.initialize(self.config_for(files))
        self.addCleanup(service.shutdown)
        return service

    def collect(self, service: LocalCoreService) -> list[dict]:
        events: list[dict] = []
        service.on_event(events.append)
        return events

    def validate(self, events: list[dict], name: str) -> None:
        contract.validate_events(json.loads(json.dumps(events)), name)


class BridgeFakeCoreTest(unittest.TestCase, SandboxMixin):
    def setUp(self):
        self.files = self.build_sandbox()

    def test_success_flow_matches_contract(self):
        service = self.make_service(files=self.files)
        events = self.collect(service)
        accepted = service.start_refinement(json.dumps(make_request("job_20261013_101")))
        self.assertEqual(accepted["state"], "queued")
        self.assertTrue(service.wait_idle())

        self.assertTrue(events, "no events were emitted")
        self.validate(events, "generated-success")
        types = [event["type"] for event in events]
        self.assertEqual(types[0], "job.accepted")
        self.assertEqual(types[-1], "job.completed")
        self.assertEqual(sum(t in contract.TERMINAL_TYPES for t in types), 1)

        stages = [
            event["payload"]["stage"]
            for event in events
            if event["type"] == "job.progress" and event["payload"]["state"] == "running"
        ]
        self.assertEqual(
            stages,
            [
                "before_fitting",
                "scale_and_background",
                "cells",
                "microstrain_displacement_atoms",
                "preferred_orientation",
            ],
        )
        result = events[-1]["payload"]["result"]
        self.assertEqual(result["validation"], {"performed": True, "passed": True})
        self.assertIn("preferredOrientation", result)

        # §5.3: Python computation must not run on the caller thread.
        # The listener fires on the worker; assert the worker name recorded
        # inside the service rather than trusting thread identity races.
        snapshot = service.get_job_snapshot("job_20261013_101")
        self.assertEqual(snapshot["state"], "succeeded")
        self.assertEqual(snapshot["lastSequence"], len(events) - 1)

        out_dir = self.files / "outputs" / "job_20261013_101"
        for name in ("PbSO4-refined.gpx", "PbSO4-refined.json", "PbSO4-refined.log"):
            self.assertTrue((out_dir / name).is_file(), f"missing artifact {name}")

    def test_public_execute_before_initialize_is_contract_error(self):
        import bridge

        previous = bridge._default_runtime
        bridge._default_runtime = None
        try:
            with self.assertRaises(BridgeError) as ctx:
                bridge.execute("{}", lambda _event: None, lambda: False)
            self.assertEqual(ctx.exception.code, "CORE_NOT_READY")
            self.assertTrue(ctx.exception.retryable)
        finally:
            bridge._default_runtime = previous

    def test_service_rejects_start_before_initialize_synchronously(self):
        service = LocalCoreService(CoreRuntime(FakeFiveStageRefiner()))
        self.addCleanup(service.shutdown)
        with self.assertRaises(BridgeError) as ctx:
            service.start_refinement(json.dumps(make_request("job_20261013_100")))
        self.assertEqual(ctx.exception.code, "CORE_NOT_READY")

    def test_invalid_scalar_types_map_to_invalid_request(self):
        cases = {
            "jobId": lambda request: request.update(jobId=7),
            "histogram id": lambda request: request["inputs"]["histograms"][0].update(id=[]),
            "histogram role": lambda request: request["inputs"]["histograms"][0].update(role=[]),
            "baseline flag": lambda request: request["options"].update(validateAgainstBaseline="yes"),
            "project name": lambda request: request["output"].update(projectName=None),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                request = make_request("job_20261013_100")
                mutate(request)
                with self.assertRaises(BridgeError) as ctx:
                    parse_request(json.dumps(request))
                self.assertEqual(ctx.exception.code, "INVALID_REQUEST")

    def test_file_symlink_escape_is_rejected(self):
        directory = self.files / "imports" / "file_symlink_escape_001"
        directory.mkdir(parents=True)
        outside = self.files / "outside.prm"
        outside.write_bytes(b"outside sandbox mapping\n")
        link = directory / "linked.prm"
        try:
            link.symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"symbolic links unavailable: {exc}")
        catalog = FileCatalog(self.files / "jobs", self.files / "outputs")
        with self.assertRaises(BridgeError) as ctx:
            catalog.resolve("file_symlink_escape_001")
        self.assertEqual(ctx.exception.code, "INVALID_REQUEST")

    def test_events_delivered_on_worker_thread(self):
        service = self.make_service(files=self.files)
        seen_threads: list[str] = []
        service.on_event(lambda event: seen_threads.append(threading.current_thread().name))
        service.start_refinement(json.dumps(make_request("job_20261013_102")))
        self.assertTrue(service.wait_idle())
        self.assertTrue(seen_threads)
        self.assertTrue(all(name == "gsas-core-worker" for name in seen_threads))
        self.assertNotIn(threading.current_thread().name, set(seen_threads))

    def test_busy_second_job(self):
        service = self.make_service(
            refiner=FakeFiveStageRefiner(stage_delay=0.3), files=self.files
        )
        events = self.collect(service)
        service.start_refinement(json.dumps(make_request("job_20261013_103")))
        with self.assertRaises(BridgeError) as ctx:
            service.start_refinement(json.dumps(make_request("job_20261013_104")))
        self.assertEqual(ctx.exception.code, "BUSY")
        self.assertTrue(ctx.exception.retryable)
        self.assertTrue(service.wait_idle(timeout=30))
        # The rejected job must never appear in the event stream.
        self.assertNotIn("job_20261013_104", {event["jobId"] for event in events})
        self.assertEqual(
            sum(event["type"] in contract.TERMINAL_TYPES for event in events), 1
        )
        # After completion a new job is accepted again.
        service.start_refinement(json.dumps(make_request("job_20261013_105")))
        self.assertTrue(service.wait_idle(timeout=30))

    def test_stage_boundary_cancel_and_restart(self):
        service = self.make_service(
            refiner=FakeFiveStageRefiner(stage_delay=0.2), files=self.files
        )
        events: list[dict] = []

        def listener(event: dict) -> None:
            events.append(event)
            if (
                event["jobId"] == "job_20261013_106"
                and event["type"] == "job.progress"
                and event["payload"]["stage"] == "scale_and_background"
            ):
                service.cancel_job("job_20261013_106")

        service.on_event(listener)
        service.start_refinement(json.dumps(make_request("job_20261013_106")))
        self.assertTrue(service.wait_idle(timeout=30))

        types = [event["type"] for event in events]
        self.assertEqual(types[-1], "job.cancelled")
        self.validate(events, "generated-cancelled")
        cancelling = events[-2]
        self.assertEqual(cancelling["payload"]["state"], "cancelling")
        self.assertEqual(cancelling["payload"]["stage"], "scale_and_background")
        self.assertEqual(cancelling["payload"]["stageIndex"], 3)
        self.assertEqual(cancelling["payload"]["percent"], 35.0)
        self.assertEqual(events[-1]["payload"]["reason"], "用户取消了精修任务")

        events.clear()
        service.start_refinement(json.dumps(make_request("job_20261013_107")))
        self.assertTrue(service.wait_idle(timeout=30))
        self.assertEqual(events[-1]["type"], "job.completed")

    def test_failed_instrument_maps_to_contract_error(self):
        # A freshly imported (non-fixture) instrument file with a wrong
        # header: the hash gate passes (unknown name) and the format check
        # must produce INVALID_INSTRUMENT_FILE, as in the contract example.
        directory = self.files / "imports" / "file_inst_bad_0000001"
        directory.mkdir(parents=True)
        (directory / "custom.prm").write_bytes(b"NOT A GSAS INSTRUMENT FILE\n")
        request = make_request("job_20261013_108")
        request["inputs"]["histograms"][0]["instrumentFileId"] = "file_inst_bad_0000001"
        service = self.make_service(files=self.files)
        events = self.collect(service)
        service.start_refinement(json.dumps(request))
        self.assertTrue(service.wait_idle())

        self.validate(events, "generated-failed")
        terminal = events[-1]
        self.assertEqual(terminal["type"], "job.failed")
        error = terminal["payload"]["error"]
        self.assertEqual(error["code"], "INVALID_INSTRUMENT_FILE")
        self.assertFalse(error["retryable"])

    def test_hash_mismatch_detected(self):
        directory = self.files / "imports" / "file_pbso4_xra_001"
        (directory / "PBSO4.XRA").write_text("tampered\n", encoding="utf-8")
        service = self.make_service(files=self.files)
        events = self.collect(service)
        service.start_refinement(json.dumps(make_request("job_20261013_109")))
        self.assertTrue(service.wait_idle())
        self.assertEqual(events[-1]["payload"]["error"]["code"], "FILE_HASH_MISMATCH")

    def test_unknown_file_id(self):
        request = make_request("job_20261013_110")
        request["inputs"]["phase"]["fileId"] = "file_does_not_exist_000000"
        service = self.make_service(files=self.files)
        events = self.collect(service)
        service.start_refinement(json.dumps(request))
        self.assertTrue(service.wait_idle())
        self.assertEqual(events[-1]["type"], "job.failed")
        self.assertEqual(events[-1]["payload"]["error"]["code"], "FILE_NOT_FOUND")

    def test_internal_error_no_traceback_leak(self):
        service = self.make_service(
            refiner=FakeFiveStageRefiner(stage_delay=0.01, boom=True), files=self.files
        )
        events = self.collect(service)
        service.start_refinement(json.dumps(make_request("job_20261013_111")))
        self.assertTrue(service.wait_idle())
        error = events[-1]["payload"]["error"]
        self.assertEqual(error["code"], "INTERNAL_ERROR")
        self.assertTrue(error["retryable"])
        self.assertNotIn("Traceback", error["message"])
        self.assertNotIn("Traceback", error.get("detail", ""))
        # The raw traceback went to the private job log, not the UI channel.
        private = self.files / "jobs" / "job_20261013_111" / "logs" / "traceback.log"
        self.assertTrue(private.is_file())
        self.assertIn("simulated GSAS-II internal failure", private.read_text(encoding="utf-8"))

    def test_synchronous_rejections_emit_no_events(self):
        service = self.make_service(files=self.files)
        events = self.collect(service)
        with self.assertRaises(BridgeError) as ctx:
            service.start_refinement(json.dumps(make_request("job_20261013_112", recipe_id="custom-recipe-v9")))
        self.assertEqual(ctx.exception.code, "UNSUPPORTED_RECIPE")
        with self.assertRaises(BridgeError) as ctx:
            service.start_refinement("{not json")
        self.assertEqual(ctx.exception.code, "INVALID_REQUEST")
        service.start_refinement(json.dumps(make_request("job_20261013_113")))
        self.assertTrue(service.wait_idle())
        # Only the one accepted job produced events.
        self.assertEqual({event["jobId"] for event in events}, {"job_20261013_113"})
        self.validate(events, "generated-single-job")

    def test_duplicate_job_id_rejected(self):
        service = self.make_service(files=self.files)
        service.start_refinement(json.dumps(make_request("job_20261013_114")))
        self.assertTrue(service.wait_idle())
        with self.assertRaises(BridgeError) as ctx:
            service.start_refinement(json.dumps(make_request("job_20261013_114")))
        self.assertEqual(ctx.exception.code, "JOB_ALREADY_EXISTS")

    def test_initialize_idempotent_and_conflict(self):
        service = self.make_service(files=self.files)
        again = service.initialize(self.config_for(self.files))
        self.assertTrue(again["ready"])
        with self.assertRaises(BridgeError) as ctx:
            service.initialize({**self.config_for(self.files), "logLevel": "debug"})
        self.assertEqual(ctx.exception.code, "CORE_ALREADY_INITIALIZED")
        info = again
        self.assertEqual(
            info["gsasCommit"], "2b4aba1bc44de63a3da9d4495944c3b99e389399"
        )
        self.assertEqual(info["supportedRecipes"], ["powder-five-stage-v1"])

    def test_initialize_rejects_invalid_config_types(self):
        cases = {
            "root": ("runtimeRoot", 7),
            "concurrency bool": ("maxConcurrentJobs", True),
            "log level": ("logLevel", None),
        }
        for name, (field, value) in cases.items():
            with self.subTest(name=name):
                config = self.config_for(self.files)
                config[field] = value
                runtime = CoreRuntime(FakeFiveStageRefiner())
                with self.assertRaises(BridgeError) as ctx:
                    runtime.initialize(json.dumps(config))
                self.assertEqual(ctx.exception.code, "INVALID_REQUEST")

    def test_snapshot_unknown_job(self):
        service = self.make_service(files=self.files)
        with self.assertRaises(BridgeError) as ctx:
            service.get_job_snapshot("job_never_started_000")
        self.assertEqual(ctx.exception.code, "JOB_NOT_FOUND")

    def test_release_surface_excludes_pydiffax(self):
        # docs/PHASE3_HANDOFF.md §10.1 — the bridge must never import the
        # DIFFaX extension.  Doc/comment mentions of the name are allowed;
        # import statements are not.
        pattern = re.compile(r"(?:import|from)\s+[\w.]*pydiffax", re.IGNORECASE)
        for source in (REPO_ROOT / "bridge").rglob("*.py"):
            self.assertIsNone(
                pattern.search(source.read_text(encoding="utf-8")),
                f"{source} imports pydiffax",
            )

    def test_generated_events_schema_if_jsonschema(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")
        schema = json.loads((REPO_ROOT / "contracts" / "core-event.schema.json").read_text(encoding="utf-8"))
        service = self.make_service(files=self.files)
        events = self.collect(service)
        service.start_refinement(json.dumps(make_request("job_20261013_115")))
        self.assertTrue(service.wait_idle())
        for event in events:
            jsonschema.validate(event, schema)


class TerminalLogArtifactsTest(unittest.TestCase, SandboxMixin):
    """B03: the delivery view the facade composes for failed/cancelled terminals.

    Registration itself lives in the ArkTS file service (pinned by
    tests/core-bridge-host.test.cjs); the Python side pins that a terminal
    stream enriched with a registered log artifact still passes the very
    validator the group lead gates on, that its absence stays valid, and
    that malformed artifact claims are rejected there.
    """

    FILE_ID = re.compile(r"file_[A-Za-z0-9_-]{8,64}")

    def setUp(self):
        self.files = self.build_sandbox()

    def _run_terminal(self, scenario: str):
        job_id = f"job_artifacts_{scenario}"
        refiner = FakeFiveStageRefiner(stage_delay=0, boom=True) if scenario == "failed" \
            else FakeFiveStageRefiner(stage_delay=0.2)
        service = self.make_service(refiner=refiner, files=self.files)
        events: list[dict] = []

        def listener(event: dict) -> None:
            events.append(event)
            if (scenario == "cancelled" and event["type"] == "job.progress"
                    and event["payload"].get("stage") == "cells"):
                service.cancel_job(job_id)

        service.on_event(listener)
        service.start_refinement(json.dumps(make_request(job_id)))
        self.assertTrue(service.wait_idle(timeout=30))
        expected = "job.failed" if scenario == "failed" else "job.cancelled"
        self.assertEqual(events[-1]["type"], expected)
        return service, job_id, events

    def _deliver_with_log(self, job_id: str, events: list[dict]) -> dict:
        """Facade order: sanitized log on disk, registration token, enriched payload."""
        log_dir = self.files / "outputs" / job_id
        log_dir.mkdir(parents=True, exist_ok=True)
        lines = [event["payload"]["message"] for event in events if event["type"] == "job.log"]
        (log_dir / "job-log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        artifact = {"fileId": f"file_log_{job_id[4:]}", "kind": "log",
                    "displayName": "job-log.txt", "mediaType": "text/plain"}
        events[-1]["payload"]["artifacts"] = [artifact]
        return artifact

    def test_failed_terminal_with_registered_log_stays_contract_valid(self):
        service, job_id, events = self._run_terminal("failed")
        # Copy before enrichment: the reference bridge hands out the payload by
        # shared reference, while the device native copies the raw event at emit.
        raw_snapshot = json.loads(json.dumps(service.get_job_snapshot(job_id)))
        artifact = self._deliver_with_log(job_id, events)
        self.validate(events, f"b03-{job_id}")
        self.assertTrue((self.files / "outputs" / job_id / "job-log.txt").is_file())
        self.assertEqual(events[-1]["payload"]["artifacts"], [artifact])
        # The raw bridge ledger predates registration: the artifact claim is
        # added only by the delivery layer, so snapshot and delivery view
        # agree on the error itself and the token comes from the file service.
        self.assertEqual(raw_snapshot["terminal"]["payload"]["error"], events[-1]["payload"]["error"])
        self.assertNotIn("artifacts", raw_snapshot["terminal"]["payload"])

    def test_cancelled_terminal_with_registered_log_stays_contract_valid(self):
        _, job_id, events = self._run_terminal("cancelled")
        artifact = self._deliver_with_log(job_id, events)
        self.validate(events, f"b03-{job_id}")
        self.assertEqual(artifact["kind"], "log")
        self.assertTrue(self.FILE_ID.fullmatch(artifact["fileId"]))

    def test_missing_artifacts_stay_valid_and_malformed_ones_are_rejected(self):
        _, job_id, events = self._run_terminal("failed")
        self.validate(events, f"b03-{job_id}-no-artifacts")  # optional: absence is legal
        good = {"fileId": f"file_log_{job_id[4:]}", "kind": "log",
                "displayName": "job-log.txt", "mediaType": "text/plain"}
        mutations = [
            [],                                                  # empty array
            [{**good, "kind": "result"}],                        # not a registered log
            [{**good, "fileId": "file_log_" + str(self.files)}],  # path-derived, not a token
            [{**good, "extra": 1}],                              # unregistered fields
            [dict(good), dict(good)],                            # duplicate token
            [good, []],                                          # non-object entry
        ]
        for mutation in mutations:
            with self.subTest(artifacts=mutation):
                payload = dict(events[-1]["payload"], artifacts=mutation)
                with self.assertRaises(ValueError):
                    contract.validate_terminal_log_artifacts(payload, "mutation")


def _register_native_dll_dirs() -> None:
    """Windows: expose MinGW runtime dirs (libgfortran etc.) to the loader.

    Mirrors ``--dll-dir`` handling in poc/core_refinement.py.  Set
    ``GSAS_DLL_DIRS`` to semicolon-separated directories before running the
    real-mode suite.
    """
    if os.name != "nt":
        return
    for directory in filter(None, os.environ.get("GSAS_DLL_DIRS", "").split(";")):
        path = Path(directory)
        if path.is_dir():
            os.add_dll_directory(str(path))


def _gsas_available() -> bool:
    _register_native_dll_dirs()
    try:
        import numpy  # noqa: F401
        import GSASII.GSASIIscriptable  # noqa: F401
    except Exception:
        return False
    return True


@unittest.skipUnless(_gsas_available(), "GSAS-II runtime unavailable (run with the gsas-poc interpreter)")
class BridgeRealGsasTest(unittest.TestCase, SandboxMixin):
    def test_real_five_stage_flow(self):
        from bridge.core import EXPECTED_PO, FiveStageRefiner

        files = self.build_sandbox()
        service = self.make_service(refiner=FiveStageRefiner(), files=files)
        events: list[dict] = []
        service.on_event(events.append)
        service.start_refinement(json.dumps(make_request("job_20261013_201")))
        self.assertTrue(service.wait_idle(timeout=300))

        self.validate(events, "generated-real-success")
        result = events[-1]["payload"]["result"]
        # validateAgainstBaseline=True means the engine already enforced
        # rtol=1e-4 on every stage Rwp; a failure would have produced
        # job.failed instead of the completed event below.
        self.assertEqual(result["validation"], {"performed": True, "passed": True})
        self.assertEqual(len(result["stages"]), 5)
        po = result["preferredOrientation"]
        self.assertAlmostEqual(po["C(2,0)"], EXPECTED_PO[0], delta=0.002)
        self.assertAlmostEqual(po["C(2,2)"], EXPECTED_PO[1], delta=0.002)
        out_dir = files / "outputs" / "job_20261013_201"
        self.assertGreater((out_dir / "PbSO4-refined.gpx").stat().st_size, 1000)
        self.assertTrue((out_dir / "PbSO4-refined.json").is_file())
        self.assertTrue((out_dir / "PbSO4-refined.log").is_file())


class NativePreflightTest(unittest.TestCase, SandboxMixin):
    """CORE_API §8: a payload without the compiled modules fails at initialize."""

    def test_fake_refiner_skips_the_native_probe(self):
        files = self.build_sandbox()
        service = LocalCoreService(CoreRuntime(FakeFiveStageRefiner(stage_delay=0)))
        self.addCleanup(service.shutdown)
        with mock.patch("bridge.engine.gsas_native_problem", return_value="boom") as probe:
            info = service.initialize(self.config_for(files))
        probe.assert_not_called()
        self.assertTrue(info["ready"])

    def test_missing_native_modules_fail_initialize_with_core_not_ready(self):
        files = self.build_sandbox()
        service = LocalCoreService(CoreRuntime(FiveStageRefiner()))
        self.addCleanup(service.shutdown)
        with mock.patch("bridge.engine.gsas_native_problem",
                        return_value="缺少 GSAS-II 原生扩展: pyspg"):
            with self.assertRaises(BridgeError) as ctx:
                service.initialize(self.config_for(files))
        self.assertEqual(ctx.exception.code, "CORE_NOT_READY")
        self.assertTrue(ctx.exception.retryable)
        self.assertIn("pyspg", ctx.exception.detail)


class GsasNativeProbeTest(unittest.TestCase):
    def test_all_modules_present(self):
        with mock.patch("bridge.engine.importlib.import_module", return_value=object()):
            self.assertIsNone(gsas_native_problem())

    def test_reports_only_missing_modules(self):
        def fake(name):
            if name == "GSASII.pyspg":
                raise ImportError("no pyspg")
            return object()

        with mock.patch("bridge.engine.importlib.import_module", side_effect=fake):
            problem = gsas_native_problem()
        self.assertIn("pyspg", problem)
        self.assertNotIn("pypowder", problem)

    def test_reports_gsas_package_failure(self):
        def fake(name):
            if name == "GSASII":
                raise ImportError("no GSAS-II")
            return object()

        with mock.patch("bridge.engine.importlib.import_module", side_effect=fake):
            problem = gsas_native_problem()
        self.assertIn("GSAS-II 无法导入", problem)


if __name__ == "__main__":
    unittest.main(verbosity=2)
