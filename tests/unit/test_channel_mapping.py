from pathlib import Path

import pytest

from change_plate_next.domain.channel_mapping import auto_assign_channels, aggregate_filament_usage, validate_channel_assignments
from change_plate_next.domain.errors import ChannelConflictError
from change_plate_next.domain.models import AmsChannel, FilamentSignature, FilamentUsage, LocalFilamentId, Plate, PlateAssetRefs, PlateId, QueueEntry


def plate(color: str) -> Plate:
    filament = FilamentUsage(LocalFilamentId(1), "tray", FilamentSignature(color, "PLA", "0.40"), used_m=1, used_g=2)
    return Plate(PlateId(color), Path("source.3mf"), Path("root"), 1, color, PlateAssetRefs(Path("plate.gcode")), 1, 2, (filament,))


def test_auto_assign_channels_splits_different_colors() -> None:
    queue = [QueueEntry(plate("#00FF00")), QueueEntry(plate("#FF0000"))]
    auto_assign_channels(queue)
    assert queue[0].channel_map[LocalFilamentId(1)] == AmsChannel(1)
    assert queue[1].channel_map[LocalFilamentId(1)] == AmsChannel(2)


def test_conflict_detection() -> None:
    queue = [QueueEntry(plate("#00FF00")), QueueEntry(plate("#FF0000"))]
    for item in queue:
        item.channel_map[LocalFilamentId(1)] = AmsChannel(1)
    conflicts = validate_channel_assignments(queue)
    assert conflicts
    with pytest.raises(ChannelConflictError):
        aggregate_filament_usage(queue)


def test_aggregate_multiplies_copies() -> None:
    queue = [QueueEntry(plate("#00FF00"), copies=3)]
    auto_assign_channels(queue)
    aggregate = aggregate_filament_usage(queue)[0]
    assert aggregate.used_g == 6
