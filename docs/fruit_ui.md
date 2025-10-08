# fruit_ui.py — Fruit layout & tagging UI

Purpose
-------
`fruit_ui.py` is a small Pygame-based utility for visualising the arena and tagging fruit positions by color. It overlays a known grid of 2×2 cm squares used in the competition and outputs legacy CSVs (`red.csv`, `black.csv`) along with a modern `fruit_config.json` mapping.

When to use
-----------
- During setup to mark fruit positions and export colour-tagged lists for autonomous routines.
- To create or verify fruit layouts before a run.

How it works
------------
- Loads `arena.png` from the repository root and fits it to the current window.
- Uses precise arena dimensions (118.1 × 114.3 cm) to convert between pixels and centimetres.
- Presents two columns of six fruit positions by default; positions can be adjusted by editing constants at the top of the file.

Controls
--------
- R: enter red-tagging mode — click a square to mark it red and save to `red.csv`.
- B: enter black-tagging mode — click a square to mark it black and save to `black.csv`.
- G: toggle 10 cm grid overlay.
- H: toggle help HUD.
- Click on UI buttons to set Start / End points and create an automatic path (uses `path_planner.py`).
- Esc / Q: quit.

Outputs
-------
- `red.csv` / `black.csv`: legacy CSVs containing the centre coordinates (x_cm, y_cm).
- `fruit_config.json`: a JSON mapping with both legacy and newer key formats (e.g. `Fruit1`, `Fruit_1_1`) that other tools can consume.

Notes & tips
------------
- The UI persists both legacy CSVs and the JSON mapping to ease compatibility with older tools.
- If the arena image uses a different pixel aspect ratio, the tool keeps separate px/cm values for X and Y to avoid distortion.
- To change positions or spacing, edit `TOP_Y_CM`, `SPACING_CM_DEFAULT`, and `OFFSETS_FROM_RIGHT_CM` near the top of the file.

Example
-------
Run the UI:

```powershell
python .\fruit_ui.py
```

Then press `R` to tag red fruits and click the squares.
