# Terrain-Conforming Unity Depth Demo

This repo is a small thesis prototype. It turns one recorded site video frame into a monocular depth map, exports that frame/depth/line bundle, and uses Unity to show a line conforming to a generated surface.

```text
video -> frame -> depth map -> clicked line -> Unity depth mesh -> surface-conforming line
```

The project intentionally avoids real-time AR, cloud services, Docker, ONNX, networking, and the older 2D video-overlay demo. The current proof is the Unity mesh view.

## Quick Start

1. Put a short video in `python/input_videos/`.
2. From the repo root, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_unity_demo.ps1
```

3. When the selector opens, click point A, click point B, press `S`, then press `Q` or `Esc`.
4. Open Unity and use `DepthMapTerrainGenerator` with `SurfaceConformingLine`.

To reuse the saved line:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_unity_demo.ps1 -SkipLineSelector
```

To check setup without changing files:

```powershell
powershell -ExecutionPolicy Bypass -File .\check_project_setup.ps1
```

## Folder Map

```text
python/
  input_videos/      local source videos
  checkpoints/       downloaded Depth Anything model weights
  output/
    frames/          extracted frames
    depth_maps/      generated depth PNGs
    unity_export/    frame.png, depth.png, line_metadata.json
  scripts/           active pipeline scripts

unity/
  Assets/Scripts/    Unity mesh and line components
  Assets/Textures/   generated copies for Unity import/use
```

See `python/README.md`, `unity/README.md`, and `COMMAND_GUIDE.md` for practical commands.

## Notes

- Generated outputs are ignored by Git.
- Input videos, model checkpoints, and saved line presets stay local.
- If VS Code C# Dev Kit says no SDKs were found, install the x64 .NET SDK. A .NET runtime alone is not enough for editor diagnostics.
