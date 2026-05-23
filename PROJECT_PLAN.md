# Project Plan: Terrain-Conforming Blueprint Overlay Using Monocular Depth Estimation

## 1. Project Overview

This project explores a monocular-depth-based terrain-conforming blueprint overlay system for AEC and AR use cases. The core idea is to use a normal camera video as input, estimate a depth map from each frame, approximate the visible terrain surface, and draw blueprint or construction layout lines that follow the terrain instead of assuming a perfectly flat ground plane.

In typical AR layout workflows, virtual lines are often placed on a detected flat plane. That approach works for indoor floors or simple planar surfaces, but it can fail outdoors when the ground is sloped, curved, uneven, or partially obstructed. This project investigates whether AI-generated monocular depth maps can provide enough terrain information to warp or project layout lines so that they visually conform to the real ground surface.

The long-term research goal is a smartphone-based AR workflow that does not require LiDAR, pre-scanning, total stations, or special hardware. The short-term prototype is intentionally smaller: an offline video-processing pipeline that proves the visual and algorithmic concept before moving into real-time AR.

## 2. Research Rationale Summary

AR is useful in architecture, engineering, and construction because it can place design intent directly over the real site. Layout lines, excavation guides, slab boundaries, path markings, and utility routes are easier to understand when they are shown in context.

However, many AR layout systems simplify the environment as one or more flat planes. Outdoor construction terrain is rarely perfectly flat. It may include slopes, depressions, bumps, gravel, soil, vegetation, or partially finished surfaces. When a blueprint line is rendered as a flat overlay, it can appear to float above the ground, cut through the ground, or drift away from the intended surface.

LiDAR and specialized scanning hardware can help solve this problem, but they are not available on all devices and may increase cost or complexity. Monocular depth estimation offers a lower-cost alternative because it can infer approximate depth from a single RGB camera frame. This project tests whether depth maps from models such as Depth Anything or Depth Anything V2 can be used to deform blueprint lines so they better follow visible terrain.

## 3. Long-Term System Architecture

The ideal full system is a smartphone AR application with the following modules:

1. Camera input module
   - Captures live RGB frames from the phone camera.
   - Provides images to the depth estimation and tracking pipeline.

2. Depth estimation module
   - Runs a monocular depth estimation model on camera frames.
   - Candidate models include Depth Anything and Depth Anything V2.
   - Produces relative depth maps that describe the visible scene geometry.

3. Terrain reconstruction module
   - Converts depth maps into an approximate 2.5D or 3D terrain surface.
   - Uses camera intrinsics and depth values to back-project image pixels into camera space.
   - May smooth, filter, or segment the terrain region to reduce noisy depth artifacts.

4. AR tracking and camera pose module
   - Estimates camera movement and pose over time.
   - Keeps the reconstructed terrain and overlay stable as the user moves.
   - Possible technologies include ARCore, ARKit, AR Foundation, ORB-SLAM, COLMAP, or visual-inertial odometry.

5. Blueprint or line input module
   - Lets the user draw, place, import, or select layout geometry.
   - Early versions may support only a line from point A to point B.
   - Later versions may support polylines, closed shapes, grids, CAD/DXF imports, or construction plan anchors.

6. Terrain-conforming projection module
   - Projects the blueprint geometry onto the estimated terrain surface.
   - Converts a straight intended layout line into a terrain-aware line that follows changes in surface depth or height.
   - Handles interpolation between sampled depth points and optional smoothing.

7. Overlay renderer
   - Renders the projected line back into the camera view.
   - In a full AR version, this would be handled by Unity with AR Foundation.
   - The renderer should support line thickness, color, opacity, and visibility rules.

8. Persistence and mapping module
   - Stores previously observed terrain so the overlay does not disappear when the camera angle changes.
   - Maintains a spatial map or accumulated terrain representation.
   - Supports revisiting earlier views and keeping the blueprint overlay anchored.

Possible technology stack:

- Python for AI/depth processing and offline experimentation.
- OpenCV for video loading, frame extraction, image processing, drawing, and export.
- Depth Anything or Depth Anything V2 for monocular depth estimation.
- Unity with AR Foundation for a future real-time AR implementation.
- ARCore or ARKit for mobile camera tracking and anchors.
- COLMAP or ORB-SLAM for research experiments involving camera pose and sparse reconstruction.

