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
    stop_motors, is_encoder_data_available, wait_for_encoder_data
)

class RobotController:
    def __init__(self):
        # Robot specifications
        self.PPR = 1500  # Pulses per rotation
        self.WHEEL_DIAMETER = 4.4  # cm
        self.WHEEL_CIRCUMFERENCE = math.pi * self.WHEEL_DIAMETER  # cm per rotation
        self.PULSES_PER_CM = self.PPR / self.WHEEL_CIRCUMFERENCE  # pulses per cm of wheel travel
        self.PULSES_PER_DEGREE = 22.3  # pulses per degree of bot rotation
        
        # Control parameters
        self.rotation_tolerance = 2.0  # degrees - allow ±2 degree error
        self.distance_tolerance = 1.0  # cm
        self.turn_speed = 60  # motor speed for turning
        self.move_speed = 60  # motor speed for movement
        self.max_turn_time = 10.0  # maximum time to attempt a turn (seconds)
        self.max_move_time = 30.0  # maximum time to attempt a move (seconds)
        
        print(f"Robot Encoder Specs:")
        print(f"  PPR: {self.PPR}")
        print(f"  Wheel diameter: {self.WHEEL_DIAMETER} cm")
        print(f"  Wheel circumference: {self.WHEEL_CIRCUMFERENCE:.2f} cm")
        print(f"  Pulses per cm: {self.PULSES_PER_CM:.2f}")
        print(f"  Pulses per degree rotation: {self.PULSES_PER_DEGREE}")
    
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
        
    def test_esp32_connection(self):
        """Test connection to ESP32 and display status"""
        print("\n🔍 Testing ESP32 Connection...")
        print("=" * 40)
        
        # Use the shared function from advanced.py
        if is_encoder_data_available():
            encoders, enc_time = get_latest_encoders()
            current_time = time.time()
            age = current_time - enc_time
            print(f"📊 Latest encoder data:")
            print(f"   m1={encoders['m1']}, m2={encoders['m2']}")
            print(f"   m3={encoders['m3']}, m4={encoders['m4']}")
            print(f"   Age: {age:.1f} seconds")
            print("✅ Connection is good!")
            return True
        else:
            print("❌ No encoder data available")
            return False

    def get_encoder_position(self):
        """Get current encoder positions for left and right motors"""
        encoders, _ = get_latest_encoders()
        # For 2-motor system: m1=left, m2=right
        left_enc = encoders.get('m1', 0)
        right_enc = encoders.get('m2', 0)
        return left_enc, right_enc
        
    def reset_encoder_reference(self):
        """Set current encoder position as reference point"""
        self.start_left, self.start_right = self.get_encoder_position()
        print(f"Encoder reference set: left={self.start_left}, right={self.start_right}")
        
    def get_relative_position(self):
        """Get encoder position relative to reference point"""
        current_left, current_right = self.get_encoder_position()
        rel_left = current_left - self.start_left
        rel_right = current_right - self.start_right
        return rel_left, rel_right
        
    def turn_to_angle(self, target_degrees):
        """Turn the robot to a specific angle using encoder differential"""
        print(f"Turning to {target_degrees:+.1f} degrees...")
        
        # Calculate target encoder difference for rotation (relative ticks)
        turn_ticks = int(abs(target_degrees) * self.PULSES_PER_DEGREE)
        if turn_ticks == 0:
            print("No rotation requested.")
            return True

        direction = 1 if target_degrees > 0 else -1
        left_target_pulses = direction * turn_ticks
        right_target_pulses = -direction * turn_ticks

        # Determine signed motor speeds so each side spins in the proper direction
        left_speed = -self.turn_speed if left_target_pulses < 0 else self.turn_speed
        right_speed = -self.turn_speed if right_target_pulses < 0 else self.turn_speed

        print(f"Target pulses: left={left_target_pulses}, right={right_target_pulses}")
        print(f"Turn speeds: left={left_speed}, right={right_speed}")
        
        # Set reference point for monitoring progress
        self.reset_encoder_reference()
        
        # Send relative move command to the Pi controller
        move_by_ticks(left_target_pulses, right_target_pulses, left_speed, right_speed)
        
        # Monitor progress
        start_time = time.time()
        last_progress_time = start_time
        
        while time.time() - start_time < self.max_turn_time:
            rel_left, rel_right = self.get_relative_position()
            
            # Calculate current rotation based on encoder difference
            avg_pulses = (abs(rel_left) + abs(rel_right)) / 2.0
            current_rotation = avg_pulses / self.PULSES_PER_DEGREE
            if target_degrees < 0:
                current_rotation = -current_rotation
                
            error = target_degrees - current_rotation
            
            # Check if we're close enough
            if abs(error) <= self.rotation_tolerance:
                stop_motors()
                print(f"Turn complete! Current rotation: {current_rotation:+.1f}°")
                return True
            
            # Progress update every second
            if time.time() - last_progress_time >= 1.0:
                print(f"Turning: target={target_degrees:+.1f}°, current={current_rotation:+.1f}°, error={error:+.1f}°")
                print(f"  Encoder deltas: left={rel_left}, right={rel_right}")
                last_progress_time = time.time()
            
            time.sleep(0.1)  # 10Hz monitoring
        
        stop_motors()
        rel_left, rel_right = self.get_relative_position()
        avg_pulses = (abs(rel_left) + abs(rel_right)) / 2.0
        final_rotation = avg_pulses / self.PULSES_PER_DEGREE
        if target_degrees < 0:
            final_rotation = -final_rotation
        print(f"Turn timeout! Final rotation: {final_rotation:+.1f}° (target was {target_degrees:+.1f}°)")
        return False
    
    def move_distance(self, target_cm):
        """Move the robot a specific distance in cm using encoders"""
        if target_cm == 0:
            print("No movement requested.")
            return True
            
        print(f"Moving {target_cm:+.1f} cm...")
        
        # Calculate target pulses
        target_pulses = int(target_cm * self.PULSES_PER_CM)
        
        print(f"Target pulses: {target_pulses} ({target_cm:.1f} cm)")
        
        # Set reference point
        self.reset_encoder_reference()
        
        # Send move_ticks command using relative ticks
        speed = self.move_speed if target_cm > 0 else -self.move_speed
        move_by_ticks(target_pulses, target_pulses, speed, speed)
        
        # Monitor progress
        start_time = time.time()
        last_progress_time = start_time
        
        direction = 1 if target_cm >= 0 else -1
        target_distance = float(target_cm)

        while time.time() - start_time < self.max_move_time:
            rel_left, rel_right = self.get_relative_position()
            
            # Calculate distance traveled using absolute encoder deltas
            avg_abs_pulses = (abs(rel_left) + abs(rel_right)) / 2.0
            distance_traveled = (avg_abs_pulses / self.PULSES_PER_CM) * direction
            error_cm = target_distance - distance_traveled
            
            # Check if we're close enough
            if abs(error_cm) <= self.distance_tolerance:
                stop_motors()
                print(f"Movement complete! Traveled: {distance_traveled:+.1f} cm")
                return True
            
            # Progress update every second
            if time.time() - last_progress_time >= 1.0:
                print(f"Moving: target={target_cm:+.1f}cm, traveled={distance_traveled:+.1f}cm, error={error_cm:+.1f}cm")
                print(f"  Encoder deltas: left={rel_left}, right={rel_right}")
                last_progress_time = time.time()
            
            time.sleep(0.1)  # 10Hz monitoring
        
        stop_motors()
        rel_left, rel_right = self.get_relative_position()
        avg_abs_pulses = (abs(rel_left) + abs(rel_right)) / 2.0
        distance_traveled = (avg_abs_pulses / self.PULSES_PER_CM) * direction
        print(f"Movement timeout! Traveled: {distance_traveled:+.1f} cm (target was {target_cm:+.1f} cm)")
        return False
    
    def execute_command(self, rotation_degrees, movement_cm):
        """Execute a rotation followed by movement command"""
        print(f"\n=== EXECUTING COMMAND ===")
        print(f"Rotation: {rotation_degrees:+.1f} degrees")
        print(f"Movement: {movement_cm:+.1f} cm")
        print("=" * 30)
        
        # Test ESP32 connection first
        if not self.test_esp32_connection():
            # If connection test fails, try waiting for data
            print("\n⏳ Waiting for ESP32 data...")
            if not wait_for_encoder_data():
                print("❌ No encoder data available")
                return False
        
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

