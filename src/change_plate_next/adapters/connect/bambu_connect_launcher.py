"""Bambu Connect URL launcher."""

from __future__ import annotations

import webbrowser
from pathlib import Path
from urllib.parse import urlencode


def build_import_url(file_path: Path, display_name: str | None = None, version: str = "1.0.0") -> str:
    resolved = file_path.expanduser().resolve()
    query = urlencode({"path": str(resolved), "name": display_name or resolved.name, "version": version})
    return f"bambu-connect://import-file?{query}"


class BambuConnectLauncher:
    def __init__(self, opener=webbrowser.open, version: str = "1.0.0") -> None:
        self.opener = opener
        self.version = version

    def open_import(self, file_path: Path, display_name: str | None = None) -> bool:
        return bool(self.opener(build_import_url(file_path, display_name, self.version)))
