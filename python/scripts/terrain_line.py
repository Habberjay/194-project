from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np


AxisMode = Literal["vertical", "normal"]
ProfileMode = Literal["residual", "absolute"]


@dataclass(frozen=True)
class TerrainLineConfig:
    samples: int = 96
    strength: float = 60.0
    smooth_window: int = 9
    axis: AxisMode = "vertical"
    profile_mode: ProfileMode = "residual"
    invert_depth: bool = False
    offset_sign: float = 1.0


@dataclass(frozen=True)
class TerrainLineResult:
    baseline_points: np.ndarray
    terrain_points: np.ndarray
    sampled_depth: np.ndarray
    smoothed_depth: np.ndarray
    offsets: np.ndarray


def parse_point(value: str) -> tuple[float, float]:
    parts = value.split(",")
    if len(parts) != 2:
        raise ValueError(f"Point must use the format x,y. Got: {value}")

    try:
        return float(parts[0].strip()), float(parts[1].strip())
    except ValueError as exc:
        raise ValueError(f"Point contains non-numeric values: {value}") from exc


def default_points(width: int, height: int) -> tuple[tuple[float, float], tuple[float, float]]:
    return (width * 0.2, height * 0.72), (width * 0.8, height * 0.72)


def linearly_spaced_points(
    start: tuple[float, float],
    end: tuple[float, float],
    samples: int,
) -> np.ndarray:
    if samples < 2:
        raise ValueError("samples must be at least 2.")

    start_array = np.asarray(start, dtype=np.float32)
    end_array = np.asarray(end, dtype=np.float32)
    weights = np.linspace(0.0, 1.0, samples, dtype=np.float32)[:, None]
    return start_array + (end_array - start_array) * weights


def sample_depth_bilinear(depth_map: np.ndarray, points: np.ndarray) -> np.ndarray:
    if depth_map.ndim != 2:
        raise ValueError("depth_map must be a single-channel grayscale image.")

    height, width = depth_map.shape
    x_coords = np.clip(points[:, 0], 0, width - 1).astype(np.float32).reshape(1, -1)
    y_coords = np.clip(points[:, 1], 0, height - 1).astype(np.float32).reshape(1, -1)

    sampled = cv2.remap(
        depth_map.astype(np.float32),
        x_coords,
        y_coords,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return sampled.reshape(-1)


def smooth_profile(values: np.ndarray, window: int) -> np.ndarray:
    if window <= 1 or values.size < 3:
        return values.astype(np.float32)

    window = min(int(window), int(values.size))
    if window % 2 == 0:
        window -= 1
    if window <= 1:
        return values.astype(np.float32)

    pad = window // 2
    padded = np.pad(values.astype(np.float32), pad_width=pad, mode="edge")
    kernel = np.ones(window, dtype=np.float32) / float(window)
    return np.convolve(padded, kernel, mode="valid")


def robust_normalize(values: np.ndarray) -> np.ndarray:
    values = values.astype(np.float32)
    low = float(np.percentile(values, 5))
    high = float(np.percentile(values, 95))

    if high <= low:
        return np.zeros_like(values, dtype=np.float32)

    normalized = (values - low) / (high - low)
    return np.clip(normalized, 0.0, 1.0).astype(np.float32)


def offsets_from_depth(
    depth_values: np.ndarray,
    strength: float,
    smooth_window: int,
    profile_mode: ProfileMode,
    offset_sign: float,
) -> tuple[np.ndarray, np.ndarray]:
    smoothed = smooth_profile(depth_values, smooth_window)
    normalized = robust_normalize(smoothed)

    if profile_mode == "residual":
        endpoint_trend = np.linspace(float(normalized[0]), float(normalized[-1]), normalized.size, dtype=np.float32)
        profile = normalized - endpoint_trend
    elif profile_mode == "absolute":
        profile = normalized - float(np.median(normalized))
    else:
        raise ValueError(f"Unsupported profile_mode: {profile_mode}")

    max_abs = float(np.max(np.abs(profile)))
    if max_abs <= 1e-6:
        offsets = np.zeros_like(profile, dtype=np.float32)
    else:
        offsets = (profile / max_abs) * float(strength) * float(offset_sign)

    if profile_mode == "residual":
        offsets[0] = 0.0
        offsets[-1] = 0.0

    return offsets.astype(np.float32), smoothed.astype(np.float32)


def displacement_vector(start: tuple[float, float], end: tuple[float, float], axis: AxisMode) -> np.ndarray:
    if axis == "vertical":
        return np.array([0.0, -1.0], dtype=np.float32)

    if axis != "normal":
        raise ValueError(f"Unsupported axis: {axis}")

    start_array = np.asarray(start, dtype=np.float32)
    end_array = np.asarray(end, dtype=np.float32)
    direction = end_array - start_array
    length = float(np.linalg.norm(direction))
    if length <= 1e-6:
        raise ValueError("Line start and end points are too close together.")

    normal = np.array([-direction[1], direction[0]], dtype=np.float32) / length
    return normal


def clamp_points_to_image(points: np.ndarray, width: int, height: int) -> np.ndarray:
    clamped = points.copy()
    clamped[:, 0] = np.clip(clamped[:, 0], 0, width - 1)
    clamped[:, 1] = np.clip(clamped[:, 1], 0, height - 1)
    return clamped


def build_terrain_line(
    depth_map: np.ndarray,
    start: tuple[float, float],
    end: tuple[float, float],
    config: TerrainLineConfig,
) -> TerrainLineResult:
    if depth_map.ndim != 2:
        raise ValueError("depth_map must be a single-channel grayscale image.")

    depth_for_sampling = depth_map
    if config.invert_depth:
        depth_for_sampling = 255 - depth_for_sampling

    baseline_points = linearly_spaced_points(start, end, config.samples)
    sampled_depth = sample_depth_bilinear(depth_for_sampling, baseline_points)
    offsets, smoothed_depth = offsets_from_depth(
        sampled_depth,
        strength=config.strength,
        smooth_window=config.smooth_window,
        profile_mode=config.profile_mode,
        offset_sign=config.offset_sign,
    )

    vector = displacement_vector(start, end, config.axis)
    terrain_points = baseline_points + offsets[:, None] * vector[None, :]
    height, width = depth_map.shape
    terrain_points = clamp_points_to_image(terrain_points, width=width, height=height)

    return TerrainLineResult(
        baseline_points=baseline_points,
        terrain_points=terrain_points,
        sampled_depth=sampled_depth,
        smoothed_depth=smoothed_depth,
        offsets=offsets,
    )
