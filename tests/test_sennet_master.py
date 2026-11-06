"""Replays the SenNet/OWA mt_meter master session against the simulator.

Frames are built exactly as Send_Fix()/Send_Var() build them in app_DL
(mt_meter.c) and responses are decoded with the same fixed frame offsets that
Analyse_Rec() uses, so a layout change that would break the real datalogger
breaks this test.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.meter.model import MeterModel
from src.protocol.iec102.application_layer import ApplicationLayer
from src.protocol.iec102.parser import FrameParser

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profiles" / "generic_iec102.json"
LINK_ADDR = 1
METER_ADDR = 1
METER_KEY = 1


def checksum(data: bytes) -> int:
    return sum(data) & 0xFF


def send_fix(c_fld: int) -> bytes:
    body = bytes([c_fld, LINK_ADDR & 0xFF, LINK_ADDR >> 8])
    return bytes([0x10]) + body + bytes([checksum(body), 0x16])


def send_var(c_fld: int, asdu_id: int, nobjs: int, cause: int, reg_addr: int) -> bytes:
    body = bytes([c_fld, LINK_ADDR & 0xFF, LINK_ADDR >> 8, asdu_id, nobjs, cause, METER_ADDR & 0xFF, METER_ADDR >> 8, reg_addr])
    if asdu_id == 183:
        body += METER_KEY.to_bytes(4, "little")
    elif asdu_id == 162:
        body += bytes([192, 193, 194])
    elif asdu_id == 156:
        body += bytes([198])
    length = len(body)
    return bytes([0x68, length, length, 0x68]) + body + bytes([checksum(body), 0x16])


def get_value(rec: bytes, pos: int, nbytes: int) -> int:
    return int.from_bytes(rec[pos:pos + nbytes], "little")


class SenNetMasterSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.model = MeterModel(Path(self.tempdir.name) / "config.json", PROFILE)
        self.model.apply_updates(
            {
                "electrical": {
                    "voltage_l1": 230.0, "voltage_l2": 231.5, "voltage_l3": 229.2,
                    "current_l1": 10.0, "current_l2": 12.3, "current_l3": 8.7,
                    "active_power_l1": 2.3, "active_power_l2": 3.0, "active_power_l3": 1.6,
                    "active_power_total": 6.9, "reactive_power": 1.5, "power_factor": 0.97,
                },
                "energy": {"active_import": 123456.789, "active_export": 4321.0,
                           "reactive_import": 12345.678, "reactive_export": 99.0},
            },
            persist=False,
        )
        self.app = ApplicationLayer(self.model)
        self.parser = FrameParser()

    def exchange(self, frame: bytes) -> bytes:
        return self.app.handle(self.parser.parse(frame)).response.raw

    def test_full_session_as_read_by_master(self) -> None:
        # INIT -> TO_RESET -> TO_START: link status / reset / link status
        self.assertEqual(self.exchange(send_fix(0x49))[:2], b"\x10\x0B")
        self.assertEqual(self.exchange(send_fix(0x40))[:2], b"\x10\x00")
        self.assertEqual(self.exchange(send_fix(0x49))[:2], b"\x10\x0B")

        # TO_SESION -> TO_SESION_DATOS: login ACK, then rec[7] == 0xB7
        self.assertEqual(self.exchange(send_var(0x73, 183, 1, 6, 0))[:2], b"\x10\x00")
        self.assertEqual(self.exchange(send_fix(0x5B))[7], 0xB7)

        # TO_VALGENERAL -> TO_VALGENERAL_DATOS: rec[7] == 0x9D, ratios at 14/18/22/26
        self.assertEqual(self.exchange(send_var(0x73, 156, 1, 5, 0))[:2], b"\x10\x00")
        rec = self.exchange(send_fix(0x5B))
        self.assertEqual(rec[7], 0x9D)
        reltra_vol = get_value(rec, 14, 4) // get_value(rec, 18, 4)
        reltra_int = get_value(rec, 22, 4) // get_value(rec, 26, 4)
        self.assertEqual((reltra_vol, reltra_int), (1, 1))

        # TO_VALINS -> TO_VALINS_DATOS: rec[7] == 0xA3, values at fixed offsets
        self.assertEqual(self.exchange(send_var(0x73, 162, 3, 5, 0))[:2], b"\x10\x00")
        rec = self.exchange(send_fix(0x5B))
        self.assertEqual(rec[7], 0xA3)
        self.assertEqual(len(rec), rec[1] + 6)

        self.assertEqual(get_value(rec, 14, 4) & 0x3FFFFFFF, 123457)  # EAI kWh
        self.assertEqual(get_value(rec, 18, 4) & 0x3FFFFFFF, 4321)    # EAE kWh
        self.assertEqual(get_value(rec, 22, 4) & 0x3FFFFFFF, 12346)   # Q1 kvarh
        self.assertEqual(get_value(rec, 34, 4) & 0x3FFFFFFF, 99)      # Q4 kvarh

        self.assertEqual([get_value(rec, pos, 3) * reltra_vol for pos in (85, 92, 99)], [2300, 2315, 2292])
        self.assertEqual([get_value(rec, pos, 3) * reltra_int for pos in (82, 89, 96)], [100, 123, 87])

        self.assertTrue(rec[51] & 0x04)  # active power positive
        self.assertTrue(rec[51] & 0x08)  # reactive power positive
        self.assertEqual(get_value(rec, 44, 3) * 1000, 7000)  # POWA total W (kW resolution)
        self.assertEqual(get_value(rec, 47, 3) * 1000, 2000)  # POWR total
        self.assertEqual([get_value(rec, pos, 3) * 1000 for pos in (52, 60, 68)], [2000, 3000, 2000])
        self.assertEqual(rec[50] | ((rec[51] & 0x03) << 8), 970)  # cos phi * 1000

        # TO_END_SESION -> TO_END_SESION_DATOS: rec[7] == 0xBB
        self.assertEqual(self.exchange(send_var(0x73, 187, 0, 6, 0))[:2], b"\x10\x00")
        self.assertEqual(self.exchange(send_fix(0x5B))[7], 0xBB)

    def test_negative_power_sets_sign_flag_off(self) -> None:
        self.model.apply_updates({"electrical": {"active_power_total": -5.0}}, persist=False)
        self.exchange(send_var(0x73, 162, 3, 5, 0))
        rec = self.exchange(send_fix(0x5B))
        self.assertFalse(rec[51] & 0x04)
        self.assertEqual(get_value(rec, 44, 3), 5)

    def test_master_retry_after_timeout_gets_same_answer(self) -> None:
        self.exchange(send_var(0x73, 156, 1, 5, 0))
        first = self.exchange(send_fix(0x5B))
        again = self.exchange(send_fix(0x5B))  # master timed out and resent
        self.assertEqual(first, again)


if __name__ == "__main__":
    unittest.main()
