from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
from pathlib import Path

import cv2

from common import (
    CHECKPOINTS_DIR,
    DEPTH_MAPS_DIR,
    FRAMES_DIR,
    INPUT_VIDEOS_DIR,
    LINE_PRESETS_PATH,
    OUTPUT_DATA_DIR,
    OUTPUT_VIDEOS_DIR,
    OVERLAYS_DIR,
    PYTHON_ROOT,
    SUPPORTED_IMAGE_EXTENSIONS,
    SUPPORTED_VIDEO_EXTENSIONS,
    collect_files,
    ensure_project_folders,
    resolve_path,
)
from line_presets import load_line_preset


def run_command(args: list[str], label: str) -> bool:
    print(f"\n== {label} ==")
    print(" ".join(args))
    sys.stdout.flush()
    result = subprocess.run(args, cwd=PYTHON_ROOT, text=True)
    if result.returncode != 0:
        print(f"Stage failed: {label} (exit {result.returncode})")
        return False
    return True


def python_command(script_name: str, extra_args: list[str]) -> list[str]:
    return [sys.executable, "-B", str(PYTHON_ROOT / "scripts" / script_name), *extra_args]


def count_images(folder: Path) -> int:
    try:
        return len(collect_files(folder, SUPPORTED_IMAGE_EXTENSIONS))
    except FileNotFoundError:
        return 0


def matched_depth_count() -> int:
    try:
        frames = collect_files(FRAMES_DIR, SUPPORTED_IMAGE_EXTENSIONS)
    except FileNotFoundError:
        return 0
    return sum(1 for frame in frames if (DEPTH_MAPS_DIR / f"{frame.stem}_depth.png").exists())


def verify_video(path: Path) -> tuple[bool, int]:
    if not path.exists() or path.stat().st_size == 0:
        return False, 0

    capture = cv2.VideoCapture(str(path))
    opened = capture.isOpened()
    frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) if opened else 0
    capture.release()
    return opened and frames > 0, frames


def preflight(args: argparse.Namespace) -> None:
    ensure_project_folders()

    for package_name in ("cv2", "numpy", "torch"):
        importlib.import_module(package_name)

    videos = collect_files(INPUT_VIDEOS_DIR, SUPPORTED_VIDEO_EXTENSIONS)
    if not videos:
        raise FileNotFoundError(f"No supported videos found in {INPUT_VIDEOS_DIR}")

    checkpoint = resolve_path(args.checkpoint)
    if not checkpoint.exists():
        raise FileNotFoundError(
            f"Checkpoint not found: {checkpoint}. Run scripts/download_checkpoint.py before the full demo."
        )

    if args.point_a and args.point_b:
        return
    if args.preset:
        load_line_preset(resolve_path(args.presets), args.preset)
    else:
        raise ValueError("Use --preset, or provide both --point-a and --point-b.")


def line_args(args: argparse.Namespace) -> list[str]:
    if args.point_a and args.point_b:
        return ["--point-a", args.point_a, "--point-b", args.point_b]
    if args.preset:
        return ["--preset", args.preset, "--presets", str(resolve_path(args.presets))]
    raise ValueError("Use --preset, or provide both --point-a and --point-b.")


def common_overlay_args(args: argparse.Namespace, safe_string: bool = False) -> list[str]:
    search_radius = 20 if safe_string else args.search_radius
    smoothness = 0.85 if safe_string else args.smoothness
    post_smooth = 0.5 if safe_string else args.post_smooth
    return [
        "--line-mode",
        args.line_mode,
        "--control-points",
        str(args.control_points),
        "--search-radius",
        str(search_radius),
        "--candidate-step",
        str(args.candidate_step),
        "--strength",
        str(args.strength),
        "--smooth-window",
        str(args.smooth_window),
        "--axis",
        args.axis,
        "--profile-mode",
        args.profile_mode,
        "--offset-sign",
        str(args.offset_sign),
        "--snap-weight",
        str(args.snap_weight),
        "--edge-weight",
        str(args.edge_weight),
        "--smoothness",
        str(smoothness),
        "--post-smooth",
        str(post_smooth),
        "--thickness",
        str(args.thickness),
    ]


