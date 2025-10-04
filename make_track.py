#!/usr/bin/env python3
# make_track.py - Track recording tool for robot path following
"""
Interactive tool to record robot movement paths by clicking waypoints.
Saves data in format: angle, measure (distance in cm)
Angle convention: Positive = Right turns, Negative = Left turns
Similar to measure_arena.py but focused on track recording.
"""
import math
import os
import sys
import pygame as pg
import csv


# Physical dimensions of the arena in centimeters (precise)
ARENA_WIDTH_CM = 118.1
ARENA_HEIGHT_CM = 114.3


def load_image(path: str) -> pg.Surface:
    if not os.path.exists(path):
        print(f"ERROR: Image not found: {path}")
        pg.quit()
        sys.exit(1)
    try:
        img = pg.image.load(path)
        return img
    except Exception as e:
        print(f"ERROR: Failed to load image '{path}': {e}")
        pg.quit()
        sys.exit(1)


def compute_scale_px_per_cm(img_w_px: int, img_h_px: int):
    # pixels per cm in each axis
    px_per_cm_x = img_w_px / ARENA_WIDTH_CM
    px_per_cm_y = img_h_px / ARENA_HEIGHT_CM
    cm_per_px_x = 1.0 / px_per_cm_x
    cm_per_px_y = 1.0 / px_per_cm_y
    return px_per_cm_x, px_per_cm_y, cm_per_px_x, cm_per_px_y


def fit_scale_and_offset(window_size, img_size):
    win_w, win_h = window_size
    img_w, img_h = img_size
    if img_w == 0 or img_h == 0:
        return 1.0, (0, 0)
    scale = min(win_w / img_w, win_h / img_h)
    # Center the image
    offset_x = (win_w - img_w * scale) / 2
    offset_y = (win_h - img_h * scale) / 2
    return scale, (offset_x, offset_y)


def screen_to_image(pos, scale, offset):
    sx, sy = pos
    ox, oy = offset
    ix = (sx - ox) / scale
    iy = (sy - oy) / scale
    return (ix, iy)


def image_to_screen(pos, scale, offset):
    ix, iy = pos
    ox, oy = offset
    sx = ox + ix * scale
    sy = oy + iy * scale
    return (sx, sy)


def heading_from_up_deg(vx_cm: float, vy_cm: float) -> float:
    """Return bearing in degrees where 0° = up (-Y), 90° = right, 180° = down, 270° = left."""
    if abs(vx_cm) < 1e-9 and abs(vy_cm) < 1e-9:
        return 0.0
    return math.degrees(math.atan2(vx_cm, -vy_cm)) % 360.0


def wrap_to_180(deg: float) -> float:
    """Wrap angle to (-180, 180]."""
    d = (deg + 180.0) % 360.0 - 180.0
    if d <= -180.0:
        d += 360.0
    return d


def snap_point_to_45_deg(p1_img, p2_img, px_per_cm_x, px_per_cm_y):
    """Snap p2 direction relative to p1 to nearest 45°."""
    x1, y1 = p1_img
    x2, y2 = p2_img
    dx_px = x2 - x1
    dy_px = y2 - y1
    if abs(dx_px) < 1e-9 and abs(dy_px) < 1e-9:
        return p2_img
    # Convert to cm-space vector
    vx_cm = dx_px * (1.0 / px_per_cm_x)
    vy_cm = dy_px * (1.0 / px_per_cm_y)
    length_cm = math.hypot(vx_cm, vy_cm)
    curr_heading = heading_from_up_deg(vx_cm, vy_cm)
    snapped_heading = round(curr_heading / 45.0) * 45.0
    rad = math.radians(snapped_heading)
    vx_cm2 = length_cm * math.sin(rad)
    vy_cm2 = -length_cm * math.cos(rad)
    # Convert back to pixels
    dx_px2 = vx_cm2 * px_per_cm_x
    dy_px2 = vy_cm2 * px_per_cm_y
    return (x1 + dx_px2, y1 + dy_px2)


def draw_text(surface, text, pos, font, color=(255, 255, 255), shadow=True):
    x, y = pos
    if shadow:
        sh = font.render(text, True, (0, 0, 0))
        surface.blit(sh, (x + 1, y + 1))
    img = font.render(text, True, color)
    surface.blit(img, (x, y))


