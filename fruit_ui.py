#!/usr/bin/env python3
"""
FRUIT UI — Arena overlay for fruit placement and color tagging

Basics:
- Loads arena.png, computes px/cm using precise arena size, fits image to window.
- Overlays two columns of six fixed 2 cm x 2 cm squares.

Interactions:
- Press R to enter red tagging mode; then click fruits to mark them red and write centers to red.csv
- Press B to enter black tagging mode; then click fruits to mark them black and write centers to black.csv
- G: toggle grid; H: help; Esc/Q: quit

Notes:
- Arena size is 118.1 cm (width) x 114.3 cm (height).
- Column A centers are ~26.19 cm from right edge; Column B ~46.27 cm from right (≈20.08 cm left of A).
- Top-most fruit center is ~5.43 cm from top; vertical spacing ~10.57 cm between centers.
"""
import os
import csv
import json
import math
import pygame as pg
from path_planner import (
    NO_GO_CLEARANCE_CM,
    build_auto_path,
    load_no_go_zones,
    load_path_config,
    save_no_go_zones,
)

# Precise arena dimensions in cm
ARENA_WIDTH_CM = 118.1
ARENA_HEIGHT_CM = 114.3

# Defaults (tuned towards your example positions; adjust interactively or via config)
FRUIT_SIZE_CM = 2.0             # square side
TOP_Y_CM = 5.43                 # top-most fruit center distance from top edge
SPACING_CM_DEFAULT = 10.57      # vertical spacing between centers
OFFSETS_FROM_RIGHT_CM = [26.19, 46.27]  # column A from right; column B ~20.08 cm left of A


def load_image(path: str) -> pg.Surface:
    return pg.image.load(path)


def compute_px_per_cm(img_w: int, img_h: int):
    return img_w / ARENA_WIDTH_CM, img_h / ARENA_HEIGHT_CM


def fit_scale_and_offset(win_wh, img_wh):
    ww, wh = win_wh
    iw, ih = img_wh
    if iw == 0 or ih == 0:
        return 1.0, (0.0, 0.0)
    s = min(ww / iw, wh / ih)
    ox = (ww - iw * s) / 2.0
    oy = (wh - ih * s) / 2.0
    return s, (ox, oy)


def image_to_screen(ix, iy, scale, offset):
    ox, oy = offset
    return ox + ix * scale, oy + iy * scale


def cm_to_image(x_cm, y_cm, px_per_cm_x, px_per_cm_y):
    return x_cm * px_per_cm_x, y_cm * px_per_cm_y


def screen_to_image(sx, sy, scale, offset):
    ox, oy = offset
    return (sx - ox) / scale, (sy - oy) / scale


def image_to_cm(ix, iy, px_per_cm_x, px_per_cm_y):
    return ix / px_per_cm_x, iy / px_per_cm_y


def draw_button(surface, rect, label, font, active=False):
    color = (70, 110, 200) if not active else (110, 160, 255)
    border = (25, 35, 60)
    pg.draw.rect(surface, color, rect, border_radius=6)
    pg.draw.rect(surface, border, rect, width=2, border_radius=6)
    text_img = font.render(label, True, (10, 12, 20))
    text_rect = text_img.get_rect(center=rect.center)
    surface.blit(text_img, text_rect)


def draw_text(surface, text, pos, font, color=(240, 240, 240)):
    img = font.render(text, True, color)
    surface.blit(img, pos)


def draw_grid(surface, scale, offset, img_size, px_per_cm_x, px_per_cm_y):
    iw, ih = img_size
    ww, wh = surface.get_size()
    grid_cm = 10
    step_x = px_per_cm_x * grid_cm * scale
    step_y = px_per_cm_y * grid_cm * scale
    ox, oy = offset
    start_x = int(max(0, math.floor((0 - ox) / step_x)))
    start_y = int(max(0, math.floor((0 - oy) / step_y)))
    max_x_lines = int(math.ceil((ww - ox) / step_x)) + 1
    max_y_lines = int(math.ceil((wh - oy) / step_y)) + 1

    grid_color = (255, 255, 255)
    alpha = 40
    grid_surf = pg.Surface((ww, wh), pg.SRCALPHA)
    for i in range(start_x, max_x_lines):
        x = ox + i * step_x
        pg.draw.line(grid_surf, (*grid_color, alpha), (x, 0), (x, wh), 1)
    for j in range(start_y, max_y_lines):
        y = oy + j * step_y
        pg.draw.line(grid_surf, (*grid_color, alpha), (0, y), (ww, y), 1)
    surface.blit(grid_surf, (0, 0))


