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
    OUTPUT_VIDEOS_DIR,
    OVERLAYS_DIR,
    SUPPORTED_IMAGE_EXTENSIONS,
    clear_folder_contents,
    collect_files,
    ensure_project_folders,
    resolve_path,
)
from line_presets import load_line_preset
from overlay_renderer import draw_label, draw_lines, find_matching_depth, load_frame_and_depth
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
    previous_points = support_points.reshape((-1, 1, 2))
    next_points, status, _error = cv2.calcOpticalFlowPyrLK(
        previous_gray,
        current_gray,
        previous_points,
        None,
        winSize=(31, 31),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )

    if next_points is None or status is None:
        return start, end, False

    good_mask = status.reshape(-1).astype(bool)
    if int(good_mask.sum()) < 3:
        return start, end, False

    previous_good = support_points[good_mask]
    next_good = next_points.reshape((-1, 2))[good_mask]
    displacement = np.median(next_good - previous_good, axis=0)

    next_start = clamp_point(tuple(start_array + displacement), width, height)
    next_end = clamp_point(tuple(end_array + displacement), width, height)
    return next_start, next_end, True


def render_overlay_with_memory(
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


def prepare_video_frame(image: np.ndarray, video_scale: float) -> np.ndarray:
    if video_scale <= 0.0:
        raise ValueError("--video-scale must be greater than 0.")

    if abs(video_scale - 1.0) < 1e-6:
        return image

    height, width = image.shape[:2]
    scaled_width = max(2, int(round(width * video_scale)))
    scaled_height = max(2, int(round(height * video_scale)))

    # Some video encoders are picky about odd frame dimensions.
    if scaled_width % 2:
        scaled_width -= 1
    if scaled_height % 2:
        scaled_height -= 1

    return cv2.resize(image, (scaled_width, scaled_height), interpolation=cv2.INTER_AREA)


def process_frames(
    frames_dir: Path,
    depth_dir: Path,
    output_dir: Path,
    video_output: Path | None,
    point_a: tuple[float, float] | None,
    point_b: tuple[float, float] | None,
    config: TerrainLineConfig,
    thickness: int,
    max_frames: int,
    fps: float,
    track_points: bool,
    temporal_memory: float,
    video_scale: float,
    fourcc_code: str,
) -> int:
    if temporal_memory < 0.0 or temporal_memory >= 1.0:
        raise ValueError("--temporal-memory must be at least 0.0 and less than 1.0.")
    if len(fourcc_code) != 4:
        raise ValueError("--fourcc must be exactly four characters, such as mp4v or MJPG.")

    frames = collect_files(frames_dir, SUPPORTED_IMAGE_EXTENSIONS)
    if max_frames:
        frames = frames[:max_frames]

    output_dir.mkdir(parents=True, exist_ok=True)
    if video_output:
        video_output.parent.mkdir(parents=True, exist_ok=True)

    writer: cv2.VideoWriter | None = None
    saved_count = 0
    previous_gray: np.ndarray | None = None
    previous_offsets: np.ndarray | None = None
    current_start = point_a
    current_end = point_b

    try:
        for frame_path in frames:
            depth_path = find_matching_depth(frame_path, depth_dir)
            frame, depth_map = load_frame_and_depth(frame_path, depth_path)
            height, width = depth_map.shape
            default_a, default_b = default_points(width, height)
            current_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            if current_start is None or current_end is None:
                current_start, current_end = default_a, default_b
            elif track_points and previous_gray is not None:
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

            overlay, previous_offsets = render_overlay_with_memory(
                frame,
                depth_map,
                current_start,
                current_end,
                config,
                thickness=thickness,
                previous_offsets=previous_offsets,
                temporal_memory=temporal_memory,
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

    return saved_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply terrain-aware overlay rendering to a sequence of extracted frames.")
    parser.add_argument("--frames-dir", default=str(FRAMES_DIR), help="Folder containing extracted RGB frames.")
    parser.add_argument("--depth-dir", default=str(DEPTH_MAPS_DIR), help="Folder containing matching depth maps.")
    parser.add_argument("--output-dir", default=str(OVERLAYS_DIR / "sequence"), help="Folder for per-frame overlay images.")
    parser.add_argument(
        "--video-output",
        default=str(OUTPUT_VIDEOS_DIR / "terrain_overlay_demo.mp4"),
        help="Output MP4 path. Use --no-video to skip video writing.",
    )
    parser.add_argument("--no-video", action="store_true", help="Do not write a video file.")
    parser.add_argument("--preset", default=None, help="Line preset name from line_presets.json.")
    parser.add_argument("--presets", default=str(LINE_PRESETS_PATH), help="Path to the line preset JSON file.")
    parser.add_argument("--point-a", default=None, help="Start point as x,y. Defaults to 20%% width, 72%% height.")
    parser.add_argument("--point-b", default=None, help="End point as x,y. Defaults to 80%% width, 72%% height.")
    parser.add_argument("--track-points", action="store_true", help="Track the two line endpoints across frames with optical flow.")
    parser.add_argument(
        "--temporal-memory",
        type=float,
        default=0.0,
        help="Blend each frame's bend with the previous bend. Use 0.5-0.8 for smoother persistence.",
    )
    parser.add_argument("--samples", type=int, default=96)
    parser.add_argument("--strength", type=float, default=60.0)
    parser.add_argument("--smooth-window", type=int, default=9)
    parser.add_argument("--axis", choices=["vertical", "normal"], default="vertical")
    parser.add_argument("--profile-mode", choices=["residual", "absolute"], default="residual")
    parser.add_argument("--invert-depth", action="store_true")
    parser.add_argument("--offset-sign", type=float, default=1.0)
    parser.add_argument("--thickness", type=int, default=4)
    parser.add_argument("--max-frames", type=int, default=0, help="Maximum frames to process. Use 0 for all.")
    parser.add_argument("--fps", type=float, default=6.0, help="Output demo video frame rate.")
    parser.add_argument("--video-scale", type=float, default=1.0, help="Scale the exported video frames. Use 0.5 for easier playback.")
    parser.add_argument("--fourcc", default="mp4v", help="FourCC codec for video output. Try MJPG with an .avi output.")
    parser.add_argument("--clear", action="store_true", help="Clean the output folder before writing.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_project_folders()

    try:
        output_dir = resolve_path(args.output_dir)
        if args.clear:
            clear_folder_contents(output_dir)

        config = TerrainLineConfig(
            samples=args.samples,
            strength=args.strength,
            smooth_window=args.smooth_window,
            axis=args.axis,
            profile_mode=args.profile_mode,
            invert_depth=args.invert_depth,
            offset_sign=args.offset_sign,
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
            config=config,
            thickness=args.thickness,
            max_frames=args.max_frames,
            fps=args.fps,
            track_points=args.track_points,
            temporal_memory=args.temporal_memory,
            video_scale=args.video_scale,
            fourcc_code=args.fourcc,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Generated {saved_count} overlay frame(s).")
    if video_output:
        print(f"Saved video: {video_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
