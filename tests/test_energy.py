from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.meter.model import MeterModel

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profiles" / "generic_iec102.json"


class EnergySimulationTests(unittest.TestCase):
    def test_automatic_energy_uses_elapsed_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model = MeterModel(Path(tmp) / "config.json", PROFILE)
            model.apply_updates({"energy": {"mode": "automatic", "time_acceleration": 60}, "electrical": {"active_power_total": 10.0, "reactive_power": 5.0}})
            start = model._last_simulation_tick
            with patch("src.meter.model.time.monotonic", return_value=start + 60.0):
                snapshot = model.snapshot()
            self.assertAlmostEqual(snapshot["energy"]["active_import"], 123466.789, places=3)
            self.assertAlmostEqual(snapshot["energy"]["reactive_import"], 12350.678, places=3)


if __name__ == "__main__":
    unittest.main()
