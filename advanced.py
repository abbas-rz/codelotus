#!/usr/bin/env python3
# advanced.py - Core bot control library
"""
Core bot control library providing motor control, telemetry handling, and basic navigation functions.
Can be imported by other modules or run standalone for manual control.
"""
import socket, threading, json, time
from pynput import keyboard

# ----------------------
# Network Configuration
# ----------------------
RPI_IP = '192.168.1.52'   # <-- set to your Pi IP
RPI_CTRL_PORT = 9000
LOCAL_TELEM_PORT = 9001

# ----------------------
# Drive config (tuneable)
# ----------------------
MOTOR_MAX_LEFT = 120
MOTOR_MAX_RIGHT = 120
GEAR_SCALES = [0.33, 0.66, 1.00]
CRAWL_SCALE = 0.25
FWD_GAIN = 1.0
TURN_GAIN = 0.5

# ----------------------
# Global State Variables
# ----------------------
seq = 1
current_distance = 0
last_lidar_time = 0
latest_accel = {"x":0, "y":0, "z":0}
latest_gyro = {"x":0, "y":0, "z":0}
latest_heading = 0.0
latest_mag = {"x":0, "y":0, "z":0}
latest_temp_c = 0.0
last_imu_time = 0
latest_encoders = {"m1": 0, "m2": 0, "m3": 0, "m4": 0}
last_enc_time = 0

# Gyro integration variables
initial_heading_set = False
total_rotation_degrees = 0.0
last_gyro_z = 0.0
last_integration_time = 0.0

# Gyro calibration variables
gyro_bias_x = 0.0
gyro_bias_y = 0.0
gyro_bias_z = 0.0
calibration_loaded = False

ctrl_sock = None
telem_sock = None
verbose = True

gear_idx = 0
key_state = set()

# ----------------------
# Socket Setup
# ----------------------
def initialize_sockets():
    global ctrl_sock, telem_sock
    if ctrl_sock is None:
        ctrl_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if telem_sock is None:
        telem_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        telem_sock.bind(('', LOCAL_TELEM_PORT))

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

# ----------------------
# Core Motor Control
# ----------------------
def send_motor(left, right):
    global seq
    if ctrl_sock is None:
        initialize_sockets()
    msg = {'type':'motor','left':int(left),'right':int(right),
           'seq':seq, 'ts': int(time.time()*1000)}
    seq += 1
    ctrl_sock.sendto(json.dumps(msg).encode(), (RPI_IP, RPI_CTRL_PORT))

def stop_motors(): send_motor(0, 0)
def move_forward(speed): send_motor(clamp(speed, 0, MOTOR_MAX_LEFT),
                                    clamp(speed, 0, MOTOR_MAX_RIGHT))
def move_backward(speed): send_motor(-clamp(speed, 0, MOTOR_MAX_LEFT),
                                     -clamp(speed, 0, MOTOR_MAX_RIGHT))
def turn_right(speed=None):
    if speed is None: speed = min(MOTOR_MAX_LEFT, MOTOR_MAX_RIGHT) // 3
    send_motor(clamp(speed, 0, MOTOR_MAX_LEFT), -clamp(speed, 0, MOTOR_MAX_RIGHT))
def turn_left(speed=None):
    if speed is None: speed = min(MOTOR_MAX_LEFT, MOTOR_MAX_RIGHT) // 3
    send_motor(-clamp(speed, 0, MOTOR_MAX_LEFT), clamp(speed, 0, MOTOR_MAX_RIGHT))
def send_motor_differential(left, right):
    send_motor(clamp(left, -MOTOR_MAX_LEFT, MOTOR_MAX_LEFT),
               clamp(right, -MOTOR_MAX_RIGHT, MOTOR_MAX_RIGHT))

