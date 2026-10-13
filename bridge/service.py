"""Local CoreService harness (host-side stand-in for ArkTS CoreService + N-API).

Simulates exactly what the C++ bridge will do on device (CORE_API §3, §7,
§10):

* one dedicated worker thread runs ``execute`` serially — the calling
  ("UI") thread only enqueues and receives events;
* ``maxConcurrentJobs=1``: a second concurrent job is rejected
  synchronously with ``BUSY`` and never produces events;
* ``jobId`` uniqueness across the process lifetime (``JOB_ALREADY_EXISTS``);
* cooperative cancellation flips a flag observed at stage boundaries;
* snapshots expose the latest state, sequence, percent and terminal summary.

On device the ArkTS-facing surface is the same minus Python: N-API would
embed this logic in C++.  Keeping it here lets member A (UI) and member B
(core) integrate and test the full event flow long before the HAP exists.
"""

from __future__ import annotations

import json
import queue
import threading
from typing import Any, Callable

from bridge.engine import CoreRuntime
from bridge.errors import BridgeError
from bridge.events import TERMINAL_TYPES, utc_timestamp
from bridge.request import parse_request

EventCallback = Callable[[dict[str, Any]], None]


class LocalCoreService:
    def __init__(self, runtime: CoreRuntime):
        self._runtime = runtime
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._worker: threading.Thread | None = None
        self._lock = threading.Lock()
        self._active_job: str | None = None
        self._cancel_flags: dict[str, threading.Event] = {}
        self._seen_job_ids: set[str] = set()
        self._snapshots: dict[str, dict[str, Any]] = {}
        self._listeners: list[EventCallback] = []
        self._stop = threading.Event()

    # ------------------------------------------------------------------
    def initialize(self, config: dict[str, Any]) -> dict[str, Any]:
        return json.loads(self._runtime.initialize(json.dumps(config, ensure_ascii=False)))

    def on_event(self, callback: EventCallback) -> Callable[[], None]:
        self._listeners.append(callback)

        def unsubscribe() -> None:
            try:
                self._listeners.remove(callback)
            except ValueError:
                pass

        return unsubscribe

    # ------------------------------------------------------------------
    # CORE_API §3.3 — returns JobAccepted JSON, or raises BridgeError for
    # synchronous rejections (INVALID_REQUEST, UNSUPPORTED_RECIPE,
    # JOB_ALREADY_EXISTS, BUSY, CORE_NOT_READY).
    # ------------------------------------------------------------------
    def start_refinement(self, request_json: str) -> dict[str, Any]:
        if not self._runtime.ready:
            raise BridgeError("CORE_NOT_READY", "核心尚未初始化")
        # Cheap synchronous validation first (CORE_API §5): structural and
        # recipe errors never create a job and never emit events.
        request = parse_request(request_json)
        if request["recipeId"] != self._runtime.refiner.recipe_id:
            raise BridgeError("UNSUPPORTED_RECIPE", f"未实现 recipe {request['recipeId']!r}")
        job_id = request["jobId"]
        with self._lock:
            if job_id in self._seen_job_ids:
                raise BridgeError("JOB_ALREADY_EXISTS", f"jobId {job_id} 已存在")
            if self._active_job is not None:
                raise BridgeError("BUSY", f"任务 {self._active_job} 正在运行")
            self._seen_job_ids.add(job_id)
            self._active_job = job_id
            self._cancel_flags[job_id] = threading.Event()
            self._snapshots[job_id] = {
                "jobId": job_id,
                "state": "queued",
                "lastSequence": -1,
                "percent": 0.0,
                "stage": None,
                "terminal": None,
            }
        if self._worker is None:
            self._worker = threading.Thread(target=self._worker_loop, name="gsas-core-worker", daemon=True)
            self._worker.start()
        self._queue.put(request_json)
        return {"schemaVersion": "1.0", "jobId": job_id, "state": "queued", "acceptedAt": utc_timestamp()}

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            if job_id not in self._cancel_flags or self._active_job != job_id:
                raise BridgeError("JOB_NOT_FOUND", f"无法取消未知或已结束的任务 {job_id}")
            self._cancel_flags[job_id].set()
        return {"schemaVersion": "1.0", "jobId": job_id, "requested": True}

    def get_job_snapshot(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            if job_id not in self._snapshots:
                raise BridgeError("JOB_NOT_FOUND", f"未知任务 {job_id}")
            return json.loads(json.dumps(self._snapshots[job_id]))

    def shutdown(self, timeout: float = 60.0) -> None:
        self._stop.set()
        worker = self._worker
        if worker is not None:
            worker.join(timeout=timeout)

    def wait_idle(self, timeout: float = 120.0) -> bool:
        """Block until the queue drains and the active job reaches terminal."""
        import time

        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self._lock:
                active = self._active_job
            if active is None and self._queue.empty():
                return True
            time.sleep(0.01)
        return False

    def _dispatch(self, event: dict[str, Any]) -> None:
        # A raising UI listener must never abort the running job (contract
        # §5.3 / §11.8: core stability is independent of the interface layer).
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------
    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                request_json = self._queue.get(timeout=0.05)
            except queue.Empty:
                continue
            job_id = json.loads(request_json)["jobId"]
            cancel_flag = self._cancel_flags[job_id]

            def emit_event(event_json: str) -> None:
                event = json.loads(event_json)
                self._record_event(event)
                self._dispatch(event)

            def is_cancelled() -> bool:
                return cancel_flag.is_set()

            try:
                terminal_json = self._runtime.execute(request_json, emit_event, is_cancelled)
            except BridgeError as exc:
                # Synchronous rejection before any event was emitted:
                # surface it as the job's single terminal failed event.
                terminal = {
                    "schemaVersion": "1.0",
                    "eventId": f"evt_{job_id.removeprefix('job_')}_sync",
                    "jobId": job_id,
                    "sequence": 0,
                    "timestamp": utc_timestamp(),
                    "type": "job.failed",
                    "payload": {"state": "failed", "error": exc.to_error_object()},
                }
                self._record_event(terminal)
                self._dispatch(terminal)
                terminal_json = json.dumps(terminal, ensure_ascii=False)
            finally:
                with self._lock:
                    self._active_job = None
                    self._cancel_flags.pop(job_id, None)
            self._queue.task_done()

    def _record_event(self, event: dict[str, Any]) -> bool:
        """Update snapshot; return False when the event arrived too late."""
        job_id = event["jobId"]
        with self._lock:
            snapshot = self._snapshots.get(job_id)
            if snapshot is None:
                return False
            if event["type"] in TERMINAL_TYPES:
                if snapshot["terminal"] is not None:
                    raise RuntimeError(f"job {job_id} produced a second terminal event")
                snapshot["terminal"] = {"type": event["type"], "payload": event["payload"]}
                state = {
                    "job.completed": "succeeded",
                    "job.failed": "failed",
                    "job.cancelled": "cancelled",
                }[event["type"]]
                snapshot["state"] = state
            else:
                snapshot["state"] = event["payload"].get("state", snapshot["state"])
            snapshot["lastSequence"] = event["sequence"]
            if event["type"] == "job.progress":
                snapshot["percent"] = event["payload"]["percent"]
                snapshot["stage"] = event["payload"]["stage"]
            return True
