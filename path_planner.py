#!/usr/bin/env python3
"""
Path Planner

Generates a path from a configurable start point to all red fruits and to a configurable end point,
while avoiding black/green fruits by penalizing segments that pass too close to obstacles.

Config file: path_config.json (next to this file)
{
  "start_cm": [10.0, 104.3],
  "end_cm": [10.0, 104.3]
}
If missing, defaults to ~bottom-left (10 cm from left, 10 cm from bottom).
"""
import os
import json
import math
import csv

# Arena size (cm)
ARENA_WIDTH_CM = 118.1
ARENA_HEIGHT_CM = 114.3

# Obstacle avoidance parameters
OBSTACLE_RADIUS_CM = 3.0
AVOID_MARGIN_CM = 8.0
PENALTY_WEIGHT = 200.0


def _dist(a, b):
    ax, ay = a; bx, by = b
    return math.hypot(ax - bx, ay - by)


def _segment_penalty(a, b, obstacles):
    if not obstacles:
        return 0.0
    (x1, y1), (x2, y2) = a, b
    dx = x2 - x1
    dy = y2 - y1
    denom = dx * dx + dy * dy
    penalty = 0.0
    for (ox, oy) in obstacles:
        if denom == 0:
            dmin = _dist(a, (ox, oy))
        else:
            t = ((ox - x1) * dx + (oy - y1) * dy) / denom
            t = max(0.0, min(1.0, t))
            px = x1 + t * dx
            py = y1 + t * dy
            dmin = math.hypot(px - ox, py - oy)
        clearance = OBSTACLE_RADIUS_CM + AVOID_MARGIN_CM
        if dmin < clearance:
            penalty += PENALTY_WEIGHT * (clearance - dmin)
    return penalty


def read_color_csv(script_dir, name):
    path = os.path.join(script_dir, name)
    pts = []
    if os.path.exists(path):
        with open(path, newline="") as f:
            r = csv.DictReader(f)
            for row in r:
                try:
                    x = float(row.get("x_cm", "0"))
                    y = float(row.get("y_cm", "0"))
                    pts.append((x, y))
                except Exception:
                    pass
    return pts


def synthesize_greens_from_fruit_ui():
    greens = []
    try:
        from fruit_ui import TOP_Y_CM as FU_TOP, SPACING_CM_DEFAULT as FU_SP, OFFSETS_FROM_RIGHT_CM as FU_OFF, ARENA_WIDTH_CM as FU_W
        cols_x = [FU_W - FU_OFF[0], FU_W - FU_OFF[1]]
        for x in cols_x:
            for i in range(6):
                greens.append((x, FU_TOP + i * FU_SP))
    except Exception:
        pass
    return greens


def load_fruits_for_overlay(script_dir):
    reds = read_color_csv(script_dir, "red.csv")
    blacks = read_color_csv(script_dir, "black.csv")
    greens = []
    green_file = os.path.join(script_dir, "green.csv")
    if os.path.exists(green_file):
        greens = read_color_csv(script_dir, "green.csv")
    else:
        greens = synthesize_greens_from_fruit_ui()
    return reds, blacks, greens


def write_checkpoints(script_dir, pts_cm):
    out = os.path.join(script_dir, "checkpoints_cm.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["x_cm", "y_cm"]) 
        for (x, y) in pts_cm:
            w.writerow([f"{x:.2f}", f"{y:.2f}"])


def write_path(script_dir, segs):
    out = os.path.join(script_dir, "path.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["turn_deg", "distance_cm"]) 
        for (t, d) in segs:
            w.writerow([f"{t:.2f}", f"{d:.2f}"])


def load_path_config(script_dir, defaults=None):
    if defaults is None:
        defaults = ((10.0, ARENA_HEIGHT_CM - 10.0), (10.0, ARENA_HEIGHT_CM - 10.0))
    cfg_path = os.path.join(script_dir, "path_config.json")
    if not os.path.exists(cfg_path):
        return defaults
    try:
        with open(cfg_path, "r") as f:
            data = json.load(f)
        s = data.get("start_cm") or []
        e = data.get("end_cm") or []
        start = (float(s[0]), float(s[1])) if len(s) == 2 else defaults[0]
        end = (float(e[0]), float(e[1])) if len(e) == 2 else defaults[1]
        return start, end
    except Exception:
        return defaults


def build_auto_path(script_dir, start_xy=None, end_xy=None):
    """
    Build a path going from start through all red fruits and ending at end, avoiding others.
    - Reads red.csv as targets, black.csv and untagged (green) fruits as obstacles.
    - If green.csv not provided, greens are synthesized from fruit_ui defaults.
    - Produces checkpoints_cm.csv (waypoints) and path.csv (turn,dist relative plan).
    """
    if start_xy is None or end_xy is None:
        start_xy, end_xy = load_path_config(script_dir)

    reds, blacks, greens = load_fruits_for_overlay(script_dir)

    # Obstacles are non-reds
    def not_near_red(p, reds_list, tol=1e-3):
        px, py = p
        for (rx, ry) in reds_list:
            if math.hypot(px - rx, py - ry) <= tol:
                return False
        return True
    obstacles = list(blacks) + [g for g in greens if not_near_red(g, reds)]

    if not reds:
        return [], []

    # Greedy NN with obstacle penalty
    remaining = reds[:]
    order = []
    cur = start_xy
    while remaining:
        best = None
        best_cost = 1e18
        for r in remaining:
            base = _dist(cur, r)
            cost = base + _segment_penalty(cur, r, obstacles)
            if cost < best_cost:
                best_cost = cost
                best = r
        order.append(best)
        remaining.remove(best)
        cur = best

    checkpoints = [start_xy] + order + [end_xy]

    # Build path relative turns
    segs = []
    heading_deg = 0.0  # start facing up
    for i in range(1, len(checkpoints)):
        x0, y0 = checkpoints[i - 1]
        x1, y1 = checkpoints[i]
        dx = x1 - x0
        dy = y1 - y0
        abs_heading = (math.degrees(math.atan2(dx, -dy)) % 360.0)
        rel_turn = (abs_heading - heading_deg + 540.0) % 360.0 - 180.0
        seg_dist = math.hypot(dx, dy)
        segs.append((rel_turn, seg_dist))
        heading_deg = abs_heading

    write_checkpoints(script_dir, checkpoints)
    write_path(script_dir, segs)
    return checkpoints, segs
