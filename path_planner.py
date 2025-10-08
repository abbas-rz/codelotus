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
# Enforce that every segment of the path stays at least this far from any non-red fruit (cm)
MIN_CLEARANCE_CM = 7.0
OBSTACLE_RADIUS_CM = 3.0          # kept for reference if boundary-based clearance is later desired
AVOID_MARGIN_CM = 8.0             # kept for tuning; currently not used in hard filter
PENALTY_WEIGHT = 200.0            # retained for optional scoring, not used in hard filter
NO_GO_CLEARANCE_CM = 8.0

# Grid-based routing parameters
GRID_STEP_CM = 1.0  # grid resolution; finer yields better paths, higher compute


def _dist(a, b):
    ax, ay = a; bx, by = b
    return math.hypot(ax - bx, ay - by)


def _make_point_obstacle(x, y, clearance):
    return {
        "type": "point",
        "x": float(x),
        "y": float(y),
        "clearance": float(clearance),
    }


def _make_rect_obstacle(x1, y1, x2, y2, clearance):
    xmin = min(x1, x2)
    xmax = max(x1, x2)
    ymin = min(y1, y2)
    ymax = max(y1, y2)
    return {
        "type": "rect",
        "xmin": float(xmin),
        "xmax": float(xmax),
        "ymin": float(ymin),
        "ymax": float(ymax),
        "clearance": float(clearance),
    }


def _distance_point_to_segment(px, py, a, b):
    (x1, y1), (x2, y2) = a, b
    dx = x2 - x1
    dy = y2 - y1
    denom = dx * dx + dy * dy
    if denom == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / denom
    t = max(0.0, min(1.0, t))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def _point_inside_rect(px, py, rect):
    return rect["xmin"] <= px <= rect["xmax"] and rect["ymin"] <= py <= rect["ymax"]


def _distance_point_to_rect(px, py, rect):
    if _point_inside_rect(px, py, rect):
        return 0.0
    dx = 0.0
    if px < rect["xmin"]:
        dx = rect["xmin"] - px
    elif px > rect["xmax"]:
        dx = px - rect["xmax"]
    dy = 0.0
    if py < rect["ymin"]:
        dy = rect["ymin"] - py
    elif py > rect["ymax"]:
        dy = py - rect["ymax"]
    return math.hypot(dx, dy)


def _orientation(p, q, r):
    val = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
    if abs(val) < 1e-9:
        return 0
    return 1 if val > 0 else 2


def _on_segment(p, q, r):
    return min(p[0], r[0]) - 1e-9 <= q[0] <= max(p[0], r[0]) + 1e-9 and \
           min(p[1], r[1]) - 1e-9 <= q[1] <= max(p[1], r[1]) + 1e-9


def _segments_intersect(p1, p2, q1, q2):
    o1 = _orientation(p1, p2, q1)
    o2 = _orientation(p1, p2, q2)
    o3 = _orientation(q1, q2, p1)
    o4 = _orientation(q1, q2, p2)

    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and _on_segment(p1, q1, p2):
        return True
    if o2 == 0 and _on_segment(p1, q2, p2):
        return True
    if o3 == 0 and _on_segment(q1, p1, q2):
        return True
    if o4 == 0 and _on_segment(q1, p2, q2):
        return True
    return False


def _distance_segment_to_segment(a1, a2, b1, b2):
    if _segments_intersect(a1, a2, b1, b2):
        return 0.0
    return min(
        _distance_point_to_segment(a1[0], a1[1], b1, b2),
        _distance_point_to_segment(a2[0], a2[1], b1, b2),
        _distance_point_to_segment(b1[0], b1[1], a1, a2),
        _distance_point_to_segment(b2[0], b2[1], a1, a2),
    )


def _segment_intersects_rect(a, b, rect):
    if _point_inside_rect(a[0], a[1], rect) or _point_inside_rect(b[0], b[1], rect):
        return True
    corners = [
        (rect["xmin"], rect["ymin"]),
        (rect["xmax"], rect["ymin"]),
        (rect["xmax"], rect["ymax"]),
        (rect["xmin"], rect["ymax"]),
    ]
    edges = [
        (corners[0], corners[1]),
        (corners[1], corners[2]),
        (corners[2], corners[3]),
        (corners[3], corners[0]),
    ]
    for e1, e2 in edges:
        if _segments_intersect(a, b, e1, e2):
            return True
    return False


