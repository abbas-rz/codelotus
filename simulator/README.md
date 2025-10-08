# Robot Simulator

A complete virtual simulation environment for the IHFC robot that allows testing path planning, calibration, and control algorithms without hardware.

## What it does

- **Virtual Robot**: Simulates 2-wheel differential drive physics with configurable motor factors, wheel parameters, and realistic encoder behavior.
- **Mock ESP32**: Emulates UDP telemetry (encoders, IMU, LIDAR) and control socket that advanced.py expects.
- **Visual Simulator**: Pygame UI showing the robot moving in the arena with real-time telemetry and path visualization.
- **Testing**: Run calibration routines and path execution in a safe, repeatable environment.

## Architecture

```
simulator/
├── virtual_robot.py      # Physics model: differential drive, encoders, odometry
├── mock_esp32.py          # UDP server emulating ESP32 telemetry/control
├── sim_advanced.py        # Drop-in replacement for advanced.py using simulator
├── simulator_ui.py        # Pygame visualization of robot + arena
├── test_calibration.py    # Demo: run PPD/PPC calibrators in simulation
└── test_path_execution.py # Demo: execute paths in simulation
```

## Quick Start

### 1. Launch the simulator

```powershell
python .\simulator\simulator_ui.py
```

This opens a window showing the arena with a virtual robot. The simulator automatically starts the mock ESP32 server.

### 2. Run calibration in simulation

```powershell
# Test PPD calibrator with virtual robot
python .\simulator\test_calibration.py --mode ppd

# Test PPC calibrator
python .\simulator\test_calibration.py --mode ppc
```

### 3. Execute a path in simulation

```powershell
# Use existing path.csv or create one with measure_arena.py first
python .\simulator\test_path_execution.py
```

The simulator UI will show the robot following the path in real-time.

## How it works

1. **mock_esp32.py** starts UDP servers on ports 9000 (control) and 9001 (telemetry), same as the real ESP32.
2. **virtual_robot.py** maintains robot state (position, heading, encoder counts) and simulates physics when motor commands arrive.
3. **sim_advanced.py** is imported instead of `advanced.py` by test scripts — it connects to the mock ESP32 locally.
4. **simulator_ui.py** visualizes everything and can be left running while you test other tools.

## Configuration

Edit `virtual_robot.py` constants to match your robot:
- `WHEEL_DIAMETER_CM`: wheel diameter
- `WHEELBASE_CM`: distance between left and right wheels
- `PPR`: pulses per rotation (encoder resolution × gear ratio)
- `MOTOR_FACTOR_LEFT`, `MOTOR_FACTOR_RIGHT`: simulate motor imbalance

## Testing real tools against simulation

Most tools can work with the simulator by ensuring:
1. The mock ESP32 is running (`simulator_ui.py` starts it automatically).
2. Replace `from advanced import ...` with `from simulator.sim_advanced import ...` in test scripts.
3. The simulator uses `192.168.4.1` (AP mode default) so tools connect automatically.

## Notes

- The simulator runs at 50 Hz physics update (configurable in `virtual_robot.py`).
- Encoder noise and motor response delays can be added for realism (see TODOs in code).
- The visual UI supports keyboard controls: W/A/S/D for manual drive, R to reset, Q to quit.

## Next Steps

- Add LIDAR distance simulation using arena obstacles.
- Add IMU gyro/accel simulation with drift.
- Record and replay simulation runs for regression testing.

Created: October 2025
