from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class EnergyWidget(QWidget):
    ENERGY_FIELDS = [
        ("active_import", "Active Import (kWh)"),
        ("active_export", "Active Export (kWh)"),
        ("reactive_import", "Reactive Import (kvarh)"),
        ("reactive_export", "Reactive Export (kvarh)"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.inputs: dict[str, QDoubleSpinBox] = {}
        form = QFormLayout()
        for name, label in self.ENERGY_FIELDS:
            spin = QDoubleSpinBox()
            spin.setDecimals(3)
            spin.setRange(0, 1_000_000_000)
            spin.setSingleStep(1.0)
            self.inputs[name] = spin
            form.addRow(label, spin)
        self.mode = QComboBox()
        self.mode.addItems(["manual", "automatic"])
        self.acceleration = QComboBox()
        self.acceleration.addItems(["1", "10", "60", "100", "1000"])
        form.addRow("Simulation mode", self.mode)
        form.addRow("Time acceleration", self.acceleration)
        group = QGroupBox("Energy")
        group.setLayout(form)
        layout = QVBoxLayout(self)
        layout.addWidget(group)
        layout.addWidget(QLabel("Tariff totals are persisted in config and reserved for later IEC-102 extensions."))

    def to_updates(self) -> dict[str, object]:
        return {
            "energy": {
                **{name: widget.value() for name, widget in self.inputs.items()},
                "mode": self.mode.currentText(),
                "time_acceleration": float(self.acceleration.currentText()),
            }
        }

    def apply_snapshot(self, snapshot: dict[str, object]) -> None:
        energy = snapshot["energy"]
        for name, widget in self.inputs.items():
            widget.setValue(float(energy[name]))
        self.mode.setCurrentText(str(energy["mode"]))
        self.acceleration.setCurrentText(str(int(float(energy["time_acceleration"]))))