def interactive_mode(controller):
    """Interactive mode for continuous commands"""
    
    print("=== ENCODER-BASED ROBOT MOVEMENT CONTROL ===")
    print("Pure encoder navigation system")
    print("Commands:")
    print("  rotation, movement  - Execute movement (e.g., '90, 100')")
    print("  config              - Show current configuration")
    print("  tolerance X, Y      - Set rotation tolerance (X°) and distance tolerance (Y cm)")
    print("  speed X, Y          - Set turn speed (X) and move speed (Y)")
    print("  timeout X, Y        - Set turn timeout (X sec) and move timeout (Y sec)")
    print("  encoders            - Show current encoder values")
    print("Examples:")
    print("  90, 100             - Turn 90° left, move 100cm forward")
    print("  -45, -50            - Turn 45° right, move 50cm backward")
    print("  tolerance 2, 1      - Set ±2° rotation tolerance, ±1cm distance tolerance")
    print("  speed 40, 30        - Set turn speed 40, move speed 30")
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
            
            if user_input.lower() == 'encoders':
                encoders, enc_time = get_latest_encoders()
                print(f"\n=== CURRENT ENCODER VALUES ===")
                print(f"m1 (left): {encoders['m1']}")
                print(f"m2 (right): {encoders['m2']}")
                print(f"m3: {encoders['m3']}")
                print(f"m4: {encoders['m4']}")
                print(f"Timestamp: {enc_time}")
                print("=" * 30)
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

