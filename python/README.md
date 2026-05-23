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

By default this uses the first supported video in `input_videos/`, saves PNG frames to `frames/`, samples about 5 frames per second, and stops after 60 frames. For a specific video:

```powershell
.\.venv\Scripts\python.exe scripts\extract_frames.py --video input_videos\site_walkthrough.mp4 --sample-fps 5 --max-frames 60 --clear
```

Use `--sample-fps 1` for fewer frames or `--sample-fps 10` for a smoother but slower sequence. `--frame-step` is still available as a manual override.

3. Generate grayscale depth maps:

```powershell
.\.venv\Scripts\python.exe scripts\run_depth.py --clear
```

Output files are written to `depth_maps/` as PNG images.

4. Choose the terrain line.

The easiest way is to click the line on a frame:

```powershell
.\.venv\Scripts\python.exe -B scripts\line_selector.py --preset site_line_1
```

An image window will open. Click point A, click point B, then press `S` to save. Press `R` to reset or `Q` to quit. The preset is saved to `line_presets.json`.

You can also type the points manually instead of using the selector:

```powershell
--point-a 220,760 --point-b 980,760
```

5. Render a terrain-conforming overlay on one frame:

```powershell
.\.venv\Scripts\python.exe -B scripts\overlay_renderer.py --preset site_line_1 --clear
```

By default this uses the first image in `frames/`, finds the matching `*_depth.png` in `depth_maps/`, and places a test line across the lower part of the frame. Results are written to `overlays/`.

For a manually typed line:

```powershell
.\.venv\Scripts\python.exe -B scripts\overlay_renderer.py --frame frames\VID20260523112932_frame_00000.png --point-a 220,760 --point-b 980,760 --strength 70
```

If the terrain-aware line bends the wrong way, try:

```powershell
.\.venv\Scripts\python.exe -B scripts\overlay_renderer.py --offset-sign -1
```

6. Optional: render overlays for all extracted frames and make a short demo video.

Reuse the same image-space line on every frame:

```powershell
.\.venv\Scripts\python.exe -B scripts\process_video.py --preset site_line_1 --clear
```

For a simple persistence demo, track the line anchors across frames:

```powershell
.\.venv\Scripts\python.exe -B scripts\process_video.py --preset site_line_1 --track-points --clear
```

For a smoother persistence demo, let the bend remember previous frames too:

```powershell
.\.venv\Scripts\python.exe -B scripts\process_video.py --preset site_line_1 --track-points --temporal-memory 0.65 --clear
```

If the MP4 will not open, export a smaller MJPEG AVI:

```powershell
.\.venv\Scripts\python.exe -B scripts\process_video.py --preset site_line_1 --track-points --temporal-memory 0.65 --video-output output_videos\terrain_overlay_demo_small.avi --fourcc MJPG --video-scale 0.5 --clear
```

If your editor says the video is binary or uses unsupported text encoding, open the file with a media player instead. To inspect the result as a normal image, create a PNG contact sheet:

```powershell
.\.venv\Scripts\python.exe -B scripts\make_contact_sheet.py
```

Per-frame overlays are written to `overlays/sequence/`. The MP4 demo is written to `output_videos/terrain_overlay_demo.mp4`.

The contact sheet is written to:

```text
overlays/contact_sheet.png
```

7. Optional: normalize existing depth images again:

```powershell
.\.venv\Scripts\python.exe scripts\normalize_depth.py --input depth_maps --output-dir depth_maps_normalized --clear
```

8. Optional: clean generated output folders:

```powershell
.\.venv\Scripts\python.exe scripts\clean_outputs.py --yes
```

## Notes

- Keep videos short for the first prototype.
- Use `--sample-fps` and `--max-frames` to control how many frames are processed. Use `--frame-step` only when you want manual video-frame skipping.
- Depth maps are relative depth, not metric measurements.
- The current terrain overlay is a 2D proof-of-concept warp, not full 3D AR projection.
- The `--track-points` option is video persistence, not true AR world anchoring. It uses optical flow to move the selected line through adjacent frames.
- The `--temporal-memory` option smooths the terrain bend across frames. Try `0.5` for lighter smoothing or `0.8` for stronger smoothing.
- Unity is not needed for the current line-selection and overlay prototype. Keep Unity for later AR or 3D terrain visualization experiments.
- The next overlay upgrade should behave more like a string over terrain: many tracked control points, local depth snapping, and smoothing across frames.
- If Unity terrain appears inverted, toggle `Invert Depth` in the Unity script.

## Current Script Roles

- `extract_frames.py`: extracts frames from a video, currently targeting about 5 frames per second by default.
- `run_depth.py`: generates Depth Anything V2 grayscale depth maps.
- `line_selector.py`: lets you click and save a reusable line preset.
- `overlay_renderer.py`: renders one frame with flat versus terrain-aware overlay comparison.
- `process_video.py`: renders multi-frame overlays with optional tracking and temporal memory.
- `make_contact_sheet.py`: creates a PNG preview sheet from overlay frames.
