from __future__ import annotations

import threading
from typing import Any

from .base import BaseTransport, TransportStatus

try:
    import serial
    from serial.tools import list_ports
except Exception:  # pragma: no cover - optional dependency during tests
    serial = None
    list_ports = None


class SerialTransport(BaseTransport):
    def __init__(self, port: str, baudrate: int, bytesize: int, parity: str, stopbits: int, timeout: float, callback) -> None:
        super().__init__(callback)
        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.timeout = timeout
        self._serial: Any = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @staticmethod
    def available_ports() -> list[str]:
        if list_ports is None:
            return []
        return [port.device for port in list_ports.comports()]

    def start(self) -> None:
        if serial is None:
            self.emit("status", TransportStatus("ERROR", "pyserial is not installed"))
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=int(self.baudrate),
                bytesize=int(self.bytesize),
                parity=self.parity,
                stopbits=int(self.stopbits),
                timeout=float(self.timeout),
            )
            self.emit("status", TransportStatus("CONNECTED", self.port))
            while not self._stop_event.is_set() and self._serial is not None:
                chunk = self._serial.read(4096)
                if chunk:
                    self.emit("rx", {"transport": f"SERIAL {self.port}", "data": chunk})
        except Exception as exc:  # pragma: no cover - requires serial device
            self.emit("status", TransportStatus("ERROR", str(exc)))
        finally:
            if self._serial is not None:
                self._serial.close()
                self._serial = None

    def send(self, data: bytes) -> None:
        if self._serial is None:
            raise RuntimeError("Serial port is not open")
        self._serial.write(data)

    def stop(self) -> None:
        self._stop_event.set()
        if self._serial is not None:
            self._serial.close()
            self._serial = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self.emit("status", TransportStatus("STOPPED"))
