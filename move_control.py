#!/usr/bin/env python3
"""
Robot Movement Control with Pure Encoder-Based Navigation
Usage: python move_control.py
Takes rotation (degrees) and movement (cm) inputs to control the robot using only encoder data.

Encoder Specifications:
- PPR (Pulses Per Rotation): 1500
- Wheel diameter: 4.4 cm
- Bot rotation: 22.3 pulses per degree
"""
import time
import sys
import math
from advanced import (
    init_bot_control, cleanup, get_latest_encoders, move_by_ticks,
    stop_motors
)

class RobotController:
    def __init__(self):
        self.rotation_tolerance = 5.0  # degrees - allow ±5 degree error
        self.distance_tolerance = 2.0  # cm
        self.turn_speed = 20  # motor speed for turning
        self.move_speed = 20  # motor speed for movement
        self.max_turn_time = 30.0  # maximum time to attempt a turn (seconds)
        self.max_move_time = 30.0  # maximum time to attempt a move (seconds)
    
    def configure_tolerances(self, rotation_tolerance=None, distance_tolerance=None):
        """Configure tolerance values for rotation and distance"""
        if rotation_tolerance is not None:
            self.rotation_tolerance = max(0.1, float(rotation_tolerance))
            print(f"Rotation tolerance set to ±{self.rotation_tolerance:.1f} degrees")
        
        if distance_tolerance is not None:
            self.distance_tolerance = max(0.1, float(distance_tolerance))
            print(f"Distance tolerance set to ±{self.distance_tolerance:.1f} cm")
    
    def configure_speeds(self, turn_speed=None, move_speed=None):
        """Configure speed values for turning and movement"""
        if turn_speed is not None:
            self.turn_speed = max(5, min(120, int(turn_speed)))
            print(f"Turn speed set to {self.turn_speed}")
        
        if move_speed is not None:
            self.move_speed = max(5, min(120, int(move_speed)))
            print(f"Move speed set to {self.move_speed}")
    
    def configure_timeouts(self, turn_timeout=None, move_timeout=None):
        """Configure timeout values for operations"""
        if turn_timeout is not None:
            self.max_turn_time = max(5.0, float(turn_timeout))
            print(f"Turn timeout set to {self.max_turn_time:.1f} seconds")
        
        if move_timeout is not None:
            self.max_move_time = max(5.0, float(move_timeout))
            print(f"Move timeout set to {self.max_move_time:.1f} seconds")
    
    def show_configuration(self):
        """Display current configuration"""
        print(f"\n=== ROBOT CONFIGURATION ===")
        print(f"Rotation tolerance: ±{self.rotation_tolerance:.1f} degrees")
        print(f"Distance tolerance: ±{self.distance_tolerance:.1f} cm")
        print(f"Turn speed: {self.turn_speed}")
        print(f"Move speed: {self.move_speed}")
        print(f"Turn timeout: {self.max_turn_time:.1f} seconds")
        print(f"Move timeout: {self.max_move_time:.1f} seconds")
        print("=" * 30)
        
    def wait_for_stationary(self, timeout=3.0):
        """Wait for robot to be stationary before starting"""
        print("Waiting for robot to be stationary...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            _, gyro, imu_time = get_latest_imu()
            if imu_time > 0:
                # Check if angular velocity is low (robot is stationary)
                if abs(gyro['z']) < 5.0:  # less than 5 degrees/second
                    print("Robot is stationary. Ready to start.")
                    return True
            time.sleep(0.1)
        
        print("Warning: Robot may still be moving")
        return False
    
    def turn_to_angle(self, target_degrees):
        """Turn the robot to a specific angle relative to start position using gyro rotation"""
        print(f"Turning to {target_degrees:+.1f} degrees...")
        
        start_time = time.time()
        last_progress_time = start_time
        
        while time.time() - start_time < self.max_turn_time:
            # Get current rotation from gyro integration
            current_rotation = get_rotation_degrees()
            error = target_degrees - current_rotation
            
            # Check if we're close enough
            if abs(error) <= self.rotation_tolerance:
                stop_motors()
                print(f"Turn complete! Current rotation: {current_rotation:+.1f}°")
                return True
            
            # Determine turn direction and speed
            if error > 0:
                # Need to turn left (positive rotation)
                turn_left(self.turn_speed)
                direction = "left"
            else:
                # Need to turn right (negative rotation)
                turn_right(self.turn_speed)
                direction = "right"
            
            # Progress update every second
            if time.time() - last_progress_time >= 1.0:
                print(f"Turning {direction}: target={target_degrees:+.1f}°, "
                      f"current={current_rotation:+.1f}°, error={error:+.1f}°")
                last_progress_time = time.time()
            
            time.sleep(0.05)  # 20Hz control loop
        
        stop_motors()
        current_rotation = get_rotation_degrees()
        print(f"Turn timeout! Current rotation: {current_rotation:+.1f}° (target was {target_degrees:+.1f}°)")
        return False
        print(f"Turn timeout! Final rotation: {current_rotation:+.1f}° (target was {target_degrees:+.1f}°)")
        return False
    
    def move_distance(self, target_cm):
        """Move the robot a specific distance in cm"""
        if target_cm == 0:
            print("No movement requested.")
            return True
            
        print(f"Moving {target_cm:+.1f} cm...")
        
        # Wait for fresh lidar data
        if not is_lidar_data_fresh():
            print("Waiting for lidar data...")
            start_wait = time.time()
            while not is_lidar_data_fresh() and time.time() - start_wait < 5.0:
                time.sleep(0.1)
            
            if not is_lidar_data_fresh():
                print("Warning: No fresh lidar data available")
                return False
        
        # Record starting distance
        start_distance_mm = get_current_distance()
        target_distance_mm = start_distance_mm + (target_cm * 10)  # convert cm to mm
        
        print(f"Start distance: {start_distance_mm} mm, Target: {target_distance_mm} mm")
        
        start_time = time.time()
        last_progress_time = start_time
        
        while time.time() - start_time < self.max_move_time:
            if not is_lidar_data_fresh(max_age_seconds=1.0):
                print("Warning: Lidar data is stale")
                break
            
            current_distance_mm = get_current_distance()
            distance_traveled_mm = current_distance_mm - start_distance_mm
            distance_traveled_cm = distance_traveled_mm / 10.0
            error_cm = target_cm - distance_traveled_cm
            
            # Check if we're close enough
            if abs(error_cm) <= self.distance_tolerance:
                stop_motors()
                print(f"Movement complete! Traveled: {distance_traveled_cm:+.1f} cm")
                return True
            
            # Determine movement direction
            if target_cm > 0:
                # Moving forward
                if error_cm > 0:
                    move_forward(self.move_speed)
                    direction = "forward"
                else:
                    # Overshot, back up
                    move_backward(self.move_speed)
                    direction = "backward (correcting)"
            else:
                # Moving backward
                if error_cm < 0:
                    move_backward(self.move_speed)
                    direction = "backward"
                else:
                    # Overshot, move forward
                    move_forward(self.move_speed)
                    direction = "forward (correcting)"
            
            # Progress update every second
            if time.time() - last_progress_time >= 1.0:
                print(f"Moving {direction}: target={target_cm:+.1f}cm, "
                      f"traveled={distance_traveled_cm:+.1f}cm, error={error_cm:+.1f}cm")
                last_progress_time = time.time()
            
            time.sleep(0.05)  # 20Hz control loop
        
        stop_motors()
        current_distance_mm = get_current_distance()
        distance_traveled_cm = (current_distance_mm - start_distance_mm) / 10.0
        print(f"Movement timeout! Traveled: {distance_traveled_cm:+.1f} cm (target was {target_cm:+.1f} cm)")
        return False
    
    def execute_command(self, rotation_degrees, movement_cm):
        """Execute a rotation followed by movement command"""
        print(f"\n=== EXECUTING COMMAND ===")
        print(f"Rotation: {rotation_degrees:+.1f} degrees")
        print(f"Movement: {movement_cm:+.1f} cm")
        print("=" * 30)
        
        # Wait for robot to be stationary
        self.wait_for_stationary()
        
        # Reset rotation counter for gyro integration
        reset_rotation()
        time.sleep(0.5)  # Give time for reset to take effect
        
        success = True
        
        # Step 1: Rotation
        if rotation_degrees != 0:
            if not self.turn_to_angle(rotation_degrees):
                print("❌ Rotation failed")
                success = False
            else:
                print("✅ Rotation successful")
                time.sleep(0.5)  # Brief pause between operations
        
        # Step 2: Movement
        if movement_cm != 0 and success:
            if not self.move_distance(movement_cm):
                print("❌ Movement failed")
                success = False
            else:
                print("✅ Movement successful")
        
        # Final stop
        stop_motors()
        
        if success:
            print("\n🎉 Command completed successfully!")
        else:
            print("\n⚠️ Command completed with errors")
        
        return success

def interactive_mode():
    """Interactive mode for continuous commands"""
    controller = RobotController()
    
    print("=== ROBOT MOVEMENT CONTROL ===")
    print("Interactive Mode")
    print("Commands:")
    print("  rotation, movement  - Execute movement (e.g., '90, 100')")
    print("  config              - Show current configuration")
    print("  tolerance X, Y      - Set rotation tolerance (X°) and distance tolerance (Y cm)")
    print("  speed X, Y          - Set turn speed (X) and move speed (Y)")
    print("  timeout X, Y        - Set turn timeout (X sec) and move timeout (Y sec)")
    print("Examples:")
    print("  90, 100             - Turn 90° left, move 100cm forward")
    print("  tolerance 5, 3      - Set ±5° rotation tolerance, ±3cm distance tolerance")
    print("  speed 30, 20        - Set turn speed 30, move speed 20")
    print("Type 'quit' or 'q' to exit")
    print()
    
    # Show initial configuration
    controller.show_configuration()
    
    while True:
        try:
            user_input = input("\nEnter command: ").strip()
            
            if user_input.lower() in ('q', 'quit', 'exit'):
                print("Exiting...")
                break
            
            if user_input.lower() == 'config':
                controller.show_configuration()
                continue
            
            if user_input.lower().startswith('tolerance '):
                # Parse tolerance command
                parts = user_input[10:].split(',')
                if len(parts) == 2:
                    rot_tol = float(parts[0].strip())
                    dist_tol = float(parts[1].strip())
                    controller.configure_tolerances(rot_tol, dist_tol)
                else:
                    print("Usage: tolerance rotation_degrees, distance_cm")
                continue
            
            if user_input.lower().startswith('speed '):
                # Parse speed command
                parts = user_input[6:].split(',')
                if len(parts) == 2:
                    turn_speed = int(parts[0].strip())
                    move_speed = int(parts[1].strip())
                    controller.configure_speeds(turn_speed, move_speed)
                else:
                    print("Usage: speed turn_speed, move_speed")
                continue
            
            if user_input.lower().startswith('timeout '):
                # Parse timeout command
                parts = user_input[8:].split(',')
                if len(parts) == 2:
                    turn_timeout = float(parts[0].strip())
                    move_timeout = float(parts[1].strip())
                    controller.configure_timeouts(turn_timeout, move_timeout)
                else:
                    print("Usage: timeout turn_seconds, move_seconds")
                continue
            
            if ',' not in user_input:
                print("Please enter movement command (rotation, movement) or configuration command")
                print("Type 'config' to see current settings")
                continue
            
            # Parse movement command
            parts = user_input.split(',')
            if len(parts) != 2:
                print("Please enter exactly two values: rotation, movement")
                continue
            
            rotation = float(parts[0].strip())
            movement = float(parts[1].strip())
            
            # Execute command
            controller.execute_command(rotation, movement)
            
            # Wait for user before next command
            input("\nPress Enter to continue or Ctrl+C to exit...")
            
        except ValueError:
            print("Please enter valid numbers")
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")

def command_line_mode():
    """Command line mode for single commands"""
    if len(sys.argv) != 3:
        print("Usage: python move_control.py <rotation_degrees> <movement_cm>")
        print("Example: python move_control.py 90 100")
        return False
    
    try:
        rotation = float(sys.argv[1])
        movement = float(sys.argv[2])
        
        controller = RobotController()
        return controller.execute_command(rotation, movement)
        
    except ValueError:
        print("Error: Please provide valid numbers for rotation and movement")
        return False

def main():
    try:
        # Initialize robot control system
        print("Initializing robot control system...")
        init_bot_control(verbose_telemetry=False)
        
        # Give time for telemetry to start
        time.sleep(2)
        
        # Check if command line arguments were provided
        if len(sys.argv) == 3:
            # Command line mode
            success = command_line_mode()
            sys.exit(0 if success else 1)
        else:
            # Interactive mode
            interactive_mode()
            
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cleanup()

if __name__ == '__main__':
    main()
