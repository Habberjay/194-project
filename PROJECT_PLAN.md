# Project Plan: Unity Surface-Conforming Depth Demo

## Current Goal

Prove the core thesis idea with the smallest reliable workflow:

```text
recorded video -> extracted frame -> monocular depth map -> Unity depth mesh -> surface-conforming layout line
```

The current prototype is not real-time AR and does not attempt construction-grade measurement. It is a visual proof that monocular depth can help a layout line follow uneven visible terrain better than a flat overlay.

## Active Scope

- Python handles offline video/frame/depth preparation.
- Unity handles the 3D surface proof.
- The user selects a single A/B line on one frame.
- The export bundle contains one frame, one matching depth map, and normalized line metadata.

Out of scope for this cleaned version:

- The older 2D/video-overlay renderer.
- Feature tracking across video frames.
- Contact sheets and overlay videos.
- AR Foundation/mobile deployment.
- Metric calibration and CAD import.

## Repository Structure

```text
project-root/
  README.md
  COMMAND_GUIDE.md
  PROJECT_PLAN.md
  check_project_setup.ps1
  run_unity_demo.ps1

  python/
    README.md
    requirements.txt
    setup_venv.ps1
    setup_venv.bat
    input_videos/
    checkpoints/
    output/
      frames/
      depth_maps/
      unity_export/
    scripts/
      clean_outputs.py
      common.py
      download_checkpoint.py
      extract_frames.py
      export_unity_demo.py
      line_presets.py
      line_selector.py
      pipeline_helpers.py
      run_depth.py

  unity/
    README.md
    Assets/
      Scripts/
      Textures/
```

## Main Workflow

1. Put a short video in `python/input_videos/`.
2. Run `run_unity_demo.ps1`.
3. Save or reuse `site_line_1`.
4. Use the generated Unity assets:
   - `python/output/unity_export/frame.png`
   - `python/output/unity_export/depth.png`
   - `python/output/unity_export/line_metadata.json`
5. In Unity, generate the depth mesh and rebuild the surface line.

## Research Notes

- Depth Anything V2 provides relative depth, not metric depth.
- The Unity mesh is a visual proxy surface created from the depth map.
- The green surface line should visibly follow the generated terrain.
- The cyan flat line remains as the comparison baseline.
- Future AR work would need camera tracking, anchoring, scale recovery, and persistence.

## Next Useful Improvements

- Add a tiny Unity sample scene once Unity project files are generated.
- Add screenshots of the expected mesh/line result.
- Add a simple calibration note for interpreting relative depth.
- Add optional camera controls or scene presets for repeatable thesis demos.
