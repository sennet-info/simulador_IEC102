from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class TimeRange:
    start: datetime | None = None
    end: datetime | None = None


@dataclass
class InformationObject:
    address: int
    data: bytes = field(default_factory=bytes)
    decoded: dict[str, Any] = field(default_factory=dict)


@dataclass
class Asdu:
    type_id: int
    vsq: int
    cause: int
    measurement_point: int
    record_address: int
    objects: list[InformationObject] = field(default_factory=list)
    raw: bytes = field(default_factory=bytes)
    shared_time: bytes | None = None

    @property
    def object_count(self) -> int:
        return self.vsq & 0x7F
