# Command Guide: Terrain-Conforming Line Overlay Prototype

This guide explains the commands for running the current video-based prototype.

The main workflow is:

```text
video -> extracted frames -> depth maps -> choose line -> bending overlay -> multi-frame demo video
```

Unity is not required for the current prototype. Use Unity later only if you want real AR, 3D terrain meshes, or mobile visualization.

## 1. Open The Python Project Folder

Run this first:

```powershell
cd C:\Users\User\Documents\GitHub\up\194-project\python
```

All commands below assume you are inside the `python/` folder.

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
- Saves image frames to `frames/`.
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
python/frames/
```

## 5. Generate Depth Maps

Basic command:

```powershell
.\.venv\Scripts\python.exe scripts\run_depth.py --clear
```

What it does:

- Reads frames from `frames/`.
- Runs Depth Anything V2.
- Saves grayscale depth maps to `depth_maps/`.

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
python/depth_maps/
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
.\.venv\Scripts\python.exe -B scripts\line_selector.py --frame frames\VID20260523203343_frame_00004.png --preset site_line_1
```

How to edit this command:

- `--preset site_line_1`: the name of the saved line.
- Change it to `--preset line_2` if you want multiple saved lines.
- `--frame frames\some_frame.png`: lets you pick which frame to click on.
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
python/overlays/
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
.\.venv\Scripts\python.exe -B scripts\overlay_renderer.py --frame frames\VID20260523203343_frame_00004.png --preset site_line_1 --clear
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

## 8. Render Multiple Frames With Memory

This is the main command for a multi-frame demo:

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
python/overlays/sequence/
python/output_videos/terrain_overlay_demo.mp4
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
- `--temporal-memory 0.0`: no bend memory.
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
.\.venv\Scripts\python.exe -B scripts\process_video.py --preset site_line_1 --track-points --temporal-memory 0.65 --video-output output_videos\terrain_overlay_demo_small.avi --fourcc MJPG --video-scale 0.5 --clear
```

Use this if `terrain_overlay_demo.mp4` will not open. It creates:

```text
python/output_videos/terrain_overlay_demo_small.avi
```

## 9. Recommended Demo Workflow

Use this sequence for a clean demo:

```powershell
cd C:\Users\User\Documents\GitHub\up\194-project\python
.\.venv\Scripts\python.exe scripts\extract_frames.py --sample-fps 5 --max-frames 30 --clear
.\.venv\Scripts\python.exe scripts\run_depth.py --clear
.\.venv\Scripts\python.exe -B scripts\line_selector.py --preset site_line_1
.\.venv\Scripts\python.exe -B scripts\overlay_renderer.py --preset site_line_1 --strength 70 --clear
.\.venv\Scripts\python.exe -B scripts\process_video.py --preset site_line_1 --track-points --temporal-memory 0.65 --strength 70 --clear
```

Then open:

```text
python/overlays/
python/output_videos/terrain_overlay_demo.mp4
```

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
--smooth-window 15 --temporal-memory 0.75
```

If the line does not follow the video well:

```powershell
--track-points
```

If tracking is unstable:

- Choose endpoints on visible, textured ground areas.
- Avoid points on sky, plain walls, blurry areas, reflections, or moving objects.
- Extract frames with a higher `--sample-fps`, such as `--sample-fps 8` or `--sample-fps 10`.

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
.\.venv\Scripts\python.exe -B scripts\process_video.py --preset site_line_1 --track-points --temporal-memory 0.65 --video-output output_videos\terrain_overlay_demo_small.avi --fourcc MJPG --video-scale 0.5 --clear
```

This writes a smaller MJPEG AVI file, which is often easier for Windows video players to open.

If you are opening the video from a text editor and see a message about binary or unsupported text encoding, that is normal. Videos are binary files. Open the video from File Explorer or a media player, not as text.

You can also create a single PNG preview sheet:

```powershell
.\.venv\Scripts\python.exe -B scripts\make_contact_sheet.py
```

This writes:

```text
python/overlays/contact_sheet.png
```

Open that PNG if you just want to quickly inspect the overlay frames.

## 11. What The Current Prototype Is And Is Not

This prototype is:

- A video-based proof of concept.
- A way to show flat blueprint lines versus depth-aware terrain-conforming lines.
- A way to test line selection, depth-based bending, and simple frame-to-frame persistence.

This prototype is not yet:

- Real-time AR.
- True world-anchored mapping.
- Metric construction-grade layout.
- Full 3D projection using camera intrinsics.

The current persistence is video persistence. It remembers line position and bend behavior across adjacent frames, but it is not yet a full AR spatial map.
