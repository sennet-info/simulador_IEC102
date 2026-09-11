from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from src.logging.protocol_logger import ProtocolEvent, ProtocolLogger
from src.meter.model import MeterModel
from src.protocol.iec102.application_layer import ApplicationLayer
from src.protocol.iec102.decoder import FrameDecoder
from src.protocol.iec102.parser import FrameParseError, FrameParser
from src.transport.base import BaseTransport, TransportStatus
from src.transport.serial_transport import SerialTransport
from src.transport.tcp_transport import TcpServerTransport


class SimulatorController(QObject):
    monitor_event = Signal(str)
    monitor_cleared = Signal()
    status_changed = Signal(str)
    client_changed = Signal(str)
    snapshot_changed = Signal(dict)
    log_saved = Signal(str)

    def __init__(self, repository_root: Path) -> None:
        super().__init__()
        self.repository_root = repository_root
        self.model = MeterModel(repository_root / "config.json", repository_root / "profiles" / "generic_iec102.json")
        self.parser = FrameParser()
        self.decoder = FrameDecoder()
        self.application = ApplicationLayer(self.model)
        self.logger = ProtocolLogger(repository_root / "logs")
        self.transport: BaseTransport | None = None
        self._rx_buffer = bytearray()

    def snapshot(self) -> dict[str, object]:
        snapshot = self.model.snapshot()
        self.snapshot_changed.emit(snapshot)
        return snapshot

    def apply_updates(self, updates: dict[str, object]) -> None:
        self.model.apply_updates(updates)
        self.snapshot()

    def start(self) -> None:
        snapshot = self.model.snapshot()
        communication = snapshot["communication"]
        mode = communication["mode"]
        self.stop()
        if mode == "serial":
            serial = communication["serial"]
            self.transport = SerialTransport(
                port=serial["port"],
                baudrate=serial["baudrate"],
                bytesize=serial["bytesize"],
                parity=serial["parity"],
                stopbits=serial["stopbits"],
                timeout=serial["timeout"],
                callback=self._handle_transport_event,
            )
        else:
            tcp = communication["tcp"]
            self.transport = TcpServerTransport(host=tcp["host"], port=int(tcp["port"]), callback=self._handle_transport_event)
        self._rx_buffer.clear()
        self.transport.start()

    def stop(self) -> None:
        if self.transport is not None:
            self.transport.stop()
            self.transport = None
        self.status_changed.emit("STOPPED")
        self.client_changed.emit("")

    def disconnect_client(self) -> None:
        if isinstance(self.transport, TcpServerTransport):
            self.transport.disconnect_client()

    def clear_monitor(self) -> None:
        self.logger.clear()
        self.monitor_cleared.emit()

    def save_log(self) -> None:
        path = self.logger.save()
        self.log_saved.emit(str(path))

    def _handle_transport_event(self, event: str, payload: object) -> None:
        if event == "status":
            status = payload if isinstance(payload, TransportStatus) else TransportStatus(str(payload))
            detail = f" {status.detail}" if status.detail else ""
            self.status_changed.emit(f"{status.state}{detail}")
            return
        if event == "client":
            self.client_changed.emit(str(payload or ""))
            return
        if event == "rx":
            raw = payload["data"]
            transport = payload["transport"]
            self._rx_buffer.extend(raw)
            frames = self.parser.extract_frames(self._rx_buffer)
            if frames:
                for frame_bytes in frames:
                    self._process_frame("RX", transport, frame_bytes)
            else:
                self._record_protocol_event("RX", transport, raw, "Partial frame buffered")

    def _process_frame(self, direction: str, transport: str, frame_bytes: bytes) -> None:
        try:
            parsed = self.parser.parse(frame_bytes)
            decoded_map = self.decoder.decode_frame(parsed)
            decoded_text = self._format_decoded_map(decoded_map)
            self._record_protocol_event(direction, transport, frame_bytes, decoded_text)
            if direction == "RX" and self.transport is not None:
                result = self.application.handle(parsed)
                self.transport.send(result.response.raw)
                self._record_protocol_event("TX", transport, result.response.raw, result.decoded)
        except FrameParseError as exc:
            self._record_protocol_event(direction, transport, frame_bytes, f"Parse error: {exc}")
        except Exception as exc:
            self._record_protocol_event(direction, transport, frame_bytes, f"Unhandled processing error: {exc}")

    def _record_protocol_event(self, direction: str, transport: str, raw: bytes, decoded: str) -> None:
        event = ProtocolEvent(datetime.now(), direction, transport, raw, decoded)
        self.logger.record(event)
        self.monitor_event.emit(event.to_monitor_line())

    def _format_decoded_map(self, decoded_map: dict[str, object]) -> str:
        parts = [
            f"kind={decoded_map['kind']}",
            f"link_address={decoded_map['address']}",
            f"function={decoded_map['function_code']}",
        ]
        asdu = decoded_map.get("asdu")
        if isinstance(asdu, dict):
            parts.extend(
                [
                    f"asdu={asdu.get('type_id')}:{asdu.get('type_name')}",
                    f"cause={asdu.get('cause')}:{asdu.get('cause_name')}",
                    f"measurement_point={asdu.get('measurement_point')}",
                    f"record={asdu.get('record_address')}",
                    f"objects={len(asdu.get('objects', []))}",
                ]
            )
        return " | ".join(parts)
