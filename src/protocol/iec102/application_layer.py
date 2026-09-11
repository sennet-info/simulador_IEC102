from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.meter.model import MeterModel

from .asdu import Asdu, InformationObject
from .constants import (
    CAUSE_ADDRESS_UNKNOWN,
    CAUSE_ASDU_NOT_AVAILABLE,
    CAUSE_REQUEST,
    MASTER_REQUEST_CLASS_2_DATA,
    MASTER_REQUEST_LINK_STATUS,
    MASTER_RESET_REMOTE_LINK,
    MASTER_SEND_USER_DATA,
    OBJECT_ACTIVE_EXPORT,
    OBJECT_ACTIVE_IMPORT,
    OBJECT_INSTANT_ENERGY_BLOCK,
    OBJECT_INSTANT_POWER_BLOCK,
    OBJECT_INSTANT_VOLTAGE_CURRENT_BLOCK,
    OBJECT_REACTIVE_EXPORT_Q4,
    OBJECT_REACTIVE_IMPORT_Q1,
    TYPE_CURRENT_TIME,
    TYPE_INCREMENTAL_TOTALS,
    TYPE_INSTANT_VALUES,
    TYPE_INTEGRATED_TOTALS,
    TYPE_LOGIN,
    TYPE_LOGOUT,
    TYPE_MANUFACTURER_IDENTIFICATION,
    TYPE_READ_CURRENT_TIME,
    TYPE_READ_INCREMENTAL_TOTALS,
    TYPE_READ_INSTANT_VALUES,
    TYPE_READ_INTEGRATED_TOTALS,
    TYPE_READ_MANUFACTURER_IDENTIFICATION,
)
from .link_layer import LinkLayer, LinkResponse
from .parser import ParsedFrame


@dataclass(slots=True)
class ApplicationResult:
    response: LinkResponse
    decoded: str


