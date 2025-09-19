# Hardware Connections (Raspberry Pi)

All BCM pin numbers (not physical pin index).

## Motor Drivers

### TB6612FNG (dual, 2 chips for 4 motors)
- STBY: GPIO23 (if used)
- Chip 1:
	- Channel A (m1): PWM=GPIO12, IN1=GPIO20, IN2=GPIO21
	- Channel B (m2): PWM=GPIO13, IN1=GPIO19, IN2=GPIO26
- Chip 2:
	- Channel A (m3): PWM=GPIO18, IN1=GPIO24, IN2=GPIO25
	- Channel B (m4): PWM=GPIO16, IN1=GPIO5,  IN2=GPIO6

Motor order used by code: m1=1A, m2=1B, m3=2A, m4=2B. Left side: m1+m3, Right side: m2+m4.


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
- Other side of button -> GND
- Internal pull-up used in software
## Encoders (N20, single-channel)
- m1 A: GPIO4
- m2 A: GPIO17
- m3 A: GPIO27
- m4 A: GPIO22

Note: This is single-channel counting; direction inferred from last motor command.

## SG90 Servo (for LIDAR sweep)
- Signal: GPIO7 (Pin 26) — 50Hz PWM

## 28BYJ-48 Stepper
- IN1..IN4: GPIO14, GPIO15, GPIO8, GPIO9 (half-step sequence)
- BUTTON -> GPIO17 (Pin 11)

### Rotational Mechanism (rotationalmech.py)
- Driver: ULN2003 board with 28BYJ-48 stepper
- GPIO (BCM):
	- IN1 -> GPIO14
	- IN2 -> GPIO15
	- IN3 -> GPIO8
	- IN4 -> GPIO9
- Power: 5V to ULN2003 board VIN; GND common with Pi
- Usage: run `rotationalmech.py` on the Pi to step in 53° increments every 5s. Adjust pins and increment in the file if needed.


## Network
- Control and telemetry over UDP
- PC host can be a static IP (e.g., 192.168.1.113) or mDNS name (e.g., abbas-pc.local)
- Ensure Pi can resolve .local names (avahi-daemon)
