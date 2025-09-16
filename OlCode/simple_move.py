#!/usr/bin/env python3
"""
Simple Robot Move - Quick command execution
Usage: python simple_move.py
"""
from move_control import RobotController
from advanced import init_bot_control, cleanup
import time

def quick_move():
    """Quick move function for simple commands"""
    print("=== SIMPLE ROBOT MOVE ===")
    print("Quick command input")
    
    try:
        # Get user input
        rotation = float(input("Enter rotation in degrees (+left/-right): "))
        movement = float(input("Enter movement in cm (+forward/-backward): "))
        
        # Initialize and execute
        print("\nInitializing robot...")
        init_bot_control(verbose_telemetry=False)
        time.sleep(2)
        
        controller = RobotController()
        success = controller.execute_command(rotation, movement)
        
        if success:
            print("\n✅ Command completed successfully!")
        else:
            print("\n❌ Command failed!")
            
    except ValueError:
        print("Error: Please enter valid numbers")
    except KeyboardInterrupt:
        print("\nCancelled by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cleanup()

if __name__ == '__main__':
    quick_move()
