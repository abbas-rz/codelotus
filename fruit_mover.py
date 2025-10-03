#!/usr/bin/env python3
# execute_fruit_track.py - Execute fruit harvesting track
from move_control import RobotController
import advanced
import time

advanced.init_bot_control(verbose_telemetry=False)
time.sleep(5)

controller = RobotController()

with open("fruit_track.txt", "r") as f:
    for line in f:
        if line.strip():
            angle, distance = map(float, line.split(','))
            controller.execute_command(angle, distance)
            time.sleep(0.5)  # Brief pause between segments

advanced.cleanup()