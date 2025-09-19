"""
rotationalmech.py — 28BYJ-48 stepper via ULN2003 on Raspberry Pi (Python)

Converted from Arduino AccelStepper example to native Python using RPi.GPIO.

Behavior: move the stepper by 53° increments, wait 5 seconds, and repeat.

Connections (BCM numbering):
- IN1 -> GPIO14
- IN2 -> GPIO15
- IN3 -> GPIO8
- IN4 -> GPIO9

You can change pins by editing PINS below. Steps per revolution defaults to 2048
for half-stepping on 28BYJ-48.
"""

import time
import math
import RPi.GPIO as GPIO  # pyright: ignore[reportMissingModuleSource]


# BCM GPIO pins for ULN2003 inputs (order matters for sequence)
PINS = [14, 15, 8, 9]

# Half-step sequence for 28BYJ-48
SEQ = [
  (1,0,0,0), (1,1,0,0), (0,1,0,0), (0,1,1,0),
  (0,0,1,0), (0,0,1,1), (0,0,0,1), (1,0,0,1),
]

STEPS_PER_REV = 2048  # typical 28BYJ-48 in half-stepping
INCREMENT_DEGREES = 53.0


def setup_gpio():
  GPIO.setmode(GPIO.BCM)
  GPIO.setwarnings(False)
  for p in PINS:
    GPIO.setup(p, GPIO.OUT, initial=GPIO.LOW)


def deenergize():
  for p in PINS:
    GPIO.output(p, GPIO.LOW)


def step(steps: int, delay_s: float = 0.003):
  """Perform signed number of half-steps with given per-step delay in seconds."""
  if steps == 0:
    return
  direction = 1 if steps > 0 else -1
  idx = 0 if direction > 0 else len(SEQ) - 1
  count = abs(int(steps))
  for _ in range(count):
    pattern = SEQ[idx]
    for pin, val in zip(PINS, pattern):
      GPIO.output(pin, GPIO.HIGH if val else GPIO.LOW)
    time.sleep(delay_s)
    idx = (idx + direction) % len(SEQ)
  deenergize()


def degrees_to_steps(deg: float) -> int:
  return int(round((deg / 360.0) * STEPS_PER_REV))


def main():
  setup_gpio()
  try:
    steps_per_increment = degrees_to_steps(INCREMENT_DEGREES)
    while True:
      step(steps_per_increment, delay_s=0.003)
      time.sleep(5.0)
  except KeyboardInterrupt:
    pass
  finally:
    deenergize()
    GPIO.cleanup()


if __name__ == "__main__":
  main()