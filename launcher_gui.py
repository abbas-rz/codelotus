#!/usr/bin/env python3
"""Simple GUI launcher for IHFC Prepsuite utilities.

Provides quick access to commonly used tools and displays the current
calibration values stored in ``robot_calibration.json``.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import Mapping, Sequence

from calibration_config import (
    load_config,
    save_pulses_per_cm,
    save_pulses_per_degree,
)

BASE_DIR = Path(__file__).resolve().parent

# Utility definitions: title, description, relative script path, optional args
UTILITIES: Sequence[Mapping[str, object]] = (
    {
        "title": "Manual Control (advanced.py)",
        "description": "Keyboard-driven motor control interface.",
        "script": BASE_DIR / "advanced.py",
    },
    {
        "title": "Telemetry UI",
        "description": "Real-time arena telemetry viewer.",
        "script": BASE_DIR / "telemetry_ui.py",
    },
    {
        "title": "Fruit Layout UI",
        "description": "Tag fruit positions and update red/black CSVs.",
        "script": BASE_DIR / "fruit_ui.py",
    },
    {
        "title": "Measure Arena",
        "description": "Capture arena measurements and checkpoints.",
        "script": BASE_DIR / "measure_arena.py",
    },
)


class LauncherApp:
    """Tkinter application wrapper."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("IHFC Utility Launcher")
        self.root.geometry("640x380")

        # Use ttk themed widgets for a cleaner look
        self.style = ttk.Style(self.root)
        if "clam" in self.style.theme_names():
            self.style.theme_use("clam")

        self._build_layout()
        self.refresh_calibration()

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        main = ttk.Frame(self.root, padding=16)
        main.pack(fill=tk.BOTH, expand=True)

        util_frame = ttk.LabelFrame(main, text="Utilities", padding=(12, 10))
        util_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        utilities = list(UTILITIES)
        for idx, utility in enumerate(utilities):
            row = ttk.Frame(util_frame, padding=(0, 4))
            row.pack(fill=tk.X, expand=True, padx=4, pady=2)

            title = ttk.Label(row, text=utility["title"], font=("Segoe UI", 11, "bold"))
            title.pack(anchor=tk.W)

            desc = ttk.Label(row, text=utility["description"], font=("Segoe UI", 9))
            desc.pack(anchor=tk.W, padx=(12, 0))

            launch_btn = ttk.Button(
                row,
                text="Launch",
                command=lambda util=utility: self.launch_utility(util),
                width=16,
            )
            launch_btn.pack(anchor=tk.E, pady=(4, 2))

            if idx < len(utilities) - 1:
                ttk.Separator(util_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=4)

        side_frame = ttk.Frame(main, padding=(12, 0))
        side_frame.pack(fill=tk.Y, expand=False, side=tk.RIGHT)

        calib_frame = ttk.LabelFrame(side_frame, text="Calibration", padding=(10, 10))
        calib_frame.pack(fill=tk.X)

        self.ppd_var = tk.StringVar()
        self.ppcm_var = tk.StringVar()
        self.motor_factor_var = tk.StringVar()
        self.updated_var = tk.StringVar()

        ttk.Label(calib_frame, textvariable=self.ppd_var).pack(anchor=tk.W)
        ttk.Label(calib_frame, textvariable=self.ppcm_var).pack(anchor=tk.W, pady=(4, 0))
        ttk.Label(calib_frame, textvariable=self.motor_factor_var).pack(anchor=tk.W, pady=(4, 0))
        ttk.Label(
            calib_frame, textvariable=self.updated_var, font=("Segoe UI", 8, "italic")
        ).pack(anchor=tk.W, pady=(2, 0))

        button_bar = ttk.Frame(calib_frame)
        button_bar.pack(anchor=tk.W, pady=(8, 0))
        ttk.Button(
            button_bar,
            text="Set Pulses/°",
            command=self.update_pulses_per_degree,
            width=14,
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            button_bar, text="Set Pulses/cm", command=self.update_pulses_per_cm, width=14
        ).pack(side=tk.LEFT)

        ttk.Button(calib_frame, text="Refresh", command=self.refresh_calibration).pack(
            anchor=tk.W, pady=(6, 0)
        )
        ttk.Button(
            calib_frame,
            text="Straight-Line Calibrator",
            command=self.launch_straight_calibrator,
            width=24,
        ).pack(anchor=tk.W, pady=(6, 0))

        ttk.Button(
            side_frame,
            text="Open Calibration File",
            command=self.open_calibration_file,
            width=24,
        ).pack(anchor=tk.NW, pady=(20, 0))

    # ------------------------------------------------------------------
    # Calibration helpers
    # ------------------------------------------------------------------
    def refresh_calibration(self) -> None:
        config = load_config()
        ppd = config.get("pulses_per_degree")
        ppcm = config.get("pulses_per_cm")
        updated = config.get("updated_at") or "Unknown"

        try:
            ppd_text = f"Pulses/degree: {float(ppd):.3f}"
        except (TypeError, ValueError):
            ppd_text = "Pulses/degree: --"

        try:
            ppcm_text = f"Pulses/cm: {float(ppcm):.3f}"
        except (TypeError, ValueError):
            ppcm_text = "Pulses/cm: --"

        left_factor = config.get("motor_factor_left")
        right_factor = config.get("motor_factor_right")
        try:
            motor_factor_text = (
                f"Motor factors L/R: {float(left_factor):.3f} / {float(right_factor):.3f}"
            )
        except (TypeError, ValueError):
            motor_factor_text = "Motor factors L/R: -- / --"

        self.ppd_var.set(ppd_text)
        self.ppcm_var.set(ppcm_text)
        self.motor_factor_var.set(motor_factor_text)
        self.updated_var.set(f"Last updated: {updated}")

    def _prompt_calibration(
        self,
        title: str,
        prompt: str,
        min_value: float,
        initial_value: float | None = None,
    ) -> float | None:
        return simpledialog.askfloat(
            title,
            prompt,
            parent=self.root,
            minvalue=min_value,
            initialvalue=initial_value,
        )

    def update_pulses_per_degree(self) -> None:
        current = load_config().get("pulses_per_degree")
        value = self._prompt_calibration(
            "Set Pulses per Degree",
            "Enter the new pulses-per-degree value:",
            1.0,
            float(current) if isinstance(current, (int, float)) else None,
        )
        if value is None:
            return
        try:
            save_pulses_per_degree(value)
        except Exception as exc:  # pragma: no cover - GUI feedback only
            messagebox.showerror("Failed to save pulses-per-degree", str(exc))
            return
        self.refresh_calibration()
        messagebox.showinfo(
            "Calibration updated",
            f"Pulses per degree saved as {value:.3f}.",
        )

    def update_pulses_per_cm(self) -> None:
        current = load_config().get("pulses_per_cm")
        value = self._prompt_calibration(
            "Set Pulses per Centimeter",
            "Enter the new pulses-per-centimeter value:",
            1.0,
            float(current) if isinstance(current, (int, float)) else None,
        )
        if value is None:
            return
        try:
            save_pulses_per_cm(value)
        except Exception as exc:  # pragma: no cover - GUI feedback only
            messagebox.showerror("Failed to save pulses-per-cm", str(exc))
            return
        self.refresh_calibration()
        messagebox.showinfo(
            "Calibration updated",
            f"Pulses per centimeter saved as {value:.3f}.",
        )

    def open_calibration_file(self) -> None:
        path = BASE_DIR / "robot_calibration.json"
        if not path.exists():
            messagebox.showwarning(
                "Calibration file missing",
                f"{path.name} was not found. It will be created after the next calibration save.",
            )
            return
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except AttributeError:
            # Non-Windows fallback
            subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:  # pragma: no cover - defensive
            messagebox.showerror("Failed to open file", str(exc))

    # ------------------------------------------------------------------
    # Utility launching
    # ------------------------------------------------------------------
    def launch_utility(self, utility: Mapping[str, object]) -> None:
        script_path = utility.get("script")
        if not isinstance(script_path, Path):
            messagebox.showerror("Invalid utility", "Utility script path missing or invalid")
            return

        if not script_path.exists():
            messagebox.showerror("Missing file", f"{script_path.name} could not be found.")
            return

        args = utility.get("args") or []
        if not isinstance(args, (list, tuple)):
            messagebox.showerror("Invalid utility", "Utility arguments must be a list or tuple.")
            return

        command = [sys.executable, str(script_path)] + [str(a) for a in args]

        creationflags = 0
        if os.name == "nt" and hasattr(subprocess, "CREATE_NEW_CONSOLE"):
            creationflags = subprocess.CREATE_NEW_CONSOLE  # type: ignore[attr-defined]

        try:
            subprocess.Popen(command, cwd=str(BASE_DIR), creationflags=creationflags)
        except Exception as exc:
            messagebox.showerror("Launch failed", str(exc))

    def launch_straight_calibrator(self) -> None:
        script_path = BASE_DIR / "straight_line_calibrator.py"
        if not script_path.exists():
            messagebox.showerror(
                "Missing file", f"{script_path.name} could not be found."
            )
            return

        command = [sys.executable, str(script_path)]

        creationflags = 0
        if os.name == "nt" and hasattr(subprocess, "CREATE_NEW_CONSOLE"):
            creationflags = subprocess.CREATE_NEW_CONSOLE  # type: ignore[attr-defined]

        try:
            subprocess.Popen(command, cwd=str(BASE_DIR), creationflags=creationflags)
        except Exception as exc:
            messagebox.showerror("Launch failed", str(exc))


def main() -> None:
    root = tk.Tk()
    app = LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
