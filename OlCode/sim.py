#!/usr/bin/env python3
# local_simulator.py - Simulate wheel RPMs for the current control logic (no Pi comms)
import time
from pynput import keyboard

# ----------------------
# Drive config (tuneable)
# ----------------------
# Max command magnitude used by the control logic per wheel
MOTOR_MAX = 120
# Approximate motor max RPM for N20s
MAX_RPM = 600

# 3 gears splitting ~600 RPM meaningfully: ~200, ~400, ~600 (as fractions of max)
GEAR_SCALES = [0.33, 0.66, 1.00]
gear_idx = 0  # start in lowest gear for safety

# Crawl scale applied while holding Shift only in lowest gear
CRAWL_SCALE = 0.25

# Keep WASD behavior but with weighted turn vs forward (orig ratio 30:60 = 0.5)
FWD_GAIN = 1.0
TURN_GAIN = 0.5

# ----------------------
# State
# ----------------------
key_state = set()
running = True


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


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
                        print(f"\nGear: {gear_idx+1}/{len(GEAR_SCALES)}  scale={GEAR_SCALES[gear_idx]:.2f}")
                    else:
                        print("\nAlready in lowest gear")
            return
        # Ctrl: gear up one press at a time
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            if 'CTRL' not in key_state:  # debounce one-shot gear up
                key_state.add('CTRL')
                if gear_idx < len(GEAR_SCALES) - 1:
                    gear_idx += 1
                    print(f"\nGear: {gear_idx+1}/{len(GEAR_SCALES)}  scale={GEAR_SCALES[gear_idx]:.2f}")
                else:
                    print("\nAlready in top gear")
            return
        return
    # normal character keys
    key_state.add(k)


def on_release(key):
    global running
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
        print("\nQuit requested")
        running = False
        return False  # stop listener


def compute_outputs():
    """Compute left/right PWM based on current key_state and config."""
    # Scale from gear and optional crawl
    scale = MOTOR_MAX * GEAR_SCALES[gear_idx]
    if gear_idx == 0 and 'SHIFT' in key_state:
        scale *= CRAWL_SCALE

    fwd_step = int(scale * FWD_GAIN)
    turn_step = int(scale * TURN_GAIN)

    left, right = 0, 0
    # WASD behavior
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
    return left, right


def pwm_to_rpm(cmd: int) -> int:
    # Map PWM command to RPM relative to MOTOR_MAX and overall motor max
    return int((cmd / float(MOTOR_MAX)) * MAX_RPM)


def status_line(left_cmd: int, right_cmd: int) -> str:
    left_rpm = pwm_to_rpm(left_cmd)
    right_rpm = pwm_to_rpm(right_cmd)
    crawl = (gear_idx == 0 and 'SHIFT' in key_state)
    pressed = ''.join(sorted([k for k in key_state if len(k) == 1 and k.isalpha()]))
    return (
        f"Gear {gear_idx+1}/{len(GEAR_SCALES)} ({GEAR_SCALES[gear_idx]*100:.0f}%)"
        f" | Crawl: {'ON' if crawl else 'OFF'}"
        f" | Keys: {pressed or '-'}"
        f" | L: {left_cmd:+4d} ({left_rpm:+4d} rpm)"
        f" | R: {right_cmd:+4d} ({right_rpm:+4d} rpm)"
    )


def main():
    print("Local RPM simulator (no Pi). Controls: WASD drive, Ctrl gear up, Shift gear down; hold Shift for crawl only in lowest gear; q to quit.")
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    # Main loop ~20 Hz
    global running
    try:
        while running:
            left, right = compute_outputs()
            line = status_line(left, right)
            # Print single updating line
            print("\r" + line + " " * max(0, 10), end='', flush=True)
            time.sleep(0.05)
    finally:
        print("\nExiting simulator.")
        try:
            listener.stop()
        except Exception:
            pass


if __name__ == '__main__':
    main()
