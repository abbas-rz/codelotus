#!/usr/bin/env python3
# autonomous_rc_modular.py - Modular autonomous RC control using advanced.py
import time
from pynput import keyboard
import advanced

# ----------------------
# Autonomous config
# ----------------------
autonomous_mode = False
MIN_DISTANCE = 25  # cm - minimum distance to obstacle before stopping
TURN_DISTANCE = 40  # cm - distance to start slowing down
SAFE_DISTANCE = 60  # cm - distance considered safe for full speed
TURN_SPEED = 25  # slower turn speed for better scanning
TURN_TIME = 0.3  # shorter turn intervals for smoother scanning
MAX_ROTATIONS = 2  # maximum number of full rotations before giving up

# Global variables for autonomous state
rotation_count = 0  # track how many full rotations we've done
key_state = set()

def calculate_autonomous_gear_from_distance(distance):
    """Calculate appropriate gear based on available space in autonomous mode"""
    if distance < MIN_DISTANCE:
        return 0  # Stop
    elif distance < TURN_DISTANCE:
        return 0  # Lowest gear (crawl)
    elif distance < SAFE_DISTANCE:
        return 1  # Medium gear
    else:
        return 2  # High gear

def calculate_autonomous_speed_from_distance(distance):
    """Calculate motor speed based on distance and gear in autonomous mode"""
    auto_gear_idx = calculate_autonomous_gear_from_distance(distance)
    
    if distance < MIN_DISTANCE:
        return 0  # Stop completely
    
    # Use gear system from advanced module
    speed = advanced.calculate_gear_speed(auto_gear_idx)
    
    # Additional modulation based on distance
    if distance < TURN_DISTANCE:
        # Gradually reduce speed as we get closer
        distance_factor = (distance - MIN_DISTANCE) / (TURN_DISTANCE - MIN_DISTANCE)
        distance_factor = max(0.2, distance_factor)  # Minimum 20% speed
        speed *= distance_factor
    
    # Reduce overall speed for safer autonomous operation
    speed *= 0.8
    
    return int(speed)

def find_clear_path():
    """Simple optimized path finding with slow turning and rotation limit"""
    global rotation_count
    
    print(f"Obstacle detected! Searching for clear path... (Rotation {rotation_count + 1}/{MAX_ROTATIONS})")
    
    # Check if we've already rotated too many times
    if rotation_count >= MAX_ROTATIONS:
        print("Maximum rotations reached. Giving up to avoid endless spinning.")
        return False
    
    steps_taken = 0
    max_steps_per_rotation = 16  # About 22.5 degrees per step for full 360
    
    # Start turning slowly and continuously check for clear path
    while steps_taken < max_steps_per_rotation:
        # Turn slowly using advanced module
        advanced.turn_right(TURN_SPEED)
        time.sleep(TURN_TIME)
        advanced.stop_motors()
        time.sleep(0.1)  # Brief pause to get stable reading
        
        steps_taken += 1
        current_distance = advanced.get_current_distance()
        
        print(f"Step {steps_taken}: Distance = {current_distance} cm")
        
        # Check if we found a decent path
        if current_distance > MIN_DISTANCE + 10:  # Just need 35cm clearance
            print(f"Clear path found! Distance: {current_distance} cm after {steps_taken} steps")
            return True
    
    # Completed one full rotation
    rotation_count += 1
    print(f"Completed rotation {rotation_count}/{MAX_ROTATIONS}")
    
    # If we haven't found a path and haven't hit max rotations, try again
    if rotation_count < MAX_ROTATIONS:
        print("No clear path found, trying another rotation...")
        return find_clear_path()
    else:
        print("No clear path found after maximum rotations")
        return False

