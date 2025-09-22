# ESP32 (WROOM-32) Control Node

This folder contains a PlatformIO project for an ESP32-WROOM-32 acting as a drop-in control/telemetry node compatible with your existing UDP protocol.

Features:
- TB6612FNG dual H-bridge driving 2x N20 DC motors with quadrature encoders
- UDP control listener (port 9000) supporting commands: motor, motor4 (first two used), move_ticks
- UDP telemetry sender (port 9001) publishing encoders and optional IMU placeholder
- JSON messages compatible with your PC/Pi tooling (`advanced.py`, `telemetry_ui.py`)

## Networking layout (platform agnostic)

- Transport: UDP over IPv4
- Control plane:
  - PC (client) → Control Node (server) on port 9000
  - Messages: JSON dicts (UTF-8)
    - `{"type":"motor","left":int,-100..100,"right":int,-100..100,"seq":n,"ts":ms}`
    - `{"type":"motor4","m1":int,"m2":int,"m3":int,"m4":int,"seq":n,"ts":ms}` (ESP32 uses m1/m2)
    - `{"type":"move_ticks","left_ticks":int,"right_ticks":int,"left_speed":int,"right_speed":int,"seq":n,"ts":ms}`
- Telemetry plane:
  - Control Node (client) → PC (server) on port 9001
  - Messages:
    - `{"type":"encoders","ts":ms,"counts":{"m1":int,"m2":int,"m3":0,"m4":0}}`
    - Optional future: IMU/other sensors same schema as Pi
- Destination: Control node learns and targets the source IP of last valid control packet for telemetry (like `pi_control.py`).

This layout works across Pi, PC, and ESP32.

## Wiring (ESP32 WROOM-32 + TB6612FNG + N20 Encoders)

All ESP32 pins listed are GPIO numbers (not physical).

TB6612FNG:
- PWMA → GPIO 25 (PWM A)
- AIN1 → GPIO 26
- AIN2 → GPIO 27
- PWMB → GPIO 14 (PWM B)
- BIN1 → GPIO 12
- BIN2 → GPIO 13
- STBY → GPIO 33 (tie HIGH to enable, or drive via GPIO)
- VM → Battery motor supply (e.g., 6-12V per motor spec)
- VCC → 3.3V
- GND → Common ground with ESP32 and encoders

Encoders (one per N20; quadrature A/B):
- Motor1: ENC1_A → GPIO 34 (input-only), ENC1_B → GPIO 35 (input-only)
- Motor2: ENC2_A → GPIO 32, ENC2_B → GPIO 39 (input-only)

Notes:
- Use appropriate level shifting or ensure encoder outputs are 3.3V logic.
- Prefer input-only pins (34-39) for encoder channels to avoid accidental pull-ups/downs.
- Ensure a solid common ground among battery, TB6612, and ESP32.

## Build/Flash

- Requires PlatformIO
- Open this folder in VS Code with the PlatformIO extension, or use CLI `pio run -t upload -e esp32dev` after setting `WIFI_SSID`/`WIFI_PASS` in `src/config.h`.

