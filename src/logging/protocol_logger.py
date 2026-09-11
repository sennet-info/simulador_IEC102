from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.protocol.iec102.frame import format_hex


@dataclass
class ProtocolEvent:
    timestamp: datetime
    direction: str
    transport: str
    raw: bytes
    decoded: str

    @property
    def byte_count(self) -> int:
        return len(self.raw)

    def to_monitor_line(self) -> str:
        return f"{self.timestamp.strftime('%H:%M:%S.%f')[:-3]} {self.direction:<2} [{self.byte_count:>3}] {format_hex(self.raw)}\n{self.decoded}"

    def to_log_line(self) -> str:
        return (
            f"{self.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} | {self.direction} | {self.transport} | "
            f"{format_hex(self.raw)} | {self.decoded}"
        )


class ProtocolLogger:
    def __init__(self, log_directory: Path) -> None:
        self.log_directory = log_directory
        self.log_directory.mkdir(parents=True, exist_ok=True)
        self.events: list[ProtocolEvent] = []

    def record(self, event: ProtocolEvent) -> None:
        self.events.append(event)

    def clear(self) -> None:
        self.events.clear()

    def save(self) -> Path:
        target = self.log_directory / f"iec102_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]}.log"
        target.write_text("\n".join(event.to_log_line() for event in self.events), encoding="utf-8")
        return target
