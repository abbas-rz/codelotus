"""Robot simulator package.

Provides virtual robot physics, mock ESP32 telemetry, and visualization
for testing without hardware.
"""
from simulator.virtual_robot import VirtualRobot, RobotConfig, RobotState
from simulator.mock_esp32 import MockESP32

__all__ = [
    'VirtualRobot',
    'RobotConfig',
    'RobotState',
    'MockESP32',
]
