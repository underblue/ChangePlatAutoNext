"""Rewrite Bambu 3MF metadata for a merged G-code export."""

from __future__ import annotations

import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

from change_plate_next.adapters.bambu_3mf.metadata_reader import metadata_value
from change_plate_next.adapters.bambu_3mf.safe_xml import SafeXmlStore
from change_plate_next.application.merge_planner import MergePlan
from change_plate_next.domain.channel_mapping import aggregate_filament_usage
from change_plate_next.domain.errors import MetadataRewriteError


class MetadataRewriter:
    def __init__(self, xml: SafeXmlStore | None = None) -> None:
        self.xml = xml or SafeXmlStore()

    def rewrite(self, staging_root: Path, plan: MergePlan) -> None:
        self._update_slice_info(staging_root, plan)
        self._update_model_settings(staging_root, plan.target_plate_index)
        self._update_rels(staging_root, plan.target_plate_index)
        self._update_filament_sequence(staging_root, plan)

    def _update_slice_info(self, staging_root: Path, plan: MergePlan) -> None:
        path = staging_root / "Metadata" / "slice_info.config"
        if not path.exists():
            raise MetadataRewriteError(f"缺少 slice_info.config: {path}")
        tree = self.xml.parse_file(path)
        root = tree.getroot()
        target = None
        for plate_node in list(root.findall("plate")):
            if metadata_value(plate_node, "index") == str(plan.target_plate_index):
                target = plate_node
            else:
                root.remove(plate_node)
        if target is None:
            raise MetadataRewriteError(f"slice_info.config 中未找到 plate {plan.target_plate_index}")

        total_prediction = sum(item.plate.prediction_seconds * max(0, int(item.copies)) for item in plan.queue)
        total_weight = sum(item.plate.weight_g * max(0, int(item.copies)) for item in plan.queue)
        for node in target.findall("metadata"):
            key = node.attrib.get("key")
            if key == "prediction":
                node.set("value", f"{total_prediction:.0f}")
            elif key == "weight":
                node.set("value", f"{total_weight:.2f}")
            elif key in {"filament_maps", "limit_filament_maps"}:
                channels = " ".join(str(int(filament.channel)) for filament in aggregate_filament_usage(list(plan.queue)))
                node.set("value", channels)

        for filament in list(target.findall("filament")):
            target.remove(filament)
        for aggregate in aggregate_filament_usage(list(plan.queue)):
            attrs = dict(aggregate.source.raw_attributes)
            attrs.update(
                {
                    "id": str(int(aggregate.channel)),
                    "tray_info_idx": aggregate.source.tray_info_idx,
                    "type": aggregate.source.signature.material,
                    "color": aggregate.source.signature.color,
                    "used_m": f"{aggregate.used_m:.2f}",
                    "used_g": f"{aggregate.used_g:.2f}",
                }
            )
            self._insert_filament_before_warning(target, ET.Element("filament", attrs))
        self.xml.write(tree, path)

    @staticmethod
    def _insert_filament_before_warning(plate_node: ET.Element, filament: ET.Element) -> None:
        children = list(plate_node)
        warning_index = next((index for index, child in enumerate(children) if child.tag == "warning"), None)
        if warning_index is None:
            plate_node.append(filament)
        else:
            plate_node.insert(warning_index, filament)

    def _update_model_settings(self, staging_root: Path, target_index: int) -> None:
        path = staging_root / "Metadata" / "model_settings.config"
        if not path.exists():
            return
        tree = self.xml.parse_file(path)
        root = tree.getroot()
        for plate_node in list(root.findall("plate")):
            values = {node.attrib.get("key", ""): node.attrib.get("value", "") for node in plate_node.findall("metadata")}
            raw_index = values.get("plater_id", "")
            if raw_index.isdigit() and int(raw_index) != target_index:
                root.remove(plate_node)
                continue
            for node in plate_node.findall("metadata"):
                key = node.attrib.get("key", "")
                value = node.attrib.get("value", "")
                replacements = {
                    "gcode_file": f"Metadata/plate_{target_index}.gcode",
                    "thumbnail_file": f"Metadata/plate_{target_index}.png",
                    "thumbnail_no_light_file": f"Metadata/plate_no_light_{target_index}.png",
                    "top_file": f"Metadata/top_{target_index}.png",
                    "pick_file": f"Metadata/pick_{target_index}.png",
                    "pattern_bbox_file": f"Metadata/plate_{target_index}.json",
                }
                if key in replacements and (not value or "Metadata/" in value):
                    node.set("value", replacements[key])
        self.xml.write(tree, path)

    def _update_rels(self, staging_root: Path, target_index: int) -> None:
        path = staging_root / "_rels" / ".rels"
        if not path.exists():
            return
        tree = self.xml.parse_file(path)
        for node in tree.getroot().iter():
            target = node.attrib.get("Target")
            if target and "/Metadata/plate_" in target:
                node.set("Target", re.sub(r"/Metadata/plate_\d+", f"/Metadata/plate_{target_index}", target))
        self.xml.write(tree, path)

    @staticmethod
    def _update_filament_sequence(staging_root: Path, plan: MergePlan) -> None:
        path = staging_root / "Metadata" / "filament_sequence.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        used_channels = sorted({int(channel) for item in plan.queue for channel in item.channel_map.values() if item.copies > 0})
        if not used_channels:
            return
        data[f"plate_{plan.target_plate_index}"] = {
            "nozzle_sequence": [channel - 1 for channel in used_channels],
            "optimal_assignment": [channel - 1 for channel in used_channels],
            "sequence": used_channels,
        }
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
