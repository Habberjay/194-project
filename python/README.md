# Python Depth Pipeline

This folder prepares the Unity proof assets. It extracts one or more frames, runs Depth Anything V2, saves a clicked A/B line, and exports a Unity-ready bundle.

Active workflow:

```text
input_videos/ -> output/frames/ -> output/depth_maps/ -> line_presets.json -> output/unity_export/
```

## Setup

From the repo root, the easiest route is:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_unity_demo.ps1
```

The runner creates the virtual environment if needed and downloads the small Depth Anything V2 checkpoint if it is missing.

Manual setup from inside `python/`:

```powershell
.\setup_venv.ps1
.\.venv\Scripts\python.exe scripts\download_checkpoint.py
```

## Main Commands

Extract frames:

```powershell
.\.venv\Scripts\python.exe scripts\extract_frames.py --sample-fps 5 --max-frames 1 --clear
```

Generate depth maps:

```powershell
.\.venv\Scripts\python.exe scripts\run_depth.py --max-images 1 --clear
```

Click and save the line preset:

```powershell
.\.venv\Scripts\python.exe -B scripts\line_selector.py --preset site_line_1
```

Export the Unity bundle:

```powershell
.\.venv\Scripts\python.exe -B scripts\export_unity_demo.py --preset site_line_1 --clear
```

Output:

```text
output/unity_export/frame.png
output/unity_export/depth.png
output/unity_export/line_metadata.json
```

Clean generated Python outputs:

```powershell
.\.venv\Scripts\python.exe scripts\clean_outputs.py --yes
```

Also clean old legacy output folders if they exist:

```powershell
.\.venv\Scripts\python.exe scripts\clean_outputs.py --yes --legacy
```

## Active Script Roles

- `extract_frames.py`: extracts still frames from the source video.
- `run_depth.py`: generates Depth Anything V2 grayscale depth maps.
- `line_selector.py`: lets you click and save a reusable A/B line preset.
- `export_unity_demo.py`: exports the current Unity bundle.
- `pipeline_helpers.py`: shared frame/depth/line utility functions.
- `line_presets.py`: reads and writes `line_presets.json`.
- `clean_outputs.py`: cleans generated outputs while preserving videos, checkpoints, and presets.
- `download_checkpoint.py`: downloads the required model checkpoint.

## Local-Only Folders

- `input_videos/`: source videos; ignored by Git.
- `checkpoints/`: model weights; ignored by Git.
- `output/`: generated files; safe to clean.

Depth maps are relative depth estimates, not construction-grade metric measurements.
