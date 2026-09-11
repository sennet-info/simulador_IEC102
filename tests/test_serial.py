from __future__ import annotations

import unittest

from src.transport.serial_transport import SerialTransport


class SerialTransportTests(unittest.TestCase):
    def test_available_ports_returns_list(self) -> None:
        ports = SerialTransport.available_ports()
        self.assertIsInstance(ports, list)


if __name__ == "__main__":
    unittest.main()
