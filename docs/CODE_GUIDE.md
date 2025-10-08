# IHFC Prepsuite — Code Guide (simple explanation)

This guide explains the project structure, what each major script does, and how the pieces interact. It's written for humans who want a clear mental model — no deep robotics background required.

Project purpose in one sentence
--------------------------------
Tools to plan, measure and run a small two-wheeled robot inside a known arena. You can draw paths on the arena image, calibrate wheel encoders (distance and rotation), run those paths on the robot, and visualise live telemetry.

How the system is organised (big picture)
-----------------------------------------
- `measure_arena.py` — interactive map editor. Draw checkpoints over `arena.png` and export `path.csv` (turns + distances) and `checkpoints_cm.csv` (actual positions in cm).
- `measure_ppc_encoder_only.py` — pulses-per-centimetre (PPC) calibrator: drives a known distance and asks you to measure it so it can compute pulses/cm.
- `measure_ppd_encoder_only.py` — pulses-per-degree (PPD) calibrator: spins the robot and refines pulses/degree so rotation commands map to real-world angles.
- `straight_line_calibrator.py` — interactive straight-line balancing tool that adjusts motor factors until the robot goes straight.
- `advanced.py` — core control library: sends commands to the ESP32 robot (motors, servos), listens to telemetry (IMU, encoders, LIDAR), and exposes helper functions for other scripts.
- `move_control.py`, `run_track.py` — higher level followers that execute the exported path using the calibrations.
- `telemetry_ui.py` — live dashboard showing arena, planned path, and estimated robot pose using encoder-based odometry plus IMU telemetry.
- `fruit_ui.py` — simple arena overlay to mark fruit positions and export color-tagged CSVs / JSON mapping.
- `launcher_gui.py` — a small Tkinter UI to launch the above tools and view/update calibration values quickly.

How data flows when you plan and run a path
-------------------------------------------
1. Use `measure_arena.py` to create checkpoints and export `path.csv` and `checkpoints_cm.csv`.
2. Place the robot at the start point in the arena. Ensure the robot's `robot_calibration.json` has reasonable PPC and PPD values (use the calibrators if not).
3. Use the `launcher_gui.py` to open `telemetry_ui.py` and `run_track.py`, or directly run `run_track.py` to execute the path.
4. `run_track.py` issues the movement primitives (turns and forward moves) via the helpers in `advanced.py`. It prefers `move_by_ticks()` (hardware encoder control) for accuracy.
5. `telemetry_ui.py` listens for encoder and IMU telemetry from the ESP32 and displays estimated pose; it uses PPR/PPC/PPD to convert encoder counts to cm/deg.

Key concepts you should know (simple)
------------------------------------
- Pulses-per-centimeter (PPC): how many encoder counts equal 1 cm of wheel travel. Used to turn distances (cm) into encoder ticks.
- Pulses-per-degree (PPD): how many encoder counts equal 1° of robot rotation when turning in place. Used to turn angles into encoder ticks.
- Motor factors: small left/right scaling multipliers that compensate mechanical differences between motors/wheels so the robot drives straight.
- `move_by_ticks`: a command sent to the robot's firmware telling it to run motors until specified encoder deltas are reached. This is preferred to open-loop PWM for accuracy.

Quick start: calibrate & run (minimum steps)
-------------------------------------------
1. Ensure the ESP32 is powered and reachable by the PC (via AP or station mode).
2. Run the PPD calibrator: `python measure_ppd_encoder_only.py` and follow the prompts to refine rotation.
3. Run the PPC calibrator: `python measure_ppc_encoder_only.py` and measure a forward run.
4. Use `launcher_gui.py` → Launch Telemetry UI and confirm the robot's reported encoder deltas look sensible when you nudge it manually.
5. Create or load a path with `measure_arena.py` and run it with `run_track.py`.

How to verify odometry quickly (sanity checks)
---------------------------------------------
- Place the robot in a known spot and command a 100 cm forward move. Measure the actual displacement and compare to what `telemetry_ui.py` reports.
- Command a 90° turn, measure the heading change (visually or with a protractor), compare to telemetry/encoders.
- If discrepancy persists, re-run PPD/PPC calibrators and/or adjust motor factors with the straight-line calibrator.

Where to look for calibration values
-----------------------------------
- `robot_calibration.json` in the repository root stores `pulses_per_cm`, `pulses_per_degree`, and motor factors. Tools read and write this file via `calibration_config.py`.

