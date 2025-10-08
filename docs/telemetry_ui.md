# telemetry_ui.py — Live telemetry and arena visualiser

Purpose
-------
`telemetry_ui.py` is a Pygame-based dashboard that shows the arena image, planned path, current segment, and live sensor telemetry (IMU, LIDAR, encoders). It's used during a run to visually confirm the robot's progress and inspect sensor values.

Important notes
---------------
- The UI expects `path.csv` and `checkpoints_cm.csv` produced by `measure_arena.py`.
- The odometry implementation uses encoder deltas and a derived wheelbase (computed from calibration values). Ensure `robot_calibration.json` is up to date (pulses/cm and pulses/degree).
- Coordinate convention: origin = top-left of the arena image, +X right, +Y downwards, 0° = up (toward negative Y).

Controls
--------
- R: reload path and checkpoints.
- A: toggle auto-tracking of the current segment.
- [ / ]: manually step the current segment index when auto-tracking is off.
- Esc / Q: quit.

Troubleshooting
---------------
- If the robot's displayed position is wrong, verify `pulses_per_cm` and `pulses_per_degree` via the PPD/PPC calibrators.
- The wheelbase is derived from pulses-per-degree and pulses-per-cm; if you change calibration, restart the UI or press R to reload.
