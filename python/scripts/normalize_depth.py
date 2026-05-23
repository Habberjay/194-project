from __future__ import annotations

import argparse
import sys

import cv2

from common import (
    DEPTH_MAPS_DIR,
    SUPPORTED_IMAGE_EXTENSIONS,
    clear_folder_contents,
    collect_files,
    ensure_project_folders,
    normalize_to_uint8,
    resolve_path,
)


def normalize_depth_images(input_path, output_dir, suffix: str, invert: bool, clear: bool) -> int:
    images = collect_files(input_path, SUPPORTED_IMAGE_EXTENSIONS)

    output_dir.mkdir(parents=True, exist_ok=True)
    if clear:
        clear_folder_contents(output_dir)

    saved_count = 0
    for image_path in images:
        image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            print(f"Skipping unreadable image: {image_path}")
            continue

        normalized = normalize_to_uint8(image)
        if invert:
            normalized = 255 - normalized

        output_path = output_dir / f"{image_path.stem}{suffix}.png"
        if not cv2.imwrite(str(output_path), normalized):
            raise RuntimeError(f"Could not write image: {output_path}")

        saved_count += 1
        print(f"Saved: {output_path.name}")

    if saved_count == 0:
        raise ValueError("No normalized images were written.")

    return saved_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize grayscale depth maps to the full 0-255 range.")
    parser.add_argument(
        "--input",
        default=str(DEPTH_MAPS_DIR),
        help="Input depth image or folder. Relative paths are resolved from the python folder.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEPTH_MAPS_DIR.parent / "depth_maps_normalized"),
        help="Folder for normalized depth maps.",
    )
    parser.add_argument("--suffix", default="_normalized", help="Suffix for output filenames.")
    parser.add_argument("--invert", action="store_true", help="Invert output grayscale values.")
    parser.add_argument("--clear", action="store_true", help="Clean the output folder before writing images.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_project_folders()

    try:
        count = normalize_depth_images(
            input_path=resolve_path(args.input),
            output_dir=resolve_path(args.output_dir),
            suffix=args.suffix,
            invert=args.invert,
            clear=args.clear,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Normalized {count} depth map(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
