#!/usr/bin/env python3
"""Modern GUI launcher for IHFC Prepsuite utilities.

Windows 11-inspired design with dark mode support and improved UX.
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

# Utility definitions: title, description, relative script path, optional args, icon emoji
UTILITIES: Sequence[Mapping[str, object]] = (
    {
        "title": "Manual Control",
        "description": "Keyboard-driven motor control interface",
        "script": BASE_DIR / "advanced.py",
        "icon": "🎮",
        "category": "Control",
    },
    {
        "title": "Telemetry UI",
        "description": "Real-time arena telemetry viewer",
        "script": BASE_DIR / "telemetry_ui.py",
        "icon": "📊",
        "category": "Monitor",
    },
    {
        "title": "Fruit Layout UI",
        "description": "Tag fruit positions and update red/black CSVs",
        "script": BASE_DIR / "fruit_ui.py",
        "icon": "🍎",
        "category": "Setup",
    },
    {
        "title": "Measure Arena",
        "description": "Capture arena measurements and checkpoints",
        "script": BASE_DIR / "measure_arena.py",
        "icon": "📐",
        "category": "Setup",
    },
)


# Modern color schemes
class ColorScheme:
    """Color schemes for light and dark modes."""
    
    # Light Mode (Windows 11 inspired)
    LIGHT = {
        "bg": "#F3F3F3",
        "fg": "#1F1F1F",
        "card_bg": "#FFFFFF",
        "card_hover": "#F9F9F9",
        "accent": "#0067C0",
        "accent_hover": "#005A9E",
        "border": "#E5E5E5",
        "text_secondary": "#616161",
        "success": "#107C10",
        "warning": "#F7630C",
        "button_bg": "#F3F3F3",
        "button_hover": "#E5E5E5",
        "shadow": "#00000010",
    }
    
    # Dark Mode (Windows 11 inspired)
    DARK = {
        "bg": "#202020",
        "fg": "#FFFFFF",
        "card_bg": "#2B2B2B",
        "card_hover": "#323232",
        "accent": "#60CDFF",
        "accent_hover": "#4FB3E3",
        "border": "#3F3F3F",
        "text_secondary": "#CCCCCC",
        "success": "#6CCB5F",
        "warning": "#FFB900",
        "button_bg": "#2B2B2B",
        "button_hover": "#323232",
        "shadow": "#00000030",
    }


class ModernButton(tk.Canvas):
    """Custom button widget with hover effects and modern styling."""
    
    def __init__(self, parent, text, command, colors, width=120, height=36, 
                 style="primary", **kwargs):
        super().__init__(parent, width=width, height=height, 
                        bg=colors["card_bg"], highlightthickness=0, **kwargs)
        
        self.colors = colors
        self.command = command
        self.text = text
        self.style = style
        self.width = width
        self.height = height
        self.is_hovered = False
        
        # Determine colors based on style
        if style == "primary":
            self.bg_color = colors["accent"]
            self.hover_color = colors["accent_hover"]
            self.text_color = "#FFFFFF"
        else:  # secondary
            self.bg_color = colors["button_bg"]
            self.hover_color = colors["button_hover"]
            self.text_color = colors["fg"]
        
        self.draw()
        
        # Bind events
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)
        
    def draw(self):
        self.delete("all")
        color = self.hover_color if self.is_hovered else self.bg_color
        
        # Rounded rectangle
        radius = 6
        self.create_rounded_rect(2, 2, self.width-2, self.height-2, radius, 
                                 fill=color, outline="")
        
        # Text
        self.create_text(self.width/2, self.height/2, text=self.text, 
                        fill=self.text_color, font=("Segoe UI", 10, "normal"))
    
    def create_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        points = [
            x1+radius, y1,
            x2-radius, y1,
            x2, y1,
            x2, y1+radius,
            x2, y2-radius,
            x2, y2,
            x2-radius, y2,
            x1+radius, y2,
            x1, y2,
            x1, y2-radius,
            x1, y1+radius,
            x1, y1
        ]
        return self.create_polygon(points, smooth=True, **kwargs)
    
    def on_enter(self, event):
        self.is_hovered = True
        self.draw()
        
    def on_leave(self, event):
        self.is_hovered = False
        self.draw()
        
    def on_click(self, event):
        if self.command:
            self.command()


class LauncherApp:
    """Modern Tkinter application wrapper."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("IHFC Robot Control Suite")
        
        # Get screen dimensions and center window
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        window_width = 900
        window_height = 650
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Set minimum size
        self.root.minsize(800, 600)
        
        # Dark mode toggle
        self.dark_mode = True  # Default to dark mode
        self.colors = ColorScheme.DARK if self.dark_mode else ColorScheme.LIGHT
        
        # Configure root window
        self.root.configure(bg=self.colors["bg"])
        
        # Remove window decorations padding
        self.root.option_add("*tearOff", False)
        
        self._build_layout()
        self.refresh_calibration()

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        # Main container
        main = tk.Frame(self.root, bg=self.colors["bg"])
        main.pack(fill=tk.BOTH, expand=True, padx=24, pady=24)
        
        # Header with title and theme toggle
        header = tk.Frame(main, bg=self.colors["bg"])
        header.pack(fill=tk.X, pady=(0, 24))
        
        # Title
        title_frame = tk.Frame(header, bg=self.colors["bg"])
        title_frame.pack(side=tk.LEFT)
        
        title = tk.Label(
            title_frame,
            text="🤖 IHFC Robot Suite",
            font=("Segoe UI", 24, "bold"),
            fg=self.colors["fg"],
            bg=self.colors["bg"]
        )
        title.pack(anchor=tk.W)
        
        subtitle = tk.Label(
            title_frame,
            text="Control • Monitor • Calibrate",
            font=("Segoe UI", 11),
            fg=self.colors["text_secondary"],
            bg=self.colors["bg"]
        )
        subtitle.pack(anchor=tk.W, pady=(4, 0))
        
        # Theme toggle button
        self.theme_btn = ModernButton(
            header,
            text="☀️ Light" if self.dark_mode else "🌙 Dark",
            command=self.toggle_theme,
            colors=self.colors,
            width=100,
            style="secondary"
        )
        self.theme_btn.pack(side=tk.RIGHT)
        
        # Content area (2 columns)
        content = tk.Frame(main, bg=self.colors["bg"])
        content.pack(fill=tk.BOTH, expand=True)
        
        # Left column - Utilities (60%)
        left_col = tk.Frame(content, bg=self.colors["bg"])
        left_col.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=(0, 16))
        
        utilities_label = tk.Label(
            left_col,
            text="Utilities",
            font=("Segoe UI", 16, "bold"),
            fg=self.colors["fg"],
            bg=self.colors["bg"]
        )
        utilities_label.pack(anchor=tk.W, pady=(0, 12))
        
        # Utilities cards container
        self.util_cards = tk.Frame(left_col, bg=self.colors["bg"])
        self.util_cards.pack(fill=tk.BOTH, expand=True)
        
        for idx, utility in enumerate(UTILITIES):
            self._create_utility_card(self.util_cards, utility, idx)
        
        # Right column - Calibration (40%)
        right_col = tk.Frame(content, bg=self.colors["bg"], width=320)
        right_col.pack(fill=tk.BOTH, expand=False, side=tk.RIGHT)
        right_col.pack_propagate(False)
        
        # Calibration section
        self._build_calibration_panel(right_col)

    def _create_utility_card(self, parent, utility, index):
        """Create a modern card for each utility."""
        card = tk.Frame(
            parent,
            bg=self.colors["card_bg"],
            relief=tk.FLAT,
            bd=0
        )
        card.pack(fill=tk.X, pady=(0, 12))
        
        # Add subtle border
        card.configure(highlightbackground=self.colors["border"], 
                      highlightthickness=1)
        
        # Inner padding
        inner = tk.Frame(card, bg=self.colors["card_bg"])
        inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)
        
        # Top row: Icon + Title + Launch button
        top_row = tk.Frame(inner, bg=self.colors["card_bg"])
        top_row.pack(fill=tk.X)
        
        # Icon
        icon_label = tk.Label(
            top_row,
            text=utility["icon"],
            font=("Segoe UI", 20),
            bg=self.colors["card_bg"]
        )
        icon_label.pack(side=tk.LEFT, padx=(0, 12))
        
        # Title and category
        text_frame = tk.Frame(top_row, bg=self.colors["card_bg"])
        text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        title_label = tk.Label(
            text_frame,
            text=utility["title"],
            font=("Segoe UI", 13, "bold"),
            fg=self.colors["fg"],
            bg=self.colors["card_bg"],
            anchor=tk.W
        )
        title_label.pack(anchor=tk.W)
        
        category_label = tk.Label(
            text_frame,
            text=f"• {utility['category']}",
            font=("Segoe UI", 9),
            fg=self.colors["accent"],
            bg=self.colors["card_bg"],
            anchor=tk.W
        )
        category_label.pack(anchor=tk.W)
        
        # Launch button
        launch_btn = ModernButton(
            top_row,
            text="Launch →",
            command=lambda u=utility: self.launch_utility(u),
            colors=self.colors,
            width=110,
            style="primary"
        )
        launch_btn.pack(side=tk.RIGHT)
        
        # Description
        desc_label = tk.Label(
            inner,
            text=utility["description"],
            font=("Segoe UI", 10),
            fg=self.colors["text_secondary"],
            bg=self.colors["card_bg"],
            anchor=tk.W,
            justify=tk.LEFT,
            wraplength=450
        )
        desc_label.pack(anchor=tk.W, pady=(8, 0))
        
        # Hover effects
        def on_enter(e):
            card.configure(bg=self.colors["card_hover"])
            inner.configure(bg=self.colors["card_hover"])
            top_row.configure(bg=self.colors["card_hover"])
            text_frame.configure(bg=self.colors["card_hover"])
            icon_label.configure(bg=self.colors["card_hover"])
            title_label.configure(bg=self.colors["card_hover"])
            category_label.configure(bg=self.colors["card_hover"])
            desc_label.configure(bg=self.colors["card_hover"])
            
        def on_leave(e):
            card.configure(bg=self.colors["card_bg"])
            inner.configure(bg=self.colors["card_bg"])
            top_row.configure(bg=self.colors["card_bg"])
            text_frame.configure(bg=self.colors["card_bg"])
            icon_label.configure(bg=self.colors["card_bg"])
            title_label.configure(bg=self.colors["card_bg"])
            category_label.configure(bg=self.colors["card_bg"])
            desc_label.configure(bg=self.colors["card_bg"])
        
        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)
        inner.bind("<Enter>", on_enter)
        inner.bind("<Leave>", on_leave)

    def _build_calibration_panel(self, parent):
        """Build the modern calibration panel."""
        # Section title
        calib_label = tk.Label(
            parent,
            text="Calibration",
            font=("Segoe UI", 16, "bold"),
            fg=self.colors["fg"],
            bg=self.colors["bg"]
        )
        calib_label.pack(anchor=tk.W, pady=(0, 12))
        
        # Calibration card
        calib_card = tk.Frame(
            parent,
            bg=self.colors["card_bg"],
            highlightbackground=self.colors["border"],
            highlightthickness=1
        )
        calib_card.pack(fill=tk.BOTH, expand=True)
        
        inner = tk.Frame(calib_card, bg=self.colors["card_bg"])
        inner.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Calibration values
        self.ppd_var = tk.StringVar()
        self.ppcm_var = tk.StringVar()
        self.motor_factor_var = tk.StringVar()
        self.updated_var = tk.StringVar()
        
        # Value displays with modern styling
        self._create_value_display(inner, "📐 Pulses per Degree", self.ppd_var)
        self._create_value_display(inner, "📏 Pulses per Centimeter", self.ppcm_var)
        self._create_value_display(inner, "⚙️ Motor Factors (L/R)", self.motor_factor_var)
        
        # Last updated timestamp
        updated_frame = tk.Frame(inner, bg=self.colors["card_bg"])
        updated_frame.pack(fill=tk.X, pady=(16, 0))
        
        updated_label = tk.Label(
            updated_frame,
            textvariable=self.updated_var,
            font=("Segoe UI", 9, "italic"),
            fg=self.colors["text_secondary"],
            bg=self.colors["card_bg"]
        )
        updated_label.pack(anchor=tk.W)
        
        # Separator
        sep = tk.Frame(inner, bg=self.colors["border"], height=1)
        sep.pack(fill=tk.X, pady=(20, 16))
        
        # Quick actions section
        actions_label = tk.Label(
            inner,
            text="Quick Actions",
            font=("Segoe UI", 12, "bold"),
            fg=self.colors["fg"],
            bg=self.colors["card_bg"]
        )
        actions_label.pack(anchor=tk.W, pady=(0, 12))
        
        # Calibration tune buttons (prominent)
        tune_frame = tk.Frame(inner, bg=self.colors["card_bg"])
        tune_frame.pack(fill=tk.X, pady=(0, 8))
        
        ModernButton(
            tune_frame,
            text="🎯 Tune PPD",
            command=self.launch_ppd_tuner,
            colors=self.colors,
            width=135,
            height=42,
            style="primary"
        ).pack(side=tk.LEFT, padx=(0, 8))
        
        ModernButton(
            tune_frame,
            text="🎯 Tune PPC",
            command=self.launch_ppc_tuner,
            colors=self.colors,
            width=135,
            height=42,
            style="primary"
        ).pack(side=tk.LEFT)
        
        # Secondary action buttons
        ModernButton(
            inner,
            text="📐 Straight-Line Calibrator",
            command=self.launch_straight_calibrator,
            colors=self.colors,
            width=280,
            style="secondary"
        ).pack(fill=tk.X, pady=(8, 0))
        
        ModernButton(
            inner,
            text="✏️ Set Pulses/Degree",
            command=self.update_pulses_per_degree,
            colors=self.colors,
            width=280,
            style="secondary"
        ).pack(fill=tk.X, pady=(8, 0))
        
        ModernButton(
            inner,
            text="✏️ Set Pulses/Centimeter",
            command=self.update_pulses_per_cm,
            colors=self.colors,
            width=280,
            style="secondary"
        ).pack(fill=tk.X, pady=(8, 0))
        
        ModernButton(
            inner,
            text="📄 Open Config File",
            command=self.open_calibration_file,
            colors=self.colors,
            width=280,
            style="secondary"
        ).pack(fill=tk.X, pady=(8, 0))
        
        # Refresh button at bottom
        ModernButton(
            inner,
            text="🔄 Refresh",
            command=self.refresh_calibration,
            colors=self.colors,
            width=280,
            style="secondary"
        ).pack(fill=tk.X, pady=(16, 0))

    def _create_value_display(self, parent, label_text, variable):
        """Create a modern value display row."""
        frame = tk.Frame(parent, bg=self.colors["card_bg"])
        frame.pack(fill=tk.X, pady=(0, 12))
        
        label = tk.Label(
            frame,
            text=label_text,
            font=("Segoe UI", 10),
            fg=self.colors["text_secondary"],
            bg=self.colors["card_bg"]
        )
        label.pack(anchor=tk.W)
        
        value = tk.Label(
            frame,
            textvariable=variable,
            font=("Consolas", 12, "bold"),
            fg=self.colors["fg"],
            bg=self.colors["card_bg"]
        )
        value.pack(anchor=tk.W, pady=(4, 0))

    def toggle_theme(self):
        """Toggle between light and dark mode."""
        self.dark_mode = not self.dark_mode
        self.colors = ColorScheme.DARK if self.dark_mode else ColorScheme.LIGHT
        
        # Rebuild the entire UI with new colors
        for widget in self.root.winfo_children():
            widget.destroy()
        
        self._build_layout()
        self.refresh_calibration()

    # ------------------------------------------------------------------
    # Calibration helpers
    # ------------------------------------------------------------------
    def refresh_calibration(self) -> None:
        config = load_config()
        ppd = config.get("pulses_per_degree")
        ppcm = config.get("pulses_per_cm")
        updated = config.get("updated_at") or "Unknown"

        try:
            ppd_text = f"{float(ppd):.3f}"
        except (TypeError, ValueError):
            ppd_text = "--"

        try:
            ppcm_text = f"{float(ppcm):.3f}"
        except (TypeError, ValueError):
            ppcm_text = "--"

        left_factor = config.get("motor_factor_left")
        right_factor = config.get("motor_factor_right")
        try:
            motor_factor_text = f"{float(left_factor):.3f} / {float(right_factor):.3f}"
        except (TypeError, ValueError):
            motor_factor_text = "-- / --"

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

    def launch_ppd_tuner(self) -> None:
        script_path = BASE_DIR / "measure_ppd_encoder_only.py"
        if not script_path.exists():
            messagebox.showerror("Missing file", f"{script_path.name} could not be found.")
            return
        try:
            creationflags = 0
            if os.name == "nt" and hasattr(subprocess, "CREATE_NEW_CONSOLE"):
                creationflags = subprocess.CREATE_NEW_CONSOLE  # type: ignore[attr-defined]
            subprocess.Popen([sys.executable, str(script_path)], cwd=str(BASE_DIR), creationflags=creationflags)
        except Exception as exc:
            messagebox.showerror("Launch failed", str(exc))

    def launch_ppc_tuner(self) -> None:
        script_path = BASE_DIR / "measure_ppc_encoder_only.py"
        if not script_path.exists():
            messagebox.showerror("Missing file", f"{script_path.name} could not be found.")
            return
        try:
            creationflags = 0
            if os.name == "nt" and hasattr(subprocess, "CREATE_NEW_CONSOLE"):
                creationflags = subprocess.CREATE_NEW_CONSOLE  # type: ignore[attr-defined]
            subprocess.Popen([sys.executable, str(script_path)], cwd=str(BASE_DIR), creationflags=creationflags)
        except Exception as exc:
            messagebox.showerror("Launch failed", str(exc))


def main() -> None:
    root = tk.Tk()
    app = LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
