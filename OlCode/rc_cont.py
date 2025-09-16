#!/usr/bin/env python3
# pc_client.py
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
# Max command magnitude expected by the Pi firmware for each wheel
MOTOR_MAX = 120

# 3 gears splitting ~600 RPM meaningfully: ~200, ~400, ~600 (as fractions of max)
GEAR_SCALES = [0.33, 0.66, 1.00]
gear_idx = 0  # start in lowest gear for safety

# Crawl scale applied while holding Shift
CRAWL_SCALE = 0.25

# Keep WASD behavior but with weighted turn vs forward (orig ratio 30:60 = 0.5)
FWD_GAIN = 1.0
TURN_GAIN = 0.5


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def send_motor(left, right):
    global seq
    msg = {'type':'motor','left':int(left),'right':int(right),'seq':seq, 'ts': int(time.time()*1000)}
    seq += 1
    ctrl_sock.sendto(json.dumps(msg).encode(), (RPI_IP, RPI_CTRL_PORT))


def telem_loop():
    while True:
        data, addr = telem_sock.recvfrom(2048)
        try:
            j = json.loads(data.decode())
            if j.get('type') == 'tfluna':
                print("LIDAR:", j['dist_mm'], "cm  ts:", j['ts'])
        except Exception as e:
            pass


def on_press(key):
    global gear_idx
    try:
        k = key.char
    except AttributeError:
        # Shift: gear down (one press) unless already in lowest gear, where it acts as crawl while held
        if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
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


def control_loop():
    # map keys to differential motor commands, scaled by gear and crawl
    while True:
        left, right = 0, 0

        # Scale from gear and optional crawl
        scale = MOTOR_MAX * GEAR_SCALES[gear_idx]
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

        # Clamp to safe max
        left = clamp(left, -MOTOR_MAX, MOTOR_MAX)
        right = clamp(right, -MOTOR_MAX, MOTOR_MAX)

        send_motor(left, right)
        time.sleep(0.05)


if __name__ == '__main__':
    threading.Thread(target=telem_loop,daemon=True).start()
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    control_loop()
