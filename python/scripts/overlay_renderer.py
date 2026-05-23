from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

from common import (
    DEPTH_MAPS_DIR,
    FRAMES_DIR,
    OVERLAYS_DIR,
    SUPPORTED_IMAGE_EXTENSIONS,
    clear_folder_contents,
    collect_files,
    ensure_project_folders,
    resolve_path,
)
from terrain_line import TerrainLineConfig, build_terrain_line, default_points, parse_point


FLAT_COLOR = (0, 210, 255)
TERRAIN_COLOR = (70, 255, 80)
ANCHOR_COLOR = (255, 255, 255)


def find_default_frame() -> Path:
    frames = collect_files(FRAMES_DIR, SUPPORTED_IMAGE_EXTENSIONS)
    if len(frames) > 1:
        print(f"Multiple frames found. Using the first one: {frames[0].name}")
    return frames[0]


def find_matching_depth(frame_path: Path, depth_dir: Path) -> Path:
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


def to_polyline(points: np.ndarray) -> np.ndarray:
    return np.rint(points).astype(np.int32).reshape((-1, 1, 2))


def draw_label(image: np.ndarray, label: str) -> None:
    cv2.rectangle(image, (0, 0), (image.shape[1], 34), (0, 0, 0), thickness=-1)
    cv2.putText(image, label, (12, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 1, cv2.LINE_AA)


def draw_lines(
    image: np.ndarray,
    start: tuple[float, float],
    end: tuple[float, float],
    terrain_points: np.ndarray,
    include_flat: bool = True,
    include_terrain: bool = True,
    thickness: int = 4,
) -> np.ndarray:
    output = image.copy()
    start_i = (int(round(start[0])), int(round(start[1])))
    end_i = (int(round(end[0])), int(round(end[1])))

    if include_flat:
        cv2.line(output, start_i, end_i, FLAT_COLOR, max(1, thickness - 1), cv2.LINE_AA)

    if include_terrain:
        cv2.polylines(output, [to_polyline(terrain_points)], isClosed=False, color=TERRAIN_COLOR, thickness=thickness, lineType=cv2.LINE_AA)

    for point in (start_i, end_i):
        cv2.circle(output, point, radius=6, color=(0, 0, 0), thickness=-1, lineType=cv2.LINE_AA)
        cv2.circle(output, point, radius=4, color=ANCHOR_COLOR, thickness=-1, lineType=cv2.LINE_AA)

    return output


def render_result(
    frame: np.ndarray,
    depth_map: np.ndarray,
    start: tuple[float, float],
    end: tuple[float, float],
    config: TerrainLineConfig,
    thickness: int,
) -> tuple[np.ndarray, np.ndarray]:
    result = build_terrain_line(depth_map, start, end, config)

    flat_view = draw_lines(frame, start, end, result.terrain_points, include_flat=True, include_terrain=False, thickness=thickness)
    draw_label(flat_view, "Original frame + flat line")

    depth_view = cv2.applyColorMap(depth_map, cv2.COLORMAP_TURBO)
    depth_view = draw_lines(depth_view, start, end, result.terrain_points, include_flat=False, include_terrain=True, thickness=thickness)
    draw_label(depth_view, "Depth map + terrain-aware line")

    overlay_view = draw_lines(frame, start, end, result.terrain_points, include_flat=True, include_terrain=True, thickness=thickness)
    draw_label(overlay_view, "Comparison: flat line vs terrain-aware line")

    comparison = np.hstack([flat_view, depth_view, overlay_view])
    return overlay_view, comparison


def write_overlay_outputs(
    frame_path: Path,
    output_dir: Path,
    overlay: np.ndarray,
    comparison: np.ndarray,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    overlay_path = output_dir / f"{frame_path.stem}_overlay.png"
    comparison_path = output_dir / f"{frame_path.stem}_comparison.png"

    if not cv2.imwrite(str(overlay_path), overlay):
        raise RuntimeError(f"Could not write overlay image: {overlay_path}")
    if not cv2.imwrite(str(comparison_path), comparison):
        raise RuntimeError(f"Could not write comparison image: {comparison_path}")

    return overlay_path, comparison_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a terrain-aware blueprint line over a frame and depth map.")
    parser.add_argument("--frame", default=None, help="Frame image. Defaults to the first image in frames/.")
    parser.add_argument("--depth", default=None, help="Depth map image. Defaults to the matching *_depth.png in depth_maps/.")
    parser.add_argument("--depth-dir", default=str(DEPTH_MAPS_DIR), help="Folder used when finding a matching depth map.")
    parser.add_argument("--output-dir", default=str(OVERLAYS_DIR), help="Folder for overlay outputs.")
    parser.add_argument("--point-a", default=None, help="Start point as x,y. Defaults to 20%% width, 72%% height.")
    parser.add_argument("--point-b", default=None, help="End point as x,y. Defaults to 80%% width, 72%% height.")
    parser.add_argument("--samples", type=int, default=96, help="Number of depth samples along the line.")
    parser.add_argument("--strength", type=float, default=60.0, help="Maximum visual displacement in pixels.")
    parser.add_argument("--smooth-window", type=int, default=9, help="Moving-average window for depth samples.")
    parser.add_argument("--axis", choices=["vertical", "normal"], default="vertical", help="Direction used for visual displacement.")
    parser.add_argument(
        "--profile-mode",
        choices=["residual", "absolute"],
        default="residual",
        help="residual preserves endpoints; absolute bends around the median depth.",
    )
    parser.add_argument("--invert-depth", action="store_true", help="Invert grayscale depth before sampling.")
    parser.add_argument("--offset-sign", type=float, default=1.0, help="Use -1 if the line bends in the wrong direction.")
    parser.add_argument("--thickness", type=int, default=4, help="Overlay line thickness.")
    parser.add_argument("--clear", action="store_true", help="Clean the output folder before writing.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_project_folders()

    try:
        frame_path = resolve_path(args.frame) if args.frame else find_default_frame()
        depth_dir = resolve_path(args.depth_dir)
        depth_path = resolve_path(args.depth) if args.depth else find_matching_depth(frame_path, depth_dir)
        output_dir = resolve_path(args.output_dir)

        if args.clear:
            clear_folder_contents(output_dir)

        frame, depth_map = load_frame_and_depth(frame_path, depth_path)
        height, width = depth_map.shape

        default_a, default_b = default_points(width, height)
        start = parse_point(args.point_a) if args.point_a else default_a
        end = parse_point(args.point_b) if args.point_b else default_b

        config = TerrainLineConfig(
            samples=args.samples,
            strength=args.strength,
            smooth_window=args.smooth_window,
            axis=args.axis,
            profile_mode=args.profile_mode,
            invert_depth=args.invert_depth,
            offset_sign=args.offset_sign,
        )

        overlay, comparison = render_result(frame, depth_map, start, end, config, thickness=args.thickness)
        overlay_path, comparison_path = write_overlay_outputs(frame_path, output_dir, overlay, comparison)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Frame: {frame_path.name}")
    print(f"Depth: {depth_path.name}")
    print(f"Point A: {start[0]:.1f},{start[1]:.1f}")
    print(f"Point B: {end[0]:.1f},{end[1]:.1f}")
    print(f"Saved overlay: {overlay_path}")
    print(f"Saved comparison: {comparison_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
