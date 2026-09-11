from __future__ import annotations

from datetime import datetime

from .constants import (
    CAUSE_ADDRESS_UNKNOWN,
    CAUSE_ASDU_NOT_AVAILABLE,
    CAUSE_DATA_NOT_AVAILABLE,
    CAUSE_REQUEST,
    TYPE_CURRENT_TIME,
    TYPE_INCREMENTAL_TOTALS,
    TYPE_INSTANT_VALUES,
    TYPE_INTEGRATED_TOTALS,
    TYPE_MANUFACTURER_IDENTIFICATION,
)
from .frame import LinkFrame, format_hex
from .parser import ParsedFrame

CAUSE_NAMES = {
    CAUSE_REQUEST: "requested",
    CAUSE_DATA_NOT_AVAILABLE: "data-not-available",
    CAUSE_ASDU_NOT_AVAILABLE: "asdu-not-available",
    CAUSE_ADDRESS_UNKNOWN: "address-unknown",
}

TYPE_NAMES = {
    TYPE_INTEGRATED_TOTALS: "integrated-totals",
    TYPE_INCREMENTAL_TOTALS: "incremental-totals",
    TYPE_MANUFACTURER_IDENTIFICATION: "manufacturer-identification",
    TYPE_CURRENT_TIME: "current-time",
    TYPE_INSTANT_VALUES: "instant-values",
}


class FrameDecoder:
    def decode_frame(self, parsed: ParsedFrame) -> dict[str, object]:
        frame: LinkFrame = parsed.frame
        output: dict[str, object] = {
            "kind": frame.kind.value,
            "address": frame.address,
            "control": frame.control,
            "function_code": frame.function_code,
            "is_request": frame.is_request,
            "hex": format_hex(frame.raw),
        }
        if parsed.asdu:
            output["asdu"] = {
                "type_id": parsed.asdu.type_id,
                "type_name": TYPE_NAMES.get(parsed.asdu.type_id, "unknown"),
                "cause": parsed.asdu.cause,
                "cause_name": CAUSE_NAMES.get(parsed.asdu.cause, "unknown"),
                "measurement_point": parsed.asdu.measurement_point,
                "record_address": parsed.asdu.record_address,
                "objects": self._decode_objects(parsed),
            }
        return output

    def _decode_objects(self, parsed: ParsedFrame) -> list[dict[str, object]]:
        assert parsed.asdu is not None
        type_id = parsed.asdu.type_id
        decoded: list[dict[str, object]] = []
        for obj in parsed.asdu.objects:
            item: dict[str, object] = {"address": obj.address, "raw": format_hex(obj.data)}
            if type_id in {TYPE_INTEGRATED_TOTALS, TYPE_INCREMENTAL_TOTALS} and len(obj.data) >= 5:
                item["value"] = int.from_bytes(obj.data[:4], "little") / 1000.0
                item["qualifier"] = obj.data[4]
            elif type_id == TYPE_CURRENT_TIME and len(obj.data) >= 7:
                item["meter_time"] = self._decode_time_tag_b(obj.data[:7])
            elif type_id == TYPE_MANUFACTURER_IDENTIFICATION and len(obj.data) >= 11:
                item["manufacturer"] = obj.data[:3].decode("ascii", errors="ignore").strip()
                item["equipment_code"] = obj.data[3:11].decode("ascii", errors="ignore").strip()
            decoded.append(item)
        return decoded

    def _decode_time_tag_b(self, payload: bytes) -> str:
        milliseconds = payload[0] | ((payload[1] & 0x03) << 8)
        second = (payload[1] >> 2) & 0x3F
        minute = payload[2] & 0x3F
        hour = payload[3] & 0x1F
        day = payload[4] & 0x1F
        month = payload[5] & 0x0F
        year = 2000 + (payload[6] & 0x7F)
        return datetime(year, month or 1, day or 1, hour, minute, second, milliseconds * 1000).isoformat(sep=" ")
