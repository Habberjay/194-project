from __future__ import annotations

import argparse
import sys

from common import (
    DEPTH_MAPS_DIR,
    FRAMES_DIR,
    OUTPUT_DATA_DIR,
    OUTPUT_ROOT,
    OUTPUT_VIDEOS_DIR,
    OVERLAYS_DIR,
    PYTHON_ROOT,
    clear_folder_contents,
    ensure_project_folders,
    resolve_path,
)


DEFAULT_OUTPUT_FOLDERS = [
    FRAMES_DIR,
    DEPTH_MAPS_DIR,
    OUTPUT_ROOT / "depth_maps_normalized",
    OVERLAYS_DIR,
    OUTPUT_VIDEOS_DIR,
    OUTPUT_DATA_DIR,
]

LEGACY_OUTPUT_FOLDERS = [
    PYTHON_ROOT / "frames",
    PYTHON_ROOT / "depth_maps",
    PYTHON_ROOT / "depth_maps_normalized",
    PYTHON_ROOT / "overlays",
    PYTHON_ROOT / "output_videos",
    PYTHON_ROOT / "output_data",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean generated output folders.")
    parser.add_argument(
        "--folders",
        nargs="*",
        default=[str(path) for path in DEFAULT_OUTPUT_FOLDERS],
        help="Folders to clean. Relative paths are resolved from the python folder.",
    )
    parser.add_argument("--legacy", action="store_true", help="Also clean old pre-output/ generated folders.")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_project_folders()
    folders = [resolve_path(folder) for folder in args.folders]
    if args.legacy:
        folders.extend(path.resolve() for path in LEGACY_OUTPUT_FOLDERS if path.exists())

    if not args.yes:
        print("This will delete generated files from:")
        for folder in folders:
            print(f"  {folder}")
        answer = input("Continue? Type yes: ").strip().lower()
        if answer != "yes":
            print("Cancelled.")
            return 0

    try:
        for folder in folders:
            clear_folder_contents(folder)
            print(f"Cleaned: {folder}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
