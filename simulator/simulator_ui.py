#!/usr/bin/env python3
"""Visual simulator UI using Pygame.

Shows the arena with a virtual robot moving in real-time. Displays telemetry
and allows manual control for testing.
"""
from __future__ import annotations

import math
import os
import sys
import time

import pygame as pg

# Add parent directory to path to import from main codebase
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulator.virtual_robot import VirtualRobot, RobotConfig
from simulator.mock_esp32 import MockESP32


# Arena dimensions (cm)
ARENA_WIDTH_CM = 118.1
ARENA_HEIGHT_CM = 114.3

# Robot visualization
ROBOT_LENGTH_CM = 10.0
ROBOT_WIDTH_CM = 8.0


class SimulatorUI:
    """Pygame visualization of virtual robot in arena."""
    
    def __init__(self):
        pg.init()
        pg.display.set_caption("Robot Simulator")
        
        # Load arena image
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        arena_path = os.path.join(script_dir, "arena.png")
        
        self.arena_img = None
        if os.path.exists(arena_path):
            self.arena_img = pg.image.load(arena_path)
        
        # Setup display
        info = pg.display.Info()
        self.win_w = int(info.current_w * 0.8)
        self.win_h = int(info.current_h * 0.8)
        self.screen = pg.display.set_mode((self.win_w, self.win_h), pg.RESIZABLE)
        
        # Fonts
        self.font = pg.font.SysFont(None, 20)
        self.font_small = pg.font.SysFont(None, 16)
        
        # Robot and ESP32
        self.config = RobotConfig()
        self.robot = VirtualRobot(self.config)
        self.esp32 = MockESP32(self.robot, pc_ip="127.0.0.1")
        
        # Start simulation
        self.robot.start()
        self.esp32.start()
        
        # Manual control state
        self.manual_left = 0
        self.manual_right = 0
        self.manual_speed = 50
        
        # UI state
        self.show_help = True
        self.show_telemetry = True
        
        print("Simulator started. Press H for help.")
    
    def run(self) -> None:
        """Main simulation loop."""
        clock = pg.time.Clock()
        running = True
        
        while running:
            # Handle events
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    running = False
                elif event.type == pg.KEYDOWN:
                    if event.key in (pg.K_ESCAPE, pg.K_q):
                        running = False
                    elif event.key == pg.K_h:
                        self.show_help = not self.show_help
                    elif event.key == pg.K_t:
                        self.show_telemetry = not self.show_telemetry
                    elif event.key == pg.K_r:
                        self.robot.reset()
                        print("Robot reset to origin")
                    elif event.key == pg.K_SPACE:
                        self.robot.set_motor_pwm(0, 0)
                        self.manual_left = 0
                        self.manual_right = 0
            
            # Manual control with WASD
            keys = pg.key.get_pressed()
            self.manual_left = 0
            self.manual_right = 0
            
            if keys[pg.K_w]:  # Forward
                self.manual_left += self.manual_speed
                self.manual_right += self.manual_speed
            if keys[pg.K_s]:  # Backward
                self.manual_left -= self.manual_speed
                self.manual_right -= self.manual_speed
            if keys[pg.K_a]:  # Turn left
                self.manual_left -= self.manual_speed // 2
                self.manual_right += self.manual_speed // 2
            if keys[pg.K_d]:  # Turn right
                self.manual_left += self.manual_speed // 2
                self.manual_right -= self.manual_speed // 2
            
            if self.manual_left != 0 or self.manual_right != 0:
                self.robot.set_motor_pwm(self.manual_left, self.manual_right)
            
            # Render
            self.render()
            
            # Cap framerate
            clock.tick(60)
        
        self.cleanup()
    
    def render(self) -> None:
        """Render the simulation."""
        # Clear screen
        self.screen.fill((20, 20, 24))
        
        # Get window size
        self.win_w, self.win_h = self.screen.get_size()
        
        # Compute arena scaling
        if self.arena_img:
            img_w, img_h = self.arena_img.get_width(), self.arena_img.get_height()
        else:
            # Use a virtual arena size
            img_w, img_h = 1181, 1143  # 10 px per cm
        
        scale = min(self.win_w * 0.7 / img_w, self.win_h * 0.9 / img_h)
        arena_w = int(img_w * scale)
        arena_h = int(img_h * scale)
        arena_x = (self.win_w - arena_w) // 2 - 100
        arena_y = (self.win_h - arena_h) // 2
        
        # Draw arena
        if self.arena_img:
            scaled_arena = pg.transform.smoothscale(self.arena_img, (arena_w, arena_h))
            self.screen.blit(scaled_arena, (arena_x, arena_y))
        else:
            # Draw placeholder arena
            pg.draw.rect(self.screen, (40, 40, 44), 
                        (arena_x, arena_y, arena_w, arena_h))
            pg.draw.rect(self.screen, (80, 80, 84), 
                        (arena_x, arena_y, arena_w, arena_h), 2)
        
        # Draw coordinate system
        px_per_cm_x = arena_w / ARENA_WIDTH_CM
        px_per_cm_y = arena_h / ARENA_HEIGHT_CM
        
        # Draw robot
        state = self.robot.get_state()
        self._draw_robot(state.x_cm, state.y_cm, state.heading_deg,
                        arena_x, arena_y, px_per_cm_x, px_per_cm_y)
        
        # Draw telemetry
        if self.show_telemetry:
            self._draw_telemetry(state, arena_x + arena_w + 20, arena_y)
        
        # Draw help
        if self.show_help:
            self._draw_help()
        
        pg.display.flip()
    
    def _draw_robot(self, x_cm: float, y_cm: float, heading_deg: float,
                   arena_x: int, arena_y: int, px_per_cm_x: float, px_per_cm_y: float) -> None:
        """Draw the robot at its current position."""
        # Convert cm to screen pixels
        screen_x = arena_x + x_cm * px_per_cm_x
        screen_y = arena_y + y_cm * px_per_cm_y
        
        # Robot dimensions in pixels
        length_px = ROBOT_LENGTH_CM * (px_per_cm_x + px_per_cm_y) / 2
        width_px = ROBOT_WIDTH_CM * (px_per_cm_x + px_per_cm_y) / 2
        
        # Draw robot body
        heading_rad = math.radians(heading_deg)
        
        # Robot corners (local coordinates)
        corners = [
            (-width_px/2, -length_px/2),  # rear left
            (width_px/2, -length_px/2),   # rear right
            (width_px/2, length_px/2),    # front right
            (-width_px/2, length_px/2),   # front left
        ]
        
        # Rotate and translate to world coordinates
        rotated = []
        cos_h = math.cos(heading_rad)
        sin_h = math.sin(heading_rad)
        for dx, dy in corners:
            rx = dx * cos_h - dy * sin_h
            ry = dx * sin_h + dy * cos_h
            rotated.append((screen_x + rx, screen_y + ry))
        
        # Draw body
        pg.draw.polygon(self.screen, (80, 120, 200), rotated)
        pg.draw.polygon(self.screen, (120, 160, 240), rotated, 2)
        
        # Draw heading indicator (arrow)
        arrow_len = length_px * 0.6
        arrow_x = screen_x + arrow_len * math.sin(heading_rad)
        arrow_y = screen_y - arrow_len * math.cos(heading_rad)
        pg.draw.line(self.screen, (255, 255, 100), 
                    (screen_x, screen_y), (arrow_x, arrow_y), 3)
        
        # Draw center dot
        pg.draw.circle(self.screen, (255, 255, 255), 
                      (int(screen_x), int(screen_y)), 3)
    
    def _draw_telemetry(self, state, x: int, y: int) -> None:
        """Draw telemetry information."""
        lines = [
            "=== Telemetry ===",
            f"Pos: ({state.x_cm:.1f}, {state.y_cm:.1f}) cm",
            f"Heading: {state.heading_deg:.1f}°",
            "",
            f"Encoders:",
            f"  L: {state.left_encoder}",
            f"  R: {state.right_encoder}",
            "",
            f"Motors (PWM):",
            f"  L: {state.left_speed_pwm}",
            f"  R: {state.right_speed_pwm}",
            "",
            f"Move active: {state.move_active}",
            "",
            f"Config:",
            f"  PPD: {self.config.pulses_per_degree:.2f}",
            f"  PPC: {self.config.pulses_per_cm:.2f}",
            f"  Wheelbase: {self.config.wheelbase_cm:.2f} cm",
        ]
        
        for i, line in enumerate(lines):
            color = (220, 220, 220) if line.startswith("===") else (180, 180, 180)
            text = self.font_small.render(line, True, color)
            self.screen.blit(text, (x, y + i * 18))
    
    def _draw_help(self) -> None:
        """Draw help overlay."""
        help_lines = [
            "Controls:",
            "  W/A/S/D - Manual drive",
            "  Space - Stop motors",
            "  R - Reset robot to origin",
            "  H - Toggle this help",
            "  T - Toggle telemetry",
            "  Q/Esc - Quit",
            "",
            "The mock ESP32 is running:",
            "  Control: port 9000",
            "  Telemetry: port 9001 → 127.0.0.1",
        ]
        
        padding = 12
        line_height = 20
        box_w = 320
        box_h = len(help_lines) * line_height + padding * 2
        box_x = self.win_w - box_w - 20
        box_y = 20
        
        # Draw semi-transparent background
        overlay = pg.Surface((box_w, box_h), pg.SRCALPHA)
        overlay.fill((10, 10, 15, 200))
        self.screen.blit(overlay, (box_x, box_y))
        
        # Draw text
        for i, line in enumerate(help_lines):
            color = (240, 240, 240) if line.endswith(":") else (200, 200, 200)
            text = self.font_small.render(line, True, color)
            self.screen.blit(text, (box_x + padding, box_y + padding + i * line_height))
    
    def cleanup(self) -> None:
        """Clean up resources."""
        print("Shutting down simulator...")
        self.esp32.stop()
        self.robot.stop()
        pg.quit()


def main():
    """Run the simulator."""
    try:
        sim = SimulatorUI()
        sim.run()
    except KeyboardInterrupt:
        print("\nInterrupted")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
