"""Shared calibration configuration helpers.

Stores calibration constants (currently pulses-per-degree) in a JSON file so
robot scripts can stay in sync. Provides convenience helpers to load and save
values with sane defaults and human-friendly logging.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict

CONFIG_FILENAME = "robot_calibration.json"
DEFAULT_CONFIG = {
    "pulses_per_degree": 45.0,
    "updated_at": None,
}


def _config_path() -> str:
    return os.path.join(os.path.dirname(__file__), CONFIG_FILENAME)


def load_config() -> Dict[str, Any]:
    path = _config_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("Calibration config must be a JSON object")
        merged = DEFAULT_CONFIG.copy()
        merged.update(data)
        return merged
    except FileNotFoundError:
        return DEFAULT_CONFIG.copy()
    except Exception as exc:
        print(f"⚠️  Failed to load calibration config ({exc}); using defaults")
        return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> None:
    path = _config_path()
    payload = DEFAULT_CONFIG.copy()
    payload.update(config)
    payload["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=4, sort_keys=True)
        print(f"💾 Calibration config saved to {path}")
    except Exception as exc:
        print(f"❌ Failed to save calibration config: {exc}")


def load_pulses_per_degree(default: float | None = None) -> float:
    config = load_config()
    value = config.get("pulses_per_degree")
    if value is None:
        return default if default is not None else DEFAULT_CONFIG["pulses_per_degree"]
    try:
        return float(value)
    except (TypeError, ValueError):
        return default if default is not None else DEFAULT_CONFIG["pulses_per_degree"]


def save_pulses_per_degree(pulses: float) -> None:
    pulses_clamped = max(1.0, float(pulses))
    config = load_config()
    config["pulses_per_degree"] = pulses_clamped
    save_config(config)