def draw_scale_bar(surface, scale, offset, img_size, px_per_cm_x, px_per_cm_y, font):
    img_w, img_h = img_size
    avg_px_per_cm = (px_per_cm_x + px_per_cm_y) / 2.0
    anisotropy = abs(px_per_cm_x - px_per_cm_y) / max(px_per_cm_x, px_per_cm_y)
    px_per_cm_for_bar = px_per_cm_x if anisotropy > 0.01 else avg_px_per_cm

    win_w, win_h = surface.get_size()
    target_px = win_w * 0.25
    candidates_cm = [2, 5, 10, 20, 25, 50, 100]
    bar_cm = min(candidates_cm, key=lambda c: abs(c * px_per_cm_for_bar * scale - target_px))
    bar_px_on_screen = bar_cm * px_per_cm_for_bar * scale

    pad = 16
    y = win_h - pad
    x0 = pad
    x1 = pad + bar_px_on_screen

    color = (255, 255, 255)
    pg.draw.line(surface, color, (x0, y), (x1, y), 3)
    pg.draw.line(surface, color, (x0, y - 6), (x0, y + 6), 3)
    pg.draw.line(surface, color, (x1, y - 6), (x1, y + 6), 3)
    draw_text(surface, f"{bar_cm} cm", (x0, y - 24), font)


def draw_grid(surface, scale, offset, img_size, px_per_cm_x, px_per_cm_y):
    img_w, img_h = img_size
    win_w, win_h = surface.get_size()
    grid_cm = 10  # 10 cm grid
    step_x = px_per_cm_x * grid_cm * scale
    step_y = px_per_cm_y * grid_cm * scale
    ox, oy = offset
    start_x = int(max(0, math.floor((0 - ox) / step_x)))
    start_y = int(max(0, math.floor((0 - oy) / step_y)))
    max_x_lines = int(math.ceil((win_w - ox) / step_x)) + 1
    max_y_lines = int(math.ceil((win_h - oy) / step_y)) + 1

    grid_color = (255, 255, 255)
    alpha = 40
    grid_surf = pg.Surface((win_w, win_h), pg.SRCALPHA)
    # Vertical lines
    for i in range(start_x, max_x_lines):
        x = ox + i * step_x
        pg.draw.line(grid_surf, (*grid_color, alpha), (x, 0), (x, win_h), 1)
    # Horizontal lines
    for j in range(start_y, max_y_lines):
        y = oy + j * step_y
        pg.draw.line(grid_surf, (*grid_color, alpha), (0, y), (win_w, y), 1)
    surface.blit(grid_surf, (0, 0))


