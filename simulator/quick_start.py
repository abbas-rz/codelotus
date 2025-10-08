#!/usr/bin/env python3
"""Quick start demo for the simulator.

This script demonstrates the complete workflow:
1. Start simulator
2. Run a simple test path
3. Show telemetry

Run this to verify the simulator is working.
"""
from __future__ import annotations

import sys
import os
import time

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulator.virtual_robot import VirtualRobot
from simulator.mock_esp32 import MockESP32
from simulator import sim_advanced as advanced


def main():
    print("="*60)
    print("ROBOT SIMULATOR - QUICK START DEMO")
    print("="*60)
    
    # Step 1: Create and start virtual robot
    print("\n[1/4] Creating virtual robot...")
    robot = VirtualRobot()
    robot.start()
    print("✓ Virtual robot started")
    
    # Step 2: Start mock ESP32
    print("\n[2/4] Starting mock ESP32 server...")
    esp32 = MockESP32(robot, pc_ip="127.0.0.1")
    esp32.start()
    print("✓ Mock ESP32 running on ports 9000 (ctrl) and 9001 (telem)")
    
    # Step 3: Initialize control interface
    print("\n[3/4] Connecting control interface...")
    advanced.init_bot_control(verbose_telemetry=False)
    time.sleep(1.0)
    
    if not advanced.wait_for_encoder_data(timeout=5.0):
        print("✗ Failed to receive encoder telemetry")
        return
    print("✓ Control interface connected")
    
    # Step 4: Run a simple test
    print("\n[4/4] Running test movements...")
    
    # Test 1: Move forward
    print("  → Moving forward 30 cm...")
    ppc = robot.config.pulses_per_cm
    ticks = int(ppc * 30)
    advanced.move_by_ticks(ticks, ticks, 40, 40)
    time.sleep(2.0)
    
    x, y, heading = robot.get_pose()
    print(f"     Position: ({x:.1f}, {y:.1f}) cm, heading {heading:.1f}°")
    
    # Test 2: Turn 90°
    print("  → Turning 90°...")
    ppd = robot.config.pulses_per_degree
    turn_ticks = int(ppd * 90)
    advanced.move_by_ticks(turn_ticks, -turn_ticks, 35, -35)
    time.sleep(2.0)
    
    x, y, heading = robot.get_pose()
    print(f"     Position: ({x:.1f}, {y:.1f}) cm, heading {heading:.1f}°")
    
    # Test 3: Move forward again
    print("  → Moving forward 20 cm...")
    ticks = int(ppc * 20)
    advanced.move_by_ticks(ticks, ticks, 40, 40)
    time.sleep(1.5)
    
    x, y, heading = robot.get_pose()
    print(f"     Position: ({x:.1f}, {y:.1f}) cm, heading {heading:.1f}°")
    
    # Show final telemetry
    print("\n" + "="*60)
    print("FINAL STATE")
    print("="*60)
    
    encoders = advanced.get_latest_encoders()[0]
    print(f"Encoders: Left={encoders.get('m1', 0)}, Right={encoders.get('m2', 0)}")
    print(f"Position: ({x:.2f}, {y:.2f}) cm")
    print(f"Heading: {heading:.1f}°")
    
    print("\n✅ Demo complete!")
    print("\nNext steps:")
    print("  • Run simulator_ui.py for visual feedback")
    print("  • Run test_calibration.py to test PPD/PPC calibration")
    print("  • Run test_path_execution.py to test path following")
    
    # Cleanup
    advanced.cleanup()
    esp32.stop()
    robot.stop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\n✗ Demo failed: {e}")
        import traceback
        traceback.print_exc()
