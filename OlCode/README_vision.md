# Vision-Integrated Autonomous Bot

This system combines computer vision for red object tracking with LIDAR-based obstacle avoidance for autonomous navigation.

## Features

- **Red Object Detection**: Detects red squares, cubes, circles with high tolerance
- **Vision-Guided Navigation**: Turns and moves toward detected red objects
- **Obstacle Avoidance**: Uses LIDAR to avoid collisions while pursuing targets
- **Multiple Modes**: Manual, Autonomous, and Vision-guided modes
- **Real-time Processing**: ~20 FPS vision processing with GStreamer

## Requirements

- Python 3.x
- OpenCV (`pip install opencv-python`)
- NumPy (`pip install numpy`)
- pynput (`pip install pynput`)
- GStreamer (for camera feed)

## Setup

1. **Start Camera Stream**:
   ```bash
   # Run the GStreamer pipeline (or use streamcode.bat)
   gst-launch-1.0 udpsrc port=5000 caps="application/x-rtp,encoding-name=H264,payload=96" ! rtph264depay ! avdec_h264 ! autovideosink sync=false
   ```

2. **Test Vision System**:
   ```bash
   python test_vision.py
   ```

3. **Run Vision-Integrated Bot**:
   ```bash
   python vision_autonomous.py
   ```

## Usage

### Manual Mode (Default)
- **WASD**: Movement control
- **Shift**: Gear down / Crawl mode
- **Ctrl**: Gear up
- **Q**: Quit

### Autonomous Mode
- **ESC**: Toggle autonomous mode
- **V**: Toggle vision mode (tracks red objects)

### Vision Mode Behavior
1. **Target Search**: Moves forward slowly while scanning for red objects
2. **Target Tracking**: Steers toward detected red objects
3. **Obstacle Avoidance**: Stops and finds clear path when obstacles detected
4. **Target Approach**: Approaches red objects until close enough

## Configuration

### Vision Parameters (in vision_autonomous.py)
```python
# Red color detection (HSV)
RED_LOWER = np.array([0, 50, 50])     # Lower threshold
RED_UPPER = np.array([10, 255, 255])  # Upper threshold
RED_LOWER2 = np.array([170, 50, 50])  # Second range (hue wrapping)
RED_UPPER2 = np.array([180, 255, 255])

# Detection sensitivity
MIN_CONTOUR_AREA = 500                # Minimum object size
VISION_TURN_THRESHOLD = 50            # Pixels from center to trigger turning
VISION_TARGET_SIZE = 5000             # Target size to stop approaching
```

### Autonomous Parameters
```python
MIN_DISTANCE = 25    # cm - stop distance for obstacles
TURN_DISTANCE = 40   # cm - slow down distance
SAFE_DISTANCE = 60   # cm - full speed distance
```

## System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Camera Feed   │────│  Vision System   │────│ Navigation Logic │
│  (GStreamer)    │    │ (Red Detection)  │    │   (Steering)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
┌─────────────────┐    ┌──────────────────┐             │
│  LIDAR Sensor   │────│ Obstacle Avoid.  │─────────────┤
│   (TF Luna)     │    │    (Safety)      │             │
└─────────────────┘    └──────────────────┘             │
                                                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  User Input     │────│  Control Loop    │────│  Motor Control  │
│ (Keyboard)      │    │  (Mode Switch)   │    │  (UDP Commands) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Priority System

1. **Safety First**: LIDAR obstacle avoidance always takes priority
2. **Vision Guidance**: When clear path exists, steer toward red objects
3. **Exploration**: When no targets visible, continue autonomous navigation

## Troubleshooting

### Camera Issues
- Ensure GStreamer pipeline is running
- Check port 5000 is not blocked
- Verify camera stream format (H.264)

### Vision Detection Issues
- Adjust HSV color ranges for your lighting
- Modify `MIN_CONTOUR_AREA` for object size sensitivity
- Use `test_vision.py` to debug detection

### Navigation Issues
- Check LIDAR data reception
- Verify motor command UDP connectivity
- Adjust distance thresholds for your environment

## Files

- `vision_autonomous.py` - Main vision-integrated autonomous system
- `test_vision.py` - Vision system test and calibration tool
- `autonomous_rc.py` - Original autonomous system (no vision)
- `streamcode.bat` - GStreamer camera stream command
