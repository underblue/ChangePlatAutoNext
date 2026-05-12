"""Ports for external application handoff."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ConnectLauncher(Protocol):
    def open_import(self, file_path: Path, display_name: str | None = None) -> bool: ...
