"""Regression checks for SQL binding and safe JSON file handling."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import mock_open, patch

import pharmacy_system as pharmacy


class SecurityTests(unittest.TestCase):
    """Exercise the security changes independently of the stock refactor."""

    def setUp(self):
        pharmacy.conn.execute("DROP TABLE IF EXISTS patients")
        pharmacy.setup_database()
        pharmacy.stock.clear()
        pharmacy.prescriptions.clear()

    def test_lookup_binds_injection_as_data(self):
        self.assertEqual(pharmacy.find_patient("' OR 1=1 --"), [])
        self.assertEqual(pharmacy.find_patient("Arjun"), [("P2", "none")])

    def test_lookup_handles_apostrophe(self):
        pharmacy.conn.execute(
            "INSERT INTO patients VALUES (?, ?, ?)",
            ("P4", "O'Brien", "none"),
        )
        self.assertEqual(pharmacy.find_patient("O'Brien"), [("P4", "none")])

    def test_missing_file_preserves_stock(self):
        pharmacy.stock["existing"] = {"units": 3, "expiry": "2099-01-01"}
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(pharmacy.load_stock(Path(directory) / "missing"))
        self.assertEqual(pharmacy.stock["existing"]["units"], 3)

    def test_invalid_json_is_reported_and_preserves_stock(self):
        pharmacy.stock["existing"] = {"units": 3, "expiry": "2099-01-01"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                pharmacy.load_stock(path)
        self.assertEqual(pharmacy.stock["existing"]["units"], 3)

    def test_permission_error_is_not_swallowed(self):
        with patch("builtins.open", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                pharmacy.load_stock("denied.json")

    def test_export_round_trip(self):
        pharmacy.prescriptions.append({"patient": "P2", "drug": "test"})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prescriptions.json"
            pharmacy.export_prescriptions(path)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")),
                             pharmacy.prescriptions)

    def test_export_closes_file_when_serialization_fails(self):
        pharmacy.prescriptions.append(object())
        opened = mock_open()
        with patch("builtins.open", opened):
            with self.assertRaises(TypeError):
                pharmacy.export_prescriptions("unused.json")
        opened.return_value.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
