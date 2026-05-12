"""Compile validated merge plans before writing output files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from change_plate_next.domain.channel_mapping import ensure_default_channel_map, ensure_valid_channel_assignments
from change_plate_next.domain.errors import ChangePlateError
from change_plate_next.domain.models import Plate, PlateChangeRecipe, QueueEntry


@dataclass(frozen=True, slots=True)
class MergePlan:
    queue: tuple[QueueEntry, ...]
    recipe: PlateChangeRecipe
    output_path: Path
    target_plate_index: int
    base_plate: Plate
    total_printed_plates: int
    warnings: tuple[str, ...] = ()


class MergePlanner:
    def compile(self, queue: list[QueueEntry], recipe: PlateChangeRecipe, output_path: Path) -> MergePlan:
        if not queue:
            raise ChangePlateError("队列为空", suggestion="请先导入至少一个已切片 3MF plate。")
        for item in queue:
            ensure_default_channel_map(item)
        ensure_valid_channel_assignments(queue)
        total = sum(max(0, int(item.copies)) for item in queue)
        if total <= 0:
            raise ChangePlateError("总打印盘数为 0", suggestion="请至少将一个队列项 copies 设置为 1。")
        output = output_path.expanduser().resolve()
        if output.suffix.lower() != ".3mf":
            output = output.with_suffix(".3mf")
        base_plate = queue[0].plate
        return MergePlan(tuple(queue), recipe, output, base_plate.source_index, base_plate, total)
