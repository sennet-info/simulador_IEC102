from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.app_controller import SimulatorController
from src.ui.communication_widget import CommunicationWidget
from src.ui.energy_widget import EnergyWidget
from src.ui.meter_widget import MeterWidget
from src.ui.protocol_monitor import ProtocolMonitorWidget


class MainWindow(QMainWindow):
    def __init__(self, repository_root: Path) -> None:
        super().__init__()
        self.setWindowTitle("IEC 60870-5-102 METER SIMULATOR")
        self.controller = SimulatorController(repository_root)

        self.communication = CommunicationWidget()
        self.meter = MeterWidget()
        self.energy = EnergyWidget()
        self.protocol_monitor = ProtocolMonitorWidget(repository_root / "logs")

        self.link_address = QLineEdit()
        self.measurement_point = QLineEdit()
        self.record_address = QLineEdit()
        self.common_address = QLineEdit()
        self.use_system_time = QCheckBox("Use Windows system time")
        self.use_system_time.setChecked(True)
        self.custom_meter_time = QLineEdit()
        self.apply_button = QPushButton("Apply values")
        self.status_banner = QLabel("Status: STOPPED")
        self.status_banner.setStyleSheet("font-weight: bold;")
        self.last_log_label = QLabel("Last log: -")

        addressing_form = QFormLayout()
        addressing_form.addRow("Link address", self.link_address)
        addressing_form.addRow("Meter/measurement point", self.measurement_point)
        addressing_form.addRow("Record address", self.record_address)
        addressing_form.addRow("Common ASDU", self.common_address)
        addressing_form.addRow(self.use_system_time)
        addressing_form.addRow("Custom meter time (ISO)", self.custom_meter_time)

        addressing_panel = QWidget()
        addressing_panel.setLayout(addressing_form)

        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.addWidget(QLabel("COMMUNICATION"))
        top_layout.addWidget(self.communication)
        top_layout.addWidget(QLabel("IEC-102 ADDRESSING"))
        top_layout.addWidget(addressing_panel)
        top_layout.addWidget(self.apply_button)
        top_layout.addWidget(self.status_banner)
        top_layout.addWidget(self.last_log_label)

        meter_tab = QWidget()
        meter_layout = QVBoxLayout(meter_tab)
        meter_layout.addWidget(self.meter)
        meter_layout.addWidget(self.energy)

        tabs = QTabWidget()
        tabs.addTab(meter_tab, "Meter")
        tabs.addTab(self.protocol_monitor, "PROTOCOL MONITOR")

        central = QWidget()
        layout = QVBoxLayout(central)
        split = QHBoxLayout()
        split.addWidget(top_container, 1)
        split.addWidget(tabs, 2)
        layout.addLayout(split)
        self.setCentralWidget(central)

        self.communication.start_button.clicked.connect(self.start_transport)
        self.communication.stop_button.clicked.connect(self.controller.stop)
        self.communication.disconnect_button.clicked.connect(self.controller.disconnect_client)
        self.apply_button.clicked.connect(self.apply_changes)
        self.protocol_monitor.clear_requested.connect(self.controller.clear_monitor)
        self.protocol_monitor.save_requested.connect(self.controller.save_log)
        self.controller.monitor_event.connect(self.protocol_monitor.append_entry)
        self.controller.monitor_cleared.connect(self.protocol_monitor.clear_entries)
        self.controller.status_changed.connect(self.on_status_changed)
        self.controller.client_changed.connect(self.communication.client_label.setText)
        self.controller.snapshot_changed.connect(self.apply_snapshot)
        self.controller.log_saved.connect(self.on_log_saved)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.controller.snapshot)
        self._timer.start()
        self.apply_snapshot(self.controller.snapshot())

    def start_transport(self) -> None:
        self.apply_changes()
        try:
            self.controller.start()
        except Exception as exc:
            QMessageBox.critical(self, "Start error", str(exc))

    def apply_changes(self) -> None:
        updates = {}
        updates.update(self.communication.to_updates())
        updates.update(self.meter.to_updates())
        updates.update(self.energy.to_updates())
        updates["iec102"] = {
            "link_address": int(self.link_address.text() or "1"),
            "measurement_point": int(self.measurement_point.text() or "1"),
            "record_address": int(self.record_address.text() or "1"),
            "common_address": int(self.common_address.text() or "1"),
            "use_system_time": self.use_system_time.isChecked(),
            "custom_meter_time": self.custom_meter_time.text() or None,
        }
        self.controller.apply_updates(updates)

    def apply_snapshot(self, snapshot: dict[str, object]) -> None:
        self.communication.apply_snapshot(snapshot)
        self.meter.apply_snapshot(snapshot)
        self.energy.apply_snapshot(snapshot)
        addressing = snapshot["iec102"]
        self.link_address.setText(str(addressing["link_address"]))
        self.measurement_point.setText(str(addressing["measurement_point"]))
        self.record_address.setText(str(addressing["record_address"]))
        self.common_address.setText(str(addressing["common_address"]))
        self.use_system_time.setChecked(bool(addressing["use_system_time"]))
        self.custom_meter_time.setText(str(addressing["custom_meter_time"] or ""))

    def on_status_changed(self, status: str) -> None:
        self.status_banner.setText(f"Status: {status}")
        self.communication.status_label.setText(status)

    def on_log_saved(self, path: str) -> None:
        self.last_log_label.setText(f"Last log: {path}")

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.controller.stop()
        super().closeEvent(event)
