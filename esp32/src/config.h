#pragma once

// Configure WiFi credentials
#define WIFI_SSID "Abbashotspot"
#define WIFI_PASS "qwertyuiop"

// PC hostname for direct communication
#define PC_HOSTNAME "msi.local"

// mDNS hostname (will be accessible as esp32-robot.local)
#define MDNS_HOSTNAME "esp32-robot"

// Static IP Configuration (optional - comment out for DHCP)
#define STATIC_IP_ENABLE false  // Disable static IP, use DHCP + mDNS instead
#define STATIC_IP       IPAddress(10, 210, 244, 100)   // Fixed IP for ESP32 (matching your PC's network)
#define GATEWAY_IP      IPAddress(10, 210, 244, 133)   // Router IP (from your ipconfig)
#define SUBNET_MASK     IPAddress(255, 255, 255, 0)    // Subnet mask
#define DNS_PRIMARY     IPAddress(8, 8, 8, 8)          // Google DNS
#define DNS_SECONDARY   IPAddress(8, 8, 4, 4)          // Google DNS backup

// Ports to match advanced.py
#define CTRL_PORT 9000
#define TELEM_PORT 9001

// Telemetry frequency (ms)
#define ENCODER_TELEM_INTERVAL_MS 50

// TB6612 pin mapping (2 motors - Motor A and Motor B)
// Motor A = Motor 1, Motor B = Motor 2
#define PIN_STBY 2

#define M1_PWM 25   // PWMA
#define M1_IN1 26   // AIN1
#define M1_IN2 27   // AIN2

#define M2_PWM 32   // PWMB
#define M2_IN1 33   // BIN1
#define M2_IN2 14   // BIN2

// Encoder pins (quadrature) for 2 motors
#define ENC1_A 34   // ENCA_A
#define ENC1_B 36   // ENCA_B
#define ENC2_A 39   // ENCB_A  
#define ENC2_B 35   // ENCB_B

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
