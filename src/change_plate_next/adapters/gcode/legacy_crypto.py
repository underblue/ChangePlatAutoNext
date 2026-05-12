"""Compatibility for legacy XOR + Base64 G-code snippets."""

from __future__ import annotations

import base64
from pathlib import Path

DEFAULT_KEY = "MySecureKey123"
BOM = b"\xef\xbb\xbf"


def xor_bytes(data: bytes, key: bytes) -> bytes:
    if not key:
        raise ValueError("key must not be empty")
    return bytes(byte ^ key[index % len(key)] for index, byte in enumerate(data))


def encrypt_text(plain_text: str, key: str = DEFAULT_KEY) -> str:
    cipher = xor_bytes(plain_text.encode("utf-8"), key.encode("utf-8"))
    return base64.b64encode(cipher).decode("ascii")


def decrypt_text(encoded_text: str, key: str = DEFAULT_KEY) -> str:
    cipher = base64.b64decode(encoded_text)
    plain = xor_bytes(cipher, key.encode("utf-8"))
    return plain.decode("utf-8")


def read_legacy_gcode(path: Path, key: str = DEFAULT_KEY) -> str:
    data = path.read_bytes()
    if data.startswith(BOM):
        data = data[len(BOM) :]
    return decrypt_text(data.decode("utf-8"), key)


def write_legacy_gcode(path: Path, gcode: str, key: str = DEFAULT_KEY) -> None:
    path.write_bytes(BOM + encrypt_text(gcode, key).encode("ascii"))
