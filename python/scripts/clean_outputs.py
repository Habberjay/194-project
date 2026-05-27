from __future__ import annotations

import argparse
import sys

from common import (
    DEPTH_MAPS_DIR,
    FRAMES_DIR,
    OUTPUT_ROOT,
    PYTHON_ROOT,
    UNITY_EXPORT_DIR,
    clear_folder_contents,
    ensure_project_folders,
    resolve_path,
)


DEFAULT_OUTPUT_FOLDERS = [
    FRAMES_DIR,
    DEPTH_MAPS_DIR,
    UNITY_EXPORT_DIR,
]

LEGACY_OUTPUT_FOLDERS = [
    OUTPUT_ROOT / "data",
    OUTPUT_ROOT / "depth_maps_normalized",
    OUTPUT_ROOT / "overlays",
    OUTPUT_ROOT / "unity_demo",
    OUTPUT_ROOT / "videos",
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
    legacy_folders = []
    if args.legacy:
        legacy_folders = [path.resolve() for path in LEGACY_OUTPUT_FOLDERS if path.exists()]

    if not args.yes:
        print("This will delete generated files from:")
        for folder in folders:
            print(f"  {folder}")
        for folder in legacy_folders:
            print(f"  {folder} (legacy folder will be removed)")
        answer = input("Continue? Type yes: ").strip().lower()
        if answer != "yes":
            print("Cancelled.")
            return 0

    try:
        for folder in folders:
            clear_folder_contents(folder)
            print(f"Cleaned: {folder}")
        for folder in legacy_folders:
            clear_folder_contents(folder, keep_names=set())
            folder.rmdir()
            print(f"Removed legacy folder: {folder}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
