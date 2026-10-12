#!/usr/bin/env python3
"""Validate the checked-in v1 core API schemas and example payloads.

The semantic checks use only the Python standard library. If the optional
``jsonschema`` package is installed, the examples are also validated against
the Draft 2020-12 schemas.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"
EXAMPLES = CONTRACTS / "examples"
JOB_ID = re.compile(r"^job_[A-Za-z0-9_-]{8,64}$")
FILE_ID = re.compile(r"^file_[A-Za-z0-9_-]{8,64}$")
EVENT_ID = re.compile(r"^evt_[A-Za-z0-9_-]{8,80}$")
TERMINAL_TYPES = {"job.completed", "job.failed", "job.cancelled"}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_timestamp(value: str, context: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{context}: invalid ISO 8601 timestamp {value!r}") from exc
    require(parsed.tzinfo is not None, f"{context}: timestamp must include a timezone")


def validate_request(request: dict[str, Any]) -> None:
    required = {
        "schemaVersion",
        "jobId",
        "operation",
        "recipeId",
        "inputs",
        "options",
        "output",
    }
    require(set(request) == required, "request: unexpected or missing top-level fields")
    require(request["schemaVersion"] == "1.0", "request: unsupported schemaVersion")
    require(bool(JOB_ID.fullmatch(request["jobId"])), "request: invalid jobId")
    require(request["operation"] == "powder-refinement", "request: invalid operation")
    require(request["recipeId"] == "powder-five-stage-v1", "request: unsupported example recipe")

    inputs = request["inputs"]
    histograms = inputs["histograms"]
    require(1 <= len(histograms) <= 8, "request: histogram count must be 1..8")
    ids = [item["id"] for item in histograms]
    require(len(ids) == len(set(ids)), "request: histogram ids must be unique")
    for index, histogram in enumerate(histograms):
        context = f"request.histograms[{index}]"
        require(
            bool(FILE_ID.fullmatch(histogram["dataFileId"])),
            f"{context}: invalid dataFileId",
        )
        require(
            bool(FILE_ID.fullmatch(histogram["instrumentFileId"])),
            f"{context}: invalid instrumentFileId",
        )

    require(bool(FILE_ID.fullmatch(inputs["phase"]["fileId"])), "request: invalid phase fileId")
    cycle_count = request["options"]["cycleCount"]
    require(type(cycle_count) is int and 0 <= cycle_count <= 50, "request: cycleCount must be 0..50")
    project_name = request["output"]["projectName"]
    require(project_name.lower().endswith(".gpx"), "request: projectName must end in .gpx")
    require("/" not in project_name and "\\" not in project_name, "request: projectName must be a filename")


def validate_event_payload(event: dict[str, Any], context: str) -> None:
    event_type = event["type"]
    payload = event["payload"]
    if event_type == "job.accepted":
        require(payload == {"state": "queued"}, f"{context}: invalid accepted payload")
    elif event_type == "job.progress":
        require(payload["state"] in {"validating", "running", "saving", "cancelling"}, f"{context}: invalid progress state")
        require(0 <= payload["percent"] <= 100, f"{context}: percent must be 0..100")
        require(0 <= payload["stageIndex"] <= payload["stageCount"], f"{context}: invalid stage index")
    elif event_type == "job.log":
        require(payload["level"] in {"debug", "info", "warning", "error"}, f"{context}: invalid log level")
    elif event_type == "job.completed":
        require(payload["state"] == "succeeded", f"{context}: invalid completed state")
        result = payload["result"]
        require(result["recipeId"], f"{context}: missing recipeId")
        require(re.fullmatch(r"[0-9a-f]{40}", result["upstreamCommit"]) is not None, f"{context}: invalid commit")
        require(result["elapsedSeconds"] >= 0, f"{context}: invalid elapsedSeconds")
        require(len(result["stages"]) > 0, f"{context}: result must contain stages")
        require(len(result["artifacts"]) > 0, f"{context}: result must contain artifacts")
        for artifact in result["artifacts"]:
            require(bool(FILE_ID.fullmatch(artifact["fileId"])), f"{context}: invalid artifact fileId")
    elif event_type == "job.failed":
        require(payload["state"] == "failed", f"{context}: invalid failed state")
        error = payload["error"]
        require(re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", error["code"]) is not None, f"{context}: invalid error code")
        require(type(error["retryable"]) is bool, f"{context}: retryable must be boolean")
        require("Traceback" not in error["message"], f"{context}: traceback leaked into user message")
    elif event_type == "job.cancelled":
        require(payload["state"] == "cancelled", f"{context}: invalid cancelled state")
        require(bool(payload["reason"]), f"{context}: missing cancellation reason")
    else:
        raise ValueError(f"{context}: unknown event type {event_type!r}")


def validate_events(events: list[dict[str, Any]], name: str) -> None:
    require(len(events) >= 2, f"{name}: expected at least accepted and terminal events")
    job_ids = {event["jobId"] for event in events}
    require(len(job_ids) == 1, f"{name}: all events must belong to one job")
    require(bool(JOB_ID.fullmatch(next(iter(job_ids)))), f"{name}: invalid jobId")
    require(events[0]["type"] == "job.accepted", f"{name}: first event must be job.accepted")

    expected_sequence = 0
    previous_percent = -1.0
    terminal_count = 0
    event_ids: set[str] = set()
    for index, event in enumerate(events):
        context = f"{name}[{index}]"
        require(event["schemaVersion"] == "1.0", f"{context}: unsupported schemaVersion")
        require(bool(EVENT_ID.fullmatch(event["eventId"])), f"{context}: invalid eventId")
        require(event["eventId"] not in event_ids, f"{context}: duplicate eventId")
        event_ids.add(event["eventId"])
        require(event["sequence"] == expected_sequence, f"{context}: sequence must be contiguous")
        expected_sequence += 1
        validate_timestamp(event["timestamp"], context)
        validate_event_payload(event, context)

        if event["type"] == "job.progress":
            percent = float(event["payload"]["percent"])
            require(percent >= previous_percent, f"{context}: progress percent moved backwards")
            previous_percent = percent
        if event["type"] in TERMINAL_TYPES:
            terminal_count += 1
            require(index == len(events) - 1, f"{context}: terminal event must be last")

    require(terminal_count == 1, f"{name}: expected exactly one terminal event")


def optional_jsonschema_validation(
    request_schema: dict[str, Any],
    event_schema: dict[str, Any],
    request: dict[str, Any],
    event_sets: list[list[dict[str, Any]]],
) -> str:
    try:
        import jsonschema
    except ImportError:
        return "jsonschema not installed; standard-library semantic validation used"

    jsonschema.Draft202012Validator.check_schema(request_schema)
    jsonschema.Draft202012Validator.check_schema(event_schema)
    jsonschema.validate(request, request_schema)
    for events in event_sets:
        for event in events:
            jsonschema.validate(event, event_schema)
    return f"JSON Schema validation used jsonschema {jsonschema.__version__}"


def main() -> int:
    request_schema = load(CONTRACTS / "refinement-request.schema.json")
    event_schema = load(CONTRACTS / "core-event.schema.json")
    request = load(EXAMPLES / "refinement-request.json")
    success_events = load(EXAMPLES / "core-events-success.json")
    failed_events = load(EXAMPLES / "core-events-failed.json")
    cancelled_events = load(EXAMPLES / "core-events-cancelled.json")

    validate_request(request)
    validate_events(success_events, "core-events-success")
    validate_events(failed_events, "core-events-failed")
    validate_events(cancelled_events, "core-events-cancelled")
    schema_status = optional_jsonschema_validation(
        request_schema,
        event_schema,
        request,
        [success_events, failed_events, cancelled_events],
    )

    print("PASS refinement request example")
    print("PASS successful event sequence")
    print("PASS failed event sequence")
    print("PASS cancelled event sequence")
    print(f"PASS {schema_status}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
