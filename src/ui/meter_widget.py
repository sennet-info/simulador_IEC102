from __future__ import annotations

from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QVBoxLayout, QWidget


class MeterWidget(QWidget):
    FIELDS = [
        ("voltage_l1", "Voltage L1 (V)", 0, 1000, 2),
        ("voltage_l2", "Voltage L2 (V)", 0, 1000, 2),
        ("voltage_l3", "Voltage L3 (V)", 0, 1000, 2),
        ("current_l1", "Current L1 (A)", 0, 5000, 2),
        ("current_l2", "Current L2 (A)", 0, 5000, 2),
        ("current_l3", "Current L3 (A)", 0, 5000, 2),
        ("active_power_l1", "Active Power L1 (kW)", -100000, 100000, 3),
        ("active_power_l2", "Active Power L2 (kW)", -100000, 100000, 3),
        ("active_power_l3", "Active Power L3 (kW)", -100000, 100000, 3),
        ("active_power_total", "Active Power Total (kW)", -100000, 100000, 3),
        ("reactive_power", "Reactive Power (kvar)", -100000, 100000, 3),
        ("apparent_power", "Apparent Power (kVA)", 0, 100000, 3),
        ("power_factor", "Power Factor", 0, 1, 3),
        ("frequency", "Frequency (Hz)", 0, 1000, 2),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.inputs: dict[str, QDoubleSpinBox] = {}
        left_form = QFormLayout()
        right_form = QFormLayout()
        for index, (name, label, minimum, maximum, decimals) in enumerate(self.FIELDS):
            spin = QDoubleSpinBox()
            spin.setDecimals(decimals)
            spin.setRange(minimum, maximum)
            spin.setSingleStep(0.1)
            self.inputs[name] = spin
            (left_form if index < len(self.FIELDS) / 2 else right_form).addRow(label, spin)
        left = QGroupBox("Meter values")
        right = QGroupBox("Additional values")
        left.setLayout(left_form)
        right.setLayout(right_form)
        row = QHBoxLayout()
        row.addWidget(left)
        row.addWidget(right)
        layout = QVBoxLayout(self)
        layout.addLayout(row)

    def to_updates(self) -> dict[str, object]:
        return {"electrical": {name: widget.value() for name, widget in self.inputs.items()}}

    def apply_snapshot(self, snapshot: dict[str, object]) -> None:
        electrical = snapshot["electrical"]
        for name, widget in self.inputs.items():
            widget.setValue(float(electrical[name]))
