import math
import os
import sys
import pygame as pg
import csv


# Physical dimensions of the arena in centimeters
ARENA_WIDTH_CM = 118.0
ARENA_HEIGHT_CM = 114.0


def load_image(path: str) -> pg.Surface:
    if not os.path.exists(path):
        print(f"ERROR: Image not found: {path}")
        pg.quit()
        sys.exit(1)
    try:
        # Load without conversion; we'll convert after creating the display
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
    """Return bearing in degrees where 0° = up (-Y), 90° = right, 180° = down, 270° = left.
    Uses image coordinate system with Y down; we negate vy for 'up'."""
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
    """Snap p2 direction relative to p1 to nearest 45° (based on physical cm axes).
    Keep the original length in cm, return snapped endpoint in image pixels.
    """
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
    # 0° up => (0, -1). With our convention: vx = sin(theta), vy = -cos(theta)
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
    # Use average px/cm for the bar length when anisotropy is small; otherwise use X axis scale
    avg_px_per_cm = (px_per_cm_x + px_per_cm_y) / 2.0
    anisotropy = abs(px_per_cm_x - px_per_cm_y) / max(px_per_cm_x, px_per_cm_y)
    px_per_cm_for_bar = px_per_cm_x if anisotropy > 0.01 else avg_px_per_cm

    # Choose a nice bar length in cm: 5, 10, 20, 50 depending on window width
    win_w, win_h = surface.get_size()
    target_px = win_w * 0.25
    candidates_cm = [2, 5, 10, 20, 25, 50, 100]
    bar_cm = min(candidates_cm, key=lambda c: abs(c * px_per_cm_for_bar * scale - target_px))
    bar_px_on_screen = bar_cm * px_per_cm_for_bar * scale

    # Position bottom-left with padding
    pad = 16
    y = win_h - pad
    x0 = pad
    x1 = pad + bar_px_on_screen

    # Bar
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
    # Start indices so lines align with image origin
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
    pg.display.set_caption("Arena Measurement Tool")

    script_dir = os.path.dirname(__file__)
    image_path = os.path.join(script_dir, "arena.png")
    img = load_image(image_path)
    img_w, img_h = img.get_width(), img.get_height()

    px_per_cm_x, px_per_cm_y, cm_per_px_x, cm_per_px_y = compute_scale_px_per_cm(img_w, img_h)

    # Prepare window roughly fitting the image but with margins
    info = pg.display.Info()
    max_w = int(info.current_w * 0.95)
    max_h = int(info.current_h * 0.90)
    win_w = min(img_w, max_w)
    win_h = min(img_h, max_h)
    screen = pg.display.set_mode((win_w, win_h), pg.RESIZABLE)
    # Now that display exists, convert for fast blits and alpha
    try:
        img = img.convert_alpha()
    except Exception:
        img = img.convert()

    font = pg.font.SysFont(None, 18)
    font_big = pg.font.SysFont(None, 24)

    # CSV output paths; overwrite (truncate) on each run
    csv_path = os.path.join(script_dir, "path.csv")
    csv_points_path = os.path.join(script_dir, "checkpoints_cm.csv")
    try:
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["turn_deg", "distance_cm"])
    except Exception as e:
        print(f"Warning: Could not initialize CSV file '{csv_path}': {e}")
    try:
        with open(csv_points_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["x_cm", "y_cm"])  # top-left origin, y increases downward
    except Exception as e:
        print(f"Warning: Could not initialize CSV file '{csv_points_path}': {e}")

    # Measurement state: checkpoint-based polyline (image coordinates)
    points_img = []  # list of (x,y) in image pixels
    mouse_img = None  # current mouse position in image coords when within bounds
    show_grid = True
    show_help = True

    clock = pg.time.Clock()

    # Check aspect ratio consistency
    img_ratio = img_w / img_h if img_h else 1.0
    cm_ratio = ARENA_WIDTH_CM / ARENA_HEIGHT_CM if ARENA_HEIGHT_CM else 1.0
    ratio_diff = abs(img_ratio - cm_ratio) / cm_ratio if cm_ratio else 0

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
                    points_img.clear()
                elif event.key == pg.K_g:
                    show_grid = not show_grid
                elif event.key == pg.K_h:
                    show_help = not show_help
                elif event.key == pg.K_f:
                    pg.display.toggle_fullscreen()
                elif event.key in (pg.K_RETURN, pg.K_KP_ENTER):
                    # Print path as: "turn_degrees, distance_cm" per segment
                    if len(points_img) < 2:
                        print("No path: add at least two checkpoints.")
                    else:
                        print("Path (turn_deg, distance_cm):")
                        prev_heading = None
                        rows = []
                        for i in range(1, len(points_img)):
                            p1 = points_img[i - 1]
                            p2 = points_img[i]
                            dx = (p2[0] - p1[0])
                            dy = (p2[1] - p1[1])
                            vx_cm = dx * (1.0 / px_per_cm_x)
                            vy_cm = dy * (1.0 / px_per_cm_y)
                            dist_cm = math.hypot(vx_cm, vy_cm)
                            curr_heading = heading_from_up_deg(vx_cm, vy_cm)
                            if prev_heading is None:
                                base_heading = 0.0
                            else:
                                base_heading = prev_heading
                            turn_deg = wrap_to_180(curr_heading - base_heading)
                            print(f"{turn_deg:.1f}, {dist_cm:.2f}")
                            rows.append((f"{turn_deg:.1f}", f"{dist_cm:.2f}"))
                            prev_heading = curr_heading
                        # Write CSVs
                        try:
                            with open(csv_path, "w", newline="") as f:
                                writer = csv.writer(f)
                                writer.writerow(["turn_deg", "distance_cm"])
                                for r in rows:
                                    writer.writerow(r)
                            print(f"Saved CSV: {csv_path}")
                        except Exception as e:
                            print(f"ERROR: Could not write CSV '{csv_path}': {e}")
                        # Write checkpoints in cm
                        try:
                            with open(csv_points_path, "w", newline="") as f:
                                writer = csv.writer(f)
                                writer.writerow(["x_cm", "y_cm"])  # top-left origin, y down
                                for (x_px, y_px) in points_img:
                                    x_cm = x_px * (1.0 / px_per_cm_x)
                                    y_cm = y_px * (1.0 / px_per_cm_y)
                                    writer.writerow([f"{x_cm:.2f}", f"{y_cm:.2f}"])
                            print(f"Saved checkpoints CSV: {csv_points_path}")
                        except Exception as e:
                            print(f"ERROR: Could not write CSV '{csv_points_path}': {e}")
            elif event.type == pg.MOUSEBUTTONDOWN:
                if event.button == 1:  # left: add checkpoint
                    mx, my = event.pos
                    ix, iy = screen_to_image((mx, my), scale, offset)
                    if 0 <= ix <= img_w and 0 <= iy <= img_h:
                        mods = pg.key.get_mods()
                        if (mods & pg.KMOD_SHIFT) and len(points_img) >= 1:
                            snapped = snap_point_to_45_deg(points_img[-1], (ix, iy), px_per_cm_x, px_per_cm_y)
                            # Clamp snapped within image bounds
                            sx = min(max(snapped[0], 0), img_w)
                            sy = min(max(snapped[1], 0), img_h)
                            points_img.append((sx, sy))
                        else:
                            points_img.append((ix, iy))
                elif event.button == 3:  # right: undo last checkpoint
                    if points_img:
                        points_img.pop()
            elif event.type == pg.MOUSEMOTION:
                mx, my = event.pos
                ix, iy = screen_to_image((mx, my), scale, offset)
                if 0 <= ix <= img_w and 0 <= iy <= img_h:
                    mods = pg.key.get_mods()
                    if (mods & pg.KMOD_SHIFT) and len(points_img) >= 1:
                        # Snap preview endpoint
                        snapped = snap_point_to_45_deg(points_img[-1], (ix, iy), px_per_cm_x, px_per_cm_y)
                        # Keep within bounds
                        sx = min(max(snapped[0], 0), img_w)
                        sy = min(max(snapped[1], 0), img_h)
                        mouse_img = (sx, sy)
                    else:
                        mouse_img = (ix, iy)
                else:
                    mouse_img = None

        # Draw
        screen.fill((20, 20, 24))
        # Blit image scaled to fit
        if abs(scale - 1.0) < 1e-6:
            screen.blit(img, offset)
        else:
            scaled_size = (int(img_w * scale), int(img_h * scale))
            scaled_img = pg.transform.smoothscale(img, scaled_size)
            screen.blit(scaled_img, offset)

        if show_grid:
            draw_grid(screen, scale, offset, (img_w, img_h), px_per_cm_x, px_per_cm_y)

        # Draw polyline segments formed by checkpoints
        for i in range(1, len(points_img)):
            p1 = points_img[i - 1]
            p2 = points_img[i]
            a = image_to_screen(p1, scale, offset)
            b = image_to_screen(p2, scale, offset)
            pg.draw.line(screen, (255, 215, 0), a, b, 2)
            # Draw endpoints
            pg.draw.circle(screen, (255, 215, 0), (int(a[0]), int(a[1])), 5, 2)
            pg.draw.circle(screen, (255, 215, 0), (int(b[0]), int(b[1])), 5, 2)
            # Label
            dx = (p2[0] - p1[0])
            dy = (p2[1] - p1[1])
            vx_cm = dx * (1.0 / px_per_cm_x)
            vy_cm = dy * (1.0 / px_per_cm_y)
            dist_cm = math.hypot(vx_cm, vy_cm)
            # Angle relative to previous movement (first baseline is up = 0°)
            curr_heading = heading_from_up_deg(vx_cm, vy_cm)
            if i == 1:
                base_heading = 0.0
            else:
                prev_p1 = points_img[i - 2]
                prev_p2 = points_img[i - 1]
                prev_dx = (prev_p2[0] - prev_p1[0])
                prev_dy = (prev_p2[1] - prev_p1[1])
                prev_vx_cm = prev_dx * (1.0 / px_per_cm_x)
                prev_vy_cm = prev_dy * (1.0 / px_per_cm_y)
                base_heading = heading_from_up_deg(prev_vx_cm, prev_vy_cm)
            angle_rel = wrap_to_180(curr_heading - base_heading)
            mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
            draw_text(screen, f"{dist_cm:.2f} cm  @  {angle_rel:.1f}° rel prev", (mid[0] + 8, mid[1] + 8), font_big)

        # Preview from last checkpoint to mouse position
        if mouse_img and len(points_img) >= 1:
            p1 = points_img[-1]
            p2 = mouse_img
            a = image_to_screen(p1, scale, offset)
            b = image_to_screen(p2, scale, offset)
            pg.draw.line(screen, (0, 200, 255), a, b, 2)
            pg.draw.circle(screen, (0, 200, 255), (int(a[0]), int(a[1])), 5, 2)
            pg.draw.circle(screen, (0, 200, 255), (int(b[0]), int(b[1])), 5, 2)
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            vx_cm = dx * (1.0 / px_per_cm_x)
            vy_cm = dy * (1.0 / px_per_cm_y)
            dist_cm = math.hypot(vx_cm, vy_cm)
            curr_heading = heading_from_up_deg(vx_cm, vy_cm)
            if len(points_img) >= 2:
                prev_p1 = points_img[-2]
                prev_p2 = points_img[-1]
                prev_dx = (prev_p2[0] - prev_p1[0])
                prev_dy = (prev_p2[1] - prev_p1[1])
                prev_vx_cm = prev_dx * (1.0 / px_per_cm_x)
                prev_vy_cm = prev_dy * (1.0 / px_per_cm_y)
                base_heading = heading_from_up_deg(prev_vx_cm, prev_vy_cm)
            else:
                base_heading = 0.0
            angle_rel = wrap_to_180(curr_heading - base_heading)
            draw_text(screen, f"{dist_cm:.2f} cm  @  {angle_rel:.1f}° rel prev", (b[0] + 8, b[1] + 8), font_big)

        # Overlays: scale info and help
        draw_scale_bar(screen, scale, offset, (img_w, img_h), px_per_cm_x, px_per_cm_y, font)

        info_lines = [
            f"Image: {img_w} x {img_h} px  |  Arena: {ARENA_WIDTH_CM:.1f} x {ARENA_HEIGHT_CM:.1f} cm",
            f"Px/cm: X={px_per_cm_x:.3f}, Y={px_per_cm_y:.3f}   (cm/px: X={1/px_per_cm_x:.4f}, Y={1/px_per_cm_y:.4f})",
            f"View: {win_w} x {win_h}  scale={scale:.3f}",
        ]
        if ratio_diff > 0.01:
            info_lines.append("Warning: Image aspect ratio differs from physical ratio; X/Y scale differs.")

        y = 10
        for line in info_lines:
            draw_text(screen, line, (10, y), font)
            y += 18

        if show_help:
            help_lines = [
                "Controls:",
                "  Left click: add checkpoint (polyline)",
                "  Right click: undo last checkpoint",
                "  Shift: snap to 45° increments",
                "  Enter: print path + save CSV (turn_deg, distance_cm) & checkpoints_cm.csv",
                "  C: clear checkpoints   G: toggle grid   H: toggle help   F: toggle fullscreen   Esc/Q: quit",
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
