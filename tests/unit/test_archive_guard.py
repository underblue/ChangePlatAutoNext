import zipfile

import pytest

from change_plate_next.adapters.bambu_3mf.archive_guard import ArchiveGuard
from change_plate_next.domain.errors import UnsafeArchiveError


def test_archive_guard_rejects_path_traversal(tmp_path) -> None:
    archive = tmp_path / "bad.3mf"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../evil.txt", "x")
    guard = ArchiveGuard()
    with pytest.raises(UnsafeArchiveError):
        guard.extract_to(archive, tmp_path / "out")


def test_archive_guard_extracts_safe_archive(tmp_path) -> None:
    archive = tmp_path / "ok.3mf"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("Metadata/slice_info.config", "<config />")
    guard = ArchiveGuard()
    guard.extract_to(archive, tmp_path / "out")
    assert (tmp_path / "out" / "Metadata" / "slice_info.config").exists()
