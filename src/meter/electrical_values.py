from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class ElectricalValues:
    voltage_l1: float = 230.0
    voltage_l2: float = 230.0
    voltage_l3: float = 230.0
    current_l1: float = 10.0
    current_l2: float = 10.0
    current_l3: float = 10.0
    active_power_l1: float = 2.3
    active_power_l2: float = 2.3
    active_power_l3: float = 2.3
    active_power_total: float = 6.9
    reactive_power: float = 1.5
    apparent_power: float = 7.1
    power_factor: float = 0.97
    frequency: float = 50.0

    def to_dict(self) -> dict[str, float]:
        return asdict(self)
