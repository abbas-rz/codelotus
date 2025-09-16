#!/usr/bin/env python3
# test_advanced.py - Test script for advanced.py library
"""
Test script to verify all functions in the advanced.py library work correctly.
Run this to make sure your bot setup is working before using other programs.
"""
import time
import threading
from pynput import keyboard
import advanced

# Test state
test_running = False
current_test = 0
test_list = [
    "Motor Control Test",
    "Telemetry Test", 
    "Gear System Test",
    "Navigation Test",
    "LIDAR Test"
]

def print_header(title):
    """Print a nice header for test sections"""
    print("\n" + "="*50)
    print(f"  {title}")
    print("="*50)

def motor_test():
    """Test basic motor control functions"""
    print_header("MOTOR CONTROL TEST")
    print("Testing basic motor commands...")
    
    print("1. Stop motors")
    advanced.stop_motors()
    time.sleep(1)
    
    print("2. Move forward (slow)")
    advanced.move_forward(30)
    time.sleep(2)
    
    print("3. Turn left")
    advanced.turn_left(40)
    time.sleep(1)
    
    print("4. Turn right") 
    advanced.turn_right(40)
    time.sleep(1)
    
    print("5. Differential steering test")
    advanced.send_motor_differential(20, 40)  # Turn left while moving
    time.sleep(1)
    
    print("6. Stop motors")
    advanced.stop_motors()
    print("✅ Motor control test complete!")

def telemetry_test():
    """Test telemetry functions"""
    print_header("TELEMETRY TEST")
    print("Testing telemetry data...")
    
    for i in range(5):
        distance = advanced.get_current_distance()
        fresh = advanced.is_lidar_data_fresh()
        print(f"Distance: {distance} cm, Data fresh: {fresh}")
        time.sleep(1)
    
    print("✅ Telemetry test complete!")

def gear_test():
    """Test gear system"""
    print_header("GEAR SYSTEM TEST")
    print("Testing gear system...")
    
    print("Starting gear:", advanced.get_current_gear())
    
    print("Gear up test:")
    for i in range(3):
        advanced.gear_up()
        gear = advanced.get_current_gear()
        speed = advanced.calculate_gear_speed()
        print(f"  Gear {gear}: Speed scale {speed}")
        time.sleep(0.5)
    
    print("Gear down test:")
    for i in range(4):
        advanced.gear_down()
        gear = advanced.get_current_gear()
        speed = advanced.calculate_gear_speed()
        print(f"  Gear {gear}: Speed scale {speed}")
        time.sleep(0.5)
    
    print("Crawl mode test:")
    crawl_speed = advanced.calculate_gear_speed(crawl=True)
    print(f"  Crawl speed: {crawl_speed}")
    
    print("✅ Gear system test complete!")

def navigation_test():
    """Test navigation functions"""
    print_header("NAVIGATION TEST")
    print("Testing navigation with obstacle avoidance...")
    print("This will move the bot forward and stop if obstacles detected")
    print("Press 'q' to skip this test")
    
    # Simple navigation test
    for i in range(10):
        distance = advanced.get_current_distance()
        
        if distance < 30:
            print(f"Obstacle detected at {distance} cm - stopping!")
            advanced.stop_motors()
            break
        elif distance < 50:
            print(f"Slow approach - distance: {distance} cm")
            advanced.move_forward(20)
        else:
            print(f"Clear path - distance: {distance} cm")
            advanced.move_forward(40)
        
        time.sleep(0.5)
    
    advanced.stop_motors()
    print("✅ Navigation test complete!")

def lidar_test():
    """Test LIDAR data reception"""
    print_header("LIDAR DATA TEST")
    print("Testing LIDAR data reception for 10 seconds...")
    print("You should see distance readings updating regularly")
    
    start_time = time.time()
    reading_count = 0
    
    while time.time() - start_time < 10:
        if advanced.is_lidar_data_fresh():
            distance = advanced.get_current_distance()
            reading_count += 1
            print(f"Reading {reading_count}: {distance} cm")
        else:
            print("No fresh LIDAR data...")
        time.sleep(0.5)
    
    print(f"✅ LIDAR test complete! Received {reading_count} readings in 10 seconds")

def on_press(key):
    """Handle key presses during testing"""
    global test_running
    
    try:
        if key.char == 'q':
            print("\nTest skipped by user")
            test_running = False
            return False
    except AttributeError:
        if key == keyboard.Key.esc:
            print("\nTesting stopped by user")
            test_running = False
            return False

def run_interactive_test():
    """Run interactive test where user chooses tests"""
    print_header("INTERACTIVE TEST MODE")
    print("Available tests:")
    for i, test_name in enumerate(test_list):
        print(f"  {i+1}. {test_name}")
    print("  0. Run all tests")
    print("  q. Quit")
    
    while True:
        try:
            choice = input("\nSelect test to run (0-5, q): ").strip().lower()
            
            if choice == 'q':
                break
            elif choice == '0':
                run_all_tests()
                break
            elif choice in ['1', '2', '3', '4', '5']:
                test_num = int(choice) - 1
                run_single_test(test_num)
            else:
                print("Invalid choice. Please enter 0-5 or q")
                
        except KeyboardInterrupt:
            print("\nTesting interrupted")
            break

def run_single_test(test_num):
    """Run a single test by number"""
    global test_running
    test_running = True
    
    if test_num == 0:
        motor_test()
    elif test_num == 1:
        telemetry_test()
    elif test_num == 2:
        gear_test()
    elif test_num == 3:
        navigation_test()
    elif test_num == 4:
        lidar_test()

def run_all_tests():
    """Run all tests in sequence"""
    global test_running
    
    print_header("RUNNING ALL TESTS")
    print("Press ESC to stop testing at any time")
    print("Press 'q' to skip current test")
    
    for i, test_name in enumerate(test_list):
        test_running = True
        print(f"\nStarting {test_name}...")
        time.sleep(1)
        
        if not test_running:
            break
            
        run_single_test(i)
        
        if not test_running:
            break
            
        print(f"{test_name} finished. Next test in 3 seconds...")
        time.sleep(3)
    
    print_header("ALL TESTS COMPLETE")

def main():
    """Main test program"""
    print_header("ADVANCED.PY LIBRARY TEST SUITE")
    print("This script will test all functions in the advanced.py library")
    print("Make sure your bot is connected and ready before starting")
    
    try:
        # Initialize the advanced module
        print("\nInitializing bot control...")
        advanced.init_bot_control(verbose_telemetry=True)
        print("✅ Bot control initialized successfully!")
        
        # Start keyboard listener
        listener = keyboard.Listener(on_press=on_press)
        listener.start()
        
        # Wait a moment for initialization
        time.sleep(2)
        
        # Run interactive test
        run_interactive_test()
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nCleaning up...")
        advanced.cleanup()
        print("✅ Cleanup complete")

if __name__ == '__main__':
    main()
