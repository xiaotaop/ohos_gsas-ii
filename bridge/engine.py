"""Python Bridge engine: the two stable entries from CORE_API §8.

``CoreRuntime.initialize(config_json) -> str`` returns CoreInfo JSON.
``CoreRuntime.execute(request_json, emit_event, is_cancelled) -> str`` runs
one job from ``job.accepted`` to exactly one terminal event on the calling
(dedicated worker) thread and returns the final event JSON, identical to
the last ``emit_event`` payload.

The engine owns the event pipeline, file resolution and cancellation at
stage boundaries.  Computation-specific work is delegated to a *refiner*
object (see :mod:`bridge.core` for the GSAS-II implementation and
:mod:`bridge.fake_core` for the scripted stand-in), so both variants emit
byte-for-byte contract-shaped event flows.
"""

from __future__ import annotations

import contextlib
import io
import json
import platform
import shutil
import time
import traceback
from pathlib import Path
from typing import Any, Callable

from bridge.errors import BridgeError, from_unexpected
from bridge.events import EventStream
from bridge.files import FileCatalog
from bridge.request import parse_request

CONFIG_FIELDS = {
    "schemaVersion",
    "runtimeRoot",
    "workspaceRoot",
    "outputRoot",
    "maxConcurrentJobs",
    "logLevel",
}
ROOT_FIELDS = ("runtimeRoot", "workspaceRoot", "outputRoot")

# Stage index/percent map; stageCount=7 as in the contract examples
# (preparing=0, reading_files=1, the five refinement stages 2..6, saving=7).
STAGE_COUNT = 7
READ_FILES = ("reading_files", 1, 10.0, "正在读取粉末、仪器和相文件")
STAGE_PROGRESS = {
    "before_fitting": (2, 20.0, "正在计算初始 Rwp"),
    "scale_and_background": (3, 35.0, "正在精修比例因子与背底"),
    "cells": (4, 55.0, "正在精修晶胞参数"),
    "microstrain_displacement_atoms": (5, 75.0, "正在精修微应变、位移与原子参数"),
    "preferred_orientation": (6, 90.0, "正在精修择优取向"),
}


class JobCancelled(Exception):
    """Internal signal: cooperative cancel observed at a stage boundary."""


