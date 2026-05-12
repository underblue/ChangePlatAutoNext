"""Domain models for the redesigned plate-change pipeline.

These classes intentionally avoid Qt, ZIP, XML, and file-system behavior. They describe the
business objects that every interface works with.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import NewType

from change_plate_next.domain.policies import InsertionStrategy

PlateId = NewType("PlateId", str)
LocalFilamentId = NewType("LocalFilamentId", int)
AmsChannel = NewType("AmsChannel", int)


@dataclass(frozen=True, slots=True)
class FilamentSignature:
    color: str
    material: str
    nozzle_diameter: str = ""

    def normalized(self) -> tuple[str, str, str]:
        return (self.color.upper(), self.material.upper(), self.nozzle_diameter)


@dataclass(frozen=True, slots=True)
class FilamentUsage:
    local_id: LocalFilamentId
    tray_info_idx: str
    signature: FilamentSignature
    used_m: float = 0.0
    used_g: float = 0.0
    raw_attributes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PlateAssetRefs:
    gcode: Path
    preview: Path | None = None
    small_preview: Path | None = None
    top_preview: Path | None = None
    pick_preview: Path | None = None
    bbox_json: Path | None = None


@dataclass(frozen=True, slots=True)
class Plate:
    id: PlateId
    source_package: Path
    package_root: Path
    source_index: int
    display_name: str
    assets: PlateAssetRefs
    prediction_seconds: float
    weight_g: float
    filaments: tuple[FilamentUsage, ...]


@dataclass(slots=True)
class QueueEntry:
    plate: Plate
    copies: int = 1
    channel_map: dict[LocalFilamentId, AmsChannel] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PlateChangeRecipe:
    change_gcode: str
    sound_gcode: str = ""
    pre_plate_gcode: str = ""
    post_plate_gcode: str = ""
    plate_change_marker: str = ";start change plate"
    insert_after_finish_sound: bool = False
    insertion_strategy: InsertionStrategy = InsertionStrategy.BEFORE_FINISH_SOUND_BLOCK
    wait_hotbed_cool: bool = False
    hotbed_temp: int = 40
    wait_before_next_plate: bool = False
    wait_seconds: int = 120
    sound_tip_when_waiting: bool = False
    sound_tip_count: int = 10
    encode_plate_number_in_m73: bool = False
    apply_start_position_fix: bool = True
    start_position_line: str = "G0 Y254 F3000"
    start_position_replacement: str = "G0 Y250 F3000 ;XKY ADD"


@dataclass(frozen=True, slots=True)
class ExportSummary:
    output_path: Path
    target_plate_index: int
    total_printed_plates: int
    warnings: tuple[str, ...] = ()
