from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout, QWidget


class ProtocolMonitorWidget(QWidget):
    clear_requested = Signal()
    save_requested = Signal()

    def __init__(self, log_directory: Path) -> None:
        super().__init__()
        self.log_directory = log_directory
        self.log_directory.mkdir(parents=True, exist_ok=True)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setAccessibleName("Protocol monitor output")
        self.text_edit.setAccessibleDescription("Shows raw IEC102 RX and TX frames with decoded summaries.")
        self.clear_button = QPushButton("Clear monitor")
        self.clear_button.setAccessibleName("Clear protocol monitor")
        self.clear_button.setAccessibleDescription("Clears the visible protocol monitor entries.")
        self.save_button = QPushButton("Save log")
        self.save_button.setAccessibleName("Save protocol log")
        self.save_button.setAccessibleDescription("Saves the current protocol monitor contents to a log file.")
        self.open_button = QPushButton("Open logs directory")
        self.open_button.setAccessibleName("Open logs directory")
        self.open_button.setAccessibleDescription("Opens the directory that stores saved protocol logs.")

        controls = QHBoxLayout()
        controls.addWidget(self.clear_button)
        controls.addWidget(self.save_button)
        controls.addWidget(self.open_button)
        controls.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.text_edit)

        self.clear_button.clicked.connect(self.clear_entries)
        self.clear_button.clicked.connect(self.clear_requested.emit)
        self.save_button.clicked.connect(self.save_requested.emit)
        self.open_button.clicked.connect(self.open_logs_directory)

    def append_entry(self, text: str) -> None:
        if self.text_edit.toPlainText():
            self.text_edit.append("")
        self.text_edit.append(text)

    def clear_entries(self) -> None:
        self.text_edit.clear()

    def open_logs_directory(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.log_directory.resolve())))
