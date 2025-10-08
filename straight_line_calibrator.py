#!/usr/bin/env python3
"""Interactive straight-line calibration tool for the IHFC robot.

Repeatedly drives the robot forward and prompts the operator to report
whether the chassis veered left or right. The tool adjusts the motor
balance factors until the operator confirms the robot travels straight,
then persists the updated factors to ``robot_calibration.json`` so all
other tools (including ``advanced.py`` and ``move_control.py``) pick up
the change automatically.
"""
from __future__ import annotations

import sys
import time

import advanced
from calibration_config import load_motor_factors, save_motor_factors

TEST_SPEED_DEFAULT = 45
TEST_DURATION_SECONDS = 3
STEP_DEFAULT = 0.02
MIN_FACTOR = 0.2
MAX_FACTOR = 3.0


def drive_forward(duration: float, speed: int, left_factor: float, right_factor: float) -> None:
    """Drive both motors forward for the requested duration and stop."""
    speed = max(5, min(120, int(speed)))
    print(f"\nDriving forward for {duration:.1f}s at speed {speed}...")
    print(f"  (Using motor factors: L={left_factor:.3f}, R={right_factor:.3f})")
    advanced.send_motor(speed, speed)
    time.sleep(duration)
    advanced.stop_motors()
    time.sleep(0.4)


def clamp_factor(value: float) -> float:
    return max(MIN_FACTOR, min(MAX_FACTOR, value))


def parse_step(command: str) -> float | None:
    parts = command.split()
    if len(parts) != 2:
        print("Usage: step <positive_number>")
        return None
    try:
        value = float(parts[1])
        if value <= 0:
            raise ValueError
        return value
    except ValueError:
        print("Step size must be a positive number (e.g. 0.02).")
        return None


def parse_speed(command: str) -> int | None:
    parts = command.split()
    if len(parts) != 2:
        print("Usage: speed <10-120>")
        return None
    try:
        value = int(float(parts[1]))
    except ValueError:
        print("Speed must be a number between 10 and 120.")
        return None
    if not 10 <= value <= 120:
        print("Speed must be between 10 and 120.")
        return None
    return value


def show_status(left: float, right: float, step: float, speed: int) -> None:
    ratio = left / right if right else float("inf")
    print(
        f"Current factors -> left: {left:.3f}, right: {right:.3f}, ratio (L/R): {ratio:.3f}"
    )
    print(f"Adjustment step: {step:.3f} | Test speed: {speed}")


def calibrate() -> int:
    print("=== Straight-Line Compensation Calibrator ===")
    print("Place the robot on a long, obstruction-free straight line.")
    print("The tool will drive forward; report whether it veered left or right.")
    print("Commands: Enter=run test, 'l'/'left', 'r'/'right', 's'/'straight',")
    print("          'step <value>' to change increment, 'speed <value>' to change test speed,")
    print("          'q' to abort without saving.")

    if not advanced.init_bot_control(verbose_telemetry=False):
        print("Failed to initialise bot control. Ensure the robot is connected.")
        return 1

    left_factor, right_factor = load_motor_factors()
    left_factor = clamp_factor(left_factor)
    right_factor = clamp_factor(right_factor)
    step = STEP_DEFAULT
    test_speed = TEST_SPEED_DEFAULT

    advanced.set_motor_factors(left_factor, right_factor)
    show_status(left_factor, right_factor, step, test_speed)

    try:
        while True:
            command = input("\nPress Enter to run the straight test (or type a command): ").strip().lower()

            if command in {"q", "quit", "exit"}:
                print("Calibration aborted. No changes saved.")
                return 1
            if command.startswith("step"):
                new_step = parse_step(command)
                if new_step is not None:
                    step = new_step
                    print(f"Adjustment step set to {step:.3f}")
                continue
            if command.startswith("speed"):
                new_speed = parse_speed(command)
                if new_speed is not None:
                    test_speed = new_speed
                    print(f"Test speed set to {test_speed}")
                continue
            if command:
                print("Unrecognised command. Press Enter, or type 'q', 'step <value>', or 'speed <value>'.")
                continue

            drive_forward(TEST_DURATION_SECONDS, test_speed, left_factor, right_factor)

            while True:
                response = input(
                    "Drift? [L]eft, [R]ight, [S]traight, 'step <value>', 'speed <value>', or 'q' to abort: "
                ).strip().lower()

                if response in {"l", "left"}:
                    left_factor = clamp_factor(left_factor + step)
                    advanced.set_motor_factors(left_factor, right_factor)
                    print("Adjusted left motor factor upward.")
                    show_status(left_factor, right_factor, step, test_speed)
                    break
                if response in {"r", "right"}:
                    left_factor = clamp_factor(left_factor - step)
                    advanced.set_motor_factors(left_factor, right_factor)
                    print("Adjusted left motor factor downward.")
                    show_status(left_factor, right_factor, step, test_speed)
                    break
                if response in {"s", "straight"}:
                    save_motor_factors(left_factor, right_factor)
                    advanced.set_motor_factors(left_factor, right_factor)
                    print("Calibration saved. The robot should now track straighter.")
                    return 0
                if response in {"q", "quit", "exit"}:
                    print("Calibration aborted. No changes saved.")
                    return 1
                if response.startswith("step"):
                    new_step = parse_step(response)
                    if new_step is not None:
                        step = new_step
                        print(f"Adjustment step set to {step:.3f}")
                    continue
                if response.startswith("speed"):
                    new_speed = parse_speed(response)
                    if new_speed is not None:
                        test_speed = new_speed
                        print(f"Test speed set to {test_speed}")
                    break  # re-run test with new speed
                print("Please respond with 'left', 'right', 'straight', or a command like 'step 0.01'.")
    except KeyboardInterrupt:
        print("\nCalibration interrupted. No changes saved.")
        return 1
    finally:
        advanced.stop_motors()
        advanced.cleanup()

    return 1


if __name__ == "__main__":
    sys.exit(calibrate())
