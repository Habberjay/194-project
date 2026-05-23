from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

from common import CHECKPOINTS_DIR, ensure_project_folders, resolve_path


VITS_CHECKPOINT_URL = (
    "https://huggingface.co/depth-anything/Depth-Anything-V2-Small/resolve/main/"
    "depth_anything_v2_vits.pth?download=true"
)
CHECKPOINT_NAME = "depth_anything_v2_vits.pth"


def progress(block_count: int, block_size: int, total_size: int) -> None:
    if total_size <= 0:
        return
    downloaded = min(block_count * block_size, total_size)
    percent = downloaded * 100 / total_size
    print(f"\rDownloading checkpoint: {percent:5.1f}%", end="")


def download_checkpoint(output_path: Path, force: bool) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and not force:
        print(f"Checkpoint already exists: {output_path}")
        print("Use --force to download it again.")
        return

    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")

    try:
        urllib.request.urlretrieve(VITS_CHECKPOINT_URL, temp_path, progress)
        print("")
    except urllib.error.URLError as exc:
        if temp_path.exists():
            temp_path.unlink()
        raise RuntimeError(f"Could not download checkpoint: {exc}") from exc

    if temp_path.stat().st_size < 1_000_000:
        temp_path.unlink()
        raise RuntimeError("Downloaded file is unexpectedly small. Check your internet connection and try again.")

    temp_path.replace(output_path)
    print(f"Saved checkpoint: {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download the Depth Anything V2 Small vits checkpoint.")
    parser.add_argument(
        "--output",
        default=str(CHECKPOINTS_DIR / CHECKPOINT_NAME),
        help="Checkpoint output path. Relative paths are resolved from the python folder.",
    )
    parser.add_argument("--force", action="store_true", help="Download again even if the checkpoint already exists.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_project_folders()
    output_path = resolve_path(args.output)

    try:
        download_checkpoint(output_path, args.force)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
