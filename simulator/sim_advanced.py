#!/usr/bin/env python3
"""Simulation adapter for advanced.py.

Drop-in replacement that connects to the mock ESP32 simulator instead of
real hardware. Import this instead of advanced.py in test scripts.
"""
from __future__ import annotations

import sys
import os

# Ensure simulator modules are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import and re-export all advanced.py functionality
# The mock ESP32 runs on localhost, so we just need to update the IP
import advanced

# Override RPI_IP to point to localhost simulator
advanced.RPI_IP = '127.0.0.1'

# Re-export everything from advanced
from advanced import (
    # Network config
    RPI_CTRL_PORT,
    LOCAL_TELEM_PORT,
    
    # Motor config
    MOTOR_FACTOR_LEFT,
    MOTOR_FACTOR_RIGHT,
    MOTOR_MAX_SPEED,
    GEAR_SCALES,
    CRAWL_SCALE,
    FWD_GAIN,
    TURN_GAIN,
    PULSES_PER_DEGREE,
    PULSES_PER_CM,
    
    # Core functions
    init_bot_control,
    cleanup,
    send_motor,
    stop_motors,
    move_forward,
    move_backward,
    turn_right,
    turn_left,
    send_motor_differential,
    send_motor4,
    move_by_ticks,
    set_servo_angle,
    stepper_steps,
    
    # Motor factors
    set_motor_factors,
    
    # Telemetry functions
    get_current_distance,
    get_last_lidar_time,
    is_lidar_data_fresh,
    get_latest_imu,
    get_latest_heading,
    get_latest_encoders,
    is_encoder_data_available,
    wait_for_encoder_data,
    get_full_imu_data,
    get_rotation_degrees,
    reset_rotation,
    
    # Gyro calibration
    load_gyro_calibration,
    get_corrected_gyro,
    integrate_gyro_rotation,
    
    # Gear functions
    get_current_gear,
    set_gear,
    gear_up,
    gear_down,
    get_gear_scale,
    calculate_gear_speed,
    move_with_gear,
    turn_with_gear,
)

# Print helpful message when imported
print("⚙️  sim_advanced: Using simulator backend (127.0.0.1)")
print("   Make sure simulator_ui.py or mock_esp32.py is running!")
