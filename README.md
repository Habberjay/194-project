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
|   +-- frames/
|   +-- depth_maps/
|   +-- overlays/
|   +-- output_videos/
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
6. Run `.\.venv\Scripts\python.exe scripts\run_depth.py --clear`.
7. Run `.\.venv\Scripts\python.exe -B scripts\line_selector.py --preset site_line_1`.
8. Run `.\.venv\Scripts\python.exe -B scripts\overlay_renderer.py --preset site_line_1 --clear`.
9. Optional: run `.\.venv\Scripts\python.exe -B scripts\process_video.py --preset site_line_1 --track-points --temporal-memory 0.65 --clear`.
10. Optional: run `.\.venv\Scripts\python.exe -B scripts\make_contact_sheet.py` for a PNG preview.
11. Optional later step: import a PNG from `python/depth_maps/` into Unity and assign it to `DepthMapTerrainGenerator`.

See [python/README.md](python/README.md) and [unity/README.md](unity/README.md) for the practical workflow.

For a command-by-command usage guide, see [COMMAND_GUIDE.md](COMMAND_GUIDE.md).

## Current Focus

The current focus is the Python video prototype, not Unity. The next research upgrade is to move from a two-endpoint bending line toward a string-like line made of many control points that can track and conform to depth changes across frames.

## References

- Depth Anything V2: https://github.com/DepthAnything/Depth-Anything-V2
- PyPI package: https://pypi.org/project/depth-anything-v2/
- Small checkpoint: https://huggingface.co/depth-anything/Depth-Anything-V2-Small
