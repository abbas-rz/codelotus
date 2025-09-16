
# autonomous_rc.py - Enhanced RC control with autonomous mode toggle
import socket, threading, json, time
from pynput import keyboard

RPI_IP = '192.168.0.126'   # <-- set to your Pi IP
RPI_CTRL_PORT = 9000
LOCAL_TELEM_PORT = 9001

ctrl_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
telem_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
telem_sock.bind(('', LOCAL_TELEM_PORT))

seq = 1
key_state = set()

# ----------------------
# Drive config (tuneable)
# ----------------------
MOTOR_MAX_LEFT = 120   # Max command for left motor
MOTOR_MAX_RIGHT = 60  # Max command for right motor (adjust if different RPM)
GEAR_SCALES = [0.33, 0.66, 1.00]
gear_idx = 0  # start in lowest gaear for safety
CRAWL_SCALE = 0.25
FWD_GAIN = 1.0
TURN_GAIN = 0.5

# ----------------------
# Autonomous config
# ----------------------
autonomous_mode = False
MIN_DISTANCE = 25  # cm - minimum distance to obstacle before stopping (less picky)
TURN_DISTANCE = 40  # cm - distance to start slowing down (less picky)
SAFE_DISTANCE = 60  # cm - distance considered safe for full speed (less picky)
TURN_SPEED = 25  # slower turn speed for better scanning
TURN_TIME = 0.3  # shorter turn intervals for smoother scanning
MAX_ROTATIONS = 2  # maximum number of full rotations before giving up

# Global variables for sensor data
current_distance = 0
last_lidar_time = 0
rotation_count = 0  # track how many full rotations we've done

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def send_motor(left, right):
    global seq
    msg = {'type':'motor','left':int(left),'right':int(right),'seq':seq, 'ts': int(time.time()*1000)}
    seq += 1
    ctrl_sock.sendto(json.dumps(msg).encode(), (RPI_IP, RPI_CTRL_PORT))

def stop_motors():
    """Stop both motors"""
    send_motor(0, 0)

def move_forward(speed):
    """Move forward at given speed"""
    left_speed = clamp(speed, 0, MOTOR_MAX_LEFT)
    right_speed = clamp(speed, 0, MOTOR_MAX_RIGHT)
    send_motor(left_speed, right_speed)

def turn_right(speed=TURN_SPEED):
    """Turn right at given speed"""
    left_speed = clamp(speed, 0, MOTOR_MAX_LEFT)
    right_speed = clamp(speed, 0, MOTOR_MAX_RIGHT)
    send_motor(left_speed, -right_speed)

def turn_left(speed=TURN_SPEED):
    """Turn left at given speed"""
    left_speed = clamp(speed, 0, MOTOR_MAX_LEFT)
    right_speed = clamp(speed, 0, MOTOR_MAX_RIGHT)
    send_motor(-left_speed, right_speed)

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
    
    # Base speed from gear - use average of left/right max for calculation
    base_speed = ((MOTOR_MAX_LEFT + MOTOR_MAX_RIGHT) / 2) * GEAR_SCALES[auto_gear_idx]
    
    # Additional modulation based on distance
    if distance < TURN_DISTANCE:
        # Gradually reduce speed as we get closer
        distance_factor = (distance - MIN_DISTANCE) / (TURN_DISTANCE - MIN_DISTANCE)
        distance_factor = max(0.2, distance_factor)  # Minimum 20% speed
        base_speed *= distance_factor
    
    # Reduce overall speed by half for safer autonomous operation
    base_speed *= 1
    
    return int(clamp(base_speed, 0, max(MOTOR_MAX_LEFT, MOTOR_MAX_RIGHT)))

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
        # Turn slowly
        turn_right(TURN_SPEED)
        time.sleep(TURN_TIME)
        stop_motors()
        time.sleep(0.1)  # Brief pause to get stable reading
        
        steps_taken += 1
        
        print(f"Step {steps_taken}: Distance = {current_distance} cm")
        
        # Check if we found a decent path (less picky than before)
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

def telem_loop():
    global current_distance, last_lidar_time
    while True:
        try:
            data, addr = telem_sock.recvfrom(2048)
            telemetry = json.loads(data.decode())
            if telemetry.get('type') == 'tfluna':
                current_distance = telemetry.get('dist_mm', 0)
                last_lidar_time = time.time()
                if autonomous_mode:
                    print(f"LIDAR: {current_distance} cm")
        except Exception as e:
            pass

def on_press(key):
    global gear_idx, autonomous_mode
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
                stop_motors()
            return
            
        # Shift: gear down (one press) unless already in lowest gear, where it acts as crawl while held
        if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
            if autonomous_mode:
                return  # Ignore gear changes in autonomous mode
            if gear_idx == 0:
                key_state.add('SHIFT')  # enable crawl only in lowest gear while held
            else:
                if 'SHIFT_GEAR' not in key_state:  # debounce one-shot gear down
                    key_state.add('SHIFT_GEAR')
                    if gear_idx > 0:
                        gear_idx -= 1
                        print(f"Gear: {gear_idx+1}/{len(GEAR_SCALES)}  scale={GEAR_SCALES[gear_idx]:.2f}")
                    else:
                        print("Already in lowest gear")
            return
            
        # Ctrl: gear up one press at a time
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            if autonomous_mode:
                return  # Ignore gear changes in autonomous mode
            if 'CTRL' not in key_state:  # debounce one-shot gear up
                key_state.add('CTRL')
                if gear_idx < len(GEAR_SCALES) - 1:
                    gear_idx += 1
                    print(f"Gear: {gear_idx+1}/{len(GEAR_SCALES)}  scale={GEAR_SCALES[gear_idx]:.2f}")
                else:
                    print("Already in top gear")
            return
        return
    # normal character keys
    if not autonomous_mode:  # Only accept manual input when not in autonomous mode
        key_state.add(k)

def on_release(key):
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
    
    # Check if we have recent lidar data
    if time.time() - last_lidar_time > 2.0:
        print("Warning: No recent LIDAR data!")
        stop_motors()
        return
    
    # Obstacle avoidance logic
    if current_distance < MIN_DISTANCE:
        # Stop immediately
        stop_motors()
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
        
        move_forward(speed)

def manual_control():
    """Manual control logic (original WASD behavior)"""
    left, right = 0, 0

    # Scale from gear and optional crawl - use average for base calculation
    scale = ((MOTOR_MAX_LEFT + MOTOR_MAX_RIGHT) / 2) * GEAR_SCALES[gear_idx]
    if gear_idx == 0 and 'SHIFT' in key_state:
        scale *= CRAWL_SCALE
    fwd_step = int(scale * FWD_GAIN)
    turn_step = int(scale * TURN_GAIN)

    # WASD behavior preserved
    if 'w' in key_state:
        left += fwd_step; right += fwd_step
    if 's' in key_state:
        left -= fwd_step; right -= fwd_step
    if 'a' in key_state:
        left -= turn_step; right += turn_step
    if 'd' in key_state:
        left += turn_step; right -= turn_step

    # Clamp to respective motor maximums
    left = clamp(left, -MOTOR_MAX_LEFT, MOTOR_MAX_LEFT)
    right = clamp(right, -MOTOR_MAX_RIGHT, MOTOR_MAX_RIGHT)

    send_motor(left, right)

def control_loop():
    """Main control loop - switches between manual and autonomous"""
    print("=== ENHANCED RC CONTROL WITH AUTONOMOUS MODE ===")
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
            stop_motors()
            break

if __name__ == '__main__':
    threading.Thread(target=telem_loop, daemon=True).start()
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    control_loop()
