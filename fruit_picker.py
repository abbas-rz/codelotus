#!/usr/bin/env python3
# fruit_planner.py - Interactive fruit placement planner with path generation
"""
Interactive tool to plan fruit harvesting and generate robot movement commands.
Based on the Robotics for Good 2025-2026 competition rulebook.
Arena: 118.1 x 114.3 cm
"""
import pygame as pg
import math
import json
import os
import sys

# Arena dimensions from rulebook (cm)
ARENA_WIDTH_CM = 118.1
ARENA_HEIGHT_CM = 114.3

# Fruit types from rulebook
FRUIT_TYPES = {
    'green': {'color': (0, 180, 0), 'name': 'Green (Unripe)', 'action': 'leave'},
    'red': {'color': (220, 20, 20), 'name': 'Red (Ripe)', 'action': 'harvest'},
    'black': {'color': (40, 40, 40), 'name': 'Black (Diseased)', 'action': 'waste'}
}

# Fruit row positions (exact from arena layout)
# Three horizontal rows on LEFT side of arena
# Coordinate system: (0,0) = top-left corner, bot starts at bottom-right corner
FRUIT_ROW_POSITIONS = [
    {'y': 7.5, 'x_start': 15, 'spacing': 2.5, 'count': 6, 'elevated': False, 'name': 'Row 1 (Green)'},  # Top row
    {'y': 17.5, 'x_start': 15, 'spacing': 2.5, 'count': 6, 'elevated': False, 'name': 'Row 2 (White)'},  # Middle row
    {'y': 27.5, 'x_start': 15, 'spacing': 2.5, 'count': 6, 'elevated': False, 'name': 'Row 3 (Orange)'}  # Bottom row
]

# Target zones (positioned for easy access from start zone)
# Based on arena layout: zones are along the sides of the field
FRUITS_ZONE = {'x': 5, 'y': 50, 'width': 15, 'height': 30, 'name': 'Fruits'}
WASTE_ZONE = {'x': 5, 'y': 85, 'width': 15, 'height': 30, 'name': 'Waste'}

# Start zone position (bottom-right corner - L-shaped area)
# Robot must start entirely within this zone
START_ZONE = {'x': 90, 'y': 100, 'width': 28, 'height': 14}