def compute_fruit_positions(spacing_cm: float, offsets_from_right_cm: list[float]):
    """Return list of positions [(x_cm, y_cm, col_index, idx_in_col), ...] for 2 columns x 6 fruits."""
    positions = []
    cols_x_cm = [ARENA_WIDTH_CM - offsets_from_right_cm[0], ARENA_WIDTH_CM - offsets_from_right_cm[1]]
    for col_idx, x_cm in enumerate(cols_x_cm):
        for i in range(6):  # six fruits per column
            y_cm = TOP_Y_CM + i * spacing_cm
            positions.append((x_cm, y_cm, col_idx, i))
    return positions


def save_color_csv(script_dir: str, filename: str, coords):
    out = os.path.join(script_dir, filename)
    try:
        with open(out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["x_cm", "y_cm"])  # centers
            for (x_cm, y_cm) in coords:
                w.writerow([f"{x_cm:.2f}", f"{y_cm:.2f}"])
        print(f"Saved {filename} ({len(coords)})")
    except Exception as e:
        print(f"ERROR saving {filename}: {e}")


def save_fruit_config(script_dir: str, positions, fruit_colors):
    """Write fruit_config.json compatible with newer runners while keeping legacy CSV workflow."""
    config_path = os.path.join(script_dir, "fruit_config.json")
    mapping: dict[str, str] = {}

    sequential_index = 1
    for (x_cm, y_cm, col, idx) in positions:
        tag = fruit_colors.get((col, idx))
        if tag == "red":
            label = "Red"
        elif tag == "black":
            label = "Black"
        else:
            label = "Green"

        mapping[f"Fruit{sequential_index}"] = label
        mapping[f"Fruit_{col+1}_{idx+1}"] = label
        sequential_index += 1

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, indent=4)
        print(f"Saved fruit_config.json ({len(mapping)} entries)")
    except Exception as e:
        print(f"ERROR saving fruit_config.json: {e}")


def persist_state(script_dir: str, positions, fruit_colors):
    """Persist both legacy CSV outputs and the new JSON mapping."""
    reds = []
    blacks = []
    for (x_cm, y_cm, col, idx) in positions:
        tag = fruit_colors.get((col, idx))
        if tag == "red":
            reds.append((x_cm, y_cm))
        elif tag == "black":
            blacks.append((x_cm, y_cm))

    save_color_csv(script_dir, "red.csv", reds)
    save_color_csv(script_dir, "black.csv", blacks)
    save_fruit_config(script_dir, positions, fruit_colors)