Developer notes (quick)
-----------------------
- Most movement code expects the same coordinate/heading convention: origin at top-left, +X=right, +Y=down, 0° = up.
- `advanced.py` performs socket-based RPC-style commands (UDP) and spawns a telemetry listener thread that populates module-level variables other scripts read.
- When adding features, prefer to reuse `move_by_ticks()` for movement to keep behaviour consistent between tuning and path execution.

Where to change physical robot constants
--------------------------------------
- `esp32/src/config.h` — firmware constants like wheel diameter and wheelbase (mm). If you change these, reflash the ESP32 firmware.
- `robot_calibration.json` — runtime calibration used by Python tools. Update via calibrators or by editing and saving.

If something breaks (quick troubleshooting checklist)
--------------------------------------------------
1. No telemetry: check WiFi/AP connectivity and that the ESP32 is broadcasting alive messages. `advanced.py` will auto-update the IP if an `alive` packet is received.
2. Robot drives in circles: run the straight-line calibrator and ensure motor factors are saved.
3. Position displayed incorrectly: re-run PPC/PPD calibrators and verify `robot_calibration.json` values.

Further reading
---------------
- See `docs/measure_ppc.md` and `docs/measure_ppd.md` for detailed calibrator instructions.
- Read `docs/telemetry_ui.md` for odometry caveats and troubleshooting.

Made changes (oct 2025)
- Added a launcher GUI shortcut for the PPD/PPC calibrators and a README-style CODE_GUIDE to make onboarding easier.
# IHFC Prep Suite Code Guide

This document provides a walkthrough of the repository layout, the primary runtime flows, and how major modules interact across the desktop control tools, the Raspberry Pi service, and the ESP32 firmware. Use it as a reference when modifying behavior or onboarding new contributors.

---

## Top-Level Architecture

The project is split across three cooperating execution environments:

1. **Desktop control & planning tools** (Python, runs on Windows): planners, UIs, and high-level robot commands.
2. **Raspberry Pi service** (`codeonthepi/`, Python): optional middle-tier that exposes identical UDP control/telemetry semantics as the ESP32 for backward compatibility.
3. **ESP32 firmware** (`esp32/`, PlatformIO / Arduino): embedded controller that directly drives the motors and publishes encoder telemetry.

Communication between components is UDP-based and JSON encoded:

- Desktop tools send control packets to UDP port **9000** on the robot controller (Pi or ESP32).
- Telemetry (encoders, IMU, LIDAR, alive messages) is streamed back to UDP port **9001** on the desktop.
- Control packets include sequence numbers (`seq`) and are acknowledged by the controller.

---

## Key Python Modules (Desktop)

### `advanced.py`
Centralized robot control helper used by most desktop scripts.

- Initializes UDP sockets and spawns the telemetry thread (`start_telemetry_thread`).
- Provides motor helpers (`send_motor`, `send_motor_differential`, `send_motor4`) that automatically clamp speeds and apply left/right scaling factors.
- Encodes relative motion commands through `move_by_ticks`, attaching additional metadata (`target`, `speeds`, `direction`) for compatibility with different firmware generations.
- Maintains global telemetry state: latest encoder counts, IMU data, LIDAR distances, rotation integration, and gear selection.
- Offers calibration facilities: gyro bias loading (`load_gyro_calibration`) and trapezoidal integration to track relative rotation (`integrate_gyro_rotation`).
- Exposes utility functions consumed elsewhere: `is_encoder_data_available`, `wait_for_encoder_data`, `get_latest_encoders`, `reset_rotation`, etc.

### `move_control.py`
Encoder-only movement controller used for scripted paths and interactive control.

- Defines `RobotController` with configurable tolerances, speeds, and timeouts.
- `turn_to_angle`: converts desired rotation to encoder ticks, issues a `move_by_ticks` command, and monitors progress via `get_relative_position` until tolerance criteria or timeout.
- `move_distance`: drives both wheels with signed speeds while monitoring encoder deltas; ensures forward and backward motion obey distance tolerance.
- High-level orchestration (`execute_command`) sequentially performs turn then move, stopping the motors and reporting success/failure.
- Provides both interactive CLI (`interactive_mode`) and argument-driven (`command_line_mode`) entry points.
- Contains correction utilities (`correct_turn_error`) for iterative turn refinement when residual error exceeds tolerance.

### Planning & UI tools

