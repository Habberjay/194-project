# Command Guide

This project now has one recommended path: generate Unity proof assets from a short video, then view the depth mesh and surface-conforming line in Unity.

## 1. Check Setup

From the repo root:

```powershell
powershell -ExecutionPolicy Bypass -File .\check_project_setup.ps1
```

This reports the Python venv, checkpoint, input videos, .NET SDK status, and whether Unity export assets already exist. It does not install system software.

## 2. Run The Main Demo

```powershell
powershell -ExecutionPolicy Bypass -File .\run_unity_demo.ps1
```

What it does:

- Creates `python/.venv/` if needed.
- Downloads the Depth Anything V2 checkpoint if missing.
- Cleans generated Python outputs.
- Extracts frame(s) from `python/input_videos/`.
- Generates depth map(s).
- Opens the line selector.
- Exports `python/output/unity_export/`.
- Copies the current export into `unity/Assets/Textures/`.

When the line selector opens, click point A, click point B, press `S`, then press `Q` or `Esc`.

Reuse an existing saved line:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_unity_demo.ps1 -SkipLineSelector
```

Use a specific video:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_unity_demo.ps1 -Video "python\input_videos\site_walkthrough.mp4"
```

Useful flags:

- `-Preset site_line_1`: saved line name.
- `-SampleFps 5`: frame sampling rate.
- `-MaxFrames 1`: one frame is enough for the Unity proof.
- `-NoClean`: keep previous generated Python outputs.
- `-NoCopyToUnity`: generate only `python/output/unity_export/`.

## 3. Manual Python Steps

From `python/`:

```powershell
.\setup_venv.ps1
.\.venv\Scripts\python.exe scripts\download_checkpoint.py
.\.venv\Scripts\python.exe scripts\extract_frames.py --sample-fps 5 --max-frames 1 --clear
.\.venv\Scripts\python.exe scripts\run_depth.py --max-images 1 --clear
.\.venv\Scripts\python.exe -B scripts\line_selector.py --preset site_line_1
.\.venv\Scripts\python.exe -B scripts\export_unity_demo.py --preset site_line_1 --clear
```

Generated Unity bundle:

```text
python/output/unity_export/frame.png
python/output/unity_export/depth.png
python/output/unity_export/line_metadata.json
```

## 4. Clean Outputs

Clean active generated outputs:

```powershell
cd python
.\.venv\Scripts\python.exe scripts\clean_outputs.py --yes
```

Clean active outputs plus old legacy output folders if they exist:

```powershell
.\.venv\Scripts\python.exe scripts\clean_outputs.py --yes --legacy
```

This preserves input videos, checkpoints, and `line_presets.json`.

## 5. Unity

Open Unity and use:

```text
unity/Assets/Scripts/DepthMapTerrainGenerator.cs
unity/Assets/Scripts/SurfaceConformingLine.cs
```

Assign:

- `unity/Assets/Textures/DepthMaps/depth.png`
- `unity/Assets/Textures/Blueprints/frame.png`
- `unity/Assets/Textures/line_metadata.json`

Then use `Load Metadata` and `Rebuild Surface Line` from the component menu.

## Troubleshooting

- `No .NET SDKs were found`: install the x64 .NET SDK, then reload VS Code.
- PyTorch appears stuck: first Windows import can take 10-30 seconds.
- No video found: put a supported video in `python/input_videos/`.
- No line preset: run without `-SkipLineSelector` once and save the clicked line.
