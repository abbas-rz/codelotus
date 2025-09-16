# UHFC Autonomous Bot Control System

This repository contains a complete autonomous navigation system for a bot with LIDAR sensor, camera vision, and motor control.

## 🏗️ Architecture Overview

### Core Library
- **`advanced.py`** - Main reusable library containing all bot control functions
  - Motor control (differential steering, speed control)
  - LIDAR telemetry handling
  - Gear system for speed management
  - Navigation helper functions
  - Cleanup and initialization

### Main Programs
- **`autonomous_rc.py`** - Original enhanced RC control with autonomous mode
- **`vision_autonomous.py`** - Complete vision-integrated autonomous system
- **`vision_modular.py`** - New modular vision system using advanced.py library

### Testing & Examples
- **`test_advanced.py`** - Comprehensive test suite for advanced.py library
- **`test_vision.py`** - Vision system testing and calibration
- **`bot_control_example.py`** - Basic usage examples for advanced.py
- **`autonomous_rc_modular.py`** - Modular autonomous system using advanced.py
- **`motor_config_examples.py`** - Motor configuration examples

### Legacy Files
- **`main.py`** - Original basic bot control
- **`rc_cont.py`** - Basic RC control
- **`sim.py`** - Simulation/testing utilities
- **`lidar_getter.py`** - LIDAR data utilities
- **`lidar_monitor.py`** - LIDAR monitoring

## 🚀 Quick Start

### 1. Test Your Setup
```bash
python test_advanced.py
```
This will test all bot functions and help you verify your hardware setup.

### 2. Basic Manual Control
```bash
python bot_control_example.py
```
Simple WASD control to verify motor operation.

### 3. Autonomous Navigation
```bash
python autonomous_rc_modular.py
```
Full autonomous mode with obstacle avoidance.

### 4. Vision-Guided Control
```bash
python vision_modular.py
```
Complete system with red object tracking and obstacle avoidance.

## ⚙️ Configuration

### Motor Setup
Different motors may need different speed limits. Configure in your script:
```python
# For different RPM motors
MOTOR_MAX_LEFT = 100   # Left motor max speed
MOTOR_MAX_RIGHT = 85   # Right motor max speed (if slower)
```

### LIDAR Setup
- **Port**: 9001 (UDP)
- **Data Format**: JSON with distance field
- **Update Rate**: ~10Hz recommended

### Camera Setup
- **Port**: 5000 (UDP H.264 stream)
- **Resolution**: 640x480
- **Format**: H.264 via GStreamer

### Vision Parameters
Adjust red detection sensitivity:
```python
RED_LOWER = np.array([0, 50, 50])      # Lower HSV bound
RED_UPPER = np.array([10, 255, 255])   # Upper HSV bound
MIN_CONTOUR_AREA = 500                 # Minimum object size
```

## 🎮 Controls

### Manual Mode
- **WASD** - Movement (forward/back/left/right)
- **Shift** - Crawl mode (slow, precise movement)
- **Ctrl** - Gear up (faster movement)
- **ESC** - Toggle autonomous mode

### Autonomous Mode
- **ESC** - Return to manual mode
- **V** or **Space** - Toggle vision mode
- **Q** - Quit program

## 🧠 Features

### Obstacle Avoidance
- LIDAR-based distance sensing
- Graduated speed reduction as obstacles approach
- Emergency stop at minimum distance (25cm)

### Vision System
- HSV-based red object detection
- Priority system: Safety > Vision > Exploration
- Gentle steering towards targets
- Approach distance control

### Gear System
- 4-speed transmission (0-3)
- Crawl mode for precise control
- Speed scaling based on gear selection

### Modular Design
- All core functions in `advanced.py` library
- Easy to import and reuse across projects
- Consistent API across all programs

## 🔧 Hardware Requirements

### Essential
- Bot with differential drive motors
- TF Luna LIDAR sensor
- WiFi/Network connection for UDP communication

### Optional
- Camera with H.264 streaming capability
- RGB LED for status indication

## 📡 Communication Protocol

### Motor Commands (Port 9000)
```json
{"left": 50, "right": 50}  // Motor speeds (-100 to 100)
```

### LIDAR Telemetry (Port 9001)
```json
{"distance": 123.45}  // Distance in centimeters
```

### Camera Stream (Port 5000)
- H.264 video stream via UDP
- Compatible with GStreamer pipeline

## 🐛 Troubleshooting

### Common Issues

**No LIDAR Data**
- Check UDP port 9001 is receiving data
- Verify JSON format matches expected structure
- Run `test_advanced.py` telemetry test

**Motors Not Responding**
- Check UDP port 9000 is reachable
- Verify motor command format
- Test with `bot_control_example.py`

**Vision Not Working**
- Check camera stream on port 5000
- Verify GStreamer installation
- Test HSV ranges with `test_vision.py`

**Bot Spinning/Unstable**
- Adjust `MOTOR_MAX_LEFT` and `MOTOR_MAX_RIGHT` for motor differences
- Check gear ratios and wheel alignment
- Reduce turning speeds in configuration

## 📈 Development

### Adding New Features
1. Add core functions to `advanced.py`
2. Update `test_advanced.py` with new tests
3. Create example usage in separate script
4. Update this README

### Testing Protocol
1. Run `test_advanced.py` after any changes
2. Test with real hardware before committing
3. Verify all existing programs still work

## 📝 Version History

- **v1.0** - Basic autonomous navigation
- **v1.1** - Enhanced turning behavior and speed control
- **v1.2** - Vision integration with red object tracking
- **v1.3** - Differential motor support
- **v2.0** - Modular architecture with advanced.py library

## 🤝 Contributing

When modifying the code:
1. Keep `advanced.py` as the central library
2. Add comprehensive tests for new features
3. Update documentation and examples
4. Test with real hardware when possible

## 📄 License

This project is designed for educational and research purposes in autonomous robotics.
