#!/usr/bin/env python3
"""
Pure Pursuit Robot Controller

- Loads waypoints from checkpoints_cm.csv (x_cm,y_cm with top-left origin, y down)
- Follows them with a simple pure pursuit logic using existing advanced API.

Assumptions:
- Heading 0° means facing up (negative Y); positive angles turn left counter-clockwise.
- Movement distances are forward along current heading.
- This controller converts waypoints into relative (turn, distance) steps using the
  same kinematics as the measurement tool for consistency.

Usage:
  python move_control_pure_pursuit.py           # interactive
  python move_control_pure_pursuit.py run       # run through all points once
"""
import csv
import math
import os
import sys
import time
from advanced import (
    init_bot_control, cleanup, get_rotation_degrees, reset_rotation,
    get_current_distance, move_forward, move_backward, turn_left, turn_right,
    stop_motors, get_latest_imu, is_lidar_data_fresh
)

# --- Geometry helpers (match measurement tool conventions) ---

def heading_from_up_deg(vx_cm: float, vy_cm: float) -> float:
    """Bearing where 0° = up (-Y), 90° = right, 180° = down, 270° = left."""
    if abs(vx_cm) < 1e-9 and abs(vy_cm) < 1e-9:
        return 0.0
    return math.degrees(math.atan2(vx_cm, -vy_cm)) % 360.0

def wrap_to_180(deg: float) -> float:
    d = (deg + 180.0) % 360.0 - 180.0
    if d <= -180.0:
        d += 360.0
    return d

# --- Controller using existing primitives ---

class RobotController:
    def __init__(self):
        self.rotation_tolerance = 5.0  # degrees
        self.distance_tolerance = 2.0  # cm
        self.turn_speed = 20
        self.move_speed = 20
        self.max_turn_time = 30.0
        self.max_move_time = 30.0

    # Reuse methods from existing controller by copying minimal logic
    def turn_to_angle(self, target_degrees):
        start_time = time.time()
        last_progress = start_time
        while time.time() - start_time < self.max_turn_time:
            current = get_rotation_degrees()
            error = target_degrees - current
            if abs(error) <= self.rotation_tolerance:
                stop_motors()
                return True
            if error > 0:
                turn_left(self.turn_speed)
                direction = "left"
            else:
                turn_right(self.turn_speed)
                direction = "right"
            if time.time() - last_progress >= 1.0:
                print(f"Turning {direction}: target={target_degrees:+.1f}°, current={current:+.1f}°, error={error:+.1f}°")
                last_progress = time.time()
            time.sleep(0.05)
        stop_motors()
        return False

    def move_distance(self, target_cm):
        if target_cm == 0:
            return True
        if not is_lidar_data_fresh():
            start = time.time()
            while not is_lidar_data_fresh() and time.time() - start < 5.0:
                time.sleep(0.1)
        start_mm = get_current_distance()
        target_mm = start_mm + (target_cm * 10)
        start_time = time.time()
        last_progress = start_time
        while time.time() - start_time < self.max_move_time:
            if not is_lidar_data_fresh(max_age_seconds=1.0):
                break
            current_mm = get_current_distance()
            traveled_cm = (current_mm - start_mm) / 10.0
            error_cm = target_cm - traveled_cm
            if abs(error_cm) <= self.distance_tolerance:
                stop_motors()
                return True
            if target_cm > 0:
                if error_cm > 0:
                    move_forward(self.move_speed)
                else:
                    move_backward(self.move_speed)
            else:
                if error_cm < 0:
                    move_backward(self.move_speed)
                else:
                    move_forward(self.move_speed)
            if time.time() - last_progress >= 1.0:
                print(f"Moving: target={target_cm:+.1f}cm, traveled={traveled_cm:+.1f}cm, error={error_cm:+.1f}cm")
                last_progress = time.time()
            time.sleep(0.05)
        stop_motors()
        return False

    def follow_waypoints(self, waypoints_cm):
        """Follow waypoints (x_cm, y_cm) with simple pure pursuit conversion to relative steps.
        We compute segment vectors and turn by relative heading, then move the segment length.
        """
        if len(waypoints_cm) < 2:
            print("Need at least two waypoints")
            return False

        # starting heading is up (0°)
        prev_heading = 0.0
        success = True

        for i in range(1, len(waypoints_cm)):
            (x1, y1) = waypoints_cm[i-1]
            (x2, y2) = waypoints_cm[i]
            vx = x2 - x1
            vy = y2 - y1
            dist_cm = math.hypot(vx, vy)
            if dist_cm < 1e-6:
                continue
            seg_heading = heading_from_up_deg(vx, vy)
            turn_deg = wrap_to_180(seg_heading - prev_heading)

            print(f"\nSegment {i}: turn {turn_deg:+.1f}°, then go {dist_cm:.2f} cm")
            reset_rotation()
            time.sleep(0.2)
            if not self.turn_to_angle(turn_deg):
                print("Turn failed")
                success = False
                break
            time.sleep(0.2)
            if not self.move_distance(dist_cm):
                print("Move failed")
                success = False
                break
            prev_heading = seg_heading
        stop_motors()
        return success


def load_checkpoints(csv_path):
    pts = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                x = float(row["x_cm"])
                y = float(row["y_cm"])
                pts.append((x, y))
            except Exception:
                continue
    return pts


def main():
    run_all = len(sys.argv) > 1 and sys.argv[1].lower() == "run"
    csv_points = os.path.join(os.path.dirname(__file__), "checkpoints_cm.csv")
    if not os.path.exists(csv_points):
        print(f"Missing {csv_points}. Create it from the measurement tool (press Enter).")
        sys.exit(1)

    try:
        print("Initializing robot control system...")
        init_bot_control(verbose_telemetry=False)
        time.sleep(2)

        waypoints = load_checkpoints(csv_points)
        if len(waypoints) < 2:
            print("Not enough waypoints in checkpoints_cm.csv")
            sys.exit(1)

        ctrl = RobotController()
        print(f"Loaded {len(waypoints)} waypoints")
        if run_all:
            ok = ctrl.follow_waypoints(waypoints)
            sys.exit(0 if ok else 1)
        else:
            print("Interactive: following all waypoints once. Press Enter to start, Ctrl+C to abort.")
            input()
            ok = ctrl.follow_waypoints(waypoints)
            sys.exit(0 if ok else 1)
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
