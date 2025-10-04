#!/usr/bin/env python3
# fruit_selector.py - Interactive fruit selection UI for robot collection
"""
Interactive pygame UI for selecting red fruits on the arena.
Creates a path for the robot to collect only the selected fruits.
"""
import math
import os
import sys
import pygame as pg
import csv
import time
from move_control import RobotController
import advanced

# Physical dimensions of the arena in centimeters (from official rulebook)
ARENA_WIDTH_CM = 118.1  # Competition field surface: 1181 ± 6 mm
ARENA_HEIGHT_CM = 114.3  # Competition field surface: 1143 ± 5 mm

# Fruit types and colors (from official rulebook)
FRUIT_TYPES = {
    'red': (255, 0, 0),      # Ripe fruit (must be harvested to "Fruits" zone)
    'green': (0, 255, 0),    # Unripe fruit (must NOT be moved)
    'black': (0, 0, 0),      # Diseased fruit (must be removed to "Waste" zone)
}

# Seed types and colors (from official rulebook)
SEED_TYPES = {
    'small': (128, 128, 128),   # Small seed (gray plot) - 20×20×20 mm
    'medium': (0, 255, 0),      # Medium seed (green plot) - 20×20×40 mm  
    'large': (255, 165, 0),     # Large seed (orange plot) - 25×25×20 mm
}

# Plot colors (from official rulebook)
PLOT_COLORS = {
    'gray': (128, 128, 128),    # Small seeds
    'green': (0, 255, 0),       # Medium seeds
    'orange': (255, 165, 0),    # Large seeds
}

# UI Colors
UI_COLORS = {
    'background': (20, 20, 24),
    'arena_border': (255, 255, 255),
    'grid': (100, 100, 100),
    'selected_fruit': (255, 100, 100),
    'unselected_fruit': (150, 150, 150),
    'path_line': (255, 215, 0),
    'start_point': (0, 255, 0),
    'end_point': (255, 0, 0),
    'text': (255, 255, 255),
    'button': (60, 60, 60),
    'button_hover': (80, 80, 80),
    'button_active': (100, 100, 100),
    'start_zone': (0, 0, 0),        # Black start zone
    'fruits_zone': (0, 255, 0),     # Green fruits collection zone
    'waste_zone': (255, 0, 0),      # Red waste collection zone
    'plot_border': (139, 69, 19),   # Brown plot borders
    'elevated_platform': (160, 82, 45), # Brown elevated platform
}

# Official competition zones and positions (from rulebook)
COMPETITION_ZONES = {
    'start_zone': {
        'x': 10, 'y': ARENA_HEIGHT_CM - 20,  # Bottom of arena
        'width': 30, 'height': 15,
        'description': 'Robot start zone (black tape)'
    },
    'crop_plots': {
        'x': 20, 'y': 10,  # Top of arena
        'width': 20, 'height': 15,
        'description': 'Crop plots (2×3 grids)'
    },
    'fruit_rows': {
        'x': ARENA_WIDTH_CM - 30, 'y': 20,  # Right side
        'width': 15, 'height': 60,
        'description': 'Three rows of fruits (one elevated)'
    },
    'fruits_zone': {
        'x': 5, 'y': 30,  # Left side
        'width': 15, 'height': 20,
        'description': 'Fruits collection zone'
    },
    'waste_zone': {
        'x': 5, 'y': 60,  # Left side, below fruits
        'width': 15, 'height': 20,
        'description': 'Waste collection zone'
    }
}

class Fruit:
    def __init__(self, x_cm, y_cm, fruit_type='red', radius_cm=1.0):
        self.x_cm = x_cm
        self.y_cm = y_cm
        self.fruit_type = fruit_type
        self.radius_cm = radius_cm  # ø20mm = 1cm radius
        self.selected = False
        self.collected = False
        self.in_correct_zone = False  # Track if fruit is in correct zone
        self.elevated = False  # Track if fruit is on elevated platform
    
    def get_color(self):
        if self.collected:
            return (100, 100, 100)  # Gray when collected
        elif self.selected:
            return UI_COLORS['selected_fruit']
        else:
            return FRUIT_TYPES.get(self.fruit_type, (255, 255, 255))

