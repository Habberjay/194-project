# Terrain-Conforming AR Blueprint Prototype

This workspace is the project root. It contains a simple offline pipeline:

```text
Input Video -> Extract Frames -> Depth Anything V2 depth maps -> Terrain-aware overlay -> Unity mesh experiments
```

The prototype intentionally avoids real-time AR, mobile inference, Docker, cloud APIs, networking features, ONNX, and advanced Unity render pipelines.

## Folders

```text
.
+-- PROJECT_PLAN.md
+-- COMMAND_GUIDE.md
+-- python/
|   +-- input_videos/
|   +-- output/
|   |   +-- frames/
|   |   +-- depth_maps/
|   |   +-- overlays/
|   |   +-- videos/
|   |   +-- data/
|   +-- scripts/
|   +-- checkpoints/
|   +-- line_presets.json
|   +-- requirements.txt
|   +-- README.md
+-- unity/
    +-- Assets/
    |   +-- Materials/
    |   +-- Scripts/
    |   +-- Textures/
    +-- README.md
```

## Quick Start

1. Open a terminal in `python/`.
2. Run `.\setup_venv.ps1`.
3. Run `.\.venv\Scripts\python.exe scripts\download_checkpoint.py`.
4. Put a video in `python/input_videos/`.
5. Run `.\.venv\Scripts\python.exe scripts\extract_frames.py --sample-fps 5 --clear`.
6. Run `.\.venv\Scripts\python.exe -B scripts\line_selector.py --preset site_line_1`.
7. Run `.\.venv\Scripts\python.exe -B scripts\run_offline_demo.py --preset site_line_1 --line-mode string --anchor-mode feature --depth-resnap light --sample-fps 5 --max-frames 60 --retries 2`.
8. Optional later step: import a PNG from `python/output/depth_maps/` into Unity and assign it to `DepthMapTerrainGenerator`.

See [python/README.md](python/README.md) and [unity/README.md](unity/README.md) for the practical workflow.

For a command-by-command usage guide, see [COMMAND_GUIDE.md](COMMAND_GUIDE.md).

## Current Focus

The current focus is the Python video prototype, not Unity. The main goal runner now builds a string-like line from many control points, anchors it to the scene using OpenCV feature tracking, lightly re-snaps it to depth, checks each pipeline stage, retries recoverable failures, and exports presentation outputs. Point A/B is only the first-frame placement; later frames are carried by visual scene features instead of fixed screen coordinates.

Generated files now live under `python/output/` so the source folder stays cleaner.

## References

- Depth Anything V2: https://github.com/DepthAnything/Depth-Anything-V2
- PyPI package: https://pypi.org/project/depth-anything-v2/
- Small checkpoint: https://huggingface.co/depth-anything/Depth-Anything-V2-Small
