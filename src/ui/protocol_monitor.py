from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout, QWidget


class ProtocolMonitorWidget(QWidget):
    def __init__(self, log_directory: Path) -> None:
        super().__init__()
        self.log_directory = log_directory
        self.log_directory.mkdir(parents=True, exist_ok=True)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.clear_button = QPushButton("Clear monitor")
        self.save_button = QPushButton("Save log")
        self.open_button = QPushButton("Open logs directory")

        controls = QHBoxLayout()
        controls.addWidget(self.clear_button)
        controls.addWidget(self.save_button)
        controls.addWidget(self.open_button)
        controls.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.text_edit)

        self.open_button.clicked.connect(self.open_logs_directory)

    def append_entry(self, text: str) -> None:
        if not text:
            self.text_edit.clear()
            return
        if self.text_edit.toPlainText():
            self.text_edit.append("")
        self.text_edit.append(text)

    def open_logs_directory(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.log_directory.resolve())))