class Seed:
    def __init__(self, x_cm, y_cm, seed_type='small'):
        self.x_cm = x_cm
        self.y_cm = y_cm
        self.seed_type = seed_type
        self.planted = False
        self.correct_plot = False
    
    def get_color(self):
        return SEED_TYPES.get(self.seed_type, (255, 255, 255))
    
    def get_dimensions(self):
        """Get seed dimensions in cm based on type"""
        if self.seed_type == 'small':
            return (2.0, 2.0, 2.0)  # 20×20×20 mm
        elif self.seed_type == 'medium':
            return (2.0, 2.0, 4.0)  # 20×20×40 mm
        elif self.seed_type == 'large':
            return (2.5, 2.5, 2.0)  # 25×25×20 mm
        return (2.0, 2.0, 2.0)

class CropPlot:
    def __init__(self, x_cm, y_cm, plot_color='gray', width_cm=20, height_cm=15):
        self.x_cm = x_cm
        self.y_cm = y_cm
        self.plot_color = plot_color
        self.width_cm = width_cm
        self.height_cm = height_cm
        self.active = True  # Referee selects 2 of 3 plots
        self.seeds = []  # Seeds planted in this plot
        self.watered = False

class Button:
    def __init__(self, x, y, width, height, text, action=None):
        self.rect = pg.Rect(x, y, width, height)
        self.text = text
        self.action = action
        self.hovered = False
        self.active = False
    
    def draw(self, surface, font):
        # Button background
        color = UI_COLORS['button']
        if self.active:
            color = UI_COLORS['button_active']
        elif self.hovered:
            color = UI_COLORS['button_hover']
        
        pg.draw.rect(surface, color, self.rect)
        pg.draw.rect(surface, UI_COLORS['text'], self.rect, 2)
        
        # Button text
        text_surface = font.render(self.text, True, UI_COLORS['text'])
        text_rect = text_surface.get_rect(center=self.rect.center)
        surface.blit(text_surface, text_rect)
    
    def handle_event(self, event):
        if event.type == pg.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pg.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.active = True
                if self.action:
                    self.action()
        elif event.type == pg.MOUSEBUTTONUP:
            self.active = False

