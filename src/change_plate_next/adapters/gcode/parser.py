"""Lightweight line parser for the small Bambu G-code subset we rewrite."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ParsedKind(str, Enum):
    BLANK = "blank"
    COMMENT = "comment"
    TOOL = "tool"
    AMS_SWITCH = "ams_switch"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ParsedLine:
    kind: ParsedKind
    original: str
    prefix: str = ""
    tool: int | None = None
    suffix: str = ""


M620_M621_RE = re.compile(r"^(?P<prefix>\s*M62[01]\s+S)(?P<tool>\d+)(?P<suffix>\s*A?.*)$")
TOOL_RE = re.compile(r"^(?P<prefix>\s*T)(?P<tool>\d+)(?P<suffix>\s*(?:;.*)?)$")


def parse_line(line: str) -> ParsedLine:
    stripped = line.lstrip()
    if not stripped:
        return ParsedLine(ParsedKind.BLANK, line)
    if stripped.startswith(";"):
        return ParsedLine(ParsedKind.COMMENT, line)

    match = M620_M621_RE.match(line)
    if match:
        return ParsedLine(
            ParsedKind.AMS_SWITCH,
            line,
            prefix=match.group("prefix"),
            tool=int(match.group("tool")),
            suffix=match.group("suffix"),
        )

    match = TOOL_RE.match(line)
    if match:
        return ParsedLine(
            ParsedKind.TOOL,
            line,
            prefix=match.group("prefix"),
            tool=int(match.group("tool")),
            suffix=match.group("suffix"),
        )

    return ParsedLine(ParsedKind.OTHER, line)
