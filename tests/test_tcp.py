from __future__ import annotations

import socket
import time
import unittest

from src.transport.tcp_transport import TcpServerTransport


class TcpTransportTests(unittest.TestCase):
    def test_tcp_transport_receives_data(self) -> None:
        events: list[tuple[str, object]] = []

        def callback(event: str, payload: object) -> None:
            events.append((event, payload))

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]

        transport = TcpServerTransport("127.0.0.1", port, callback)
        transport.start()
        self.addCleanup(transport.stop)
        time.sleep(0.2)
        client = socket.create_connection(("127.0.0.1", port), timeout=2)
        self.addCleanup(client.close)
        client.sendall(b"\x10\x49\x01\x00\x4A\x16")
        time.sleep(0.3)
        self.assertTrue(any(event == "rx" for event, _ in events))


if __name__ == "__main__":
    unittest.main()
