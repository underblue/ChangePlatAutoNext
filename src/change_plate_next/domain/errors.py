"""Typed domain and application errors."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ErrorDetail:
    message: str
    suggestion: str = ""
    technical_detail: str = ""


class ChangePlateError(Exception):
    """Base class for user-actionable failures."""

    def __init__(self, message: str, *, suggestion: str = "", technical_detail: str = "") -> None:
        super().__init__(message)
        self.detail = ErrorDetail(message, suggestion, technical_detail)


class InvalidThreeMfError(ChangePlateError):
    """The package is not a supported Bambu sliced 3MF."""


class UnslicedThreeMfError(InvalidThreeMfError):
    """The package appears to be a project/model package without plate G-code."""


class MissingMetadataError(InvalidThreeMfError):
    """Required 3MF metadata is missing."""


class UnsafeArchiveError(InvalidThreeMfError):
    """The package failed archive safety checks."""


class ChannelMappingError(ChangePlateError):
    """Filament-to-AMS channel assignments are invalid."""


class ChannelConflictError(ChannelMappingError):
    """One actual channel contains incompatible filament signatures."""


class ChannelLimitExceededError(ChannelMappingError):
    """Auto assignment requires more actual channels than available."""


class GcodeTransformError(ChangePlateError):
    """A G-code transform could not be applied safely."""


class FinishMarkerMissingError(GcodeTransformError):
    """The configured safe G-code insertion marker could not be found."""


class ExportError(ChangePlateError):
    """Export failed after validation."""


class MetadataRewriteError(ExportError):
    """3MF metadata could not be rewritten consistently."""


class ConnectLaunchError(ChangePlateError):
    """Bambu Connect handoff failed."""
