"""Composable G-code transform pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from change_plate_next.adapters.gcode.stages import (
    GcodeContext,
    StageResult,
    append_post_plate_gcode,
    apply_start_position_patch,
    encode_m73_plate_number,
    ensure_trailing_newline,
    normalize_newlines,
    insert_change_gcode,
    prepend_pre_plate_gcode,
    remap_channels,
)

Stage = Callable[[str, GcodeContext], StageResult]


@dataclass(frozen=True, slots=True)
class PipelineResult:
    text: str
    warnings: tuple[str, ...] = ()
    metrics: dict[str, int] = field(default_factory=dict)


class GcodePipeline:
    def __init__(self, stages: tuple[Stage, ...] | None = None) -> None:
        self.stages = stages or (
            _normalize_stage,
            prepend_pre_plate_gcode,
            apply_start_position_patch,
            remap_channels,
            encode_m73_plate_number,
            insert_change_gcode,
            append_post_plate_gcode,
            _trailing_newline_stage,
        )

    def run(self, text: str, context: GcodeContext) -> PipelineResult:
        warnings: list[str] = []
        metrics: dict[str, int] = {}
        current = text
        for stage in self.stages:
            result = stage(current, context)
            current = result.text
            warnings.extend(result.warnings)
            for key, value in result.metrics.items():
                metrics[key] = metrics.get(key, 0) + value
        return PipelineResult(current, tuple(warnings), metrics)


def _normalize_stage(text: str, context: GcodeContext) -> StageResult:
    return StageResult(normalize_newlines(text))


def _trailing_newline_stage(text: str, context: GcodeContext) -> StageResult:
    return StageResult(ensure_trailing_newline(text))