# Extended motor control: 4 independent motors (TB6612 x2)
def send_motor4(m1, m2=None, m3=None, m4=None):
    """Send per-motor speed commands. Accepts either 4 positional ints or a dict with keys m1..m4."""
    global seq
    if ctrl_sock is None:
        initialize_sockets()
    if isinstance(m1, dict):
        speeds = {
            'm1': int(clamp(m1.get('m1', 0), -MOTOR_MAX_LEFT, MOTOR_MAX_LEFT)),
            'm2': int(clamp(m1.get('m2', 0), -MOTOR_MAX_RIGHT, MOTOR_MAX_RIGHT)),
            'm3': int(clamp(m1.get('m3', 0), -MOTOR_MAX_LEFT, MOTOR_MAX_LEFT)),
            'm4': int(clamp(m1.get('m4', 0), -MOTOR_MAX_RIGHT, MOTOR_MAX_RIGHT)),
        }
    else:
        speeds = {
            'm1': int(clamp(m1 or 0, -MOTOR_MAX_LEFT, MOTOR_MAX_LEFT)),
            'm2': int(clamp(m2 or 0, -MOTOR_MAX_RIGHT, MOTOR_MAX_RIGHT)),
            'm3': int(clamp(m3 or 0, -MOTOR_MAX_LEFT, MOTOR_MAX_LEFT)),
            'm4': int(clamp(m4 or 0, -MOTOR_MAX_RIGHT, MOTOR_MAX_RIGHT)),
        }
    msg = {'type': 'motor4', **speeds, 'seq': seq, 'ts': int(time.time()*1000)}
    seq += 1
    ctrl_sock.sendto(json.dumps(msg).encode(), (RPI_IP, RPI_CTRL_PORT))

def move_by_ticks(left_ticks, right_ticks, left_speed, right_speed):
    """Move until encoders reach absolute tick targets at given speeds."""
    global seq
    if ctrl_sock is None:
        initialize_sockets()
    msg = {
        'type': 'move_ticks',
        'left_ticks': int(left_ticks),
        'right_ticks': int(right_ticks),
        'left_speed': int(clamp(left_speed, -MOTOR_MAX_LEFT, MOTOR_MAX_LEFT)),
        'right_speed': int(clamp(right_speed, -MOTOR_MAX_RIGHT, MOTOR_MAX_RIGHT)),
        'seq': seq,
        'ts': int(time.time()*1000)
    }
    seq += 1
    ctrl_sock.sendto(json.dumps(msg).encode(), (RPI_IP, RPI_CTRL_PORT))

def set_servo_angle(angle_deg):
    """Set SG90 servo angle in degrees (0-180 typical)."""
    global seq
    if ctrl_sock is None:
        initialize_sockets()
    msg = {'type': 'servo', 'angle': float(angle_deg), 'seq': seq, 'ts': int(time.time()*1000)}
    seq += 1
    ctrl_sock.sendto(json.dumps(msg).encode(), (RPI_IP, RPI_CTRL_PORT))

def stepper_steps(steps, step_delay_ms=None):
    """Move 28BYJ-48 stepper by step count. Optional per-step delay in ms."""
    global seq
    if ctrl_sock is None:
        initialize_sockets()
    msg = {'type': 'stepper', 'steps': int(steps), 'seq': seq, 'ts': int(time.time()*1000)}
    if step_delay_ms is not None:
        msg['delay_ms'] = int(step_delay_ms)
    seq += 1
    ctrl_sock.sendto(json.dumps(msg).encode(), (RPI_IP, RPI_CTRL_PORT))

# ----------------------
# Telemetry Functions
# ----------------------
def get_current_distance(): return current_distance
def get_last_lidar_time(): return last_lidar_time
def is_lidar_data_fresh(max_age_seconds=2.0):
    return (time.time() - last_lidar_time) <= max_age_seconds
def get_latest_imu(): return latest_accel, latest_gyro, last_imu_time

def get_latest_heading(): return latest_heading, last_imu_time

def get_latest_encoders():
    """Return latest encoder counts dict and timestamp."""
    return latest_encoders, last_enc_time

def get_full_imu_data(): 
    """Get all IMU data including heading, magnetometer, and temperature"""
    return {
        'accel': latest_accel,
        'gyro': latest_gyro,
        'heading': latest_heading,
        'mag': latest_mag,
        'temp_c': latest_temp_c,
        'timestamp': last_imu_time
    }

def get_rotation_degrees():
    """Get the total rotation in degrees since start"""
    return total_rotation_degrees

def reset_rotation():
    """Reset the rotation counter to zero"""
    global total_rotation_degrees, initial_heading_set, last_integration_time
    total_rotation_degrees = 0.0
    initial_heading_set = False
    last_integration_time = 0.0
    print("Rotation counter reset to 0 degrees")

def load_gyro_calibration(filename="gyro_calibration.json"):
    """Load gyro calibration from file"""
    global gyro_bias_x, gyro_bias_y, gyro_bias_z, calibration_loaded
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        
        gyro_bias_x = data.get("bias_x", 0.0)
        gyro_bias_y = data.get("bias_y", 0.0)
        gyro_bias_z = data.get("bias_z", 0.0)
        calibration_loaded = True
        
        print(f"Gyro calibration loaded: bias Z = {gyro_bias_z:+.4f}°/s")
        return True
    except FileNotFoundError:
        print("No gyro calibration file found. Run gyro_calibration.py to create one.")
        return False
    except Exception as e:
        print(f"Error loading gyro calibration: {e}")
        return False

