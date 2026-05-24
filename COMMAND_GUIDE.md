# Command Guide: Terrain-Conforming Line Overlay Prototype

This guide explains the commands for running the current video-based prototype.

The main workflow is:

```text
video -> extracted frames -> depth maps -> choose line -> feature-anchored string overlay -> multi-frame demo video
```

Unity is not required for the current prototype. Use Unity later only if you want real AR, 3D terrain meshes, or mobile visualization.

## 1. Open The Python Project Folder

Run this first:

```powershell
cd C:\Users\User\Documents\GitHub\up\194-project\python
```

All commands below assume you are inside the `python/` folder.

Generated frames, depth maps, overlays, videos, and JSON files are written under:

```text
python/output/
```

## 2. Setup

If you have not set up the Python environment yet:

```powershell
.\setup_venv.ps1
```

If PowerShell blocks the script:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_venv.ps1
```

Download the Depth Anything V2 checkpoint:

```powershell
.\.venv\Scripts\python.exe scripts\download_checkpoint.py
```

You only need to do setup/checkpoint download once.

## 3. Put A Video In The Input Folder

Put your recorded terrain video here:

```text
python/input_videos/
```

Example:

```text
python/input_videos/site_walkthrough.mp4
```

## 4. Extract Frames From The Video

Basic command:

```powershell
.\.venv\Scripts\python.exe scripts\extract_frames.py --clear
```

What it does:

- Reads the first video in `input_videos/`.
- Saves image frames to `output/frames/`.
- Saves about 5 frames per second by default.
- Clears old frames first because of `--clear`.

Use a specific video:

```powershell
.\.venv\Scripts\python.exe scripts\extract_frames.py --video input_videos\site_walkthrough.mp4 --clear
```

Extract more or fewer frames:

```powershell
.\.venv\Scripts\python.exe scripts\extract_frames.py --sample-fps 5 --max-frames 40 --clear
```

How to edit this command:

- `--sample-fps 5`: saves about 5 frames per second.
- `--sample-fps 1`: saves about 1 frame per second.
- `--sample-fps 10`: saves about 10 frames per second, smoother but slower.
- `--frame-step 30`: manual override that saves one frame every 30 video frames.
- Smaller `--frame-step`, like `--frame-step 10`: more frames, smoother video, slower processing.
- Larger `--frame-step`, like `--frame-step 60`: fewer frames, faster processing.
- `--max-frames 40`: stops after 40 saved frames.
- `--clear`: deletes old extracted frames before writing new ones.

Output:

```text
python/output/frames/
```

## 5. Generate Depth Maps

Basic command:

```powershell
.\.venv\Scripts\python.exe scripts\run_depth.py --clear
```

What it does:

- Reads frames from `output/frames/`.
- Runs Depth Anything V2.
- Saves grayscale depth maps to `output/depth_maps/`.

Limit how many frames are processed:

```powershell
.\.venv\Scripts\python.exe scripts\run_depth.py --max-images 10 --clear
```

Invert the depth map if the output behaves backward:

```powershell
.\.venv\Scripts\python.exe scripts\run_depth.py --invert --clear
```

How to edit this command:

- `--max-images 10`: processes only the first 10 frames.
- `--input-size 518`: controls model input size. Higher may improve detail but is slower.
- `--invert`: flips black/white depth values.
- `--clear`: deletes old depth maps before writing new ones.

Output:

```text
python/output/depth_maps/
```

## 6. Choose The Terrain Line By Clicking

Use the line selector:

```powershell
.\.venv\Scripts\python.exe -B scripts\line_selector.py --preset site_line_1
```

What it does:

- Opens a frame window.
- You click point A.
- You click point B.
- Press `S` to save the line.
- Press `R` to reset the selected points.
- Press `Q` or `Esc` to quit.

The line is saved as a preset in:

```text
python/line_presets.json
```

Use a different preset name:

```powershell
.\.venv\Scripts\python.exe -B scripts\line_selector.py --preset driveway_line
```

Use a specific frame for line selection:

```powershell
.\.venv\Scripts\python.exe -B scripts\line_selector.py --frame output\frames\VID20260523203343_frame_00004.png --preset site_line_1
```

How to edit this command:

- `--preset site_line_1`: the name of the saved line.
- Change it to `--preset line_2` if you want multiple saved lines.
- `--frame output\frames\some_frame.png`: lets you pick which frame to click on.
- `-B`: prevents Python from writing bytecode cache files. Keep it in these commands.

## 7. Render One Bending Line Overlay

After saving a line preset, run:

```powershell
.\.venv\Scripts\python.exe -B scripts\overlay_renderer.py --preset site_line_1 --clear
```

What it does:

- Loads one frame.
- Loads the matching depth map.
- Loads your saved line preset.
- Draws the flat line and the terrain-aware bending line.
- Saves overlay images.

Output:

```text
python/output/overlays/
```

Important output files:

```text
*_overlay.png
*_comparison.png
```

Use manually typed points instead of a preset:

```powershell
.\.venv\Scripts\python.exe -B scripts\overlay_renderer.py --point-a 220,760 --point-b 980,760 --clear
```

Use a specific frame:

```powershell
.\.venv\Scripts\python.exe -B scripts\overlay_renderer.py --frame output\frames\VID20260523203343_frame_00004.png --preset site_line_1 --clear
```

Make the bend stronger:

```powershell
.\.venv\Scripts\python.exe -B scripts\overlay_renderer.py --preset site_line_1 --strength 100 --clear
```

Make the bend gentler:

```powershell
.\.venv\Scripts\python.exe -B scripts\overlay_renderer.py --preset site_line_1 --strength 35 --clear
```

Flip the bending direction:

```powershell
.\.venv\Scripts\python.exe -B scripts\overlay_renderer.py --preset site_line_1 --offset-sign -1 --clear
```

How to edit this command:

- `--preset site_line_1`: uses a saved clicked line.
- `--point-a 220,760 --point-b 980,760`: manually sets the line in image pixel coordinates.
- `--strength 60`: controls how much the line bends visually.
- `--strength 100`: stronger bend.
- `--strength 30`: weaker bend.
- `--smooth-window 9`: smooths depth samples along the line.
- `--smooth-window 15`: smoother, less noisy.
- `--smooth-window 3`: more sensitive, possibly noisier.
- `--offset-sign -1`: flips the bend if it goes the wrong way.
- `--axis vertical`: bends the line up/down in the image.
- `--axis normal`: bends the line perpendicular to the selected line.
- `--clear`: removes old overlay images first.

## 8. Legacy: Render Multiple Frames With Direct Memory

This older mode is still useful for experiments, but it is not the recommended final demo anymore. It blends image coordinates and bend shapes directly across frames, which can create messy overlays when the camera moves.

Legacy command:

```powershell
.\.venv\Scripts\python.exe -B scripts\process_video.py --preset site_line_1 --track-points --temporal-memory 0.65 --clear
```

What it does:

- Uses your saved line preset.
- Processes all extracted frames.
- Tracks the line position across frames with optical flow.
- Smooths the bending shape across frames using temporal memory.
- Saves overlay images and a demo video.

Outputs:

```text
python/output/overlays/sequence/
python/output/videos/terrain_overlay_demo.mp4
```

Run without tracking:

```powershell
.\.venv\Scripts\python.exe -B scripts\process_video.py --preset site_line_1 --clear
```

This reuses the same image-space line on every frame.

Run with tracking but no bend smoothing:

```powershell
.\.venv\Scripts\python.exe -B scripts\process_video.py --preset site_line_1 --track-points --clear
```

Run with stronger memory:

```powershell
.\.venv\Scripts\python.exe -B scripts\process_video.py --preset site_line_1 --track-points --temporal-memory 0.8 --clear
```

Run with lighter memory:

```powershell
.\.venv\Scripts\python.exe -B scripts\process_video.py --preset site_line_1 --track-points --temporal-memory 0.5 --clear
```

How to edit this command:

- `--track-points`: moves the selected line across frames using optical flow.
- `--temporal-memory 0.65`: blends the current bend with previous frame bends.
- `--temporal-memory 0.0`: no direct coordinate memory. This is recommended for final feature-anchored output.
- `--temporal-memory 0.5`: light smoothing.
- `--temporal-memory 0.8`: strong smoothing, more stable but slower to react.
- `--fps 6`: output video frame rate.
- `--max-frames 10`: process only the first 10 frames.
- `--no-video`: save overlay images only, no MP4.

Example with more options:

```powershell
.\.venv\Scripts\python.exe -B scripts\process_video.py --preset site_line_1 --track-points --temporal-memory 0.7 --strength 85 --smooth-window 13 --fps 8 --clear
```

Export a smaller Windows-friendly video:

```powershell
.\.venv\Scripts\python.exe -B scripts\process_video.py --preset site_line_1 --track-points --temporal-memory 0.65 --video-output output\videos\terrain_overlay_demo_small.avi --fourcc MJPG --video-scale 0.5 --clear
```

Use this if `terrain_overlay_demo.mp4` will not open. It creates:

```text
python/output/videos/terrain_overlay_demo_small.avi
```

## 9. Recommended Demo Workflow

Use this sequence for the full checked string demo:

```powershell
cd C:\Users\User\Documents\GitHub\up\194-project\python
.\.venv\Scripts\python.exe scripts\extract_frames.py --sample-fps 5 --max-frames 30 --clear
.\.venv\Scripts\python.exe -B scripts\line_selector.py --preset site_line_1
.\.venv\Scripts\python.exe -B scripts\run_offline_demo.py --preset site_line_1 --line-mode string --anchor-mode feature --depth-resnap light --sample-fps 5 --max-frames 60 --retries 2
```

Then open:

```text
python/output/overlays/string_contact_sheet.png
python/output/videos/terrain_string_demo_small.avi
```

The runner also writes a single-frame smoke check to:

```text
python/output/overlays/string_single/
```

What the full runner checks:

- Input video exists.
- Required packages import correctly.
- Depth checkpoint exists.
- The selected line preset exists.
- Frame extraction produces at least 2 frames.
- Depth maps match the extracted frames.
- Single-frame string/debug overlay can be produced.
- Multi-frame string overlays can be produced.
- The exported AVI can be opened by OpenCV.
- Feature-anchor confidence is present in the point-data JSON.
- Feature-anchor transform kind is recorded as `identity`, `affine`, or `homography`.
- A contact sheet is created even if video export fails.

If a recoverable error occurs, the runner retries with safer settings. If video export still fails, the PNG sequence and contact sheet remain the required visual outputs.

Important: `--anchor-mode feature` is the recommended TikTok-like offline mode. Point A/B is used only to place the string in the first frame. After that, scene features carry the string through the video, and `--depth-resnap light` makes only small depth corrections.

## 10. Troubleshooting

If the line bends the wrong way:

```powershell
--offset-sign -1
```

If the bend is too small:

```powershell
--strength 100
```

If the bend is too extreme:

```powershell
--strength 30
```

If the bend is noisy:

```powershell
--depth-resnap none
```

Use `--depth-resnap none` when visual anchoring looks good but the depth correction is adding jitter. Use `--depth-resnap full` only when you specifically want to show the more aggressive depth reaction.

If the line does not follow the video well:

```powershell
--anchor-mode feature --depth-resnap light
```

If tracking is unstable:

- Choose endpoints on visible, textured ground areas.
- Avoid points on sky, plain walls, blurry areas, reflections, or moving objects.
- Extract frames with a higher `--sample-fps`, such as `--sample-fps 8` or `--sample-fps 10`.
- Try a larger feature search area: `--anchor-roi-padding 240`.
- Try fewer required anchor points: `--min-anchor-points 12`.
- Try pure visual anchoring with no depth correction: `--depth-resnap none`.

If processing is slow:

```powershell
--max-frames 10
```

or extract fewer frames:

```powershell
.\.venv\Scripts\python.exe scripts\extract_frames.py --sample-fps 1 --max-frames 15 --clear
```

If the MP4 video will not open:

```powershell
.\.venv\Scripts\python.exe -B scripts\run_offline_demo.py --preset site_line_1 --line-mode string --anchor-mode feature --depth-resnap light --video-scale 0.5 --max-frames 60 --retries 2
```

The full runner writes `output/videos/terrain_string_demo_small.avi`, which is often easier for Windows video players to open than the older MP4 export.

If you are opening the video from a text editor and see a message about binary or unsupported text encoding, that is normal. Videos are binary files. Open the video from File Explorer or a media player, not as text.

You can also create a single PNG preview sheet:

```powershell
.\.venv\Scripts\python.exe -B scripts\make_contact_sheet.py
```

This writes:

```text
python/output/overlays/contact_sheet.png
```

Open that PNG if you just want to quickly inspect the overlay frames.

## 11. What The Current Prototype Is And Is Not

This prototype is:

- A video-based proof of concept.
- A way to show flat blueprint lines versus depth-aware terrain-conforming lines.
- A way to test line selection, depth-based bending, and simple frame-to-frame persistence.
- A practical Python/OpenCV workflow for inspecting results before building real AR.
- A checked end-to-end runner for finishing the non-real-time demo.

This prototype is not yet:

- Real-time AR.
- True world-anchored mapping.
- Metric construction-grade layout.
- Full 3D projection using camera intrinsics.
- A true physical string simulation over a reconstructed surface.

The current persistence is video persistence. It remembers line position and bend behavior across adjacent frames, but it is not yet a full AR spatial map.

## 12. Current Limitation And Next Direction

The current overlay starts from point A and point B. It samples depth along that line and bends the line visually. This is useful, but it can still look too tied to the original endpoints.

The current feature-anchored string overlay model is:

```text
clicked A/B line -> first-frame string -> feature anchor projection -> light depth re-snap -> overlay
```

What is now implemented for the offline prototype:

- Use many control points along the line, not only A and B.
- Track the first-frame scene using visual features.
- Project the first-frame string into each later frame using the estimated feature transform.
- Let depth make only a small correction with `--depth-resnap light`.
- Keep the old `--temporal-memory` behavior available only as an experiment; avoid it for final output.

This still will not be true AR anchoring. For viewpoint-correct behavior, the later system needs camera pose estimation and a persistent 3D terrain map.

## 13. Full Runner Command Reference

Main goal command:

```powershell
.\.venv\Scripts\python.exe -B scripts\run_offline_demo.py --preset site_line_1 --line-mode string --anchor-mode feature --depth-resnap light --sample-fps 5 --max-frames 60 --retries 2
```

Useful edits:

- `--preset site_line_1`: saved line from `line_selector.py`.
- `--sample-fps 5`: extracts about 5 frames per second.
- `--max-frames 60`: caps the demo at 60 frames.
- `--retries 2`: retries recoverable stages.
- `--anchor-mode feature`: attaches the string to tracked scene features.
- `--depth-resnap light`: lightly adjusts the anchored string to current depth.
- `--depth-resnap none`: pure visual anchoring, usually the most stable.
- `--depth-resnap full`: aggressive depth snapping, useful for experiments but less stable.
- `--anchor-roi-padding 160`: area around the first-frame string used for feature tracking.
- `--min-anchor-points 20`: minimum inliers for a confident anchor update.
- `--max-anchor-misses 5`: how many weak frames can reuse the last good transform.
- `--search-radius 32`: how far string points can search around the initial line.
- `--control-points 96`: number of string points.
- `--temporal-memory 0`: recommended final behavior; direct memory blending is experimental.
- `--video-scale 0.5`: smaller video for easier playback.

Manual point version:

```powershell
.\.venv\Scripts\python.exe -B scripts\run_offline_demo.py --point-a 220,760 --point-b 980,760 --line-mode string --anchor-mode feature --depth-resnap light --sample-fps 5 --max-frames 60 --retries 2
```

## 14. Clean Generated Files

To clear the generated `output/` folders:

```powershell
.\.venv\Scripts\python.exe scripts\clean_outputs.py --yes
```

If old pre-`output/` folders ever reappear, include:

```powershell
.\.venv\Scripts\python.exe scripts\clean_outputs.py --legacy --yes
```
