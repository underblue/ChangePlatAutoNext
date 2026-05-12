"""Persistent desktop settings for the PyQt interface."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from change_plate_next.resources.defaults import load_default_change_gcode, load_default_sound_gcode


@dataclass(slots=True)
class DesktopSettings:
    language: str = "en"
    output_directory: str = ""
    change_gcode: str = ""
    sound_gcode: str = ""
    pre_plate_gcode: str = ""
    post_plate_gcode: str = ""
    apply_start_position_fix: bool = True
    encode_plate_number_in_m73: bool = False
    append_if_marker_missing: bool = False
    wait_hotbed_cool: bool = False
    hotbed_temp: int = 40
    wait_before_next_plate: bool = False
    wait_seconds: int = 120
    sound_tip_when_waiting: bool = False
    sound_tip_count: int = 10


def settings_dir() -> Path:
    home = Path.home()
    if sys_platform() == "darwin":
        return home / "Library" / "Application Support" / "ChangePlatAutoNext"
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "ChangePlatAutoNext"
        return home / "AppData" / "Roaming" / "ChangePlatAutoNext"
    return home / ".config" / "change-plate-next"


def settings_path() -> Path:
    return settings_dir() / "settings.json"


def sys_platform() -> str:
    return os.sys.platform


def default_settings() -> DesktopSettings:
    return DesktopSettings(
        change_gcode=load_default_change_gcode(),
        sound_gcode=load_default_sound_gcode(),
    )


def load_settings() -> DesktopSettings:
    defaults = default_settings()
    path = settings_path()
    if not path.exists():
        return defaults
    data = json.loads(path.read_text(encoding="utf-8"))
    merged = asdict(defaults)
    merged.update({key: value for key, value in data.items() if key in merged})
    return DesktopSettings(**merged)


def save_settings(settings: DesktopSettings) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