def on_press(key):
    """Handle key press events"""
    global autonomous_mode
    
    try:
        k = key.char
    except AttributeError:
        # ESC: Toggle autonomous mode
        if key == keyboard.Key.esc:
            autonomous_mode = not autonomous_mode
            if autonomous_mode:
                print("=== AUTONOMOUS MODE ACTIVATED ===")
                print(f"Min distance: {MIN_DISTANCE} cm")
                print(f"Turn distance: {TURN_DISTANCE} cm") 
                print(f"Safe distance: {SAFE_DISTANCE} cm")
                print("Press ESC again to return to manual control")
            else:
                print("=== MANUAL MODE ACTIVATED ===")
                advanced.stop_motors()
            return
            
        # Pass gear changes to advanced module
        if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
            if autonomous_mode:
                return  # Ignore gear changes in autonomous mode
            if advanced.get_current_gear() == 0:
                key_state.add('SHIFT')  # enable crawl only in lowest gear while held
            else:
                if 'SHIFT_GEAR' not in key_state:  # debounce one-shot gear down
                    key_state.add('SHIFT_GEAR')
                    advanced.gear_down()
            return
            
        # Ctrl: gear up one press at a time
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            if autonomous_mode:
                return  # Ignore gear changes in autonomous mode
            if 'CTRL' not in key_state:  # debounce one-shot gear up
                key_state.add('CTRL')
                advanced.gear_up()
            return
        return
    
    # normal character keys
    if not autonomous_mode:  # Only accept manual input when not in autonomous mode
        key_state.add(k)

def on_release(key):
    """Handle key release events"""
    try:
        k = key.char
    except AttributeError:
        if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
            if 'SHIFT' in key_state:
                key_state.remove('SHIFT')
            if 'SHIFT_GEAR' in key_state:
                key_state.remove('SHIFT_GEAR')
            return
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            if 'CTRL' in key_state:
                key_state.remove('CTRL')
            return
        return
    if k in key_state:
        key_state.remove(k)
    if k == 'q':
        print("Quit requested")
        return False

def autonomous_control():
    """Autonomous navigation logic"""
    global rotation_count
    
    # Check if we have recent lidar data using advanced module
    if not advanced.is_lidar_data_fresh():
        print("Warning: No recent LIDAR data!")
        advanced.stop_motors()
        return
    
    current_distance = advanced.get_current_distance()
    
    # Obstacle avoidance logic
    if current_distance < MIN_DISTANCE:
        # Stop immediately
        advanced.stop_motors()
        print(f"STOP! Obstacle at {current_distance} cm")
        
        # Try to find a clear path
        if find_clear_path():
            print("Clear path found! Resuming forward movement...")
            # Reset rotation counter on successful path finding
            rotation_count = 0
        else:
            print("Stuck! Switching to manual mode.")
            global autonomous_mode
            autonomous_mode = False
            # Reset rotation counter when giving up
            rotation_count = 0
            
    else:
        # Calculate appropriate speed based on distance
        speed = calculate_autonomous_speed_from_distance(current_distance)
        auto_gear = calculate_autonomous_gear_from_distance(current_distance)
        
        # Reset rotation counter when moving forward successfully
        if rotation_count > 0:
            print("Successfully moving forward, resetting rotation counter")
            rotation_count = 0
        
        print(f"Moving forward - Distance: {current_distance} cm, "
              f"Auto Gear: {auto_gear + 1}, Speed: {speed}")
        
        advanced.move_forward(speed)

def manual_control():
    """Manual control logic using advanced module functions"""
    left, right = 0, 0

    # Use advanced module's gear system
    scale = advanced.calculate_gear_speed(crawl=('SHIFT' in key_state))
    fwd_step = int(scale * advanced.FWD_GAIN)
    turn_step = int(scale * advanced.TURN_GAIN)

    # WASD behavior preserved
    if 'w' in key_state:
        left += fwd_step; right += fwd_step
    if 's' in key_state:
        left -= fwd_step; right -= fwd_step
    if 'a' in key_state:
        left -= turn_step; right += turn_step
    if 'd' in key_state:
        left += turn_step; right -= turn_step

    # Send using advanced module's differential motor function
    advanced.send_motor_differential(left, right)

def control_loop():
    """Main control loop - switches between manual and autonomous"""
    print("=== MODULAR AUTONOMOUS RC CONTROL ===")
    print("Manual Controls:")
    print("  WASD - Movement")
    print("  Shift - Gear down / Crawl mode")
    print("  Ctrl - Gear up")
    print("  ESC - Toggle autonomous mode")
    print("  Q - Quit")
    print("\nStarting in manual mode...")
    
    while True:
        try:
            if autonomous_mode:
                autonomous_control()
            else:
                manual_control()
            
            time.sleep(0.05)
            
        except KeyboardInterrupt:
            print("\nShutting down...")
            advanced.stop_motors()
            break

if __name__ == '__main__':
    try:
        # Initialize using advanced module
        advanced.init_bot_control(verbose_telemetry=False)  # Quiet telemetry in autonomous mode
        
        # Start keyboard listener
        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        
        # Run main control loop
        control_loop()
        
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        advanced.cleanup()
