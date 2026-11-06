from __future__ import annotations

import threading
import time
import unittest

from src.transport.serial_transport import SerialTransport


class _FakeSerial:
    """Mimics pyserial: read(n) blocks until n bytes arrive or the timeout expires."""

    def __init__(self, data: bytes, timeout: float) -> None:
        self._data = bytearray(data)
        self.timeout = timeout

    @property
    def in_waiting(self) -> int:
        return len(self._data)

    def read(self, size: int) -> bytes:
        if len(self._data) < size:
            time.sleep(self.timeout)
        out = bytes(self._data[:size])
        del self._data[:size]
        return out

    def close(self) -> None:
        pass


class SerialTransportTests(unittest.TestCase):
    def test_available_ports_returns_list(self) -> None:
        ports = SerialTransport.available_ports()
        self.assertIsInstance(ports, list)

    def test_frame_is_delivered_without_waiting_for_read_timeout(self) -> None:
        received: list[tuple[float, bytes]] = []
        transport = SerialTransport("COMX", 9600, 8, "E", 1, 1.0, None)
        transport.emit = lambda kind, payload: received.append((time.monotonic(), payload["data"])) if kind == "rx" else None
        transport._serial = _FakeSerial(bytes.fromhex("10 49 01 00 4A 16"), timeout=1.0)
        start = time.monotonic()
        thread = threading.Thread(target=transport._run, daemon=True)
        thread.start()
        deadline = start + 2.0
        while not received and time.monotonic() < deadline:
            time.sleep(0.01)
        transport._stop_event.set()
        self.assertTrue(received)
        delivered_at, data = received[0]
        self.assertEqual(data, bytes.fromhex("10 49 01 00 4A 16"))
        self.assertLess(delivered_at - start, 0.3)


if __name__ == "__main__":
    unittest.main()
