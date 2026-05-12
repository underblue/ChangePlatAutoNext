"""Safety and behavior policies used by the application layer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class InsertionStrategy(str, Enum):
    BEFORE_FINISH_SOUND_BLOCK = "before_finish_sound_block"
    AFTER_FINISH_SOUND_BLOCK = "after_finish_sound_block"
    APPEND_WITH_WARNING = "append_with_warning"
    FAIL_FAST = "fail_fast"


@dataclass(frozen=True, slots=True)
class ArchiveSafetyPolicy:
    max_files: int = 5000
    max_uncompressed_bytes: int = 1024 * 1024 * 1024
    max_single_file_bytes: int = 512 * 1024 * 1024
    max_xml_bytes: int = 64 * 1024 * 1024
    max_compression_ratio: int = 200
    reject_backslash_paths: bool = True
    reject_symlinks: bool = True


@dataclass(frozen=True, slots=True)
class GcodeSafetyPolicy:
    finish_sound_marker: str = ";=====printer finish  sound========="
    plate_change_marker: str = ";start change plate"
    insertion_strategy: InsertionStrategy = InsertionStrategy.BEFORE_FINISH_SOUND_BLOCK
    reserved_tool_numbers: tuple[int, ...] = (255, 1000)
