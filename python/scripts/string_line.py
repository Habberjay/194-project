from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np

from terrain_line import (
    AxisMode,
    ProfileMode,
    clamp_points_to_image,
    displacement_vector,
    linearly_spaced_points,
    offsets_from_depth,
    sample_depth_bilinear,
    smooth_profile,
)


@dataclass(frozen=True)
class StringLineConfig:
    control_points: int = 96
    search_radius: int = 32
    candidate_step: int = 2
    strength: float = 60.0
    smooth_window: int = 9
    axis: AxisMode = "normal"
    profile_mode: ProfileMode = "absolute"
    invert_depth: bool = False
    offset_sign: float = 1.0
    snap_weight: float = 1.0
    edge_weight: float = 0.35
    smoothness: float = 0.65
    post_smooth: float = 0.35
    post_smooth_iterations: int = 2


@dataclass(frozen=True)
class StringLineResult:
    baseline_points: np.ndarray
    raw_points: np.ndarray
    string_points: np.ndarray
    sampled_depth: np.ndarray
    smoothed_depth: np.ndarray
    target_offsets: np.ndarray
    chosen_offsets: np.ndarray
    candidate_offsets: np.ndarray


def candidate_offsets(search_radius: int, candidate_step: int) -> np.ndarray:
    if search_radius < 1:
        raise ValueError("search_radius must be at least 1.")
    if candidate_step < 1:
        raise ValueError("candidate_step must be at least 1.")

    offsets = np.arange(-search_radius, search_radius + 1, candidate_step, dtype=np.float32)
    if not np.any(np.isclose(offsets, 0.0)):
        offsets = np.sort(np.append(offsets, 0.0)).astype(np.float32)
    return offsets


