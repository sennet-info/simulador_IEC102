from __future__ import annotations

from src.meter.model import MeterModel


class MeterSimulator:
    def __init__(self, model: MeterModel) -> None:
        self.model = model

    def snapshot(self) -> dict[str, object]:
        return self.model.snapshot()
