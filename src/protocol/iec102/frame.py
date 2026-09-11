from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FrameKind(str, Enum):
    FIXED = "fixed"
    VARIABLE = "variable"


@dataclass
class LinkFrame:
    kind: FrameKind
    control: int
    address: int
    payload: bytes = field(default_factory=bytes)
    raw: bytes = field(default_factory=bytes)
    checksum_ok: bool = True

    @property
    def is_request(self) -> bool:
        return bool(self.control & 0x40)

    @property
    def function_code(self) -> int:
        return self.control & 0x0F


def format_hex(data: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in data)
