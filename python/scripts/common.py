from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable

import numpy as np


PYTHON_ROOT = Path(__file__).resolve().parents[1]
INPUT_VIDEOS_DIR = PYTHON_ROOT / "input_videos"
FRAMES_DIR = PYTHON_ROOT / "frames"
DEPTH_MAPS_DIR = PYTHON_ROOT / "depth_maps"
OVERLAYS_DIR = PYTHON_ROOT / "overlays"
OUTPUT_VIDEOS_DIR = PYTHON_ROOT / "output_videos"
CHECKPOINTS_DIR = PYTHON_ROOT / "checkpoints"
LINE_PRESETS_PATH = PYTHON_ROOT / "line_presets.json"

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}


def ensure_project_folders() -> None:
    for folder in (INPUT_VIDEOS_DIR, FRAMES_DIR, DEPTH_MAPS_DIR, OVERLAYS_DIR, OUTPUT_VIDEOS_DIR, CHECKPOINTS_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def resolve_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = PYTHON_ROOT / path
    return path.resolve()


def is_supported_file(path: Path, extensions: set[str]) -> bool:
    return path.suffix.lower() in extensions


def collect_files(input_path: Path, extensions: set[str], recursive: bool = False) -> list[Path]:
    if input_path.is_file():
        if not is_supported_file(input_path, extensions):
            supported = ", ".join(sorted(extensions))
            raise ValueError(f"Unsupported file type: {input_path}. Supported: {supported}")
        return [input_path]

    if not input_path.exists():
        raise FileNotFoundError(f"Path does not exist: {input_path}")

    if not input_path.is_dir():
        raise ValueError(f"Path is not a file or folder: {input_path}")

    iterator: Iterable[Path] = input_path.rglob("*") if recursive else input_path.iterdir()
    files = sorted(path for path in iterator if path.is_file() and is_supported_file(path, extensions))

    if not files:
        supported = ", ".join(sorted(extensions))
        raise FileNotFoundError(f"No supported files found in {input_path}. Supported: {supported}")

    return files


def normalize_to_uint8(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=np.float32)
    finite_mask = np.isfinite(array)

    if not finite_mask.any():
        return np.zeros(array.shape, dtype=np.uint8)

    clean = np.where(finite_mask, array, np.nan)
    min_value = float(np.nanmin(clean))
    max_value = float(np.nanmax(clean))

    if max_value <= min_value:
        return np.zeros(array.shape, dtype=np.uint8)

    normalized = (clean - min_value) / (max_value - min_value)
    normalized = np.nan_to_num(normalized, nan=0.0, posinf=1.0, neginf=0.0)
    return np.clip(normalized * 255.0, 0, 255).astype(np.uint8)


def clear_folder_contents(folder: Path, keep_names: set[str] | None = None) -> None:
    folder = folder.resolve()
    root = PYTHON_ROOT.resolve()
    keep_names = keep_names or {".gitkeep"}

    if folder == root or root not in folder.parents:
        raise ValueError(f"Refusing to clean outside the Python project folder: {folder}")

    folder.mkdir(parents=True, exist_ok=True)

    for item in folder.iterdir():
        if item.name in keep_names:
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
