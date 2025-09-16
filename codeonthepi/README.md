# Pi Control (Robot runtime)

This folder contains the code that runs on the Raspberry Pi.

## What it does
- Listens for UDP motor commands on `CTRL_PORT` (default 9000)
- Streams telemetry (IMU + TF-Luna LIDAR) via UDP to the PC on `TELEM_PORT` (default 9001)
- Telemetry destination host can be a static IPv4 or `.local` mDNS name. It auto-updates to the most recent controller IP that sends a command.

## Files
- `pi_control.py` — main service (motor control, telemetry)
- `movement.py` — legacy shim that launches `pi_control.py`
- `button_launcher.py` — start/stop `pi_control.py` with a tactile push button
- `config.json` — optional config (overridden via env vars or CLI)
- `CONNECTIONS.md` — wiring diagram for motors and sensors

## Configure PC host/IP
Choose one:
1. Edit `config.json` (pc_host can be e.g. `abbas-pc.local`)
2. Set env vars (for systemd): `PC_HOST=abbas-pc.local`
3. CLI: `python3 pi_control.py --pc-host abbas-pc.local`

## Run at boot
Use the systemd units in `../docs/PI_SETUP.md`.

## Dependencies (on Pi)
- `python3-rpi.gpio` (Raspberry Pi OS package)
- `python3-smbus` (I2C)
- `pyserial` (pip)
- `avahi-daemon` (for `.local` name resolution)

## Button usage
- Short press: start service
- Long press (>2s): stop service

## Telemetry formats
- IMU: `{type:"imu", ts, accel:{x,y,z}, gyro:{x,y,z}}`
- TF-Luna: `{type:"tfluna", ts, dist_mm, strength, temp_c}`