def _distance_segment_to_rect(a, b, rect):
    if _segment_intersects_rect(a, b, rect):
        return 0.0
    corners = [
        (rect["xmin"], rect["ymin"]),
        (rect["xmax"], rect["ymin"]),
        (rect["xmax"], rect["ymax"]),
        (rect["xmin"], rect["ymax"]),
    ]
    edges = [
        (corners[0], corners[1]),
        (corners[1], corners[2]),
        (corners[2], corners[3]),
        (corners[3], corners[0]),
    ]
    dist = min(
        _distance_point_to_rect(a[0], a[1], rect),
        _distance_point_to_rect(b[0], b[1], rect),
    )
    for e1, e2 in edges:
        dist = min(dist, _distance_segment_to_segment(a, b, e1, e2))
    return dist


def _segment_penalty(a, b, obstacles):
    if not obstacles:
        return 0.0
    penalty = 0.0
    for obs in obstacles:
        if obs["type"] == "point":
            dmin = _distance_point_to_segment(obs["x"], obs["y"], a, b)
        else:
            dmin = _distance_segment_to_rect(a, b, obs)
        clearance = obs.get("clearance", OBSTACLE_RADIUS_CM + AVOID_MARGIN_CM)
        if dmin < clearance:
            penalty += PENALTY_WEIGHT * (clearance - dmin)
    return penalty


def _segment_min_clearance(a, b, obstacles):
    """Return the minimum distance from segment AB to any obstacle (in cm)."""
    if not obstacles:
        return float("inf")
    min_d = float("inf")
    for obs in obstacles:
        if obs["type"] == "point":
            dmin = _distance_point_to_segment(obs["x"], obs["y"], a, b)
        else:
            dmin = _distance_segment_to_rect(a, b, obs)
        if dmin < min_d:
            min_d = dmin
    return min_d


def _segment_is_clear(a, b, obstacles):
    """Return True if segment AB keeps the required clearance from all obstacles."""
    for obs in obstacles:
        clearance = obs.get("clearance", MIN_CLEARANCE_CM)
        if obs["type"] == "point":
            dmin = _distance_point_to_segment(obs["x"], obs["y"], a, b)
        else:
            dmin = _distance_segment_to_rect(a, b, obs)
        if dmin < clearance:
            return False
    return True


def _polyline_length(path):
    if not path or len(path) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(path)):
        total += _dist(path[i-1], path[i])
    return total


def _build_occupancy(obstacles, step=GRID_STEP_CM):
    """Return occupancy grid and helpers for planning. True=blocked."""
    gw = int(math.ceil(ARENA_WIDTH_CM / step)) + 1
    gh = int(math.ceil(ARENA_HEIGHT_CM / step)) + 1
    occ = [[False] * gw for _ in range(gh)]
    for gy in range(gh):
        y = gy * step
        for gx in range(gw):
            x = gx * step
            blocked = False
            for obs in obstacles:
                clear = obs.get("clearance", MIN_CLEARANCE_CM)
                if obs["type"] == "point":
                    dx = x - obs["x"]
                    dy = y - obs["y"]
                    if dx * dx + dy * dy <= clear * clear:
                        blocked = True
                        break
                else:
                    if _distance_point_to_rect(x, y, obs) <= clear:
                        blocked = True
                        break
            occ[gy][gx] = blocked
    return occ, gw, gh, step


def _in_bounds(gx, gy, gw, gh):
    return 0 <= gx < gw and 0 <= gy < gh


def _neighbors8(gx, gy):
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            yield gx + dx, gy + dy


def _heuristic(a, b):
    ax, ay = a; bx, by = b
    return math.hypot(ax - bx, ay - by)


