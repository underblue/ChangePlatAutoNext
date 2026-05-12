"""Write merged Bambu 3MF packages."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import zipfile
from pathlib import Path

from change_plate_next.adapters.bambu_3mf.metadata_rewriter import MetadataRewriter
from change_plate_next.adapters.bambu_3mf.preview_composer import copy_or_compose_preview
from change_plate_next.adapters.gcode.pipeline import GcodePipeline
from change_plate_next.adapters.gcode.stages import GcodeContext
from change_plate_next.application.merge_planner import MergePlan
from change_plate_next.domain.models import ExportSummary


class PackageWriter:
    def __init__(self, pipeline: GcodePipeline | None = None, rewriter: MetadataRewriter | None = None) -> None:
        self.pipeline = pipeline or GcodePipeline()
        self.rewriter = rewriter or MetadataRewriter()

    def write(self, plan: MergePlan) -> ExportSummary:
        warnings: list[str] = list(plan.warnings)
        with tempfile.TemporaryDirectory(prefix="change_plate_next_export_") as tmp:
            staging_root = Path(tmp) / "staging"
            shutil.copytree(plan.base_plate.package_root, staging_root)
            target_index = plan.target_plate_index
            target_gcode = staging_root / "Metadata" / f"plate_{target_index}.gcode"
            target_preview = staging_root / "Metadata" / f"plate_{target_index}.png"
            target_small = staging_root / "Metadata" / f"plate_no_light_{target_index}.png"

            parts: list[str] = []
            plate_number = 0
            for item in plan.queue:
                for _ in range(max(0, int(item.copies))):
                    plate_number += 1
                    source = item.plate.assets.gcode.read_text(encoding="utf-8-sig")
                    result = self.pipeline.run(
                        source,
                        GcodeContext(channel_map=item.channel_map, plate_number=plate_number, recipe=plan.recipe),
                    )
                    warnings.extend(result.warnings)
                    parts.append(result.text if result.text.endswith("\n") else result.text + "\n")
            merged = "".join(parts)
            target_gcode.parent.mkdir(parents=True, exist_ok=True)
            target_gcode.write_text(merged, encoding="utf-8")
            self._write_md5(target_gcode, merged)
            warnings.extend(copy_or_compose_preview(list(plan.queue), target_preview, target_small))
            self._delete_other_plate_gcodes(staging_root / "Metadata", target_index)
            self.rewriter.rewrite(staging_root, plan)
            self._pack(staging_root, plan.output_path)
        return ExportSummary(plan.output_path, plan.target_plate_index, plan.total_printed_plates, tuple(warnings))

    @staticmethod
    def _write_md5(gcode_path: Path, text: str) -> None:
        digest = hashlib.md5(text.encode("utf-8")).hexdigest()
        gcode_path.with_suffix(gcode_path.suffix + ".md5").write_text(digest, encoding="utf-8")

    @staticmethod
    def _delete_other_plate_gcodes(metadata_dir: Path, target_index: int) -> None:
        for path in metadata_dir.glob("plate_*.gcode"):
            if path.name != f"plate_{target_index}.gcode":
                path.unlink(missing_ok=True)
                path.with_suffix(path.suffix + ".md5").unlink(missing_ok=True)

    @staticmethod
    def _pack(root_dir: Path, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in sorted(path for path in root_dir.rglob("*") if path.is_file()):
                archive.write(file_path, file_path.relative_to(root_dir).as_posix())
