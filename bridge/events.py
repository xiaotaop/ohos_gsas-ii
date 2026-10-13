"""CoreEvent construction with contract invariants enforced (CORE_API §6)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

TERMINAL_TYPES = frozenset({"job.completed", "job.failed", "job.cancelled"})

EmitEvent = Callable[[str], None]


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class EventStream:
    """Per-job event emitter.

    Guarantees: contiguous ``sequence`` from 0, process-unique ``eventId``,
    monotonically non-decreasing ``percent`` inside ``job.progress``, and at
    most one terminal event after which emitting raises.
    """

    def __init__(self, job_id: str):
        self.job_id = job_id
        self._sequence = 0
        self._last_percent = -1.0
        self.terminal_json: str | None = None
        self.events: list[dict[str, Any]] = []

    def _event_id(self) -> str:
        tail = self.job_id.removeprefix("job_")
        return f"evt_{tail}_{self._sequence:04d}"

    def emit(self, event_type: str, payload: dict[str, Any], emit_event: EmitEvent) -> str:
        if self.terminal_json is not None:
            raise RuntimeError(f"event {event_type!r} emitted after terminal event")
        if event_type == "job.progress":
            percent = float(payload["percent"])
            if percent < self._last_percent:
                percent = self._last_percent
                payload = {**payload, "percent": percent}
            self._last_percent = percent
        event = {
            "schemaVersion": "1.0",
            "eventId": self._event_id(),
            "jobId": self.job_id,
            "sequence": self._sequence,
            "timestamp": utc_timestamp(),
            "type": event_type,
            "payload": payload,
        }
        self._sequence += 1
        rendered = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        self.events.append(event)
        if event_type in TERMINAL_TYPES:
            self.terminal_json = rendered
        emit_event(rendered)
        return rendered

    def progress(
        self,
        emit_event: EmitEvent,
        state: str,
        stage: str,
        stage_index: int,
        stage_count: int,
        percent: float,
        message: str,
    ) -> str:
        return self.emit(
            "job.progress",
            {
                "state": state,
                "stage": stage,
                "stageIndex": stage_index,
                "stageCount": stage_count,
                "percent": percent,
                "message": message,
            },
            emit_event,
        )

    def log(self, emit_event: EmitEvent, level: str, source: str, message: str) -> str:
        from bridge.errors import sanitize

        return self.emit(
            "job.log",
            {"level": level, "source": source, "message": sanitize(message)[:2000]},
            emit_event,
        )
