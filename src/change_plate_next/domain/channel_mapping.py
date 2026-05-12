"""Filament-to-AMS channel mapping rules."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from change_plate_next.domain.errors import ChannelConflictError, ChannelLimitExceededError
from change_plate_next.domain.models import AmsChannel, FilamentUsage, LocalFilamentId, QueueEntry


@dataclass(frozen=True, slots=True)
class AggregatedFilament:
    channel: AmsChannel
    source: FilamentUsage
    used_m: float
    used_g: float
    copies: int

    @property
    def signature_key(self) -> tuple[str, str, str]:
        return self.source.signature.normalized()


def _channel_for(item: QueueEntry, local_id: LocalFilamentId) -> AmsChannel:
    return item.channel_map.get(local_id, AmsChannel(int(local_id)))


def ensure_default_channel_map(item: QueueEntry) -> None:
    for filament in item.plate.filaments:
        item.channel_map.setdefault(filament.local_id, AmsChannel(int(filament.local_id)))


def reset_to_local_channels(queue: list[QueueEntry]) -> None:
    for item in queue:
        item.channel_map = {
            filament.local_id: AmsChannel(int(filament.local_id)) for filament in item.plate.filaments
        }


def auto_assign_channels(queue: list[QueueEntry], max_channels: int = 16) -> None:
    signature_to_channel: dict[tuple[str, str, str], AmsChannel] = {}
    next_channel = 1
    for item in queue:
        item.channel_map.clear()
        for filament in item.plate.filaments:
            signature = filament.signature.normalized()
            if signature not in signature_to_channel:
                if next_channel > max_channels:
                    raise ChannelLimitExceededError(
                        f"耗材种类超过可用通道数量: {max_channels}",
                        suggestion="减少队列中的不同耗材，或提高最大通道数。",
                    )
                signature_to_channel[signature] = AmsChannel(next_channel)
                next_channel += 1
            item.channel_map[filament.local_id] = signature_to_channel[signature]


def validate_channel_assignments(queue: list[QueueEntry]) -> list[str]:
    by_channel: dict[int, set[tuple[str, str, str]]] = defaultdict(set)
    for item in queue:
        ensure_default_channel_map(item)
        if item.copies <= 0:
            continue
        for filament in item.plate.filaments:
            channel = int(_channel_for(item, filament.local_id))
            by_channel[channel].add(filament.signature.normalized())

    conflicts: list[str] = []
    for channel, signatures in sorted(by_channel.items()):
        if len(signatures) > 1:
            joined = ", ".join("/".join(part or "?" for part in signature) for signature in sorted(signatures))
            conflicts.append(f"实际通道 {channel} 同时映射了不同耗材: {joined}")
    return conflicts


def ensure_valid_channel_assignments(queue: list[QueueEntry]) -> None:
    conflicts = validate_channel_assignments(queue)
    if conflicts:
        raise ChannelConflictError("\n".join(conflicts), suggestion="请在装料通道页调整本地通道映射。")


def aggregate_filament_usage(queue: list[QueueEntry]) -> tuple[AggregatedFilament, ...]:
    ensure_valid_channel_assignments(queue)
    aggregates: dict[int, AggregatedFilament] = {}
    for item in queue:
        ensure_default_channel_map(item)
        copies = max(0, int(item.copies))
        if copies == 0:
            continue
        for filament in item.plate.filaments:
            channel = int(_channel_for(item, filament.local_id))
            current = aggregates.get(channel)
            used_m = filament.used_m * copies
            used_g = filament.used_g * copies
            if current is None:
                aggregates[channel] = AggregatedFilament(AmsChannel(channel), filament, used_m, used_g, copies)
            else:
                aggregates[channel] = AggregatedFilament(
                    AmsChannel(channel),
                    current.source,
                    current.used_m + used_m,
                    current.used_g + used_g,
                    current.copies + copies,
                )
    return tuple(aggregates[channel] for channel in sorted(aggregates))
