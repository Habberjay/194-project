from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

from common import (
    FRAMES_DIR,
    INPUT_VIDEOS_DIR,
    SUPPORTED_VIDEO_EXTENSIONS,
    clear_folder_contents,
    collect_files,
    ensure_project_folders,
    is_supported_file,
    resolve_path,
)


def find_default_video() -> Path:
    videos = collect_files(INPUT_VIDEOS_DIR, SUPPORTED_VIDEO_EXTENSIONS)
    if len(videos) > 1:
        print(f"Multiple videos found. Using the first one: {videos[0].name}")
    return videos[0]


def extract_frames(
    video_path: Path,
    output_dir: Path,
    frame_step: int | None,
    sample_fps: float,
    max_frames: int,
    image_extension: str,
    clear: bool,
) -> int:
    if not video_path.exists():
        raise FileNotFoundError(f"Video does not exist: {video_path}")

    if not is_supported_file(video_path, SUPPORTED_VIDEO_EXTENSIONS):
        supported = ", ".join(sorted(SUPPORTED_VIDEO_EXTENSIONS))
        raise ValueError(f"Unsupported video format: {video_path.suffix}. Supported: {supported}")

    if frame_step is not None and frame_step < 1:
        raise ValueError("--frame-step must be 1 or greater.")

    if sample_fps <= 0:
        raise ValueError("--sample-fps must be greater than 0.")

    if max_frames < 0:
        raise ValueError("--max-frames must be 0 or greater.")

    output_dir.mkdir(parents=True, exist_ok=True)
    if clear:
        clear_folder_contents(output_dir)

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames == 0:
        print("Warning: OpenCV reports 0 frames. The script will still try to read the video.")

    source_fps = float(capture.get(cv2.CAP_PROP_FPS))
    if frame_step is None:
        if source_fps > 0:
            frame_step = max(1, int(round(source_fps / sample_fps)))
        else:
            frame_step = max(1, int(round(30.0 / sample_fps)))
            print("Warning: OpenCV could not read the video FPS. Assuming 30 FPS for sampling.")

    if source_fps > 0:
        effective_sample_fps = source_fps / frame_step
        print(f"Video FPS: {source_fps:.2f}. Saving about {effective_sample_fps:.2f} frame(s) per second.")
    print(f"Frame step: {frame_step}")

    saved_count = 0
    frame_index = 0
    image_extension = image_extension.lstrip(".").lower()
    stem = video_path.stem

    while True:
        success, frame = capture.read()
        if not success:
            break

        if frame_index % frame_step == 0:
            output_path = output_dir / f"{stem}_frame_{saved_count:05d}.{image_extension}"
            if not cv2.imwrite(str(output_path), frame):
                raise RuntimeError(f"Could not write frame: {output_path}")

            saved_count += 1
            if max_frames and saved_count >= max_frames:
                break

        frame_index += 1

    capture.release()

    if saved_count == 0:
        raise ValueError("No frames were extracted. The video may be empty or unreadable.")

    return saved_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract still frames from a video.")
    parser.add_argument(
        "--video",
        default=None,
        help="Video path. If omitted, the first supported video in input_videos/ is used.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(FRAMES_DIR),
        help="Folder for extracted frames. Relative paths are resolved from the python folder.",
    )
    parser.add_argument(
        "--sample-fps",
        type=float,
        default=5.0,
        help="Target number of frames to save per second when --frame-step is not set.",
    )
    parser.add_argument(
        "--frame-step",
        type=int,
        default=None,
        help="Save one frame every N frames. Overrides --sample-fps when provided.",
    )
    parser.add_argument("--max-frames", type=int, default=60, help="Maximum frames to save. Use 0 for no limit.")
    parser.add_argument("--image-extension", choices=["png", "jpg", "jpeg"], default="png")
    parser.add_argument("--clear", action="store_true", help="Clean the output folder before extraction.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_project_folders()

    try:
        video_path = resolve_path(args.video) if args.video else find_default_video()
        output_dir = resolve_path(args.output_dir)
        saved_count = extract_frames(
            video_path=video_path,
            output_dir=output_dir,
            frame_step=args.frame_step,
            sample_fps=args.sample_fps,
            max_frames=args.max_frames,
            image_extension=args.image_extension,
            clear=args.clear,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Extracted {saved_count} frame(s) to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