class CoreRuntime:
    """Stateful bridge runtime; the N-API layer keeps exactly one per process."""

    def __init__(self, refiner):
        self.refiner = refiner
        self._config: dict[str, Any] | None = None
        self._catalog: FileCatalog | None = None

    # ------------------------------------------------------------------
    # CORE_API §3.1 / §3.2
    # ------------------------------------------------------------------
    def initialize(self, config_json: str) -> str:
        try:
            config = json.loads(config_json)
        except (json.JSONDecodeError, TypeError) as exc:
            raise BridgeError("INVALID_REQUEST", "config JSON 无法解析", detail=str(exc), cause=exc) from exc
        if not isinstance(config, dict) or set(config) != CONFIG_FIELDS:
            raise BridgeError("INVALID_REQUEST", "config 字段不完整或含未知字段")
        if config["schemaVersion"] != "1.0":
            raise BridgeError("UNSUPPORTED_SCHEMA", f"不支持的配置版本 {config['schemaVersion']!r}")
        if config["maxConcurrentJobs"] != 1:
            raise BridgeError("INVALID_REQUEST", "MVP 的 maxConcurrentJobs 固定为 1")
        config = {
            **config,
            **{key: str(Path(config[key])) for key in ROOT_FIELDS},
        }
        if not all(Path(config[key]).is_absolute() for key in ROOT_FIELDS):
            raise BridgeError("INVALID_REQUEST", "三个根目录必须为绝对路径")
        if self._config is not None:
            if self._config == config:
                return self.core_info_json()
            raise BridgeError("CORE_ALREADY_INITIALIZED", "重复初始化且配置不一致")
        workspace = Path(config["workspaceRoot"])
        for value in (workspace.parent / "imports", *(Path(config[key]) for key in ROOT_FIELDS)):
            value.mkdir(parents=True, exist_ok=True)
        self._config = config
        self._catalog = FileCatalog(workspace, Path(config["outputRoot"]))
        return self.core_info_json()

    def core_info_json(self) -> str:
        return json.dumps(
            {
                "schemaVersion": "1.0",
                "ready": True,
                "pythonVersion": platform.python_version(),
                "gsasCommit": self.refiner.upstream_commit,
                "supportedRecipes": [self.refiner.recipe_id],
            },
            ensure_ascii=False,
        )

    # ------------------------------------------------------------------
    # CORE_API §8 — must run on the dedicated worker thread
    # ------------------------------------------------------------------
    def execute(self, request_json: str, emit_event: Callable[[str], None], is_cancelled: Callable[[], bool]) -> str:
        if self._config is None or self._catalog is None:
            raise BridgeError("CORE_NOT_READY", "核心尚未初始化")
        catalog = self._catalog
        request = parse_request(request_json)
        if request["recipeId"] != self.refiner.recipe_id:
            raise BridgeError("UNSUPPORTED_RECIPE", f"未实现 recipe {request['recipeId']!r}")

        stream = EventStream(request["jobId"])
        stream.emit("job.accepted", {"state": "queued"}, emit_event)
        started = time.perf_counter()
        try:
            final = self._run_job(request, catalog, stream, emit_event, is_cancelled, started)
        except JobCancelled:
            final = stream.emit(
                "job.cancelled",
                {"state": "cancelled", "reason": "用户取消了精修任务"},
                emit_event,
            )
        except BridgeError as exc:
            self._record_private_traceback(catalog, request["jobId"], exc)
            final = stream.emit("job.failed", {"state": "failed", "error": exc.to_error_object()}, emit_event)
        except Exception as exc:  # noqa: BLE001 — contract §9: unknown → INTERNAL_ERROR
            self._record_private_traceback(catalog, request["jobId"], exc)
            mapped = from_unexpected(exc)
            final = stream.emit("job.failed", {"state": "failed", "error": mapped.to_error_object()}, emit_event)
        assert stream.terminal_json == final
        return final

    # ------------------------------------------------------------------
    def _run_job(self, request, catalog, stream, emit_event, is_cancelled, started) -> str:
        dirs = catalog.ensure_job_dirs(request["jobId"])
        self._check_cancel(is_cancelled, stream, emit_event, None)

        stream.progress(emit_event, "validating", READ_FILES[0], READ_FILES[1], STAGE_COUNT, READ_FILES[2], READ_FILES[3])
        paths = self._resolve_inputs(request, catalog)
        stream.log(emit_event, "info", "core", f"已解析 {len(paths)} 个输入文件")

        console = io.StringIO()
        session = self._capturing(console, lambda: self.refiner.prepare(paths, dirs["work"], request))
        stage_results = []
        current_stage: str | None = None
        for stage in self.refiner.stages:
            self._check_cancel(is_cancelled, stream, emit_event, current_stage)
            index, percent, message = STAGE_PROGRESS[stage]
            current_stage = stage
            stream.progress(emit_event, "running", stage, index, STAGE_COUNT, percent, message)
            rwp = self._capturing(console, lambda stage=stage: session.run_stage(stage))
            stage_results.append({"name": stage, "rwpByHistogram": rwp})
            summary = ", ".join(f"{key}={value:.3f}" for key, value in sorted(rwp.items()))
            stream.log(emit_event, "info", "gsas-ii", f"{stage} 完成: Rwp {summary}")
            if request["options"].get("validateAgainstBaseline"):
                session.check_baseline(stage, rwp)

        self._check_cancel(is_cancelled, stream, emit_event, current_stage)
        stream.progress(emit_event, "saving", "saving", STAGE_COUNT, STAGE_COUNT, 97.0, "正在写出 .gpx 与结果文件")
        preferred_orientation = self._capturing(console, session.finish)
        result = self._persist_outputs(
            catalog, request, session, stage_results, preferred_orientation, console.getvalue(), started
        )
        return stream.emit("job.completed", {"state": "succeeded", "result": result}, emit_event)

    @staticmethod
    def _capturing(console: io.StringIO, fn: Callable[[], Any]) -> Any:
        with contextlib.redirect_stdout(console):
            return fn()

    def _resolve_inputs(self, request, catalog: FileCatalog) -> dict[str, Any]:
        paths: dict[str, Any] = {}
        for hist in request["inputs"]["histograms"]:
            instrument = catalog.resolve_verified(hist["instrumentFileId"])
            paths[hist["id"]] = {
                "data": catalog.resolve_verified(hist["dataFileId"]),
                "instrument": instrument,
                "formatHint": hist["formatHint"],
                "role": hist["role"],
            }
            self.refiner.validate_instrument(instrument)
        phase = request["inputs"]["phase"]
        phase_file = catalog.resolve_verified(phase["fileId"])
        paths["phase"] = {"file": phase_file, "name": phase["name"], "id": phase["id"]}
        self.refiner.validate_phase(phase_file)
        return paths

    @staticmethod
    def _check_cancel(is_cancelled, stream, emit_event, current_stage: str | None) -> None:
        if not is_cancelled():
            return
        if current_stage is not None:
            stage, index, percent, _ = (current_stage, *STAGE_PROGRESS[current_stage])
        else:
            stage, index, percent = READ_FILES[:3]
        stream.progress(emit_event, "cancelling", stage, index, STAGE_COUNT, percent, "正在等待当前计算阶段安全结束")
        raise JobCancelled()

    def _persist_outputs(
        self, catalog, request, session, stage_results, preferred_orientation, console_text, started
    ) -> dict[str, Any]:
        job_id = request["jobId"]
        tail = job_id.removeprefix("job_")
        out_dir = catalog.job_output_dir(job_id)
        project_name = request["output"]["projectName"]
        stem = project_name[: -len(".gpx")]
        gpx_dst = out_dir / project_name
        json_dst = out_dir / f"{stem}.json"
        log_dst = out_dir / f"{stem}.log"
        if not request["output"]["overwrite"]:
            for destination in (gpx_dst, json_dst, log_dst):
                if destination.exists():
                    raise BridgeError("OUTPUT_WRITE_FAILED", f"输出文件已存在且 overwrite=false: {destination.name}")
        elapsed = round(time.perf_counter() - started, 3)
        performed = bool(request["options"].get("validateAgainstBaseline"))
        result: dict[str, Any] = {
            "recipeId": self.refiner.recipe_id,
            "upstreamCommit": self.refiner.upstream_commit,
            "elapsedSeconds": elapsed,
            "stages": stage_results,
            "validation": {"performed": performed, "passed": True if performed else None},
            "artifacts": [
                {
                    "fileId": f"file_out_{tail}_gpx",
                    "kind": "project",
                    "displayName": project_name,
                    "mediaType": "application/octet-stream",
                },
                {
                    "fileId": f"file_out_{tail}_json",
                    "kind": "result",
                    "displayName": json_dst.name,
                    "mediaType": "application/json",
                },
                {
                    "fileId": f"file_out_{tail}_log",
                    "kind": "log",
                    "displayName": log_dst.name,
                    "mediaType": "text/plain",
                },
            ],
        }
        if preferred_orientation:
            result["preferredOrientation"] = preferred_orientation
        try:
            shutil.copyfile(session.gpx_path, gpx_dst)
            json_dst.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            log_dst.write_text(console_text or "(no console output)\n", encoding="utf-8")
        except OSError as exc:
            raise BridgeError("OUTPUT_WRITE_FAILED", "结果文件写入失败", detail=str(exc), cause=exc) from exc
        return result

    @staticmethod
    def _record_private_traceback(catalog: FileCatalog, job_id: str, exc: BaseException) -> None:
        try:
            log_dir = catalog.workspace_root / job_id / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            with (log_dir / "traceback.log").open("a", encoding="utf-8") as handle:
                handle.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
                handle.write("\n")
        except OSError:
            pass  # private logging must never mask the contract error
