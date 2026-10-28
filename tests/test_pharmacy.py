"""Behavior regressions with fixed calendar dates and isolated state."""

from copy import deepcopy
from datetime import date, timedelta
import json
from pathlib import Path
import tempfile
import unittest

import pharmacy_system as pharmacy


TODAY = date(2030, 6, 15)


class PharmacyTests(unittest.TestCase):
    """Cover quantities, allergies, stock availability, and date boundaries."""

    def setUp(self):
        pharmacy.conn.execute("DROP TABLE IF EXISTS patients")
        pharmacy.setup_database()
        pharmacy.stock.clear()
        pharmacy.prescriptions.clear()

    def add(self, drug="Paracetamol", units=10, days=30):
        """Create dated stock relative to a deterministic reference day."""
        return pharmacy.add_stock(
            drug, units, (TODAY + timedelta(days=days)).isoformat()
        )

    def reject(self, patient="Arjun", drug="Paracetamol", units=1):
        """Check that rejection leaves every stock and prescription unchanged."""
        before_stock = deepcopy(pharmacy.stock)
        before_records = deepcopy(pharmacy.prescriptions)
        self.assertFalse(pharmacy.dispense(patient, drug, units, today=TODAY))
        self.assertEqual(pharmacy.stock, before_stock)
        self.assertEqual(pharmacy.prescriptions, before_records)

    def test_positive_dispensing_records_and_decrements(self):
        self.add()
        self.assertTrue(pharmacy.dispense(
            "Arjun", "  PARACETAMOL ", 3, today=TODAY
        ))
        self.assertEqual(pharmacy.stock["paracetamol"]["units"], 7)
        record = pharmacy.prescriptions[0]
        self.assertEqual((record["patient"], record["drug"], record["units"]),
                         ("P2", "paracetamol", 3))
        self.assertTrue(record["time"])

    def test_exact_available_quantity_can_be_dispensed(self):
        self.add()
        self.assertTrue(pharmacy.dispense(
            "Arjun", "Paracetamol", 10, today=TODAY
        ))
        self.assertEqual(pharmacy.stock["paracetamol"]["units"], 0)
        self.reject()

    def test_case_insensitive_allergies(self):
        for patient, drug in [("Kavya", "Penicillin"), ("Meena", "Ibuprofen")]:
            self.add(drug)
            with self.subTest(patient=patient):
                self.reject(patient, drug.upper())

    def test_multiple_allergies_are_normalized(self):
        pharmacy.conn.execute(
            "UPDATE patients SET allergy = ? WHERE id = ?",
            (" IBUPROFEN , penicillin ", "P2"),
        )
        self.add("Ibuprofen")
        self.reject(drug="Ibuprofen")

    def test_allergy_is_exact_medicine_match(self):
        self.add("Pen")
        self.assertTrue(pharmacy.dispense("Kavya", "Pen", 1, today=TODAY))

    def test_unknown_patient_preserves_state(self):
        self.add()
        self.reject(patient="Ghost")

    def test_injected_patient_cannot_dispense(self):
        self.add()
        self.reject(patient="' OR 1=1 --")

    def test_unknown_medicine_preserves_state(self):
        self.add()
        self.reject(drug="unknown")

    def test_insufficient_stock_preserves_state(self):
        self.add()
        self.reject(units=11)

    def test_invalid_dispensing_quantities_preserve_state(self):
        self.add()
        for units in [0, -1, 1.5, "2", None, True, False]:
            with self.subTest(units=units):
                self.reject(units=units)

    def test_invalid_stock_quantities_preserve_state(self):
        self.add()
        before = deepcopy(pharmacy.stock)
        for units in [0, -1, 1.5, "2", None, True, False]:
            with self.subTest(units=units):
                with self.assertRaises(ValueError):
                    pharmacy.add_stock("Paracetamol", units, "2030-07-15")
                self.assertEqual(pharmacy.stock, before)

    def test_invalid_medicine_names(self):
        for name in ["", "  ", None, 4]:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    pharmacy.add_stock(name, 1, "2030-07-15")
                self.reject(drug=name)

    def test_normalized_additions_share_inventory(self):
        self.add("Paracetamol", 3)
        self.add(" PARACETAMOL ", 4)
        self.assertEqual(list(pharmacy.stock), ["paracetamol"])
        self.assertEqual(pharmacy.stock["paracetamol"]["units"], 7)

    def test_default_batch_logs_are_independent(self):
        self.assertEqual(self.add("First"), 1)
        self.assertEqual(self.add("Second"), 1)

    def test_explicit_batch_log_accumulates(self):
        batch_log = []
        self.assertEqual(pharmacy.add_stock(
            "First", 2, "2030-07-15", batch_log
        ), 1)
        self.assertEqual(pharmacy.add_stock(
            "Second", 3, "2030-07-15", batch_log
        ), 2)
        self.assertEqual(batch_log, [("first", 2), ("second", 3)])

    def test_invalid_expiry_dates_preserve_state(self):
        self.add()
        before = deepcopy(pharmacy.stock)
        for expiry in ["2030-02-30", "2030-7-15", "20300715", "bad", None, 3]:
            with self.subTest(expiry=expiry):
                with self.assertRaises(ValueError):
                    pharmacy.add_stock("Paracetamol", 2, expiry)
                self.assertEqual(pharmacy.stock, before)

    def test_restock_cannot_overwrite_existing_expiry(self):
        self.add()
        before = deepcopy(pharmacy.stock)
        with self.assertRaises(ValueError):
            self.add(days=60)
        self.assertEqual(pharmacy.stock, before)

    def test_empty_stock_can_be_replenished_with_new_expiry(self):
        self.add()
        pharmacy.dispense("Arjun", "Paracetamol", 10, today=TODAY)
        self.add(days=60)
        self.assertEqual(pharmacy.stock["paracetamol"]["expiry"], "2030-08-14")

    def test_expired_stock_is_not_dispensed(self):
        self.add(days=-1)
        self.reject()

    def test_medicine_is_usable_on_expiry_day(self):
        self.add(days=0)
        self.assertTrue(pharmacy.dispense(
            "Arjun", "Paracetamol", 1, today=TODAY
        ))

    def test_expiry_window_includes_both_boundaries(self):
        for drug, days in [("expired", -1), ("today", 0), ("inside", 29),
                           ("boundary", 30), ("later", 31), ("empty", 15)]:
            self.add(drug, days=days)
        pharmacy.stock["empty"]["units"] = 0
        self.assertEqual(pharmacy.expiring_soon(today=TODAY),
                         ["today", "inside", "boundary"])
        self.assertEqual(pharmacy.expiring_soon(0, today=TODAY), ["today"])

    def test_expiry_window_crosses_year_and_leap_day(self):
        pharmacy.add_stock("Leap", 1, "2032-02-29")
        pharmacy.add_stock("January", 1, "2032-01-01")
        self.assertEqual(pharmacy.expiring_soon(
            30, today=date(2031, 12, 31)
        ), ["january"])
        self.assertEqual(pharmacy.expiring_soon(
            1, today=date(2032, 2, 28)
        ), ["leap"])

    def test_invalid_expiry_windows(self):
        for days in [-1, 1.5, "30", True, None]:
            with self.subTest(days=days):
                with self.assertRaises(ValueError):
                    pharmacy.expiring_soon(days, today=TODAY)

    def load_json(self, data):
        """Load a temporary inventory without leaving a runtime file."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stock.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return pharmacy.load_stock(path)

    def test_load_normalizes_and_merges_equivalent_names(self):
        original = pharmacy.stock
        self.assertTrue(self.load_json({
            "PARACETAMOL": {"units": 2, "expiry": "2030-07-15"},
            " Paracetamol ": {"units": 3, "expiry": "2030-07-15"},
        }))
        self.assertIs(pharmacy.stock, original)
        self.assertEqual(pharmacy.stock, {
            "paracetamol": {"units": 5, "expiry": "2030-07-15"}
        })

    def test_load_allows_zero_stock(self):
        self.assertTrue(self.load_json({
            "Empty": {"units": 0, "expiry": "2030-07-15"}
        }))
        self.assertEqual(pharmacy.stock["empty"]["units"], 0)

    def test_invalid_loaded_stock_is_rejected_atomically(self):
        self.add()
        before = deepcopy(pharmacy.stock)
        invalid = [[], None, {"bad": None}, {"bad": {}},
                   {"bad": {"units": -1, "expiry": "2030-07-15"}},
                   {"bad": {"units": True, "expiry": "2030-07-15"}},
                   {"bad": {"units": 1.5, "expiry": "2030-07-15"}},
                   {"bad": {"units": 1, "expiry": "not-a-date"}},
                   {" ": {"units": 1, "expiry": "2030-07-15"}},
                   {"same": {"units": 1, "expiry": "2030-07-15"},
                    "SAME": {"units": 2, "expiry": "2030-08-15"}}]
        for data in invalid:
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    self.load_json(data)
                self.assertEqual(pharmacy.stock, before)

    def test_setup_database_is_repeatable(self):
        pharmacy.setup_database()
        self.assertEqual(pharmacy.find_patient("Arjun"), [("P2", "none")])


if __name__ == "__main__":
    unittest.main()
