from __future__ import annotations

import json
import threading
import time
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from src.meter.electrical_values import ElectricalValues
from src.meter.energy import EnergyValues, TariffValues
from src.protocol.iec102.constants import (
    DEFAULT_BAUDRATE,
    DEFAULT_BYTESIZE,
    DEFAULT_PARITY,
    DEFAULT_SERIAL_TIMEOUT,
    DEFAULT_STOPBITS,
    DEFAULT_TCP_HOST,
    DEFAULT_TCP_PORT,
    DEFAULT_TIME_ACCELERATION,
)


@dataclass(slots=True)
class IECAddressing:
    link_address: int = 1
    measurement_point: int = 1
    record_address: int = 1
    common_address: int = 1
    use_system_time: bool = True
    custom_meter_time: str | None = None


@dataclass(slots=True)
class SerialSettings:
    port: str = "COM1"
    baudrate: int = DEFAULT_BAUDRATE
    bytesize: int = DEFAULT_BYTESIZE
    parity: str = DEFAULT_PARITY
    stopbits: int = DEFAULT_STOPBITS
    timeout: float = DEFAULT_SERIAL_TIMEOUT


@dataclass(slots=True)
class TcpSettings:
    host: str = DEFAULT_TCP_HOST
    port: int = DEFAULT_TCP_PORT


@dataclass(slots=True)
class CommunicationSettings:
    mode: str = "tcp"
    serial: SerialSettings = field(default_factory=SerialSettings)
    tcp: TcpSettings = field(default_factory=TcpSettings)


@dataclass(slots=True)
class MeterProfile:
    name: str = "Generic IEC 60870-5-102 Meter"
    manufacturer: str = "GEN"
    equipment_code: str = "IEC102SIM"
    supported_asdu_types: list[int] = field(default_factory=lambda: [71, 72, 8, 11, 163])
    supported_request_types: list[int] = field(default_factory=lambda: [100, 103, 122, 123, 162, 183, 187])


