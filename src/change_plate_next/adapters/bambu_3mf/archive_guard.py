"""Safe 3MF archive inspection and extraction."""

from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

from change_plate_next.domain.errors import UnsafeArchiveError
from change_plate_next.domain.policies import ArchiveSafetyPolicy


@dataclass(frozen=True, slots=True)
class ArchiveManifest:
    files: tuple[str, ...]
    total_uncompressed_bytes: int


def is_symlink_member(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0o170000
    return mode == 0o120000


class ArchiveGuard:
    def __init__(self, policy: ArchiveSafetyPolicy | None = None) -> None:
        self.policy = policy or ArchiveSafetyPolicy()

    def safe_member_path(self, root_dir: Path, member_name: str) -> Path:
        if self.policy.reject_backslash_paths and "\\" in member_name:
            raise UnsafeArchiveError(f"3MF 内部路径包含反斜杠，已拒绝: {member_name}")
        if member_name.startswith("/") or member_name.startswith("../"):
            raise UnsafeArchiveError(f"3MF 内部路径不安全，已拒绝: {member_name}")
        parts = Path(member_name).parts
        if any(part in {"", ".", ".."} for part in parts):
            raise UnsafeArchiveError(f"3MF 内部路径不安全，已拒绝: {member_name}")
        target = (root_dir / member_name).resolve()
        root = root_dir.resolve()
        if target != root and root not in target.parents:
            raise UnsafeArchiveError(f"3MF 内部路径越界，已拒绝: {member_name}")
        return target

    def inspect(self, source: Path) -> ArchiveManifest:
        with zipfile.ZipFile(source, "r") as archive:
            bad_member = archive.testzip()
            if bad_member is not None:
                raise UnsafeArchiveError(f"3MF CRC 校验失败: {bad_member}")
            infos = archive.infolist()
            if len(infos) > self.policy.max_files:
                raise UnsafeArchiveError(f"3MF 文件数量过多，已拒绝: {len(infos)}")
            total = 0
            names: list[str] = []
            for info in infos:
                if info.is_dir():
                    continue
                if self.policy.reject_symlinks and is_symlink_member(info):
                    raise UnsafeArchiveError(f"3MF 包含符号链接，已拒绝: {info.filename}")
                if info.file_size > self.policy.max_single_file_bytes:
                    raise UnsafeArchiveError(f"3MF 单个文件过大，已拒绝: {info.filename}")
                total += info.file_size
                if total > self.policy.max_uncompressed_bytes:
                    raise UnsafeArchiveError("3MF 解压后体积过大，已拒绝")
                if info.compress_size and info.file_size / max(1, info.compress_size) > self.policy.max_compression_ratio:
                    raise UnsafeArchiveError(f"3MF 压缩比异常，已拒绝: {info.filename}")
                names.append(info.filename)
            return ArchiveManifest(tuple(names), total)

    def extract_to(self, source: Path, root_dir: Path) -> ArchiveManifest:
        manifest = self.inspect(source)
        with zipfile.ZipFile(source, "r") as archive:
            for info in archive.infolist():
                target = self.safe_member_path(root_dir, info.filename)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info, "r") as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
        return manifest
