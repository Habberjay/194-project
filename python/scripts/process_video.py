from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

from anchor_tracker import AnchorConfig, AnchorTrackResult, FeatureAnchorTracker, draw_anchor_debug
from common import (
    DEPTH_MAPS_DIR,
    FRAMES_DIR,
    LINE_PRESETS_PATH,
    OUTPUT_DATA_DIR,
    OUTPUT_VIDEOS_DIR,
    OVERLAYS_DIR,
    SUPPORTED_IMAGE_EXTENSIONS,
    clear_folder_contents,
    collect_files,
    ensure_project_folders,
    resolve_path,
)
from line_presets import load_line_preset
from overlay_renderer import (
    draw_label,
    draw_lines,
    draw_string_debug,
    find_matching_depth,
    load_frame_and_depth,
    resolve_axis,
    resolve_profile_mode,
)
from string_line import StringLineConfig, build_string_line, string_points_to_json
from terrain_line import (
    TerrainLineConfig,
    build_terrain_line,
    clamp_points_to_image,
    default_points,
    displacement_vector,
    parse_point,
)


def clamp_point(point: tuple[float, float], width: int, height: int) -> tuple[float, float]:
    return float(np.clip(point[0], 0, width - 1)), float(np.clip(point[1], 0, height - 1))


def track_line_points(
    previous_gray: np.ndarray,
    current_gray: np.ndarray,
    start: tuple[float, float],
    end: tuple[float, float],
    width: int,
    height: int,
) -> tuple[tuple[float, float], tuple[float, float], bool]:
    start_array = np.asarray(start, dtype=np.float32)
    end_array = np.asarray(end, dtype=np.float32)
    weights = np.linspace(0.0, 1.0, 11, dtype=np.float32)[:, None]
    support_points = start_array + (end_array - start_array) * weights
    tracked_points, ratio, tracked = track_control_points(previous_gray, current_gray, support_points, width, height)

    if not tracked and ratio <= 0.0:
        return start, end, False

    displacement = np.median(tracked_points - support_points, axis=0)
    next_start = clamp_point(tuple(start_array + displacement), width, height)
    next_end = clamp_point(tuple(end_array + displacement), width, height)
    return next_start, next_end, tracked


def track_control_points(
    previous_gray: np.ndarray,
    current_gray: np.ndarray,
    previous_points: np.ndarray,
    width: int,
    height: int,
    min_good_ratio: float = 0.35,
) -> tuple[np.ndarray, float, bool]:
    previous_points = np.asarray(previous_points, dtype=np.float32)
    if previous_points.ndim != 2 or previous_points.shape[1] != 2:
        raise ValueError("previous_points must have shape (N, 2).")

    previous_cv = previous_points.reshape((-1, 1, 2))
    next_points, status, _error = cv2.calcOpticalFlowPyrLK(
        previous_gray,
        current_gray,
        previous_cv,
        None,
        winSize=(31, 31),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )

    if next_points is None or status is None:
        return previous_points.copy(), 0.0, False

    good_mask = status.reshape(-1).astype(bool)
    good_count = int(good_mask.sum())
    ratio = good_count / float(previous_points.shape[0])
    if good_count == 0:
        return previous_points.copy(), 0.0, False

    next_flat = next_points.reshape((-1, 2))
    displacement = np.median(next_flat[good_mask] - previous_points[good_mask], axis=0)
    predicted = previous_points + displacement
    predicted[good_mask] = next_flat[good_mask]
    predicted = clamp_points_to_image(predicted, width=width, height=height)
    return predicted.astype(np.float32), ratio, ratio >= min_good_ratio


def render_simple_overlay_with_memory(
    frame: np.ndarray,
    depth_map: np.ndarray,
    start: tuple[float, float],
    end: tuple[float, float],
    config: TerrainLineConfig,
    thickness: int,
    previous_offsets: np.ndarray | None,
    temporal_memory: float,
) -> tuple[np.ndarray, np.ndarray]:
    result = build_terrain_line(depth_map, start, end, config)
    offsets = result.offsets

    if previous_offsets is not None and previous_offsets.shape == offsets.shape and temporal_memory > 0.0:
        offsets = (previous_offsets * temporal_memory) + (offsets * (1.0 - temporal_memory))

    vector = displacement_vector(start, end, config.axis)
    terrain_points = result.baseline_points + offsets[:, None] * vector[None, :]
    height, width = depth_map.shape
    terrain_points = clamp_points_to_image(terrain_points, width=width, height=height)

    overlay = draw_lines(frame, start, end, terrain_points, include_flat=True, include_terrain=True, thickness=thickness)
    draw_label(overlay, "Persistent terrain-aware overlay")
    return overlay, offsets.astype(np.float32)


