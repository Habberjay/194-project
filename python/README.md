# Python Pipeline

This folder handles the offline AI depth pipeline. It uses the smallest Depth Anything V2 model, `vits`, because it is the fastest option listed for relative depth estimation.

## Setup

Use Python 3.12 or newer. The `depth-anything-v2` PyPI package currently declares Python `>=3.12`.

```powershell
cd python
.\setup_venv.ps1
.\.venv\Scripts\python.exe scripts\download_checkpoint.py
```

If PowerShell blocks scripts, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_venv.ps1
```

The checkpoint downloader saves:

```text
python/checkpoints/depth_anything_v2_vits.pth
```

## Workflow

1. Place a video in `input_videos/`.

2. Extract frames:

```powershell
.\.venv\Scripts\python.exe scripts\extract_frames.py --clear
```

By default this uses the first supported video in `input_videos/`, saves PNG frames to `frames/`, samples every 30th frame, and stops after 60 frames. For a specific video:

```powershell
.\.venv\Scripts\python.exe scripts\extract_frames.py --video input_videos\site_walkthrough.mp4 --frame-step 30 --max-frames 60 --clear
```

3. Generate grayscale depth maps:

```powershell
.\.venv\Scripts\python.exe scripts\run_depth.py --clear
```

Output files are written to `depth_maps/` as PNG images.

4. Render a terrain-conforming overlay on one frame:

```powershell
.\.venv\Scripts\python.exe -B scripts\overlay_renderer.py --clear
```

By default this uses the first image in `frames/`, finds the matching `*_depth.png` in `depth_maps/`, and places a test line across the lower part of the frame. Results are written to `overlays/`.

For a more intentional line, pass two image-space points:

```powershell
.\.venv\Scripts\python.exe -B scripts\overlay_renderer.py --frame frames\VID20260523112932_frame_00000.png --point-a 220,760 --point-b 980,760 --strength 70
```

If the terrain-aware line bends the wrong way, try:

```powershell
.\.venv\Scripts\python.exe -B scripts\overlay_renderer.py --offset-sign -1
```

5. Optional: render overlays for all extracted frames and make a short demo video:

```powershell
.\.venv\Scripts\python.exe -B scripts\process_video.py --clear
```

Per-frame overlays are written to `overlays/sequence/`. The MP4 demo is written to `output_videos/terrain_overlay_demo.mp4`.

6. Optional: normalize existing depth images again:

```powershell
.\.venv\Scripts\python.exe scripts\normalize_depth.py --input depth_maps --output-dir depth_maps_normalized --clear
```

7. Optional: clean generated output folders:

```powershell
.\.venv\Scripts\python.exe scripts\clean_outputs.py --yes
```

## Notes

- Keep videos short for the first prototype.
- Use `--frame-step` and `--max-frames` to reduce processing time on low-end devices.
- Depth maps are relative depth, not metric measurements.
- The current terrain overlay is a 2D proof-of-concept warp, not full 3D AR projection.
- If Unity terrain appears inverted, toggle `Invert Depth` in the Unity script.
