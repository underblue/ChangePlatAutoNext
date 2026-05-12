"""Bundled default G-code snippets."""

from __future__ import annotations

from importlib import resources

RESOURCE_PACKAGE = "change_plate_next.resources"


def load_default_change_gcode() -> str:
    """Load the legacy default plate-change G-code bundled with the package."""
    return resources.files(RESOURCE_PACKAGE).joinpath("default_change_plate.gcode").read_text(encoding="utf-8-sig")


def load_default_sound_gcode() -> str:
    """Load the bundled default finish-sound G-code."""
    return resources.files(RESOURCE_PACKAGE).joinpath("default_finish_sound.gcode").read_text(encoding="utf-8-sig")
