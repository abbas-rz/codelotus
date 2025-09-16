#!/usr/bin/env python3
# vision_autonomous.py - Vision-guided autonomous navigation with red object tracking
import socket, threading, json, time, cv2, numpy as np
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
MOTOR_MAX_RIGHT = 120  # Max command for right motor (adjust if different RPM)
GEAR_SCALES = [0.33, 0.66, 1.00]
gear_idx = 0  # start in lowest gear for safety
CRAWL_SCALE = 0.25
FWD_GAIN = 1.0
TURN_GAIN = 0.5

# ----------------------
# Autonomous config
# ----------------------
autonomous_mode = False
vision_mode = False  # New: toggle for vision-guided navigation
MIN_DISTANCE = 25  # cm - minimum distance to obstacle before stopping
TURN_DISTANCE = 40  # cm - distance to start slowing down
SAFE_DISTANCE = 60  # cm - distance considered safe for full speed
TURN_SPEED = 25  # slower turn speed for better scanning
TURN_TIME = 0.3  # shorter turn intervals for smoother scanning
MAX_ROTATIONS = 2  # maximum number of full rotations before giving up

# ----------------------
# Vision config
# ----------------------
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
RED_LOWER = np.array([0, 50, 50])     # Lower HSV threshold for red
RED_UPPER = np.array([10, 255, 255])  # Upper HSV threshold for red
RED_LOWER2 = np.array([170, 50, 50])  # Second red range (wraps around hue)
RED_UPPER2 = np.array([180, 255, 255])
MIN_CONTOUR_AREA = 500  # Minimum area for red object detection
VISION_TURN_THRESHOLD = 50  # Pixels from center to trigger turning
VISION_TARGET_SIZE = 5000  # Target contour area to approach

# Global variables for sensor data
current_distance = 0
last_lidar_time = 0
rotation_count = 0  # track how many full rotations we've done

# Global variables for vision data
red_object_detected = False
red_object_center_x = 0
red_object_area = 0
last_vision_time = 0
camera_capture = None

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

def setup_camera():
    """Setup camera capture using GStreamer pipeline"""
    global camera_capture
    
    # GStreamer pipeline for UDP H.264 stream
    gst_pipeline = (
        "udpsrc port=5000 caps=\"application/x-rtp,encoding-name=H264,payload=96\" ! "
        "rtph264depay ! avdec_h264 ! videoconvert ! appsink sync=false"
    )
    
    try:
        camera_capture = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
        if camera_capture.isOpened():
            camera_capture.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            camera_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            print("Camera initialized successfully")
            return True
        else:
            print("Failed to open camera stream")
            return False
    except Exception as e:
        print(f"Camera setup error: {e}")
        return False