class ApplicationLayer:
    def __init__(self, meter_model: MeterModel) -> None:
        self.meter_model = meter_model
        self.link_layer = LinkLayer()
        self._pending_class2: LinkResponse | None = None

    def handle(self, parsed: ParsedFrame) -> ApplicationResult:
        frame = parsed.frame
        if frame.function_code == MASTER_RESET_REMOTE_LINK:
            self._pending_class2 = None
            response = self.link_layer.ack(frame.address, "Link reset acknowledged")
            return ApplicationResult(response, response.description)
        if frame.function_code == MASTER_REQUEST_LINK_STATUS:
            response = self.link_layer.status(frame.address, "Link status")
            return ApplicationResult(response, response.description)
        if frame.function_code == MASTER_REQUEST_CLASS_2_DATA:
            if self._pending_class2 is not None:
                response = self._pending_class2
                self._pending_class2 = None
                return ApplicationResult(response, response.description)
            response = self.link_layer.no_data(frame.address, "No class 2 data queued")
            return ApplicationResult(response, response.description)
        if frame.function_code != MASTER_SEND_USER_DATA or parsed.asdu is None:
            response = self.link_layer.nack(frame.address, "Unsupported link-layer request")
            return ApplicationResult(response, response.description)

        snapshot = self.meter_model.snapshot()
        addressing = snapshot["iec102"]
        if frame.address != int(addressing["link_address"]):
            response = self.link_layer.nack(frame.address, "Link address mismatch")
            return ApplicationResult(response, response.description)
        if parsed.asdu.measurement_point != int(addressing["measurement_point"]):
            payload = self._encode_error_asdu(parsed.asdu, CAUSE_ADDRESS_UNKNOWN)
            self._pending_class2 = self.link_layer.user_data(frame.address, payload, "Measurement point mismatch")
            ack = self.link_layer.ack(frame.address, "Request accepted, error queued")
            return ApplicationResult(ack, ack.description)

        if parsed.asdu.type_id == TYPE_LOGIN:
            self._pending_class2 = None
            ack = self.link_layer.ack(frame.address, "Session/login request acknowledged")
            return ApplicationResult(ack, ack.description)
        if parsed.asdu.type_id == TYPE_LOGOUT:
            self._pending_class2 = None
            ack = self.link_layer.ack(frame.address, "Session close request acknowledged")
            return ApplicationResult(ack, ack.description)

        payload, decoded = self._build_asdu_response(parsed.asdu, snapshot)
        self._pending_class2 = self.link_layer.user_data(frame.address, payload, decoded)
        ack = self.link_layer.ack(frame.address, f"Request accepted, queued {parsed.asdu.type_id}")
        return ApplicationResult(ack, ack.description)

    def _build_asdu_response(self, request: Asdu, snapshot: dict[str, object]) -> tuple[bytes, str]:
        if request.type_id == TYPE_READ_MANUFACTURER_IDENTIFICATION:
            return self._encode_manufacturer(snapshot)
        if request.type_id == TYPE_READ_CURRENT_TIME:
            return self._encode_current_time(snapshot)
        if request.type_id == TYPE_READ_INTEGRATED_TOTALS:
            return self._encode_integrated_totals(request, snapshot, TYPE_INTEGRATED_TOTALS)
        if request.type_id == TYPE_READ_INCREMENTAL_TOTALS:
            return self._encode_integrated_totals(request, snapshot, TYPE_INCREMENTAL_TOTALS)
        if request.type_id == TYPE_READ_INSTANT_VALUES:
            return self._encode_instant_values(snapshot)
        return self._encode_error_asdu(request, CAUSE_ASDU_NOT_AVAILABLE), f"ASDU {request.type_id} not supported"

    def _encode_error_asdu(self, request: Asdu, cause: int) -> bytes:
        return self._encode_asdu(
            type_id=request.type_id,
            cause=cause,
            measurement_point=request.measurement_point,
            record_address=request.record_address,
            objects=b"",
            object_count=0,
        )

    def _encode_manufacturer(self, snapshot: dict[str, object]) -> tuple[bytes, str]:
        profile = snapshot["profile"]
        manufacturer = str(profile["manufacturer"])[:3].encode("ascii", errors="ignore").ljust(3, b" ")
        equipment = str(profile["equipment_code"])[:8].encode("ascii", errors="ignore").ljust(8, b" ")
        objects = bytes([1]) + manufacturer + equipment
        payload = self._encode_asdu(
            type_id=TYPE_MANUFACTURER_IDENTIFICATION,
            cause=CAUSE_REQUEST,
            measurement_point=int(snapshot["iec102"]["measurement_point"]),
            record_address=int(snapshot["iec102"]["record_address"]),
            objects=objects,
            object_count=1,
        )
        return payload, f"ASDU 71 manufacturer={manufacturer.decode().strip()} equipment={equipment.decode().strip()}"

    def _encode_current_time(self, snapshot: dict[str, object]) -> tuple[bytes, str]:
        meter_time = datetime.fromisoformat(str(snapshot["meter_time"]))
        objects = bytes([1]) + encode_time_tag_b(meter_time)
        payload = self._encode_asdu(
            type_id=TYPE_CURRENT_TIME,
            cause=CAUSE_REQUEST,
            measurement_point=int(snapshot["iec102"]["measurement_point"]),
            record_address=int(snapshot["iec102"]["record_address"]),
            objects=objects,
            object_count=1,
        )
        return payload, f"ASDU 72 meter_time={meter_time.isoformat(sep=' ', timespec='seconds')}"

    def _encode_integrated_totals(self, request: Asdu, snapshot: dict[str, object], response_type: int) -> tuple[bytes, str]:
        energy = snapshot["energy"]
        requested_objects = self._requested_total_objects(request)
        entries: list[bytes] = []
        parts: list[str] = []
        for item in requested_objects:
            value = self._energy_for_object(item.address, energy)
            entries.append(bytes([item.address]) + encode_integrated_total(float(value)))
            parts.append(f"obj={item.address}:{float(value):.3f}")
        payload = self._encode_asdu(
            type_id=response_type,
            cause=CAUSE_REQUEST,
            measurement_point=request.measurement_point,
            record_address=request.record_address,
            objects=b"".join(entries) + encode_time_tag_a(datetime.fromisoformat(str(snapshot["meter_time"]))),
            object_count=len(entries),
        )
        return payload, f"ASDU {response_type} " + ", ".join(parts)


    def _requested_total_objects(self, request: Asdu) -> list[InformationObject]:
        if request.objects:
            first = request.objects[0]
            if first.data:
                end = first.data[0]
                start = first.address
                if start <= end:
                    return [InformationObject(address=value) for value in range(start, end + 1)]
            return [InformationObject(address=item.address) for item in request.objects]
        return [InformationObject(address=OBJECT_ACTIVE_IMPORT), InformationObject(address=OBJECT_ACTIVE_EXPORT), InformationObject(address=OBJECT_REACTIVE_IMPORT_Q1), InformationObject(address=OBJECT_REACTIVE_EXPORT_Q4)]

    def _energy_for_object(self, address: int, energy: dict[str, object]) -> float:
        if address == OBJECT_ACTIVE_IMPORT:
            return float(energy["active_import"])
        if address == OBJECT_ACTIVE_EXPORT:
            return float(energy["active_export"])
        if address == OBJECT_REACTIVE_IMPORT_Q1:
            return float(energy["reactive_import"])
        if address == OBJECT_REACTIVE_EXPORT_Q4:
            return float(energy["reactive_export"])
        return 0.0

    def _encode_instant_values(self, snapshot: dict[str, object]) -> tuple[bytes, str]:
        electrical = snapshot["electrical"]
        energy = snapshot["energy"]
        meter_time = datetime.fromisoformat(str(snapshot["meter_time"]))
        objects = b"".join(
            [
                bytes([OBJECT_INSTANT_ENERGY_BLOCK]) + self._encode_energy_block(energy, meter_time),
                bytes([OBJECT_INSTANT_POWER_BLOCK]) + self._encode_power_block(electrical, meter_time),
                bytes([OBJECT_INSTANT_VOLTAGE_CURRENT_BLOCK]) + self._encode_voltage_current_block(electrical, meter_time),
            ]
        )
        payload = self._encode_asdu(
            type_id=TYPE_INSTANT_VALUES,
            cause=CAUSE_REQUEST,
            measurement_point=int(snapshot["iec102"]["measurement_point"]),
            record_address=int(snapshot["iec102"]["record_address"]),
            objects=objects,
            object_count=3,
        )
        return payload, "ASDU 163 instant values"

    def _encode_energy_block(self, energy: dict[str, object], meter_time: datetime) -> bytes:
        return b"".join(
            [
                encode_24_2(float(energy["active_import"])),
                encode_24_2(float(energy["active_export"])),
                encode_24_2(float(energy["reactive_import"])),
                encode_24_2(0.0),
                encode_24_2(0.0),
                encode_24_2(float(energy["reactive_export"])),
            ]
        ) + encode_time_tag_a(meter_time)

    def _encode_power_block(self, electrical: dict[str, object], meter_time: datetime) -> bytes:
        return b"".join(
            [
                encode_24(float(electrical["active_power_total"])),
                encode_24(float(electrical["reactive_power"])),
                encode_pf(float(electrical["power_factor"])),
                encode_24(float(electrical["active_power_l1"])),
                encode_24(float(electrical["reactive_power"]) / 3.0),
                encode_pf(float(electrical["power_factor"])),
                encode_24(float(electrical["active_power_l2"])),
                encode_24(float(electrical["reactive_power"]) / 3.0),
                encode_pf(float(electrical["power_factor"])),
                encode_24(float(electrical["active_power_l3"])),
                encode_24(float(electrical["reactive_power"]) / 3.0),
                encode_pf(float(electrical["power_factor"])),
            ]
        ) + encode_time_tag_a(meter_time)

    def _encode_voltage_current_block(self, electrical: dict[str, object], meter_time: datetime) -> bytes:
        return b"".join(
            [
                encode_24(float(electrical["current_l1"]), scale=10),
                encode_24_2(float(electrical["voltage_l1"]), scale=10),
                encode_24(float(electrical["current_l2"]), scale=10),
                encode_24_2(float(electrical["voltage_l2"]), scale=10),
                encode_24(float(electrical["current_l3"]), scale=10),
                encode_24_2(float(electrical["voltage_l3"]), scale=10),
            ]
        ) + encode_time_tag_a(meter_time)

    def _encode_asdu(self, type_id: int, cause: int, measurement_point: int, record_address: int, objects: bytes, object_count: int) -> bytes:
        vsq = object_count & 0x7F
        return bytes(
            [
                type_id,
                vsq,
                cause,
                measurement_point & 0xFF,
                (measurement_point >> 8) & 0xFF,
                record_address & 0xFF,
            ]
        ) + objects


