"""Unified contract error codes and traceback sanitization (CORE_API §9)."""

from __future__ import annotations

import re

ERROR_CODES = (
    "INVALID_REQUEST",
    "UNSUPPORTED_SCHEMA",
    "UNSUPPORTED_RECIPE",
    "JOB_ALREADY_EXISTS",
    "CORE_NOT_READY",
    "CORE_ALREADY_INITIALIZED",
    "BUSY",
    "FILE_NOT_FOUND",
    "FILE_HASH_MISMATCH",
    "UNSUPPORTED_FILE",
    "INVALID_INSTRUMENT_FILE",
    "INVALID_PHASE_FILE",
    "REFINEMENT_FAILED",
    "OUTPUT_WRITE_FAILED",
    "JOB_NOT_FOUND",
    "PROCESS_INTERRUPTED",
    "INTERNAL_ERROR",
)

_RETRYABLE = {
    "CORE_NOT_READY",
    "BUSY",
    "REFINEMENT_FAILED",
    "OUTPUT_WRITE_FAILED",
    "PROCESS_INTERRUPTED",
    "INTERNAL_ERROR",
}

_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
# Absolute Windows/POSIX paths and Python object addresses must never reach
# UI-visible strings (CORE_API §6 job.log rule).
_WIN_PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\s\"']+")
_POSIX_PATH_RE = re.compile(r"(?<![\w])/(?:[^\s/\"']+/)+[^\s/\"']+")
_ADDR_RE = re.compile(r"0x[0-9a-fA-F]+")


def sanitize(text: str) -> str:
    """Strip absolute paths (keep only the file name) and object addresses."""

    def _win(match: re.Match) -> str:
        return match.group(0).replace("\\", "/").rsplit("/", 1)[-1]

    def _posix(match: re.Match) -> str:
        return match.group(0).rsplit("/", 1)[-1]

    cleaned = _WIN_PATH_RE.sub(_win, text)
    cleaned = _POSIX_PATH_RE.sub(_posix, cleaned)
    cleaned = _ADDR_RE.sub("0x…", cleaned)
    return cleaned


class BridgeError(Exception):
    """A contract-level failure carrying a user-safe message.

    The raw cause (including any traceback) belongs in the private job log,
    never in ``message``.
    """

    def __init__(self, code: str, message: str, detail: str = "", cause: BaseException | None = None):
        assert code in ERROR_CODES, f"unknown error code {code!r}"
        assert _CODE_RE.fullmatch(code), f"invalid error code format {code!r}"
        super().__init__(message)
        self.code = code
        self.message = sanitize(message)[:500]
        self.detail = sanitize(detail)[:2000] if detail else ""
        self.retryable = code in _RETRYABLE
        self.cause = cause

    def to_error_object(self) -> dict:
        error = {"code": self.code, "message": self.message, "retryable": self.retryable}
        if self.detail:
            error["detail"] = self.detail
        return error


def from_unexpected(exc: BaseException) -> BridgeError:
    """Map any unknown exception to INTERNAL_ERROR, preserving the cause."""

    return BridgeError(
        "INTERNAL_ERROR",
        f"内部错误: {type(exc).__name__}",
        detail=sanitize(str(exc)),
        cause=exc,
    )
