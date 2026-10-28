"""Track pharmacy stock, patient allergies, and prescription dispensing.

Stock uses casefolded medicine names and one expiry date per medicine.
Quantities are whole units. Rejected dispensing never changes stored state.
"""

import json
import sqlite3
from datetime import date, datetime, timedelta

# Mutable application state is kept in place so callers can retain references.
conn = sqlite3.connect(":memory:")
stock = {}
prescriptions = []


def setup_database():
    """Create the sample patient database once, retaining existing patients."""
    with conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS patients "
            "(id TEXT PRIMARY KEY, name TEXT, allergy TEXT)"
        )
        conn.executemany(
            "INSERT OR IGNORE INTO patients VALUES (?, ?, ?)",
            [("P1", "Kavya", "penicillin"), ("P2", "Arjun", "none"),
             ("P3", "Meena", "ibuprofen")],
        )


def find_patient(name):
    """Return patient IDs and allergies matching a literal patient name."""
    query = "SELECT id, allergy FROM patients WHERE name = ?"
    return conn.execute(query, (name,)).fetchall()


def _medicine_name(drug):
    """Return the normalized medicine key or reject an invalid name."""
    if not isinstance(drug, str) or not drug.strip():
        raise ValueError("Medicine name must be a nonempty string")
    return drug.strip().casefold()


def _valid_quantity(units, minimum=1):
    """Accept only integer quantities, excluding booleans and fractions."""
    return (isinstance(units, int) and not isinstance(units, bool)
            and units >= minimum)


def _expiry_date(expiry):
    """Parse a strict ISO calendar date; reject malformed stock records."""
    if not isinstance(expiry, str):
        raise ValueError("Expiry must be a YYYY-MM-DD string")
    parsed = date.fromisoformat(expiry)
    if parsed.isoformat() != expiry:
        raise ValueError("Expiry must use YYYY-MM-DD format")
    return parsed


def add_stock(drug, units, expiry, batch_log=None):
    """Add positive whole units and return this caller's batch-log length.

    A medicine with units remaining cannot receive a different expiry date:
    the simple stock format cannot safely represent multiple dated batches.
    """
    drug = _medicine_name(drug)
    if not _valid_quantity(units):
        raise ValueError("Stock additions must be positive whole units")
    _expiry_date(expiry)
    existing = stock.get(drug, {})
    if existing.get("units", 0) and existing["expiry"] != expiry:
        raise ValueError("Existing units must keep their original expiry date")
    stock[drug] = {"units": existing.get("units", 0) + units, "expiry": expiry}
    if batch_log is None:
        batch_log = []
    batch_log.append((drug, units))
    return len(batch_log)


def dispense(patient_name, drug, units, *, today=None):
    """Dispense only valid, available, unexpired, non-allergenic medicine.

    Return False for rejected requests without changing stock or records.
    Expiry dates are inclusive: medicine is usable through its expiry day.
    """
    if not _valid_quantity(units):
        return False
    try:
        drug = _medicine_name(drug)
    except ValueError:
        return False
    patients = find_patient(patient_name)
    if not patients:
        return False
    patient_id, allergy = patients[0]
    allergies = {name.strip().casefold() for name in allergy.split(",")}
    if drug in allergies:
        print("Allergy warning for", patient_name)
        return False
    medicine = stock.get(drug)
    if (medicine is None or units > medicine["units"]
            or _expiry_date(medicine["expiry"]) < (today or date.today())):
        return False
    medicine["units"] -= units
    prescriptions.append({
        "patient": patient_id, "drug": drug, "units": units,
        "time": datetime.now().isoformat(timespec="seconds"),
    })
    return True


def expiring_soon(days=30, *, today=None):
    """List stocked medicines expiring from today through days ahead inclusive.

    Exclude expired medicines and empty stock. Compare calendar dates to
    avoid rounding away part of a day. Zero days means today's expiry only.
    """
    if not _valid_quantity(days, minimum=0):
        raise ValueError("Days must be a nonnegative whole number")
    reference = today or date.today()
    return [
        drug for drug, medicine in stock.items()
        if medicine["units"] > 0
        and 0 <= (_expiry_date(medicine["expiry"]) - reference).days <= days
    ]


def export_prescriptions(file="prescriptions.json"):
    """Export prescriptions as UTF-8 JSON and always close the output file."""
    with open(file, "w", encoding="utf-8") as output_file:
        json.dump(prescriptions, output_file)


def load_stock(file="stock.json"):
    """Atomically load validated stock, normalizing medicine names.

    Return False only if the file is absent. Propagate unreadable files,
    invalid JSON, and invalid stock data while preserving existing stock.
    """
    try:
        with open(file, encoding="utf-8") as input_file:
            loaded_stock = json.load(input_file)
    except FileNotFoundError:
        return False
    if not isinstance(loaded_stock, dict):
        raise ValueError("Stock must be a JSON object")
    validated = {}
    for name, medicine in loaded_stock.items():
        drug = _medicine_name(name)
        if (not isinstance(medicine, dict)
                or not _valid_quantity(medicine.get("units"), minimum=0)):
            raise ValueError("Stored units must be nonnegative whole numbers")
        _expiry_date(medicine.get("expiry"))
        previous = validated.get(drug)
        if previous and previous["expiry"] != medicine["expiry"]:
            raise ValueError(
                "Duplicate medicine names have different expiries"
            )
        validated[drug] = {
            "units": (medicine["units"]
                      + (previous["units"] if previous else 0)),
            "expiry": medicine["expiry"],
        }
    stock.clear()
    stock.update(validated)
    return True


def print_stock():
    """Print the normalized medicine stock and its expiry dates."""
    print("Pharmacy Stock")
    for drug, medicine in stock.items():
        print(drug, "->", medicine["units"],
              "units, expires", medicine["expiry"])


def main():
    """Run a dated demonstration and allow a literal patient-name lookup."""
    setup_database()
    load_stock()
    today = date.today()
    # Seed only absent medicines so a valid loaded inventory is respected.
    for drug, units, days in [
            ("Paracetamol", 100, 120), ("Amoxicillin", 20, -1),
            ("Penicillin", 50, 60), ("Ibuprofen", 15, 15)]:
        if _medicine_name(drug) not in stock:
            add_stock(drug, units, (today + timedelta(days=days)).isoformat())
    print("Arjun gets Amoxicillin:", dispense("Arjun", "Amoxicillin", 30))
    print("Kavya gets Penicillin:", dispense("Kavya", "Penicillin", 10))
    print("Meena gets ibuprofen:", dispense("Meena", "ibuprofen", 2))
    print("Unknown patient:", dispense("Ghost", "Paracetamol", 5))
    print("Arjun gets Paracetamol:", dispense("Arjun", "Paracetamol", 5))
    name = input("Patient name to look up (Enter for Arjun): ") or "Arjun"
    print("Lookup result:", find_patient(name))
    print("Expiring within 30 days:", expiring_soon())
    export_prescriptions()
    print_stock()


if __name__ == "__main__":
    try:
        main()
    finally:
        conn.close()
