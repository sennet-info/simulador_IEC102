from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.meter.model import MeterModel
from src.protocol.iec102.application_layer import ApplicationLayer, encode_24
from src.protocol.iec102.constants import (
    CAUSE_ADDRESS_UNKNOWN,
    MASTER_REQUEST_CLASS_2_DATA,
    MASTER_SEND_USER_DATA,
    TYPE_CURRENT_TIME,
    TYPE_INCREMENTAL_TOTALS,
    TYPE_INTEGRATED_TOTALS,
    TYPE_READ_CURRENT_TIME,
    TYPE_READ_INTEGRATED_TOTALS,
)
from src.protocol.iec102.encoder import encode_fixed_frame, encode_variable_frame
from src.protocol.iec102.parser import FrameParseError, FrameParser

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profiles" / "generic_iec102.json"


class ProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = FrameParser()
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.model = MeterModel(Path(self.tempdir.name) / "config.json", PROFILE)
        self.app = ApplicationLayer(self.model)

    def test_parse_fixed_frame(self) -> None:
        frame = encode_fixed_frame(0x49, 1)
        parsed = self.parser.parse(frame)
        self.assertEqual(parsed.frame.address, 1)
        self.assertEqual(parsed.frame.function_code, 9)

    def test_invalid_checksum_raises(self) -> None:
        with self.assertRaises(FrameParseError):
            self.parser.parse(bytes([0x10, 0x49, 0x01, 0x00, 0x00, 0x16]))

    def test_incomplete_variable_frame_raises(self) -> None:
        with self.assertRaises(FrameParseError):
            self.parser.parse(bytes([0x68, 0x05, 0x05, 0x68, 0x73]))

    def test_read_current_time_is_queued_then_returned_on_class2_poll(self) -> None:
        request_payload = bytes([TYPE_READ_CURRENT_TIME, 0x00, 0x05, 0x01, 0x00, 0x01])
        request_frame = encode_variable_frame(0x73, 1, request_payload)
        ack = self.app.handle(self.parser.parse(request_frame))
        self.assertEqual(ack.response.raw[0], 0x10)
        self.assertIn("queued", ack.decoded.lower())

        poll_frame = encode_fixed_frame(0x5B, 1)
        response = self.app.handle(self.parser.parse(poll_frame))
        parsed_response = self.parser.parse(response.response.raw)
        self.assertEqual(parsed_response.asdu.type_id, TYPE_CURRENT_TIME)

    def test_integrated_totals_response_contains_configured_energy(self) -> None:
        self.model.apply_updates({"energy": {"active_import": 223456.789, "reactive_import": 333.0}})
        request_payload = bytes([TYPE_READ_INTEGRATED_TOTALS, 0x00, 0x05, 0x01, 0x00, 0x01])
        request_frame = encode_variable_frame(0x73, 1, request_payload)
        self.app.handle(self.parser.parse(request_frame))
        response = self.app.handle(self.parser.parse(encode_fixed_frame(MASTER_REQUEST_CLASS_2_DATA | 0x40, 1)))
        parsed_response = self.parser.parse(response.response.raw)
        self.assertEqual(parsed_response.asdu.type_id, TYPE_INTEGRATED_TOTALS)
        self.assertIsNotNone(parsed_response.asdu.shared_time)
        first = parsed_response.asdu.objects[0]
        self.assertEqual(first.address, 1)
        self.assertEqual(int.from_bytes(first.data[:4], "little"), 223456789)

    def test_integrated_totals_range_request_returns_reactive_values(self) -> None:
        self.model.apply_updates({"energy": {"reactive_import": 333.0, "reactive_export": 444.0}})
        request_payload = bytes([TYPE_READ_INTEGRATED_TOTALS, 0x01, 0x05, 0x01, 0x00, 0x01, 0x03, 0x06])
        request_frame = encode_variable_frame(0x73, 1, request_payload)
        self.app.handle(self.parser.parse(request_frame))
        response = self.app.handle(self.parser.parse(encode_fixed_frame(0x4B, 1)))
        parsed_response = self.parser.parse(response.response.raw)
        self.assertEqual([obj.address for obj in parsed_response.asdu.objects], [3, 4, 5, 6])
        values = [int.from_bytes(obj.data[:4], "little") for obj in parsed_response.asdu.objects]
        self.assertEqual(values, [333000, 333000, 444000, 444000])

    def test_wrong_measurement_point_queues_address_error(self) -> None:
        request_payload = bytes([TYPE_READ_INTEGRATED_TOTALS, 0x00, 0x05, 0x02, 0x00, 0x01])
        request_frame = encode_variable_frame(0x73, 1, request_payload)
        self.app.handle(self.parser.parse(request_frame))
        response = self.app.handle(self.parser.parse(encode_fixed_frame(0x4B, 1)))
        parsed_response = self.parser.parse(response.response.raw)
        self.assertEqual(parsed_response.asdu.cause, CAUSE_ADDRESS_UNKNOWN)

    def test_instant_values_response_contains_expected_blocks(self) -> None:
        self.model.apply_updates({"energy": {"active_import": 223456.789}, "electrical": {"active_power_total": -1.0}})
        request_payload = bytes([162, 0x00, 0x05, 0x01, 0x00, 0x01])
        request_frame = encode_variable_frame(0x73, 1, request_payload)
        self.app.handle(self.parser.parse(request_frame))
        response = self.app.handle(self.parser.parse(encode_fixed_frame(0x4B, 1)))
        parsed_response = self.parser.parse(response.response.raw)
        self.assertEqual(parsed_response.asdu.type_id, 163)
        self.assertEqual([obj.address for obj in parsed_response.asdu.objects], [192, 193, 194])
        energy_block = parsed_response.asdu.objects[0].data
        instant_energy = int.from_bytes(energy_block[:3], "little") | (((energy_block[3] & 0xFC) >> 2) << 24)
        self.assertEqual(instant_energy, 223456789)
        power_block = parsed_response.asdu.objects[1].data
        self.assertEqual(power_block[:3], encode_24(-1.0))

    def test_signed_power_encoding_preserves_negative_values(self) -> None:
        self.assertEqual(encode_24(-1.0), bytes([0x18, 0xFC, 0xFF]))

    def test_incremental_totals_response_type(self) -> None:
        request_payload = bytes([123, 0x00, 0x05, 0x01, 0x00, 0x01])
        request_frame = encode_variable_frame(0x73, 1, request_payload)
        self.app.handle(self.parser.parse(request_frame))
        response = self.app.handle(self.parser.parse(encode_fixed_frame(0x4B, 1)))
        parsed_response = self.parser.parse(response.response.raw)
        self.assertEqual(parsed_response.asdu.type_id, TYPE_INCREMENTAL_TOTALS)


if __name__ == "__main__":
    unittest.main()
