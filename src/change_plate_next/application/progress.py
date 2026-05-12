"""Progress event objects emitted by long-running workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ProgressPhase = Literal["import", "plan", "transform", "metadata", "pack", "connect"]


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    phase: ProgressPhase
    current: int
    total: int
    message: str
