from __future__ import annotations

from .constants import END_FRAME, START_FIXED, START_VARIABLE


def encode_fixed_frame(control: int, address: int) -> bytes:
    low = address & 0xFF
    high = (address >> 8) & 0xFF
    checksum = (control + low + high) & 0xFF
    return bytes([START_FIXED, control, low, high, checksum, END_FRAME])


def encode_variable_frame(control: int, address: int, payload: bytes) -> bytes:
    low = address & 0xFF
    high = (address >> 8) & 0xFF
    length = 3 + len(payload)
    checksum = (control + low + high + sum(payload)) & 0xFF
    return bytes([START_VARIABLE, length, length, START_VARIABLE, control, low, high]) + payload + bytes([checksum, END_FRAME])
