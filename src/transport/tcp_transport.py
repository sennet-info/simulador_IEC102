from __future__ import annotations

import socket
import threading
from typing import cast

from .base import BaseTransport, TransportStatus


class TcpServerTransport(BaseTransport):
    def __init__(self, host: str, port: int, callback) -> None:
        super().__init__(callback)
        self.host = host
        self.port = port
        self._server: socket.socket | None = None
        self._client: socket.socket | None = None
        self._client_address: tuple[str, int] | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._send_lock = threading.Lock()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((self.host, int(self.port)))
        self._server.listen(1)
        self._server.settimeout(0.5)
        self.emit("status", TransportStatus("LISTENING", f"{self.host}:{self.port}"))
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            while not self._stop_event.is_set():
                try:
                    client, address = self._server.accept()
                except socket.timeout:
                    continue
                if self._client is not None:
                    client.close()
                    continue
                self._client = client
                self._client_address = address
                client.settimeout(0.5)
                self.emit("client", f"{address[0]}:{address[1]}")
                self.emit("status", TransportStatus("CONNECTED", f"{address[0]}:{address[1]}"))
                try:
                    while not self._stop_event.is_set():
                        try:
                            chunk = client.recv(4096)
                        except socket.timeout:
                            continue
                        except OSError:
                            break
                        if not chunk:
                            break
                        self.emit("rx", {"transport": f"TCP {address[0]}:{address[1]}", "data": chunk})
                finally:
                    if self._close_client():
                        self.emit("client", None)
                        if not self._stop_event.is_set():
                            self.emit("status", TransportStatus("LISTENING", f"{self.host}:{self.port}"))
        except OSError as exc:
            if not self._stop_event.is_set():
                self.emit("status", TransportStatus("ERROR", str(exc)))
        finally:
            if self._server is not None:
                self._server.close()
                self._server = None

    def send(self, data: bytes) -> None:
        with self._send_lock:
            if self._client is None:
                raise RuntimeError("No TCP client connected")
            self._client.sendall(data)

    def _close_client(self) -> bool:
        with self._send_lock:
            client = self._client
            self._client = None
            self._client_address = None
            if client is None:
                return False
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            client.close()
            return True

    def disconnect_client(self) -> None:
        if self._close_client():
            self.emit("client", None)
            if self._server is not None and not self._stop_event.is_set():
                self.emit("status", TransportStatus("LISTENING", f"{self.host}:{self.port}"))

    def stop(self) -> None:
        self._stop_event.set()
        self._close_client()
        if self._server is not None:
            self._server.close()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self.emit("status", TransportStatus("STOPPED"))
