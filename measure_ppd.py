#!/usr/bin/env python3
"""
PPD (Pulses Per Degree) Measurement Tool

This tool helps you measure how many encoder pulses your robot needs to turn 1 degree.
Run this to calibrate the PULSES_PER_DEGREE constant in telemetry_ui.py.

Usage:
    python measure_ppd.py
"""

import time
import math
from advanced import (
    init_bot_control, cleanup, get_latest_encoders,
    send_motor, stop_motors, get_rotation_degrees, reset_rotation
)

def measure_ppd():
    """Measure pulses per degree by turning the robot and recording encoder data"""
    
    print("=== PPD (Pulses Per Degree) Measurement Tool ===")
    print("This tool will help you calibrate PULSES_PER_DEGREE for telemetry_ui.py")
    print()
    
    # Initialize bot control
    print("Initializing bot control...")
    init_bot_control(verbose_telemetry=False)  # Disable verbose telemetry
    time.sleep(3)  # Wait for telemetry to start
    
    # Wait for encoder data
    print("Waiting for encoder data...")
    start_time = time.time()
    while time.time() - start_time < 10:
        encoders, enc_time = get_latest_encoders()
        if enc_time > 0:
            print("✅ Encoder data received!")
            break
        time.sleep(0.1)
    else:
        print("❌ No encoder data received. Check ESP32 connection.")
        return None
    
    print("\n=== Measurement Instructions ===")
    print("1. Place robot on a flat surface")
    print("2. Mark the robot's orientation (use a piece of tape)")
    print("3. The robot will turn 90 degrees")
    print("4. We'll measure the encoder pulses used")
    print()
    
    input("Press Enter when ready to start measurement...")
    
    # Get initial encoder readings
    initial_encoders, _ = get_latest_encoders()
    initial_left = initial_encoders.get('m1', 0)
    initial_right = initial_encoders.get('m2', 0)
    
    print(f"Initial encoders: Left={initial_left}, Right={initial_right}")
    
    # Reset rotation counter
    reset_rotation()
    time.sleep(0.5)
    
    print("\n🔄 Starting 90-degree turn...")
    print("Robot will turn LEFT (counter-clockwise)")
    
    # Start turning left
    turn_speed = 30
    send_motor(-turn_speed, turn_speed)  # Left turn
    
    # Monitor rotation
    start_time = time.time()
    target_rotation = 90.0
    tolerance = 5.0  # Increased tolerance
    
    print(f"Target: {target_rotation}° (tolerance: ±{tolerance}°)")
    
    while time.time() - start_time < 10:  # Reduced timeout to 10 seconds
        current_rotation = get_rotation_degrees()
        print(f"Current rotation: {current_rotation:.1f}°", end='\r')
        
        if abs(current_rotation - target_rotation) <= tolerance:
            print(f"\n✅ Turn complete! Final rotation: {current_rotation:.1f}°")
            break
            
        time.sleep(0.1)
    else:
        print(f"\n⚠️ Turn timeout. Final rotation: {current_rotation:.1f}°")
        print("Stopping motors...")
    
    # Stop motors
    stop_motors()
    time.sleep(0.5)
    
    # Get final encoder readings
    final_encoders, _ = get_latest_encoders()
    final_left = final_encoders.get('m1', 0)
    final_right = final_encoders.get('m2', 0)
    
    # Calculate encoder deltas
    left_delta = final_left - initial_left
    right_delta = final_right - initial_right
    
    print(f"\n=== Results ===")
    print(f"Initial encoders: Left={initial_left}, Right={initial_right}")
    print(f"Final encoders:   Left={final_left}, Right={final_right}")
    print(f"Encoder deltas:   Left={left_delta}, Right={right_delta}")
    print(f"Actual rotation:  {current_rotation:.1f}°")
    
    # Calculate PPD
    if current_rotation > 0:
        # Average of left and right encoder deltas
        avg_encoder_delta = (abs(left_delta) + abs(right_delta)) / 2
        ppd = avg_encoder_delta / current_rotation
        
        print(f"\n=== PPD Calculation ===")
        print(f"Average encoder delta: {avg_encoder_delta:.1f} pulses")
        print(f"Rotation: {current_rotation:.1f}°")
        print(f"Pulses Per Degree: {ppd:.1f}")
        
        # Round to nearest integer
        ppd_rounded = round(ppd)
        print(f"Rounded PPD: {ppd_rounded}")
        
        print(f"\n=== Update telemetry_ui.py ===")
        print(f"Change this line in telemetry_ui.py:")
        print(f"PULSES_PER_DEGREE = {ppd_rounded}  # Measured value")
        
        return ppd_rounded
    else:
        print("❌ No rotation detected. Check gyro or motor connections.")
        return None