class FruitPlanner:
    def __init__(self):
        pg.init()
        pg.display.set_caption("Fruit Harvesting Planner")
        
        # Window setup
        info = pg.display.Info()
        self.win_w = min(1200, int(info.current_w * 0.9))
        self.win_h = min(800, int(info.current_h * 0.85))
        self.screen = pg.display.set_mode((self.win_w, self.win_h))
        
        # Fonts
        self.font = pg.font.SysFont(None, 20)
        self.font_small = pg.font.SysFont(None, 16)
        self.font_large = pg.font.SysFont(None, 24)
        
        # Arena drawing area
        self.arena_margin = 50
        self.arena_w = self.win_w - 350  # Leave space for controls
        self.arena_h = self.win_h - 100
        
        # Calculate scale
        scale_x = self.arena_w / ARENA_WIDTH_CM
        scale_y = self.arena_h / ARENA_HEIGHT_CM
        self.scale = min(scale_x, scale_y)
        
        # Arena offset (centered)
        arena_pixel_w = ARENA_WIDTH_CM * self.scale
        arena_pixel_h = ARENA_HEIGHT_CM * self.scale
        self.arena_x = (self.arena_w - arena_pixel_w) / 2 + self.arena_margin
        self.arena_y = (self.win_h - arena_pixel_h) / 2
        
        # State
        self.fruit_positions = []  # List of (fruit_type, row_idx, pos_idx)
        # Robot starts at center of start zone (corner position)
        self.robot_start = (START_ZONE['x'] + START_ZONE['width']/2, START_ZONE['y'] + START_ZONE['height']/2)
        self.show_path = False
        self.harvest_order = []  # Order to harvest fruits
        
        # Initialize with random configuration
        self.randomize_fruits()
        
        self.clock = pg.time.Clock()
    
    def randomize_fruits(self):
        """Create a random fruit configuration"""
        import random
        self.fruit_positions.clear()
        
        for row_idx, row in enumerate(FRUIT_ROW_POSITIONS):
            # All rows are ground level now, but exclude boundary fruits
            for pos_idx in range(row['count']):
                # Exclude fruits too close to boundary (first and last positions)
                if pos_idx == 0 or pos_idx == row['count'] - 1:
                    continue
                    
                fruit_type = random.choice(['green', 'red', 'black'])
                self.fruit_positions.append((fruit_type, row_idx, pos_idx))
    
    def cm_to_pixel(self, x_cm, y_cm):
        """Convert cm coordinates to pixel coordinates"""
        px = self.arena_x + x_cm * self.scale
        py = self.arena_y + y_cm * self.scale
        return (int(px), int(py))
    
    def pixel_to_cm(self, px, py):
        """Convert pixel coordinates to cm coordinates"""
        x_cm = (px - self.arena_x) / self.scale
        y_cm = (py - self.arena_y) / self.scale
        return (x_cm, y_cm)
    
    def get_fruit_position_cm(self, row_idx, pos_idx):
        """Get fruit position in cm coordinates"""
        row = FRUIT_ROW_POSITIONS[row_idx]
        x = row['x_start'] + pos_idx * row['spacing']
        y = row['y']
        return (x, y)
    
    def draw_text(self, text, pos, font=None, color=(255, 255, 255), shadow=True):
        """Draw text with optional shadow"""
        if font is None:
            font = self.font
        x, y = pos
        if shadow:
            sh = font.render(text, True, (0, 0, 0))
            self.screen.blit(sh, (x + 1, y + 1))
        img = font.render(text, True, color)
        self.screen.blit(img, (x, y))
    
    def draw_arena(self):
        """Draw the arena field"""
        # Arena border
        arena_rect = pg.Rect(
            self.arena_x,
            self.arena_y,
            ARENA_WIDTH_CM * self.scale,
            ARENA_HEIGHT_CM * self.scale
        )
        pg.draw.rect(self.screen, (255, 255, 255), arena_rect, 2)
        
        # Start zone
        start_rect = pg.Rect(
            *self.cm_to_pixel(START_ZONE['x'], START_ZONE['y']),
            START_ZONE['width'] * self.scale,
            START_ZONE['height'] * self.scale
        )
        pg.draw.rect(self.screen, (100, 100, 100), start_rect, 2)
        self.draw_text("START", (start_rect.x + 5, start_rect.y + 5), 
                      self.font_small, (200, 200, 200))
        
        # Fruit zone
        fruits_rect = pg.Rect(
            *self.cm_to_pixel(FRUITS_ZONE['x'], FRUITS_ZONE['y']),
            FRUITS_ZONE['width'] * self.scale,
            FRUITS_ZONE['height'] * self.scale
        )
        pg.draw.rect(self.screen, (0, 200, 0), fruits_rect, 2)
        self.draw_text("FRUITS", (fruits_rect.x + 5, fruits_rect.y + 5), 
                      self.font_small, (0, 255, 0))
        
        # Waste zone
        waste_rect = pg.Rect(
            *self.cm_to_pixel(WASTE_ZONE['x'], WASTE_ZONE['y']),
            WASTE_ZONE['width'] * self.scale,
            WASTE_ZONE['height'] * self.scale
        )
        pg.draw.rect(self.screen, (200, 0, 0), waste_rect, 2)
        self.draw_text("WASTE", (waste_rect.x + 5, waste_rect.y + 5), 
                      self.font_small, (255, 100, 100))
        
        # Fruit rows (left side of arena)
        for row_idx, row in enumerate(FRUIT_ROW_POSITIONS):
            y_pos = row['y']
            # Draw row label
            label_pos = self.cm_to_pixel(row['x_start'] - 5, y_pos)
            label = f"R{row_idx+1}"
            self.draw_text(label, (label_pos[0] - 20, label_pos[1] - 8), 
                          self.font_small, (200, 200, 200))
            
            # Draw position markers
            for pos_idx in range(row['count']):
                x, y = self.get_fruit_position_cm(row_idx, pos_idx)
                pos = self.cm_to_pixel(x, y)
                
                # Draw position circle
                pg.draw.circle(self.screen, (150, 150, 150), pos, 6, 1)
    
    def draw_fruits(self):
        """Draw fruit placements"""
        # First draw all possible fruit positions (including excluded ones)
        for row_idx, row in enumerate(FRUIT_ROW_POSITIONS):
            for pos_idx in range(row['count']):
                x, y = self.get_fruit_position_cm(row_idx, pos_idx)
                pos = self.cm_to_pixel(x, y)
                
                # Check if this position is excluded (only boundary now)
                is_boundary = (pos_idx == 0 or pos_idx == row['count'] - 1)
                
                if is_boundary:
                    # Draw excluded position as gray circle with X
                    pg.draw.circle(self.screen, (100, 100, 100), pos, int(6 * self.scale), 2)
                    # Draw X to indicate excluded
                    pg.draw.line(self.screen, (150, 150, 150), 
                               (pos[0] - 4, pos[1] - 4), (pos[0] + 4, pos[1] + 4), 2)
                    pg.draw.line(self.screen, (150, 150, 150), 
                               (pos[0] + 4, pos[1] - 4), (pos[0] - 4, pos[1] + 4), 2)
                else:
                    # Draw position marker for available positions
                    pg.draw.circle(self.screen, (200, 200, 200), pos, int(6 * self.scale), 1)
        
        # Then draw actual fruits
        for idx, (fruit_type, row_idx, pos_idx) in enumerate(self.fruit_positions):
            x, y = self.get_fruit_position_cm(row_idx, pos_idx)
            pos = self.cm_to_pixel(x, y)
            color = FRUIT_TYPES[fruit_type]['color']
            
            # Draw fruit as filled circle
            pg.draw.circle(self.screen, color, pos, int(8 * self.scale), 0)
            pg.draw.circle(self.screen, (255, 255, 255), pos, int(8 * self.scale), 1)
            
            # Draw harvest order number if in harvest list
            if idx in self.harvest_order:
                order_num = self.harvest_order.index(idx) + 1
                self.draw_text(str(order_num), (pos[0] + 12, pos[1] - 8), 
                             self.font_small, (255, 255, 0))
    
    def draw_path(self):
        """Draw robot path if enabled"""
        if not self.show_path or not self.harvest_order:
            return
        
        current_pos = self.robot_start
        
        # Draw start position
        pg.draw.circle(self.screen, (0, 255, 0), 
                      self.cm_to_pixel(*current_pos), 8, 2)
        
        for order_idx, fruit_idx in enumerate(self.harvest_order):
            fruit_type, row_idx, pos_idx = self.fruit_positions[fruit_idx]
            target_x, target_y = self.get_fruit_position_cm(row_idx, pos_idx)
            
            # Draw line to fruit
            start_pixel = self.cm_to_pixel(*current_pos)
            fruit_pixel = self.cm_to_pixel(target_x, target_y)
            pg.draw.line(self.screen, (255, 215, 0), start_pixel, fruit_pixel, 2)
            
            # Determine target zone
            if fruit_type == 'red':
                zone_x = FRUITS_ZONE['x'] + FRUITS_ZONE['width']/2
                zone_y = FRUITS_ZONE['y'] + FRUITS_ZONE['height']/2
            elif fruit_type == 'black':
                zone_x = WASTE_ZONE['x'] + WASTE_ZONE['width']/2
                zone_y = WASTE_ZONE['y'] + WASTE_ZONE['height']/2
            else:
                continue  # Green fruits are not harvested
            
            # Draw line to zone
            zone_pixel = self.cm_to_pixel(zone_x, zone_y)
            pg.draw.line(self.screen, (0, 200, 255), fruit_pixel, zone_pixel, 2)
            
            # Update current position to zone
            current_pos = (zone_x, zone_y)
            
            # Draw waypoint marker
            pg.draw.circle(self.screen, (255, 215, 0), fruit_pixel, 5, 2)
    
    def draw_controls(self):
        """Draw control panel"""
        panel_x = self.arena_w + 20
        y = 20
        
        # Title
        self.draw_text("FRUIT HARVESTER", (panel_x, y), self.font_large, (255, 100, 100))
        y += 40
        
        # Instructions
        self.draw_text("Click fruit to add/remove", (panel_x, y), self.font_small)
        y += 20
        self.draw_text("from harvest order", (panel_x, y), self.font_small)
        y += 20
        self.draw_text("(Left side rows only)", (panel_x, y), self.font_small, (200, 200, 100))
        y += 20
        self.draw_text("(No boundary fruits)", (panel_x, y), self.font_small, (200, 200, 100))
        y += 20
        
        # Harvest order
        self.draw_text("Harvest Order:", (panel_x, y), self.font)
        y += 25
        
        if self.harvest_order:
            for order_idx, fruit_idx in enumerate(self.harvest_order):
                fruit_type, row_idx, pos_idx = self.fruit_positions[fruit_idx]
                color = FRUIT_TYPES[fruit_type]['color']
                name = FRUIT_TYPES[fruit_type]['name']
                
                # Draw color indicator
                color_rect = pg.Rect(panel_x, y, 20, 20)
                pg.draw.rect(self.screen, color, color_rect)
                pg.draw.rect(self.screen, (255, 255, 255), color_rect, 1)
                
                text = f"{order_idx+1}. {name} R{row_idx+1}P{pos_idx+1}"
                self.draw_text(text, (panel_x + 25, y + 2), self.font_small)
                y += 25
        else:
            self.draw_text("(empty)", (panel_x + 10, y), self.font_small, (150, 150, 150))
            y += 25
        
        y += 20
        
        # Statistics
        red_count = sum(1 for i in self.harvest_order 
                       if self.fruit_positions[i][0] == 'red')
        black_count = sum(1 for i in self.harvest_order 
                         if self.fruit_positions[i][0] == 'black')
        
        self.draw_text(f"Red fruits: {red_count}", (panel_x, y), self.font_small)
        y += 20
        self.draw_text(f"Black fruits: {black_count}", (panel_x, y), self.font_small)
        y += 30
        
        # Options
        path_text = "[X]" if self.show_path else "[ ]"
        self.draw_text(f"{path_text} Show Path (P)", (panel_x, y), self.font_small)
        y += 30
        
        # Controls
        self.draw_text("Controls:", (panel_x, y), self.font)
        y += 25
        
        controls = [
            "Left click: Add/remove fruit",
            "R: Randomize fruits",
            "C: Clear harvest order",
            "P: Toggle path preview",
            "Enter: Generate track",
            "Q/Esc: Quit"
        ]
        
        for control in controls:
            self.draw_text(control, (panel_x, y), self.font_small, (200, 200, 200))
            y += 20
        
        y += 20
        
        # Legend
        self.draw_text("Legend:", (panel_x, y), self.font)
        y += 25
        
        legend_items = [
            ("● Available fruit", (200, 200, 200)),
            ("✗ Excluded (boundary only)", (150, 150, 150)),
            ("🟢 Green = Leave unripe", (0, 180, 0)),
            ("🔴 Red = Harvest to Fruits", (220, 20, 20)),
            ("⚫ Black = Remove to Waste", (40, 40, 40))
        ]
        
        for item, color in legend_items:
            self.draw_text(item, (panel_x, y), self.font_small, color)
            y += 18
    
    def handle_click(self, pos):
        """Handle mouse click on arena"""
        x_cm, y_cm = self.pixel_to_cm(*pos)
        
        # Check which fruit was clicked
        for idx, (fruit_type, row_idx, pos_idx) in enumerate(self.fruit_positions):
            fx, fy = self.get_fruit_position_cm(row_idx, pos_idx)
            distance = math.sqrt((x_cm - fx)**2 + (y_cm - fy)**2)
            
            if distance < 2.0:  # Click tolerance in cm
                # Check if this position is excluded (only boundary now)
                row = FRUIT_ROW_POSITIONS[row_idx]
                is_boundary = (pos_idx == 0 or pos_idx == row['count'] - 1)
                
                if is_boundary:
                    print("Cannot harvest boundary fruits - too close to field edge")
                    return
                
                # Toggle fruit in harvest order
                if fruit_type == 'green':
                    print("Green fruits cannot be harvested (must remain unripe)")
                    return
                
                if idx in self.harvest_order:
                    self.harvest_order.remove(idx)
                    print(f"Removed {fruit_type} fruit from harvest order")
                else:
                    self.harvest_order.append(idx)
                    print(f"Added {fruit_type} fruit to harvest order (position {len(self.harvest_order)})")
                return
    
    def generate_track(self):
        """Generate track file from harvest order"""
        if not self.harvest_order:
            print("No fruits selected for harvesting")
            return False
        
        print("\n=== Generating Track ===")
        print(f"Robot starts at: ({self.robot_start[0]:.1f}, {self.robot_start[1]:.1f}) cm")
        
        current_pos = self.robot_start
        current_heading = 0.0  # 0° = up (-Y direction), robot starts facing up from corner
        
        track_segments = []
        
        for order_idx, fruit_idx in enumerate(self.harvest_order):
            fruit_type, row_idx, pos_idx = self.fruit_positions[fruit_idx]
            
            # Step 1: Navigate to fruit
            fruit_x, fruit_y = self.get_fruit_position_cm(row_idx, pos_idx)
            
            dx = fruit_x - current_pos[0]
            dy = fruit_y - current_pos[1]
            distance = math.sqrt(dx**2 + dy**2)
            target_heading = math.degrees(math.atan2(dx, -dy)) % 360.0
            
            angle_diff = target_heading - current_heading
            while angle_diff > 180:
                angle_diff -= 360
            while angle_diff <= -180:
                angle_diff += 360
            
            print(f"Segment {len(track_segments)+1}: Go to {fruit_type} fruit")
            print(f"  Turn {angle_diff:+.1f}°, Move {distance:.1f} cm")
            track_segments.append((angle_diff, distance))
            
            current_pos = (fruit_x, fruit_y)
            current_heading = target_heading
            
            # Step 2: Navigate to appropriate zone
            if fruit_type == 'red':
                zone_x = FRUITS_ZONE['x'] + FRUITS_ZONE['width']/2
                zone_y = FRUITS_ZONE['y'] + FRUITS_ZONE['height']/2
                zone_name = "Fruits zone"
            elif fruit_type == 'black':
                zone_x = WASTE_ZONE['x'] + WASTE_ZONE['width']/2
                zone_y = WASTE_ZONE['y'] + WASTE_ZONE['height']/2
                zone_name = "Waste zone"
            else:
                continue
            
            dx = zone_x - current_pos[0]
            dy = zone_y - current_pos[1]
            distance = math.sqrt(dx**2 + dy**2)
            target_heading = math.degrees(math.atan2(dx, -dy)) % 360.0
            
            angle_diff = target_heading - current_heading
            while angle_diff > 180:
                angle_diff -= 360
            while angle_diff <= -180:
                angle_diff += 360
            
            print(f"Segment {len(track_segments)+1}: Go to {zone_name}")
            print(f"  Turn {angle_diff:+.1f}°, Move {distance:.1f} cm")
            track_segments.append((angle_diff, distance))
            
            current_pos = (zone_x, zone_y)
            current_heading = target_heading
        
        # Write track file
        try:
            with open("fruit_track.txt", "w") as f:
                for angle, measure in track_segments:
                    f.write(f"{angle:.1f}, {measure:.2f}\n")
            print(f"\nTrack saved to: fruit_track.txt")
            print(f"Total segments: {len(track_segments)}")
            
            # Also save configuration
            with open("fruit_config.json", "w") as f:
                json.dump({
                    'fruits': [(t, r, p) for t, r, p in self.fruit_positions],
                    'harvest_order': self.harvest_order
                }, f, indent=2)
            print("Configuration saved to: fruit_config.json")
            
            return True
            
        except Exception as e:
            print(f"Error saving track: {e}")
            return False
    
    def run(self):
        """Main loop"""
        running = True
        
        while running:
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    running = False
                    
                elif event.type == pg.KEYDOWN:
                    if event.key in (pg.K_ESCAPE, pg.K_q):
                        running = False
                    elif event.key == pg.K_r:
                        self.randomize_fruits()
                        self.harvest_order.clear()
                        print("Randomized fruit configuration")
                    elif event.key == pg.K_p:
                        self.show_path = not self.show_path
                    elif event.key == pg.K_c:
                        self.harvest_order.clear()
                        print("Cleared harvest order")
                    elif event.key in (pg.K_RETURN, pg.K_KP_ENTER):
                        self.generate_track()
                        
                elif event.type == pg.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Left click
                        self.handle_click(event.pos)
            
            # Draw
            self.screen.fill((20, 20, 24))
            self.draw_arena()
            self.draw_fruits()
            self.draw_path()
            self.draw_controls()
            
            pg.display.flip()
            self.clock.tick(60)
        
        pg.quit()


def main():
    planner = FruitPlanner()
    planner.run()


if __name__ == "__main__":
    main()