def depth_edge_map(depth_map: np.ndarray) -> np.ndarray:
    depth = depth_map.astype(np.float32)
    grad_x = cv2.Sobel(depth, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(depth, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = cv2.magnitude(grad_x, grad_y)
    high = float(np.percentile(magnitude, 95))
    if high <= 1e-6:
        return np.zeros(depth_map.shape, dtype=np.float32)
    return np.clip(magnitude / high, 0.0, 1.0).astype(np.float32)


def sample_image_at_candidates(image: np.ndarray, candidate_points: np.ndarray) -> np.ndarray:
    if image.ndim != 2:
        raise ValueError("image must be a single-channel array.")

    height, width = image.shape
    x_map = np.clip(candidate_points[:, :, 0], 0, width - 1).astype(np.float32)
    y_map = np.clip(candidate_points[:, :, 1], 0, height - 1).astype(np.float32)
    return cv2.remap(
        image.astype(np.float32),
        x_map,
        y_map,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )


def smooth_polyline(points: np.ndarray, amount: float, iterations: int) -> np.ndarray:
    if points.shape[0] < 3 or amount <= 0.0 or iterations < 1:
        return points.astype(np.float32)

    amount = float(np.clip(amount, 0.0, 1.0))
    smoothed = points.astype(np.float32).copy()
    for _ in range(iterations):
        previous = smoothed.copy()
        neighbor_average = 0.5 * (previous[:-2] + previous[2:])
        smoothed[1:-1] = (1.0 - amount) * previous[1:-1] + amount * neighbor_average
    return smoothed


def choose_string_offsets(
    target_offsets: np.ndarray,
    edge_values: np.ndarray,
    offsets: np.ndarray,
    config: StringLineConfig,
) -> np.ndarray:
    point_count = target_offsets.size
    candidate_count = offsets.size
    if point_count == 0 or edge_values.shape != (point_count, candidate_count):
        raise ValueError("Invalid string candidate dimensions.")

    radius = max(float(config.search_radius), 1.0)
    data_cost = config.snap_weight * ((offsets[None, :] - target_offsets[:, None]) / radius) ** 2
    data_cost -= config.edge_weight * edge_values

    transition = config.smoothness * ((offsets[:, None] - offsets[None, :]) / radius) ** 2
    dp = np.zeros((point_count, candidate_count), dtype=np.float32)
    parents = np.zeros((point_count, candidate_count), dtype=np.int32)
    dp[0] = data_cost[0]

    for index in range(1, point_count):
        costs = dp[index - 1][:, None] + transition
        parents[index] = np.argmin(costs, axis=0)
        dp[index] = data_cost[index] + np.min(costs, axis=0)

    chosen = np.zeros(point_count, dtype=np.float32)
    candidate_index = int(np.argmin(dp[-1]))
    for index in range(point_count - 1, -1, -1):
        chosen[index] = offsets[candidate_index]
        candidate_index = int(parents[index, candidate_index])

    return chosen


def build_string_line(
    depth_map: np.ndarray,
    start: tuple[float, float],
    end: tuple[float, float],
    config: StringLineConfig,
    predicted_points: np.ndarray | None = None,
) -> StringLineResult:
    if depth_map.ndim != 2:
        raise ValueError("depth_map must be a single-channel grayscale image.")
    if config.control_points < 2:
        raise ValueError("control_points must be at least 2.")

    depth_for_sampling = depth_map
    if config.invert_depth:
        depth_for_sampling = 255 - depth_for_sampling

    if predicted_points is not None:
        baseline_points = np.asarray(predicted_points, dtype=np.float32)
        if baseline_points.shape != (config.control_points, 2):
            baseline_points = resample_polyline(baseline_points, config.control_points)
    else:
        baseline_points = linearly_spaced_points(start, end, config.control_points)

    sampled_depth = sample_depth_bilinear(depth_for_sampling, baseline_points)
    target_offsets, smoothed_depth = offsets_from_depth(
        sampled_depth,
        strength=min(float(config.strength), float(config.search_radius)),
        smooth_window=config.smooth_window,
        profile_mode=config.profile_mode,
        offset_sign=config.offset_sign,
    )

    vector = displacement_vector(start, end, config.axis)
    offsets = candidate_offsets(config.search_radius, config.candidate_step)
    candidates = baseline_points[:, None, :] + offsets[None, :, None] * vector[None, None, :]
    height, width = depth_map.shape
    candidates[:, :, 0] = np.clip(candidates[:, :, 0], 0, width - 1)
    candidates[:, :, 1] = np.clip(candidates[:, :, 1], 0, height - 1)

    edges = depth_edge_map(depth_for_sampling)
    edge_values = sample_image_at_candidates(edges, candidates)
    chosen_offsets = choose_string_offsets(target_offsets, edge_values, offsets, config)

    raw_points = baseline_points + chosen_offsets[:, None] * vector[None, :]
    raw_points = clamp_points_to_image(raw_points, width=width, height=height)
    string_points = smooth_polyline(raw_points, amount=config.post_smooth, iterations=config.post_smooth_iterations)
    string_points = clamp_points_to_image(string_points, width=width, height=height)

    return StringLineResult(
        baseline_points=baseline_points,
        raw_points=raw_points,
        string_points=string_points,
        sampled_depth=sampled_depth.astype(np.float32),
        smoothed_depth=smooth_profile(smoothed_depth, max(config.smooth_window, 1)),
        target_offsets=target_offsets.astype(np.float32),
        chosen_offsets=chosen_offsets.astype(np.float32),
        candidate_offsets=offsets.astype(np.float32),
    )


def resample_polyline(points: np.ndarray, count: int) -> np.ndarray:
    points = np.asarray(points, dtype=np.float32)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("points must have shape (N, 2).")
    if points.shape[0] == count:
        return points.copy()
    if points.shape[0] < 2:
        raise ValueError("At least two points are required to resample a polyline.")

    distances = np.linalg.norm(np.diff(points, axis=0), axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(distances)])
    total = float(cumulative[-1])
    if total <= 1e-6:
        return np.repeat(points[:1], count, axis=0)

    targets = np.linspace(0.0, total, count, dtype=np.float32)
    x_coords = np.interp(targets, cumulative, points[:, 0])
    y_coords = np.interp(targets, cumulative, points[:, 1])
    return np.column_stack([x_coords, y_coords]).astype(np.float32)


def string_points_to_json(points: np.ndarray) -> list[list[float]]:
    return [[round(float(x), 2), round(float(y), 2)] for x, y in np.asarray(points, dtype=np.float32)]
