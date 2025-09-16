#!/usr/bin/env python3
"""
button_launcher.py — watch a tactile button to control the robot service

Gestures:
- Single tap: start pi_control (if not running)
- Double tap (<=0.5s): update repo to latest (git pull/reset) and restart pi_control
- Long press (>2s): shutdown the Pi

Wiring (BCM): BUTTON_PIN = 17 (Pin 11), wired to GND with internal pull-up enabled

For systemd service and sudo permissions, see docs/PI_SETUP.md
"""
import subprocess, time, os, signal, shlex
import RPi.GPIO as GPIO

BUTTON_PIN = 17
PROCESS = None
DOUBLE_WINDOW_S = 0.5
LONG_PRESS_S = 2.0


def is_running(proc):
    return proc is not None and proc.poll() is None


def start_service():
    global PROCESS
    if is_running(PROCESS):
        return
    # Launch pi_control.py located in same folder
    script = os.path.join(os.path.dirname(__file__), 'pi_control.py')
    python = 'python3'
    env = os.environ.copy()
    PROCESS = subprocess.Popen([python, script], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print("pi_control started")


def stop_service():
    global PROCESS
    if not is_running(PROCESS):
        return
    PROCESS.send_signal(signal.SIGINT)
    try:
        PROCESS.wait(timeout=3)
    except subprocess.TimeoutExpired:
        PROCESS.kill()
    print("pi_control stopped")


def run_cmd(cmd: str, cwd: str = None):
    print(f"$ {cmd}")
    try:
        out = subprocess.check_output(shlex.split(cmd), stderr=subprocess.STDOUT, cwd=cwd)
        print(out.decode(errors='ignore'))
    except subprocess.CalledProcessError as e:
        print(e.output.decode(errors='ignore'))


def update_repo_and_restart():
    # Determine repo root (two levels up from this file)
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    was_running = is_running(PROCESS)
    if was_running:
        stop_service()
    # Try to pull latest main
    run_cmd("git fetch --all --prune", cwd=repo_root)
    # Prefer rebasing cleanly; fallback to hard reset if needed
    try:
        run_cmd("git pull --rebase", cwd=repo_root)
    except Exception:
        run_cmd("git reset --hard origin/main", cwd=repo_root)
    # Optional: update submodules
    run_cmd("git submodule update --init --recursive", cwd=repo_root)
    if was_running or not is_running(PROCESS):
        start_service()


def shutdown_pi():
    print("Shutting down Pi (long press)")
    try:
        subprocess.Popen(["sudo", "/sbin/shutdown", "-h", "now"])  # requires sudoers permission
    except Exception as e:
        print("shutdown failed:", e)


def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    pressed_time = None
    last_tap_time = None

    try:
        while True:
            state = GPIO.input(BUTTON_PIN)
            now = time.time()
            if state == GPIO.LOW:  # pressed
                if pressed_time is None:
                    pressed_time = now
                else:
                    # check long press while held
                    if now - pressed_time > LONG_PRESS_S:
                        shutdown_pi()
                        # wait for release before continuing
                        while GPIO.input(BUTTON_PIN) == GPIO.LOW:
                            time.sleep(0.05)
                        pressed_time = None
                time.sleep(0.02)
            else:  # released
                if pressed_time is not None:
                    press_dur = now - pressed_time
                    if 0.03 < press_dur < LONG_PRESS_S:
                        # short tap
                        if last_tap_time and (now - last_tap_time) <= DOUBLE_WINDOW_S:
                            # double tap -> update
                            last_tap_time = None
                            update_repo_and_restart()
                        else:
                            # wait to see if a second tap arrives
                            last_tap_time = now
                    pressed_time = None
                else:
                    # check if pending single tap should fire
                    if last_tap_time and (now - last_tap_time) > DOUBLE_WINDOW_S:
                        # single tap -> start if not running
                        if not is_running(PROCESS):
                            start_service()
                        last_tap_time = None
                time.sleep(0.02)
    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup()
        if is_running(PROCESS):
            stop_service()


if __name__ == '__main__':
    main()
