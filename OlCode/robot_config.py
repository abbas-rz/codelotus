#!/usr/bin/env python3
"""
Robot Configuration Tool
Quick configuration for robot movement tolerances and settings
"""
from move_control import RobotController

def main():
    print("=== ROBOT CONFIGURATION TOOL ===")
    print("Configure robot movement parameters")
    print()
    
    controller = RobotController()
    controller.show_configuration()
    
    while True:
        print("\nConfiguration Options:")
        print("1. Set rotation tolerance (degrees)")
        print("2. Set distance tolerance (cm)")
        print("3. Set motor speeds")
        print("4. Set timeouts")
        print("5. Show current configuration")
        print("6. Test with sample values")
        print("0. Exit")
        
        try:
            choice = input("\nEnter choice (0-6): ").strip()
            
            if choice == '0':
                print("Configuration saved. Exiting...")
                break
            
            elif choice == '1':
                current = controller.rotation_tolerance
                new_val = input(f"Enter rotation tolerance in degrees (current: {current}): ").strip()
                if new_val:
                    controller.configure_tolerances(rotation_tolerance=float(new_val))
            
            elif choice == '2':
                current = controller.distance_tolerance
                new_val = input(f"Enter distance tolerance in cm (current: {current}): ").strip()
                if new_val:
                    controller.configure_tolerances(distance_tolerance=float(new_val))
            
            elif choice == '3':
                print(f"Current speeds - Turn: {controller.turn_speed}, Move: {controller.move_speed}")
                turn_speed = input("Enter turn speed (5-120): ").strip()
                move_speed = input("Enter move speed (5-120): ").strip()
                if turn_speed and move_speed:
                    controller.configure_speeds(int(turn_speed), int(move_speed))
            
            elif choice == '4':
                print(f"Current timeouts - Turn: {controller.max_turn_time}s, Move: {controller.max_move_time}s")
                turn_timeout = input("Enter turn timeout (seconds): ").strip()
                move_timeout = input("Enter move timeout (seconds): ").strip()
                if turn_timeout and move_timeout:
                    controller.configure_timeouts(float(turn_timeout), float(move_timeout))
            
            elif choice == '5':
                controller.show_configuration()
            
            elif choice == '6':
                print("\nRecommended settings based on robot type:")
                print("Precise robot:     tolerance 2, 1   speed 15, 10")
                print("Standard robot:    tolerance 5, 2   speed 25, 15")
                print("Fast/rough robot:  tolerance 10, 5  speed 40, 30")
                
                preset = input("Apply preset? (precise/standard/fast/none): ").strip().lower()
                if preset == 'precise':
                    controller.configure_tolerances(2.0, 1.0)
                    controller.configure_speeds(15, 10)
                elif preset == 'standard':
                    controller.configure_tolerances(5.0, 2.0)
                    controller.configure_speeds(25, 15)
                elif preset == 'fast':
                    controller.configure_tolerances(10.0, 5.0)
                    controller.configure_speeds(40, 30)
            
            else:
                print("Invalid choice. Please enter 0-6.")
        
        except ValueError:
            print("Please enter valid numbers.")
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == '__main__':
    main()
