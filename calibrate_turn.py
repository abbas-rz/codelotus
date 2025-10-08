#!/usr/bin/env python3
# calibrate_turn.py - Calibrate turn precision for robot
"""
Simple calibration script to determine the correct PULSES_PER_DEGREE value
for accurate turning. Run this to fine-tune your robot's turn precision.
"""
import time
import sys
from move_control import RobotController
import advanced

def calibrate_turn():
    """Calibrate turn precision by testing known angles"""
    print("=== Turn Calibration Tool ===")
    print("This will help determine the correct PULSES_PER_DEGREE value")
    print("for accurate turning.\n")
    
    # Initialize robot control
    if not advanced.init_bot_control(verbose_telemetry=False):
        print("ERROR: Failed to initialize robot control")
        return
    
    # Create robot controller
    robot = RobotController()
    
    # Test angles to calibrate
    test_angles = [90, 180, 360]  # degrees
    
    print("Test sequence:")
    print("1. Place robot on a flat surface")
    print("2. Mark the starting position and orientation")
    print("3. Robot will turn specified angles")
    print("4. Measure actual turn and calculate correction factor")
    print("\nPress Enter when ready to start...")
    input()
    
    for angle in test_angles:
        print(f"\n--- Testing {angle}° turn ---")
        print(f"Robot will turn {angle}°")
        print("Mark the starting position, then press Enter...")
        input()
        
        # Execute turn
        success = robot.turn_to_angle(angle)
        
        print(f"\nTurn completed. Success: {success}")
        print(f"Measure the actual angle turned and enter it below.")
        print(f"Expected: {angle}°")
        
        try:
            actual_angle = float(input("Actual angle turned: "))
            if actual_angle != 0:
                correction_factor = angle / actual_angle
                print(f"Correction factor: {correction_factor:.4f}")
                
                # Calculate new PULSES_PER_DEGREE
                current_ppd = robot.PULSES_PER_DEGREE
                new_ppd = current_ppd * correction_factor
                print(f"Current PULSES_PER_DEGREE: {current_ppd:.3f}")
                print(f"Suggested PULSES_PER_DEGREE: {new_ppd:.3f}")

                save_choice = input(
                    "Save this value to the shared calibration config now? [y/N]: "
                ).strip().lower()
                if save_choice in ("y", "yes"):
                    robot.configure_turn_precision(pulses_per_degree=new_ppd)
                    print("Calibration config updated.")
            else:
                print("Invalid angle entered")
        except ValueError:
            print("Invalid input")
        
        print("\nPress Enter to continue to next test...")
        input()
    
    print("\n=== Calibration Complete ===")
    print("Saved values are written to robot_calibration.json so all tools stay in sync.")
    print("If you skipped saving, rerun and confirm with 'y' to persist the new value.")
    
    advanced.cleanup()

def quick_test():
    """Quick test of current turn precision"""
    print("=== Quick Turn Test ===")
    
    if not advanced.init_bot_control(verbose_telemetry=False):
        print("ERROR: Failed to initialize robot control")
        return
    
    robot = RobotController()
    
    print("Testing 90° turn...")
    print("Mark starting position, then press Enter...")
    input()
    
    success = robot.turn_to_angle(90)
    print(f"Turn completed. Success: {success}")
    print("Measure actual angle and compare to expected 90°")
    
    advanced.cleanup()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        quick_test()
    else:
        calibrate_turn()

