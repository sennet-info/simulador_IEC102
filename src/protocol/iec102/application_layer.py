from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.meter.model import MeterModel

from .asdu import Asdu, InformationObject
from .constants import (
    CAUSE_ACTIVATION_CONFIRM,
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
    OBJECT_TRANSFORMER_RATIOS,
    OBJECT_REACTIVE_EXPORT_Q4,
    OBJECT_REACTIVE_IMPORT_Q1,
    TYPE_CURRENT_TIME,
    TYPE_INCREMENTAL_TOTALS,
    TYPE_GENERAL_VALUES,
    TYPE_INSTANT_VALUES,
    TYPE_INTEGRATED_TOTALS,
    TYPE_LOGIN,
    TYPE_LOGOUT,
    TYPE_MANUFACTURER_IDENTIFICATION,
    TYPE_READ_CURRENT_TIME,
    TYPE_READ_INCREMENTAL_TOTALS,
    TYPE_READ_GENERAL_VALUES,
    TYPE_READ_INSTANT_VALUES,
    TYPE_READ_INTEGRATED_TOTALS,
    TYPE_READ_MANUFACTURER_IDENTIFICATION,
)
from .link_layer import LinkLayer, LinkResponse
from .parser import ParsedFrame


FCB_BIT = 0x20
FCV_BIT = 0x10


@dataclass
class ApplicationResult:
    response: LinkResponse
    decoded: str


