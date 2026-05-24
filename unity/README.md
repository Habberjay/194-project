# Unity Setup

Unity is optional for the current prototype.

The active research prototype is the Python/OpenCV pipeline:

```text
video -> frames -> depth maps -> clicked line preset -> terrain-aware overlay -> demo video/contact sheet
```

Use Unity later if you want to experiment with 3D mesh visualization, mobile AR, or Unity AR Foundation. You do not need Unity to select a line, generate the bending overlay, process multiple frames, or create the current demo video.

## Current Unity Purpose

The Unity folder currently supports a separate depth-map-to-mesh experiment:

```text
Depth map PNG -> generated mesh -> blueprint texture on mesh
```

This can help visualize depth maps as terrain-like geometry, but it is not the main overlay workflow.

## Create The Project

1. Open Unity Hub.
2. Create a new `3D Core` project using Unity 2022 LTS.
3. Name it something simple, such as `TerrainBlueprintPrototype`.
4. Copy the contents of this `unity/Assets/` folder into the Unity project's `Assets/` folder.

## Place Assets

Use this layout inside the Unity project:

```text
Assets/
+-- Materials/
+-- Scripts/
|   +-- DepthMapTerrainGenerator.cs
+-- Textures/
    +-- Blueprints/
    +-- DepthMaps/
```

Import one grayscale depth PNG from `python/output/depth_maps/` into:

```text
Assets/Textures/DepthMaps/
```

Import your blueprint image into:

```text
Assets/Textures/Blueprints/
```

Recommended depth map import settings:

- Texture Type: `Default`
- sRGB (Color Texture): off
- Compression: `None`
- Wrap Mode: `Clamp`

Recommended blueprint texture settings:

- Texture Type: `Default`
- Wrap Mode: `Repeat`

## Create The Scene

1. Create an empty GameObject named `BlueprintTerrain`.
2. Add the `DepthMapTerrainGenerator` component.
3. Assign the depth map PNG to `Depth Map`.
4. Assign your blueprint texture to `Blueprint Texture`.
5. Optional: create a material in `Assets/Materials/` using `Unlit/Texture`, then assign it to `Terrain Material`.
6. Click the component menu and choose `Generate Terrain`, or press Play.

If no material is assigned, the script creates a simple unlit material automatically.

## Tune Parameters

- `Terrain Height Scale`: controls vertical displacement.
- `Mesh Resolution`: controls mesh density. Start with `128` on low-end devices.
- `Texture Tiling`: controls how often the blueprint repeats across the mesh.
- `Invert Depth`: toggle this if high areas appear low.

## Test

1. Set `Terrain Height Scale` to `2`.
2. Set `Mesh Resolution` to `128`.
3. Set `Texture Tiling` to `(1, 1)`.
4. Rotate the Scene view and confirm the mesh deforms.
5. Adjust height scale until the blueprint visibly conforms to the terrain.

## Future Unity Direction

Unity becomes important later if the project moves from offline video processing to AR:

- Unity AR Foundation can provide ARCore/ARKit camera tracking.
- AR anchors can help keep overlays stable in world space.
- A generated terrain mesh can be rendered in 3D instead of only drawing on video frames.
- Blueprint lines can become world-space geometry projected onto terrain.

For now, keep the Python results as the main research demo and use Unity only as an optional visualization experiment.