def encode_integrated_total(value: float, qualifier: int = 0x40) -> bytes:
    scaled = max(0, min(int(round(value * 1000)), 0xFFFFFFFF))
    return scaled.to_bytes(4, "little") + bytes([qualifier])


def encode_24(value: float, scale: int = 1000) -> bytes:
    scaled = int(round(value * scale))
    scaled = max(-(1 << 23), min(scaled, (1 << 23) - 1))
    if scaled < 0:
        scaled = (1 << 24) + scaled
    return scaled.to_bytes(3, "little")


def encode_24_2(value: float, scale: int = 1000) -> bytes:
    scaled = max(0, min(int(round(value * scale)), 0x3FFFFFFF))
    low = scaled & 0xFFFFFF
    high = (scaled >> 24) & 0x3F
    return low.to_bytes(3, "little") + bytes([high << 2])


def encode_pf(value: float) -> bytes:
    scaled = max(0, min(int(round(value * 1000)), 0x3FF))
    return bytes([scaled & 0xFF, (scaled >> 8) << 6])


def encode_time_tag_a(value: datetime) -> bytes:
    minute = value.minute & 0x3F
    hour = value.hour & 0x1F
    day = value.day & 0x1F
    weekday = ((value.isoweekday() % 7) + 1) & 0x07
    month = value.month & 0x0F
    year = (value.year - 2000) & 0x7F
    return bytes([
        minute,
        hour | (0x80 if value.dst() else 0),
        day | (weekday << 5),
        month,
        year,
    ])


def encode_time_tag_b(value: datetime) -> bytes:
    millisecond = int(value.microsecond / 1000)
    second = value.second
    minute = value.minute & 0x3F
    hour = value.hour & 0x1F
    day = value.day & 0x1F
    weekday = ((value.isoweekday() % 7) + 1) & 0x07
    month = value.month & 0x0F
    year = (value.year - 2000) & 0x7F
    return bytes([
        millisecond & 0xFF,
        ((second & 0x3F) << 2) | ((millisecond >> 8) & 0x03),
        minute,
        hour,
        day | (weekday << 5),
        month,
        year,
    ])
