#!/usr/bin/env python3
"""
Fixed Robot Movement Control - uses existing telemetry connection
"""
import time
import sys
import math

# Import everything we need from advanced
from advanced import (
    init_bot_control, cleanup, get_latest_encoders, move_by_ticks,
    stop_motors, is_encoder_data_available, wait_for_encoder_data
)
from calibration_config import load_pulses_per_degree

class RobotController:
    def __init__(self):
        # Robot specifications
        self.PPR = 1500  # Pulses per rotation
        self.WHEEL_DIAMETER = 4.4  # cm
        self.WHEEL_CIRCUMFERENCE = math.pi * self.WHEEL_DIAMETER  # cm per rotation
        self.PULSES_PER_CM = self.PPR / self.WHEEL_CIRCUMFERENCE  # pulses per cm of wheel travel
        self.PULSES_PER_DEGREE = load_pulses_per_degree()
        
        # Control parameters
        self.rotation_tolerance = 2.0  # degrees - allow ±2 degree error
        self.distance_tolerance = 1.0  # cm
        self.turn_speed = 30  # motor speed for turning
        self.move_speed = 30  # motor speed for movement
        self.max_turn_time = 30.0  # maximum time to attempt a turn (seconds)
        self.max_move_time = 30.0  # maximum time to attempt a move (seconds)
        
        print(f"Robot Encoder Specs:")
        print(f"  PPR: {self.PPR}")
        print(f"  Wheel diameter: {self.WHEEL_DIAMETER} cm")
        print(f"  Wheel circumference: {self.WHEEL_CIRCUMFERENCE:.2f} cm")
        print(f"  Pulses per cm: {self.PULSES_PER_CM:.2f}")
        print(f"  Pulses per degree rotation: {self.PULSES_PER_DEGREE}")

    def test_encoder_connection(self):
        """Test if encoder data is available"""
        print("\n🔍 Testing Encoder Connection...")
        print("=" * 40)
        
        if is_encoder_data_available():
            encoders, enc_time = get_latest_encoders()
            current_time = time.time()
            age = current_time - enc_time
            
            print(f"✅ Encoder data available:")
            print(f"   m1={encoders['m1']}, m2={encoders['m2']}")
            print(f"   m3={encoders['m3']}, m4={encoders['m4']}")
            print(f"   Age: {age:.1f} seconds")
            return True
        else:
            print("❌ No recent encoder data")
            print("Waiting for encoder data...")
            
            if wait_for_encoder_data(timeout=5.0):
                encoders, enc_time = get_latest_encoders()
                print(f"✅ Encoder data now available:")
                print(f"   m1={encoders['m1']}, m2={encoders['m2']}")
                return True
            else:
                print("❌ Still no encoder data after waiting")
                return False

    def execute_simple_test(self, rotation_degrees):
        """Execute a simple rotation test"""
        print(f"\n=== SIMPLE ROTATION TEST ===")
        print(f"Rotation: {rotation_degrees:+.1f} degrees")
        print("=" * 30)
        
        # Test encoder connection first
        if not self.test_encoder_connection():
            print("❌ Cannot proceed without encoder data")
            return False
        
        # Get initial position
        encoders, _ = get_latest_encoders()
        initial_left = encoders['m1']
        initial_right = encoders['m2']
        
        print(f"Initial position: L={initial_left}, R={initial_right}")
        
        # Calculate target ticks for rotation
        target_ticks = int(abs(rotation_degrees) * self.PULSES_PER_DEGREE)
        
        print(f"Target rotation: {target_ticks} ticks")
        
        # Simple rotation using move_by_ticks
        if rotation_degrees > 0:
            # Left turn: left motor backward, right motor forward
            left_ticks = -target_ticks
            right_ticks = target_ticks
        else:
            # Right turn: left motor forward, right motor backward
            left_ticks = target_ticks
            right_ticks = -target_ticks
        
        print(f"Executing: left={left_ticks}, right={right_ticks}")
        
        try:
            success = move_by_ticks(left_ticks, right_ticks, speed=self.turn_speed)
            if success:
                print("✅ Rotation completed")
                
                # Check final position
                time.sleep(0.5)  # Let encoders update
                encoders, _ = get_latest_encoders()
                final_left = encoders['m1']
                final_right = encoders['m2']
                
                actual_left = final_left - initial_left
                actual_right = final_right - initial_right
                
                print(f"Final position: L={final_left}, R={final_right}")
                print(f"Actual movement: L={actual_left}, R={actual_right}")
                
                return True
            else:
                print("❌ Rotation failed")
                return False
                
        except Exception as e:
            print(f"❌ Error during rotation: {e}")
            return False

def main():
    try:
        print("🤖 Simple Robot Movement Test")
        print("=" * 40)
        
        # Don't reinitialize - use existing connection
        print("Using existing telemetry connection...")
        
        controller = RobotController()
        
        if len(sys.argv) == 2:
            # Command line mode - just rotation
            try:
                rotation = float(sys.argv[1])
                success = controller.execute_simple_test(rotation)
                sys.exit(0 if success else 1)
            except ValueError:
                print("Error: Please provide a valid number for rotation")
                sys.exit(1)
        else:
            # Interactive mode
            print("\nInteractive mode:")
            print("Enter rotation in degrees (e.g., 90, -45)")
            print("Type 'quit' to exit")
            
            while True:
                try:
                    user_input = input("\nRotation: ").strip()
                    if user_input.lower() in ['quit', 'q', 'exit']:
                        break
                    
                    rotation = float(user_input)
                    controller.execute_simple_test(rotation)
                    
                except ValueError:
                    print("Please enter a valid number")
                except KeyboardInterrupt:
                    print("\nExiting...")
                    break
                except Exception as e:
                    print(f"Error: {e}")
        
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    finally:
        stop_motors()

if __name__ == '__main__':
    main()