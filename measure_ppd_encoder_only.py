#!/usr/bin/env python3
"""Interactive encoder-only pulses-per-degree calibration.

This tool repeatedly commands a 360° in-place spin using encoder ticks and
asks you whether the robot overshot (>360°) or undershot (<360°). It narrows
in on the correct pulses-per-degree value and stores the result in the shared
calibration config so every script stays in sync.

Usage:
    python measure_ppd_encoder_only.py
"""
from __future__ import annotations

import math
import time
from typing import Tuple

from advanced import (
    init_bot_control,
    cleanup,
    get_latest_encoders,
    move_by_ticks,
    stop_motors,
    wait_for_encoder_data,
)
from calibration_config import load_pulses_per_degree, save_pulses_per_degree

DEFAULT_SPEED = 35
LOWER_BOUND = 5.0
UPPER_BOUND = 200.0
TOLERANCE_TICKS = 40


def wait_for_encoders(timeout: float = 10.0) -> None:
    print("Waiting for live encoder data…", end=" ")
    if wait_for_encoder_data(timeout):
        print("✅ ready!")
        return
    raise RuntimeError("No encoder telemetry received. Check ESP32 link.")


def get_encoder_snapshot() -> Tuple[int, int]:
    encoders, _ = get_latest_encoders()
    return int(encoders.get("m1", 0)), int(encoders.get("m2", 0))


def wait_for_turn_completion(target_ticks: int, start_left: int, start_right: int,
                             timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        cur_left, cur_right = get_encoder_snapshot()
        left_delta = abs(cur_left - start_left)
        right_delta = abs(cur_right - start_right)

        if left_delta >= target_ticks - TOLERANCE_TICKS and right_delta >= target_ticks - TOLERANCE_TICKS:
            return True
        time.sleep(0.1)
    return False


def perform_full_turn(ppd: float, speed: int = DEFAULT_SPEED) -> Tuple[int, int, int, float]:
    ticks = max(1, int(round(ppd * 360.0)))
    start_left, start_right = get_encoder_snapshot()

    print(f"\n🌀 Executing 360° turn using {ppd:.2f} pulses/° ({ticks} ticks)…")
    move_by_ticks(-ticks, ticks, -speed, speed)

    completed = wait_for_turn_completion(ticks, start_left, start_right)
    stop_motors()
    time.sleep(0.4)

    end_left, end_right = get_encoder_snapshot()
    left_delta = end_left - start_left
    right_delta = end_right - start_right
    avg_ticks = (abs(left_delta) + abs(right_delta)) / 2.0

    if not completed:
        print("⚠️  Turn timeout reached; encoders may not have hit target ticks.")

    approx_rotation = avg_ticks / ppd if ppd else float('nan')
    print(f"  Enc Δ: left={left_delta}, right={right_delta}, avg={avg_ticks:.1f} ticks")
    if math.isfinite(approx_rotation):
        print(f"  Approx rotation using current PPD: {approx_rotation:.1f}°")

    return left_delta, right_delta, ticks, avg_ticks


def prompt_adjustment() -> str:
    print("Was that turn more than 360°, less than 360°, or just right?")
    print("  [m] More (overshoot)    [l] Less (undershoot)    [p] Perfect")
    print("  Or enter a numeric pulses-per-degree value to try directly.")
    return input("Response: ").strip().lower()


def refine_guess(current: float, response: str, bounds: Tuple[float, float]) -> Tuple[float, Tuple[float, float], bool]:
    low, high = bounds
    if response in {"p", "perfect", "good", "exact"}:
        return current, (low, high), True
    if response in {"m", "more", "over", "overshoot", "+"}:
        high = current if current < high else high
        if math.isfinite(high) and low < high:
            next_guess = (low + high) / 2.0
        else:
            next_guess = current * 0.9
        return max(LOWER_BOUND, next_guess), (low, high), False
    if response in {"l", "less", "under", "undershoot", "-"}:
        low = current if current > low else low
        if math.isfinite(high) and low < high:
            next_guess = (low + high) / 2.0
        else:
            next_guess = current * 1.1
        return min(max(next_guess, LOWER_BOUND), UPPER_BOUND), (low, high), False

    try:
        manual = float(response)
        manual = min(max(manual, LOWER_BOUND), UPPER_BOUND)
        return manual, (low, high), False
    except ValueError:
        print("Input not understood. Please reply with m / l / p or a number.")
        return current, (low, high), False


def interactive_calibration():
    print("=== Encoder Pulses-Per-Degree Calibrator ===")
    print("This wizard will spin the robot 360° and let you guide adjustments.")
    print("Mark the robot's facing, clear the area, and be ready to observe.")

    init_bot_control(verbose_telemetry=False)
    wait_for_encoders()

    current_guess = load_pulses_per_degree()
    print(f"Starting from current config value: {current_guess:.2f} pulses/°")

    bounds = (LOWER_BOUND, UPPER_BOUND)
    iteration = 1
    try:
        while True:
            print(f"\n=== Iteration {iteration} ===")
            perform_full_turn(current_guess, DEFAULT_SPEED)
            response = prompt_adjustment()
            new_guess, bounds, done = refine_guess(current_guess, response, bounds)
            if done:
                print(f"Great! Final pulses-per-degree: {current_guess:.3f}")
                save_pulses_per_degree(current_guess)
                break
            if abs(new_guess - current_guess) < 0.01:
                current_guess = new_guess
                print("Change too small; assume converged.")
                save_pulses_per_degree(current_guess)
                break
            current_guess = new_guess
            iteration += 1
    finally:
        stop_motors()
        cleanup()
        print("Cleanup complete. Calibration config updated.")


def main():
    try:
        interactive_calibration()
    except KeyboardInterrupt:
        print("\nCalibration cancelled by user.")
        stop_motors()
        cleanup()
    except Exception as exc:
        print(f"❌ Calibration failed: {exc}")
        stop_motors()
        cleanup()


if __name__ == "__main__":
    main()
