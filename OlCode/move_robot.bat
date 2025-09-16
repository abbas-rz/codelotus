@echo off
REM Batch script to run robot movement control
echo Robot Movement Control
echo ====================

if "%1"=="" (
    echo Interactive mode - no arguments provided
    c:\Users\abbas\code\UHFC\trans\.ven\Scripts\python.exe c:\Users\abbas\code\UHFC\trans\move_control.py
) else if "%2"=="" (
    echo Error: Please provide both rotation and movement values
    echo Usage: move_robot.bat [rotation_degrees] [movement_cm]
    echo Example: move_robot.bat 90 100
    pause
) else (
    echo Command mode: Rotation=%1 degrees, Movement=%2 cm
    c:\Users\abbas\code\UHFC\trans\.ven\Scripts\python.exe c:\Users\abbas\code\UHFC\trans\move_control.py %1 %2
    pause
)