def measure_multiple_turns():
    """Measure PPD with multiple turns for better accuracy"""
    
    print("\n=== Multiple Turn Measurement ===")
    print("This will measure PPD with 180° and 360° turns for better accuracy")
    
    measurements = []
    
    for target_angle in [180, 360]:
        print(f"\n--- Measuring {target_angle}° turn ---")
        
        # Get initial readings
        initial_encoders, _ = get_latest_encoders()
        initial_left = initial_encoders.get('m1', 0)
        initial_right = initial_encoders.get('m2', 0)
        
        # Reset rotation
        reset_rotation()
        time.sleep(0.5)
        
        print(f"Starting {target_angle}° turn...")
        
        # Turn
        send_motor(-30, 30)  # Left turn
        
        start_time = time.time()
        while time.time() - start_time < 20:  # Reduced timeout to 20 seconds
            current_rotation = get_rotation_degrees()
            print(f"Current rotation: {current_rotation:.1f}°", end='\r')
            if abs(current_rotation - target_angle) <= 5.0:  # Increased tolerance
                print(f"\n✅ {target_angle}° turn complete!")
                break
            time.sleep(0.1)
        else:
            print(f"\n⚠️ {target_angle}° turn timeout. Final: {current_rotation:.1f}°")
        
        stop_motors()
        time.sleep(0.5)
        
        # Get final readings
        final_encoders, _ = get_latest_encoders()
        final_left = final_encoders.get('m1', 0)
        final_right = final_encoders.get('m2', 0)
        
        # Calculate PPD
        left_delta = abs(final_left - initial_left)
        right_delta = abs(final_right - initial_right)
        avg_delta = (left_delta + right_delta) / 2
        
        if current_rotation > 0:
            ppd = avg_delta / current_rotation
            measurements.append(ppd)
            print(f"PPD for {target_angle}°: {ppd:.1f}")
    
    if measurements:
        avg_ppd = sum(measurements) / len(measurements)
        rounded_ppd = round(avg_ppd)
        
        print(f"\n=== Final Results ===")
        print(f"Individual PPD measurements: {[round(p, 1) for p in measurements]}")
        print(f"Average PPD: {avg_ppd:.1f}")
        print(f"Rounded PPD: {rounded_ppd}")
        
        return rounded_ppd
    
    return None

def main():
    try:
        print("PPD Measurement Tool")
        print("Choose measurement method:")
        print("1. Single 90° turn (quick)")
        print("2. Multiple turns (more accurate)")
        
        choice = input("Enter choice (1 or 2): ").strip()
        
        if choice == "1":
            ppd = measure_ppd()
        elif choice == "2":
            ppd = measure_multiple_turns()
        else:
            print("Invalid choice. Using single turn method.")
            ppd = measure_ppd()
        
        if ppd:
            print(f"\n🎉 Measurement complete!")
            print(f"Update telemetry_ui.py with: PULSES_PER_DEGREE = {ppd}")
        else:
            print("❌ Measurement failed. Check robot connections.")
            
    except KeyboardInterrupt:
        print("\nMeasurement cancelled by user.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        stop_motors()
        cleanup()
        print("Cleanup complete.")

if __name__ == "__main__":
    main()
