from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

from common import (
    DEPTH_MAPS_DIR,
    FRAMES_DIR,
    OUTPUT_VIDEOS_DIR,
    OVERLAYS_DIR,
    SUPPORTED_IMAGE_EXTENSIONS,
    clear_folder_contents,
    collect_files,
    ensure_project_folders,
    resolve_path,
)
from overlay_renderer import find_matching_depth, load_frame_and_depth, render_result
from terrain_line import TerrainLineConfig, default_points, parse_point


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
) -> int:
    frames = collect_files(frames_dir, SUPPORTED_IMAGE_EXTENSIONS)
    if max_frames:
        frames = frames[:max_frames]

    output_dir.mkdir(parents=True, exist_ok=True)
    if video_output:
        video_output.parent.mkdir(parents=True, exist_ok=True)

    writer: cv2.VideoWriter | None = None
    saved_count = 0

    try:
        for frame_path in frames:
            depth_path = find_matching_depth(frame_path, depth_dir)
            frame, depth_map = load_frame_and_depth(frame_path, depth_path)
            height, width = depth_map.shape
            default_a, default_b = default_points(width, height)
            start = point_a if point_a else default_a
            end = point_b if point_b else default_b

            overlay, _comparison = render_result(frame, depth_map, start, end, config, thickness=thickness)

            overlay_path = output_dir / f"{frame_path.stem}_overlay.png"
            if not cv2.imwrite(str(overlay_path), overlay):
                raise RuntimeError(f"Could not write overlay image: {overlay_path}")

            if video_output:
                if writer is None:
                    frame_height, frame_width = overlay.shape[:2]
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    writer = cv2.VideoWriter(str(video_output), fourcc, fps, (frame_width, frame_height))
                    if not writer.isOpened():
                        raise RuntimeError(f"Could not open video writer: {video_output}")
                writer.write(overlay)

            saved_count += 1
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
    parser.add_argument("--point-a", default=None, help="Start point as x,y. Defaults to 20%% width, 72%% height.")
    parser.add_argument("--point-b", default=None, help="End point as x,y. Defaults to 80%% width, 72%% height.")
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

        video_output = None if args.no_video else resolve_path(args.video_output)
        saved_count = process_frames(
            frames_dir=resolve_path(args.frames_dir),
            depth_dir=resolve_path(args.depth_dir),
            output_dir=output_dir,
            video_output=video_output,
            point_a=parse_point(args.point_a) if args.point_a else None,
            point_b=parse_point(args.point_b) if args.point_b else None,
            config=config,
            thickness=args.thickness,
            max_frames=args.max_frames,
            fps=args.fps,
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
