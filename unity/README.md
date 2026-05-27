# Unity Surface Demo

Unity is the visual proof stage. Python creates a frame, depth map, and line metadata; Unity turns the depth map into a mesh and draws a flat comparison line plus a surface-conforming line.

```text
python/output/unity_export/ -> unity/Assets/Textures/ -> depth mesh + line renderers
```

## Assets

After running `run_unity_demo.ps1`, these files are copied into the Unity folder:

```text
Assets/Textures/Blueprints/frame.png
Assets/Textures/DepthMaps/depth.png
Assets/Textures/line_metadata.json
```

The active scripts are:

- `DepthMapTerrainGenerator.cs`: builds the mesh from `depth.png` and applies the frame texture.
- `SurfaceConformingLine.cs`: reads `line_metadata.json`, samples the mesh, and draws the conforming line.

## Scene Setup

1. Create an empty GameObject named `BlueprintTerrain`.
2. Add `DepthMapTerrainGenerator`.
3. Assign `DepthMaps/depth.png` to `Depth Map`.
4. Assign `Blueprints/frame.png` to `Blueprint Texture`.
5. Add `SurfaceConformingLine` to the same GameObject.
6. Assign `line_metadata.json` to `Line Metadata`.
7. Use the component menu: `Load Metadata`, then `Rebuild Surface Line`.

Recommended starting values:

- `Mesh Resolution`: `128`
- `Terrain Height Scale`: `2`
- `Texture Tiling`: `(1, 1)`
- `SurfaceConformingLine > Sample Count`: `96`

If the terrain looks upside down, toggle `Invert Depth`.

## Editor Setup

For VS Code C# Dev Kit diagnostics, install a x64 .NET SDK. A runtime alone is not enough. You can verify with:

```powershell
dotnet --list-sdks
```

Unity itself may still compile scripts, but VS Code IntelliSense needs the SDK and Unity-generated `.sln`/`.csproj` files.
