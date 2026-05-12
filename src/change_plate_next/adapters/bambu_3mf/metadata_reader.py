"""Read Bambu sliced 3MF metadata into domain objects."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

from change_plate_next.adapters.bambu_3mf.archive_guard import ArchiveGuard
from change_plate_next.adapters.bambu_3mf.safe_xml import SafeXmlStore
from change_plate_next.domain.errors import InvalidThreeMfError, MissingMetadataError, UnslicedThreeMfError
from change_plate_next.domain.models import (
    FilamentSignature,
    FilamentUsage,
    LocalFilamentId,
    Plate,
    PlateAssetRefs,
    PlateId,
)


def float_value(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def metadata_value(plate_node: ET.Element, key: str, default: str = "") -> str:
    for node in plate_node.findall("metadata"):
        if node.attrib.get("key") == key:
            return node.attrib.get("value", default)
    return default


class MetadataReader:
    def __init__(self, xml: SafeXmlStore | None = None) -> None:
        self.xml = xml or SafeXmlStore()

    def read_plates(self, root_dir: Path, source_package: Path) -> tuple[Plate, ...]:
        config_path = root_dir / "Metadata" / "slice_info.config"
        if not config_path.exists():
            raise MissingMetadataError(
                f"缺少 Metadata/slice_info.config: {source_package}",
                suggestion="请确认导入的是 Bambu/Orca 已切片 3MF。",
            )
        tree = self.xml.parse_file(config_path)
        model_settings = self._model_settings(root_dir)
        plates: list[Plate] = []
        for plate_node in tree.getroot().findall("plate"):
            index_text = metadata_value(plate_node, "index")
            if not index_text.isdigit():
                continue
            index = int(index_text)
            meta = model_settings.get(index, {})
            gcode = self._metadata_path(root_dir, meta.get("gcode_file"), root_dir / "Metadata" / f"plate_{index}.gcode")
            if not gcode.exists():
                continue
            assets = PlateAssetRefs(
                gcode=gcode,
                preview=self._metadata_path(root_dir, meta.get("thumbnail_file"), root_dir / "Metadata" / f"plate_{index}.png"),
                small_preview=self._metadata_path(root_dir, meta.get("thumbnail_no_light_file"), root_dir / "Metadata" / f"plate_no_light_{index}.png"),
                top_preview=self._metadata_path(root_dir, meta.get("top_file"), root_dir / "Metadata" / f"top_{index}.png"),
                pick_preview=self._metadata_path(root_dir, meta.get("pick_file"), root_dir / "Metadata" / f"pick_{index}.png"),
                bbox_json=self._metadata_path(root_dir, meta.get("pattern_bbox_file"), root_dir / "Metadata" / f"plate_{index}.json"),
            )
            filaments = tuple(self._filament(node) for node in plate_node.findall("filament"))
            plates.append(
                Plate(
                    id=PlateId(f"{source_package.resolve()}#plate_{index}"),
                    source_package=source_package,
                    package_root=root_dir,
                    source_index=index,
                    display_name=f"{source_package.name} / plate_{index}",
                    assets=assets,
                    prediction_seconds=float_value(metadata_value(plate_node, "prediction")),
                    weight_g=float_value(metadata_value(plate_node, "weight")),
                    filaments=filaments,
                )
            )
        if not plates:
            raise self._missing_plate_error(root_dir, source_package)
        return tuple(plates)

    def _filament(self, node: ET.Element) -> FilamentUsage:
        attrs = dict(node.attrib)
        return FilamentUsage(
            local_id=LocalFilamentId(int(attrs.get("id", "1"))),
            tray_info_idx=attrs.get("tray_info_idx", ""),
            signature=FilamentSignature(
                color=attrs.get("color", "#808080"),
                material=attrs.get("type", ""),
                nozzle_diameter=attrs.get("nozzle_diameter", ""),
            ),
            used_m=float_value(attrs.get("used_m")),
            used_g=float_value(attrs.get("used_g")),
            raw_attributes=attrs,
        )

    def _model_settings(self, root_dir: Path) -> dict[int, dict[str, str]]:
        path = root_dir / "Metadata" / "model_settings.config"
        if not path.exists():
            return {}
        tree = self.xml.parse_file(path)
        result: dict[int, dict[str, str]] = {}
        for plate_node in tree.getroot().findall("plate"):
            values = {node.attrib.get("key", ""): node.attrib.get("value", "") for node in plate_node.findall("metadata")}
            raw_index = values.get("plater_id", "")
            if not raw_index.isdigit():
                match = re.search(r"plate_(\d+)\.gcode$", values.get("gcode_file", ""))
                raw_index = match.group(1) if match else ""
            if raw_index.isdigit():
                result[int(raw_index)] = values
        return result

    @staticmethod
    def _metadata_path(root_dir: Path, package_path: str | None, fallback: Path) -> Path:
        if not package_path:
            return fallback
        cleaned = package_path.lstrip("/")
        if ".." in Path(cleaned).parts or "\\" in cleaned:
            return fallback
        return root_dir / cleaned

    @staticmethod
    def _missing_plate_error(root_dir: Path, source_package: Path) -> InvalidThreeMfError:
        metadata_dir = root_dir / "Metadata"
        model_files = sorted((root_dir / "3D").rglob("*.model")) if (root_dir / "3D").exists() else []
        preview_files = sorted(metadata_dir.glob("plate_*.png")) if metadata_dir.exists() else []
        gcode_files = sorted(metadata_dir.glob("plate_*.gcode")) if metadata_dir.exists() else []
        if model_files and preview_files and not gcode_files:
            return UnslicedThreeMfError(
                f"{source_package}\n这是未切片的 3MF 项目/模型包，包内没有 Metadata/plate_N.gcode。",
                suggestion="请先在 Bambu Studio 或 Orca Slicer 中完成切片，再导出包含 plate G-code 的 3MF。",
            )
        return InvalidThreeMfError(
            f"{source_package}\n未找到可打印 plate G-code。",
            suggestion="请确认导入的是已切片并包含 Metadata/plate_N.gcode 的 3MF。",
        )


class PackageReader:
    def __init__(self, guard: ArchiveGuard | None = None, metadata: MetadataReader | None = None) -> None:
        self.guard = guard or ArchiveGuard()
        self.metadata = metadata or MetadataReader()

    def inspect(self, source: Path, workspace_dir: Path | None = None) -> tuple[Plate, ...]:
        source = source.expanduser().resolve()
        if source.suffix.lower() != ".3mf":
            raise InvalidThreeMfError(f"不是 3MF 文件: {source}")
        if not source.exists():
            raise FileNotFoundError(source)
        workspace = workspace_dir or Path(tempfile.gettempdir()) / "change_plate_next"
        workspace.mkdir(parents=True, exist_ok=True)
        root_dir = Path(tempfile.mkdtemp(prefix=f"{source.stem}_", dir=workspace))
        self.guard.extract_to(source, root_dir)
        return self.metadata.read_plates(root_dir, source)