def main():
    pg.init()
    pg.display.set_caption("Track Recording Tool")

    script_dir = os.path.dirname(__file__)
    image_path = os.path.join(script_dir, "arena.png")
    img = load_image(image_path)
    img_w, img_h = img.get_width(), img.get_height()

    px_per_cm_x, px_per_cm_y, cm_per_px_x, cm_per_px_y = compute_scale_px_per_cm(img_w, img_h)

    # Prepare window
    info = pg.display.Info()
    max_w = int(info.current_w * 0.95)
    max_h = int(info.current_h * 0.90)
    win_w = min(img_w, max_w)
    win_h = min(img_h, max_h)
    screen = pg.display.set_mode((win_w, win_h), pg.RESIZABLE)
    
    try:
        img = img.convert_alpha()
    except Exception:
        img = img.convert()

    font = pg.font.SysFont(None, 18)
    font_big = pg.font.SysFont(None, 24)

    # CSV output path for track data
    csv_path = os.path.join(script_dir, "track.csv")
    try:
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["angle", "measure"])
    except Exception as e:
        print(f"Warning: Could not initialize CSV file '{csv_path}': {e}")

    # Track recording state
    waypoints_img = []  # list of (x,y) in image pixels
    mouse_img = None    # current mouse position in image coords
    show_grid = True
    show_help = True

    clock = pg.time.Clock()

    running = True
    while running:
        # Recompute layout
        win_w, win_h = screen.get_size()
        scale, offset = fit_scale_and_offset((win_w, win_h), (img_w, img_h))

        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False
            elif event.type == pg.KEYDOWN:
                if event.key in (pg.K_ESCAPE, pg.K_q):
                    running = False
                elif event.key == pg.K_c:
                    waypoints_img.clear()
                    print("Track cleared")
                elif event.key == pg.K_g:
                    show_grid = not show_grid
                elif event.key == pg.K_h:
                    show_help = not show_help
                elif event.key == pg.K_f:
                    pg.display.toggle_fullscreen()
                elif event.key in (pg.K_RETURN, pg.K_KP_ENTER):
                    # Save track as: "angle, measure" per segment
                    if len(waypoints_img) < 2:
                        print("No track: add at least two waypoints.")
                    else:
                        print("Track (angle, measure):")
                        rows = []
                        for i in range(1, len(waypoints_img)):
                            p1 = waypoints_img[i - 1]
                            p2 = waypoints_img[i]
                            dx = (p2[0] - p1[0])
                            dy = (p2[1] - p1[1])
                            vx_cm = dx * (1.0 / px_per_cm_x)
                            vy_cm = dy * (1.0 / px_per_cm_y)
                            distance_cm = math.hypot(vx_cm, vy_cm)
                            
                            # Calculate angle relative to previous segment
                            if i == 1:
                                # First segment: angle relative to "up" (0°)
                                angle_deg = heading_from_up_deg(vx_cm, vy_cm)
                            else:
                                # Subsequent segments: angle relative to previous direction
                                prev_p1 = waypoints_img[i - 2]
                                prev_p2 = waypoints_img[i - 1]
                                prev_dx = (prev_p2[0] - prev_p1[0])
                                prev_dy = (prev_p2[1] - prev_p1[1])
                                prev_vx_cm = prev_dx * (1.0 / px_per_cm_x)
                                prev_vy_cm = prev_dy * (1.0 / px_per_cm_y)
                                prev_heading = heading_from_up_deg(prev_vx_cm, prev_vy_cm)
                                curr_heading = heading_from_up_deg(vx_cm, vy_cm)
                                # Flip sign so right turns are positive
                                angle_deg = wrap_to_180(curr_heading - prev_heading)
                            
                            print(f"{angle_deg:.1f}, {distance_cm:.2f}")
                            rows.append((f"{angle_deg:.1f}", f"{distance_cm:.2f}"))
                        
                        # Write CSV
                        try:
                            with open(csv_path, "w", newline="") as f:
                                writer = csv.writer(f)
                                writer.writerow(["angle", "measure"])
                                for r in rows:
                                    writer.writerow(r)
                            print(f"Track saved to: {csv_path}")
                        except Exception as e:
                            print(f"ERROR: Could not write CSV '{csv_path}': {e}")
                            
            elif event.type == pg.MOUSEBUTTONDOWN:
                if event.button == 1:  # left: add waypoint
                    mx, my = event.pos
                    ix, iy = screen_to_image((mx, my), scale, offset)
                    if 0 <= ix <= img_w and 0 <= iy <= img_h:
                        mods = pg.key.get_mods()
                        if (mods & pg.KMOD_SHIFT) and len(waypoints_img) >= 1:
                            snapped = snap_point_to_45_deg(waypoints_img[-1], (ix, iy), px_per_cm_x, px_per_cm_y)
                            sx = min(max(snapped[0], 0), img_w)
                            sy = min(max(snapped[1], 0), img_h)
                            waypoints_img.append((sx, sy))
                        else:
                            waypoints_img.append((ix, iy))
                        print(f"Added waypoint {len(waypoints_img)}: ({ix:.1f}, {iy:.1f})")
                elif event.button == 3:  # right: undo last waypoint
                    if waypoints_img:
                        removed = waypoints_img.pop()
                        print(f"Removed waypoint: ({removed[0]:.1f}, {removed[1]:.1f})")
                        
            elif event.type == pg.MOUSEMOTION:
                mx, my = event.pos
                ix, iy = screen_to_image((mx, my), scale, offset)
                if 0 <= ix <= img_w and 0 <= iy <= img_h:
                    mods = pg.key.get_mods()
                    if (mods & pg.KMOD_SHIFT) and len(waypoints_img) >= 1:
                        snapped = snap_point_to_45_deg(waypoints_img[-1], (ix, iy), px_per_cm_x, px_per_cm_y)
                        sx = min(max(snapped[0], 0), img_w)
                        sy = min(max(snapped[1], 0), img_h)
                        mouse_img = (sx, sy)
                    else:
                        mouse_img = (ix, iy)
                else:
                    mouse_img = None

        # Draw
        screen.fill((20, 20, 24))
        if abs(scale - 1.0) < 1e-6:
            screen.blit(img, offset)
        else:
            scaled_size = (int(img_w * scale), int(img_h * scale))
            scaled_img = pg.transform.smoothscale(img, scaled_size)
            screen.blit(scaled_img, offset)

        if show_grid:
            draw_grid(screen, scale, offset, (img_w, img_h), px_per_cm_x, px_per_cm_y)

        # Draw track segments
        for i in range(1, len(waypoints_img)):
            p1 = waypoints_img[i - 1]
            p2 = waypoints_img[i]
            a = image_to_screen(p1, scale, offset)
            b = image_to_screen(p2, scale, offset)
            pg.draw.line(screen, (255, 215, 0), a, b, 20)
            # Draw waypoints
            pg.draw.circle(screen, (255, 215, 0), (int(a[0]), int(a[1])), 6, 2)
            pg.draw.circle(screen, (255, 215, 0), (int(b[0]), int(b[1])), 6, 2)
            
            # Calculate and display segment info
            dx = (p2[0] - p1[0])
            dy = (p2[1] - p1[1])
            vx_cm = dx * (1.0 / px_per_cm_x)
            vy_cm = dy * (1.0 / px_per_cm_y)
            distance_cm = math.hypot(vx_cm, vy_cm)
            
            # Calculate angle
            if i == 1:
                angle_deg = heading_from_up_deg(vx_cm, vy_cm)
            else:
                prev_p1 = waypoints_img[i - 2]
                prev_p2 = waypoints_img[i - 1]
                prev_dx = (prev_p2[0] - prev_p1[0])
                prev_dy = (prev_p2[1] - prev_p1[1])
                prev_vx_cm = prev_dx * (1.0 / px_per_cm_x)
                prev_vy_cm = prev_dy * (1.0 / px_per_cm_y)
                prev_heading = heading_from_up_deg(prev_vx_cm, prev_vy_cm)
                curr_heading = heading_from_up_deg(vx_cm, vy_cm)
                # Flip sign so right turns are positive
                angle_deg = -wrap_to_180(curr_heading - prev_heading)
            
            mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
            draw_text(screen, f"{distance_cm:.1f}cm @ {angle_deg:.1f}°", (mid[0] + 8, mid[1] + 8), font_big)

        # Preview from last waypoint to mouse position
        if mouse_img and len(waypoints_img) >= 1:
            p1 = waypoints_img[-1]
            p2 = mouse_img
            a = image_to_screen(p1, scale, offset)
            b = image_to_screen(p2, scale, offset)
            pg.draw.line(screen, (0, 200, 255), a, b, 15)
            pg.draw.circle(screen, (0, 200, 255), (int(a[0]), int(a[1])), 6, 2)
            pg.draw.circle(screen, (0, 200, 255), (int(b[0]), int(b[1])), 6, 2)
            
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            vx_cm = dx * (1.0 / px_per_cm_x)
            vy_cm = dy * (1.0 / px_per_cm_y)
            distance_cm = math.hypot(vx_cm, vy_cm)
            
            if len(waypoints_img) >= 2:
                prev_p1 = waypoints_img[-2]
                prev_p2 = waypoints_img[-1]
                prev_dx = (prev_p2[0] - prev_p1[0])
                prev_dy = (prev_p2[1] - prev_p1[1])
                prev_vx_cm = prev_dx * (1.0 / px_per_cm_x)
                prev_vy_cm = prev_dy * (1.0 / px_per_cm_y)
                prev_heading = heading_from_up_deg(prev_vx_cm, prev_vy_cm)
                curr_heading = heading_from_up_deg(vx_cm, vy_cm)
                # Flip sign so right turns are positive
                angle_deg = -wrap_to_180(curr_heading - prev_heading)
            else:
                angle_deg = heading_from_up_deg(vx_cm, vy_cm)
            
            draw_text(screen, f"{distance_cm:.1f}cm @ {angle_deg:.1f}°", (b[0] + 8, b[1] + 8), font_big)

        # Draw waypoint numbers
        for i, (x, y) in enumerate(waypoints_img):
            screen_pos = image_to_screen((x, y), scale, offset)
            draw_text(screen, str(i + 1), (screen_pos[0] + 10, screen_pos[1] - 10), font_big, (255, 255, 0))

        # Overlays
        draw_scale_bar(screen, scale, offset, (img_w, img_h), px_per_cm_x, px_per_cm_y, font)

        info_lines = [
            f"Track Recording Tool - Waypoints: {len(waypoints_img)}",
            f"Image: {img_w} x {img_h} px  |  Arena: {ARENA_WIDTH_CM:.1f} x {ARENA_HEIGHT_CM:.1f} cm",
            f"Px/cm: X={px_per_cm_x:.3f}, Y={px_per_cm_y:.3f}",
        ]

        y = 10
        for line in info_lines:
            draw_text(screen, line, (10, y), font)
            y += 18

        if show_help:
            help_lines = [
                "Track Recording Controls:",
                "  Left click: add waypoint",
                "  Right click: undo last waypoint",
                "  Shift: snap to 45° increments",
                "  Enter: save track to track.csv (angle, measure format)",
                "  C: clear track   G: toggle grid   H: toggle help   F: fullscreen   Esc/Q: quit",
                "",
                "Angle Convention:",
                "  Positive angles = Right turns",
                "  Negative angles = Left turns",
            ]
            # Background box
            box_w = max(font.size(s)[0] for s in help_lines) + 16
            box_h = len(help_lines) * 18 + 12
            box = pg.Surface((box_w, box_h), pg.SRCALPHA)
            box.fill((0, 0, 0, 140))
            screen.blit(box, (10, y + 6))
            yy = y + 12
            for line in help_lines:
                draw_text(screen, line, (18, yy), font)
                yy += 18

        pg.display.flip()
        clock.tick(60)

    pg.quit()


if __name__ == "__main__":
    main()