def _astar(start_cm, goal_cm, obstacles, step=GRID_STEP_CM):
    """Plan a polyline from start to goal using A* on a clearance-inflated occupancy grid."""
    occ, gw, gh, step = _build_occupancy(obstacles, step)
    def pt_to_grid(p):
        x, y = p
        gx = int(round(x / step))
        gy = int(round(y / step))
        return gx, gy
    def grid_to_pt(g):
        gx, gy = g
        return (gx * step, gy * step)

    start_g = pt_to_grid(start_cm)
    goal_g = pt_to_grid(goal_cm)
    if not _in_bounds(*start_g, gw, gh) or not _in_bounds(*goal_g, gw, gh):
        return None
    if occ[start_g[1]][start_g[0]] or occ[goal_g[1]][goal_g[0]]:
        # Start or goal inside blocked region
        return None

    import heapq
    openh = []
    heapq.heappush(openh, (0.0, start_g))
    came = {start_g: None}
    gscore = {start_g: 0.0}
    while openh:
        _, cur = heapq.heappop(openh)
        if cur == goal_g:
            # Reconstruct
            path = []
            c = cur
            while c is not None:
                path.append(grid_to_pt(c))
                c = came[c]
            path.reverse()
            return path
        cx, cy = cur
        for nx, ny in _neighbors8(cx, cy):
            if not _in_bounds(nx, ny, gw, gh):
                continue
            if occ[ny][nx]:
                continue
            # prevent diagonal cutting corners: require adjacent orthogonals to be free
            if nx != cx and ny != cy:
                if occ[cy][nx] or occ[ny][cx]:
                    continue
            step_cost = math.hypot((nx - cx), (ny - cy)) * step
            tentative = gscore[cur] + step_cost
            nb = (nx, ny)
            if tentative < gscore.get(nb, float('inf')):
                came[nb] = cur
                gscore[nb] = tentative
                f = tentative + _heuristic(grid_to_pt(nb), grid_to_pt(goal_g))
                heapq.heappush(openh, (f, nb))
    return None


def _smooth_polyline(path_cm, obstacles):
    if not path_cm or len(path_cm) <= 2:
        return path_cm
    smoothed = [path_cm[0]]
    i = 0
    while i < len(path_cm) - 1:
        j = len(path_cm) - 1
        # Find the farthest j such that segment (i->j) is clear
        while j > i + 1 and not _segment_is_clear(path_cm[i], path_cm[j], obstacles):
            j -= 1
        smoothed.append(path_cm[j])
        i = j
    return smoothed


def _plan_segment_with_clearance(a, b, obstacles):
    """Return a clearance-respecting polyline from a to b (inclusive)."""
    if _segment_is_clear(a, b, obstacles):
        return [a, b]
    path = _astar(a, b, obstacles, GRID_STEP_CM)
    if path is None:
        return None
    path = _smooth_polyline(path, obstacles)
    # Ensure back to exact endpoints
    if path[0] != a:
        path[0] = a
    if path[-1] != b:
        path[-1] = b
    return path


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


def load_no_go_zones(script_dir):
    cfg = os.path.join(script_dir, "nogo_zones.json")
    points = []
    rectangles = []
    clearance = NO_GO_CLEARANCE_CM
    if not os.path.exists(cfg):
        return points, rectangles, clearance
    try:
        with open(cfg, "r", encoding="utf-8") as f:
            data = json.load(f)
        clearance = float(data.get("clearance_cm", clearance))
        for entry in data.get("points_cm", []):
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                points.append((float(entry[0]), float(entry[1])))
        for entry in data.get("rectangles_cm", []):
            if isinstance(entry, (list, tuple)) and len(entry) >= 4:
                x1, y1, x2, y2 = map(float, entry[:4])
                rectangles.append((x1, y1, x2, y2))
    except Exception:
        # Malformed file; ignore and fall back to defaults
        return [], [], NO_GO_CLEARANCE_CM
    return points, rectangles, clearance


