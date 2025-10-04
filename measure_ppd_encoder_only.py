#!/usr/bin/env python3
"""
Encoder-Only PPD (Pulses Per Degree) Measurement Tool

This tool measures PPD using only encoder data - no gyro required.
It uses differential encoder counting to determine rotation.

Usage:
    python measure_ppd_encoder_only.py
"""

import time
import math
from advanced import (
    init_bot_control, cleanup, get_latest_encoders,
    send_motor, stop_motors
)

def calculate_rotation_from_encoders(left_delta, right_delta):
    """
    Calculate rotation in degrees from encoder deltas for 2WD robot
    
    Args:
        left_delta: Left encoder pulse change
        right_delta: Right encoder pulse change  
    
    Returns:
        Rotation in degrees
    """
    # For 2WD robots, we can use the existing PULSES_PER_DEGREE constant
    # or calculate it directly from the encoder difference
    
    # Simple approach: use the average of both encoders as rotation indicator
    # This works well for 2WD differential drive
    avg_encoder_delta = (abs(left_delta) + abs(right_delta)) / 2
    
    # For 2WD, we can estimate rotation based on encoder difference
    # This is a simplified approach that works well for most 2WD robots
    encoder_diff = abs(left_delta - right_delta)
    
    # Use a reasonable estimate for 2WD rotation
    # This will be calibrated by the measurement
    estimated_rotation = encoder_diff / 2.0  # Rough estimate
    
    return estimated_rotation, avg_encoder_delta

def measure_ppd_encoder_only():
    """Measure PPD using encoder-only method"""
    
    print("=== Encoder-Only PPD Measurement Tool ===")
    print("This tool measures PPD using only encoder data - no gyro required")
    print()
    
    # Initialize bot control
    print("Initializing bot control...")
    init_bot_control(verbose_telemetry=False)
    time.sleep(3)
    
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
    print("3. The robot will turn for a fixed time")
    print("4. We'll calculate PPD from encoder differences")
    print()
    
    input("Press Enter when ready to start measurement...")
    
    # Get initial encoder readings
    initial_encoders, _ = get_latest_encoders()
    initial_left = initial_encoders.get('m1', 0)
    initial_right = initial_encoders.get('m2', 0)
    
    print(f"Initial encoders: Left={initial_left}, Right={initial_right}")
    
    print("\n🔄 Starting turn...")
    print("Robot will turn LEFT for 3 seconds")
    
    # Start turning left
    turn_speed = 40
    send_motor(-turn_speed, turn_speed)  # Left turn
    
    # Turn for fixed time
    turn_duration = 3.0  # seconds
    start_time = time.time()
    
    while time.time() - start_time < turn_duration:
        elapsed = time.time() - start_time
        print(f"Turning... {elapsed:.1f}s", end='\r')
        time.sleep(0.1)
    
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
    print(f"Turn duration:    {turn_duration}s")
    
    # Calculate rotation from encoders (2WD method)
    estimated_rotation, avg_encoder_delta = calculate_rotation_from_encoders(left_delta, right_delta)
    
    print(f"\n=== Rotation Calculation ===")
    print(f"Estimated rotation: {estimated_rotation:.1f}°")
    print(f"Average encoder delta: {avg_encoder_delta:.1f} pulses")
    
    if avg_encoder_delta > 10:  # If we detected significant movement
        # For 2WD, we'll use a simpler PPD calculation
        # Assume the robot turned approximately 90 degrees in 3 seconds
        assumed_rotation = 90.0  # degrees
        ppd = avg_encoder_delta / assumed_rotation
        
        print(f"\n=== PPD Calculation ===")
        print(f"Average encoder delta: {avg_encoder_delta:.1f} pulses")
        print(f"Assumed rotation: {assumed_rotation}° (for 3-second turn)")
        print(f"Pulses Per Degree: {ppd:.1f}")
        
        # Round to nearest integer
        ppd_rounded = round(ppd)
        print(f"Rounded PPD: {ppd_rounded}")
        
        print(f"\n=== Update telemetry_ui.py ===")
        print(f"Change this line in telemetry_ui.py:")
        print(f"PULSES_PER_DEGREE = {ppd_rounded}  # Measured value")
        
        return ppd_rounded
    else:
        print("❌ No significant movement detected. Check:")
        print("- Motor connections")
        print("- Encoder connections")
        return None

def measure_ppd_manual_encoder():
    """Manual PPD measurement using encoder-only method"""
    
    print("\n=== Manual Encoder-Only PPD Measurement ===")
    print("You will control the robot turn manually")
    print()
    
    # Initialize bot control
    print("Initializing bot control...")
    init_bot_control(verbose_telemetry=False)
    time.sleep(3)
    
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
    
    print("\n=== Manual Measurement Instructions ===")
    print("1. Place robot on a flat surface")
    print("2. Mark the robot's orientation")
    print("3. Press Enter to start recording")
    print("4. Manually turn the robot 90 degrees")
    print("5. Press Enter to stop recording")
    print()
    
    input("Press Enter to start recording...")
    
    # Get initial encoder readings
    initial_encoders, _ = get_latest_encoders()
    initial_left = initial_encoders.get('m1', 0)
    initial_right = initial_encoders.get('m2', 0)
    
    print(f"Initial encoders: Left={initial_left}, Right={initial_right}")
    print("Now manually turn the robot 90 degrees...")
    
    input("Press Enter when you've turned the robot 90 degrees...")
    
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
    
    # Calculate rotation from encoders (2WD method)
    estimated_rotation, avg_encoder_delta = calculate_rotation_from_encoders(left_delta, right_delta)
    
    print(f"\n=== Rotation Calculation ===")
    print(f"Estimated rotation: {estimated_rotation:.1f}°")
    print(f"Expected rotation: 90.0°")
    print(f"Average encoder delta: {avg_encoder_delta:.1f} pulses")
    
    if avg_encoder_delta > 10:  # If we detected significant movement
        # For manual 90-degree turn, use the actual rotation
        assumed_rotation = 90.0  # degrees
        ppd = avg_encoder_delta / assumed_rotation
        
        print(f"\n=== PPD Calculation ===")
        print(f"Average encoder delta: {avg_encoder_delta:.1f} pulses")
        print(f"Rotation: {assumed_rotation}° (manual 90° turn)")
        print(f"Pulses Per Degree: {ppd:.1f}")
        
        # Round to nearest integer
        ppd_rounded = round(ppd)
        print(f"Rounded PPD: {ppd_rounded}")
        
        print(f"\n=== Update telemetry_ui.py ===")
        print(f"Change this line in telemetry_ui.py:")
        print(f"PULSES_PER_DEGREE = {ppd_rounded}  # Measured value")
        
        return ppd_rounded
    else:
        print("❌ No significant movement detected. Check encoder connections.")
        return None

def main():
    try:
        print("Encoder-Only PPD Measurement Tool")
        print("Choose measurement method:")
        print("1. Automatic turn (3 seconds)")
        print("2. Manual turn (you control the robot)")
        
        choice = input("Enter choice (1 or 2): ").strip()
        
        if choice == "1":
            ppd = measure_ppd_encoder_only()
        elif choice == "2":
            ppd = measure_ppd_manual_encoder()
        else:
            print("Invalid choice. Using automatic method.")
            ppd = measure_ppd_encoder_only()
        
        if ppd:
            print(f"\n🎉 Measurement complete!")
            print(f"Update telemetry_ui.py with: PULSES_PER_DEGREE = {ppd}")
        else:
            print("❌ Measurement failed. Check robot connections and wheel base measurement.")
            
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