class FruitSelector:
    def __init__(self):
        pg.init()
        pg.display.set_caption("Fruit Collection Planner")
        
        # Initialize display first
        self.setup_display()
        
        # Load arena image after display is ready
        self.load_arena_image()
        
        # Finalize display setup with arena image
        self.finalize_display()
        
        # Competition elements
        self.fruits = []
        self.seeds = []
        self.crop_plots = []
        self.selected_fruits = []
        self.robot_path = []
        
        # UI state
        self.current_fruit_type = 'red'
        self.current_seed_type = 'small'
        self.show_grid = True
        self.show_path = True
        self.show_zones = True
        self.robot_start_pos = None
        self.mission_mode = 'harvesting'  # 'harvesting' or 'cultivation'
        
        # Robot control
        self.robot_controller = None
        self.collection_mode = False
        
        # Create UI buttons
        self.create_buttons()
        
        # Initialize official competition setup
        self.setup_competition_field()
        
        # Load existing data if available
        self.load_fruits()
    
    def load_arena_image(self):
        """Load the arena background image"""
        script_dir = os.path.dirname(__file__)
        image_path = os.path.join(script_dir, "arena.png")
        
        if os.path.exists(image_path):
            self.arena_img = pg.image.load(image_path)
            # Don't convert until display is set up
        else:
            # Create a placeholder if no image
            self.arena_img = pg.Surface((800, 600))
            self.arena_img.fill((50, 50, 50))
            pg.draw.rect(self.arena_img, (255, 255, 255), (50, 50, 700, 500), 3)
    
    def setup_display(self):
        """Setup the pygame display"""
        # Calculate display size
        info = pg.display.Info()
        max_w = int(info.current_w * 0.9)
        max_h = int(info.current_h * 0.9)
        
        # Default display size (will be adjusted after loading arena image)
        self.display_w = min(1200, max_w)
        self.display_h = min(800, max_h)
        
        self.screen = pg.display.set_mode((self.display_w, self.display_h), pg.RESIZABLE)
    
    def finalize_display(self):
        """Finalize display setup after arena image is loaded"""
        self.arena_img_w, self.arena_img_h = self.arena_img.get_size()
        
        # Now convert the arena image after display is set up
        try:
            self.arena_img = self.arena_img.convert_alpha()
        except:
            self.arena_img = self.arena_img.convert()
        
        # Calculate display size based on arena image
        info = pg.display.Info()
        max_w = int(info.current_w * 0.9)
        max_h = int(info.current_h * 0.9)
        
        # Fit arena image with space for UI
        self.display_w = min(self.arena_img_w + 300, max_w)  # Extra space for UI
        self.display_h = min(self.arena_img_h + 100, max_h)
        
        # Resize display if needed
        if self.display_w != self.screen.get_width() or self.display_h != self.screen.get_height():
            self.screen = pg.display.set_mode((self.display_w, self.display_h), pg.RESIZABLE)
        
        # Calculate scaling and positioning
        self.arena_scale = min(
            (self.display_w - 300) / self.arena_img_w,
            (self.display_h - 100) / self.arena_img_h
        )
        self.arena_w = int(self.arena_img_w * self.arena_scale)
        self.arena_h = int(self.arena_img_h * self.arena_scale)
        self.arena_x = 20
        self.arena_y = 20
        
        # Calculate pixels per cm
        self.px_per_cm_x = self.arena_w / ARENA_WIDTH_CM
        self.px_per_cm_y = self.arena_h / ARENA_HEIGHT_CM
    
    def setup_competition_field(self):
        """Setup the official competition field layout"""
        # Create crop plots (2×3 grids at top of field)
        plot_colors = ['gray', 'green', 'orange']
        for i, color in enumerate(plot_colors):
            x = COMPETITION_ZONES['crop_plots']['x'] + i * 25
            y = COMPETITION_ZONES['crop_plots']['y']
            plot = CropPlot(x, y, color)
            self.crop_plots.append(plot)
        
        # Create fruit rows (3 rows on right side, one elevated)
        fruit_types = ['green', 'red', 'black']
        for i, fruit_type in enumerate(fruit_types):
            x = COMPETITION_ZONES['fruit_rows']['x']
            y = COMPETITION_ZONES['fruit_rows']['y'] + i * 20
            elevated = (i == 1)  # Middle row is elevated
            fruit = Fruit(x, y, fruit_type)
            fruit.elevated = elevated
            self.fruits.append(fruit)
        
        # Set robot start position
        start_zone = COMPETITION_ZONES['start_zone']
        self.robot_start_pos = (
            start_zone['x'] + start_zone['width'] / 2,
            start_zone['y'] + start_zone['height'] / 2
        )
    
    def create_buttons(self):
        """Create UI buttons"""
        self.buttons = []
        button_y = self.arena_y + self.arena_h + 10
        button_width = 120
        button_height = 30
        button_spacing = 10
        
        # Mission mode buttons
        btn = Button(self.arena_x, button_y, button_width, button_height, 
                    "Harvesting Mode", lambda: self.set_mission_mode('harvesting'))
        self.buttons.append(btn)
        
        btn = Button(self.arena_x + button_width + button_spacing, button_y, 
                    button_width, button_height, "Cultivation Mode", 
                    lambda: self.set_mission_mode('cultivation'))
        self.buttons.append(btn)
        
        # Fruit type selection buttons (for harvesting mode)
        fruit_types = ['red', 'green', 'black']
        for i, fruit_type in enumerate(fruit_types):
            x = self.arena_x + (i + 2) * (button_width + button_spacing)
            btn = Button(x, button_y, button_width, button_height, 
                        f"Add {fruit_type.title()}", 
                        lambda t=fruit_type: self.set_fruit_type(t))
            self.buttons.append(btn)
        
        # Seed type selection buttons (for cultivation mode)
        seed_types = ['small', 'medium', 'large']
        for i, seed_type in enumerate(seed_types):
            x = self.arena_x + (i + 2) * (button_width + button_spacing)
            btn = Button(x, button_y + button_height + button_spacing, 
                        button_width, button_height, 
                        f"Add {seed_type.title()}", 
                        lambda t=seed_type: self.set_seed_type(t))
            self.buttons.append(btn)
        
        # Control buttons
        control_y = button_y + 2 * (button_height + button_spacing)
        control_buttons = [
            ("Clear All", self.clear_all_fruits),
            ("Select All Red", self.select_all_red),
            ("Generate Path", self.generate_path),
            ("Start Mission", self.start_mission),
            ("Save Data", self.save_data),
            ("Load Data", self.load_data),
            ("Toggle Zones", self.toggle_zones),
            ("Reset Field", self.reset_field),
        ]
        
        for i, (text, action) in enumerate(control_buttons):
            x = self.arena_x + (i % 3) * (button_width + button_spacing)
            y = control_y + (i // 3) * (button_height + button_spacing)
            btn = Button(x, y, button_width, button_height, text, action)
            self.buttons.append(btn)
    
    def set_mission_mode(self, mode):
        """Set the current mission mode"""
        self.mission_mode = mode
        print(f"Mission mode: {mode}")
    
    def set_fruit_type(self, fruit_type):
        """Set the current fruit type for placement"""
        self.current_fruit_type = fruit_type
        print(f"Selected fruit type: {fruit_type}")
    
    def set_seed_type(self, seed_type):
        """Set the current seed type for placement"""
        self.current_seed_type = seed_type
        print(f"Selected seed type: {seed_type}")
    
    def cm_to_pixels(self, x_cm, y_cm):
        """Convert cm coordinates to screen pixels"""
        x_px = self.arena_x + x_cm * self.px_per_cm_x
        y_px = self.arena_y + y_cm * self.px_per_cm_y
        return int(x_px), int(y_px)
    
    def pixels_to_cm(self, x_px, y_px):
        """Convert screen pixels to cm coordinates"""
        x_cm = (x_px - self.arena_x) / self.px_per_cm_x
        y_cm = (y_px - self.arena_y) / self.px_per_cm_y
        return x_cm, y_cm
    
    def add_fruit(self, x_cm, y_cm, fruit_type=None):
        """Add a fruit at the specified position"""
        if fruit_type is None:
            fruit_type = self.current_fruit_type
        
        # Check if position is within arena bounds
        if 0 <= x_cm <= ARENA_WIDTH_CM and 0 <= y_cm <= ARENA_HEIGHT_CM:
            fruit = Fruit(x_cm, y_cm, fruit_type)
            self.fruits.append(fruit)
            print(f"Added {fruit_type} fruit at ({x_cm:.1f}, {y_cm:.1f}) cm")
            return True
        return False
    
    def remove_fruit(self, x_cm, y_cm, radius_cm=5.0):
        """Remove fruit near the specified position"""
        for i, fruit in enumerate(self.fruits):
            distance = math.sqrt((fruit.x_cm - x_cm)**2 + (fruit.y_cm - y_cm)**2)
            if distance <= radius_cm:
                removed = self.fruits.pop(i)
                print(f"Removed {removed.fruit_type} fruit at ({removed.x_cm:.1f}, {removed.y_cm:.1f}) cm")
                return True
        return False
    
    def toggle_fruit_selection(self, x_cm, y_cm, radius_cm=5.0):
        """Toggle selection of fruit near the specified position"""
        for fruit in self.fruits:
            distance = math.sqrt((fruit.x_cm - x_cm)**2 + (fruit.y_cm - y_cm)**2)
            if distance <= radius_cm:
                fruit.selected = not fruit.selected
                if fruit.selected:
                    if fruit not in self.selected_fruits:
                        self.selected_fruits.append(fruit)
                else:
                    if fruit in self.selected_fruits:
                        self.selected_fruits.remove(fruit)
                print(f"{'Selected' if fruit.selected else 'Deselected'} {fruit.fruit_type} fruit at ({fruit.x_cm:.1f}, {fruit.y_cm:.1f}) cm")
                return True
        return False
    
    def clear_all_fruits(self):
        """Clear all fruits"""
        self.fruits.clear()
        self.selected_fruits.clear()
        self.robot_path.clear()
        print("Cleared all fruits")
    
    def select_all_red(self):
        """Select all red fruits"""
        for fruit in self.fruits:
            if fruit.fruit_type == 'red':
                fruit.selected = True
                if fruit not in self.selected_fruits:
                    self.selected_fruits.append(fruit)
        print(f"Selected {len([f for f in self.fruits if f.fruit_type == 'red'])} red fruits")
    
    def generate_path(self):
        """Generate optimal path for collecting selected fruits"""
        if not self.selected_fruits:
            print("No fruits selected for collection")
            return
        
        # Simple path generation: visit fruits in order of distance
        if not self.robot_start_pos:
            # Default start position (center of arena)
            self.robot_start_pos = (ARENA_WIDTH_CM / 2, ARENA_HEIGHT_CM / 2)
        
        # Create path using nearest neighbor algorithm
        path = [self.robot_start_pos]
        remaining_fruits = self.selected_fruits.copy()
        current_pos = self.robot_start_pos
        
        while remaining_fruits:
            # Find nearest fruit
            nearest_fruit = min(remaining_fruits, 
                              key=lambda f: math.sqrt((f.x_cm - current_pos[0])**2 + (f.y_cm - current_pos[1])**2))
            
            path.append((nearest_fruit.x_cm, nearest_fruit.y_cm))
            current_pos = (nearest_fruit.x_cm, nearest_fruit.y_cm)
            remaining_fruits.remove(nearest_fruit)
        
        self.robot_path = path
        print(f"Generated path with {len(path)} waypoints")
    
    def start_mission(self):
        """Start robot mission (harvesting or cultivation)"""
        if not self.robot_path:
            print("No path generated. Generate path first.")
            return
        
        print(f"Starting {self.mission_mode} mission...")
        self.collection_mode = True
        
        # Initialize robot control
        try:
            if not advanced.init_bot_control(verbose_telemetry=False):
                print("ERROR: Failed to initialize robot control")
                return
            
            self.robot_controller = RobotController()
            print("Robot control initialized")
            
            # Execute mission path
            if self.mission_mode == 'harvesting':
                self.execute_harvesting_mission()
            else:
                self.execute_cultivation_mission()
            
        except Exception as e:
            print(f"Error during mission: {e}")
        finally:
            self.collection_mode = False
            advanced.cleanup()
    
    def start_collection(self):
        """Legacy method - redirects to start_mission"""
        self.start_mission()
    
    def execute_collection_path(self):
        """Execute the robot collection path"""
        if not self.robot_controller:
            return
        
        print(f"Executing collection path with {len(self.robot_path)} waypoints...")
        
        for i, (target_x, target_y) in enumerate(self.robot_path):
            if i == 0:
                continue  # Skip start position
            
            # Calculate movement from previous position
            prev_x, prev_y = self.robot_path[i-1]
            dx = target_x - prev_x
            dy = target_y - prev_y
            
            # Calculate distance and angle
            distance = math.sqrt(dx**2 + dy**2)
            angle = math.degrees(math.atan2(dy, dx))
            
            print(f"Waypoint {i}: Move {distance:.1f}cm at {angle:.1f}°")
            
            # Execute movement
            success = self.robot_controller.execute_command(angle, distance)
            if not success:
                print(f"Failed to reach waypoint {i}")
                break
            
            # Mark fruit as collected
            for fruit in self.fruits:
                if (abs(fruit.x_cm - target_x) < 5 and 
                    abs(fruit.y_cm - target_y) < 5 and 
                    fruit.selected):
                    fruit.collected = True
                    print(f"Collected {fruit.fruit_type} fruit at ({fruit.x_cm:.1f}, {fruit.y_cm:.1f})")
        
        print("Collection complete!")
    
    def execute_harvesting_mission(self):
        """Execute the harvesting mission (Mission 2)"""
        print("Executing harvesting mission...")
        # Similar to execute_collection_path but with proper scoring
        self.execute_collection_path()
    
    def execute_cultivation_mission(self):
        """Execute the cultivation mission (Mission 1)"""
        print("Executing cultivation mission...")
        # Plant seeds and water plots
        if not self.robot_controller:
            return
        
        print("Planting seeds and watering plots...")
        # Implementation for seed planting and irrigation
        # This would involve navigating to crop plots and operating irrigation gates
    
    def save_data(self):
        """Save all competition data to CSV files"""
        # Save fruits
        self.save_fruits()
        # Save seeds
        self.save_seeds()
        print("All competition data saved")
    
    def load_data(self):
        """Load all competition data from CSV files"""
        self.load_fruits()
        self.load_seeds()
        print("All competition data loaded")
    
    def save_fruits(self):
        """Save fruits to CSV file"""
        filename = "fruits.csv"
        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['x_cm', 'y_cm', 'fruit_type', 'selected', 'collected', 'elevated'])
                for fruit in self.fruits:
                    writer.writerow([fruit.x_cm, fruit.y_cm, fruit.fruit_type, 
                                   fruit.selected, fruit.collected, fruit.elevated])
            print(f"Saved {len(self.fruits)} fruits to {filename}")
        except Exception as e:
            print(f"Error saving fruits: {e}")
    
    def load_fruits(self):
        """Load fruits from CSV file"""
        filename = "fruits.csv"
        if not os.path.exists(filename):
            return
        
        try:
            self.fruits.clear()
            self.selected_fruits.clear()
            
            with open(filename, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    fruit = Fruit(
                        float(row['x_cm']),
                        float(row['y_cm']),
                        row['fruit_type'],
                    )
                    fruit.selected = row.get('selected', 'False').lower() == 'true'
                    fruit.collected = row.get('collected', 'False').lower() == 'true'
                    fruit.elevated = row.get('elevated', 'False').lower() == 'true'
                    
                    self.fruits.append(fruit)
                    if fruit.selected:
                        self.selected_fruits.append(fruit)
            
            print(f"Loaded {len(self.fruits)} fruits from {filename}")
        except Exception as e:
            print(f"Error loading fruits: {e}")
    
    def save_seeds(self):
        """Save seeds to CSV file"""
        filename = "seeds.csv"
        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['x_cm', 'y_cm', 'seed_type', 'planted', 'correct_plot'])
                for seed in self.seeds:
                    writer.writerow([seed.x_cm, seed.y_cm, seed.seed_type, 
                                   seed.planted, seed.correct_plot])
            print(f"Saved {len(self.seeds)} seeds to {filename}")
        except Exception as e:
            print(f"Error saving seeds: {e}")
    
    def load_seeds(self):
        """Load seeds from CSV file"""
        filename = "seeds.csv"
        if not os.path.exists(filename):
            return
        
        try:
            self.seeds.clear()
            
            with open(filename, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    seed = Seed(
                        float(row['x_cm']),
                        float(row['y_cm']),
                        row['seed_type'],
                    )
                    seed.planted = row.get('planted', 'False').lower() == 'true'
                    seed.correct_plot = row.get('correct_plot', 'False').lower() == 'true'
                    
                    self.seeds.append(seed)
            
            print(f"Loaded {len(self.seeds)} seeds from {filename}")
        except Exception as e:
            print(f"Error loading seeds: {e}")
    
    def toggle_zones(self):
        """Toggle display of competition zones"""
        self.show_zones = not self.show_zones
        print(f"Zones display: {'ON' if self.show_zones else 'OFF'}")
    
    def reset_field(self):
        """Reset field to official competition setup"""
        self.clear_all_fruits()
        self.setup_competition_field()
        print("Field reset to official competition setup")
    
    def draw_grid(self):
        """Draw grid on the arena"""
        if not self.show_grid:
            return
        
        grid_spacing_cm = 10
        grid_color = UI_COLORS['grid']
        
        # Vertical lines
        for x_cm in range(0, int(ARENA_WIDTH_CM) + 1, grid_spacing_cm):
            x_px, _ = self.cm_to_pixels(x_cm, 0)
            pg.draw.line(self.screen, grid_color, 
                        (x_px, self.arena_y), 
                        (x_px, self.arena_y + self.arena_h), 1)
        
        # Horizontal lines
        for y_cm in range(0, int(ARENA_HEIGHT_CM) + 1, grid_spacing_cm):
            _, y_px = self.cm_to_pixels(0, y_cm)
            pg.draw.line(self.screen, grid_color,
                        (self.arena_x, y_px),
                        (self.arena_x + self.arena_w, y_px), 1)
    
    def draw_competition_zones(self):
        """Draw official competition zones"""
        if not self.show_zones:
            return
        
        for zone_name, zone_info in COMPETITION_ZONES.items():
            x_px, y_px = self.cm_to_pixels(zone_info['x'], zone_info['y'])
            w_px = int(zone_info['width'] * self.px_per_cm_x)
            h_px = int(zone_info['height'] * self.px_per_cm_y)
            
            # Choose color based on zone type
            if zone_name == 'start_zone':
                color = UI_COLORS['start_zone']
            elif zone_name == 'fruits_zone':
                color = UI_COLORS['fruits_zone']
            elif zone_name == 'waste_zone':
                color = UI_COLORS['waste_zone']
            else:
                color = (100, 100, 100)
            
            # Draw zone rectangle
            pg.draw.rect(self.screen, color, (x_px, y_px, w_px, h_px), 2)
            
            # Draw zone label
            font = pg.font.SysFont(None, 16)
            text = font.render(zone_name.replace('_', ' ').title(), True, UI_COLORS['text'])
            self.screen.blit(text, (x_px, y_px - 20))
    
    def draw_crop_plots(self):
        """Draw crop plots with 2×3 grids"""
        for plot in self.crop_plots:
            x_px, y_px = self.cm_to_pixels(plot.x_cm, plot.y_cm)
            w_px = int(plot.width_cm * self.px_per_cm_x)
            h_px = int(plot.height_cm * self.px_per_cm_y)
            
            # Draw plot border
            color = PLOT_COLORS.get(plot.plot_color, (100, 100, 100))
            pg.draw.rect(self.screen, color, (x_px, y_px, w_px, h_px), 3)
            
            # Draw 2×3 grid
            for i in range(2):
                for j in range(3):
                    grid_x = x_px + i * (w_px // 2)
                    grid_y = y_px + j * (h_px // 3)
                    grid_w = w_px // 2
                    grid_h = h_px // 3
                    pg.draw.rect(self.screen, UI_COLORS['plot_border'], 
                               (grid_x, grid_y, grid_w, grid_h), 1)
            
            # Draw plot label
            font = pg.font.SysFont(None, 16)
            text = font.render(f"{plot.plot_color.title()} Plot", True, UI_COLORS['text'])
            self.screen.blit(text, (x_px, y_px - 20))
    
    def draw_seeds(self):
        """Draw all seeds on the arena"""
        for seed in self.seeds:
            x_px, y_px = self.cm_to_pixels(seed.x_cm, seed.y_cm)
            w, h, d = seed.get_dimensions()
            w_px = int(w * self.px_per_cm_x)
            h_px = int(h * self.px_per_cm_y)
            
            # Draw seed rectangle
            color = seed.get_color()
            pg.draw.rect(self.screen, color, (x_px - w_px//2, y_px - h_px//2, w_px, h_px))
            pg.draw.rect(self.screen, UI_COLORS['text'], 
                        (x_px - w_px//2, y_px - h_px//2, w_px, h_px), 1)
    
    def draw_fruits(self):
        """Draw all fruits on the arena"""
        for fruit in self.fruits:
            x_px, y_px = self.cm_to_pixels(fruit.x_cm, fruit.y_cm)
            radius_px = int(fruit.radius_cm * self.px_per_cm_x)
            
            # Draw fruit circle
            color = fruit.get_color()
            pg.draw.circle(self.screen, color, (x_px, y_px), radius_px)
            pg.draw.circle(self.screen, UI_COLORS['text'], (x_px, y_px), radius_px, 2)
            
            # Draw elevated platform indicator
            if fruit.elevated:
                pg.draw.circle(self.screen, UI_COLORS['elevated_platform'], 
                             (x_px, y_px), radius_px + 5, 2)
            
            # Draw selection indicator
            if fruit.selected:
                pg.draw.circle(self.screen, UI_COLORS['selected_fruit'], 
                             (x_px, y_px), radius_px + 3, 3)
    
    def draw_path(self):
        """Draw the robot collection path"""
        if not self.show_path or len(self.robot_path) < 2:
            return
        
        # Draw path lines
        for i in range(len(self.robot_path) - 1):
            x1_px, y1_px = self.cm_to_pixels(self.robot_path[i][0], self.robot_path[i][1])
            x2_px, y2_px = self.cm_to_pixels(self.robot_path[i+1][0], self.robot_path[i+1][1])
            pg.draw.line(self.screen, UI_COLORS['path_line'], (x1_px, y1_px), (x2_px, y2_px), 3)
        
        # Draw waypoints
        for i, (x_cm, y_cm) in enumerate(self.robot_path):
            x_px, y_px = self.cm_to_pixels(x_cm, y_cm)
            if i == 0:
                color = UI_COLORS['start_point']
                radius = 8
            elif i == len(self.robot_path) - 1:
                color = UI_COLORS['end_point']
                radius = 8
            else:
                color = UI_COLORS['path_line']
                radius = 5
            
            pg.draw.circle(self.screen, color, (x_px, y_px), radius)
            pg.draw.circle(self.screen, UI_COLORS['text'], (x_px, y_px), radius, 2)
    
    def draw_ui(self):
        """Draw the user interface"""
        font = pg.font.SysFont(None, 24)
        small_font = pg.font.SysFont(None, 18)
        
        # Draw buttons
        for button in self.buttons:
            button.draw(self.screen, small_font)
        
        # Draw status information
        status_y = self.arena_y + self.arena_h + 80
        status_lines = [
            f"Mission: {self.mission_mode.title()}",
            f"Fruits: {len(self.fruits)} total, {len(self.selected_fruits)} selected",
            f"Seeds: {len(self.seeds)} total",
            f"Path: {len(self.robot_path)} waypoints",
            f"Current mode: {'Mission' if self.collection_mode else 'Planning'}",
            f"Active type: {self.current_fruit_type if self.mission_mode == 'harvesting' else self.current_seed_type}",
        ]
        
        for i, line in enumerate(status_lines):
            text_surface = small_font.render(line, True, UI_COLORS['text'])
            self.screen.blit(text_surface, (self.arena_x, status_y + i * 20))
        
        # Draw instructions
        instructions = [
            "Left click: Add fruit/seed",
            "Right click: Remove fruit/seed", 
            "Middle click: Toggle selection",
            "G: Toggle grid",
            "P: Toggle path",
            "Z: Toggle zones",
            "ESC: Exit"
        ]
        
        inst_x = self.arena_x + self.arena_w + 10
        inst_y = self.arena_y
        for i, instruction in enumerate(instructions):
            text_surface = small_font.render(instruction, True, UI_COLORS['text'])
            self.screen.blit(text_surface, (inst_x, inst_y + i * 20))
    
    def handle_events(self):
        """Handle pygame events"""
        for event in pg.event.get():
            if event.type == pg.QUIT:
                return False
            
            elif event.type == pg.KEYDOWN:
                if event.key == pg.K_ESCAPE:
                    return False
                elif event.key == pg.K_g:
                    self.show_grid = not self.show_grid
                elif event.key == pg.K_p:
                    self.show_path = not self.show_path
                elif event.key == pg.K_z:
                    self.toggle_zones()
            
            elif event.type == pg.MOUSEBUTTONDOWN:
                # Check if click is within arena
                if (self.arena_x <= event.pos[0] <= self.arena_x + self.arena_w and
                    self.arena_y <= event.pos[1] <= self.arena_y + self.arena_h):
                    
                    # Convert to cm coordinates
                    x_cm = (event.pos[0] - self.arena_x) / self.px_per_cm_x
                    y_cm = (event.pos[1] - self.arena_y) / self.px_per_cm_y
                    
                    if event.button == 1:  # Left click - add fruit
                        self.add_fruit(x_cm, y_cm)
                    elif event.button == 3:  # Right click - remove fruit
                        self.remove_fruit(x_cm, y_cm)
                    elif event.button == 2:  # Middle click - toggle selection
                        self.toggle_fruit_selection(x_cm, y_cm)
            
            # Handle button events
            for button in self.buttons:
                button.handle_event(event)
        
        return True
    
    def run(self):
        """Main application loop"""
        clock = pg.time.Clock()
        running = True
        
        print("=== Official Competition Field Planner ===")
        print("Instructions:")
        print("- Left click: Add fruit/seed")
        print("- Right click: Remove fruit/seed")
        print("- Middle click: Toggle selection")
        print("- Use buttons to control the interface")
        print("- Switch between Harvesting and Cultivation modes")
        print("- Generate path and start mission when ready")
        print("- Official competition: 2 minutes, autonomous operation")
        
        while running:
            running = self.handle_events()
            
            # Draw everything
            self.screen.fill(UI_COLORS['background'])
            
            # Draw arena
            scaled_arena = pg.transform.scale(self.arena_img, (self.arena_w, self.arena_h))
            self.screen.blit(scaled_arena, (self.arena_x, self.arena_y))
            
            # Draw arena border
            pg.draw.rect(self.screen, UI_COLORS['arena_border'], 
                        (self.arena_x, self.arena_y, self.arena_w, self.arena_h), 3)
            
            # Draw grid
            self.draw_grid()
            
            # Draw competition zones
            self.draw_competition_zones()
            
            # Draw crop plots
            self.draw_crop_plots()
            
            # Draw seeds
            self.draw_seeds()
            
            # Draw path
            self.draw_path()
            
            # Draw fruits
            self.draw_fruits()
            
            # Draw UI
            self.draw_ui()
            
            pg.display.flip()
            clock.tick(60)
        
        # Save fruits before exiting
        self.save_fruits()
        pg.quit()

def main():
    try:
        app = FruitSelector()
        app.run()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
