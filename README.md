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
+-- python/
|   +-- input_videos/
|   +-- frames/
|   +-- depth_maps/
|   +-- overlays/
|   +-- output_videos/
|   +-- scripts/
|   +-- checkpoints/
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
5. Run `.\.venv\Scripts\python.exe scripts\extract_frames.py --clear`.
6. Run `.\.venv\Scripts\python.exe scripts\run_depth.py --clear`.
7. Run `.\.venv\Scripts\python.exe -B scripts\line_selector.py --preset site_line_1`.
8. Run `.\.venv\Scripts\python.exe -B scripts\overlay_renderer.py --preset site_line_1 --clear`.
9. Optional: run `.\.venv\Scripts\python.exe -B scripts\process_video.py --preset site_line_1 --track-points --clear`.
10. Optional later step: import a PNG from `python/depth_maps/` into Unity and assign it to `DepthMapTerrainGenerator`.

See [python/README.md](python/README.md) and [unity/README.md](unity/README.md) for the practical workflow.

For a command-by-command usage guide, see [COMMAND_GUIDE.md](COMMAND_GUIDE.md).

## References

- Depth Anything V2: https://github.com/DepthAnything/Depth-Anything-V2
- PyPI package: https://pypi.org/project/depth-anything-v2/
- Small checkpoint: https://huggingface.co/depth-anything/Depth-Anything-V2-Small
