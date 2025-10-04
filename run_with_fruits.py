#!/usr/bin/env python3
"""
Run robot track with fruit color mapping
- Loads fruit_config.json from fruit_ui.py
- Loads track.csv (like run_track.py)
- Executes robot path based on mapping
"""

import os
import sys
import time
import csv
import json

try:
    from move_control import RobotController
    import advanced
except ImportError as e:
    print(f"ERROR: Required modules not found: {e}")
    sys.exit(1)


class FruitTrackRunner:
    def __init__(self, track_file="track.csv", config_file="fruit_config.json"):
        self.track_file = track_file
        self.config_file = config_file
        self.track_data = []
        self.fruit_config = {}
        self.robot = RobotController()

    def load_config(self):
        """Load fruit color mapping"""
        if not os.path.exists(self.config_file):
            print(f"ERROR: Config file {self.config_file} not found. Run fruit_ui.py first.")
            sys.exit(1)

        with open(self.config_file, "r") as f:
            self.fruit_config = json.load(f)

        print("Loaded fruit config:", self.fruit_config)

    def load_track(self):
        """Load track data from CSV file"""
        if not os.path.exists(self.track_file):
            print(f"ERROR: Track file {self.track_file} not found. Run make_track.py first.")
            sys.exit(1)

        with open(self.track_file, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                angle = float(row["angle"])
                measure = float(row["measure"])
                self.track_data.append((angle, measure))

        print(f"Loaded {len(self.track_data)} track segments from {self.track_file}")

    def execute(self):
        """Execute the track based on fruit mapping"""
        if not self.track_data:
            print("No track data found!")
            return

        if not self.fruit_config:
            print("No fruit config found!")
            return

        print("\n=== Starting Fruit-Based Track Execution ===")
        print(f"Track segments: {len(self.track_data)}")
        print(f"Fruit mapping: {self.fruit_config}")

        # Example rule: Different color → different speed
        color_speed_map = {
            "Red": 40,
            "Green": 60,
            "Blue": 80,
            "Yellow": 100,
        }

        time.sleep(2)
        success_count = 0

        for i, (angle, measure) in enumerate(self.track_data):
            fruit_key = f"Fruit{i+1}"
            chosen_color = self.fruit_config.get(fruit_key, "Green")  # default Green
            speed = color_speed_map.get(chosen_color, 60)

            print(f"\n--- Segment {i+1} ---")
            print(f"Target: {angle:.1f}° turn, {measure:.1f} cm forward")
            print(f"Fruit: {fruit_key} → {chosen_color}, Speed: {speed}")

            # Adjust robot speed before execution
            self.robot.configure_speeds(move_speed=speed)

            if not self.robot.execute_command(angle, measure):
                print(f"⚠️ Failed to execute segment {i+1}")
                break

            success_count += 1
            print(f"✅ Segment {i+1} done with {chosen_color}")

        print(f"\n=== Execution finished: {success_count}/{len(self.track_data)} segments successful ===")


def main():
    print("=== Fruit-Based Robot Runner ===")

    if not advanced.init_bot_control(verbose_telemetry=False):
        print("ERROR: Failed to initialize robot control")
        return

    runner = FruitTrackRunner()
    runner.load_config()
    runner.load_track()
    runner.execute()

    advanced.cleanup()
    print("Robot control cleaned up.")


if __name__ == "__main__":
    main()
