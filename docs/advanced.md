# advanced.py — Core robot control library

Overview
--------
`advanced.py` contains the core networking, motor control, telemetry and primitive navigation helpers used by the rest of the tools. It implements a simple UDP control channel for sending motor and actuator commands to the ESP32 robot, and a telemetry listener for receiving IMU, encoder and LIDAR messages.

Key features
------------
- UDP-based control socket for motor, servo and stepper commands.
- `move_by_ticks()` helper: hardware-accelerated encoder-targeted movements.
- Motor factor scaling with `set_motor_factors()` to compensate left/right differences.
- Telemetry thread (`start_telemetry_thread`) that populates shared state: IMU, encoders, LIDAR.
- Utilities for gyro integration, encoder availability checks and a manual keyboard-driven control loop.

Public API (important functions)
--------------------------------
- `init_bot_control(verbose_telemetry=True)` — initialize sockets and telemetry thread.
- `cleanup()` — stop motors and close sockets.
- `send_motor(left, right)` — send a paired left/right motor PWM command.
- `move_by_ticks(left_ticks, right_ticks, left_speed, right_speed)` — command the robot to move until encoder targets are reached (preferred for accuracy).
- `set_motor_factors(left, right)` — update per-side motor scaling factors used by all motor helpers.
- Telemetry getters: `get_latest_encoders()`, `get_full_imu_data()`, `get_rotation_degrees()`, `get_current_distance()`.

Calibration
-----------
Calibration values (pulses per cm / degree and motor factors) are loaded from `robot_calibration.json` via `calibration_config.py` and applied at module import. Call `set_motor_factors()` to change them at runtime and `save_*` helpers in `calibration_config.py` to persist changes.

Notes & Best Practices
----------------------
- Prefer `move_by_ticks()` for deterministic motion; `send_motor()` is lower-level and open-loop.
- `start_telemetry_thread()` must be called before expecting encoder/IMU data to be available.
- The telemetry listener auto-updates `RPI_IP` when an `alive` packet arrives, simplifying discovery.

Example
-------
Start telemetry and do a short forward move:

```powershell
python -c "from advanced import init_bot_control, move_forward, cleanup; init_bot_control(); move_forward(40); import time; time.sleep(0.5); cleanup()"
```