## 4. Three-Day Prototype Scope

The current prototype should be video-based rather than real-time AR. The goal is to produce a clear proof of concept that demonstrates terrain-conforming line generation from monocular video and depth maps.

Minimum viable prototype:

1. Load a recorded monocular video.
2. Extract frames from the video.
3. Run depth estimation on each selected frame.
4. Save depth maps as image files.
5. Select or hardcode two points on one frame.
6. Sample depth values along the 2D line between those points.
7. Convert the straight 2D line into a terrain-aware polyline.
8. Draw the warped or conforming line on the original frame.
9. Export visual results showing:
   - Original frame.
   - Depth map.
   - Frame with terrain-conforming overlay.
   - Optional side-by-side comparison.
10. If time allows, process multiple frames to show that the overlay can be tracked, reused, or approximately propagated through the video.

This prototype does not need to solve full AR anchoring, real-time inference, metric depth calibration, mobile deployment, or robust camera pose estimation. Those are long-term research targets.

## 5. Suggested File and Folder Structure

The current repository already separates the Python prototype and future Unity work. The recommended structure is:

```txt
project-root/
  PROJECT_PLAN.md
  COMMAND_GUIDE.md
  README.md

  python/
    README.md
    requirements.txt
    setup_venv.ps1
    setup_venv.bat
    line_presets.json

    input_videos/
      example_site_video.mp4

    frames/
      video_frame_00000.png

    depth_maps/
      video_frame_00000_depth.png

    overlays/
      video_frame_00000_overlay.png
      video_frame_00000_comparison.png
      contact_sheet.png
      sequence/
        video_frame_00000_overlay.png

    output_videos/
      terrain_overlay_demo.mp4
      terrain_overlay_demo_small.avi

    checkpoints/
      depth_anything_v2_vits.pth

    scripts/
      common.py
      clean_outputs.py
      download_checkpoint.py
      extract_frames.py
      run_depth.py
      normalize_depth.py
      line_presets.py
      line_selector.py
      terrain_line.py
      overlay_renderer.py
      process_video.py
      make_contact_sheet.py

  unity/
    README.md
    Assets/
      Materials/
      Scripts/
      Textures/

  docs/
    research_notes.md
    experiment_log.md
```

Current important Python scripts:

- `extract_frames.py`: extracts frames from the source video. The current default target is about 5 frames per second.
- `run_depth.py`: runs Depth Anything V2 and saves grayscale depth maps.
- `line_selector.py`: lets the user click point A and point B on a frame and save them as a line preset.
- `line_presets.py`: reads and writes reusable line presets.
- `terrain_line.py`: generates depth-aware polylines from frame points and depth maps.
- `overlay_renderer.py`: draws flat-line and terrain-aware-line overlays for one frame.
- `process_video.py`: renders overlays across multiple frames, with optional optical-flow tracking and temporal bend memory.
- `make_contact_sheet.py`: creates a single PNG preview sheet from overlay frames.

## 6. Prototype Algorithm

The short-term line-conforming algorithm can begin as a 2D image-space approximation:

1. Choose two image points, `A = (x1, y1)` and `B = (x2, y2)`.
2. Sample `N` points along the straight line between A and B.
3. Read the depth value at each sample point from the depth map.
4. Smooth the sampled depth profile to reduce noise.
5. Convert depth changes into a vertical or normal-direction image displacement.
6. Create a polyline from the displaced sample points.
7. Draw the polyline on top of the original frame.

This is not yet true 3D projection, but it is useful for demonstrating the concept visually. A more advanced version should:

- Use camera intrinsics to back-project depth samples into 3D.
- Estimate or assume a ground/terrain coordinate system.
- Project the intended blueprint line onto the reconstructed terrain surface.
- Reproject the resulting 3D terrain-following line back into the image.

Important research note: monocular depth models usually output relative depth, not directly measured metric depth. For construction-grade use, the system would eventually need calibration, scale recovery, known reference measurements, or integration with AR tracking.

## 7. Three-Day Work Plan

### Day 1: Confirm Offline Depth Pipeline

- Verify that the video input folder, frame extraction script, and depth estimation script work.
- Generate depth maps from a short recorded outdoor terrain video.
- Save a small, clean set of example frames and depth maps.
- Document the exact command sequence in `README.md` or `python/README.md`.

Expected output:

