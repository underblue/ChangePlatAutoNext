"""Ports for 3MF package IO."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from change_plate_next.domain.models import Plate, QueueEntry


class PackageReader(Protocol):
    def inspect(self, source: Path) -> tuple[Plate, ...]: ...


class PackageWriter(Protocol):
    def write_merged(self, queue: list[QueueEntry], output: Path) -> Path: ...