class MeterModel:
    def __init__(self, config_path: Path, profile_path: Path) -> None:
        self._lock = threading.RLock()
        self.config_path = config_path
        self.profile_path = profile_path
        self.electrical = ElectricalValues()
        self.energy = EnergyValues(
            active_import_tariffs=TariffValues(total=123456.789, t1=0.0, t2=0.0, t3=0.0, t4=0.0),
            reactive_import_tariffs=TariffValues(total=12345.678, t1=0.0, t2=0.0, t3=0.0, t4=0.0),
        )
        self.addressing = IECAddressing()
        self.communication = CommunicationSettings()
        self.profile = MeterProfile()
        self._last_simulation_tick = time.monotonic()
        self.load_profile()
        self.load_config()

    def load_profile(self) -> None:
        if not self.profile_path.exists():
            return
        data = json.loads(self.profile_path.read_text(encoding="utf-8"))
        self.profile = MeterProfile(
            name=data.get("name", self.profile.name),
            manufacturer=data.get("manufacturer", self.profile.manufacturer),
            equipment_code=data.get("equipment_code", self.profile.equipment_code),
            supported_asdu_types=data.get("supported_asdu_types", self.profile.supported_asdu_types),
            supported_request_types=data.get("supported_request_types", self.profile.supported_request_types),
        )
        self.addressing.link_address = data.get("link_address", self.addressing.link_address)
        self.addressing.measurement_point = data.get("measurement_point", self.addressing.measurement_point)
        self.addressing.record_address = data.get("record_address", self.addressing.record_address)

    def load_config(self) -> None:
        if not self.config_path.exists():
            return
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        with self._lock:
            self.communication = CommunicationSettings(
                mode=data.get("communication", {}).get("mode", self.communication.mode),
                serial=SerialSettings(**data.get("communication", {}).get("serial", {})),
                tcp=TcpSettings(**data.get("communication", {}).get("tcp", {})),
            )
            self.addressing = IECAddressing(**data.get("iec102", {}))
            self.electrical = ElectricalValues(**data.get("electrical", {}))
            energy_data = data.get("energy", {})
            self.energy = EnergyValues(
                active_import=energy_data.get("active_import", self.energy.active_import),
                active_export=energy_data.get("active_export", self.energy.active_export),
                reactive_import=energy_data.get("reactive_import", self.energy.reactive_import),
                reactive_export=energy_data.get("reactive_export", self.energy.reactive_export),
                active_import_tariffs=TariffValues(**energy_data.get("active_import_tariffs", {})),
                active_export_tariffs=TariffValues(**energy_data.get("active_export_tariffs", {})),
                reactive_import_tariffs=TariffValues(**energy_data.get("reactive_import_tariffs", {})),
                reactive_export_tariffs=TariffValues(**energy_data.get("reactive_export_tariffs", {})),
                mode=energy_data.get("mode", "manual"),
                time_acceleration=energy_data.get("time_acceleration", DEFAULT_TIME_ACCELERATION),
            )
            self._last_simulation_tick = time.monotonic()

    def save_config(self) -> None:
        with self._lock:
            payload = {
                "communication": {
                    "mode": self.communication.mode,
                    "serial": asdict(self.communication.serial),
                    "tcp": asdict(self.communication.tcp),
                },
                "iec102": asdict(self.addressing),
                "electrical": self.electrical.to_dict(),
                "energy": self.energy.to_dict(),
                "profile": asdict(self.profile),
            }
        self.config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            self._advance_energy_locked()
            return {
                "electrical": deepcopy(self.electrical.to_dict()),
                "energy": deepcopy(self.energy.to_dict()),
                "addressing": deepcopy(asdict(self.addressing)),
                "communication": {
                    "mode": self.communication.mode,
                    "serial": deepcopy(asdict(self.communication.serial)),
                    "tcp": deepcopy(asdict(self.communication.tcp)),
                },
                "profile": deepcopy(asdict(self.profile)),
                "meter_time": self.current_meter_time().isoformat(),
            }

    def current_meter_time(self) -> datetime:
        if self.addressing.use_system_time or not self.addressing.custom_meter_time:
            return datetime.now()
        return datetime.fromisoformat(self.addressing.custom_meter_time)

    def apply_updates(self, updates: dict[str, object]) -> None:
        with self._lock:
            electrical = updates.get("electrical", {})
            for key, value in electrical.items():
                setattr(self.electrical, key, float(value))
            energy = updates.get("energy", {})
            for key in ("active_import", "active_export", "reactive_import", "reactive_export"):
                if key in energy:
                    setattr(self.energy, key, float(energy[key]))
            if "mode" in energy:
                self.energy.mode = str(energy["mode"])
            if "time_acceleration" in energy:
                self.energy.time_acceleration = float(energy["time_acceleration"])
            for tariff_key in (
                "active_import_tariffs",
                "active_export_tariffs",
                "reactive_import_tariffs",
                "reactive_export_tariffs",
            ):
                if tariff_key in energy:
                    target = getattr(self.energy, tariff_key)
                    for key, value in energy[tariff_key].items():
                        setattr(target, key, float(value))
            communication = updates.get("communication", {})
            if "mode" in communication:
                self.communication.mode = str(communication["mode"])
            if "serial" in communication:
                for key, value in communication["serial"].items():
                    setattr(self.communication.serial, key, value)
            if "tcp" in communication:
                for key, value in communication["tcp"].items():
                    setattr(self.communication.tcp, key, value)
            if "iec102" in updates:
                for key, value in updates["iec102"].items():
                    setattr(self.addressing, key, value)
            self._last_simulation_tick = time.monotonic()
        self.save_config()

    def _advance_energy_locked(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_simulation_tick
        self._last_simulation_tick = now
        if elapsed <= 0 or self.energy.mode != "automatic":
            return
        hours = (elapsed * self.energy.time_acceleration) / 3600.0
        self.energy.active_import += self.electrical.active_power_total * hours
        self.energy.reactive_import += max(self.electrical.reactive_power, 0.0) * hours
        self.energy.active_import_tariffs.total = self.energy.active_import
        self.energy.reactive_import_tariffs.total = self.energy.reactive_import

