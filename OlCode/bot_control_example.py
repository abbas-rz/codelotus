#!/usr/bin/env python3
# bot_control_example.py - Example of using advanced.py as a library
"""
Example showing how to use advanced.py as a library for bot control.
This demonstrates basic movement, telemetry reading, and gear control.
"""
import time
import advanced

def example_basic_movements():
    """Demonstrate basic movement functions"""
    print("=== Basic Movement Example ===")
    
    # Initialize the bot control system
    advanced.init_bot_control(verbose_telemetry=True)
    
    print("Starting movement sequence in 3 seconds...")
    time.sleep(3)
    
    # Move forward at speed 60
    print("Moving forward...")
    advanced.move_forward(60)
    time.sleep(2)
    
    # Stop
    print("Stopping...")
    advanced.stop_motors()
    time.sleep(1)
    
    # Turn right
    print("Turning right...")
    advanced.turn_right(40)
    time.sleep(1)
    
    # Stop
    advanced.stop_motors()
    time.sleep(1)
    
    # Turn left
    print("Turning left...")
    advanced.turn_left(40)
    time.sleep(1)
    
    # Stop
    print("Stopping...")
    advanced.stop_motors()

def example_gear_system():
    """Demonstrate gear system usage"""
    print("\n=== Gear System Example ===")
    
    # Test different gears
    for gear in range(3):
        advanced.set_gear(gear)
        speed = advanced.calculate_gear_speed(gear)
        print(f"Gear {gear + 1}: Speed = {speed}")
        
        print(f"Moving forward in gear {gear + 1}...")
        advanced.move_with_gear(forward=True, gear=gear)
        time.sleep(1)
        
        advanced.stop_motors()
        time.sleep(0.5)

def example_lidar_monitoring():
    """Demonstrate LIDAR data reading"""
    print("\n=== LIDAR Monitoring Example ===")
    
    print("Monitoring LIDAR for 10 seconds...")
    start_time = time.time()
    
    while time.time() - start_time < 10:
        distance = advanced.get_current_distance()
        is_fresh = advanced.is_lidar_data_fresh()
        
        print(f"Distance: {distance} cm, Data fresh: {is_fresh}")
        
        # Example: Stop if obstacle too close
        if distance > 0 and distance < 30:
            print("Obstacle detected! Stopping.")
            advanced.stop_motors()
        
        time.sleep(1)

def example_autonomous_behavior():
    """Simple autonomous behavior using the library"""
    print("\n=== Simple Autonomous Example ===")
    
    print("Running simple autonomous behavior for 20 seconds...")
    start_time = time.time()
    
    while time.time() - start_time < 20:
        distance = advanced.get_current_distance()
        
        if not advanced.is_lidar_data_fresh():
            print("No LIDAR data, stopping...")
            advanced.stop_motors()
        elif distance < 30:
            print(f"Obstacle at {distance}cm, turning...")
            advanced.turn_right(30)
        elif distance < 50:
            print(f"Approaching obstacle at {distance}cm, slowing...")
            advanced.move_forward(30)
        else:
            print(f"Clear path at {distance}cm, moving...")
            advanced.move_forward(60)
        
        time.sleep(0.5)
    
    advanced.stop_motors()

def main():
    """Run all examples"""
    try:
        print("Bot Control Library Example")
        print("===========================")
        
        # Run examples
        example_basic_movements()
        example_gear_system()
        example_lidar_monitoring()
        example_autonomous_behavior()
        
        print("\nAll examples completed!")
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        advanced.cleanup()

if __name__ == '__main__':
    main()