def save_no_go_zones(script_dir, points, rectangles, clearance=NO_GO_CLEARANCE_CM):
    cfg = os.path.join(script_dir, "nogo_zones.json")
    data = {
        "clearance_cm": float(clearance),
        "points_cm": [[float(x), float(y)] for (x, y) in points],
        "rectangles_cm": [[float(x1), float(y1), float(x2), float(y2)] for (x1, y1, x2, y2) in rectangles],
    }
    try:
        with open(cfg, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        print(f"ERROR saving nogo_zones.json: {exc}")


def load_path_config(script_dir, defaults=None):
    if defaults is None:
        # Default: bottom-right-ish for both start and end
        defaults = ((ARENA_WIDTH_CM - 6.0, ARENA_HEIGHT_CM - 14.0),
                    (ARENA_WIDTH_CM - 6.0, ARENA_HEIGHT_CM - 14.0))
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


def load_final_destination(script_dir):
    """
    Load the final destination point from path_config.json.
    Returns None if not set.
    """
    cfg_path = os.path.join(script_dir, "path_config.json")
    if not os.path.exists(cfg_path):
        return None
    try:
        with open(cfg_path, "r") as f:
            data = json.load(f)
        fd = data.get("final_destination_cm")
        if fd and len(fd) == 2:
            return (float(fd[0]), float(fd[1]))
        return None
    except Exception:
        return None


def save_final_destination(script_dir, point):
    """
    Save the final destination point to path_config.json.
    Preserves existing start/end points.
    """
    cfg_path = os.path.join(script_dir, "path_config.json")
    data = {}
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r") as f:
                data = json.load(f)
        except Exception:
            pass
    
    if point is None:
        data.pop("final_destination_cm", None)
    else:
        data["final_destination_cm"] = [float(point[0]), float(point[1])]
    
    try:
        with open(cfg_path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        print(f"ERROR saving final destination: {exc}")


def build_auto_path(script_dir, start_xy=None, end_xy=None, final_dest_xy=None, enable_corner_recalibration=True):
    """
    Build a path going from start through all red fruits and ending at end, avoiding others.
    After reaching end_xy, optionally:
    1. Reverse 10cm from end point (if enable_corner_recalibration is True)
    2. Ram into bottom-left corner for recalibration (forward until corner hit)
    3. Collect black fruits
    4. Go to final destination
    
    Args:
        script_dir: Directory containing config files
        start_xy: Starting position (x, y) in cm
        end_xy: End position (x, y) in cm after collecting red fruits
        final_dest_xy: Final destination after black fruit collection
        enable_corner_recalibration: If True, adds reverse + corner ram sequence
    
    - Reads red.csv as targets, black.csv and untagged (green) fruits as obstacles.
    - If green.csv not provided, greens are synthesized from fruit_ui defaults.
    - Produces checkpoints_cm.csv (waypoints) and path.csv (turn,dist relative plan).
    """
    if start_xy is None or end_xy is None:
        start_xy, end_xy = load_path_config(script_dir)
    
    if final_dest_xy is None:
        final_dest_xy = load_final_destination(script_dir)

    reds, blacks, greens = load_fruits_for_overlay(script_dir)

    # Obstacles are non-reds
    def not_near_red(p, reds_list, tol=1e-3):
        px, py = p
        for (rx, ry) in reds_list:
            if math.hypot(px - rx, py - ry) <= tol:
                return False
        return True
    obstacles = []
    for (bx, by) in blacks:
        obstacles.append(_make_point_obstacle(bx, by, MIN_CLEARANCE_CM))
    for gx, gy in greens:
        if not_near_red((gx, gy), reds):
            obstacles.append(_make_point_obstacle(gx, gy, MIN_CLEARANCE_CM))

    nogo_points, nogo_rects, nogo_clearance = load_no_go_zones(script_dir)
    nogo_clearance = max(nogo_clearance, NO_GO_CLEARANCE_CM)
    print(f"Path planning obstacle setup:")
    print(f"  MIN_CLEARANCE_CM (fruits): {MIN_CLEARANCE_CM} cm")
    print(f"  No-go zone clearance: {nogo_clearance} cm")
    print(f"  Black fruits: {len(blacks)}")
    print(f"  Green fruits (obstacles): {len([g for g in greens if not_near_red(g, reds)])}")
    print(f"  No-go points: {len(nogo_points)}")
    print(f"  No-go rectangles: {len(nogo_rects)}")
    for (nx, ny) in nogo_points:
        obstacles.append(_make_point_obstacle(nx, ny, nogo_clearance))
    for (x1, y1, x2, y2) in nogo_rects:
        obstacles.append(_make_rect_obstacle(x1, y1, x2, y2, nogo_clearance))

    if not reds:
        return [], []

    # Greedy selection by actual routed path length (A*), favoring feasible and maximally clear legs
    remaining = reds[:]
    order = []
    cur = start_xy
    while remaining:
        scored = []
        for r in remaining:
            poly = _plan_segment_with_clearance(cur, r, obstacles)
            if poly is None:
                continue
            scored.append((_polyline_length(poly), r, poly))
        if not scored:
            # fallback: choose nearest by Euclidean distance
            chosen = min(remaining, key=lambda r: _dist(cur, r))
            poly = [cur, chosen] if _segment_is_clear(cur, chosen, obstacles) else _plan_segment_with_clearance(cur, chosen, obstacles)
        else:
            scored.sort(key=lambda t: t[0])
            _, chosen, poly = scored[0]
        # Append intermediate waypoints (excluding current)
        if poly and len(poly) > 1:
            # Avoid duplicating cur
            for wp in poly[1:]:
                order.append(wp)
        remaining.remove(chosen)
        cur = chosen

    # Validate last hop to end respects clearance; insert waypoints if needed
    tail = _plan_segment_with_clearance(cur, end_xy, obstacles)
    if tail is None:
        tail = [cur, end_xy]
    checkpoints = [start_xy]
    # order might contain intermediate waypoints and reds; ensure we don't duplicate start
    for wp in order:
        if len(checkpoints) == 0 or wp != checkpoints[-1]:
            checkpoints.append(wp)
    # Append tail except first point (it's cur and likely already present)
    for wp in tail[1:]:
        if wp != checkpoints[-1]:
            checkpoints.append(wp)

    # --- Enhanced path: corner recalibration, reverse, black fruits, final destination ---
    recalibration_checkpoint_idx = None  # Track where recalibration ram starts
    reverse_checkpoint_idx = None  # Track where reverse starts
    
    # Step 1: Corner recalibration sequence (if enabled and final destination is set)
    if enable_corner_recalibration and final_dest_xy is not None:
        last_checkpoint = checkpoints[-1]
        ex, ey = last_checkpoint
        
        print(f"\n🔄 Corner recalibration sequence enabled")
        
        # Step 1a: Reverse 10cm from end point
        # Calculate reverse direction (opposite of the heading toward end point)
        if len(checkpoints) >= 2:
            prev_x, prev_y = checkpoints[-2]
            dx = ex - prev_x
            dy = ey - prev_y
            heading_len = math.hypot(dx, dy)
            if heading_len > 0.1:
                # Reverse 10cm in opposite direction of approach
                reverse_distance = 10.0
                reverse_x = ex - (dx / heading_len) * reverse_distance
                reverse_y = ey - (dy / heading_len) * reverse_distance
                # Clamp to arena bounds
                reverse_x = max(5.0, min(ARENA_WIDTH_CM - 5.0, reverse_x))
                reverse_y = max(5.0, min(ARENA_HEIGHT_CM - 5.0, reverse_y))
                reverse_point = (reverse_x, reverse_y)
                
                # Check if reverse path is clear
                reverse_path = _plan_segment_with_clearance(last_checkpoint, reverse_point, obstacles)
                if reverse_path is not None:
                    reverse_checkpoint_idx = len(checkpoints)  # Mark where reverse starts
                    print(f"   Reversing 10cm from ({ex:.1f},{ey:.1f}) to ({reverse_x:.1f},{reverse_y:.1f})")
                    # Add reverse waypoints
                    for wp in reverse_path[1:]:
                        if wp != checkpoints[-1]:
                            checkpoints.append(wp)
                else:
                    print(f"⚠️  Cannot reverse 10cm with required clearance")
        
        # Step 1b: Ram into bottom-left corner (0, ARENA_HEIGHT_CM)
        # From current position, drive toward bottom-left corner
        current_pos = checkpoints[-1]
        cx, cy = current_pos
        
        # Target: Bottom-left corner
        target_corner = (0, ARENA_HEIGHT_CM)
        
        # Calculate direction to corner
        dx_to_corner = target_corner[0] - cx
        dy_to_corner = target_corner[1] - cy
        dist_to_corner = math.hypot(dx_to_corner, dy_to_corner)
        
        if dist_to_corner > 0.1:
            # Ram point: go all the way to the corner (or as close as clearance allows)
            # We'll aim for a point just before the corner to maintain clearance from walls
            ram_distance = max(5.0, dist_to_corner - 2.0)  # Leave 2cm from corner
            ram_x = cx + (dx_to_corner / dist_to_corner) * ram_distance
            ram_y = cy + (dy_to_corner / dist_to_corner) * ram_distance
            ram_point = (ram_x, ram_y)
            
            print(f"   Ramming into bottom-left corner: ({cx:.1f},{cy:.1f}) → ({ram_x:.1f},{ram_y:.1f})")
            
            # Check if ram path is clear
            ram_path = _plan_segment_with_clearance(current_pos, ram_point, obstacles)
            if ram_path is not None:
                recalibration_checkpoint_idx = len(checkpoints)  # Mark where ram starts
                # Add ram waypoints
                for wp in ram_path[1:]:
                    if wp != checkpoints[-1]:
                        checkpoints.append(wp)
                print(f"   ✅ Recalibration sequence added")
            else:
                print(f"⚠️  Cannot ram into bottom-left corner with required clearance, skipping")
        else:
            print(f"⚠️  Already at or very close to bottom-left corner")
    
    # Step 2: Black fruit collection (regardless of recalibration setting)
    if final_dest_xy is not None:
        # Build obstacles that exclude blacks (only greens and reds as obstacles)
        black_obstacles = []
        # Red fruits are still obstacles when collecting blacks
        for (rx, ry) in reds:
            black_obstacles.append(_make_point_obstacle(rx, ry, MIN_CLEARANCE_CM))
        for gx, gy in greens:
            black_obstacles.append(_make_point_obstacle(gx, gy, MIN_CLEARANCE_CM))
        # Add no-go zones
        for (nx, ny) in nogo_points:
            black_obstacles.append(_make_point_obstacle(nx, ny, nogo_clearance))
        for (x1, y1, x2, y2) in nogo_rects:
            black_obstacles.append(_make_rect_obstacle(x1, y1, x2, y2, nogo_clearance))
        
        # Route through black fruits using greedy nearest neighbor
        if blacks:
            remaining_blacks = blacks[:]
            cur_pos = checkpoints[-1]
            while remaining_blacks:
                # Find nearest black fruit
                nearest_black = min(remaining_blacks, key=lambda b: _dist(cur_pos, b))
                
                # Plan path to this black fruit with proper clearance
                black_path = _plan_segment_with_clearance(cur_pos, nearest_black, black_obstacles)
                if black_path is None:
                    # If A* fails, skip this black fruit (it's unreachable with clearance)
                    print(f"⚠️  Cannot reach black fruit at ({nearest_black[0]:.1f},{nearest_black[1]:.1f}) with required clearance, skipping")
                    remaining_blacks.remove(nearest_black)
                    continue
                
                # Add waypoints (excluding first point which is cur_pos)
                for wp in black_path[1:]:
                    if wp != checkpoints[-1]:
                        checkpoints.append(wp)
                
                remaining_blacks.remove(nearest_black)
                cur_pos = nearest_black
        
        # Step 3: Go to final destination
        final_path = _plan_segment_with_clearance(checkpoints[-1], final_dest_xy, black_obstacles)
        if final_path is None:
            print(f"⚠️  Cannot reach final destination ({final_dest_xy[0]:.1f},{final_dest_xy[1]:.1f}) with required clearance")
            print(f"     Final destination may be blocked or too close to obstacles. Path will end at last reachable point.")
        else:
            for wp in final_path[1:]:
                if wp != checkpoints[-1]:
                    checkpoints.append(wp)

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
        
        # Special case: reverse segment (negative distance)
        if reverse_checkpoint_idx is not None and i == reverse_checkpoint_idx:
            # This is the reverse segment - make distance negative
            seg_dist = -seg_dist
            # No turn needed for pure reverse
            rel_turn = 0.0
        
        segs.append((rel_turn, seg_dist))
        heading_deg = abs_heading

    # Validate clearance for all segments
    print(f"\n📏 Validating path clearance ({len(checkpoints)-1} segments)...")
    min_clearances = []
    violations = []
    for i in range(1, len(checkpoints)):
        a = checkpoints[i-1]
        b = checkpoints[i]
        min_clear = _segment_min_clearance(a, b, obstacles)
        min_clearances.append(min_clear)
        if min_clear < MIN_CLEARANCE_CM:
            violations.append((i-1, a, b, min_clear))
    
    if violations:
        print(f"⚠️  WARNING: {len(violations)} segment(s) violate minimum clearance:")
        for seg_idx, a, b, clear in violations[:5]:  # Show first 5
            print(f"   Segment {seg_idx}: ({a[0]:.1f},{a[1]:.1f}) → ({b[0]:.1f},{b[1]:.1f}) only {clear:.2f}cm clear (need {MIN_CLEARANCE_CM}cm)")
    else:
        avg_clear = sum(min_clearances) / len(min_clearances) if min_clearances else 0
        min_overall = min(min_clearances) if min_clearances else 0
        print(f"✅ All segments respect clearance (min: {min_overall:.2f}cm, avg: {avg_clear:.2f}cm)")

    write_checkpoints(script_dir, checkpoints)
    write_path(script_dir, segs)
    return checkpoints, segs
