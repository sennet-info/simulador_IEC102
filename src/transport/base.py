from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass(slots=True)
class TransportStatus:
    state: str
    detail: str = ""


class TransportCallback(Protocol):
    def __call__(self, event: str, payload: object) -> None: ...


class BaseTransport:
    def __init__(self, callback: TransportCallback) -> None:
        self.callback = callback

    def emit(self, event: str, payload: object) -> None:
        if self.callback:
            self.callback(event, payload)

    def start(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def stop(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def send(self, data: bytes) -> None:  # pragma: no cover - interface
        raise NotImplementedError
