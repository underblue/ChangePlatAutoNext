"""Safe XML parsing and writing."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as StdET

try:
    from defusedxml import ElementTree as SafeET
except ImportError:  # pragma: no cover
    SafeET = None

from change_plate_next.domain.errors import InvalidThreeMfError, MetadataRewriteError
from change_plate_next.domain.policies import ArchiveSafetyPolicy


class SafeXmlStore:
    def __init__(self, policy: ArchiveSafetyPolicy | None = None) -> None:
        self.policy = policy or ArchiveSafetyPolicy()

    def parse_file(self, path: Path) -> StdET.ElementTree:
        if path.stat().st_size > self.policy.max_xml_bytes:
            raise InvalidThreeMfError(f"XML 文件过大，拒绝解析: {path}")
        data = path.read_bytes()
        return self.parse_bytes(data, str(path))

    def parse_bytes(self, data: bytes, label: str) -> StdET.ElementTree:
        if len(data) > self.policy.max_xml_bytes:
            raise MetadataRewriteError(f"XML 文件过大，拒绝解析: {label}")
        if SafeET is not None:
            return StdET.ElementTree(SafeET.fromstring(data))
        text = data.decode("utf-8-sig", errors="replace")
        lowered = text.lower()
        if "<!doctype" in lowered or "<!entity" in lowered:
            raise InvalidThreeMfError(f"XML 文件包含 DOCTYPE 或 ENTITY，拒绝解析: {label}")
        return StdET.ElementTree(StdET.fromstring(text))

    def write(self, tree: StdET.ElementTree, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(path, encoding="utf-8", xml_declaration=True)