def command_line_mode(controller):
    """Command line mode for single commands"""
    if len(sys.argv) != 3:
        print("Usage: python move_control.py <rotation_degrees> <movement_cm>")
        print("Example: python move_control.py 90 100")
        return False
    
    try:
        rotation = float(sys.argv[1])
        movement = float(sys.argv[2])
        
        return controller.execute_command(rotation, movement)
        
    except ValueError:
        print("Error: Please provide valid numbers for rotation and movement")
        return False

def main():
    try:
        # Initialize robot control system
        print("Initializing robot control system...")
        init_bot_control(verbose_telemetry=False)  # Enable verbose to see what's happening
        
        # Give more time for telemetry to start and receive data
        print("Waiting for ESP32 connection and telemetry data...")
        time.sleep(5)  # Increased from 2 to 5 seconds
        
        # Test connection before proceeding
        controller = RobotController()
        print("\n" + "="*50)
        print("🤖 ROBOT CONTROL SYSTEM")
        print("="*50)
        
        if not controller.test_esp32_connection():
            print("\n⚠️ ESP32 connection issues detected!")
            print("Please check:")
            print("1. ESP32 is powered on")
            print("2. Connected to 'ESP32-FruitBot' WiFi")
            print("3. ESP32 firmware uploaded correctly")
            print("\nTrying to continue anyway...")
        
        # Check if command line arguments were provided
        if len(sys.argv) == 3:
            # Command line mode
            success = command_line_mode(controller)
            sys.exit(0 if success else 1)
        else:
            # Interactive mode
            interactive_mode(controller)
            
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cleanup()

if __name__ == '__main__':
    main()
