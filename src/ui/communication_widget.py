from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.transport.serial_transport import SerialTransport


class CommunicationWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.serial_radio = QRadioButton("Serial")
        self.tcp_radio = QRadioButton("TCP Server")
        self.serial_radio.setChecked(True)

        self.mode_stack = QStackedWidget()
        self.serial_port = QComboBox()
        self.refresh_ports_button = QPushButton("Refresh COM")
        self.serial_baudrate = QComboBox()
        self.serial_baudrate.addItems(["300", "600", "1200", "2400", "4800", "9600", "19200"])
        self.serial_bytesize = QComboBox()
        self.serial_bytesize.addItems(["5", "6", "7", "8"])
        self.serial_bytesize.setCurrentText("8")
        self.serial_parity = QComboBox()
        self.serial_parity.addItems(["N", "E", "O"])
        self.serial_parity.setCurrentText("E")
        self.serial_stopbits = QComboBox()
        self.serial_stopbits.addItems(["1", "2"])
        self.serial_timeout = QLineEdit("1.0")

        serial_form = QFormLayout()
        serial_row = QHBoxLayout()
        serial_row.addWidget(self.serial_port)
        serial_row.addWidget(self.refresh_ports_button)
        serial_form.addRow("Port", serial_row)
        serial_form.addRow("Baudrate", self.serial_baudrate)
        serial_form.addRow("Data bits", self.serial_bytesize)
        serial_form.addRow("Parity", self.serial_parity)
        serial_form.addRow("Stop bits", self.serial_stopbits)
        serial_form.addRow("Timeout (s)", self.serial_timeout)
        serial_box = QGroupBox("Serial")
        serial_box.setLayout(serial_form)

        self.tcp_host = QLineEdit("0.0.0.0")
        self.tcp_port = QLineEdit("4001")
        tcp_form = QFormLayout()
        tcp_form.addRow("Local IP", self.tcp_host)
        tcp_form.addRow("Port", self.tcp_port)
        tcp_box = QGroupBox("TCP")
        tcp_box.setLayout(tcp_form)

        self.mode_stack.addWidget(serial_box)
        self.mode_stack.addWidget(tcp_box)

        self.start_button = QPushButton("START SERVER / CONNECT")
        self.stop_button = QPushButton("STOP")
        self.disconnect_button = QPushButton("Disconnect client")
        self.status_label = QLabel("STOPPED")
        self.client_label = QLabel("-")

        top = QHBoxLayout()
        top.addWidget(self.serial_radio)
        top.addWidget(self.tcp_radio)
        top.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.stop_button)
        buttons.addWidget(self.disconnect_button)
        buttons.addStretch(1)

        status_grid = QGridLayout()
        status_grid.addWidget(QLabel("Status"), 0, 0)
        status_grid.addWidget(self.status_label, 0, 1)
        status_grid.addWidget(QLabel("Client connected"), 1, 0)
        status_grid.addWidget(self.client_label, 1, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.mode_stack)
        layout.addLayout(buttons)
        layout.addLayout(status_grid)

        self.serial_radio.toggled.connect(self._update_mode)
        self.refresh_ports_button.clicked.connect(self.refresh_ports)
        self.refresh_ports()
        self._update_mode()

    def _update_mode(self) -> None:
        self.mode_stack.setCurrentIndex(0 if self.serial_radio.isChecked() else 1)

    def refresh_ports(self) -> None:
        current = self.serial_port.currentText()
        self.serial_port.clear()
        ports = SerialTransport.available_ports() or ["COM1", "COM2", "COM3"]
        self.serial_port.addItems(ports)
        if current and current in ports:
            self.serial_port.setCurrentText(current)

    def set_mode(self, mode: str) -> None:
        serial = mode == "serial"
        self.serial_radio.setChecked(serial)
        self.tcp_radio.setChecked(not serial)
        self._update_mode()

    def to_updates(self) -> dict[str, object]:
        return {
            "communication": {
                "mode": "serial" if self.serial_radio.isChecked() else "tcp",
                "serial": {
                    "port": self.serial_port.currentText(),
                    "baudrate": int(self.serial_baudrate.currentText()),
                    "bytesize": int(self.serial_bytesize.currentText()),
                    "parity": self.serial_parity.currentText(),
                    "stopbits": int(self.serial_stopbits.currentText()),
                    "timeout": float(self.serial_timeout.text() or "1.0"),
                },
                "tcp": {
                    "host": self.tcp_host.text() or "0.0.0.0",
                    "port": int(self.tcp_port.text() or "4001"),
                },
            }
        }

    def apply_snapshot(self, snapshot: dict[str, object]) -> None:
        communication = snapshot["communication"]
        self.set_mode(communication["mode"])
        serial = communication["serial"]
        if serial["port"] and self.serial_port.findText(serial["port"]) == -1:
            self.serial_port.addItem(serial["port"])
        self.serial_port.setCurrentText(serial["port"])
        self.serial_baudrate.setCurrentText(str(serial["baudrate"]))
        self.serial_bytesize.setCurrentText(str(serial["bytesize"]))
        self.serial_parity.setCurrentText(serial["parity"])
        self.serial_stopbits.setCurrentText(str(serial["stopbits"]))
        self.serial_timeout.setText(str(serial["timeout"]))
        tcp = communication["tcp"]
        self.tcp_host.setText(tcp["host"])
        self.tcp_port.setText(str(tcp["port"]))
