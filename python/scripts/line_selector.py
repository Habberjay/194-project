from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

from common import FRAMES_DIR, LINE_PRESETS_PATH, SUPPORTED_IMAGE_EXTENSIONS, collect_files, ensure_project_folders, resolve_path
from line_presets import save_line_preset


WINDOW_NAME = "Select terrain line"


def find_default_frame() -> Path:
    frames = collect_files(FRAMES_DIR, SUPPORTED_IMAGE_EXTENSIONS)
    if len(frames) > 1:
        print(f"Multiple frames found. Using the first one: {frames[0].name}")
    return frames[0]


def display_scale(width: int, height: int, max_width: int, max_height: int) -> float:
    return min(max_width / float(width), max_height / float(height), 1.0)


def draw_selector_view(image: np.ndarray, points: list[tuple[float, float]], scale: float) -> np.ndarray:
    display = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    cv2.rectangle(display, (0, 0), (display.shape[1], 58), (0, 0, 0), thickness=-1)
    cv2.putText(
        display,
        "Click point A, click point B. S save, R reset, Q quit.",
        (12, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        display,
        f"Selected points: {len(points)}/2",
        (12, 48),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (180, 240, 255),
        1,
        cv2.LINE_AA,
    )

    scaled_points = [(int(round(x * scale)), int(round(y * scale))) for x, y in points]
    for index, point in enumerate(scaled_points):
        cv2.circle(display, point, radius=6, color=(255, 255, 255), thickness=-1, lineType=cv2.LINE_AA)
        cv2.circle(display, point, radius=9, color=(0, 0, 0), thickness=2, lineType=cv2.LINE_AA)
        cv2.putText(
            display,
            "A" if index == 0 else "B",
            (point[0] + 10, point[1] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.72,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )

    if len(scaled_points) == 2:
        cv2.line(display, scaled_points[0], scaled_points[1], (0, 210, 255), 3, cv2.LINE_AA)

    return display


def select_points(
    image: np.ndarray,
    scale: float,
    preset_name: str,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    points: list[tuple[float, float]] = []

    def on_mouse(event: int, x: int, y: int, _flags: int, _userdata: object) -> None:
        if event != cv2.EVENT_LBUTTONDOWN or len(points) >= 2:
            return
        points.append((x / scale, y / scale))

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(WINDOW_NAME, on_mouse)

    print(f"Selecting preset '{preset_name}'. Click two points, then press S to save.")

    while True:
        view = draw_selector_view(image, points, scale)
        cv2.imshow(WINDOW_NAME, view)
        key = cv2.waitKey(30) & 0xFF

        if key in (ord("q"), 27):
            cv2.destroyWindow(WINDOW_NAME)
            return None

        if key == ord("r"):
            points.clear()

        if key == ord("s"):
            if len(points) != 2:
                print("Select two points before saving.")
                continue
            cv2.destroyWindow(WINDOW_NAME)
            return points[0], points[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Click two points on a frame and save them as a reusable line preset.")
    parser.add_argument("--frame", default=None, help="Frame image. Defaults to the first image in output/frames/.")
    parser.add_argument("--preset", default="default", help="Preset name to save.")
    parser.add_argument("--output", default=str(LINE_PRESETS_PATH), help="JSON file for saved line presets.")
    parser.add_argument("--max-width", type=int, default=1200, help="Maximum display width.")
    parser.add_argument("--max-height", type=int, default=800, help="Maximum display height.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_project_folders()

    try:
        frame_path = resolve_path(args.frame) if args.frame else find_default_frame()
        image = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Could not read frame: {frame_path}")

        height, width = image.shape[:2]
        scale = display_scale(width, height, args.max_width, args.max_height)
        selected = select_points(image, scale, args.preset)
        if selected is None:
            print("Cancelled.")
            return 0

        point_a, point_b = selected
        output_path = resolve_path(args.output)
        save_line_preset(output_path, args.preset, frame_path, point_a, point_b, image_size=(width, height))
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Saved preset '{args.preset}' to {output_path}")
    print(f"Point A: {point_a[0]:.1f},{point_a[1]:.1f}")
    print(f"Point B: {point_b[0]:.1f},{point_b[1]:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