def get_corrected_gyro(raw_gyro):
    """Apply bias correction to raw gyro data"""
    if not calibration_loaded:
        return raw_gyro
    
    return {
        'x': raw_gyro['x'] - gyro_bias_x,
        'y': raw_gyro['y'] - gyro_bias_y,
        'z': raw_gyro['z'] - gyro_bias_z
    }

def integrate_gyro_rotation(gyro_z_dps, current_time):
    """
    Integrate gyro z-axis data to calculate total rotation
    gyro_z_dps: angular velocity in degrees per second
    current_time: current timestamp in seconds
    """
    global total_rotation_degrees, last_gyro_z, last_integration_time, initial_heading_set
    
    if not initial_heading_set:
        last_gyro_z = gyro_z_dps
        last_integration_time = current_time
        initial_heading_set = True
        return total_rotation_degrees
    
    # Calculate time delta
    dt = current_time - last_integration_time
    
    # Only integrate if we have a reasonable time delta
    if 0.001 <= dt <= 1.0:  # Between 1ms and 1s
        # Use trapezoidal integration for better accuracy
        avg_gyro = (gyro_z_dps + last_gyro_z) / 2.0
        rotation_increment = avg_gyro * dt
        total_rotation_degrees += rotation_increment
    
    # Update for next iteration
    last_gyro_z = gyro_z_dps
    last_integration_time = current_time
    
    return total_rotation_degrees

def telem_loop(verbose=True):
    global current_distance, last_lidar_time
    global latest_accel, latest_gyro, latest_heading, latest_mag, latest_temp_c, last_imu_time

    if telem_sock is None:
        initialize_sockets()

    while True:
        try:
            data, addr = telem_sock.recvfrom(2048)
            j = json.loads(data.decode())

            # --- LIDAR ---
            if j.get('type') == 'tfluna':
                current_distance = j.get('dist_mm', 0)
                last_lidar_time = time.time()
                if verbose:
                    print("LIDAR:", current_distance, "mm  ts:", j['ts'])

            # --- IMU ---
            elif j.get('type') == 'imu':
                latest_accel = j.get('accel', {"x":0,"y":0,"z":0})
                latest_gyro  = j.get('gyro', {"x":0,"y":0,"z":0})
                latest_heading = j.get('heading', 0.0)
                latest_mag = j.get('mag', {"x":0,"y":0,"z":0})
                latest_temp_c = j.get('temp_c', 0.0)
                last_imu_time = time.time()
                
                # Apply calibration correction to gyro data
                corrected_gyro = get_corrected_gyro(latest_gyro)
                
                # Integrate corrected gyro z-axis for rotation tracking
                gyro_z_dps = corrected_gyro['z']  # degrees per second
                current_rotation = integrate_gyro_rotation(gyro_z_dps, last_imu_time)
                
                if verbose:
                    cal_indicator = " [CAL]" if calibration_loaded else " [RAW]"
                    print(f"IMU accel: x={latest_accel['x']:.2f}, y={latest_accel['y']:.2f}, z={latest_accel['z']:.2f}  "
                          f"gyro: x={corrected_gyro['x']:.2f}, y={corrected_gyro['y']:.2f}, z={corrected_gyro['z']:.2f}{cal_indicator}  "
                          f"heading: {latest_heading:.1f}°  rotation: {current_rotation:.1f}°  ts={j.get('ts',0)}")

            # --- Encoders ---
            elif j.get('type') == 'encoders':
                counts = j.get('counts') or j.get('encoders') or {}
                # Normalize to m1..m4 keys
                normalized = {
                    'm1': int(counts.get('m1', counts.get('left', 0)) or 0),
                    'm2': int(counts.get('m2', counts.get('right', 0)) or 0),
                    'm3': int(counts.get('m3', 0) or 0),
                    'm4': int(counts.get('m4', 0) or 0),
                }
                latest_encoders.update(normalized)
                last_enc_time = time.time()
                if verbose:
                    print(f"ENC m1={latest_encoders['m1']} m2={latest_encoders['m2']} m3={latest_encoders['m3']} m4={latest_encoders['m4']}  ts={j.get('ts',0)}")

        except Exception as e:
            if verbose:
                print(f"Telemetry error: {e}")

def start_telemetry_thread(verbose=True):
    telem_thread = threading.Thread(target=telem_loop, args=(verbose,), daemon=True)
    telem_thread.start()
    return telem_thread

