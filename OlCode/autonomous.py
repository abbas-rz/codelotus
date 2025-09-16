#!/usr/bin/env python3
# autonomous.py - Basic autonomous navigation algorithm
import socket, threading, json, time, random

RPI_IP = '192.168.0.126'   # <-- set to your Pi IP
RPI_CTRL_PORT = 9000
LOCAL_TELEM_PORT = 9001

ctrl_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
telem_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
telem_sock.bind(('', LOCAL_TELEM_PORT))

seq = 1

# ----------------------
# Drive config
# ----------------------
MOTOR_MAX_LEFT = 120   # Max command for left motor
MOTOR_MAX_RIGHT = 120  # Max command for right motor (adjust if different RPM)

# 3 gears splitting ~600 RPM meaningfully: ~200, ~400, ~600 (as fractions of max)
GEAR_SCALES = [0.33, 0.66, 1.00]

# ----------------------
# Autonomous config
# ----------------------
MIN_DISTANCE = 25  # cm - minimum distance to obstacle before stopping (less picky)
TURN_DISTANCE = 40  # cm - distance to start slowing down (less picky)
SAFE_DISTANCE = 60  # cm - distance considered safe for full speed (less picky)

# Turn parameters
TURN_SPEED = 25  # slower turn speed for better scanning
TURN_TIME = 0.3  # shorter turn intervals for smoother scanning
MAX_ROTATIONS = 2  # maximum number of full rotations before giving up

# Global variables for sensor data
current_distance = 0
last_lidar_time = 0
autonomous_active = True
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

def calculate_gear_from_distance(distance):
    """Calculate appropriate gear based on available space"""
    if distance < MIN_DISTANCE:
        return 0  # Stop
    elif distance < TURN_DISTANCE:
        return 0  # Lowest gear (crawl)
    elif distance < SAFE_DISTANCE:
        return 1  # Medium gear
    else:
        return 2  # High gear

def calculate_speed_from_distance(distance):
    """Calculate motor speed based on distance and gear"""
    gear_idx = calculate_gear_from_distance(distance)
    
    if distance < MIN_DISTANCE:
        return 0  # Stop completely
    
    # Base speed from gear - use average of left/right max for calculation
    base_speed = ((MOTOR_MAX_LEFT + MOTOR_MAX_RIGHT) / 2) * GEAR_SCALES[gear_idx]
    
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
    """Handle incoming telemetry data"""
    global current_distance, last_lidar_time
    
    while True:
        try:
            data, addr = telem_sock.recvfrom(2048)
            telemetry = json.loads(data.decode())
            
            if telemetry.get('type') == 'tfluna':
                current_distance = telemetry.get('dist_mm', 0)
                last_lidar_time = time.time()
                print(f"LIDAR: {current_distance} cm")
                
        except Exception as e:
            print(f"Telemetry error: {e}")

def autonomous_loop():
    """Main autonomous navigation loop"""
    global autonomous_active, rotation_count
    
    print("=== AUTONOMOUS NAVIGATION STARTED ===")
    print(f"Min distance: {MIN_DISTANCE} cm")
    print(f"Turn distance: {TURN_DISTANCE} cm")
    print(f"Safe distance: {SAFE_DISTANCE} cm")
    print(f"Max rotations: {MAX_ROTATIONS}")
    print("Press Ctrl+C to stop\n")
    
    while autonomous_active:
        try:
            # Check if we have recent lidar data
            if time.time() - last_lidar_time > 2.0:
                print("Warning: No recent LIDAR data!")
                stop_motors()
                time.sleep(0.5)
                continue
            
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
                    print("Stuck! Stopping autonomous mode.")
                    autonomous_active = False
                    # Reset rotation counter when giving up
                    rotation_count = 0
                    break
                    
            else:
                # Calculate appropriate speed based on distance
                speed = calculate_speed_from_distance(current_distance)
                gear = calculate_gear_from_distance(current_distance)
                
                # Reset rotation counter when moving forward successfully
                if rotation_count > 0:
                    print("Successfully moving forward, resetting rotation counter")
                    rotation_count = 0
                
                print(f"Moving forward - Distance: {current_distance} cm, "
                      f"Gear: {gear + 1}, Speed: {speed}")
                
                move_forward(speed)
            
            time.sleep(0.1)  # Main loop delay
            
        except KeyboardInterrupt:
            print("\nAutonomous navigation stopped by user")
            autonomous_active = False
            break
        except Exception as e:
            print(f"Autonomous loop error: {e}")
            stop_motors()
            time.sleep(1)
    
    # Cleanup
    stop_motors()
    print("Autonomous navigation stopped")

def main():
    """Main function"""
    global autonomous_active
    
    try:
        # Start telemetry thread
        telem_thread = threading.Thread(target=telem_loop, daemon=True)
        telem_thread.start()
        
        # Wait for initial lidar data
        print("Waiting for LIDAR data...")
        while current_distance == 0 and autonomous_active:
            time.sleep(0.1)
        
        if autonomous_active:
            # Start autonomous navigation
            autonomous_loop()
        
    except KeyboardInterrupt:
        print("\nShutting down...")
        autonomous_active = False
    finally:
        stop_motors()
        ctrl_sock.close()
        telem_sock.close()

if __name__ == '__main__':
    main()
