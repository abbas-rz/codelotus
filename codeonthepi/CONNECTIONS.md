# Hardware Connections (Raspberry Pi)

All BCM pin numbers (not physical pin index).

## Motor Driver (L298N)
- ENA: GPIO12 (Pin 32)
- IN1: GPIO20 (Pin 38)
- IN2: GPIO21 (Pin 40)
- ENB: GPIO13 (Pin 33)
- IN3: GPIO19 (Pin 35)
- IN4: GPIO26 (Pin 37)
- Power: 12V battery to L298N, 5V logic from Pi NOT recommended through L298N 5V out; prefer external 5V regulator for Pi.
- Grounds: Common ground between Pi, L298N, sensors, battery.

## TF-Luna LIDAR (UART)
- UART TX (TF-Luna) -> Pi GPIO15 (RXD0, Pin 10)
- UART RX (TF-Luna) -> Pi GPIO14 (TXD0, Pin 8) (often not required if only receiving)
- GND -> Pi GND
- VCC -> 5V (per your module, many TF-Luna versions accept 5V)
- Serial device: /dev/serial0 (enable UART; disable console on serial)

## MPU6050 IMU (I2C)
- SDA -> GPIO2 (SDA1, Pin 3)
- SCL -> GPIO3 (SCL1, Pin 5)
- VCC -> 3.3V (or 5V if module supports it with level shifting; safer is 3.3V)
- GND -> GND
- I2C bus: 1, Address: 0x68 (default)

## Tactile Button (Start/Stop)
- BUTTON -> GPIO17 (Pin 11)
- Other side of button -> GND
- Internal pull-up used in software

## Network
- Control and telemetry over UDP
- PC host can be a static IP (e.g., 192.168.1.113) or mDNS name (e.g., abbas-pc.local)
- Ensure Pi can resolve .local names (avahi-daemon)
