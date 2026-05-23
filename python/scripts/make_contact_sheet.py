from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import cv2
import numpy as np

from common import OVERLAYS_DIR, SUPPORTED_IMAGE_EXTENSIONS, collect_files, ensure_project_folders, resolve_path


def resize_to_height(image: np.ndarray, target_height: int) -> np.ndarray:
    height, width = image.shape[:2]
    if height == target_height:
        return image

    target_width = max(1, int(round(width * (target_height / float(height)))))
    return cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_AREA)


def make_contact_sheet(
    input_dir: Path,
    output_path: Path,
    columns: int,
    thumb_height: int,
    max_images: int,
) -> int:
    if columns < 1:
        raise ValueError("--columns must be at least 1.")
    if thumb_height < 32:
        raise ValueError("--thumb-height must be at least 32.")

    image_paths = collect_files(input_dir, SUPPORTED_IMAGE_EXTENSIONS)
    if max_images:
        image_paths = image_paths[:max_images]

    thumbnails: list[np.ndarray] = []
    for image_path in image_paths:
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            print(f"Skipping unreadable image: {image_path}")
            continue
        thumbnails.append(resize_to_height(image, thumb_height))

    if not thumbnails:
        raise ValueError(f"No readable images found in {input_dir}")

    thumb_width = max(image.shape[1] for image in thumbnails)
    rows = math.ceil(len(thumbnails) / columns)
    sheet = np.full((rows * thumb_height, columns * thumb_width, 3), 20, dtype=np.uint8)

    for index, thumbnail in enumerate(thumbnails):
        row = index // columns
        column = index % columns
        y = row * thumb_height
        x = column * thumb_width
        sheet[y : y + thumbnail.shape[0], x : x + thumbnail.shape[1]] = thumbnail

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), sheet):
        raise RuntimeError(f"Could not write contact sheet: {output_path}")

    return len(thumbnails)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create one PNG preview sheet from overlay frame images.")
    parser.add_argument("--input-dir", default=str(OVERLAYS_DIR / "sequence"), help="Folder containing overlay frame images.")
    parser.add_argument("--output", default=str(OVERLAYS_DIR / "contact_sheet.png"), help="Output PNG path.")
    parser.add_argument("--columns", type=int, default=3, help="Number of thumbnails per row.")
    parser.add_argument("--thumb-height", type=int, default=480, help="Thumbnail height in pixels.")
    parser.add_argument("--max-images", type=int, default=0, help="Maximum images to include. Use 0 for all.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_project_folders()

    try:
        count = make_contact_sheet(
            input_dir=resolve_path(args.input_dir),
            output_path=resolve_path(args.output),
            columns=args.columns,
            thumb_height=args.thumb_height,
            max_images=args.max_images,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Created contact sheet with {count} image(s): {resolve_path(args.output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