- Extracted RGB frames.
- Depth map PNG files.
- One selected test frame for overlay experiments.

### Day 2: Implement Terrain-Conforming Line Overlay

- Add a script to define two points on a selected frame.
- Sample the depth map along the point-to-point line.
- Convert the straight line into a depth-influenced polyline.
- Render both the original straight line and the terrain-conforming line for comparison.
- Export result images to `python/overlays/`.

Expected output:

- One or more overlay images showing the difference between flat and terrain-conforming lines.
- A clear comparison image suitable for presentation.

### Day 3: Multi-Frame Demonstration and Documentation

- Extend the overlay script to process multiple frames if feasible.
- Attempt simple propagation of the selected line across adjacent frames.
- Export a short result video or a sequence of comparison images.
- Update documentation with current limitations, screenshots, and next steps.

Expected output:

- Final demo image or short demo video.
- Notes explaining what is real, what is approximate, and what remains future work.

## 8. Evaluation Criteria

The prototype should be judged by research usefulness rather than production accuracy.

Core success criteria:

- A recorded video can be converted into frames.
- Depth maps can be generated for selected frames.
- A straight user-defined line can be transformed into a terrain-aware polyline.
- The overlay result visually follows depth variation better than a flat straight line.
- Output images or videos are saved in a reproducible folder.

Optional success criteria:

- The same overlay concept is shown across multiple frames.
- The output includes side-by-side original frame, depth map, and overlay visualization.
- The line generation parameters can be adjusted from the command line.

## 9. Known Limitations

- Monocular depth is relative and may not match real-world metric distances.
- Depth maps can be noisy around thin objects, vegetation, shadows, reflective areas, and sky.
- A 2D warped line is only an approximation of terrain conformance.
- Real AR anchoring requires camera pose tracking and world-coordinate persistence.
- Construction-grade layout accuracy is outside the current prototype scope.
- Outdoor lighting, motion blur, and camera shake can affect both depth estimation and visual tracking.

## 10. Future Research Directions

Longer-term improvements may include:

- True 3D back-projection using camera intrinsics.
- Terrain segmentation to isolate ground from buildings, people, plants, and equipment.
- Temporal smoothing of depth maps across video frames.
- Camera pose estimation with ARCore, ARKit, COLMAP, or ORB-SLAM.
- Persistent terrain mapping so previously seen ground is retained.
- Blueprint import from CAD, DXF, SVG, or GIS-like line data.
- Scale calibration using known measurements on site.
- Unity AR Foundation prototype for mobile visualization.
- User interaction for selecting anchors, drawing lines, and adjusting overlay confidence.
- Accuracy evaluation against measured terrain or LiDAR reference data.

## 11. Current Recommended Next Step

The current working pipeline is:

```txt
video -> frames -> depth maps -> clicked line preset -> bending overlay -> persistent video demo
```

The next research step is to improve the overlay logic from a two-endpoint bending line into a string-like surface-conforming line. The current result is useful for showing the idea, but it is still visually constrained by point A and point B. It cannot yet fully behave like a physical string laid over an object or terrain surface from changing viewpoints.

Next implementation target:

1. Convert the selected A/B line into many control points.
2. Track those control points across frames, not only the two endpoints.
3. Use local depth neighborhoods to adjust each control point toward visible surface shape.
4. Smooth the control points so the line behaves like a continuous string.
5. Export debug images showing control points, depth samples, and final overlay.

## 12. Current Prototype Status

The Python prototype now includes the terrain overlay stage:

```txt
video -> frames -> depth maps -> line preset -> terrain-aware overlay images -> optional demo video/contact sheet
```

Implemented scripts:

- `scripts/extract_frames.py`: extracts video frames. By default, it now samples about 5 frames per second unless `--frame-step` is manually provided.
- `scripts/terrain_line.py`: samples depth along a user-defined line and converts it into a depth-aware polyline.
- `scripts/line_selector.py`: lets the user click two points on a frame and save them as a reusable line preset.
- `scripts/overlay_renderer.py`: renders a single-frame comparison with the original frame, depth map, flat line, and terrain-aware line.
- `scripts/process_video.py`: applies the overlay renderer to multiple extracted frames, optionally tracks the selected line through the sequence, smooths the line bend with temporal memory, and writes an MP4 demo.
- `scripts/make_contact_sheet.py`: creates a PNG preview sheet from the generated overlay frames.

