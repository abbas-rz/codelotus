# Motor Configuration Examples
# 
# This file shows how to configure different motor maximum speeds
# to compensate for motors with different RPM ratings on left and right sides.

# ===== EXAMPLE CONFIGURATIONS =====

# Example 1: Identical motors (default)
MOTOR_MAX_LEFT = 120
MOTOR_MAX_RIGHT = 120

# Example 2: Right motor is faster, compensate by reducing its max speed
# If right motor spins 20% faster than left motor:
# MOTOR_MAX_LEFT = 120
# MOTOR_MAX_RIGHT = 100

# Example 3: Left motor is faster, compensate by reducing its max speed
# If left motor spins 15% faster than right motor:
# MOTOR_MAX_LEFT = 105
# MOTOR_MAX_RIGHT = 120

# Example 4: Significantly different motors
# If you have a 300 RPM left motor and 500 RPM right motor:
# MOTOR_MAX_LEFT = 120
# MOTOR_MAX_RIGHT = 72    # 120 * (300/500) = 72

# ===== HOW TO DETERMINE YOUR VALUES =====

# Method 1: Trial and Error
# 1. Start with equal values (120, 120)
# 2. Run the bot forward in manual mode
# 3. If it curves left: reduce MOTOR_MAX_LEFT
# 4. If it curves right: reduce MOTOR_MAX_RIGHT
# 5. Adjust until it goes straight

# Method 2: RPM Measurement
# 1. Measure actual RPM of each motor at full speed
# 2. Calculate ratio: slower_rpm / faster_rpm
# 3. Multiply the faster motor's MOTOR_MAX by this ratio

# Method 3: Encoder Feedback (if available)
# 1. Use encoder counts over time to measure actual speeds
# 2. Adjust MOTOR_MAX values to equalize actual movement

# ===== FINE-TUNING TIPS =====

# Small adjustments (±5) for minor drift
# Medium adjustments (±10-20) for noticeable pulling
# Large adjustments (±30+) for significant speed differences

# Test in both directions:
# - Forward movement should be straight
# - Turning should be symmetrical (same turn radius left/right)

# Remember: These values affect ALL movement modes:
# - Manual control (WASD)
# - Autonomous navigation
# - Vision-guided tracking

print("Motor configuration loaded")
print(f"Left motor max: {MOTOR_MAX_LEFT}")
print(f"Right motor max: {MOTOR_MAX_RIGHT}")

if MOTOR_MAX_LEFT != MOTOR_MAX_RIGHT:
    ratio = min(MOTOR_MAX_LEFT, MOTOR_MAX_RIGHT) / max(MOTOR_MAX_LEFT, MOTOR_MAX_RIGHT)
    slower_side = "LEFT" if MOTOR_MAX_LEFT < MOTOR_MAX_RIGHT else "RIGHT"
    print(f"Compensation: {slower_side} motor limited to {ratio:.1%} of faster motor")
else:
    print("Motors configured for equal maximum speeds")
