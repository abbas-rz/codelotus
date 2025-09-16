#!/usr/bin/env python3
# test_autonomous.py - Test the autonomous navigation algorithm
import time
import json

def test_gear_calculation():
    """Test the gear calculation logic"""
    print("=== Testing Gear Calculation ===")
    
    # Import the functions from autonomous module
    import sys
    sys.path.append('.')
    from autonomous import calculate_gear_from_distance, calculate_speed_from_distance
    
    test_distances = [10, 25, 35, 55, 75, 120, 200]
    
    for distance in test_distances:
        gear = calculate_gear_from_distance(distance)
        speed = calculate_speed_from_distance(distance)
        print(f"Distance: {distance:3d} cm -> Gear: {gear+1}, Speed: {speed:3d}")

def simulate_autonomous_behavior():
    """Simulate autonomous behavior with different scenarios"""
    print("\n=== Simulating Autonomous Behavior ===")
    
    # Scenario 1: Clear path ahead
    print("\nScenario 1: Clear path (150 cm)")
    distance = 150
    gear = calculate_gear_from_distance(distance)
    speed = calculate_speed_from_distance(distance)
    print(f"Action: Move forward at gear {gear+1}, speed {speed}")
    
    # Scenario 2: Approaching obstacle
    print("\nScenario 2: Approaching obstacle (60 cm)")
    distance = 60
    gear = calculate_gear_from_distance(distance)
    speed = calculate_speed_from_distance(distance)
    print(f"Action: Slow down to gear {gear+1}, speed {speed}")
    
    # Scenario 3: Obstacle close
    print("\nScenario 3: Close obstacle (25 cm)")
    distance = 25
    gear = calculate_gear_from_distance(distance)
    speed = calculate_speed_from_distance(distance)
    if speed == 0:
        print("Action: STOP and search for clear path")
    else:
        print(f"Action: Crawl at gear {gear+1}, speed {speed}")

def calculate_gear_from_distance(distance):
    """Calculate appropriate gear based on available space"""
    MIN_DISTANCE = 30
    TURN_DISTANCE = 50
    SAFE_DISTANCE = 100
    
    if distance < MIN_DISTANCE:
        return 0  # Stop
    elif distance < TURN_DISTANCE:
        return 0  # Lowest gear (crawl)
    elif distance < SAFE_DISTANCE:
        return 1  # Medium gear
    else:
        return 2  # High gear

def calculate_speed_from_distance(distance):
    """Calculate motor speed based on distance and gear"""
    MOTOR_MAX = 120
    GEAR_SCALES = [0.33, 0.66, 1.00]
    MIN_DISTANCE = 30
    TURN_DISTANCE = 50
    
    gear_idx = calculate_gear_from_distance(distance)
    
    if distance < MIN_DISTANCE:
        return 0  # Stop completely
    
    # Base speed from gear
    base_speed = MOTOR_MAX * GEAR_SCALES[gear_idx]
    
    # Additional modulation based on distance
    if distance < TURN_DISTANCE:
        # Gradually reduce speed as we get closer
        distance_factor = (distance - MIN_DISTANCE) / (TURN_DISTANCE - MIN_DISTANCE)
        distance_factor = max(0.2, distance_factor)  # Minimum 20% speed
        base_speed *= distance_factor
    
    return int(max(0, min(base_speed, MOTOR_MAX)))

if __name__ == '__main__':
    test_gear_calculation()
    simulate_autonomous_behavior()
    
    print("\n=== Test Complete ===")
    print("The autonomous algorithm will:")
    print("1. Stop when obstacles are closer than 30 cm")
    print("2. Use low gear (crawl) when obstacles are 30-50 cm away")
    print("3. Use medium gear when obstacles are 50-100 cm away")
    print("4. Use high gear when obstacles are >100 cm away")
    print("5. Turn to find clear paths when blocked")
    print("6. Modulate speed smoothly based on available space")
