"""FileId resolution against the sandbox layout (CORE_API §4).

The bridge must never accept raw URIs or caller-supplied absolute paths.
FileService is contracted to import user files as::

    files/imports/<fileId>/<原始文件名>

and the bridge derives the imports root from ``workspaceRoot`` (which is
``files/jobs``).  Per-job directories ``input/``, ``work/`` and ``logs/``
live under ``files/jobs/<jobId>/``; finished artifacts are copied to
``files/outputs/<jobId>/``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from bridge.errors import BridgeError

# SHA-256 of the five pinned upstream PbSO4 fixtures (mirrors
# poc/core_refinement.py).  When an imported file's name matches one of
# these fixtures, its content hash must match before refinement starts.
FIXTURE_SHA256 = {
    "PBSO4.XRA": "CA2DA02FC7E17D2FC912DE22A979F8101BA6140F2E8104F9D3AA64F030CA58BB",
    "INST_XRY.PRM": "E59413059BC3B12A51F1C6EEBC5D581470320D05A31F11A41DBB32E16D1D16B9",
    "PBSO4.CWN": "59462BA6D7C72C9800B0B6BF41903F9933ED5AC5ADAB101D27022D5D25CF18BA",
    "INST_D1A.PRM": "A1031174A9B509F889377752F5C095A1DAD49A25FB0A72C057F184F7B321FCEA",
    "PBSO4-WYCKOFF.CIF": "22CBA0B64FB6BF89178FE828FDF63570BFFEBED1485313E78C50C2918A47A970",
}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def imports_root(workspace_root: Path) -> Path:
    return workspace_root.parent / "imports"


class FileCatalog:
    """Reads FileService-managed sandbox files by fileId only."""

    def __init__(self, workspace_root: Path, output_root: Path):
        self.workspace_root = workspace_root
        self.output_root = output_root
        self.imports_root = imports_root(workspace_root)

    def resolve(self, file_id: str) -> Path:
        root = self.imports_root.resolve()
        requested_directory = root / file_id
        if requested_directory.is_symlink():
            raise BridgeError("INVALID_REQUEST", f"fileId 不允许指向符号链接: {file_id!r}")
        directory = requested_directory.resolve()
        if not directory.is_relative_to(root):
            raise BridgeError("INVALID_REQUEST", f"fileId 解析越界: {file_id!r}")
        if not directory.is_dir():
            raise BridgeError("FILE_NOT_FOUND", f"未找到文件 {file_id}")
        candidates = [item for item in directory.iterdir() if item.is_file()]
        if len(candidates) != 1:
            raise BridgeError(
                "FILE_NOT_FOUND",
                f"fileId {file_id} 未指向唯一导入文件",
                detail=f"目录内文件数: {len(candidates)}",
            )
        candidate = candidates[0]
        resolved = candidate.resolve()
        if candidate.is_symlink() or not resolved.is_relative_to(directory):
            raise BridgeError("INVALID_REQUEST", f"fileId 文件解析越界: {file_id!r}")
        return resolved

    def resolve_verified(self, file_id: str) -> Path:
        """Resolve and enforce fixture hashes for the five pinned samples."""
        path = self.resolve(file_id)
        expected = FIXTURE_SHA256.get(path.name.upper())
        if expected is not None:
            actual = sha256_of(path)
            if actual != expected:
                raise BridgeError(
                    "FILE_HASH_MISMATCH",
                    f"文件 {path.name} 与锁定基线哈希不一致",
                    detail=f"expected {expected[:16]}… got {actual[:16]}…",
                )
        return path

    def ensure_job_dirs(self, job_id: str) -> dict[str, Path]:
        base = self.workspace_root / job_id
        dirs = {name: base / name for name in ("input", "work", "logs")}
        for path in dirs.values():
            path.mkdir(parents=True, exist_ok=True)
        return dirs

    def job_output_dir(self, job_id: str) -> Path:
        path = self.output_root / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path
