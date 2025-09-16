#!/usr/bin/env python3
"""
Test script for gyro rotation tracking functionality with calibration support
"""
import time
from advanced import (
    init_bot_control, get_rotation_degrees, reset_rotation,
    get_latest_imu, get_corrected_gyro, load_gyro_calibration, cleanup
)

def test_rotation_tracking():
    """Test the rotation tracking functionality"""
    print("=== ROTATION TRACKING TEST ===")
    print("This test will monitor gyro data and show cumulative rotation")
    print("Press Ctrl+C to stop\n")
    
    # Initialize the bot control system
    init_bot_control(verbose_telemetry=False)
    
    # Reset rotation counter to start fresh
    reset_rotation()
    
    try:
        while True:
            # Get current rotation
            current_rotation = get_rotation_degrees()
            
            # Get latest IMU data
            accel, gyro, imu_time = get_latest_imu()
            corrected_gyro = get_corrected_gyro(gyro)
            
            # Display status
            if imu_time > 0:  # Only show if we have IMU data
                print(f"\rCurrent rotation: {current_rotation:+7.1f}° | "
                      f"Raw Gyro Z: {gyro['z']:+6.2f}°/s | "
                      f"Corrected Z: {corrected_gyro['z']:+6.2f}°/s | "
                      f"Time: {time.time():.1f}s", end="", flush=True)
            else:
                print(f"\rWaiting for IMU data... {time.time():.1f}s", end="", flush=True)
            
            time.sleep(0.1)  # Update 10 times per second
            
    except KeyboardInterrupt:
        print(f"\n\nFinal rotation: {get_rotation_degrees():.1f} degrees")
        print("Test completed.")
    finally:
        cleanup()

def test_manual_rotation_reset():
    """Test manual rotation with periodic resets"""
    print("=== MANUAL ROTATION RESET TEST ===")
    print("This test will reset rotation every 10 seconds")
    print("Press Ctrl+C to stop\n")
    
    init_bot_control(verbose_telemetry=False)
    reset_rotation()
    
    start_time = time.time()
    last_reset = start_time
    
    try:
        while True:
            current_time = time.time()
            elapsed = current_time - start_time
            since_reset = current_time - last_reset
            
            # Reset every 10 seconds
            if since_reset >= 10.0:
                print(f"\n[{elapsed:.1f}s] Resetting rotation counter...")
                reset_rotation()
                last_reset = current_time
            
            # Display current state
            rotation = get_rotation_degrees()
            accel, gyro, imu_time = get_latest_imu()
            corrected_gyro = get_corrected_gyro(gyro)
            
            if imu_time > 0:
                print(f"\r[{elapsed:5.1f}s] Rotation: {rotation:+7.1f}° | "
                      f"Reset in: {10.0-since_reset:4.1f}s | "
                      f"Corrected Z: {corrected_gyro['z']:+6.2f}°/s", end="", flush=True)
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print(f"\n\nTest completed. Final rotation: {get_rotation_degrees():.1f}°")
    finally:
        cleanup()

if __name__ == '__main__':
    print("Choose test mode:")
    print("1. Basic rotation tracking")
    print("2. Manual rotation reset test")
    
    try:
        choice = input("Enter choice (1 or 2): ").strip()
        if choice == '1':
            test_rotation_tracking()
        elif choice == '2':
            test_manual_rotation_reset()
        else:
            print("Invalid choice. Running basic rotation tracking...")
            test_rotation_tracking()
    except KeyboardInterrupt:
        print("\nExiting...")
