#!/usr/bin/env python3
"""Interactive encoder-only pulses-per-centimeter calibration.

This wizard drives the robot forward a fixed distance using encoder ticks,
then lets you adjust the pulses-per-centimeter constant based on how far the
robot actually travelled. The refined value is stored in the shared
calibration config so movement routines, telemetry, and planners remain in sync.

Usage:
    python measure_ppc_encoder_only.py
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
from calibration_config import (
    load_pulses_per_cm,
    save_pulses_per_cm,
)

DEFAULT_SPEED = 45
DEFAULT_DISTANCE_CM = 80.0
TOLERANCE_TICKS = 80
SETTLE_DELAY_S = 0.4


def wait_for_encoders(timeout: float = 10.0) -> None:
    print("Waiting for live encoder data…", end=" ")
    if wait_for_encoder_data(timeout):
        print("✅ ready!")
        return
    raise RuntimeError("No encoder telemetry received. Check ESP32 link.")


def get_encoder_snapshot() -> Tuple[int, int]:
    encoders, _ = get_latest_encoders()
    return int(encoders.get("m1", 0)), int(encoders.get("m2", 0))


def wait_for_move_completion(target_ticks: int, start_left: int, start_right: int,
                             timeout: float = 25.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        cur_left, cur_right = get_encoder_snapshot()
        left_delta = abs(cur_left - start_left)
        right_delta = abs(cur_right - start_right)
        if left_delta >= max(0, target_ticks - TOLERANCE_TICKS) and \
           right_delta >= max(0, target_ticks - TOLERANCE_TICKS):
            return True
        time.sleep(0.1)
    return False


def perform_forward_move(ppc: float, distance_cm: float, speed: int = DEFAULT_SPEED) -> Tuple[int, int, int, float, float]:
    ticks = max(1, int(round(ppc * distance_cm)))
    start_left, start_right = get_encoder_snapshot()

    print(f"\n➡️  Driving forward {distance_cm:.1f} cm using {ppc:.2f} pulses/cm ({ticks} ticks)…")
    move_by_ticks(ticks, ticks, speed, speed)

    completed = wait_for_move_completion(ticks, start_left, start_right)
    stop_motors()
    time.sleep(SETTLE_DELAY_S)

    end_left, end_right = get_encoder_snapshot()
    left_delta = end_left - start_left
    right_delta = end_right - start_right
    avg_ticks = (abs(left_delta) + abs(right_delta)) / 2.0
    approx_distance = avg_ticks / ppc if ppc else float("nan")

    if not completed:
        print("⚠️  Move timeout reached; encoders may not have hit target ticks.")

    print(f"  Encoder Δ: left={left_delta}, right={right_delta}, avg={avg_ticks:.1f} ticks")
    if math.isfinite(approx_distance):
        print(f"  Approx distance using current PPC: {approx_distance:.2f} cm")

    return left_delta, right_delta, ticks, avg_ticks, approx_distance


def prompt_measured_distance(expected_cm: float) -> float | None:
    while True:
        response = input(
            f"Enter measured distance in cm (blank = {expected_cm:.1f}, 'r' to redo run, 'q' to quit): "
        ).strip()
        if not response:
            return expected_cm
        lowered = response.lower()
        if lowered in {"r", "redo", "retry"}:
            return None
        if lowered in {"q", "quit", "exit"}:
            raise KeyboardInterrupt
        try:
            measured = float(response)
            if measured <= 0:
                raise ValueError
            return measured
        except ValueError:
            print("Please enter a positive number, blank, 'r', or 'q'.")


def interactive_calibration() -> None:
    print("=== Encoder Pulses-Per-Centimeter Calibrator ===")
    print("This wizard will drive the robot forward a fixed distance.")
    print("Measure how far it actually moved, and we'll refine the pulses/cm value.")

    init_bot_control(verbose_telemetry=False)
    wait_for_encoders()

    current_ppc = load_pulses_per_cm()
    print(f"Starting from current config value: {current_ppc:.2f} pulses/cm")
    move_distance = DEFAULT_DISTANCE_CM

    try:
        iteration = 1
        while True:
            print(f"\n=== Iteration {iteration} ===")
            print("Place the robot at the start mark with enough space to move forward.")
            input("Press Enter when ready to begin the drive…")

            _, _, target_ticks, avg_ticks, approx_distance = perform_forward_move(
                current_ppc, move_distance, DEFAULT_SPEED
            )

            try:
                measured_cm = prompt_measured_distance(move_distance)
            except KeyboardInterrupt:
                print("\nCalibration cancelled by user. No changes saved.")
                break

            if measured_cm is None:
                print("Redoing the run with the same settings…")
                continue

            if measured_cm <= 0:
                print("Measured distance must be positive. Let's try again.")
                continue

            suggested_ppc = avg_ticks / measured_cm if measured_cm else current_ppc
            if not math.isfinite(suggested_ppc) or suggested_ppc <= 0:
                print("Could not compute a valid pulses/cm suggestion. Rerunning…")
                continue

            print("\n--- Result Summary ---")
            print(f"Measured distance: {measured_cm:.2f} cm")
            print(f"Average encoder ticks: {avg_ticks:.1f}")
            print(f"Current pulses/cm: {current_ppc:.3f}")
            print(f"Suggested pulses/cm: {suggested_ppc:.3f}")

            decision = input("Accept suggested value? [Y]es / [R]erun / [M]anual / [Q]uit without saving: ").strip().lower()
            if decision in {"", "y", "yes"}:
                save_pulses_per_cm(suggested_ppc)
                print(f"Saved pulses-per-centimeter = {suggested_ppc:.3f}")
                break
            if decision in {"m", "manual"}:
                manual_input = input("Enter pulses/cm to use: ").strip()
                try:
                    manual_value = float(manual_input)
                    if manual_value <= 0:
                        raise ValueError
                    current_ppc = manual_value
                except ValueError:
                    print("Invalid number; keeping previous value.")
                continue
            if decision in {"q", "quit"}:
                print("Exiting without saving changes.")
                break

            current_ppc = suggested_ppc
            iteration += 1
    finally:
        stop_motors()
        cleanup()
        print("Cleanup complete.")


def main() -> None:
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