Main commands from the `python/` folder:

```powershell
.\.venv\Scripts\python.exe scripts\extract_frames.py --sample-fps 5 --max-frames 60 --clear
.\.venv\Scripts\python.exe scripts\run_depth.py --clear
.\.venv\Scripts\python.exe -B scripts\line_selector.py --preset site_line_1
.\.venv\Scripts\python.exe -B scripts\overlay_renderer.py --preset site_line_1 --clear
.\.venv\Scripts\python.exe -B scripts\process_video.py --preset site_line_1 --track-points --temporal-memory 0.65 --clear
```

Current outputs:

- Single-frame overlay images are written to `python/overlays/`.
- Multi-frame overlay sequences are written to `python/overlays/sequence/`.
- The demo video is written to `python/output_videos/terrain_overlay_demo.mp4`.
- A more compatible fallback video can be written to `python/output_videos/terrain_overlay_demo_small.avi` using `--fourcc MJPG --video-scale 0.5`.
- A normal image preview can be written to `python/overlays/contact_sheet.png`.

Unity is not required for the current prototype. The present research milestone can be completed in Python using OpenCV outputs. Unity should be treated as a later implementation path for real-time AR, mobile visualization, or 3D terrain mesh experiments.

The current persistence mode is a video-based approximation. It has two memory mechanisms: optical-flow endpoint tracking to carry the selected line across frames, and temporal bend smoothing to blend each frame's depth-based bend with previous frames. This should make the demo more stable, but it is still not a true world-anchored AR map.

The next research task is to tune the selected line points and overlay parameters on a good terrain frame. After the visual behavior is acceptable, the next technical step is to replace the current 2D depth-warp approximation with a more physically meaningful 3D projection using camera intrinsics.

## 13. Next Overlay Logic Upgrade: String-Like Surface Conformance

The current overlay is still mostly a 2D line effect. The endpoints are selected in image space, and the interior of the line bends according to depth values. This is useful for a first demo, but it does not fully behave like a physical string laid across an object or uneven terrain.

A better model is:

```txt
selected endpoints -> many rope/control points -> depth-aware surface snapping -> temporal tracking -> projected overlay
```

Recommended short-term upgrade:

- Convert the line from only two endpoints into many control points.
- Track the control points across frames using optical flow, not only point A and point B.
- At each frame, resample the depth map around each control point.
- Move each control point toward nearby depth ridges, slopes, or terrain changes.
- Smooth the control points so the line behaves like a continuous string instead of a noisy curve.
- Add a debug output that shows raw control points, depth-adjusted control points, and the final smoothed string.
- Keep the clicked A/B line as the user input, but treat it as an initial guide rather than a rigid final constraint.

Possible short-term algorithm:

1. Generate `N` control points along the clicked line.
2. For each control point, search a small vertical or normal-direction window in the depth map.
3. Prefer positions that are locally consistent with neighboring control points and have strong depth/surface support.
4. Apply a simple string constraint so adjacent points do not move too far apart.
5. Blend the new control-point positions with the previous frame's positions for temporal stability.

Recommended long-term upgrade:

- Convert monocular depth frames into a 3D point cloud or mesh.
- Estimate camera pose across frames.
- Place the blueprint/string line in a persistent 3D coordinate system.
- Compute a surface path over the terrain mesh, similar to a geodesic or constrained shortest path.
- Reproject that 3D surface-following path into each video frame or AR camera view.

The long-term version is the one that would show viewpoint changes correctly. It requires camera pose estimation and a persistent surface map. Possible tools include COLMAP, ORB-SLAM, ARCore, ARKit, or Unity AR Foundation later. For the current Python prototype, the best next step is dense control-point tracking plus depth-aware snapping.

## 14. Documentation Status

The current documentation set is:

- `README.md`: quick project overview and shortest run sequence.
- `COMMAND_GUIDE.md`: command-by-command usage guide with parameters and troubleshooting.
- `python/README.md`: practical Python workflow.
- `unity/README.md`: optional Unity mesh experiment notes.
- `PROJECT_PLAN.md`: research context, current status, limitations, and future direction.

When new scripts or parameters are added, update `COMMAND_GUIDE.md` first, then mirror the shortest version into `README.md` and `python/README.md`. Keep `PROJECT_PLAN.md` focused on research direction and implementation milestones rather than every command detail.