def main():
    pg.init()
    pg.display.set_caption("FRUIT UI")

    script_dir = os.path.dirname(__file__)
    arena_path = os.path.join(script_dir, "arena.png")
    if not os.path.exists(arena_path):
        raise FileNotFoundError("arena.png not found next to fruit_ui.py")

    arena_img = load_image(arena_path)
    iw, ih = arena_img.get_width(), arena_img.get_height()
    px_per_cm_x, px_per_cm_y = compute_px_per_cm(iw, ih)

    info = pg.display.Info()
    w, h = int(info.current_w * 0.9), int(info.current_h * 0.9)
    screen = pg.display.set_mode((w, h), pg.RESIZABLE)
    font = pg.font.SysFont(None, 18)
    font_big = pg.font.SysFont(None, 24)

    show_grid = True
    show_help = True
    active_mode = None  # "red" or "black"
    positions = compute_fruit_positions(SPACING_CM_DEFAULT, OFFSETS_FROM_RIGHT_CM)
    fruit_colors: dict[tuple[int, int], str] = {}
    start_point_cm, end_point_cm = load_path_config(script_dir)
    nogo_points_raw, nogo_rects_raw, nogo_clearance = load_no_go_zones(script_dir)
    nogo_clearance = max(nogo_clearance, NO_GO_CLEARANCE_CM)
    nogo_points: list[tuple[float, float]] = list(nogo_points_raw)
    nogo_rects: list[tuple[float, float, float, float]] = list(nogo_rects_raw)
    select_mode = None  # "start", "end", "nogo_point", "nogo_rect"
    pending_rect_corner: tuple[float, float] | None = None
    status_message = ""

    clock = pg.time.Clock()
    running = True
    while running:
        ww, wh = screen.get_size()
        scale, offset = fit_scale_and_offset((ww, wh), (iw, ih))

        button_height = 40
        button_width = 150
        button_gap = 12
        bottom_margin = 14
        second_row_y = wh - button_height - bottom_margin
        first_row_y = max(0, second_row_y - button_height - 10)
        set_start_rect = pg.Rect(14, first_row_y, button_width, button_height)
        set_end_rect = pg.Rect(set_start_rect.right + button_gap, first_row_y, button_width, button_height)
        create_path_rect = pg.Rect(set_end_rect.right + button_gap, first_row_y, button_width, button_height)
        add_nogo_point_rect = pg.Rect(14, second_row_y, button_width, button_height)
        add_nogo_rect_rect = pg.Rect(add_nogo_point_rect.right + button_gap, second_row_y, button_width, button_height)
        clear_nogo_rect = pg.Rect(add_nogo_rect_rect.right + button_gap, second_row_y, button_width, button_height)

        clickable_rects = []
        sq_w_px = FRUIT_SIZE_CM * px_per_cm_x * scale
        sq_h_px = FRUIT_SIZE_CM * px_per_cm_y * scale
        for (x_cm, y_cm, col, idx) in positions:
            ix, iy = cm_to_image(x_cm, y_cm, px_per_cm_x, px_per_cm_y)
            sx, sy = image_to_screen(ix, iy, scale, offset)
            rect = pg.Rect(0, 0, sq_w_px, sq_h_px)
            rect.center = (sx, sy)
            clickable_rects.append((rect, (col, idx), (x_cm, y_cm)))

        for e in pg.event.get():
            if e.type == pg.QUIT:
                running = False
            elif e.type == pg.KEYDOWN:
                if e.key in (pg.K_ESCAPE, pg.K_q):
                    running = False
                elif e.key == pg.K_g:
                    show_grid = not show_grid
                elif e.key == pg.K_h:
                    show_help = not show_help
                elif e.key == pg.K_r:
                    active_mode = "red"
                elif e.key == pg.K_b:
                    active_mode = "black"
            elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                if set_start_rect.collidepoint(mx, my):
                    select_mode = "start"
                    active_mode = None
                    pending_rect_corner = None
                    status_message = "Click inside the arena to set START point"
                elif set_end_rect.collidepoint(mx, my):
                    select_mode = "end"
                    active_mode = None
                    pending_rect_corner = None
                    status_message = "Click inside the arena to set END point"
                elif add_nogo_point_rect.collidepoint(mx, my):
                    select_mode = "nogo_point"
                    active_mode = None
                    pending_rect_corner = None
                    status_message = f"Click inside the arena to add a no-go point (≥ {nogo_clearance:.1f} cm)"
                elif add_nogo_rect_rect.collidepoint(mx, my):
                    select_mode = "nogo_rect"
                    active_mode = None
                    pending_rect_corner = None
                    status_message = "Click first corner of the no-go rectangle"
                elif clear_nogo_rect.collidepoint(mx, my):
                    nogo_points.clear()
                    nogo_rects.clear()
                    save_no_go_zones(script_dir, nogo_points, nogo_rects, nogo_clearance)
                    select_mode = None
                    active_mode = None
                    pending_rect_corner = None
                    status_message = "Cleared all no-go zones"
                elif create_path_rect.collidepoint(mx, my):
                    select_mode = None
                    pending_rect_corner = None
                    active_mode = None
                    try:
                        checkpoints, segments = build_auto_path(script_dir, start_point_cm, end_point_cm)
                        if segments:
                            status_message = f"Path saved: {len(segments)} segments"
                        else:
                            status_message = "Path planner returned no segments"
                    except Exception as exc:
                        status_message = f"Path creation failed: {exc}"
                elif select_mode:
                    ix, iy = screen_to_image(mx, my, scale, offset)
                    if 0 <= ix <= iw and 0 <= iy <= ih:
                        sx_cm, sy_cm = image_to_cm(ix, iy, px_per_cm_x, px_per_cm_y)
                        if select_mode == "start":
                            start_point_cm = (round(sx_cm, 2), round(sy_cm, 2))
                            status_message = f"Start set to ({start_point_cm[0]:.1f}, {start_point_cm[1]:.1f}) cm"
                            select_mode = None
                        elif select_mode == "end":
                            end_point_cm = (round(sx_cm, 2), round(sy_cm, 2))
                            status_message = f"End set to ({end_point_cm[0]:.1f}, {end_point_cm[1]:.1f}) cm"
                            select_mode = None
                        elif select_mode == "nogo_point":
                            point = (round(sx_cm, 2), round(sy_cm, 2))
                            nogo_points.append(point)
                            save_no_go_zones(script_dir, nogo_points, nogo_rects, nogo_clearance)
                            status_message = f"Added no-go point at ({point[0]:.1f}, {point[1]:.1f}) cm"
                            select_mode = None
                        elif select_mode == "nogo_rect":
                            if pending_rect_corner is None:
                                pending_rect_corner = (sx_cm, sy_cm)
                                status_message = "First corner captured; click opposite corner"
                            else:
                                x1, y1 = pending_rect_corner
                                x2, y2 = sx_cm, sy_cm
                                rect = (round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2))
                                nogo_rects.append(rect)
                                save_no_go_zones(script_dir, nogo_points, nogo_rects, nogo_clearance)
                                status_message = "No-go rectangle added"
                                pending_rect_corner = None
                                select_mode = None
                        else:
                            select_mode = None
                    else:
                        if select_mode == "nogo_rect" and pending_rect_corner is not None:
                            status_message = "Click within arena bounds to finish rectangle"
                        else:
                            status_message = "Click within arena bounds to set point"
                        if select_mode != "nogo_rect":
                            select_mode = None
                elif active_mode:
                    for rect, key, _coords in clickable_rects:
                        if rect.collidepoint(mx, my):
                            fruit_colors[key] = active_mode
                            persist_state(script_dir, positions, fruit_colors)
                            break

        screen.fill((20, 20, 24))
        ssz = (int(iw * scale), int(ih * scale))
        scaled = pg.transform.smoothscale(arena_img, ssz)
        screen.blit(scaled, offset)

        if show_grid:
            draw_grid(screen, scale, offset, (iw, ih), px_per_cm_x, px_per_cm_y)

        sq_w_px = FRUIT_SIZE_CM * px_per_cm_x * scale
        sq_h_px = FRUIT_SIZE_CM * px_per_cm_y * scale
        for (x_cm, y_cm, col, idx) in positions:
            ix, iy = cm_to_image(x_cm, y_cm, px_per_cm_x, px_per_cm_y)
            sx, sy = image_to_screen(ix, iy, scale, offset)
            rect = pg.Rect(0, 0, sq_w_px, sq_h_px)
            rect.center = (sx, sy)
            tag = fruit_colors.get((col, idx))
            if tag == "red":
                fill = (220, 60, 60)
            elif tag == "black":
                fill = (30, 30, 30)
            else:
                fill = (60, 180, 60)
            pg.draw.rect(screen, fill, rect)
            pg.draw.rect(screen, (220, 220, 220), rect, 2)

        # Draw no-go points (avoidance radius ring)
        if nogo_points:
            radius_px = nogo_clearance * 0.5 * (px_per_cm_x + px_per_cm_y) * scale
            radius_px = max(radius_px, 8.0)
            for (nx, ny) in nogo_points:
                ix, iy = cm_to_image(nx, ny, px_per_cm_x, px_per_cm_y)
                sx, sy = image_to_screen(ix, iy, scale, offset)
                center = (int(sx), int(sy))
                pg.draw.circle(screen, (255, 150, 60), center, int(radius_px), width=2)
                pg.draw.circle(screen, (20, 24, 28), center, int(max(4, radius_px * 0.3)), width=1)
                pg.draw.line(screen, (255, 150, 60), (center[0] - 6, center[1]), (center[0] + 6, center[1]), 1)
                pg.draw.line(screen, (255, 150, 60), (center[0], center[1] - 6), (center[0], center[1] + 6), 1)

        # Draw no-go rectangles with translucent overlay
        for (x1, y1, x2, y2) in nogo_rects:
            ix1, iy1 = cm_to_image(x1, y1, px_per_cm_x, px_per_cm_y)
            ix2, iy2 = cm_to_image(x2, y2, px_per_cm_x, px_per_cm_y)
            sx1, sy1 = image_to_screen(ix1, iy1, scale, offset)
            sx2, sy2 = image_to_screen(ix2, iy2, scale, offset)
            left = int(min(sx1, sx2))
            top = int(min(sy1, sy2))
            width = int(abs(sx2 - sx1))
            height = int(abs(sy2 - sy1))
            rect = pg.Rect(left, top, width or 2, height or 2)
            overlay = pg.Surface((rect.width, rect.height), pg.SRCALPHA)
            overlay.fill((255, 120, 40, 70))
            screen.blit(overlay, rect.topleft)
            pg.draw.rect(screen, (255, 180, 80), rect, width=2)

        if select_mode == "nogo_rect" and pending_rect_corner is not None:
            px_cm, py_cm = pending_rect_corner
            ix, iy = cm_to_image(px_cm, py_cm, px_per_cm_x, px_per_cm_y)
            sx, sy = image_to_screen(ix, iy, scale, offset)
            pg.draw.circle(screen, (255, 200, 120), (int(sx), int(sy)), 6, width=2)

        # Draw start/end markers if available
        for label, point, color in (("S", start_point_cm, (80, 180, 255)), ("E", end_point_cm, (255, 140, 60))):
            if point is None:
                continue
            ix, iy = cm_to_image(point[0], point[1], px_per_cm_x, px_per_cm_y)
            sx, sy = image_to_screen(ix, iy, scale, offset)
            if 0 <= sx <= ww and 0 <= sy <= wh:
                pg.draw.circle(screen, color, (int(sx), int(sy)), 8)
                pg.draw.circle(screen, (20, 24, 28), (int(sx), int(sy)), 10, width=2)
                lbl = font.render(label, True, (10, 12, 20))
                rect = lbl.get_rect(center=(sx, sy))
                screen.blit(lbl, rect)

        hud_x, hud_y = 12, 12
        draw_text(screen, f"Arena: {ARENA_WIDTH_CM} x {ARENA_HEIGHT_CM} cm", (hud_x, hud_y), font_big)
        hud_y += 22
        draw_text(screen, f"Fruit: 2cm squares; top center {TOP_Y_CM} cm; spacing {SPACING_CM_DEFAULT:.2f} cm", (hud_x, hud_y), font)
        hud_y += 20
        draw_text(screen, f"Cols from right (A,B): {OFFSETS_FROM_RIGHT_CM[0]:.2f} cm, {OFFSETS_FROM_RIGHT_CM[1]:.2f} cm", (hud_x, hud_y), font)
        hud_y += 20
        first_row = positions[:2]
        if len(first_row) == 2:
            (xa, ya, _, _), (xb, yb, _, _) = first_row
            draw_text(screen, f"Row0 centers: A=({xa:.2f},{ya:.2f})  B=({xb:.2f},{yb:.2f}) cm", (hud_x, hud_y), font)
            hud_y += 20
        draw_text(screen, f"No-go zones: {len(nogo_points)} points, {len(nogo_rects)} rectangles (≥ {nogo_clearance:.1f} cm)", (hud_x, hud_y), font)
        hud_y += 20
        if show_help:
            mode = active_mode or "none"
            draw_text(screen, f"Keys: R=red mode, B=black mode, Click=tag, G=grid, H=help, Esc=quit  [mode: {mode}]", (hud_x, hud_y), font)

        # Draw buttons and status
        draw_button(screen, set_start_rect, "Set Start", font_big, active=(select_mode == "start"))
        draw_button(screen, set_end_rect, "Set End", font_big, active=(select_mode == "end"))
        draw_button(screen, create_path_rect, "Create Path", font_big)
        draw_button(screen, add_nogo_point_rect, "No-Go Point", font_big, active=(select_mode == "nogo_point"))
        draw_button(screen, add_nogo_rect_rect, "No-Go Rect", font_big, active=(select_mode == "nogo_rect"))
        draw_button(screen, clear_nogo_rect, "Clear No-Go", font_big, active=bool(nogo_points or nogo_rects))

        if status_message:
            msg_img = font.render(status_message, True, (220, 220, 220))
            msg_rect = msg_img.get_rect()
            anchor = clear_nogo_rect if status_message else create_path_rect
            msg_rect.topleft = (anchor.right + 20, anchor.y + (anchor.height - msg_rect.height) / 2)
            screen.blit(msg_img, msg_rect)

        pg.display.flip()
        clock.tick(60)

    pg.quit()


if __name__ == "__main__":
    main()
