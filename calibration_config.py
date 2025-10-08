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
    "pulses_per_cm": 407.4,
    "motor_factor_left": 1.0,
    "motor_factor_right": 1.0,
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


def load_pulses_per_cm(default: float | None = None) -> float:
    config = load_config()
    value = config.get("pulses_per_cm")
    fallback = DEFAULT_CONFIG["pulses_per_cm"] if default is None else default
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def save_pulses_per_cm(pulses: float) -> None:
    pulses_clamped = max(1.0, float(pulses))
    config = load_config()
    config["pulses_per_cm"] = pulses_clamped
    save_config(config)


def load_motor_factors(
    default_left: float | None = None,
    default_right: float | None = None,
) -> tuple[float, float]:
    config = load_config()
    left_default = 1.0 if default_left is None else float(default_left)
    right_default = 1.0 if default_right is None else float(default_right)

    def _safe_float(value, fallback):
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    left = _safe_float(config.get("motor_factor_left"), left_default)
    right = _safe_float(config.get("motor_factor_right"), right_default)

    left = max(0.2, min(3.0, left))
    right = max(0.2, min(3.0, right))
    return left, right


def save_motor_factors(left_factor: float, right_factor: float) -> None:
    left = max(0.2, min(3.0, float(left_factor)))
    right = max(0.2, min(3.0, float(right_factor)))
    config = load_config()
    config["motor_factor_left"] = left
    config["motor_factor_right"] = right
    save_config(config)
