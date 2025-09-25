#pragma once

// Configure WiFi credentials
#define WIFI_SSID "Abbashotspot"
#define WIFI_PASS "qwertyuiop"

// Ports to match the Pi/PC tooling
#define CTRL_PORT 9000
#define TELEM_PORT 9001

// Telemetry frequency (ms)
#define ENCODER_TELEM_INTERVAL_MS 50

// TB6612 pin mapping (4 motors across two TB6612 drivers)
// Motor index mapping: m1=front-left, m2=front-right, m3=rear-left, m4=rear-right
// Adjust as needed for your wiring
#define PIN_STBY 33

#define M1_PWM 25
#define M1_IN1 26
#define M1_IN2 27

#define M2_PWM 14
#define M2_IN1 18
#define M2_IN2 19

#define M3_PWM 23
#define M3_IN1 21
#define M3_IN2 22

#define M4_PWM 32
#define M4_IN1 13
#define M4_IN2 17

// Encoder pins (quadrature) for 4 wheels
// Prefer input-only pins (34-39) where available; add others as needed.
#define ENC1_A 34
#define ENC1_B 35
#define ENC2_A 36
#define ENC2_B 39
#define ENC3_A 4
#define ENC3_B 5
#define ENC4_A 2
#define ENC4_B 15

// PWM frequency
#define PWM_FREQ 20000
// PWM resolution (bits) for ledc
#define PWM_RES_BITS 10

// Kinematics / geometry
#define WHEEL_DIAMETER_MM 44.0
#define ENCODER_PPR 3
#define GEAR_RATIO 200
#define COUNTS_PER_WHEEL_ROTATION (ENCODER_PPR * GEAR_RATIO)  // 600
#define WHEEL_CIRCUMFERENCE_MM (3.1416f * WHEEL_DIAMETER_MM)   // ~138.2
#define DISTANCE_PER_PULSE_MM (WHEEL_CIRCUMFERENCE_MM / COUNTS_PER_WHEEL_ROTATION) // ~0.2303
#define WHEEL_BASE_MM 0  // TODO: measure this in mm and set a proper value
