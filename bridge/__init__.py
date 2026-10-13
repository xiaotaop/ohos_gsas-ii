"""Python Bridge for the GSAS-II HarmonyOS desktop core (member B deliverable).

C++/N-API callers must only use the two stable entry points named in
``docs/CORE_API.md`` section 8:

    initialize(config_json: str) -> str
    execute(request_json: str, emit_event, is_cancelled) -> str

On the HarmonyOS device the embedded CPython imports this module and the
N-API layer calls the functions below against the single dedicated worker
thread.  ``execute`` must never run on the UI thread.

The module-level functions use a process-wide default runtime (real GSAS-II
engine).  Host-side tests and the local harness create their own runtimes
through :class:`bridge.engine.CoreRuntime` instead.
"""

from __future__ import annotations

from bridge.engine import CoreRuntime
from bridge.errors import BridgeError
from bridge import core as _core

__all__ = ["initialize", "execute", "BridgeError"]

_default_runtime: CoreRuntime | None = None


def initialize(config_json: str) -> str:
    global _default_runtime
    if _default_runtime is None:
        _default_runtime = CoreRuntime(_core.make_refiner())
    return _default_runtime.initialize(config_json)


def execute(request_json: str, emit_event, is_cancelled) -> str:
    if _default_runtime is None:
        raise BridgeError(
            "CORE_NOT_READY",
            "核心尚未初始化",
        )
    return _default_runtime.execute(request_json, emit_event, is_cancelled)
