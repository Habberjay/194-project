from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

from common import (
    DEPTH_MAPS_DIR,
    FRAMES_DIR,
    LINE_PRESETS_PATH,
    OVERLAYS_DIR,
    SUPPORTED_IMAGE_EXTENSIONS,
    clear_folder_contents,
    collect_files,
    ensure_project_folders,
    resolve_path,
)
from line_presets import load_line_preset
from string_line import StringLineConfig, StringLineResult, build_string_line, string_points_to_json
from terrain_line import TerrainLineConfig, build_terrain_line, default_points, parse_point


FLAT_COLOR = (0, 210, 255)
TERRAIN_COLOR = (70, 255, 80)
ANCHOR_COLOR = (255, 255, 255)
RAW_STRING_COLOR = (0, 140, 255)
BASELINE_COLOR = (255, 190, 80)


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


def resolve_profile_mode(line_mode: str, profile_mode: str) -> str:
    if profile_mode == "auto":
        return "absolute" if line_mode == "string" else "residual"
    return profile_mode


def resolve_axis(line_mode: str, axis: str) -> str:
    if axis == "auto":
        return "normal" if line_mode == "string" else "vertical"
    return axis


def draw_string_debug(
    frame: np.ndarray,
    depth_map: np.ndarray,
    start: tuple[float, float],
    end: tuple[float, float],
    result: StringLineResult,
    thickness: int,
) -> np.ndarray:
    depth_view = cv2.applyColorMap(depth_map, cv2.COLORMAP_TURBO)
    debug = cv2.addWeighted(frame, 0.55, depth_view, 0.45, 0)

    cv2.polylines(debug, [to_polyline(result.baseline_points)], False, BASELINE_COLOR, max(1, thickness - 2), cv2.LINE_AA)
    cv2.polylines(debug, [to_polyline(result.raw_points)], False, RAW_STRING_COLOR, max(1, thickness - 1), cv2.LINE_AA)
    cv2.polylines(debug, [to_polyline(result.string_points)], False, TERRAIN_COLOR, thickness, cv2.LINE_AA)

    stride = max(1, result.string_points.shape[0] // 24)
    for point in result.raw_points[::stride]:
        center = (int(round(point[0])), int(round(point[1])))
        cv2.circle(debug, center, 3, RAW_STRING_COLOR, -1, cv2.LINE_AA)
    for point in result.string_points[::stride]:
        center = (int(round(point[0])), int(round(point[1])))
        cv2.circle(debug, center, 3, TERRAIN_COLOR, -1, cv2.LINE_AA)

    start_i = (int(round(start[0])), int(round(start[1])))
    end_i = (int(round(end[0])), int(round(end[1])))
    for point in (start_i, end_i):
        cv2.circle(debug, point, 7, (0, 0, 0), -1, cv2.LINE_AA)
        cv2.circle(debug, point, 5, ANCHOR_COLOR, -1, cv2.LINE_AA)

    draw_label(debug, "String debug: baseline, raw snapped points, final smoothed string")
    return debug


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


def render_result_with_mode(
    frame: np.ndarray,
    depth_map: np.ndarray,
    start: tuple[float, float],
    end: tuple[float, float],
    line_mode: str,
    terrain_config: TerrainLineConfig,
    string_config: StringLineConfig,
    thickness: int,
    debug_string: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, dict[str, object]]:
    if line_mode == "simple":
        result = build_terrain_line(depth_map, start, end, terrain_config)
        terrain_points = result.terrain_points
        debug_view = None
        points_data = {
            "mode": "simple",
            "points": string_points_to_json(terrain_points),
        }
        line_label = "Depth map + terrain-aware line"
        comparison_label = "Comparison: flat line vs terrain-aware line"
    elif line_mode == "string":
        result = build_string_line(depth_map, start, end, string_config)
        terrain_points = result.string_points
        debug_view = draw_string_debug(frame, depth_map, start, end, result, thickness) if debug_string else None
        points_data = {
            "mode": "string",
            "baseline_points": string_points_to_json(result.baseline_points),
            "raw_points": string_points_to_json(result.raw_points),
            "string_points": string_points_to_json(result.string_points),
            "chosen_offsets": [round(float(value), 3) for value in result.chosen_offsets],
        }
        line_label = "Depth map + terrain-aware string"
        comparison_label = "Comparison: flat line vs terrain-aware string"
    else:
        raise ValueError(f"Unsupported line mode: {line_mode}")

    flat_view = draw_lines(frame, start, end, terrain_points, include_flat=True, include_terrain=False, thickness=thickness)
    draw_label(flat_view, "Original frame + flat line")

    depth_view = cv2.applyColorMap(depth_map, cv2.COLORMAP_TURBO)
    depth_view = draw_lines(depth_view, start, end, terrain_points, include_flat=False, include_terrain=True, thickness=thickness)
    draw_label(depth_view, line_label)

    overlay_view = draw_lines(frame, start, end, terrain_points, include_flat=True, include_terrain=True, thickness=thickness)
    draw_label(overlay_view, comparison_label)

    comparison = np.hstack([flat_view, depth_view, overlay_view])
    return overlay_view, comparison, debug_view, points_data


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


def write_debug_output(frame_path: Path, output_dir: Path, debug_image: np.ndarray | None) -> Path | None:
    if debug_image is None:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    debug_path = output_dir / f"{frame_path.stem}_string_debug.png"
    if not cv2.imwrite(str(debug_path), debug_image):
        raise RuntimeError(f"Could not write debug image: {debug_path}")
    return debug_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a terrain-aware blueprint line over a frame and depth map.")
    parser.add_argument("--frame", default=None, help="Frame image. Defaults to the first image in output/frames/.")
    parser.add_argument("--depth", default=None, help="Depth map image. Defaults to the matching *_depth.png in output/depth_maps/.")
    parser.add_argument("--depth-dir", default=str(DEPTH_MAPS_DIR), help="Folder used when finding a matching depth map.")
    parser.add_argument("--output-dir", default=str(OVERLAYS_DIR), help="Folder for overlay outputs.")
    parser.add_argument("--preset", default=None, help="Line preset name from line_presets.json.")
    parser.add_argument("--presets", default=str(LINE_PRESETS_PATH), help="Path to the line preset JSON file.")
    parser.add_argument("--point-a", default=None, help="Start point as x,y. Defaults to 20%% width, 72%% height.")
    parser.add_argument("--point-b", default=None, help="End point as x,y. Defaults to 80%% width, 72%% height.")
    parser.add_argument("--line-mode", choices=["simple", "string"], default="simple", help="Overlay algorithm to use.")
    parser.add_argument("--samples", type=int, default=96, help="Number of depth samples along the line.")
    parser.add_argument("--control-points", type=int, default=96, help="Number of string control points.")
    parser.add_argument("--search-radius", type=int, default=32, help="String snap search radius in pixels.")
    parser.add_argument("--candidate-step", type=int, default=2, help="Pixel step between string snap candidates.")
    parser.add_argument("--strength", type=float, default=60.0, help="Maximum visual displacement in pixels.")
    parser.add_argument("--smooth-window", type=int, default=9, help="Moving-average window for depth samples.")
    parser.add_argument("--axis", choices=["auto", "vertical", "normal"], default="auto", help="Direction used for visual displacement.")
    parser.add_argument(
        "--profile-mode",
        choices=["auto", "residual", "absolute"],
        default="auto",
        help="auto uses residual for simple mode and absolute for string mode.",
    )
    parser.add_argument("--invert-depth", action="store_true", help="Invert grayscale depth before sampling.")
    parser.add_argument("--offset-sign", type=float, default=1.0, help="Use -1 if the line bends in the wrong direction.")
    parser.add_argument("--snap-weight", type=float, default=1.0, help="String preference for depth-derived snap target.")
    parser.add_argument("--edge-weight", type=float, default=0.35, help="String preference for depth edges/ridges.")
    parser.add_argument("--smoothness", type=float, default=0.65, help="String penalty for abrupt neighbor motion.")
    parser.add_argument("--post-smooth", type=float, default=0.35, help="Final string smoothing amount.")
    parser.add_argument("--debug-string", action="store_true", help="Write a debug PNG showing string construction.")
    parser.add_argument("--debug-dir", default=str(OVERLAYS_DIR / "string_debug"), help="Folder for string debug images.")
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
        start, end = default_a, default_b

        if args.preset:
            start, end = load_line_preset(resolve_path(args.presets), args.preset)

        if args.point_a or args.point_b:
            if not args.point_a or not args.point_b:
                raise ValueError("Use both --point-a and --point-b, or use neither.")
            start = parse_point(args.point_a)
            end = parse_point(args.point_b)

        profile_mode = resolve_profile_mode(args.line_mode, args.profile_mode)
        axis = resolve_axis(args.line_mode, args.axis)
        terrain_config = TerrainLineConfig(
            samples=args.samples,
            strength=args.strength,
            smooth_window=args.smooth_window,
            axis=axis,
            profile_mode=profile_mode,
            invert_depth=args.invert_depth,
            offset_sign=args.offset_sign,
        )

        string_config = StringLineConfig(
            control_points=args.control_points,
            search_radius=args.search_radius,
            candidate_step=args.candidate_step,
            strength=args.strength,
            smooth_window=args.smooth_window,
            axis=axis,
            profile_mode=profile_mode,
            invert_depth=args.invert_depth,
            offset_sign=args.offset_sign,
            snap_weight=args.snap_weight,
            edge_weight=args.edge_weight,
            smoothness=args.smoothness,
            post_smooth=args.post_smooth,
        )

        overlay, comparison, debug_image, _points_data = render_result_with_mode(
            frame,
            depth_map,
            start,
            end,
            line_mode=args.line_mode,
            terrain_config=terrain_config,
            string_config=string_config,
            thickness=args.thickness,
            debug_string=args.debug_string,
        )
        overlay_path, comparison_path = write_overlay_outputs(frame_path, output_dir, overlay, comparison)
        debug_path = write_debug_output(frame_path, resolve_path(args.debug_dir), debug_image)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Frame: {frame_path.name}")
    print(f"Depth: {depth_path.name}")
    print(f"Point A: {start[0]:.1f},{start[1]:.1f}")
    print(f"Point B: {end[0]:.1f},{end[1]:.1f}")
    print(f"Line mode: {args.line_mode}")
    print(f"Saved overlay: {overlay_path}")
    print(f"Saved comparison: {comparison_path}")
    if debug_path:
        print(f"Saved debug: {debug_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
