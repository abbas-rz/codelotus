#!/usr/bin/env python3
"""Test calibration routines in simulation.

Demonstrates running the PPD and PPC calibrators with the virtual robot.
"""
from __future__ import annotations

import argparse
import sys
import time
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import simulator components
from simulator.virtual_robot import VirtualRobot, RobotConfig
from simulator.mock_esp32 import MockESP32

# Import calibration using sim_advanced
from simulator import sim_advanced as advanced
from calibration_config import load_pulses_per_degree, load_pulses_per_cm


def test_ppd_calibration():
    """Test pulses-per-degree calibration in simulation."""
    print("=== PPD Calibration Test (Simulation) ===")
    print("This will command 360° rotations and show encoder behavior.\n")
    
    # Start simulator
    robot = VirtualRobot()
    robot.start()
    esp32 = MockESP32(robot, pc_ip="127.0.0.1")
    esp32.start()
    
    # Initialize control
    advanced.init_bot_control(verbose_telemetry=False)
    time.sleep(1.0)  # Wait for telemetry
    
    if not advanced.wait_for_encoder_data(timeout=5.0):
        print("ERROR: No encoder data from simulator")
        return
    
    current_ppd = load_pulses_per_degree()
    print(f"Current PPD from config: {current_ppd:.2f}")
    print(f"Simulator PPD: {robot.config.pulses_per_degree:.2f}\n")
    
    # Test a 360° rotation
    ticks_per_360 = int(current_ppd * 360)
    print(f"Commanding 360° rotation ({ticks_per_360} ticks)...")
    
    start_enc = advanced.get_latest_encoders()[0]
    start_left = start_enc.get('m1', 0)
    start_right = start_enc.get('m2', 0)
    
    # Turn in place (left=-ticks, right=+ticks)
    advanced.move_by_ticks(-ticks_per_360, ticks_per_360, -45, 45)
    
    # Wait for completion
    timeout = time.time() + 10.0
    while time.time() < timeout:
        enc = advanced.get_latest_encoders()[0]
        left_delta = abs(enc.get('m1', 0) - start_left)
        right_delta = abs(enc.get('m2', 0) - start_right)
        
        if left_delta >= ticks_per_360 * 0.95 and right_delta >= ticks_per_360 * 0.95:
            break
        time.sleep(0.1)
    
    advanced.stop_motors()
    time.sleep(0.5)
    
    # Check final state
    end_enc = advanced.get_latest_encoders()[0]
    end_left = end_enc.get('m1', 0)
    end_right = end_enc.get('m2', 0)
    
    actual_left = abs(end_left - start_left)
    actual_right = abs(end_right - start_right)
    avg_ticks = (actual_left + actual_right) / 2.0
    
    actual_rotation = avg_ticks / current_ppd
    
    print(f"\nResults:")
    print(f"  Commanded: 360°")
    print(f"  Target ticks: {ticks_per_360}")
    print(f"  Actual ticks: left={actual_left}, right={actual_right}, avg={avg_ticks:.1f}")
    print(f"  Actual rotation (using config PPD): {actual_rotation:.1f}°")
    
    # Compare with simulator truth
    x, y, heading = robot.get_pose()
    print(f"  Simulator truth: heading={heading:.1f}° (should be ~0° after 360°)")
    
    # Compute error
    error_deg = abs(360.0 - actual_rotation)
    print(f"\nRotation error: {error_deg:.1f}°")
    
    if error_deg < 5.0:
        print("✅ PPD calibration looks good!")
    else:
        print(f"⚠️  PPD may need adjustment. Suggested PPD: {avg_ticks / 360.0:.2f}")
    
    # Cleanup
    advanced.cleanup()
    esp32.stop()
    robot.stop()


def test_ppc_calibration():
    """Test pulses-per-cm calibration in simulation."""
    print("=== PPC Calibration Test (Simulation) ===")
    print("This will command forward movement and check encoder behavior.\n")
    
    # Start simulator
    robot = VirtualRobot()
    robot.start()
    esp32 = MockESP32(robot, pc_ip="127.0.0.1")
    esp32.start()
    
    # Initialize control
    advanced.init_bot_control(verbose_telemetry=False)
    time.sleep(1.0)
    
    if not advanced.wait_for_encoder_data(timeout=5.0):
        print("ERROR: No encoder data from simulator")
        return
    
    current_ppc = load_pulses_per_cm()
    print(f"Current PPC from config: {current_ppc:.2f}")
    print(f"Simulator PPC: {robot.config.pulses_per_cm:.2f}\n")
    
    # Test 80 cm forward movement
    distance_cm = 80.0
    ticks = int(current_ppc * distance_cm)
    print(f"Commanding {distance_cm} cm forward ({ticks} ticks)...")
    
    start_enc = advanced.get_latest_encoders()[0]
    start_left = start_enc.get('m1', 0)
    start_right = start_enc.get('m2', 0)
    start_x, start_y, _ = robot.get_pose()
    
    # Move forward
    advanced.move_by_ticks(ticks, ticks, 45, 45)
    
    # Wait for completion
    timeout = time.time() + 10.0
    while time.time() < timeout:
        enc = advanced.get_latest_encoders()[0]
        left_delta = abs(enc.get('m1', 0) - start_left)
        right_delta = abs(enc.get('m2', 0) - start_right)
        
        if left_delta >= ticks * 0.95 and right_delta >= ticks * 0.95:
            break
        time.sleep(0.1)
    
    advanced.stop_motors()
    time.sleep(0.5)
    
    # Check final state
    end_enc = advanced.get_latest_encoders()[0]
    end_left = end_enc.get('m1', 0)
    end_right = end_enc.get('m2', 0)
    
    actual_left = abs(end_left - start_left)
    actual_right = abs(end_right - start_right)
    avg_ticks = (actual_left + actual_right) / 2.0
    
    actual_distance = avg_ticks / current_ppc
    
    print(f"\nResults:")
    print(f"  Commanded: {distance_cm} cm")
    print(f"  Target ticks: {ticks}")
    print(f"  Actual ticks: left={actual_left}, right={actual_right}, avg={avg_ticks:.1f}")
    print(f"  Actual distance (using config PPC): {actual_distance:.2f} cm")
    
    # Compare with simulator truth
    end_x, end_y, _ = robot.get_pose()
    true_distance = ((end_x - start_x)**2 + (end_y - start_y)**2)**0.5
    print(f"  Simulator truth: {true_distance:.2f} cm")
    
    # Compute error
    error_cm = abs(distance_cm - actual_distance)
    print(f"\nDistance error: {error_cm:.2f} cm")
    
    if error_cm < 2.0:
        print("✅ PPC calibration looks good!")
    else:
        print(f"⚠️  PPC may need adjustment. Suggested PPC: {avg_ticks / distance_cm:.2f}")
    
    # Cleanup
    advanced.cleanup()
    esp32.stop()
    robot.stop()


def main():
    parser = argparse.ArgumentParser(description="Test calibration in simulation")
    parser.add_argument("--mode", choices=["ppd", "ppc", "both"], default="both",
                       help="Which calibration to test")
    args = parser.parse_args()
    
    try:
        if args.mode in ("ppd", "both"):
            test_ppd_calibration()
            if args.mode == "both":
                print("\n" + "="*60 + "\n")
                time.sleep(1.0)
        
        if args.mode in ("ppc", "both"):
            test_ppc_calibration()
    
    except KeyboardInterrupt:
        print("\nTest interrupted")
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
