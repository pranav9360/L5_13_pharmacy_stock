# Baseline provenance

Captured before editing pharmacy_system.py from starter commit `55a462f`. SHA-256 of the committed source bytes: `7421caacc2c402adef9bf6823b8b3b7134cca4275bc4f83f4d635131517c70ff`.

The default program run supplies an empty line. The second run supplies `' OR 1=1 --` to demonstrate the SQL injection against the in-memory database. Both runs exit 0, despite the incorrect behavior visible in their outputs. Analyzer files contain combined stdout and stderr; command_results.json records exact command arguments, input, and exit codes. Flake8's baseline contains 15 findings.

Tool versions are recorded in ../tool_versions.txt. Program execution creates prescriptions.json, which is a runtime artifact and is ignored.
