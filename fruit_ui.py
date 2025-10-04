#!/usr/bin/env python3
"""
Fruit Grid Selector UI (6x6)
- Displays a 6x6 grid of fruit positions
- Click each fruit to cycle through colors
- Save mapping into fruit_config.json
"""

import pygame
import sys
import json

pygame.init()

# Grid dimensions
ROWS, COLS = 6, 6
CELL_SIZE = 80
MARGIN = 10
WIDTH, HEIGHT = COLS * CELL_SIZE + 2 * MARGIN, ROWS * CELL_SIZE + 100
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Fruit Grid Selector (6x6)")

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
COLOR_OPTIONS = {
    "Red": (255, 0, 0),
    "Green": (0, 200, 0),
    "Blue": (0, 0, 255),
    "Yellow": (255, 255, 0),
    "None": (180, 180, 180)   # unassigned / default
}
color_keys = list(COLOR_OPTIONS.keys())

# Start with "None"
fruit_colors = [[color_keys.index("None") for _ in range(COLS)] for _ in range(ROWS)]

font = pygame.font.SysFont(None, 24)

def draw_grid():
    screen.fill(WHITE)

    for r in range(ROWS):
        for c in range(COLS):
            color_name = color_keys[fruit_colors[r][c]]
            color = COLOR_OPTIONS[color_name]

            x = MARGIN + c * CELL_SIZE + CELL_SIZE // 2
            y = MARGIN + r * CELL_SIZE + CELL_SIZE // 2

            pygame.draw.circle(screen, color, (x, y), 30)
            label = font.render(f"{r+1},{c+1}", True, BLACK)
            screen.blit(label, (x - 15, y + 35))

    # Confirm button
    confirm_rect = pygame.Rect(WIDTH // 2 - 60, HEIGHT - 70, 120, 50)
    pygame.draw.rect(screen, (100, 200, 100), confirm_rect)
    confirm_label = font.render("CONFIRM", True, BLACK)
    screen.blit(confirm_label, (WIDTH // 2 - 40, HEIGHT - 55))

    return confirm_rect


def main():
    clock = pygame.time.Clock()
    confirm_rect = None

    while True:
        confirm_rect = draw_grid()
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.MOUSEBUTTONDOWN:
                x, y = event.pos

                # Check grid clicks
                for r in range(ROWS):
                    for c in range(COLS):
                        cx = MARGIN + c * CELL_SIZE + CELL_SIZE // 2
                        cy = MARGIN + r * CELL_SIZE + CELL_SIZE // 2
                        dx, dy = x - cx, y - cy
                        if dx * dx + dy * dy <= 30 * 30:
                            fruit_colors[r][c] = (fruit_colors[r][c] + 1) % len(color_keys)

                # Check confirm button
                if confirm_rect.collidepoint(x, y):
                    mapping = {}
                    for r in range(ROWS):
                        for c in range(COLS):
                            mapping[f"Fruit_{r+1}_{c+1}"] = color_keys[fruit_colors[r][c]]

                    with open("fruit_config.json", "w") as f:
                        json.dump(mapping, f, indent=4)

                    print("✅ Saved fruit_config.json")
                    pygame.quit()
                    return

        clock.tick(30)


if __name__ == "__main__":
    main()
