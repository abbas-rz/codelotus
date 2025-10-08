#!/usr/bin/env python3
"""Virtual robot physics simulator.

Simulates a 2-wheel differential drive robot with encoders, motor factors,
and realistic physics. Used by mock_esp32.py to provide telemetry data.
"""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Tuple


@dataclass
class RobotConfig:
    """Physical robot configuration."""
    wheel_diameter_cm: float = 4.4
    wheelbase_cm: float = 11.86  # distance between left and right wheels
    ppr: int = 5632  # pulses per rotation (encoder resolution × gear ratio)
    motor_factor_left: float = 0.98  # simulate motor imbalance
    motor_factor_right: float = 1.0
    max_speed: int = 100  # maximum PWM value
    
    @property
    def wheel_circumference_cm(self) -> float:
        return math.pi * self.wheel_diameter_cm
    
    @property
    def pulses_per_cm(self) -> float:
        """Encoder pulses per cm of wheel travel."""
        return self.ppr / self.wheel_circumference_cm
    
    @property
    def pulses_per_degree(self) -> float:
        """Encoder pulses per degree of rotation."""
        # For differential drive: rotation creates arc length difference
        # arc_diff = wheelbase * angle_rad
        # pulses_diff = arc_diff_cm * pulses_per_cm
        return (self.pulses_per_cm * self.wheelbase_cm * math.pi) / 360.0


@dataclass
class RobotState:
    """Current robot state."""
    x_cm: float = 0.0
    y_cm: float = 0.0
    heading_deg: float = 0.0  # 0 = up (north), 90 = right (east)
    
    left_encoder: int = 0
    right_encoder: int = 0
    
    left_speed_pwm: int = 0  # current motor PWM (-100 to 100)
    right_speed_pwm: int = 0
    
    # Move-by-ticks state
    move_active: bool = False
    move_target_left: int = 0
    move_target_right: int = 0
    move_start_left: int = 0
    move_start_right: int = 0
    move_speed_left: int = 0
    move_speed_right: int = 0


