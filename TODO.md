# TODO — IHFC Prepsuite (updated)

High-priority items
- [ ] Validate odometry on a real run and adjust wheelbase parameter if needed (telemetry_ui derives wheelbase from PPD/PPC; measure physically if surprising drift occurs).
- [ ] Add unit tests for parser/CSV helpers in `measure_arena.py` and `path_planner.py`.
- [ ] Add a small end-to-end smoke test that runs the PPD/PPC calibrators in simulation (mock `advanced` telemetry).

Immediate fixes (recommended)
- [ ] Add a short script to dump current encoder and IMU telemetry to a CSV for offline analysis.
- [ ] Add a quick 'verify calibration' script that executes a 1 m forward move and 90° turn and prints errors.

Low-priority / Nice-to-have
- [ ] Add a documented API shim so external systems can query live telemetry over HTTP.
- [ ] Improve launcher GUI with icons and a one-click 'Run calibration' workflow.

Repository maintenance
- [ ] Add CONTRIBUTING.md describing coding style and testing guidelines.

How to help
- Run the calibration tools on your robot and commit updated `robot_calibration.json` when they provide improved values.
- Run `telemetry_ui.py` during a controlled forward run to collect encoder deltas and verify odometry.

Contact
- Repo maintainer: abbas-rz (owner)