def render_string_overlay_with_memory(
    frame: np.ndarray,
    depth_map: np.ndarray,
    start: tuple[float, float],
    end: tuple[float, float],
    config: StringLineConfig,
    thickness: int,
    predicted_points: np.ndarray | None,
    previous_points: np.ndarray | None,
    temporal_memory: float,
    debug_string: bool,
) -> tuple[np.ndarray, np.ndarray | None, np.ndarray, dict[str, object]]:
    result = build_string_line(depth_map, start, end, config, predicted_points=predicted_points)
    string_points = result.string_points

    if previous_points is not None and previous_points.shape == string_points.shape and temporal_memory > 0.0:
        string_points = (previous_points * temporal_memory) + (string_points * (1.0 - temporal_memory))
        height, width = depth_map.shape
        string_points = clamp_points_to_image(string_points, width=width, height=height)
        result = replace(result, string_points=string_points)

    overlay = draw_lines(frame, start, end, string_points, include_flat=True, include_terrain=True, thickness=thickness)
    draw_label(overlay, "Persistent terrain-aware string overlay")
    debug = draw_string_debug(frame, depth_map, start, end, result, thickness) if debug_string else None
    points_data = {
        "string_points": string_points_to_json(string_points),
        "raw_points": string_points_to_json(result.raw_points),
        "chosen_offsets": [round(float(value), 3) for value in result.chosen_offsets],
    }
    return overlay, debug, string_points.astype(np.float32), points_data


def light_resnap_config(config: StringLineConfig) -> StringLineConfig:
    return replace(
        config,
        search_radius=min(12, config.search_radius),
        strength=min(12.0, config.strength),
        snap_weight=min(0.5, config.snap_weight),
        edge_weight=min(0.2, config.edge_weight),
        smoothness=max(0.85, config.smoothness),
        post_smooth=max(0.45, config.post_smooth),
    )


def apply_depth_resnap(
    depth_map: np.ndarray,
    projected_points: np.ndarray,
    string_config: StringLineConfig,
    depth_resnap: str,
) -> tuple[np.ndarray, dict[str, object]]:
    if depth_resnap == "none":
        return projected_points.astype(np.float32), {
            "string_points": string_points_to_json(projected_points),
            "raw_points": string_points_to_json(projected_points),
            "chosen_offsets": [],
        }

    config = light_resnap_config(string_config) if depth_resnap == "light" else string_config
    start = tuple(projected_points[0])
    end = tuple(projected_points[-1])
    result = build_string_line(depth_map, start, end, config, predicted_points=projected_points)
    return result.string_points.astype(np.float32), {
        "string_points": string_points_to_json(result.string_points),
        "raw_points": string_points_to_json(result.raw_points),
        "chosen_offsets": [round(float(value), 3) for value in result.chosen_offsets],
    }


def initial_anchor_result(
    tracker: FeatureAnchorTracker,
    points: np.ndarray,
) -> AnchorTrackResult:
    inliers = np.ones(tracker.reference_points.shape[0], dtype=bool)
    return AnchorTrackResult(
        transform=np.eye(3, dtype=np.float32),
        projected_points=points.astype(np.float32),
        tracked_points=tracker.current_points.astype(np.float32),
        reference_points=tracker.reference_points.astype(np.float32),
        inlier_mask=inliers,
        roi=tracker.roi,
        good_points=int(tracker.current_points.shape[0]),
        inliers=int(inliers.sum()),
        confidence=1.0,
        transform_kind="identity",
        reused_last_transform=False,
        missed_frames=0,
    )


def prepare_video_frame(image: np.ndarray, video_scale: float) -> np.ndarray:
    if video_scale <= 0.0:
        raise ValueError("--video-scale must be greater than 0.")

    if abs(video_scale - 1.0) < 1e-6:
        return image

    height, width = image.shape[:2]
    scaled_width = max(2, int(round(width * video_scale)))
    scaled_height = max(2, int(round(height * video_scale)))

    if scaled_width % 2:
        scaled_width -= 1
    if scaled_height % 2:
        scaled_height -= 1

    return cv2.resize(image, (scaled_width, scaled_height), interpolation=cv2.INTER_AREA)


