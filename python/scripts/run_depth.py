from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import torch

from common import (
    CHECKPOINTS_DIR,
    DEPTH_MAPS_DIR,
    FRAMES_DIR,
    SUPPORTED_IMAGE_EXTENSIONS,
    clear_folder_contents,
    collect_files,
    ensure_project_folders,
    normalize_to_uint8,
    resolve_path,
)


MODEL_CONFIGS = {
    "vits": {"encoder": "vits", "features": 64, "out_channels": [48, 96, 192, 384]},
}


def choose_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load_depth_model(checkpoint_path: Path, device: str):
    try:
        from depth_anything_v2.dpt import DepthAnythingV2
    except ImportError as exc:
        raise ImportError("Depth Anything V2 is not installed. Run: pip install -r requirements.txt") from exc

    if not checkpoint_path.exists():
        raise FileNotFoundError(
            f"Checkpoint not found: {checkpoint_path}. "
            "Run scripts/download_checkpoint.py or place depth_anything_v2_vits.pth in checkpoints/."
        )

    model = DepthAnythingV2(**MODEL_CONFIGS["vits"])

    try:
        state_dict = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    except TypeError:
        state_dict = torch.load(checkpoint_path, map_location="cpu")

    model.load_state_dict(state_dict)
    model = model.to(device).eval()
    return model


def run_depth(
    input_path: Path,
    output_dir: Path,
    checkpoint_path: Path,
    input_size: int,
    max_images: int,
    invert: bool,
    clear: bool,
) -> int:
    if input_size < 224:
        raise ValueError("--input-size should be at least 224.")

    if max_images < 0:
        raise ValueError("--max-images must be 0 or greater.")

    images = collect_files(input_path, SUPPORTED_IMAGE_EXTENSIONS)
    if max_images:
        images = images[:max_images]

    output_dir.mkdir(parents=True, exist_ok=True)
    if clear:
        clear_folder_contents(output_dir)

    device = choose_device()
    print(f"Using device: {device}")
    print("Using Depth Anything V2 encoder: vits")

    model = load_depth_model(checkpoint_path, device)
    saved_count = 0

    with torch.inference_mode():
        for image_path in images:
            raw_image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if raw_image is None:
                print(f"Skipping unreadable image: {image_path}")
                continue

            depth = model.infer_image(raw_image, input_size=input_size)
            depth_image = normalize_to_uint8(depth)

            if invert:
                depth_image = 255 - depth_image

            output_path = output_dir / f"{image_path.stem}_depth.png"
            if not cv2.imwrite(str(output_path), depth_image):
                raise RuntimeError(f"Could not write depth map: {output_path}")

            saved_count += 1
            print(f"Saved: {output_path.name}")

    if saved_count == 0:
        raise ValueError("No depth maps were generated. Check that the input images are readable.")

    return saved_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate grayscale Depth Anything V2 depth maps.")
    parser.add_argument(
        "--input",
        default=str(FRAMES_DIR),
        help="Input image file or folder. Relative paths are resolved from the python folder.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEPTH_MAPS_DIR),
        help="Folder for grayscale depth maps. Relative paths are resolved from the python folder.",
    )
    parser.add_argument(
        "--checkpoint",
        default=str(CHECKPOINTS_DIR / "depth_anything_v2_vits.pth"),
        help="Path to depth_anything_v2_vits.pth.",
    )
    parser.add_argument("--input-size", type=int, default=518, help="Depth Anything V2 input size.")
    parser.add_argument("--max-images", type=int, default=0, help="Maximum images to process. Use 0 for all.")
    parser.add_argument("--invert", action="store_true", help="Invert the saved grayscale depth map.")
    parser.add_argument("--clear", action="store_true", help="Clean the output folder before writing depth maps.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_project_folders()

    try:
        count = run_depth(
            input_path=resolve_path(args.input),
            output_dir=resolve_path(args.output_dir),
            checkpoint_path=resolve_path(args.checkpoint),
            input_size=args.input_size,
            max_images=args.max_images,
            invert=args.invert,
            clear=args.clear,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Generated {count} grayscale depth map(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
