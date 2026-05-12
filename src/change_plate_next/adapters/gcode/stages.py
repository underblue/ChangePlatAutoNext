"""G-code transform stages."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from change_plate_next.adapters.gcode.parser import ParsedKind, parse_line
from change_plate_next.domain.errors import FinishMarkerMissingError
from change_plate_next.domain.models import AmsChannel, LocalFilamentId, PlateChangeRecipe
from change_plate_next.domain.policies import GcodeSafetyPolicy, InsertionStrategy

M73_RE = re.compile(r"^(M73\s+P\d+\s+R)(\d+)(.*)$")


@dataclass(frozen=True, slots=True)
class GcodeContext:
    channel_map: dict[LocalFilamentId, AmsChannel] = field(default_factory=dict)
    plate_number: int = 1
    recipe: PlateChangeRecipe | None = None
    safety: GcodeSafetyPolicy = field(default_factory=GcodeSafetyPolicy)


@dataclass(frozen=True, slots=True)
class StageResult:
    text: str
    warnings: tuple[str, ...] = ()
    metrics: dict[str, int] = field(default_factory=dict)


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def ensure_trailing_newline(text: str) -> str:
    return text if text.endswith("\n") else text + "\n"


def normalize_optional_gcode(text: str) -> str:
    gcode = normalize_newlines(text).strip("\n")
    return ensure_trailing_newline(gcode) if gcode.strip() else ""


def build_change_gcode(recipe: PlateChangeRecipe) -> str:
    gcode = normalize_optional_gcode(recipe.change_gcode)
    if recipe.wait_hotbed_cool:
        gcode = f"M190 S{max(40, int(recipe.hotbed_temp))}\n" + gcode
    if recipe.wait_before_next_plate:
        wait_seconds = max(0, int(recipe.wait_seconds))
        if recipe.sound_tip_when_waiting and recipe.sound_tip_count > 0:
            tip_count = max(1, int(recipe.sound_tip_count))
            step_ms = int(wait_seconds / tip_count * 1000)
            sound = normalize_optional_gcode(recipe.sound_gcode)
            chunks: list[str] = []
            for _ in range(tip_count):
                chunks.append(sound)
                chunks.append(f"G4 P{step_ms}\n")
            gcode = ensure_trailing_newline(gcode) + "".join(chunks)
        else:
            gcode = ensure_trailing_newline(gcode) + f"G4 P{wait_seconds * 1000}\n"
    return ensure_trailing_newline(gcode)


def prepend_pre_plate_gcode(text: str, context: GcodeContext) -> StageResult:
    recipe = context.recipe
    if recipe is None:
        return StageResult(text)
    prefix = normalize_optional_gcode(recipe.pre_plate_gcode)
    if not prefix:
        return StageResult(text)
    return StageResult(prefix + normalize_newlines(text), metrics={"pre_plate_insertions": 1})


def append_post_plate_gcode(text: str, context: GcodeContext) -> StageResult:
    recipe = context.recipe
    if recipe is None:
        return StageResult(text)
    suffix = normalize_optional_gcode(recipe.post_plate_gcode)
    if not suffix:
        return StageResult(text)
    return StageResult(ensure_trailing_newline(normalize_newlines(text)) + suffix, metrics={"post_plate_insertions": 1})


def apply_start_position_patch(text: str, context: GcodeContext) -> StageResult:
    recipe = context.recipe
    if recipe is None or not recipe.apply_start_position_fix:
        return StageResult(text)
    lines = normalize_newlines(text).split("\n")
    replaced = 0
    for index, line in enumerate(lines):
        if line == recipe.start_position_line:
            lines[index] = recipe.start_position_replacement
            replaced += 1
    warnings = () if replaced else (f"未找到起始位置修正行: {recipe.start_position_line}",)
    return StageResult("\n".join(lines), warnings, {"start_position_replacements": replaced})


def _remap_tool_number(tool: int, context: GcodeContext) -> int:
    if tool in context.safety.reserved_tool_numbers:
        return tool
    local_id = LocalFilamentId(tool + 1)
    if local_id not in context.channel_map:
        return tool
    return max(0, int(context.channel_map[local_id]) - 1)


def remap_channels(text: str, context: GcodeContext) -> StageResult:
    if not context.channel_map:
        return StageResult(text)
    rewritten = 0
    output: list[str] = []
    for line in normalize_newlines(text).split("\n"):
        parsed = parse_line(line)
        if parsed.kind in {ParsedKind.AMS_SWITCH, ParsedKind.TOOL} and parsed.tool is not None:
            new_tool = _remap_tool_number(parsed.tool, context)
            if new_tool != parsed.tool:
                rewritten += 1
            output.append(f"{parsed.prefix}{new_tool}{parsed.suffix}")
        else:
            output.append(line)
    return StageResult("\n".join(output), metrics={"channel_rewrites": rewritten})


def encode_m73_plate_number(text: str, context: GcodeContext) -> StageResult:
    recipe = context.recipe
    if recipe is None or not recipe.encode_plate_number_in_m73:
        return StageResult(text)
    rewritten = 0
    output: list[str] = []
    for line in normalize_newlines(text).split("\n"):
        if line.startswith("M73"):
            match = M73_RE.match(line)
            if match:
                remaining = int(match.group(2)) + 6000 * context.plate_number
                line = f"{match.group(1)}{remaining}{match.group(3)}"
                rewritten += 1
        output.append(line)
    return StageResult("\n".join(output), metrics={"m73_rewrites": rewritten})


def insert_change_gcode(text: str, context: GcodeContext) -> StageResult:
    recipe = context.recipe
    if recipe is None:
        return StageResult(text)
    source = normalize_newlines(text)
    marker = recipe.plate_change_marker or context.safety.plate_change_marker
    if marker and marker in source:
        return StageResult(ensure_trailing_newline(source), metrics={"change_insertions": 0})

    change = build_change_gcode(recipe)
    strategy = recipe.insertion_strategy
    finish_marker = context.safety.finish_sound_marker
    warnings: list[str] = []

    if recipe.insert_after_finish_sound or strategy == InsertionStrategy.AFTER_FINISH_SOUND_BLOCK:
        return StageResult(ensure_trailing_newline(source) + change, metrics={"change_insertions": 1})

    last = source.rfind(finish_marker)
    previous = source.rfind(finish_marker, 0, last) if last != -1 else -1
    if previous != -1:
        suffix = "" if source.endswith("\n") else "\n"
        return StageResult(source[:previous] + change + source[previous:] + suffix, metrics={"change_insertions": 1})

    if strategy == InsertionStrategy.APPEND_WITH_WARNING:
        warnings.append("未找到完整结束音乐标记块，已按显式策略追加到文件末尾")
        return StageResult(ensure_trailing_newline(source) + change, tuple(warnings), {"change_insertions": 1})

    raise FinishMarkerMissingError(
        "未找到完整结束音乐标记块，已中止生成。",
        suggestion="检查源 G-code，或在专家模式中显式选择追加策略。",
    )
