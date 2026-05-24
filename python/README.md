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

By default this uses the first supported video in `input_videos/`, saves PNG frames to `output/frames/`, samples about 5 frames per second, and stops after 60 frames. For a specific video:

```powershell
.\.venv\Scripts\python.exe scripts\extract_frames.py --video input_videos\site_walkthrough.mp4 --sample-fps 5 --max-frames 60 --clear
```

Use `--sample-fps 1` for fewer frames or `--sample-fps 10` for a smoother but slower sequence. `--frame-step` is still available as a manual override.

3. Generate grayscale depth maps:

```powershell
.\.venv\Scripts\python.exe scripts\run_depth.py --clear
```

Output files are written to `output/depth_maps/` as PNG images.

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

By default this uses the first image in `output/frames/`, finds the matching `*_depth.png` in `output/depth_maps/`, and places a test line across the lower part of the frame. Results are written to `output/overlays/`.

For a manually typed line:

```powershell
.\.venv\Scripts\python.exe -B scripts\overlay_renderer.py --frame output\frames\VID20260523112932_frame_00000.png --point-a 220,760 --point-b 980,760 --strength 70
```

If the terrain-aware line bends the wrong way, try:

```powershell
.\.venv\Scripts\python.exe -B scripts\overlay_renderer.py --offset-sign -1
```

6. Optional legacy mode: render overlays for all extracted frames and make a short demo video.

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

This legacy mode is not recommended for the final output because direct coordinate memory can make the line messy. Use the feature-anchored full runner in step 7 for the current TikTok-like offline behavior.

If the MP4 will not open, export a smaller MJPEG AVI:

```powershell
.\.venv\Scripts\python.exe -B scripts\process_video.py --preset site_line_1 --track-points --temporal-memory 0.65 --video-output output\videos\terrain_overlay_demo_small.avi --fourcc MJPG --video-scale 0.5 --clear
```

If your editor says the video is binary or uses unsupported text encoding, open the file with a media player instead. To inspect the result as a normal image, create a PNG contact sheet:

```powershell
.\.venv\Scripts\python.exe -B scripts\make_contact_sheet.py
```

Per-frame overlays are written to `output/overlays/sequence/`. The MP4 demo is written to `output/videos/terrain_overlay_demo.mp4`.

The contact sheet is written to:

```text
output/overlays/contact_sheet.png
```

7. Run the full checked offline string demo.

After you have selected `site_line_1`, this command runs the full goal pipeline with checks and retries:

```powershell
.\.venv\Scripts\python.exe -B scripts\run_offline_demo.py --preset site_line_1 --line-mode string --anchor-mode feature --depth-resnap light --sample-fps 5 --max-frames 60 --retries 2
```

It runs frame extraction, depth generation, single-frame debug rendering, feature-anchored multi-frame string overlay rendering, readable AVI export, point-data export, and contact-sheet export.

In this mode, point A/B only places the string in the first frame. Later frames use scene features near that first-frame string to carry the overlay through the video, then `--depth-resnap light` makes a small terrain-depth correction.

Main outputs:

```text
output/overlays/string_sequence/
output/overlays/string_debug/
output/overlays/anchor_debug/
output/overlays/string_single/
output/overlays/string_contact_sheet.png
output/videos/terrain_string_demo_small.avi
output/data/string_points.json
```

8. Optional: normalize existing depth images again:

```powershell
.\.venv\Scripts\python.exe scripts\normalize_depth.py --input output\depth_maps --output-dir output\depth_maps_normalized --clear
```

9. Optional: clean generated output folders:

```powershell
.\.venv\Scripts\python.exe scripts\clean_outputs.py --yes
```

To also clean old pre-`output/` folders if they ever reappear:

```powershell
.\.venv\Scripts\python.exe scripts\clean_outputs.py --legacy --yes
```

## Notes

- Keep videos short for the first prototype.
- Generated frames, depth maps, overlays, videos, and JSON data are kept under `output/`.
- Use `--sample-fps` and `--max-frames` to control how many frames are processed. Use `--frame-step` only when you want manual video-frame skipping.
- Depth maps are relative depth, not metric measurements.
- The current terrain overlay is a 2D proof-of-concept warp, not full 3D AR projection.
- The `--track-points` option is video persistence, not true AR world anchoring. It uses optical flow to move the selected line through adjacent frames.
- The recommended final demo uses `--anchor-mode feature`, not `--track-points`, so the first-frame string is attached to scene features instead of fixed screen points.
- The `--depth-resnap light` option lightly adjusts the anchored string to the current depth map without letting depth destroy the anchor.
- Use `--depth-resnap none` for the most stable pure visual anchor and `--depth-resnap full` only for aggressive depth experiments.
- The `--temporal-memory` option is now experimental; avoid it for the final demo because direct coordinate blending can make the line messy.
- Unity is not needed for the current line-selection and overlay prototype. Keep Unity for later AR or 3D terrain visualization experiments.
- The string overlay behaves more like a string over terrain: many tracked control points, local depth snapping, and smoothing across frames.
- `run_offline_demo.py` is the recommended final offline demo command because it performs checks and retries stage failures.
- If Unity terrain appears inverted, toggle `Invert Depth` in the Unity script.

## Current Script Roles

- `extract_frames.py`: extracts frames from a video, currently targeting about 5 frames per second by default.
- `run_depth.py`: generates Depth Anything V2 grayscale depth maps.
- `line_selector.py`: lets you click and save a reusable line preset.
- `string_line.py`: creates the string-like overlay from many depth-snapped control points.
- `anchor_tracker.py`: tracks the first-frame string against scene features for TikTok-like offline anchoring, using affine RANSAC first and homography only as a conservative fallback.
- `overlay_renderer.py`: renders one frame with flat versus terrain-aware overlay comparison.
- `process_video.py`: renders multi-frame overlays with optional tracking and temporal memory.
- `make_contact_sheet.py`: creates a PNG preview sheet from overlay frames.
- `run_offline_demo.py`: runs the full feature-anchored offline string demo with checks, retries, fallback video export, contact sheet creation, anchor debug output, and point-data export.
