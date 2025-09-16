#!/usr/bin/env python3
# vision_modular.py - Vision integration using advanced.py library
"""
Vision-guided bot control using the advanced.py library.
Simplified version that focuses on vision logic while delegating
motor control and telemetry to the advanced module.
"""
import time
import threading
import cv2
import numpy as np
from pynput import keyboard
import advanced

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

# ----------------------
# Mode control
# ----------------------
autonomous_mode = False
vision_mode = False
key_state = set()

# Vision state
red_object_detected = False
red_object_center_x = 0
red_object_area = 0
last_vision_time = 0
camera_capture = None

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

def on_press(key):
    """Handle key press events"""
    global autonomous_mode, vision_mode
    
    try:
        k = key.char
    except AttributeError:
        # ESC: Toggle autonomous mode
        if key == keyboard.Key.esc:
            autonomous_mode = not autonomous_mode
            if autonomous_mode:
                print("=== AUTONOMOUS MODE ACTIVATED ===")
                print("Press V for vision mode, ESC again for manual control")
            else:
                print("=== MANUAL MODE ACTIVATED ===")
                vision_mode = False
                advanced.stop_motors()
                cv2.destroyAllWindows()
            return
        
        # Space: Toggle vision mode (only works in autonomous mode)
        if key == keyboard.Key.space:
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
            
        # Pass gear control to advanced module
        if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
            if autonomous_mode:
                return
            if advanced.get_current_gear() == 0:
                key_state.add('SHIFT')
            else:
                if 'SHIFT_GEAR' not in key_state:
                    key_state.add('SHIFT_GEAR')
                    advanced.gear_down()
            return
            
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            if autonomous_mode:
                return
            if 'CTRL' not in key_state:
                key_state.add('CTRL')
                advanced.gear_up()
            return
        return
    
    # Handle 'v' key for vision mode
    if k == 'v' and autonomous_mode:
        vision_mode = not vision_mode
        if vision_mode:
            print("=== VISION MODE ACTIVATED ===")
        else:
            print("=== VISION MODE DEACTIVATED ===")
            cv2.destroyAllWindows()
        return
        
    if not autonomous_mode:
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
    """Enhanced autonomous navigation logic with vision integration"""
    # Check LIDAR data using advanced module
    if not advanced.is_lidar_data_fresh():
        print("Warning: No recent LIDAR data!")
        advanced.stop_motors()
        return
    
    current_distance = advanced.get_current_distance()
    
    # Priority 1: Obstacle avoidance (safety first)
    if current_distance < 25:  # MIN_DISTANCE
        advanced.stop_motors()
        print(f"STOP! Obstacle at {current_distance} cm")
        # Simple obstacle avoidance - just turn right
        advanced.turn_right(25)
        time.sleep(0.3)
        return
    
    # Priority 2: Vision-guided navigation (if enabled)
    if vision_mode:
        steering, action = calculate_vision_steering()
        speed = 40 if current_distance > 60 else 20  # Adjust speed based on distance
        
        if action == "TARGET_REACHED":
            print("Red target reached! Stopping.")
            advanced.stop_motors()
        elif action == "ALIGNED_APPROACH":
            print(f"Approaching target - Distance: {current_distance} cm")
            advanced.move_forward(speed)
        elif action == "TURN_RIGHT":
            print(f"Steering toward red object (right)")
            # Gentle turn while moving forward
            advanced.send_motor_differential(speed, speed // 2)
        elif action == "TURN_LEFT":
            print(f"Steering toward red object (left)")
            # Gentle turn while moving forward
            advanced.send_motor_differential(speed // 2, speed)
        else:
            # No target or stale data - search mode
            print(f"Searching for red objects")
            advanced.move_forward(speed // 2)  # Move slowly while searching
    else:
        # Priority 3: Basic autonomous navigation
        if current_distance > 60:
            advanced.move_forward(60)
        elif current_distance > 40:
            advanced.move_forward(30)
        else:
            advanced.move_forward(20)

def manual_control():
    """Manual control using advanced module"""
    left, right = 0, 0
    
    # Use advanced module's gear system
    scale = advanced.calculate_gear_speed(crawl=('SHIFT' in key_state))
    fwd_step = int(scale * advanced.FWD_GAIN)
    turn_step = int(scale * advanced.TURN_GAIN)
    
    # WASD behavior
    if 'w' in key_state:
        left += fwd_step; right += fwd_step
    if 's' in key_state:
        left -= fwd_step; right -= fwd_step
    if 'a' in key_state:
        left -= turn_step; right += turn_step
    if 'd' in key_state:
        left += turn_step; right -= turn_step
    
    advanced.send_motor_differential(left, right)

def control_loop():
    """Main control loop"""
    print("=== MODULAR VISION-INTEGRATED RC CONTROL ===")
    print("Controls:")
    print("  WASD - Movement (manual mode)")
    print("  Shift/Ctrl - Gear control")
    print("  ESC - Toggle autonomous mode")
    print("  V or Space - Toggle vision mode (autonomous only)")
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
            break

if __name__ == '__main__':
    try:
        # Initialize bot control using advanced module
        advanced.init_bot_control(verbose_telemetry=False)
        
        # Start vision thread
        threading.Thread(target=vision_loop, daemon=True).start()
        
        # Start keyboard listener
        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        
        # Run main control loop
        control_loop()
        
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        advanced.cleanup()
        if camera_capture:
            camera_capture.release()
        cv2.destroyAllWindows()
