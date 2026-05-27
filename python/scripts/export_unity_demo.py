from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import cv2

from common import (
    DEPTH_MAPS_DIR,
    FRAMES_DIR,
    LINE_PRESETS_PATH,
    UNITY_EXPORT_DIR,
    clear_folder_contents,
    ensure_project_folders,
    resolve_path,
)
from line_presets import load_line_preset, load_presets
from pipeline_helpers import (
    default_line_points,
    find_default_frame,
    find_matching_depth,
    load_frame_and_depth,
    parse_point,
    relative_to_python_root,
)


def frame_from_preset(presets_path: Path, preset_name: str) -> Path | None:
    presets = load_presets(presets_path)
    preset = presets.get(preset_name)
    if not isinstance(preset, dict):
        return None

    frame_value = preset.get("frame")
    if not isinstance(frame_value, str) or not frame_value.strip():
        return None

    candidate = resolve_path(frame_value)
    if candidate.exists():
        return candidate

    fallback = FRAMES_DIR / Path(frame_value).name
    if fallback.exists():
        return fallback

    return None


def normalized_point(point: tuple[float, float], width: int, height: int) -> dict[str, float]:
    max_x = max(width - 1, 1)
    max_y = max(height - 1, 1)
    return {
        "x": round(float(point[0]) / float(max_x), 6),
        "y": round(float(point[1]) / float(max_y), 6),
    }


def write_metadata(
    output_path: Path,
    frame_path: Path,
    depth_path: Path,
    preset_name: str | None,
    point_a: tuple[float, float],
    point_b: tuple[float, float],
    width: int,
    height: int,
    samples: int,
    terrain_size: float,
    terrain_height_scale: float,
) -> None:
    metadata = {
        "version": 1,
        "purpose": "single_frame_depth_mesh_surface_line_demo",
        "frame": "frame.png",
        "depth": "depth.png",
        "preset": preset_name or "",
        "source_frame": relative_to_python_root(frame_path),
        "source_depth": relative_to_python_root(depth_path),
        "image_width": int(width),
        "image_height": int(height),
        "point_a_pixels": {"x": round(float(point_a[0]), 2), "y": round(float(point_a[1]), 2)},
        "point_b_pixels": {"x": round(float(point_b[0]), 2), "y": round(float(point_b[1]), 2)},
        "point_a_normalized": normalized_point(point_a, width, height),
        "point_b_normalized": normalized_point(point_b, width, height),
        "unity": {
            "terrain_size": float(terrain_size),
            "terrain_height_scale": float(terrain_height_scale),
            "line_samples": int(samples),
            "flip_image_y": True,
            "recommended_surface_offset": 0.03,
            "recommended_flat_height_offset": 0.6,
        },
        "notes": [
            "Assign depth.png to DepthMapTerrainGenerator.depthMap.",
            "Assign frame.png to DepthMapTerrainGenerator.blueprintTexture for visual reference.",
            "Assign line_metadata.json as a TextAsset to SurfaceConformingLine.lineMetadata.",
        ],
    }

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=2)
        file.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export one frame/depth/line bundle for the Unity 3D surface demo.")
    parser.add_argument("--frame", default=None, help="Frame image. Defaults to preset frame or first output/frames image.")
    parser.add_argument("--depth", default=None, help="Depth image. Defaults to matching *_depth.png in output/depth_maps.")
    parser.add_argument("--depth-dir", default=str(DEPTH_MAPS_DIR), help="Depth map folder used for matching.")
    parser.add_argument("--preset", default="site_line_1", help="Line preset name from line_presets.json.")
    parser.add_argument("--presets", default=str(LINE_PRESETS_PATH), help="Path to line preset JSON.")
    parser.add_argument("--point-a", default=None, help="Manual start point as x,y. Overrides preset.")
    parser.add_argument("--point-b", default=None, help="Manual end point as x,y. Overrides preset.")
    parser.add_argument("--output-dir", default=str(UNITY_EXPORT_DIR), help="Output folder for Unity export assets.")
    parser.add_argument("--samples", type=int, default=96, help="Recommended Unity line sample count.")
    parser.add_argument("--terrain-size", type=float, default=10.0, help="Recommended Unity terrain size.")
    parser.add_argument("--terrain-height-scale", type=float, default=2.0, help="Recommended Unity height scale.")
    parser.add_argument("--clear", action="store_true", help="Clean output folder before exporting.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_project_folders()

    try:
        output_dir = resolve_path(args.output_dir)
        if args.clear:
            clear_folder_contents(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        presets_path = resolve_path(args.presets)
        frame_path = resolve_path(args.frame) if args.frame else frame_from_preset(presets_path, args.preset)
        if frame_path is None:
            frame_path = find_default_frame()

        depth_path = resolve_path(args.depth) if args.depth else find_matching_depth(frame_path, resolve_path(args.depth_dir))
        frame, depth_map = load_frame_and_depth(frame_path, depth_path)
        height, width = frame.shape[:2]

        point_a, point_b = default_line_points(width, height)
        preset_name = args.preset if args.preset else None
        if args.preset:
            point_a, point_b = load_line_preset(presets_path, args.preset)

        if args.point_a or args.point_b:
            if not args.point_a or not args.point_b:
                raise ValueError("Use both --point-a and --point-b, or use neither.")
            point_a = parse_point(args.point_a)
            point_b = parse_point(args.point_b)
            preset_name = None

        frame_output = output_dir / "frame.png"
        depth_output = output_dir / "depth.png"
        metadata_output = output_dir / "line_metadata.json"

        shutil.copy2(frame_path, frame_output)
        if depth_map.shape[:2] == (height, width):
            shutil.copy2(depth_path, depth_output)
        else:
            if not cv2.imwrite(str(depth_output), depth_map):
                raise RuntimeError(f"Could not write resized depth image: {depth_output}")

        write_metadata(
            metadata_output,
            frame_path,
            depth_path,
            preset_name,
            point_a,
            point_b,
            width,
            height,
            args.samples,
            args.terrain_size,
            args.terrain_height_scale,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Exported Unity assets to: {output_dir}")
    print(f"Frame: {frame_output}")
    print(f"Depth: {depth_output}")
    print(f"Metadata: {metadata_output}")
    print(f"Point A normalized: {normalized_point(point_a, width, height)}")
    print(f"Point B normalized: {normalized_point(point_b, width, height)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
