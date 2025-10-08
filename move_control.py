#!/usr/bin/env python3
"""
Robot Movement Control with Pure Encoder-Based Navigation
Usage: python move_control.py
Takes rotation (degrees) and movement (cm) inputs to control the robot using only encoder data.

Encoder Specifications:
- PPR (Pulses Per Rotation): 1500
- Wheel diameter: 4.4 cm
- Bot rotation: 22.3 pulses per degree
"""
import time
import sys
import math
from advanced import (
    init_bot_control, cleanup, get_latest_encoders, move_by_ticks,
    stop_motors, is_encoder_data_available, wait_for_encoder_data, send_motor
)
from calibration_config import (
    load_pulses_per_degree,
    load_pulses_per_cm,
    save_pulses_per_degree,
    save_pulses_per_cm,
)

class RobotController:
    def __init__(self):
        # Robot specifications
        self.PPR = 5640  # Pulses per rotation
        self.WHEEL_DIAMETER = 4.4  # cm
        self.WHEEL_CIRCUMFERENCE = math.pi * self.WHEEL_DIAMETER  # cm per rotation
        self.DEFAULT_PULSES_PER_CM = self.PPR / self.WHEEL_CIRCUMFERENCE
        self.PULSES_PER_CM = load_pulses_per_cm(self.DEFAULT_PULSES_PER_CM)
        self.PULSES_PER_DEGREE = load_pulses_per_degree()
        self.session_pulses_per_degree = self.PULSES_PER_DEGREE
        self.session_pulses_per_cm = self.PULSES_PER_CM
        
        # Control parameters
        # CRITICAL: Motor speeds must match calibration utilities (measure_ppd/ppc_encoder_only.py)
        # to ensure calibrated values produce accurate movements. Different speeds cause
        # different motor behavior, momentum, and backlash characteristics.
        self.rotation_tolerance = 350000000.0  # degrees - allow ±5 degree error
        self.distance_tolerance = 50000000.0  # cm - allow ±5 cm error
        self.turn_speed = 45 # motor speed for turning - MUST MATCH CALIBRATION SPEED
        self.move_speed = 45  # motor speed for movement - MUST MATCH CALIBRATION SPEED
        self.max_turn_time = 10.0  # maximum time to attempt a turn (seconds)
        self.max_move_time = 30.0  # maximum time to attempt a move (seconds)
        self.enable_error_correction = True  # automatically correct errors
        self.max_correction_attempts = 5  # maximum correction iterations
        self.turn_brake_duration = 0.08

        self.turn_brake_scale = 0.55
        self.turn_progress_timeout = 1.2

        self.distance_adapt_alpha = 0.25
        self.move_decel_ratio = 0.22
        self.move_min_speed_scale = 0.32
        self.move_brake_scale = 0.5
        self.move_brake_duration = 0.12
        self.no_progress_timeout = 1.5

        self.last_turn_adjustment = 0.0
        
        print(f"Robot Encoder Specs:")
        print(f"  PPR: {self.PPR}")
        print(f"  Wheel diameter: {self.WHEEL_DIAMETER} cm")
        print(f"  Wheel circumference: {self.WHEEL_CIRCUMFERENCE:.2f} cm")
        print(f"  Pulses per cm: {self.PULSES_PER_CM:.2f} (default {self.DEFAULT_PULSES_PER_CM:.2f})")
        print(f"  Pulses per degree rotation: {self.PULSES_PER_DEGREE}")
    
    def configure_tolerances(self, rotation_tolerance=None, distance_tolerance=None):
        """Configure tolerance values for rotation and distance"""
        if rotation_tolerance is not None:
            self.rotation_tolerance = max(0.1, float(rotation_tolerance))
            print(f"Rotation tolerance set to ±{self.rotation_tolerance:.1f} degrees")
        
        if distance_tolerance is not None:
            self.distance_tolerance = max(0.1, float(distance_tolerance))
            print(f"Distance tolerance set to ±{self.distance_tolerance:.1f} cm")
    
    def configure_turn_precision(self, pulses_per_degree=None, turn_speed=None):
        """Configure turn precision parameters"""
        if pulses_per_degree is not None:
            self.PULSES_PER_DEGREE = max(1, float(pulses_per_degree))
            save_pulses_per_degree(self.PULSES_PER_DEGREE)
            self.session_pulses_per_degree = self.PULSES_PER_DEGREE
            self.last_turn_adjustment = 0.0
            print(f"PULSES_PER_DEGREE set to {self.PULSES_PER_DEGREE}")
        
        if turn_speed is not None:
            self.turn_speed = max(5, min(50, int(turn_speed)))
            print(f"Turn speed set to {self.turn_speed}")

    def configure_distance_precision(self, pulses_per_cm=None):
        """Configure and persist encoder pulses-per-centimeter."""
        if pulses_per_cm is not None:
            self.PULSES_PER_CM = max(1.0, float(pulses_per_cm))
            save_pulses_per_cm(self.PULSES_PER_CM)
            self.session_pulses_per_cm = self.PULSES_PER_CM
            print(f"PULSES_PER_CM set to {self.PULSES_PER_CM:.3f}")
    
    def configure_error_correction(self, enable=None):
        """Configure error correction settings"""
        if enable is not None:
            self.enable_error_correction = bool(enable)
            status = "enabled" if self.enable_error_correction else "disabled"
            print(f"Error correction {status}")
    
    def set_rotation_tolerance(self, tolerance_degrees):
        """Set rotation tolerance for turn accuracy"""
        self.rotation_tolerance = max(0.1, float(tolerance_degrees))
        print(f"Rotation tolerance set to ±{self.rotation_tolerance:.1f} degrees")
    
    def configure_speeds(self, turn_speed=None, move_speed=None):
        """Configure speed values for turning and movement"""
        if turn_speed is not None:
            self.turn_speed = max(5, min(120, int(turn_speed)))
            print(f"Turn speed set to {self.turn_speed}")
        
        if move_speed is not None:
            self.move_speed = max(5, min(120, int(move_speed)))
            print(f"Move speed set to {self.move_speed}")
    
    def configure_timeouts(self, turn_timeout=None, move_timeout=None):
        """Configure timeout values for operations"""
        if turn_timeout is not None:
            self.max_turn_time = max(5.0, float(turn_timeout))
            print(f"Turn timeout set to {self.max_turn_time:.1f} seconds")
        
        if move_timeout is not None:
            self.max_move_time = max(5.0, float(move_timeout))
            print(f"Move timeout set to {self.max_move_time:.1f} seconds")
    
    def show_configuration(self):
        """Display current configuration"""
        print(f"\n=== ROBOT CONFIGURATION ===")
        print(f"Rotation tolerance: ±{self.rotation_tolerance:.1f} degrees")
        print(f"Distance tolerance: ±{self.distance_tolerance:.1f} cm")
        print(f"Turn speed: {self.turn_speed}")
        print(f"Move speed: {self.move_speed}")
        print(f"Turn timeout: {self.max_turn_time:.1f} seconds")
        print(f"Move timeout: {self.max_move_time:.1f} seconds")
        print(
            f"Turn calibration: session {self.session_pulses_per_degree:.3f} ppd (persisted {self.PULSES_PER_DEGREE:.3f}, Δ{self.last_turn_adjustment:+.3f})"
        )
        print(
            f"Distance calibration: session {self.session_pulses_per_cm:.3f} ppcm (persisted {self.PULSES_PER_CM:.3f}, Δ{self.session_pulses_per_cm - self.PULSES_PER_CM:+.3f})"
        )
        print("=" * 30)
        
    def test_esp32_connection(self):
        """Test connection to ESP32 and display status"""
        print("\n🔍 Testing ESP32 Connection...")
        print("=" * 40)
        
        # Use the shared function from advanced.py
        if is_encoder_data_available():
            encoders, enc_time = get_latest_encoders()
            current_time = time.time()
            age = current_time - enc_time
            print(f"📊 Latest encoder data:")
            print(f"   m1={encoders['m1']}, m2={encoders['m2']}")
            print(f"   m3={encoders['m3']}, m4={encoders['m4']}")
            print(f"   Age: {age:.1f} seconds")
            print("✅ Connection is good!")
            return True
        else:
            print("❌ No encoder data available")
            return False

    def get_encoder_position(self):
        """Get current encoder positions for left and right motors"""
        encoders, _ = get_latest_encoders()
        # For 2-motor system: m1=left, m2=right
        left_enc = encoders.get('m1', 0)
        right_enc = encoders.get('m2', 0)
        return left_enc, right_enc
        
    def reset_encoder_reference(self):
        """Set current encoder position as reference point"""
        self.start_left, self.start_right = self.get_encoder_position()
        print(f"Encoder reference set: left={self.start_left}, right={self.start_right}")
        
    def get_relative_position(self):
        """Get encoder position relative to reference point"""
        current_left, current_right = self.get_encoder_position()
        rel_left = current_left - self.start_left
        rel_right = current_right - self.start_right
        return rel_left, rel_right

    def apply_brake(self, left_sign, right_sign, base_speed, scale, duration):
        """Send a short reverse pulse to counter momentum before fully stopping."""
        brake_speed = max(0, int(abs(base_speed) * scale))
        if brake_speed == 0:
            stop_motors()
            return

        send_motor(-left_sign * brake_speed, -right_sign * brake_speed)
        time.sleep(max(0.02, duration))
        stop_motors()
        
    def turn_to_angle(self, target_degrees):
        """Turn the robot using hardware encoder-based movement."""
        print(f"Turning {target_degrees:+.1f} degrees using hardware encoder control...")

        if abs(target_degrees) < 0.1:
            print("No significant rotation requested.")
            return True

        # Use session calibration value
        target_ticks = int(round(abs(target_degrees) * self.session_pulses_per_degree))
        direction = 1 if target_degrees > 0 else -1
        direction_text = "right (CW)" if direction > 0 else "left (CCW)"

        print(f"Target ticks per wheel: {target_ticks} (for {abs(target_degrees):.1f}°)")
        print(f"Turning {direction_text} at speed {self.turn_speed}")
        print(f"Using session_pulses_per_degree: {self.session_pulses_per_degree:.3f}")

        # Reset encoder reference to measure actual movement
        self.reset_encoder_reference()
        time.sleep(0.1)

        # Use hardware move_by_ticks for precise encoder-based turning
        # For right turn: left=positive ticks, right=negative ticks
        # For left turn: left=negative ticks, right=positive ticks
        left_ticks = direction * target_ticks
        right_ticks = -direction * target_ticks
        left_speed = direction * self.turn_speed
        right_speed = -direction * self.turn_speed
        
        move_by_ticks(left_ticks, right_ticks, left_speed, right_speed)
        
        # Wait for movement to complete (ESP32 handles the control loop)
        # Poll encoders to detect completion
        start_time = time.time()
        last_check_ticks = 0.0
        stall_count = 0
        
        while time.time() - start_time < self.max_turn_time:
            rel_left, rel_right = self.get_relative_position()
            avg_ticks = (abs(rel_left) + abs(rel_right)) / 2.0
            
            # Check if we've reached target (with small tolerance)
            if avg_ticks >= target_ticks - 5:
                time.sleep(0.2)  # Let it settle
                break
            
            # Stall detection
            if abs(avg_ticks - last_check_ticks) < 2:
                stall_count += 1
                if stall_count > 10:  # 0.5 seconds of no progress
                    print("⚠️ Turn appears stalled")
                    break
            else:
                stall_count = 0
            
            last_check_ticks = avg_ticks
            time.sleep(0.05)
        else:
            print("⚠️ Turn timeout reached")

        stop_motors()
        time.sleep(0.2)

        # Measure final result
        rel_left, rel_right = self.get_relative_position()
        final_ticks = (abs(rel_left) + abs(rel_right)) / 2.0
        actual_rotation = (final_ticks / self.session_pulses_per_degree) * direction

        error = target_degrees - actual_rotation

        print("Turn results:")
        print(f"  Target: {target_degrees:+.1f}° ({target_ticks} ticks per wheel)")
        print(f"  Actual: {actual_rotation:+.1f}° ({final_ticks:.1f} ticks average)")
        print(f"  Error: {error:+.1f}°")
        print(f"  Encoder deltas: left={rel_left}, right={rel_right}")
        print(f"  Tolerance: ±{self.rotation_tolerance:.1f}°")

        success = abs(error) <= self.rotation_tolerance
        if success:
            print("✅ Turn completed within tolerance")
            return True
        
        # Error correction if enabled
        if not self.enable_error_correction:
            print("⚠️ Turn completed but outside tolerance (correction disabled)")
            return False
        
        print(f"⚠️ Turn error {error:+.1f}° exceeds tolerance, attempting correction...")
        
        # Try up to max_correction_attempts to get within tolerance
        for attempt in range(self.max_correction_attempts):
            correction_degrees = -error  # Opposite of error
            
            # Don't correct if error is tiny
            if abs(correction_degrees) < 0.5:
                print("✅ Error correction converged")
                return True
            
            print(f"  Correction attempt {attempt + 1}/{self.max_correction_attempts}: adjusting {correction_degrees:+.1f}°")
            
            # Make corrective turn (recursive call with correction disabled to avoid infinite loop)
            saved_correction_flag = self.enable_error_correction
            self.enable_error_correction = False
            
            correction_success = self.turn_to_angle(correction_degrees)
            
            self.enable_error_correction = saved_correction_flag
            
            if not correction_success:
                print("❌ Correction turn failed")
                return False
            
            # Measure total rotation from original reference
            rel_left, rel_right = self.get_relative_position()
            final_ticks = (abs(rel_left) + abs(rel_right)) / 2.0
            actual_rotation = (final_ticks / self.session_pulses_per_degree) * direction
            error = target_degrees - actual_rotation
            
            print(f"  After correction: actual={actual_rotation:+.1f}°, error={error:+.1f}°")
            
            if abs(error) <= self.rotation_tolerance:
                print("✅ Turn corrected successfully")
                return True
        
        print(f"❌ Turn correction failed after {self.max_correction_attempts} attempts")
        return False
    
    def test_tolerance_logic(self, target_degrees, actual_degrees):
        """Test tolerance logic with specific values"""
        error = target_degrees - actual_degrees
        success = abs(error) <= self.rotation_tolerance
        
        print(f"Tolerance Test:")
        print(f"  Target: {target_degrees:+.1f}°")
        print(f"  Actual: {actual_degrees:+.1f}°")
        print(f"  Error: {error:+.1f}°")
        print(f"  Tolerance: ±{self.rotation_tolerance:.1f}°")
        print(f"  Check: |{error:.1f}| <= {self.rotation_tolerance:.1f} = {success}")
        print(f"  Result: {'✅ Within tolerance' if success else '❌ Outside tolerance'}")
        
        return success
    
    def correct_turn_error(self, error_degrees, max_corrections=2):
        """Attempt to correct turn error by making small adjustment turns"""
        if abs(error_degrees) < 0.5:  # Don't correct very small errors
            return True
            
        print(f"Correcting {error_degrees:+.1f}° error...")
        
        # Calculate correction angle (opposite of error)
        correction_angle = -error_degrees
        
        # Limit correction to reasonable amount
        max_correction = 10.0  # degrees
        if abs(correction_angle) > max_correction:
            correction_angle = max_correction if correction_angle > 0 else -max_correction
            print(f"Limiting correction to {correction_angle:+.1f}°")
        
        # Use slower speed for corrections
        original_speed = self.turn_speed
        self.turn_speed = max(8, self.turn_speed // 2)  # Half speed for corrections
        
        try:
            # Make correction turn
            correction_ticks = max(1, int(round(abs(correction_angle) * self.session_pulses_per_degree)))
            
            # Determine correction direction
            if correction_angle > 0:
                left_speed = self.turn_speed
                right_speed = -self.turn_speed
                direction_text = "right"
            else:
                left_speed = -self.turn_speed
                right_speed = self.turn_speed
                direction_text = "left"
            
            print(f"Correction: {correction_angle:+.1f}° {direction_text} ({correction_ticks} ticks)")
            
            # Set new reference point for correction
            self.reset_encoder_reference()
            
            # Start correction motors
            send_motor(left_speed, right_speed)
            
            # Monitor correction progress
            start_time = time.time()
            max_correction_time = 3.0  # Shorter timeout for corrections
            
            while time.time() - start_time < max_correction_time:
                rel_left, rel_right = self.get_relative_position()
                
                # Calculate current correction ticks using weighted average
                from advanced import MOTOR_FACTOR_LEFT, MOTOR_FACTOR_RIGHT
                left_weight = MOTOR_FACTOR_LEFT
                right_weight = MOTOR_FACTOR_RIGHT
                total_weight = left_weight + right_weight
                current_ticks = (abs(rel_left) * left_weight + abs(rel_right) * right_weight) / total_weight
                
                # Check if correction is complete
                if current_ticks >= correction_ticks:
                    stop_motors()
                    break
                    
                time.sleep(0.05)  # 20Hz monitoring
            else:
                # Timeout - stop motors
                stop_motors()
            
            time.sleep(0.2)  # Brief pause to let everything settle
            
            # Measure final correction results
            rel_left, rel_right = self.get_relative_position()
            final_ticks = (abs(rel_left) * left_weight + abs(rel_right) * right_weight) / total_weight
            actual_correction = final_ticks / self.session_pulses_per_degree
            if correction_angle < 0:
                actual_correction = -actual_correction
                
            correction_error = correction_angle - actual_correction
            
            print(f"Correction results:")
            print(f"  Target correction: {correction_angle:+.1f}°")
            print(f"  Actual correction: {actual_correction:+.1f}°")
            print(f"  Correction error: {correction_error:+.1f}°")
            
            # Check if correction was successful
            correction_success = abs(correction_error) <= self.rotation_tolerance
            return correction_success
            
        finally:
            # Restore original turn speed
            self.turn_speed = original_speed
    
    def move_distance(self, target_cm):
        """Move the robot using hardware encoder-based movement."""
        if abs(target_cm) < 0.1:
            print("No significant movement requested.")
            return True

        print(f"Moving {target_cm:+.1f} cm using hardware encoder control...")

        target_ticks = int(round(abs(target_cm) * self.session_pulses_per_cm))
        direction = 1 if target_cm > 0 else -1
        direction_text = "forward" if direction > 0 else "backward"

        print(f"Target ticks: {target_ticks} (for {abs(target_cm):.1f} cm)")
        print(f"Moving {direction_text} at speed {self.move_speed}")
        print(f"Using session_pulses_per_cm: {self.session_pulses_per_cm:.3f}")

        # Reset encoder reference to measure actual movement
        self.reset_encoder_reference()
        time.sleep(0.1)

        # Use hardware move_by_ticks for precise encoder-based movement
        left_ticks = direction * target_ticks
        right_ticks = direction * target_ticks
        left_speed = direction * self.move_speed
        right_speed = direction * self.move_speed

        move_by_ticks(left_ticks, right_ticks, left_speed, right_speed)

        # Wait for movement to complete (ESP32 handles the control loop)
        start_time = time.time()
        last_check_ticks = 0.0
        stall_count = 0

        while time.time() - start_time < self.max_move_time:
            rel_left, rel_right = self.get_relative_position()
            avg_ticks = (abs(rel_left) + abs(rel_right)) / 2.0

            # Check if we've reached target (with small tolerance)
            if avg_ticks >= target_ticks - 10:
                time.sleep(0.2)  # Let it settle
                break

            # Stall detection
            if abs(avg_ticks - last_check_ticks) < 5:
                stall_count += 1
                if stall_count > 10:  # 0.5 seconds of no progress
                    print("⚠️ Movement appears stalled")
                    break
            else:
                stall_count = 0

            last_check_ticks = avg_ticks
            time.sleep(0.05)
        else:
            print("⚠️ Movement timeout reached")

        stop_motors()
        time.sleep(0.2)

        # Measure final result
        rel_left, rel_right = self.get_relative_position()
        final_ticks = (abs(rel_left) + abs(rel_right)) / 2.0
        actual_distance = (final_ticks / self.session_pulses_per_cm) * direction

        error = target_cm - actual_distance

        print("Movement results:")
        print(f"  Target: {target_cm:+.1f} cm ({target_ticks} ticks)")
        print(f"  Actual: {actual_distance:+.1f} cm ({final_ticks:.0f} ticks)")
        print(f"  Error: {error:+.1f} cm")
        print(f"  Encoder deltas: left={rel_left}, right={rel_right}")
        print(f"  Left wheel: {abs(rel_left) / self.session_pulses_per_cm:.1f} cm")
        print(f"  Right wheel: {abs(rel_right) / self.session_pulses_per_cm:.1f} cm")

        success = abs(error) <= self.distance_tolerance
        if success:
            print("✅ Movement completed within tolerance")
            return True
        
        # Error correction if enabled
        if not self.enable_error_correction:
            print("⚠️ Movement completed but outside tolerance (correction disabled)")
            return False
        
        print(f"⚠️ Movement error {error:+.1f} cm exceeds tolerance, attempting correction...")
        
        # Try up to max_correction_attempts to get within tolerance
        for attempt in range(self.max_correction_attempts):
            correction_cm = error  # Move the error distance (positive = forward, negative = backward)
            
            # Don't correct if error is tiny
            if abs(correction_cm) < 0.5:
                print("✅ Error correction converged")
                return True
            
            print(f"  Correction attempt {attempt + 1}/{self.max_correction_attempts}: adjusting {correction_cm:+.1f} cm")
            
            # Make corrective move (recursive call with correction disabled to avoid infinite loop)
            saved_correction_flag = self.enable_error_correction
            self.enable_error_correction = False
            
            correction_success = self.move_distance(correction_cm)
            
            self.enable_error_correction = saved_correction_flag
            
            if not correction_success:
                print("❌ Correction move failed")
                return False
            
            # Measure total distance from original reference
            rel_left, rel_right = self.get_relative_position()
            final_ticks = (abs(rel_left) + abs(rel_right)) / 2.0
            actual_distance = (final_ticks / self.session_pulses_per_cm) * direction
            error = target_cm - actual_distance
            
            print(f"  After correction: actual={actual_distance:+.1f} cm, error={error:+.1f} cm")
            
            if abs(error) <= self.distance_tolerance:
                print("✅ Movement corrected successfully")
                return True
        
        print(f"❌ Movement correction failed after {self.max_correction_attempts} attempts")
        return False
    
    def execute_command(self, rotation_degrees, movement_cm):
        """Execute a rotation followed by movement command"""
        print(f"\n=== EXECUTING COMMAND ===")
        print(f"Rotation: {rotation_degrees:+.1f} degrees")
        print(f"Movement: {movement_cm:+.1f} cm")
        print("=" * 30)
        
        # Test ESP32 connection first
        if not self.test_esp32_connection():
            # If connection test fails, try waiting for data
            print("\n⏳ Waiting for ESP32 data...")
            if not wait_for_encoder_data():
                print("❌ No encoder data available")
                return False
        
        success = True
        
        # Step 1: Rotation
        if rotation_degrees != 0:
            if not self.turn_to_angle(rotation_degrees):
                print("❌ Rotation failed")
                success = False
            else:
                print("✅ Rotation successful")
                time.sleep(0.5)  # Brief pause between operations
        
        # Step 2: Movement
        if movement_cm != 0 and success:
            if not self.move_distance(movement_cm):
                print("❌ Movement failed")
                success = False
            else:
                print("✅ Movement successful")
        
        # Final stop
        stop_motors()
        
        if success:
            print("\n🎉 Command completed successfully!")
        else:
            print("\n⚠️ Command completed with errors")
        
        return success

def interactive_mode(controller):
    """Interactive mode for continuous commands"""
    
    print("=== ENCODER-BASED ROBOT MOVEMENT CONTROL ===")
    print("Pure encoder navigation system")
    print("Commands:")
    print("  rotation, movement  - Execute movement (e.g., '90, 100')")
    print("  config              - Show current configuration")
    print("  tolerance X, Y      - Set rotation tolerance (X°) and distance tolerance (Y cm)")
    print("  speed X, Y          - Set turn speed (X) and move speed (Y)")
    print("  timeout X, Y        - Set turn timeout (X sec) and move timeout (Y sec)")
    print("  encoders            - Show current encoder values")
    print("Examples:")
    print("  90, 100             - Turn 90° left, move 100cm forward")
    print("  -45, -50            - Turn 45° right, move 50cm backward")
    print("  tolerance 2, 1      - Set ±2° rotation tolerance, ±1cm distance tolerance")
    print("  speed 40, 30        - Set turn speed 40, move speed 30")
    print("Type 'quit' or 'q' to exit")
    print()
    
    # Show initial configuration
    controller.show_configuration()
    
    while True:
        try:
            user_input = input("\nEnter command: ").strip()
            
            if user_input.lower() in ('q', 'quit', 'exit'):
                print("Exiting...")
                break
            
            if user_input.lower() == 'config':
                controller.show_configuration()
                continue
            
            if user_input.lower() == 'encoders':
                encoders, enc_time = get_latest_encoders()
                print(f"\n=== CURRENT ENCODER VALUES ===")
                print(f"m1 (left): {encoders['m1']}")
                print(f"m2 (right): {encoders['m2']}")
                print(f"m3: {encoders['m3']}")
                print(f"m4: {encoders['m4']}")
                print(f"Timestamp: {enc_time}")
                print("=" * 30)
                continue
            
            if user_input.lower().startswith('tolerance '):
                # Parse tolerance command
                parts = user_input[10:].split(',')
                if len(parts) == 2:
                    rot_tol = float(parts[0].strip())
                    dist_tol = float(parts[1].strip())
                    controller.configure_tolerances(rot_tol, dist_tol)
                else:
                    print("Usage: tolerance rotation_degrees, distance_cm")
                continue
            
            if user_input.lower().startswith('speed '):
                # Parse speed command
                parts = user_input[6:].split(',')
                if len(parts) == 2:
                    turn_speed = int(parts[0].strip())
                    move_speed = int(parts[1].strip())
                    controller.configure_speeds(turn_speed, move_speed)
                else:
                    print("Usage: speed turn_speed, move_speed")
                continue
            
            if user_input.lower().startswith('timeout '):
                # Parse timeout command
                parts = user_input[8:].split(',')
                if len(parts) == 2:
                    turn_timeout = float(parts[0].strip())
                    move_timeout = float(parts[1].strip())
                    controller.configure_timeouts(turn_timeout, move_timeout)
                else:
                    print("Usage: timeout turn_seconds, move_seconds")
                continue
            
            if ',' not in user_input:
                print("Please enter movement command (rotation, movement) or configuration command")
                print("Type 'config' to see current settings")
                continue
            
            # Parse movement command
            parts = user_input.split(',')
            if len(parts) != 2:
                print("Please enter exactly two values: rotation, movement")
                continue
            
            rotation = float(parts[0].strip())
            movement = float(parts[1].strip())
            
            # Execute command
            controller.execute_command(rotation, movement)
            
            # Wait for user before next command
            input("\nPress Enter to continue or Ctrl+C to exit...")
            
        except ValueError:
            print("Please enter valid numbers")
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")

def command_line_mode(controller):
    """Command line mode for single commands"""
    if len(sys.argv) != 3:
        print("Usage: python move_control.py <rotation_degrees> <movement_cm>")
        print("Example: python move_control.py 90 100")
        return False
    
    try:
        rotation = float(sys.argv[1])
        movement = float(sys.argv[2])
        
        return controller.execute_command(rotation, movement)
        
    except ValueError:
        print("Error: Please provide valid numbers for rotation and movement")
        return False

def main():
    try:
        # Initialize robot control system
        print("Initializing robot control system...")
        init_bot_control(verbose_telemetry=False)  # Enable verbose to see what's happening
        
        # Give more time for telemetry to start and receive data
        print("Waiting for ESP32 connection and telemetry data...")
        time.sleep(5)  # Increased from 2 to 5 seconds
        
        # Test connection before proceeding
        controller = RobotController()
        print("\n" + "="*50)
        print("🤖 ROBOT CONTROL SYSTEM")
        print("="*50)
        
        if not controller.test_esp32_connection():
            print("\n⚠️ ESP32 connection issues detected!")
            print("Please check:")
            print("1. ESP32 is powered on")
            print("2. Connected to 'ESP32-FruitBot' WiFi")
            print("3. ESP32 firmware uploaded correctly")
            print("\nTrying to continue anyway...")
        
        # Check if command line arguments were provided
        if len(sys.argv) == 3:
            # Command line mode
            success = command_line_mode(controller)
            sys.exit(0 if success else 1)
        else:
            # Interactive mode
            interactive_mode(controller)
            
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cleanup()

if __name__ == '__main__':
    main()