def matched_frame_depth_pairs(frames_dir: Path, depth_dir: Path, max_frames: int) -> list[tuple[Path, Path]]:
    frames = collect_files(frames_dir, SUPPORTED_IMAGE_EXTENSIONS)
    if max_frames:
        frames = frames[:max_frames]

    pairs: list[tuple[Path, Path]] = []
    for frame_path in frames:
        try:
            pairs.append((frame_path, find_matching_depth(frame_path, depth_dir)))
        except FileNotFoundError as exc:
            print(f"Warning: {exc}")

    if not pairs:
        raise ValueError("No matched frame/depth pairs were found.")

    return pairs


def write_points_data(output_path: Path | None, records: list[dict[str, object]]) -> None:
    if output_path is None:
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump({"frames": records}, file, indent=2)
        file.write("\n")


def process_frames(
    frames_dir: Path,
    depth_dir: Path,
    output_dir: Path,
    video_output: Path | None,
    point_a: tuple[float, float] | None,
    point_b: tuple[float, float] | None,
    terrain_config: TerrainLineConfig,
    string_config: StringLineConfig,
    line_mode: str,
    thickness: int,
    max_frames: int,
    fps: float,
    track_points: bool,
    temporal_memory: float,
    video_scale: float,
    fourcc_code: str,
    debug_string: bool,
    debug_dir: Path,
    anchor_debug_dir: Path,
    output_data: Path | None,
    max_tracking_failures: int,
    anchor_mode: str,
    depth_resnap: str,
    anchor_config: AnchorConfig,
) -> int:
    if temporal_memory < 0.0 or temporal_memory >= 1.0:
        raise ValueError("--temporal-memory must be at least 0.0 and less than 1.0.")
    if len(fourcc_code) != 4:
        raise ValueError("--fourcc must be exactly four characters, such as mp4v or MJPG.")
    if line_mode not in {"simple", "string"}:
        raise ValueError(f"Unsupported line mode: {line_mode}")
    if anchor_mode not in {"none", "feature"}:
        raise ValueError(f"Unsupported anchor mode: {anchor_mode}")
    if depth_resnap not in {"none", "light", "full"}:
        raise ValueError(f"Unsupported depth re-snap mode: {depth_resnap}")
    if anchor_mode == "feature" and line_mode != "string":
        raise ValueError("--anchor-mode feature requires --line-mode string.")

    pairs = matched_frame_depth_pairs(frames_dir, depth_dir, max_frames)
    output_dir.mkdir(parents=True, exist_ok=True)
    if debug_string:
        debug_dir.mkdir(parents=True, exist_ok=True)
    if anchor_mode == "feature":
        anchor_debug_dir.mkdir(parents=True, exist_ok=True)
    if video_output:
        video_output.parent.mkdir(parents=True, exist_ok=True)

    writer: cv2.VideoWriter | None = None
    saved_count = 0
    previous_gray: np.ndarray | None = None
    previous_offsets: np.ndarray | None = None
    previous_string_points: np.ndarray | None = None
    anchor_string_points: np.ndarray | None = None
    anchor_tracker: FeatureAnchorTracker | None = None
    current_start = point_a
    current_end = point_b
    tracking_enabled = track_points
    tracking_failures = 0
    point_records: list[dict[str, object]] = []

    try:
        for frame_path, depth_path in pairs:
            frame, depth_map = load_frame_and_depth(frame_path, depth_path)
            height, width = depth_map.shape
            default_a, default_b = default_points(width, height)
            current_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            if current_start is None or current_end is None:
                current_start, current_end = default_a, default_b

            tracking_ratio = 1.0
            tracked = False
            predicted_string_points: np.ndarray | None = None

            if line_mode == "simple":
                if tracking_enabled and previous_gray is not None:
                    current_start, current_end, tracked = track_line_points(
                        previous_gray,
                        current_gray,
                        current_start,
                        current_end,
                        width,
                        height,
                    )
                    if not tracked:
                        print(f"Warning: point tracking failed for {frame_path.name}; using previous endpoints.")

                overlay, previous_offsets = render_simple_overlay_with_memory(
                    frame,
                    depth_map,
                    current_start,
                    current_end,
                    terrain_config,
                    thickness=thickness,
                    previous_offsets=previous_offsets,
                    temporal_memory=temporal_memory,
                )
                point_records.append(
                    {
                        "frame": frame_path.name,
                        "mode": "simple",
                        "point_a": [round(float(current_start[0]), 2), round(float(current_start[1]), 2)],
                        "point_b": [round(float(current_end[0]), 2), round(float(current_end[1]), 2)],
                        "tracked": tracked,
                    }
                )
            elif anchor_mode == "feature":
                if anchor_tracker is None:
                    first_result = build_string_line(depth_map, current_start, current_end, string_config)
                    anchor_string_points = first_result.string_points.astype(np.float32)
                    anchor_tracker = FeatureAnchorTracker(current_gray, anchor_string_points, anchor_config)
                    anchor_result = initial_anchor_result(anchor_tracker, anchor_string_points)
                    projected_points = anchor_string_points
                    string_points = anchor_string_points
                    points_data = {
                        "string_points": string_points_to_json(string_points),
                        "raw_points": string_points_to_json(first_result.raw_points),
                        "chosen_offsets": [round(float(value), 3) for value in first_result.chosen_offsets],
                    }
                else:
                    if anchor_string_points is None:
                        raise RuntimeError("Anchor string was not initialized.")
                    anchor_result = anchor_tracker.project(current_gray, anchor_string_points)
                    projected_points = anchor_result.projected_points
                    string_points, points_data = apply_depth_resnap(
                        depth_map,
                        projected_points,
                        string_config,
                        depth_resnap,
                    )
                    current_start = tuple(projected_points[0])
                    current_end = tuple(projected_points[-1])

                overlay = draw_lines(frame, current_start, current_end, string_points, include_flat=False, include_terrain=True, thickness=thickness)
                draw_label(overlay, f"Feature-anchored terrain string ({depth_resnap} depth re-snap)")

                if debug_string:
                    if anchor_result.reused_last_transform:
                        print(
                            f"Warning: anchor tracking weak for {frame_path.name}; "
                            f"reused transform after {anchor_result.missed_frames} miss(es)."
                        )
                    anchor_debug = draw_anchor_debug(frame, anchor_result, projected_points, string_points, thickness)
                    anchor_debug_path = anchor_debug_dir / f"{frame_path.stem}_anchor_debug.png"
                    if not cv2.imwrite(str(anchor_debug_path), anchor_debug):
                        raise RuntimeError(f"Could not write anchor debug image: {anchor_debug_path}")

                point_records.append(
                    {
                        "frame": frame_path.name,
                        "mode": "string",
                        "anchor_mode": "feature",
                        "depth_resnap": depth_resnap,
                        "anchor_good_points": anchor_result.good_points,
                        "anchor_inliers": anchor_result.inliers,
                        "anchor_confidence": round(float(anchor_result.confidence), 4),
                        "anchor_transform_kind": anchor_result.transform_kind,
                        "anchor_reused_last_transform": anchor_result.reused_last_transform,
                        "anchor_missed_frames": anchor_result.missed_frames,
                        "transform": [[round(float(value), 6) for value in row] for row in anchor_result.transform],
                        **points_data,
                    }
                )
            else:
                if previous_string_points is not None:
                    predicted_string_points = previous_string_points
                    if tracking_enabled and previous_gray is not None:
                        predicted_string_points, tracking_ratio, tracked = track_control_points(
                            previous_gray,
                            current_gray,
                            previous_string_points,
                            width,
                            height,
                        )
                        if not tracked:
                            tracking_failures += 1
                            print(
                                f"Warning: string tracking weak for {frame_path.name} "
                                f"({tracking_ratio:.0%} good points); using predicted string."
                            )
                            if tracking_failures > max_tracking_failures:
                                tracking_enabled = False
                                print("Warning: too many tracking failures; disabling optical-flow tracking.")
                        else:
                            tracking_failures = 0

                    current_start = tuple(predicted_string_points[0])
                    current_end = tuple(predicted_string_points[-1])

                overlay, debug_image, previous_string_points, points_data = render_string_overlay_with_memory(
                    frame,
                    depth_map,
                    current_start,
                    current_end,
                    string_config,
                    thickness=thickness,
                    predicted_points=predicted_string_points,
                    previous_points=previous_string_points,
                    temporal_memory=temporal_memory,
                    debug_string=debug_string,
                )

                if debug_image is not None:
                    debug_path = debug_dir / f"{frame_path.stem}_string_debug.png"
                    if not cv2.imwrite(str(debug_path), debug_image):
                        raise RuntimeError(f"Could not write debug image: {debug_path}")

                point_records.append(
                    {
                        "frame": frame_path.name,
                        "mode": "string",
                        "anchor_mode": "none",
                        "depth_resnap": "full",
                        "tracked": tracked,
                        "tracking_ratio": round(float(tracking_ratio), 4),
                        **points_data,
                    }
                )

            overlay_path = output_dir / f"{frame_path.stem}_overlay.png"
            if not cv2.imwrite(str(overlay_path), overlay):
                raise RuntimeError(f"Could not write overlay image: {overlay_path}")

            if video_output:
                video_frame = prepare_video_frame(overlay, video_scale)
                if writer is None:
                    frame_height, frame_width = video_frame.shape[:2]
                    fourcc = cv2.VideoWriter_fourcc(*fourcc_code)
                    writer = cv2.VideoWriter(str(video_output), fourcc, fps, (frame_width, frame_height))
                    if not writer.isOpened():
                        raise RuntimeError(f"Could not open video writer: {video_output}")
                writer.write(video_frame)

            saved_count += 1
            previous_gray = current_gray
            print(f"Saved: {overlay_path.name}")
    finally:
        if writer is not None:
            writer.release()

    if saved_count == 0:
        raise ValueError("No overlay frames were generated.")

    write_points_data(output_data, point_records)
    return saved_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply terrain-aware overlay rendering to a sequence of extracted frames.")
    parser.add_argument("--frames-dir", default=str(FRAMES_DIR), help="Folder containing extracted RGB frames.")
    parser.add_argument("--depth-dir", default=str(DEPTH_MAPS_DIR), help="Folder containing matching depth maps.")
    parser.add_argument("--output-dir", default=None, help="Folder for per-frame overlay images.")
    parser.add_argument("--debug-dir", default=str(OVERLAYS_DIR / "string_debug"), help="Folder for string debug images.")
    parser.add_argument("--anchor-debug-dir", default=str(OVERLAYS_DIR / "anchor_debug"), help="Folder for feature-anchor debug images.")
    parser.add_argument("--output-data", default=str(OUTPUT_DATA_DIR / "string_points.json"), help="JSON output for string points.")
    parser.add_argument(
        "--video-output",
        default=str(OUTPUT_VIDEOS_DIR / "terrain_overlay_demo.mp4"),
        help="Output video path. Use --no-video to skip video writing.",
    )
    parser.add_argument("--no-video", action="store_true", help="Do not write a video file.")
    parser.add_argument("--preset", default=None, help="Line preset name from line_presets.json.")
    parser.add_argument("--presets", default=str(LINE_PRESETS_PATH), help="Path to the line preset JSON file.")
    parser.add_argument("--point-a", default=None, help="Start point as x,y. Defaults to 20%% width, 72%% height.")
    parser.add_argument("--point-b", default=None, help="End point as x,y. Defaults to 80%% width, 72%% height.")
    parser.add_argument("--line-mode", choices=["simple", "string"], default="simple", help="Overlay algorithm to use.")
    parser.add_argument("--anchor-mode", choices=["none", "feature"], default="none", help="Scene anchoring method for string mode.")
    parser.add_argument("--depth-resnap", choices=["none", "light", "full"], default="light", help="Depth correction after feature anchoring.")
    parser.add_argument("--anchor-roi-padding", type=int, default=160, help="Pixels around the first-frame string used for feature anchoring.")
    parser.add_argument("--min-anchor-points", type=int, default=20, help="Minimum feature inliers needed for a valid anchor update.")
    parser.add_argument("--max-anchor-misses", type=int, default=5, help="Frames allowed to reuse the last anchor transform.")
    parser.add_argument("--track-points", action="store_true", help="Track line/string points across frames with optical flow.")
    parser.add_argument(
        "--temporal-memory",
        type=float,
        default=0.0,
        help="Blend each frame's geometry with the previous frame. Use 0.5-0.8 for smoother persistence.",
    )
    parser.add_argument("--samples", type=int, default=96, help="Simple-mode sample count.")
    parser.add_argument("--control-points", type=int, default=96, help="String-mode control point count.")
    parser.add_argument("--search-radius", type=int, default=32, help="String snap search radius in pixels.")
    parser.add_argument("--candidate-step", type=int, default=2, help="Pixel step between string snap candidates.")
    parser.add_argument("--strength", type=float, default=60.0, help="Maximum visual displacement in pixels.")
    parser.add_argument("--smooth-window", type=int, default=9)
    parser.add_argument("--axis", choices=["auto", "vertical", "normal"], default="auto")
    parser.add_argument("--profile-mode", choices=["auto", "residual", "absolute"], default="auto")
    parser.add_argument("--invert-depth", action="store_true")
    parser.add_argument("--offset-sign", type=float, default=1.0)
    parser.add_argument("--snap-weight", type=float, default=1.0)
    parser.add_argument("--edge-weight", type=float, default=0.35)
    parser.add_argument("--smoothness", type=float, default=0.65)
    parser.add_argument("--post-smooth", type=float, default=0.35)
    parser.add_argument("--debug-string", action="store_true")
    parser.add_argument("--max-tracking-failures", type=int, default=3)
    parser.add_argument("--thickness", type=int, default=4)
    parser.add_argument("--max-frames", type=int, default=0, help="Maximum frames to process. Use 0 for all.")
    parser.add_argument("--fps", type=float, default=6.0, help="Output demo video frame rate.")
    parser.add_argument("--video-scale", type=float, default=1.0, help="Scale the exported video frames. Use 0.5 for easier playback.")
    parser.add_argument("--fourcc", default="mp4v", help="FourCC codec for video output. Try MJPG with an .avi output.")
    parser.add_argument("--clear", action="store_true", help="Clean the output folders before writing.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_project_folders()

    try:
        output_dir = resolve_path(args.output_dir) if args.output_dir else OVERLAYS_DIR / ("string_sequence" if args.line_mode == "string" else "sequence")
        debug_dir = resolve_path(args.debug_dir)
        anchor_debug_dir = resolve_path(args.anchor_debug_dir)
        output_data = resolve_path(args.output_data) if args.output_data else None
        if args.clear:
            clear_folder_contents(output_dir)
            if args.debug_string:
                clear_folder_contents(debug_dir)
            if args.anchor_mode == "feature":
                clear_folder_contents(anchor_debug_dir)

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
        anchor_config = AnchorConfig(
            roi_padding=args.anchor_roi_padding,
            min_points=args.min_anchor_points,
            max_misses=args.max_anchor_misses,
        )

        point_a = None
        point_b = None
        if args.preset:
            point_a, point_b = load_line_preset(resolve_path(args.presets), args.preset)
        if args.point_a or args.point_b:
            if not args.point_a or not args.point_b:
                raise ValueError("Use both --point-a and --point-b, or use neither.")
            point_a = parse_point(args.point_a)
            point_b = parse_point(args.point_b)

        video_output = None if args.no_video else resolve_path(args.video_output)
        saved_count = process_frames(
            frames_dir=resolve_path(args.frames_dir),
            depth_dir=resolve_path(args.depth_dir),
            output_dir=output_dir,
            video_output=video_output,
            point_a=point_a,
            point_b=point_b,
            terrain_config=terrain_config,
            string_config=string_config,
            line_mode=args.line_mode,
            thickness=args.thickness,
            max_frames=args.max_frames,
            fps=args.fps,
            track_points=args.track_points,
            temporal_memory=args.temporal_memory,
            video_scale=args.video_scale,
            fourcc_code=args.fourcc,
            debug_string=args.debug_string,
            debug_dir=debug_dir,
            anchor_debug_dir=anchor_debug_dir,
            output_data=output_data,
            max_tracking_failures=args.max_tracking_failures,
            anchor_mode=args.anchor_mode,
            depth_resnap=args.depth_resnap,
            anchor_config=anchor_config,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Generated {saved_count} overlay frame(s).")
    print(f"Output frames: {output_dir}")
    if output_data:
        print(f"Saved point data: {output_data}")
    if video_output:
        print(f"Saved video: {video_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
