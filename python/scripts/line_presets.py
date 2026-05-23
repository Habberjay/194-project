from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from common import PYTHON_ROOT


Point = tuple[float, float]


def _relative_to_python_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PYTHON_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def load_presets(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Preset file must contain a JSON object: {path}")

    return data


def save_presets(path: Path, presets: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(presets, file, indent=2)
        file.write("\n")


def _read_point(value: Any, label: str) -> Point:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"Preset {label} must be a two-value list.")

    return float(value[0]), float(value[1])


def load_line_preset(path: Path, name: str) -> tuple[Point, Point]:
    presets = load_presets(path)
    if name not in presets:
        available = ", ".join(sorted(presets)) if presets else "none"
        raise KeyError(f"Line preset '{name}' was not found in {path}. Available presets: {available}")

    preset = presets[name]
    if not isinstance(preset, dict):
        raise ValueError(f"Line preset '{name}' must be a JSON object.")

    return _read_point(preset.get("point_a"), "point_a"), _read_point(preset.get("point_b"), "point_b")


def save_line_preset(
    path: Path,
    name: str,
    frame_path: Path,
    point_a: Point,
    point_b: Point,
    image_size: tuple[int, int],
) -> None:
    presets = load_presets(path)
    presets[name] = {
        "frame": _relative_to_python_root(frame_path),
        "point_a": [round(float(point_a[0]), 2), round(float(point_a[1]), 2)],
        "point_b": [round(float(point_b[0]), 2), round(float(point_b[1]), 2)],
        "image_size": [int(image_size[0]), int(image_size[1])],
    }
    save_presets(path, presets)