class ApplicationLayer:
    def __init__(self, meter_model: MeterModel) -> None:
        self.meter_model = meter_model
        self.link_layer = LinkLayer()
        self._pending_class2: LinkResponse | None = None
        self._last_fcb: int | None = None
        self._last_response: LinkResponse | None = None

    def handle(self, parsed: ParsedFrame) -> ApplicationResult:
        frame = parsed.frame
        fcv = bool(frame.control & FCV_BIT)
        if fcv:
            fcb = 1 if frame.control & FCB_BIT else 0
            if self._last_response is not None and fcb == self._last_fcb:
                # Same FCB as the previous request: the master did not get our
                # answer and is retransmitting, so the last response must be repeated.
                repeated = self._last_response
                return ApplicationResult(repeated, f"Retransmission (FCB={fcb} unchanged), repeating: {repeated.description}")
            result = self._handle(parsed)
            self._last_fcb = fcb
            self._last_response = result.response
            return result
        return self._handle(parsed)

    def _handle(self, parsed: ParsedFrame) -> ApplicationResult:
        frame = parsed.frame
        if frame.function_code == MASTER_RESET_REMOTE_LINK:
            self._pending_class2 = None
            self._last_fcb = None
            self._last_response = None
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

        if parsed.asdu.type_id in {TYPE_LOGIN, TYPE_LOGOUT}:
            # The master ACKs at link level and then polls class 2 expecting the
            # same ASDU echoed back with cause 7 (activation confirmation).
            label = "login" if parsed.asdu.type_id == TYPE_LOGIN else "logout"
            payload = self._encode_activation_confirm(parsed.asdu)
            self._pending_class2 = self.link_layer.user_data(
                frame.address, payload, f"ASDU {parsed.asdu.type_id} {label} confirmed (cause 7)"
            )
            ack = self.link_layer.ack(frame.address, f"Session {label} request accepted, confirmation queued")
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
        if request.type_id == TYPE_READ_GENERAL_VALUES:
            return self._encode_general_values(snapshot)
        return self._encode_error_asdu(request, CAUSE_ASDU_NOT_AVAILABLE), f"ASDU {request.type_id} not supported"

    def _encode_activation_confirm(self, request: Asdu) -> bytes:
        return self._encode_asdu(
            type_id=request.type_id,
            cause=CAUSE_ACTIVATION_CONFIRM,
            measurement_point=request.measurement_point,
            record_address=request.record_address,
            objects=request.raw[6:],
            object_count=request.object_count,
        )

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
        objects = b"".join(entries)
        if response_type in {TYPE_INTEGRATED_TOTALS, TYPE_INCREMENTAL_TOTALS}:
            objects += encode_time_tag_a(datetime.fromisoformat(str(snapshot["meter_time"])))
        payload = self._encode_asdu(
            type_id=response_type,
            cause=CAUSE_REQUEST,
            measurement_point=request.measurement_point,
            record_address=request.record_address,
            objects=objects,
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
        if address in {OBJECT_REACTIVE_IMPORT_Q1, 4}:
            return float(energy["reactive_import"])
        if address in {5, OBJECT_REACTIVE_EXPORT_Q4}:
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

    # Instant-value blocks (ASDU 163). Layout and units match what the SenNet/OWA
    # mt_meter master reads at fixed frame offsets (mt_meter.c, Analyse_Rec):
    #   192 energies: 6 x uint32 LE kWh (EAI, EAE, Q1, Q2, Q3, Q4) + time tag
    #   193 powers:   [total, L1, L2, L3] x (P kW u24, Q kvar u24, PF u16) + time tag
    #                 PF = cos(phi)*1000 in 10 bits; 2nd PF byte bit2 = P>=0, bit3 = Q>=0
    #   194 V/I:      [L1, L2, L3] x (I 0.1 A u24, V 0.1 V u32) + time tag
    def _encode_energy_block(self, energy: dict[str, object], meter_time: datetime) -> bytes:
        return b"".join(
            [
                encode_energy_kwh(float(energy["active_import"])),
                encode_energy_kwh(float(energy["active_export"])),
                encode_energy_kwh(float(energy["reactive_import"])),
                encode_energy_kwh(0.0),
                encode_energy_kwh(0.0),
                encode_energy_kwh(float(energy["reactive_export"])),
            ]
        ) + encode_time_tag_a(meter_time)

    def _encode_power_block(self, electrical: dict[str, object], meter_time: datetime) -> bytes:
        pf = float(electrical["power_factor"])
        total_p = float(electrical["active_power_total"])
        total_q = float(electrical["reactive_power"])
        phases = [
            (total_p, total_q),
            (float(electrical["active_power_l1"]), total_q / 3.0),
            (float(electrical["active_power_l2"]), total_q / 3.0),
            (float(electrical["active_power_l3"]), total_q / 3.0),
        ]
        # The master takes the P/Q sign only from the total entry; use it everywhere.
        return b"".join(
            encode_u24(abs(p)) + encode_u24(abs(q)) + encode_pf_signed(pf, total_p >= 0, total_q >= 0)
            for p, q in phases
        ) + encode_time_tag_a(meter_time)

    def _encode_voltage_current_block(self, electrical: dict[str, object], meter_time: datetime) -> bytes:
        return b"".join(
            encode_u24(float(electrical[f"current_l{n}"]) * 10) + encode_u32(float(electrical[f"voltage_l{n}"]) * 10)
            for n in (1, 2, 3)
        ) + encode_time_tag_a(meter_time)

    def _encode_general_values(self, snapshot: dict[str, object]) -> tuple[bytes, str]:
        # ASDU 157, object 198: primary/secondary voltage and current (uint32 LE each).
        # The master computes ratio = primary // secondary and multiplies V and I by it.
        profile = snapshot["profile"]
        ratios = [
            int(profile.get("voltage_primary", 1)),
            int(profile.get("voltage_secondary", 1)),
            int(profile.get("current_primary", 1)),
            int(profile.get("current_secondary", 1)),
        ]
        objects = bytes([OBJECT_TRANSFORMER_RATIOS]) + b"".join(encode_u32(value) for value in ratios)
        payload = self._encode_asdu(
            type_id=TYPE_GENERAL_VALUES,
            cause=CAUSE_REQUEST,
            measurement_point=int(snapshot["iec102"]["measurement_point"]),
            record_address=int(snapshot["iec102"]["record_address"]),
            objects=objects,
            object_count=1,
        )
        return payload, "ASDU 157 transformer ratios V {}/{} I {}/{}".format(*ratios)

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



def encode_u24(value: float) -> bytes:
    return max(0, min(int(round(value)), 0xFFFFFF)).to_bytes(3, "little")


def encode_u32(value: float) -> bytes:
    return max(0, min(int(round(value)), 0xFFFFFFFF)).to_bytes(4, "little")


def encode_energy_kwh(value: float) -> bytes:
    # Top 2 bits are quality flags (the master masks them with 0x3FFFFFFF).
    return max(0, min(int(round(value)), 0x3FFFFFFF)).to_bytes(4, "little")


def encode_pf_signed(value: float, active_positive: bool, reactive_positive: bool) -> bytes:
    scaled = max(0, min(int(round(abs(value) * 1000)), 0x3FF))
    flags = (0x04 if active_positive else 0) | (0x08 if reactive_positive else 0)
    return bytes([scaled & 0xFF, ((scaled >> 8) & 0x03) | flags])


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
