# Lab 5: Static Code Analysis — Pharmacy Prescription & Stock Tracker

**Your file:** `pharmacy_system.py`

Follow the lab handout for the full instructions.

## About the program

A stock and prescription tracker for a small pharmacy. It records medicine stock and expiry dates, looks up patients and their allergies in a small database, dispenses prescriptions and exports them to `prescriptions.json`.

The code works, but only just. It has quality, style and security problems of the kind Pylint, Flake8 and Bandit are built to find.

## What to do

1. **Run it first** and read the output carefully:
   ```bash
   python pharmacy_system.py
   ```
   It asks one question. Press Enter to use the default, then try a few inputs of your own. Not every problem in this file is something a tool will flag, so pay attention to output that looks wrong.

2. **Install the tools:**
   ```bash
   pip install pylint bandit flake8
   ```

3. **Run the analysis** and save the reports:
   ```bash
   pylint pharmacy_system.py > pylint_report.txt
   bandit -r pharmacy_system.py > bandit_report.txt
   flake8 pharmacy_system.py > flake8_report.txt
   ```

4. **Document the issues** in `issues.md` using this table (at least 4 rows, high and medium severity first):

   | Issue | Type | Line(s) | Description | Fix Approach |
   |-------|------|---------|-------------|--------------|
   | ... | ... | ... | ... | ... |

5. **Fix the code.** Fix at least 4 of the issues you documented, then rerun all three tools to confirm they are gone. Repeat until you are satisfied. The program should still do its job when you are done.

6. **Reflection exemption.** The instructor notice supplied for this lab says reflection questions do not need to be submitted. `reflection.md` records the exemption; no answers are required.

## Deliverables

1. `pharmacy_system.py`: your cleaned version, with at least 4 issues fixed.
2. `issues.md`: the completed issue table.
3. `reflection.md`: the supplied instructor exemption from reflection submission.

**Target:** aim for a Pylint score above 9.5 on your final file. A perfect 10.00/10 is very good.

Be ready to explain the bugs you found and how you fixed them. You may be called on to present.


## Completed analysis and validation

The starter was inspected on `main` at `55a462f` with no existing user changes.
GitHub confirmed that `origin`,
`https://github.com/pranav9360/L5_13_pharmacy_stock.git`, is owned by the
authenticated account `pranav9360` and is a fork of
`SETAPESU26/L5_13_pharmacy_stock`. The instructor repository remains `upstream`.
No push was performed; review the three local lab commits before publishing.

The measured before/after results are:

| Check | Before | After |
|-------|--------|-------|
| Pylint | 6.90/10, exit 28 | 10.00/10, exit 0 |
| Bandit | 2 findings: 1 medium B608, 1 low B110; exit 1 | 0 findings, exit 0 |
| Flake8 | 15 findings, exit 1 | 0 findings, exit 0 |
| Program, default input | Exit 0, incorrect dispensing/expiry behavior | Exit 0, correct rejection and successful dispensing demonstrated |
| Program, SQL injection input | Returns all three patients | Returns an empty result |
| Regression suite | No starter tests | 34 tests passed |

Raw tool output, program output, and exit-code manifests are in
`reports/before/` and `reports/after/`. The final test output is
`reports/after/tests_report.txt`. The empty final Flake8 report is intentional:
Flake8 emits no output on success, and its recorded exit code is zero.
`reports/tool_versions.txt` records all installed package versions.
Before reports are preserved verbatim, including analyzer-emitted whitespace.
`issues.md` links each finding to the original source lines and distinguishes
tool reports from manually identified bugs.

### Reproduce on Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r reports/tool_versions.txt
.\.venv\Scripts\python.exe pharmacy_system.py
.\.venv\Scripts\python.exe -m pylint pharmacy_system.py
.\.venv\Scripts\python.exe -m bandit -r pharmacy_system.py
.\.venv\Scripts\python.exe -m flake8 pharmacy_system.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Press Enter for the default patient lookup. The main program demonstrates
rejected over-dispensing, allergies and an unknown patient, then successfully
dispenses Paracetamol to Arjun. Sample expiry dates are relative to the run
date so the demonstration remains usable later. It seeds only medicines
absent from an optional `stock.json`. Exported `prescriptions.json` is an
ignored runtime artifact. Importing the module does not run the demonstration.

### Correctness contracts and limits

- Medicine names are stripped and casefolded consistently. Allergy checks
  match exact medicine names in the sample database's comma-separated field.
  Drug-family relationships are not represented in this simple lab model.
- Additions and dispensing accept positive whole integer units; booleans
  are rejected. Loaded inventories may contain zero units. Rejected requests
  do not change stock or prescription history.
- Medicine can be dispensed through its expiry date. Upcoming expiry lists
  include today through the requested number of days, both inclusive, and
  exclude expired and empty stock. Tests use fixed dates, including leap day.
- The existing inventory schema stores one expiry per medicine. Different
  dated batches cannot be combined while units remain; an explicit error
  prevents an incoming batch from concealing old stock's expiry.
- Loading is validated before any stock replacement. Missing stock files
  are optional; malformed JSON, invalid records, and permission errors are
  reported as exceptions. SQLite errors are not silently swallowed.
- The sample patient database is still in memory, as in the starter. This is
  a single-process teaching program with no persistent patient management or
  concurrent transaction model. The regression suite covers its intended
  contracts; clean static analysis does not establish production readiness.
- No blanket Pylint/Flake8 disables, Bandit `nosec` annotations, or relaxed
  analyzer configurations were introduced.