| File | Purpose |
| ---- | ------- |
| `measure_arena.py` | Pygame-CE measurement tool for drawing checkpoints over `arena.png`; exports `path.csv` (turn/advance pairs) and `checkpoints_cm.csv` (absolute coordinates). |
| `path_planner.py` | Grid-based planner that routes around obstacles using A*; useful for generating safe trajectories when fruit positions are known. |
| `fruit_picker.py` | Interactive planner for fruit harvesting order; generates track files consumed by `fruit_mover.py`. |
| `fruit_selector.py` | Richer UI for selecting fruits, seeds, and plots with robot path previews. |
| `fruit_mover.py` / `run_with_fruits.py` | Execute fruit harvesting tracks by streaming angles/distances into `RobotController`. |
| `telemetry_ui.py` | Live visualization of arena progress, IMU, LIDAR, and encoder-derived odometry; subscribes to telemetry via `advanced.py`. |
| `simple_move_test.py`, `test_turn_precision.py` | Diagnostics for verifying encoder-based turning/movement in isolation. |
| `quick_esp32_check.py` | Connectivity diagnostic: verifies Wi-Fi association, pings ESP32 AP, listens for telemetry.

Many of these tools rely on CSV assets (`path.csv`, `checkpoints_cm.csv`, `fruitpos.csv`, etc.) generated at runtime or supplied from rulebook measurements.

### Robot Support Scripts

- `calibrate_turn.py`, `measure_ppd.py`, `measure_ppd_encoder_only.py`: utilities to tune pulses-per-degree and pulses-per-distance constants.
- `diagnose_esp32.py`, `test_esp32_ap.py`, `test_esp32_network.py`: scripts to validate network and telemetry flows.
- `move_robot.bat`, `add_firewall_rules.bat`: Windows helpers to launch control loops and configure UDP firewall exceptions.

---

## `codeonthepi/` (Raspberry Pi Service)

Although the current setup favors direct ESP32 control, `codeonthepi/pi_control.py` mirrors the same UDP API:

- Chooses between TB6612 and legacy L298N motor drivers.
- Streams LIDAR (TF-Luna), IMU (MPU6050), and encoder telemetry to the desktop.
- Accepts `motor`, `motor4`, and `move_ticks` commands, implementing blocking encoder-driven moves when encoders are present.
- `telemetry_sender` spawns threads for IMU, LIDAR, and encoder loops, automatically updating the destination IP to the last controller.
- Includes `Encoders` helper that integrates with TB6612 state to infer direction from PWM commands.
- Configurable via `codeonthepi/config.json`, environment variables, or CLI arguments; `docs/PI_SETUP.md` describes systemd setup.

Legacy wrappers (`codeonthepi/movement.py`) simply point to `pi_control.py` for backwards compatibility.

---

## `esp32/` PlatformIO Firmware

The embedded firmware implements the same UDP protocol on an ESP32-WROOM-32:

- `src/main.cpp` handles Wi-Fi (AP or STA modes), AsyncUDP server, and motor/encoder control.
- `config.h` (per environment) defines Wi-Fi credentials, hostnames, IP settings, motor pin mappings, and telemetry intervals.
- Control flow:
  1. On boot, configure Wi-Fi and optionally mDNS.
  2. Initialize TB6612 driver pins, attach quadrature encoders using `ESP32Encoder`.
  3. Listen for UDP packets on `CTRL_PORT` (default 9000). Supported packet types mirror `advanced.py` expectations.
  4. Periodically send encoder telemetry (`sendEncoders`) and `alive` status updates to port 9001, targeting the last controlling IP and broadcast address.
  5. `move_ticks` commands run a blocking loop until absolute tick targets are met or a timeout occurs, then stop motors and ACK the request.

This arrangement lets the Windows host talk directly to the ESP32 without the Pi, while retaining compatibility if the Pi service is used instead.

---

## Telemetry & Control Data Structures

### Control Messages (sent from desktop)

```json
{
  "type": "motor",
  "left": -100..100,
  "right": -100..100,
  "seq": <int>,
  "ts": <ms>
}
```

```json
{
  "type": "move_ticks",
  "left_ticks": <int>,          // relative ticks (+/-)
  "right_ticks": <int>,
  "left_speed": <int>,          // signed, factors applied in advanced.py
  "right_speed": <int>,
  "target": [<abs left>, <abs right>],
  "speeds": [<left>, <right>],
  "direction": [<-1|0|1>, <-1|0|1>],
  "seq": <int>,
  "ts": <ms>
}
```

