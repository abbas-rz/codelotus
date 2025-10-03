#!/usr/bin/env python3
"""
Test script for turn precision calibration
Run this to fix the 5-degree overshoot issue
"""

import sys
import time
from move_control import RobotController

def main():
    print("🎯 Turn Precision Test & Calibration")
    print("=" * 40)
    
    # Initialize controller
    print("Initializing robot controller...")
    controller = RobotController()
    
    # Test ESP32 connection
    if not controller.test_esp32_connection():
        print("❌ Cannot connect to ESP32. Check connection and try again.")
        return
    
    print("\n🔧 Current Settings:")
    print(f"  PULSES_PER_DEGREE: {controller.PULSES_PER_DEGREE}")
    print(f"  Turn speed: {controller.turn_speed}")
    print(f"  Rotation tolerance: ±{controller.rotation_tolerance}°")
    
    while True:
        print("\n" + "=" * 40)
        print("Turn Precision Test Menu:")
        print("1. Test 90° turn (left)")
        print("2. Test 90° turn (right)")
        print("3. Test 45° turn (left)")
        print("4. Test 45° turn (right)")
        print("5. Test custom angle")
        print("6. Calibrate PULSES_PER_DEGREE")
        print("7. Adjust turn speed")
        print("8. Exit")
        
        choice = input("\nSelect option (1-8): ").strip()
        
        if choice == "1":
            print("\n🔄 Testing 90° left turn...")
            controller.turn_to_angle(90)
            
        elif choice == "2":
            print("\n🔄 Testing 90° right turn...")
            controller.turn_to_angle(-90)
            
        elif choice == "3":
            print("\n🔄 Testing 45° left turn...")
            controller.turn_to_angle(45)
            
        elif choice == "4":
            print("\n🔄 Testing 45° right turn...")
            controller.turn_to_angle(-45)
            
        elif choice == "5":
            try:
                angle = float(input("Enter angle in degrees (positive=left, negative=right): "))
                print(f"\n🔄 Testing {angle}° turn...")
                controller.turn_to_angle(angle)
            except ValueError:
                print("❌ Invalid angle. Please enter a number.")
                
        elif choice == "6":
            try:
                test_angle = float(input("Enter test angle for calibration (default 90): ") or "90")
                controller.calibrate_turn_precision(test_angle)
            except ValueError:
                print("❌ Invalid angle. Please enter a number.")
                
        elif choice == "7":
            try:
                new_speed = int(input(f"Enter new turn speed (current: {controller.turn_speed}): "))
                controller.configure_speeds(turn_speed=new_speed)
            except ValueError:
                print("❌ Invalid speed. Please enter a number.")
                
        elif choice == "8":
            print("👋 Exiting...")
            break
            
        else:
            print("❌ Invalid choice. Please select 1-8.")
        
        # Brief pause between operations
        time.sleep(0.5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user. Exiting...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