def detect_red_objects(frame):
    """Detect red objects in the frame and return the largest one's info"""
    global red_object_detected, red_object_center_x, red_object_area, last_vision_time
    
    # Convert BGR to HSV
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Create mask for red color (two ranges due to hue wrapping)
    mask1 = cv2.inRange(hsv, RED_LOWER, RED_UPPER)
    mask2 = cv2.inRange(hsv, RED_LOWER2, RED_UPPER2)
    mask = cv2.bitwise_or(mask1, mask2)
    
    # Apply morphological operations to reduce noise
    kernel = np.ones((5,5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    
    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    red_object_detected = False
    largest_area = 0
    largest_center_x = 0
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > MIN_CONTOUR_AREA and area > largest_area:
            largest_area = area
            # Get centroid
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                largest_center_x = cx
                red_object_detected = True
                
                # Draw detection on frame for debugging
                cv2.drawContours(frame, [contour], -1, (0, 255, 0), 2)
                cv2.circle(frame, (cx, cy), 5, (255, 0, 0), -1)
                cv2.putText(frame, f"Area: {area}", (cx-50, cy-20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    if red_object_detected:
        red_object_center_x = largest_center_x
        red_object_area = largest_area
        last_vision_time = time.time()
        print(f"Red object detected: Center X={red_object_center_x}, Area={red_object_area}")
    
    return frame

def vision_loop():
    """Main vision processing loop"""
    global camera_capture
    
    if not setup_camera():
        print("Vision system disabled - camera setup failed")
        return
    
    print("Vision system started")
    
    while True:
        try:
            if camera_capture is None or not camera_capture.isOpened():
                time.sleep(1)
                continue
                
            ret, frame = camera_capture.read()
            if not ret:
                print("Failed to read frame")
                time.sleep(0.1)
                continue
            
            # Process frame for red object detection
            frame = detect_red_objects(frame)
            
            # Show frame if in vision mode (optional)
            if vision_mode:
                cv2.imshow('Vision Feed', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
            time.sleep(0.05)  # ~20 FPS
            
        except Exception as e:
            print(f"Vision loop error: {e}")
            time.sleep(1)

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
    
    # Reduce overall speed for safer autonomous operation
    base_speed *= 0.8
    
    return int(clamp(base_speed, 0, max(MOTOR_MAX_LEFT, MOTOR_MAX_RIGHT)))

def calculate_vision_steering():
    """Calculate steering adjustment based on red object position"""
    if not red_object_detected:
        return 0, "NO_TARGET"
    
    # Check if vision data is recent
    if time.time() - last_vision_time > 1.0:
        return 0, "STALE_DATA"
    
    # Calculate steering based on object position
    center_x = CAMERA_WIDTH // 2
    offset = red_object_center_x - center_x
    
    # Determine action based on offset and object size
    if abs(offset) < VISION_TURN_THRESHOLD:
        if red_object_area > VISION_TARGET_SIZE:
            return 0, "TARGET_REACHED"
        else:
            return 0, "ALIGNED_APPROACH"
    elif offset > 0:
        # Object is to the right, turn right
        return 1, "TURN_RIGHT"
    else:
        # Object is to the left, turn left
        return -1, "TURN_LEFT"

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
        # In vision mode, prefer turning toward red objects
        if vision_mode and red_object_detected:
            steering, action = calculate_vision_steering()
            if steering > 0:
                turn_right(TURN_SPEED)
            elif steering < 0:
                turn_left(TURN_SPEED)
            else:
                turn_right(TURN_SPEED)  # Default behavior
        else:
            # Default behavior: turn right
            turn_right(TURN_SPEED)
            
        time.sleep(TURN_TIME)
        stop_motors()
        time.sleep(0.1)  # Brief pause to get stable reading
        
        steps_taken += 1
        
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

def telem_loop():
    global current_distance, last_lidar_time
    while True:
        try:
            data, addr = telem_sock.recvfrom(2048)
            telemetry = json.loads(data.decode())
            if telemetry.get('type') == 'tfluna':
                current_distance = telemetry.get('dist_mm', 0)
                last_lidar_time = time.time()
                if autonomous_mode and not vision_mode:
                    print(f"LIDAR: {current_distance} cm")
        except Exception as e:
            pass

def on_press(key):
    global gear_idx, autonomous_mode, vision_mode
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
                print("Press V for vision mode, ESC again for manual control")
            else:
                print("=== MANUAL MODE ACTIVATED ===")
                vision_mode = False
                stop_motors()
                cv2.destroyAllWindows()
            return
        
        # V: Toggle vision mode (only works in autonomous mode)
        if key == keyboard.Key.space:  # Using space as V key
            if autonomous_mode:
                vision_mode = not vision_mode
                if vision_mode:
                    print("=== VISION MODE ACTIVATED ===")
                    print("Bot will now track red objects while avoiding obstacles")
                else:
                    print("=== VISION MODE DEACTIVATED ===")
                    cv2.destroyAllWindows()
            else:
                print("Vision mode only available in autonomous mode")
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
    if k == 'v' and autonomous_mode:
        vision_mode = not vision_mode
        if vision_mode:
            print("=== VISION MODE ACTIVATED ===")
            print("Bot will now track red objects while avoiding obstacles")
        else:
            print("=== VISION MODE DEACTIVATED ===")
            cv2.destroyAllWindows()
        return
        
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
    """Enhanced autonomous navigation logic with vision integration"""
    global rotation_count
    
    # Check if we have recent lidar data
    if time.time() - last_lidar_time > 2.0:
        print("Warning: No recent LIDAR data!")
        stop_motors()
        return
    
    # Priority 1: Obstacle avoidance (safety first)
    if current_distance < MIN_DISTANCE:
        # Stop immediately
        stop_motors()
        print(f"STOP! Obstacle at {current_distance} cm")
        
        # Try to find a clear path (vision-aware if enabled)
        if find_clear_path():
            print("Clear path found! Resuming movement...")
            rotation_count = 0
        else:
            print("Stuck! Switching to manual mode.")
            global autonomous_mode
            autonomous_mode = False
            rotation_count = 0
            
    else:
        # Priority 2: Vision-guided navigation (if enabled)
        if vision_mode:
            steering, action = calculate_vision_steering()
            speed = calculate_autonomous_speed_from_distance(current_distance)
            
            # Reset rotation counter when moving successfully
            if rotation_count > 0:
                print("Successfully moving, resetting rotation counter")
                rotation_count = 0
            
            if action == "TARGET_REACHED":
                print("Red target reached! Stopping.")
                stop_motors()
            elif action == "ALIGNED_APPROACH":
                print(f"Approaching target - Distance: {current_distance} cm, Speed: {speed}")
                move_forward(speed)
            elif action == "TURN_RIGHT":
                print(f"Steering toward red object (right) - Distance: {current_distance} cm")
                # Gentle turn while moving forward
                turn_speed = min(speed // 2, TURN_SPEED)
                send_motor(speed, speed - turn_speed)
            elif action == "TURN_LEFT":
                print(f"Steering toward red object (left) - Distance: {current_distance} cm")
                # Gentle turn while moving forward
                turn_speed = min(speed // 2, TURN_SPEED)
                send_motor(speed - turn_speed, speed)
            else:
                # No target or stale data - search mode
                print(f"Searching for red objects - Distance: {current_distance} cm")
                move_forward(speed // 2)  # Move slowly while searching
                
        else:
            # Priority 3: Basic autonomous navigation (original behavior)
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
    print("=== VISION-INTEGRATED AUTONOMOUS RC CONTROL ===")
    print("Manual Controls:")
    print("  WASD - Movement")
    print("  Shift - Gear down / Crawl mode")
    print("  Ctrl - Gear up")
    print("  ESC - Toggle autonomous mode")
    print("  V - Toggle vision mode (autonomous only)")
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
            cv2.destroyAllWindows()
            break

if __name__ == '__main__':
    # Start telemetry thread
    threading.Thread(target=telem_loop, daemon=True).start()
    
    # Start vision thread
    threading.Thread(target=vision_loop, daemon=True).start()
    
    # Start keyboard listener
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    
    # Run main control loop
    control_loop()
    
    # Cleanup
    if camera_capture:
        camera_capture.release()
    cv2.destroyAllWindows()
