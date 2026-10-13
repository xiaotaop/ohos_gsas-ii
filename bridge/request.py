"""RefinementRequest parsing and validation (CORE_API §5)."""

from __future__ import annotations

import json
import re
from typing import Any

from bridge.errors import BridgeError

JOB_ID_RE = re.compile(r"^job_[A-Za-z0-9_-]{8,64}$")
FILE_ID_RE = re.compile(r"^file_[A-Za-z0-9_-]{8,64}$")
EVENT_ID_RE = re.compile(r"^evt_[A-Za-z0-9_-]{8,80}$")
RECIPE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{2,63}$")
HIST_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
PROJECT_NAME_RE = re.compile(r"^[^/\\]{1,100}\.gpx$")

TOP_FIELDS = {"schemaVersion", "jobId", "operation", "recipeId", "inputs", "options", "output"}
HIST_FIELDS = {"id", "role", "dataFileId", "instrumentFileId", "formatHint"}
PHASE_FIELDS = {"id", "name", "fileId"}


def parse_request(request_json: str) -> dict[str, Any]:
    try:
        request = json.loads(request_json)
    except (json.JSONDecodeError, TypeError) as exc:
        raise BridgeError("INVALID_REQUEST", "请求 JSON 无法解析", detail=str(exc), cause=exc) from exc
    if not isinstance(request, dict):
        raise BridgeError("INVALID_REQUEST", "请求必须是 JSON 对象")
    return validate_request(request)


def validate_request(request: dict[str, Any]) -> dict[str, Any]:
    if set(request) != TOP_FIELDS:
        raise BridgeError("INVALID_REQUEST", "请求顶层字段不完整或含未知字段")
    if request["schemaVersion"] != "1.0":
        raise BridgeError("UNSUPPORTED_SCHEMA", f"不支持的接口版本 {request['schemaVersion']!r}")
    if not JOB_ID_RE.fullmatch(request["jobId"]):
        raise BridgeError("INVALID_REQUEST", "jobId 不符合命名规则")
    if request["operation"] != "powder-refinement":
        raise BridgeError("INVALID_REQUEST", "仅支持 operation=powder-refinement")
    if not RECIPE_ID_RE.fullmatch(request["recipeId"]):
        raise BridgeError("INVALID_REQUEST", "recipeId 不符合命名规则")

    inputs = request["inputs"]
    if not isinstance(inputs, dict) or set(inputs) != {"histograms", "phase"}:
        raise BridgeError("INVALID_REQUEST", "inputs 必须恰含 histograms 与 phase")
    histograms = inputs["histograms"]
    if not isinstance(histograms, list) or not 1 <= len(histograms) <= 8:
        raise BridgeError("INVALID_REQUEST", "histograms 数量必须为 1..8")
    seen_ids: set[str] = set()
    for item in histograms:
        if not isinstance(item, dict) or set(item) != HIST_FIELDS:
            raise BridgeError("INVALID_REQUEST", "histogram 字段不完整或含未知字段")
        if not HIST_ID_RE.fullmatch(item["id"]) or item["id"] in seen_ids:
            raise BridgeError("INVALID_REQUEST", f"histogram id 无效或重复: {item['id']!r}")
        seen_ids.add(item["id"])
        if item["role"] not in {"xray", "neutron", "other"}:
            raise BridgeError("INVALID_REQUEST", f"未知 histogram role: {item['role']!r}")
        if not FILE_ID_RE.fullmatch(item["dataFileId"]):
            raise BridgeError("INVALID_REQUEST", f"dataFileId 无效: {item['dataFileId']!r}")
        if not FILE_ID_RE.fullmatch(item["instrumentFileId"]):
            raise BridgeError("INVALID_REQUEST", f"instrumentFileId 无效: {item['instrumentFileId']!r}")
        if not isinstance(item["formatHint"], str) or not 1 <= len(item["formatHint"]) <= 80:
            raise BridgeError("INVALID_REQUEST", "formatHint 无效")

    phase = inputs["phase"]
    if not isinstance(phase, dict) or set(phase) != PHASE_FIELDS:
        raise BridgeError("INVALID_REQUEST", "phase 字段不完整或含未知字段")
    if not HIST_ID_RE.fullmatch(phase["id"]):
        raise BridgeError("INVALID_REQUEST", f"phase id 无效: {phase['id']!r}")
    if not isinstance(phase["name"], str) or not 1 <= len(phase["name"]) <= 80:
        raise BridgeError("INVALID_REQUEST", "phase.name 无效")
    if not FILE_ID_RE.fullmatch(phase["fileId"]):
        raise BridgeError("INVALID_REQUEST", f"phase fileId 无效: {phase['fileId']!r}")

    options = request["options"]
    if not isinstance(options, dict) or "cycleCount" not in options:
        raise BridgeError("INVALID_REQUEST", "options.cycleCount 必填")
    if not set(options) <= {"cycleCount", "validateAgainstBaseline"}:
        raise BridgeError("INVALID_REQUEST", "options 含未知字段")
    cycles = options["cycleCount"]
    if not isinstance(cycles, int) or isinstance(cycles, bool) or not 0 <= cycles <= 50:
        raise BridgeError("INVALID_REQUEST", "cycleCount 必须为 0..50 的整数")

    output = request["output"]
    if not isinstance(output, dict) or set(output) != {"projectName", "overwrite"}:
        raise BridgeError("INVALID_REQUEST", "output 字段不完整或含未知字段")
    if not PROJECT_NAME_RE.fullmatch(output["projectName"]):
        raise BridgeError("INVALID_REQUEST", "projectName 必须是 .gpx 文件名且不含路径")
    if not isinstance(output["overwrite"], bool):
        raise BridgeError("INVALID_REQUEST", "output.overwrite 必须是布尔值")
    return request
