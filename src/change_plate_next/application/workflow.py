"""Application workflow facade used by CLI and GUI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from change_plate_next.adapters.bambu_3mf.package_reader import PackageReader
from change_plate_next.adapters.bambu_3mf.package_writer import PackageWriter
from change_plate_next.application.merge_planner import MergePlan, MergePlanner
from change_plate_next.domain.channel_mapping import auto_assign_channels
from change_plate_next.domain.models import ExportSummary, Plate, PlateChangeRecipe, QueueEntry


@dataclass(slots=True)
class ChangePlateWorkflow:
    package_reader: PackageReader
    package_writer: PackageWriter
    merge_planner: MergePlanner

    @classmethod
    def create_default(cls) -> "ChangePlateWorkflow":
        return cls(PackageReader(), PackageWriter(), MergePlanner())

    def inspect_package(self, path: Path) -> tuple[Plate, ...]:
        return self.package_reader.inspect(path)

    def build_queue_from_packages(self, paths: list[Path], copies: int = 1, auto_map: bool = True) -> list[QueueEntry]:
        queue: list[QueueEntry] = []
        for path in paths:
            for plate in self.inspect_package(path):
                queue.append(QueueEntry(plate=plate, copies=copies))
        if auto_map:
            auto_assign_channels(queue)
        return queue

    def compile_plan(self, queue: list[QueueEntry], recipe: PlateChangeRecipe, output_path: Path) -> MergePlan:
        return self.merge_planner.compile(queue, recipe, output_path)

    def export_queue(self, queue: list[QueueEntry], recipe: PlateChangeRecipe, output_path: Path) -> ExportSummary:
        plan = self.compile_plan(queue, recipe, output_path)
        return self.package_writer.write(plan)
