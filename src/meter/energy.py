from __future__ import annotations

from dataclasses import asdict, dataclass, field

from src.protocol.iec102.constants import DEFAULT_TIME_ACCELERATION


@dataclass(slots=True)
class TariffValues:
    total: float = 0.0
    t1: float = 0.0
    t2: float = 0.0
    t3: float = 0.0
    t4: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(slots=True)
class EnergyValues:
    active_import: float = 123456.789
    active_export: float = 0.0
    reactive_import: float = 12345.678
    reactive_export: float = 0.0
    active_import_tariffs: TariffValues = field(default_factory=TariffValues)
    active_export_tariffs: TariffValues = field(default_factory=TariffValues)
    reactive_import_tariffs: TariffValues = field(default_factory=TariffValues)
    reactive_export_tariffs: TariffValues = field(default_factory=TariffValues)
    mode: str = "manual"
    time_acceleration: float = DEFAULT_TIME_ACCELERATION

    def to_dict(self) -> dict[str, object]:
        return {
            "active_import": self.active_import,
            "active_export": self.active_export,
            "reactive_import": self.reactive_import,
            "reactive_export": self.reactive_export,
            "active_import_tariffs": self.active_import_tariffs.to_dict(),
            "active_export_tariffs": self.active_export_tariffs.to_dict(),
            "reactive_import_tariffs": self.reactive_import_tariffs.to_dict(),
            "reactive_export_tariffs": self.reactive_export_tariffs.to_dict(),
            "mode": self.mode,
            "time_acceleration": self.time_acceleration,
        }