def anchor_args(args: argparse.Namespace, safe_anchor: bool = False) -> list[str]:
    roi_padding = args.anchor_roi_padding + 80 if safe_anchor else args.anchor_roi_padding
    min_points = max(8, args.min_anchor_points // 2) if safe_anchor else args.min_anchor_points
    depth_resnap = "none" if safe_anchor else args.depth_resnap
    return [
        "--anchor-mode",
        args.anchor_mode,
        "--depth-resnap",
        depth_resnap,
        "--anchor-roi-padding",
        str(roi_padding),
        "--min-anchor-points",
        str(min_points),
        "--max-anchor-misses",
        str(args.max_anchor_misses),
    ]


def verify_anchor_quality(path: Path) -> tuple[bool, int, int]:
    if not path.exists():
        return False, 0, 0

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    frames = data.get("frames", [])
    anchor_frames = [frame for frame in frames if frame.get("anchor_mode") == "feature"]
    if not anchor_frames:
        return False, 0, 0

    good_frames = sum(1 for frame in anchor_frames if float(frame.get("anchor_confidence", 0.0)) > 0.0)
    required = max(1, len(anchor_frames) // 2)
    return good_frames >= required, good_frames, len(anchor_frames)


def extract_frames_stage(args: argparse.Namespace) -> None:
    attempts = [args.sample_fps, 3.0]
    for index, sample_fps in enumerate(attempts[: max(1, args.retries)]):
        command = python_command(
            "extract_frames.py",
            [
                "--sample-fps",
                str(sample_fps),
                "--max-frames",
                str(args.max_frames),
                "--clear",
            ],
        )
        if run_command(command, f"Extract frames attempt {index + 1}"):
            frame_count = count_images(FRAMES_DIR)
            print(f"Frame count: {frame_count}")
            if frame_count >= 2:
                return
            print("Frame extraction produced fewer than 2 frames; retrying with safer sampling.")

    raise RuntimeError("Frame extraction failed after retries.")


def depth_stage(args: argparse.Namespace) -> None:
    for index in range(max(1, args.retries)):
        command = python_command(
            "run_depth.py",
            [
                "--checkpoint",
                str(resolve_path(args.checkpoint)),
                "--clear",
            ],
        )
        if run_command(command, f"Depth generation attempt {index + 1}"):
            frame_count = count_images(FRAMES_DIR)
            depth_count = matched_depth_count()
            print(f"Matched depth maps: {depth_count}/{frame_count}")
            if depth_count == frame_count and depth_count > 0:
                return
            if depth_count > 0:
                print("Warning: depth count mismatch; matched frames will still be processed.")
                return
        print("Retrying depth generation.")

    raise RuntimeError("Depth generation failed after retries.")


def single_frame_stage(args: argparse.Namespace) -> None:
    base_command = [
        *line_args(args),
        "--output-dir",
        str(OVERLAYS_DIR / "string_single"),
        "--debug-dir",
        str(OVERLAYS_DIR / "string_debug"),
        "--debug-string",
        "--clear",
    ]
    attempts = [
        ("single-frame string overlay", [*common_overlay_args(args), *base_command]),
        ("single-frame string overlay with safer defaults", [*common_overlay_args(args, safe_string=True), *base_command]),
    ]

    for label, extra_args in attempts[: max(1, args.retries)]:
        if run_command(python_command("overlay_renderer.py", extra_args), label):
            if count_images(OVERLAYS_DIR) > 0:
                return

    fallback_args = [
        "--line-mode",
        "simple",
        *line_args(args),
        "--output-dir",
        str(OVERLAYS_DIR / "string_single"),
        "--clear",
    ]
    if run_command(python_command("overlay_renderer.py", fallback_args), "single-frame simple fallback"):
        print("Warning: string single-frame overlay failed; simple fallback output was created.")
        return

    raise RuntimeError("Single-frame overlay failed after retries and fallback.")


def video_stage(args: argparse.Namespace) -> bool:
    video_path = OUTPUT_VIDEOS_DIR / "terrain_string_demo_small.avi"
    string_sequence = OVERLAYS_DIR / "string_sequence"
    string_debug = OVERLAYS_DIR / "string_debug"
    points_path = OUTPUT_DATA_DIR / "string_points.json"

    scales = [args.video_scale, 0.35]
    for index, scale in enumerate(scales[: max(1, args.retries)]):
        safe_anchor = index > 0
        command = python_command(
            "process_video.py",
            [
                *line_args(args),
                *common_overlay_args(args),
                *anchor_args(args, safe_anchor=safe_anchor),
                "--temporal-memory",
                str(args.temporal_memory),
                "--debug-string",
                "--output-dir",
                str(string_sequence),
                "--debug-dir",
                str(string_debug),
                "--anchor-debug-dir",
                str(OVERLAYS_DIR / "anchor_debug"),
                "--output-data",
                str(points_path),
                "--video-output",
                str(video_path),
                "--fourcc",
                "MJPG",
                "--video-scale",
                str(scale),
                "--fps",
                str(args.fps),
                "--max-tracking-failures",
                str(args.max_tracking_failures),
                "--clear",
            ],
        )
        if not run_command(command, f"multi-frame string video attempt {index + 1}"):
            continue

        ok, frame_count = verify_video(video_path)
        anchor_ok, good_anchor_frames, total_anchor_frames = verify_anchor_quality(points_path)
        print(f"Video verification: opened={ok}, frames={frame_count}")
        if args.anchor_mode == "feature":
            print(f"Anchor verification: good={good_anchor_frames}/{total_anchor_frames}")
        if ok:
            if args.anchor_mode == "feature" and not anchor_ok and index < max(1, args.retries) - 1:
                print("Anchor quality was weak; retrying with safer anchor settings.")
                continue
            if args.anchor_mode == "feature" and not anchor_ok:
                print("Warning: anchor quality remained weak; keeping generated outputs for inspection.")
            return True
        print("Video was not readable; retrying with a smaller scale.")

    no_video_command = python_command(
        "process_video.py",
        [
            *line_args(args),
            *common_overlay_args(args),
            *anchor_args(args, safe_anchor=True),
            "--temporal-memory",
            str(args.temporal_memory),
            "--debug-string",
            "--output-dir",
            str(string_sequence),
            "--debug-dir",
            str(string_debug),
            "--anchor-debug-dir",
            str(OVERLAYS_DIR / "anchor_debug"),
            "--output-data",
            str(points_path),
            "--no-video",
            "--max-tracking-failures",
            str(args.max_tracking_failures),
            "--clear",
        ],
    )
    if run_command(no_video_command, "multi-frame string image fallback"):
        print("Warning: video export failed; PNG sequence will be used as the visual deliverable.")
        return False

    raise RuntimeError("Multi-frame string processing failed.")


def contact_sheet_stage() -> None:
    command = python_command(
        "make_contact_sheet.py",
        [
            "--input-dir",
            str(OVERLAYS_DIR / "string_sequence"),
            "--output",
            str(OVERLAYS_DIR / "string_contact_sheet.png"),
        ],
    )
    if not run_command(command, "Create string contact sheet"):
        raise RuntimeError("Contact sheet generation failed.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full offline terrain-string demo with checks and retries.")
    parser.add_argument("--preset", default="site_line_1", help="Line preset name from line_presets.json.")
    parser.add_argument("--presets", default=str(LINE_PRESETS_PATH), help="Path to line preset JSON.")
    parser.add_argument("--point-a", default=None, help="Manual start point as x,y.")
    parser.add_argument("--point-b", default=None, help="Manual end point as x,y.")
    parser.add_argument("--checkpoint", default=str(CHECKPOINTS_DIR / "depth_anything_v2_vits.pth"))
    parser.add_argument("--sample-fps", type=float, default=5.0)
    parser.add_argument("--max-frames", type=int, default=60)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--line-mode", choices=["simple", "string"], default="string")
    parser.add_argument("--control-points", type=int, default=96)
    parser.add_argument("--search-radius", type=int, default=32)
    parser.add_argument("--candidate-step", type=int, default=2)
    parser.add_argument("--strength", type=float, default=60.0)
    parser.add_argument("--smooth-window", type=int, default=9)
    parser.add_argument("--axis", choices=["auto", "vertical", "normal"], default="auto")
    parser.add_argument("--profile-mode", choices=["auto", "residual", "absolute"], default="auto")
    parser.add_argument("--offset-sign", type=float, default=1.0)
    parser.add_argument("--snap-weight", type=float, default=1.0)
    parser.add_argument("--edge-weight", type=float, default=0.35)
    parser.add_argument("--smoothness", type=float, default=0.65)
    parser.add_argument("--post-smooth", type=float, default=0.35)
    parser.add_argument("--temporal-memory", type=float, default=0.0)
    parser.add_argument("--anchor-mode", choices=["none", "feature"], default="feature")
    parser.add_argument("--depth-resnap", choices=["none", "light", "full"], default="light")
    parser.add_argument("--anchor-roi-padding", type=int, default=160)
    parser.add_argument("--min-anchor-points", type=int, default=20)
    parser.add_argument("--max-anchor-misses", type=int, default=5)
    parser.add_argument("--max-tracking-failures", type=int, default=3)
    parser.add_argument("--thickness", type=int, default=4)
    parser.add_argument("--fps", type=float, default=6.0)
    parser.add_argument("--video-scale", type=float, default=0.5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        preflight(args)
        extract_frames_stage(args)
        depth_stage(args)
        single_frame_stage(args)
        video_ok = video_stage(args)
        contact_sheet_stage()
    except Exception as exc:
        print(f"\nFull offline demo failed: {exc}", file=sys.stderr)
        return 1

    print("\nFull offline demo complete.")
    print(f"String sequence: {OVERLAYS_DIR / 'string_sequence'}")
    print(f"String debug: {OVERLAYS_DIR / 'string_debug'}")
    print(f"Anchor debug: {OVERLAYS_DIR / 'anchor_debug'}")
    print(f"Contact sheet: {OVERLAYS_DIR / 'string_contact_sheet.png'}")
    print(f"Point data: {OUTPUT_DATA_DIR / 'string_points.json'}")
    if video_ok:
        print(f"Video: {OUTPUT_VIDEOS_DIR / 'terrain_string_demo_small.avi'}")
    else:
        print("Video export was skipped after retries; use the PNG sequence/contact sheet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