### Telemetry Messages (controller → desktop)

| Type | Payload |
| ---- | ------- |
| `encoders` | `{ "counts": { "m1": <int>, "m2": <int>, "m3": <int>, "m4": <int> }, "ts": <ms> }` |
| `imu` | `{ "accel": {...}, "gyro": {...}, "heading": <float>, "mag": {...}, "temp_c": <float>, "ts": <ms> }` |
| `tfluna` | `{ "dist_mm": <int>, "strength": <int>, "temp_c": <float>, "ts": <ms> }` |
| `alive` | `{ "device": <str>, "ip": <str>, "mode": "AP"|"STA", "ts": <ms> }` |

`advanced.py` consumes all of these, updating global state accessible to the rest of the desktop scripts.

---

## Typical Workflows

### Plan → Execute Path

1. **Design path** using `measure_arena.py` or `path_planner.py`, generating `path.csv` and `checkpoints_cm.csv`.
2. **Connect** to the ESP32 Wi-Fi or ensure the Pi service is running.
3. **Start telemetry** by importing or running `advanced.py`; call `init_bot_control()`.
4. **Run controller** (`move_control.py` or `move_control_pure_pursuit.py`) to execute sequential turn-and-move commands from the CSV.
5. **Monitor progress** in real time with `telemetry_ui.py`, which highlights segments and displays sensor data.

### Fruit Harvesting

1. Plan fruit order with `fruit_picker.py` or `fruit_selector.py`, exporting `fruit_track.txt` (angle/distance pairs).
2. Run `fruit_mover.py` or `run_with_fruits.py`, which streams those commands through `RobotController`.
3. Use telemetry UI to verify path adherence and sensor status.

### Diagnostics & Calibration

- `quick_esp32_check.py`: ensures UDP telemetry reaches the PC.
- `debug_encoders.py`: prints raw encoder counts over time.
- `test_turn_precision.py`: sweeps rotation commands, reporting error statistics so `PULSES_PER_DEGREE` and `MOTOR_FACTOR` can be tuned.
- `measure_ppd.py` / `measure_ppd_encoder_only.py`: derive pulses per distance.

---

## Configuration Touchpoints

- **Network**: adjust `RPI_IP`, `FALLBACK_IPS`, ports in `advanced.py`. For ESP32, edit `esp32/src/config.h` (`USE_ACCESS_POINT`, SSID/PASS, hostnames, static IPs). Pi service uses `codeonthepi/config.json` or environment vars.
- **Motor calibration**: tweak `MOTOR_FACTOR_LEFT/RIGHT`, `MOTOR_MAX_SPEED`, and gear ratios in `advanced.py`; `move_control.py` exposes runtime configuration via interactive commands.
- **Physical constants**: `RobotController` stores `PULSES_PER_CM`, `PULSES_PER_DEGREE` derived from encoder specs and wheel geometry; update when hardware changes.
- **Arena assets**: `arena.png`, `path.csv`, `checkpoints_cm.csv`, `fruit_config.json`, and color CSVs provide visual overlays and planning data.

---

## Extending the System

- To add new telemetry: update ESP32 firmware (or Pi service) to include new JSON fields. Extend `advanced.telem_loop` to parse and expose them, then modify UIs to display the data.
- To support alternate motor drivers: abstract motor commands in the controller firmware (ESP32) and align scaling factors in `advanced.py`.
- For autonomous path following (pure pursuit), build on `move_control_pure_pursuit.py` or replace the turn-then-go logic inside `RobotController`.
- When introducing additional planners or UIs, re-use the shared CSV formats and `RobotController` interface to maintain compatibility.

---

## Related Documentation

- `README.md`: quick start and usage of the primary tools.
- `docs/PI_SETUP.md`: Raspberry Pi provisioning, systemd services, and troubleshooting.
- `esp32/README.md`: overview of the ESP32 PlatformIO project and wiring.
- Rulebook PDF (`Final_Rulebook_26_09.pdf`): authoritative field dimensions and scoring requirements.

---

## Suggested Next Steps

- Consider consolidating calibration constants into a configuration file to avoid duplicated numbers across modules.
- Expand automated tests (e.g., mocked telemetry feeds) to validate controller logic without hardware.
- Add logging abstraction so critical events (timeouts, corrections) can be persisted for debugging.

Feel free to extend this guide as the codebase evolves.