# ----------------------
# Gear Functions
# ----------------------
def get_current_gear(): return gear_idx
def set_gear(gear):
    global gear_idx
    gear_idx = clamp(gear, 0, len(GEAR_SCALES) - 1)
    return gear_idx
def gear_up():
    global gear_idx
    if gear_idx < len(GEAR_SCALES) - 1:
        gear_idx += 1
        print(f"Gear: {gear_idx+1}/{len(GEAR_SCALES)}  scale={GEAR_SCALES[gear_idx]:.2f}")
    else: print("Already in top gear")
    return gear_idx
def gear_down():
    global gear_idx
    if gear_idx > 0:
        gear_idx -= 1
        print(f"Gear: {gear_idx+1}/{len(GEAR_SCALES)}  scale={GEAR_SCALES[gear_idx]:.2f}")
    else: print("Already in lowest gear")
    return gear_idx
def get_gear_scale(gear=None):
    if gear is None: gear = gear_idx
    return GEAR_SCALES[clamp(gear, 0, len(GEAR_SCALES) - 1)]

# ----------------------
# Advanced Movement
# ----------------------
def calculate_gear_speed(gear=None, crawl=False):
    if gear is None: gear = gear_idx
    scale = ((MOTOR_MAX_LEFT + MOTOR_MAX_RIGHT) / 2) * get_gear_scale(gear)
    if crawl and gear == 0: scale *= CRAWL_SCALE
    return int(scale)

def move_with_gear(forward=True, gear=None, crawl=False):
    speed = calculate_gear_speed(gear, crawl)
    if forward: move_forward(speed)
    else: move_backward(speed)

def turn_with_gear(right=True, gear=None, crawl=False):
    speed = calculate_gear_speed(gear, crawl) * TURN_GAIN
    if right: turn_right(int(speed))
    else: turn_left(int(speed))

# ----------------------
# Manual Control
# ----------------------
def on_press(key):
    global gear_idx
    try: k = key.char
    except AttributeError:
        if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
            if gear_idx == 0: key_state.add('SHIFT')
            else:
                if 'SHIFT_GEAR' not in key_state:
                    key_state.add('SHIFT_GEAR')
                    gear_down()
            return
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            if 'CTRL' not in key_state:
                key_state.add('CTRL')
                gear_up()
            return
        return
    key_state.add(k)

def on_release(key):
    try: k = key.char
    except AttributeError:
        if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
            key_state.discard('SHIFT')
            key_state.discard('SHIFT_GEAR')
            return
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            key_state.discard('CTRL')
            return
        return
    key_state.discard(k)
    if k == 'q':
        print("Quit requested")
        return False
    if k == 'r':
        reset_rotation()
        return
    if k == 'c':
        load_gyro_calibration()
        return

def manual_control_loop():
    print("=== MANUAL CONTROL MODE ===")
    print("Controls:\n  WASD - Movement\n  Shift - Gear down / Crawl mode\n  Ctrl - Gear up\n  R - Reset rotation counter\n  C - Reload gyro calibration\n  Q - Quit")
    print(f"Starting in gear {gear_idx+1}/{len(GEAR_SCALES)}")
    while True:
        left, right = 0, 0
        scale = ((MOTOR_MAX_LEFT + MOTOR_MAX_RIGHT) / 2) * GEAR_SCALES[gear_idx]
        if gear_idx == 0 and 'SHIFT' in key_state: scale *= CRAWL_SCALE
        fwd_step = int(scale * FWD_GAIN)
        turn_step = int(scale * TURN_GAIN)
        if 'w' in key_state: left += fwd_step; right += fwd_step
        if 's' in key_state: left -= fwd_step; right -= fwd_step
        if 'a' in key_state: left -= turn_step; right += turn_step
        if 'd' in key_state: left += turn_step; right -= turn_step
        send_motor_differential(left, right)
        time.sleep(0.05)

# ----------------------
# Init / Cleanup
# ----------------------
def init_bot_control(verbose_telemetry=True):
    initialize_sockets()
    start_telemetry_thread(verbose_telemetry)
    
    # Try to load gyro calibration
    load_gyro_calibration()
    
    print("Bot control system initialized")
    print(f"Motor limits: LEFT={MOTOR_MAX_LEFT}, RIGHT={MOTOR_MAX_RIGHT}")
    return True

def cleanup():
    stop_motors()
    if ctrl_sock: ctrl_sock.close()
    if telem_sock: telem_sock.close()

if __name__ == '__main__':
    try:
        init_bot_control()
        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        manual_control_loop()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        cleanup()