class VirtualRobot:
    """Simulates differential drive robot with encoder feedback."""
    
    def __init__(self, config: RobotConfig | None = None):
        self.config = config or RobotConfig()
        self.state = RobotState()
        self.lock = threading.Lock()
        
        # Physics simulation
        self.dt = 0.02  # 50 Hz update rate
        self.running = False
        self.physics_thread: threading.Thread | None = None
        
        # Simulation parameters
        self.speed_to_cm_per_sec = 0.5  # PWM 100 = 50 cm/s (adjustable)
    
    def start(self) -> None:
        """Start physics simulation thread."""
        if self.running:
            return
        self.running = True
        self.physics_thread = threading.Thread(target=self._physics_loop, daemon=True)
        self.physics_thread.start()
        print("Virtual robot physics started")
    
    def stop(self) -> None:
        """Stop physics simulation."""
        self.running = False
        if self.physics_thread:
            self.physics_thread.join(timeout=1.0)
    
    def reset(self, x: float = 0.0, y: float = 0.0, heading: float = 0.0) -> None:
        """Reset robot to given pose."""
        with self.lock:
            self.state.x_cm = x
            self.state.y_cm = y
            self.state.heading_deg = heading
            self.state.left_encoder = 0
            self.state.right_encoder = 0
            self.state.left_speed_pwm = 0
            self.state.right_speed_pwm = 0
            self.state.move_active = False
    
    def set_motor_pwm(self, left_pwm: int, right_pwm: int) -> None:
        """Set motor PWM values (direct control)."""
        with self.lock:
            self.state.left_speed_pwm = max(-self.config.max_speed, 
                                            min(self.config.max_speed, left_pwm))
            self.state.right_speed_pwm = max(-self.config.max_speed, 
                                             min(self.config.max_speed, right_pwm))
            # Cancel move-by-ticks if active
            self.state.move_active = False
    
    def move_by_ticks(self, left_ticks: int, right_ticks: int, 
                      left_speed: int, right_speed: int) -> None:
        """Command robot to move until encoder targets are reached."""
        with self.lock:
            self.state.move_active = True
            self.state.move_target_left = left_ticks
            self.state.move_target_right = right_ticks
            self.state.move_start_left = self.state.left_encoder
            self.state.move_start_right = self.state.right_encoder
            self.state.move_speed_left = left_speed
            self.state.move_speed_right = right_speed
            # Set initial motor speeds
            self.state.left_speed_pwm = left_speed
            self.state.right_speed_pwm = right_speed
    
    def get_state(self) -> RobotState:
        """Get current robot state (thread-safe copy)."""
        with self.lock:
            return RobotState(
                x_cm=self.state.x_cm,
                y_cm=self.state.y_cm,
                heading_deg=self.state.heading_deg,
                left_encoder=self.state.left_encoder,
                right_encoder=self.state.right_encoder,
                left_speed_pwm=self.state.left_speed_pwm,
                right_speed_pwm=self.state.right_speed_pwm,
                move_active=self.state.move_active,
            )
    
    def get_encoders(self) -> Tuple[int, int]:
        """Get current encoder counts."""
        with self.lock:
            return self.state.left_encoder, self.state.right_encoder
    
    def get_pose(self) -> Tuple[float, float, float]:
        """Get current pose (x, y, heading)."""
        with self.lock:
            return self.state.x_cm, self.state.y_cm, self.state.heading_deg
    
    def _physics_loop(self) -> None:
        """Physics simulation loop (runs in separate thread)."""
        last_time = time.time()
        
        while self.running:
            current_time = time.time()
            dt = current_time - last_time
            
            if dt >= self.dt:
                self._update_physics(dt)
                last_time = current_time
            
            time.sleep(0.001)  # Small sleep to prevent CPU spinning
    
    def _update_physics(self, dt: float) -> None:
        """Update robot physics for one timestep."""
        with self.lock:
            # Check move-by-ticks completion
            if self.state.move_active:
                left_delta = abs(self.state.left_encoder - self.state.move_start_left)
                right_delta = abs(self.state.right_encoder - self.state.move_start_right)
                
                if left_delta >= abs(self.state.move_target_left) and \
                   right_delta >= abs(self.state.move_target_right):
                    # Target reached, stop motors
                    self.state.left_speed_pwm = 0
                    self.state.right_speed_pwm = 0
                    self.state.move_active = False
            
            # Apply motor factors
            left_actual = self.state.left_speed_pwm * self.config.motor_factor_left
            right_actual = self.state.right_speed_pwm * self.config.motor_factor_right
            
            # Convert PWM to wheel speeds (cm/s)
            left_speed_cm_s = (left_actual / self.config.max_speed) * self.speed_to_cm_per_sec * self.config.max_speed
            right_speed_cm_s = (right_actual / self.config.max_speed) * self.speed_to_cm_per_sec * self.config.max_speed
            
            # Differential drive kinematics
            forward_speed = (left_speed_cm_s + right_speed_cm_s) / 2.0
            angular_speed_deg_s = (right_speed_cm_s - left_speed_cm_s) / self.config.wheelbase_cm * 180.0 / math.pi
            
            # Update pose
            heading_rad = math.radians(self.state.heading_deg)
            self.state.x_cm += forward_speed * math.sin(heading_rad) * dt
            self.state.y_cm -= forward_speed * math.cos(heading_rad) * dt  # -Y is up
            self.state.heading_deg += angular_speed_deg_s * dt
            self.state.heading_deg = self.state.heading_deg % 360.0
            
            # Update encoders based on wheel distances
            left_dist_cm = left_speed_cm_s * dt
            right_dist_cm = right_speed_cm_s * dt
            
            left_pulses = int(left_dist_cm * self.config.pulses_per_cm)
            right_pulses = int(right_dist_cm * self.config.pulses_per_cm)
            
            self.state.left_encoder += left_pulses
            self.state.right_encoder += right_pulses


def main():
    """Test virtual robot."""
    print("=== Virtual Robot Test ===")
    robot = VirtualRobot()
    robot.start()
    
    print("Initial pose:", robot.get_pose())
    print("Initial encoders:", robot.get_encoders())
    
    # Test 1: Move forward
    print("\nTest 1: Moving forward at PWM 50 for 2 seconds")
    robot.set_motor_pwm(50, 50)
    time.sleep(2.0)
    robot.set_motor_pwm(0, 0)
    print("Pose:", robot.get_pose())
    print("Encoders:", robot.get_encoders())
    
    # Test 2: Turn in place
    print("\nTest 2: Turning in place (PWM -50, 50) for 1 second")
    robot.set_motor_pwm(-50, 50)
    time.sleep(1.0)
    robot.set_motor_pwm(0, 0)
    print("Pose:", robot.get_pose())
    print("Encoders:", robot.get_encoders())
    
    # Test 3: Move by ticks
    print("\nTest 3: Move by ticks (4000 ticks forward)")
    robot.move_by_ticks(4000, 4000, 45, 45)
    time.sleep(3.0)
    print("Pose:", robot.get_pose())
    print("Encoders:", robot.get_encoders())
    
    robot.stop()
    print("\nTest complete")


if __name__ == "__main__":
    main()
