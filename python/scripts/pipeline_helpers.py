from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from common import DEPTH_MAPS_DIR, FRAMES_DIR, SUPPORTED_IMAGE_EXTENSIONS, collect_files, resolve_path


def relative_to_python_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(resolve_path("."))).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def find_default_frame() -> Path:
    frames = collect_files(FRAMES_DIR, SUPPORTED_IMAGE_EXTENSIONS)
    if len(frames) > 1:
        print(f"Multiple frames found. Using the first one: {frames[0].name}")
    return frames[0]


def find_matching_depth(frame_path: Path, depth_dir: Path = DEPTH_MAPS_DIR) -> Path:
    depth_path = depth_dir / f"{frame_path.stem}_depth.png"
    if not depth_path.exists():
        raise FileNotFoundError(f"Matching depth map not found: {depth_path}")
    return depth_path


def load_frame_and_depth(frame_path: Path, depth_path: Path) -> tuple[np.ndarray, np.ndarray]:
    frame = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError(f"Could not read frame: {frame_path}")

    depth_map = cv2.imread(str(depth_path), cv2.IMREAD_GRAYSCALE)
    if depth_map is None:
        raise ValueError(f"Could not read depth map: {depth_path}")

    frame_height, frame_width = frame.shape[:2]
    if depth_map.shape[:2] != (frame_height, frame_width):
        depth_map = cv2.resize(depth_map, (frame_width, frame_height), interpolation=cv2.INTER_LINEAR)

    return frame, depth_map


def parse_point(value: str) -> tuple[float, float]:
    parts = value.split(",")
    if len(parts) != 2:
        raise ValueError(f"Point must use the format x,y. Got: {value}")

    try:
        return float(parts[0].strip()), float(parts[1].strip())
    except ValueError as exc:
        raise ValueError(f"Point contains non-numeric values: {value}") from exc


def default_line_points(width: int, height: int) -> tuple[tuple[float, float], tuple[float, float]]:
    return (width * 0.2, height * 0.72), (width * 0.8, height * 0.72)
