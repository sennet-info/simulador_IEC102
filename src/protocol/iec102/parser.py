from __future__ import annotations

from dataclasses import dataclass

from .asdu import Asdu, InformationObject
from .constants import (
    OBJECT_INSTANT_ENERGY_BLOCK,
    OBJECT_INSTANT_POWER_BLOCK,
    OBJECT_INSTANT_VOLTAGE_CURRENT_BLOCK,
    TYPE_CURRENT_TIME,
    TYPE_INCREMENTAL_TOTALS,
    TYPE_INSTANT_VALUES,
    TYPE_INTEGRATED_TOTALS,
    TYPE_MANUFACTURER_IDENTIFICATION,
)
from .constants import END_FRAME, START_FIXED, START_VARIABLE
from .frame import FrameKind, LinkFrame


class FrameParseError(ValueError):
    pass


@dataclass
class ParsedFrame:
    frame: LinkFrame
    asdu: Asdu | None = None


class FrameParser:
    def extract_frames(self, buffer: bytearray) -> list[bytes]:
        frames: list[bytes] = []
        while buffer:
            if buffer[0] == START_FIXED:
                if len(buffer) < 6:
                    break
                frames.append(bytes(buffer[:6]))
                del buffer[:6]
                continue
            if buffer[0] == START_VARIABLE:
                if len(buffer) < 4:
                    break
                total_length = buffer[1] + 6
                if len(buffer) < total_length:
                    break
                frames.append(bytes(buffer[:total_length]))
                del buffer[:total_length]
                continue
            del buffer[0]
        return frames

    def parse(self, data: bytes) -> ParsedFrame:
        if not data:
            raise FrameParseError("Empty frame")
        if data[0] == START_FIXED:
            return ParsedFrame(frame=self._parse_fixed(data))
        if data[0] == START_VARIABLE:
            frame = self._parse_variable(data)
            asdu = self.parse_asdu(frame.payload) if frame.payload else None
            return ParsedFrame(frame=frame, asdu=asdu)
        raise FrameParseError("Unknown frame start byte")

    def _parse_fixed(self, data: bytes) -> LinkFrame:
        if len(data) != 6:
            raise FrameParseError("Fixed frame must contain 6 bytes")
        if data[-1] != END_FRAME:
            raise FrameParseError("Fixed frame missing end marker")
        checksum = (data[1] + data[2] + data[3]) & 0xFF
        if checksum != data[4]:
            raise FrameParseError("Fixed frame checksum mismatch")
        address = data[2] | (data[3] << 8)
        return LinkFrame(kind=FrameKind.FIXED, control=data[1], address=address, raw=data)

    def _parse_variable(self, data: bytes) -> LinkFrame:
        if len(data) < 10:
            raise FrameParseError("Variable frame is incomplete")
        if data[3] != START_VARIABLE or data[-1] != END_FRAME:
            raise FrameParseError("Variable frame markers are invalid")
        if data[1] != data[2]:
            raise FrameParseError("Variable frame length bytes differ")
        expected_length = data[1]
        if expected_length != len(data) - 6:
            raise FrameParseError("Variable frame length does not match payload")
        checksum = sum(data[4:-2]) & 0xFF
        if checksum != data[-2]:
            raise FrameParseError("Variable frame checksum mismatch")
        address = data[5] | (data[6] << 8)
        payload = data[7:-2]
        return LinkFrame(kind=FrameKind.VARIABLE, control=data[4], address=address, payload=payload, raw=data)

    def parse_asdu(self, payload: bytes) -> Asdu:
        if len(payload) < 6:
            raise FrameParseError("ASDU payload must contain at least 6 bytes")
        type_id = payload[0]
        vsq = payload[1]
        cause = payload[2]
        measurement_point = payload[3] | (payload[4] << 8)
        record_address = payload[5]
        objects_blob = payload[6:]
        objects: list[InformationObject] = []
        object_count = vsq & 0x7F
        shared_time: bytes | None = None
        expected_object_bytes = object_count * 6
        if type_id in {TYPE_INTEGRATED_TOTALS, TYPE_INCREMENTAL_TOTALS} and len(objects_blob) >= expected_object_bytes + 5:
            shared_time = objects_blob[expected_object_bytes:expected_object_bytes + 5]
            objects_blob = objects_blob[:expected_object_bytes]
        offset = 0
        lengths = self._object_lengths(type_id, object_count, objects_blob)
        for length in lengths:
            if offset >= len(objects_blob):
                break
            address = objects_blob[offset]
            chunk = objects_blob[offset + 1 : offset + length]
            objects.append(InformationObject(address=address, data=chunk))
            offset += length
        return Asdu(
            type_id=type_id,
            vsq=vsq,
            cause=cause,
            measurement_point=measurement_point,
            record_address=record_address,
            objects=objects,
            raw=payload,
            shared_time=shared_time,
        )

    def _object_lengths(self, type_id: int, count: int, blob: bytes) -> list[int]:
        if count <= 0:
            return []
        if type_id in {TYPE_INTEGRATED_TOTALS, TYPE_INCREMENTAL_TOTALS}:
            return [6] * count
        if type_id == TYPE_MANUFACTURER_IDENTIFICATION:
            return [len(blob)] if blob else []
        if type_id == TYPE_CURRENT_TIME:
            return [8] * count
        if type_id == TYPE_INSTANT_VALUES:
            mapping = {
                OBJECT_INSTANT_ENERGY_BLOCK: 30,
                OBJECT_INSTANT_POWER_BLOCK: 38,
                OBJECT_INSTANT_VOLTAGE_CURRENT_BLOCK: 27,
            }
            lengths: list[int] = []
            offset = 0
            while offset < len(blob) and len(lengths) < count:
                address = blob[offset]
                length = mapping.get(address, len(blob) - offset)
                lengths.append(length)
                offset += length
            return lengths
        base = len(blob) // count
        extra = len(blob) % count
        return [base + (1 if index < extra else 0) for index in range(count)]
