#!/usr/bin/env python3
# run_track.py - Robot path following using recorded track data
"""
Robot path following script that reads track data from track.csv
and executes the movements using the move_control.py precise movement system.
Uses PURE ENCODER-BASED navigation (NO GYRO) for reliable path following.
Format: angle, measure (distance in cm)
"""
import csv
import time
import sys
import os

# Import the movement control system
try:
    from move_control import RobotController
    import advanced
except ImportError as e:
    print(f"ERROR: Required modules not found: {e}")
    print("Make sure move_control.py and advanced.py are in the same directory.")
    sys.exit(1)


class TrackFollower:
    def __init__(self, track_file="track.csv"):
        self.track_file = track_file
        self.track_data = []
        self.robot = RobotController()
        self.load_track()
        
    def load_track(self):
        """Load track data from CSV file"""
        if not os.path.exists(self.track_file):
            print(f"ERROR: Track file '{self.track_file}' not found.")
            print("Run make_track.py first to create a track.")
            sys.exit(1)
            
        try:
            with open(self.track_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    angle = float(row['angle'])
                    measure = float(row['measure'])
                    self.track_data.append((angle, measure))
            print(f"Loaded {len(self.track_data)} track segments from {self.track_file}")
        except Exception as e:
            print(f"ERROR: Failed to load track file: {e}")
            sys.exit(1)
    
    def execute_track(self, start_delay=3.0):
        """Execute the complete track using pure encoder-based movement control (NO GYRO)"""
        if not self.track_data:
            print("No track data to execute")
            return False
            
        print(f"Executing track with {len(self.track_data)} segments")
        print(f"Starting in {start_delay} seconds...")
        
        # Countdown
        for i in range(int(start_delay), 0, -1):
            print(f"{i}...")
            time.sleep(1.0)
        print("GO!")
        
        success_count = 0
        for i, (angle, measure) in enumerate(self.track_data):
            print(f"\n--- Segment {i+1}/{len(self.track_data)} ---")
            print(f"Target: {angle:.1f}° turn, {measure:.1f} cm forward")
            
            # Break down large turns into smaller ones
            if abs(angle) > 135:  # If turn is close to 180 degrees
                print(f"Breaking down {angle:.1f}° turn into two 90° turns")
                
                # First 90-degree turn
                first_turn = 90 if angle > 0 else -90
                print(f"  First turn: {first_turn:.1f}°")
                if not self.robot.turn_to_angle(first_turn):
                    print(f"Failed first turn in segment {i+1}")
                    break
                
                # Second 90-degree turn
                second_turn = angle - first_turn
                print(f"  Second turn: {second_turn:.1f}°")
                if not self.robot.turn_to_angle(second_turn):
                    print(f"Failed second turn in segment {i+1}")
                    break
                
                # Move forward
                if measure > 0:
                    print(f"  Moving forward: {measure:.1f} cm")
                    if not self.robot.move_distance(measure):
                        print(f"Failed forward movement in segment {i+1}")
                        break
            else:
                # Use the precise movement control system for normal turns
                if not self.robot.execute_command(angle, measure):
                    print(f"Failed to execute segment {i+1}")
                    break
                
            success_count += 1
            print(f"Segment {i+1} completed successfully")
        
        print(f"\nTrack execution complete: {success_count}/{len(self.track_data)} segments successful")
        return success_count == len(self.track_data)
    
    def preview_track(self):
        """Preview the track without executing"""
        if not self.track_data:
            print("No track data to preview")
            return
            
        print(f"Track Preview ({len(self.track_data)} segments):")
        print("Segment | Turn Angle | Distance | Notes")
        print("--------|------------|----------|------------------")
        
        cumulative_angle = 0.0
        total_distance = 0.0
        breakdown_count = 0
        
        for i, (angle, measure) in enumerate(self.track_data):
            cumulative_angle += angle
            total_distance += measure
            
            # Check if this turn will be broken down
            notes = ""
            if abs(angle) > 135:
                notes = "→ 2×90° turns"
                breakdown_count += 1
            
            print(f"   {i+1:2d}   |   {angle:6.1f}°  |  {measure:6.1f} cm | {notes}")
        
        print("--------|------------|----------|------------------")
        print(f" Total  |   {cumulative_angle:6.1f}°  |  {total_distance:6.1f} cm | {breakdown_count} segments split")


def main():
    print("=== Robot Track Follower ===")
    
    # Initialize robot control
    if not advanced.init_bot_control(verbose_telemetry=False):
        print("ERROR: Failed to initialize robot control")
        return
    
    # Create track follower
    follower = TrackFollower()
    
    # Preview track
    follower.preview_track()
    
    # Ask user for confirmation
    print("\nOptions:")
    print("1. Execute track")
    print("2. Preview only (exit)")
    print("3. Exit")
    
    try:
        choice = input("\nEnter choice (1-3): ").strip()
        
        if choice == "1":
            print("\nStarting track execution...")
            success = follower.execute_track()
            if success:
                print("Track completed successfully!")
            else:
                print("Track execution failed or incomplete.")
        elif choice == "2":
            print("Preview complete.")
        else:
            print("Exiting.")
            
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        advanced.cleanup()
        print("Robot control cleaned up")


if __name__ == "__main__":
    main()
