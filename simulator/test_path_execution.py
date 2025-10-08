#!/usr/bin/env python3
"""Test path execution in simulation.

Loads path.csv and executes it using the virtual robot, demonstrating
how the path following works without hardware.
"""
from __future__ import annotations

import csv
import os
import sys
import time

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import simulator components
from simulator.virtual_robot import VirtualRobot, RobotConfig
from simulator.mock_esp32 import MockESP32

# Import control using sim_advanced
from simulator import sim_advanced as advanced
from calibration_config import load_pulses_per_degree, load_pulses_per_cm


def load_path(script_dir: str) -> list[tuple[float, float]]:
    """Load path from path.csv."""
    path_file = os.path.join(script_dir, "path.csv")
    segments = []
    
    if not os.path.exists(path_file):
        print(f"Warning: {path_file} not found. Using demo path.")
        # Demo path: square
        return [
            (0, 50),    # forward 50cm
            (90, 50),   # turn 90°, forward 50cm
            (90, 50),   # turn 90°, forward 50cm
            (90, 50),   # turn 90°, forward 50cm
        ]
    
    with open(path_file, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            turn_deg = float(row.get("turn_deg", 0))
            distance_cm = float(row.get("distance_cm", 0))
            segments.append((turn_deg, distance_cm))
    
    return segments


def execute_path(robot: VirtualRobot, segments: list[tuple[float, float]]) -> None:
    """Execute path segments using move_by_ticks."""
    ppd = load_pulses_per_degree()
    ppc = load_pulses_per_cm()
    
    print(f"\n=== Executing Path ===")
    print(f"Segments: {len(segments)}")
    print(f"Using PPD={ppd:.2f}, PPC={ppc:.2f}\n")
    
    for i, (turn_deg, distance_cm) in enumerate(segments, 1):
        print(f"Segment {i}/{len(segments)}: Turn {turn_deg:.1f}°, Move {distance_cm:.1f} cm")
        
        # Turn
        if abs(turn_deg) > 0.5:
            turn_ticks = int(abs(ppd * turn_deg))
            turn_speed = 40
            
            if turn_deg > 0:
                # Turn right (left=+, right=-)
                advanced.move_by_ticks(turn_ticks, -turn_ticks, turn_speed, -turn_speed)
            else:
                # Turn left (left=-, right=+)
                advanced.move_by_ticks(-turn_ticks, turn_ticks, -turn_speed, turn_speed)
            
            # Wait for turn completion
            time.sleep(abs(turn_deg) / 90.0 * 1.5 + 0.5)
            advanced.stop_motors()
            time.sleep(0.3)
        
        # Move forward
        if distance_cm > 0.5:
            move_ticks = int(ppc * distance_cm)
            move_speed = 45
            
            advanced.move_by_ticks(move_ticks, move_ticks, move_speed, move_speed)
            
            # Wait for move completion
            time.sleep(distance_cm / 40.0 + 0.5)
            advanced.stop_motors()
            time.sleep(0.3)
        
        # Print current state
        x, y, heading = robot.get_pose()
        print(f"  Robot at: ({x:.1f}, {y:.1f}) cm, heading {heading:.1f}°")
    
    print("\n✅ Path execution complete!")


def main():
    print("=== Path Execution Test (Simulation) ===\n")
    
    # Load path
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    segments = load_path(script_dir)
    
    print(f"Loaded {len(segments)} segments from path")
    for i, (turn, dist) in enumerate(segments, 1):
        print(f"  {i}. Turn {turn:+.1f}°, Move {dist:.1f} cm")
    
    # Start simulator
    print("\nStarting simulator...")
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
    
    print("Simulator ready!")
    print("\nNote: Run simulator_ui.py in another terminal to see visualization")
    input("Press Enter to start path execution...")
    
    try:
        # Reset robot to known start
        robot.reset(x=20.0, y=20.0, heading=0.0)
        advanced.reset_rotation()
        time.sleep(0.5)
        
        # Execute path
        execute_path(robot, segments)
        
        # Final state
        x, y, heading = robot.get_pose()
        print(f"\nFinal robot state:")
        print(f"  Position: ({x:.1f}, {y:.1f}) cm")
        print(f"  Heading: {heading:.1f}°")
        
        encoders = advanced.get_latest_encoders()[0]
        print(f"  Encoders: L={encoders.get('m1', 0)}, R={encoders.get('m2', 0)}")
        
    except KeyboardInterrupt:
        print("\nPath execution interrupted")
    except Exception as e:
        print(f"Path execution failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        advanced.cleanup()
        esp32.stop()
        robot.stop()
        print("\nSimulator stopped")


if __name__ == "__main__":
    main()
