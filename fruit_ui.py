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

    clock = pg.time.Clock()
    running = True
    while running:
        ww, wh = screen.get_size()
        scale, offset = fit_scale_and_offset((ww, wh), (iw, ih))

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
                if active_mode:
                    mx, my = e.pos
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
        if show_help:
            mode = active_mode or "none"
            draw_text(screen, f"Keys: R=red mode, B=black mode, Click=tag, G=grid, H=help, Esc=quit  [mode: {mode}]", (hud_x, hud_y), font)

        pg.display.flip()
        clock.tick(60)

    pg.quit()


if __name__ == "__main__":
    main()
