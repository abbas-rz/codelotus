# IHFC Prep Suite (2025)

A small, focused toolkit to plan, visualize, and execute paths for our ITU IHFC Bot 2025. It includes:

- A Pygame-CE arena measurement tool to design paths and export commands.
- A pure-pursuit-style follower that runs those paths on the robot.
- A live telemetry UI to visualize sensors and progress over the arena map.

All tools assume an arena sized 118 cm (W) x 114 cm (H) and share the same coordinate and heading conventions.

## Contents

- `measure_arena.py` — Design paths over `arena.png`, measure distances/angles, export CSVs.
- `move_control_pure_pursuit.py` — Follows exported checkpoints on the robot (turn-then-go steps).
- `telemetry_ui.py` — Live dashboard: highlights current segment, shows LIDAR/IMU and estimated position.
- `advanced.py` — Robot control + telemetry plumbing (motors, gyro integration, LIDAR feed).
- `arena.png` — The arena illustration (physical 118 cm x 114 cm).

## Quick start

Requirements:
- Python 3.9+ (Windows recommended)
- pygame-ce

Install dependency (once):

```powershell
uv pip install pygame-ce
```

### 1) Plan your path (desktop)

```powershell
python .\measure_arena.py
```

Controls (measurement tool):
- Left click: add checkpoint (polyline)
- Right click: undo last checkpoint
- Shift: snap to 45° increments (preview and on add)
- G: toggle 10 cm grid
- H: toggle help panel
- F: toggle fullscreen
- C: clear checkpoints
- Enter: print path and save CSVs
	- `path.csv`: turn_deg, distance_cm
	- `checkpoints_cm.csv`: x_cm, y_cm (origin at top-left, y increases down)
- Esc or Q: quit

Notes
- Angles: 0° points up (toward negative Y). First segment’s turn is relative to current facing when run on the robot (gyro reset), not absolute up.
- Scale: Pixels-per-cm derived from image size vs 118×114 cm. If the PNG’s aspect ratio differs, X/Y scales are handled anisotropically; a warning is shown.

### 2) Run it on the robot

Ensure `advanced.py` is configured for your robot IP and telemetry is flowing.

Follow the exported checkpoints:

```powershell
python .\move_control_pure_pursuit.py run
```

Behavior
- Uses `checkpoints_cm.csv` to compute relative turn and segment distances.
- Resets the gyro before the first turn so the robot’s current facing becomes 0°.
- Performs each segment as: relative turn → forward move (with simple tolerances/timeouts).

### 3) Visualize telemetry (desktop)

```powershell
python .\telemetry_ui.py
```

What you’ll see
- Arena image with the full path; current segment highlighted.
- Estimated robot position along the current segment based on LIDAR delta.
- Live IMU (accel/gyro/heading/temperature) and relative rotation from `advanced.py`.
- LIDAR distance and freshness.

Controls (telemetry UI)
- R: reload `path.csv` and `checkpoints_cm.csv`
- A: toggle auto-tracking of the current segment
- [ and ]: manual segment index (when auto-tracking is off)
- Esc or Q: quit

## Coordinate & heading conventions

- Arena size: 118 cm wide (X), 114 cm tall (Y).
- Origin: top-left of `arena.png`.
- +X to the right, +Y downward.
- Heading: 0° = up (toward negative Y), 90° = right, 180° = down, 270° = left.
- Robot follower: at start, the current facing is taken as 0° by resetting gyro; first turn uses relative angle from that heading.

## Data formats

- `path.csv`
	- Columns: `turn_deg`, `distance_cm`
	- Turn is relative to the previous segment; the first turn is relative to initial facing.
- `checkpoints_cm.csv`
	- Columns: `x_cm`, `y_cm`
	- Coordinates in centimeters using the arena conventions above.

## Troubleshooting

- “No telemetry” or stale LIDAR/IMU: check `advanced.py` network config (IP/ports) and ensure the Pi is streaming.
- PNG aspect ratio mismatch: tool warns and compensates; distances remain correct using different X/Y scales.
- Window doesn’t open or `convert_alpha` error: ensure a display mode exists (we convert after `set_mode`).

## Roadmap

- Encoder integration and odometry overlay in telemetry UI.
- True continuous pure pursuit (lookahead curvature) in addition to turn-then-go.
- Export/import of multiple named paths.

## License

Internal project code for IHFC Bot 2025. If you plan to reuse externally, please add a license file appropriate for your needs.
