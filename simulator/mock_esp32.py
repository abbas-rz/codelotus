#!/usr/bin/env python3
"""Mock ESP32 UDP server for simulation.

Emulates the ESP32's control and telemetry UDP sockets. Accepts motor commands
and sends encoder/IMU/LIDAR telemetry matching the real robot's protocol.
"""
from __future__ import annotations

import json
import socket
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from virtual_robot import VirtualRobot


class MockESP32:
    """Mock ESP32 UDP server for simulation."""
    
    def __init__(self, robot: VirtualRobot, 
                 ctrl_port: int = 9000, 
                 telem_port: int = 9001,
                 pc_ip: str = "127.0.0.1"):
        self.robot = robot
        self.ctrl_port = ctrl_port
        self.telem_port = telem_port
        self.pc_ip = pc_ip
        
        self.ctrl_sock: socket.socket | None = None
        self.telem_sock: socket.socket | None = None
        
        self.running = False
        self.ctrl_thread: threading.Thread | None = None
        self.telem_thread: threading.Thread | None = None
        
        # Telemetry parameters
        self.encoder_interval = 0.05  # 50ms = 20 Hz
        self.imu_interval = 0.1  # 100ms = 10 Hz
        self.alive_interval = 5.0  # 5 seconds
        
        # Simulated IMU state
        self.imu_heading = 0.0
        self.prev_robot_heading = 0.0
        
    def start(self) -> None:
        """Start mock ESP32 server."""
        if self.running:
            return
        
        self.running = True
        
        # Create control socket (listens for commands)
        self.ctrl_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.ctrl_sock.bind(('0.0.0.0', self.ctrl_port))
        self.ctrl_sock.settimeout(0.1)
        
        # Create telemetry socket (sends data to PC)
        self.telem_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Start threads
        self.ctrl_thread = threading.Thread(target=self._control_loop, daemon=True)
        self.telem_thread = threading.Thread(target=self._telemetry_loop, daemon=True)
        
        self.ctrl_thread.start()
        self.telem_thread.start()
        
        print(f"Mock ESP32 started: control={self.ctrl_port}, telemetry={self.telem_port}")
        print(f"Telemetry target: {self.pc_ip}:{self.telem_port}")
    
    def stop(self) -> None:
        """Stop mock ESP32 server."""
        self.running = False
        if self.ctrl_thread:
            self.ctrl_thread.join(timeout=1.0)
        if self.telem_thread:
            self.telem_thread.join(timeout=1.0)
        if self.ctrl_sock:
            self.ctrl_sock.close()
        if self.telem_sock:
            self.telem_sock.close()
        print("Mock ESP32 stopped")
    
    def _control_loop(self) -> None:
        """Listen for and handle control commands."""
        while self.running:
            try:
                data, addr = self.ctrl_sock.recvfrom(2048)
                msg = json.loads(data.decode())
                self._handle_command(msg, addr)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Control loop error: {e}")
    
    def _handle_command(self, msg: dict, addr: tuple) -> None:
        """Handle incoming control command."""
        msg_type = msg.get('type')
        
        if msg_type == 'motor':
            # Direct motor control
            left = msg.get('left', 0)
            right = msg.get('right', 0)
            self.robot.set_motor_pwm(left, right)
            
        elif msg_type == 'motor4':
            # 4-motor control (use first two motors)
            m1 = msg.get('m1', 0)
            m2 = msg.get('m2', 0)
            self.robot.set_motor_pwm(m1, m2)
            
        elif msg_type == 'move_ticks':
            # Move by encoder ticks
            left_ticks = msg.get('left_ticks', 0)
            right_ticks = msg.get('right_ticks', 0)
            left_speed = msg.get('left_speed', 0)
            right_speed = msg.get('right_speed', 0)
            self.robot.move_by_ticks(left_ticks, right_ticks, left_speed, right_speed)
            
        elif msg_type == 'servo':
            # Servo control (ignored in simulation)
            pass
            
        elif msg_type == 'stepper':
            # Stepper control (ignored in simulation)
            pass
    
    def _telemetry_loop(self) -> None:
        """Send telemetry data to PC."""
        last_encoder = 0.0
        last_imu = 0.0
        last_alive = 0.0
        start_time = time.time()
        
        while self.running:
            current_time = time.time()
            
            # Send encoder telemetry
            if current_time - last_encoder >= self.encoder_interval:
                self._send_encoder_telemetry()
                last_encoder = current_time
            
            # Send IMU telemetry
            if current_time - last_imu >= self.imu_interval:
                self._send_imu_telemetry()
                last_imu = current_time
            
            # Send alive message
            if current_time - last_alive >= self.alive_interval:
                self._send_alive(int((current_time - start_time) * 1000))
                last_alive = current_time
            
            time.sleep(0.01)
    
    def _send_encoder_telemetry(self) -> None:
        """Send encoder counts to PC."""
        left, right = self.robot.get_encoders()
        msg = {
            'type': 'encoders',
            'counts': {
                'm1': left,
                'm2': right,
                'm3': 0,
                'm4': 0,
                'left': left,
                'right': right,
            },
            'ts': int(time.time() * 1000)
        }
        self._send_telemetry(msg)
    
    def _send_imu_telemetry(self) -> None:
        """Send simulated IMU data to PC."""
        # Get robot heading and compute gyro z-axis
        _, _, current_heading = self.robot.get_pose()
        
        # Compute angular velocity (degrees per second)
        heading_delta = current_heading - self.prev_robot_heading
        # Handle wrap-around
        if heading_delta > 180:
            heading_delta -= 360
        elif heading_delta < -180:
            heading_delta += 360
        
        gyro_z = heading_delta / self.imu_interval  # deg/s
        self.prev_robot_heading = current_heading
        
        # Update IMU heading (simulate magnetometer)
        self.imu_heading = current_heading
        
        msg = {
            'type': 'imu',
            'accel': {'x': 0.0, 'y': 0.0, 'z': 9.81},  # Static, gravity only
            'gyro': {'x': 0.0, 'y': 0.0, 'z': gyro_z},
            'heading': self.imu_heading,
            'mag': {'x': 0.0, 'y': 0.0, 'z': 0.0},
            'temp_c': 25.0,
            'ts': int(time.time() * 1000)
        }
        self._send_telemetry(msg)
    
    def _send_alive(self, uptime_ms: int) -> None:
        """Send alive/heartbeat message."""
        msg = {
            'type': 'alive',
            'device': 'SimulatedESP32',
            'ip': '192.168.4.1',  # Simulate AP mode
            'ts': uptime_ms
        }
        self._send_telemetry(msg)
    
    def _send_telemetry(self, msg: dict) -> None:
        """Send telemetry message to PC."""
        try:
            data = json.dumps(msg).encode()
            self.telem_sock.sendto(data, (self.pc_ip, self.telem_port))
        except Exception as e:
            if self.running:
                print(f"Telemetry send error: {e}")


def main():
    """Test mock ESP32."""
    from virtual_robot import VirtualRobot
    
    print("=== Mock ESP32 Test ===")
    robot = VirtualRobot()
    robot.start()
    
    esp32 = MockESP32(robot, pc_ip="127.0.0.1")
    esp32.start()
    
    print("Mock ESP32 running. Listening for commands on port 9000.")
    print("Sending telemetry to 127.0.0.1:9001")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            time.sleep(1)
            state = robot.get_state()
            print(f"Robot: pos=({state.x_cm:.1f}, {state.y_cm:.1f}), "
                  f"heading={state.heading_deg:.1f}°, "
                  f"enc=({state.left_encoder}, {state.right_encoder})")
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        esp32.stop()
        robot.stop()


if __name__ == "__main__":
    main()
