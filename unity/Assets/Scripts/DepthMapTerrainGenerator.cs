using UnityEngine;
using UnityEngine.Rendering;

[ExecuteAlways]
[RequireComponent(typeof(MeshFilter), typeof(MeshRenderer), typeof(MeshCollider))]
public class DepthMapTerrainGenerator : MonoBehaviour
{
    [Header("Inputs")]
    public Texture2D depthMap;
    public Texture2D blueprintTexture;
    public Material terrainMaterial;

    [Header("Terrain")]
    [Range(2, 256)]
    public int meshResolution = 128;
    public float terrainSize = 10f;
    public float terrainHeightScale = 2f;
    public bool invertDepth;

    [Header("Texture")]
    public Vector2 textureTiling = Vector2.one;

    [Header("Options")]
    public bool autoRegenerate = true;
    public bool updateMeshCollider = true;

    private const string GeneratedMeshName = "Generated Depth Terrain";
    private const string GeneratedMaterialName = "Generated Blueprint Material";

    private MeshFilter meshFilter;
    private MeshRenderer meshRenderer;
    private MeshCollider meshCollider;
    private Texture2D readableDepthMap;

    private void OnEnable()
    {
        CacheComponents();

        if (autoRegenerate)
        {
            GenerateTerrain();
        }
    }

    private void OnValidate()
    {
        meshResolution = Mathf.Clamp(meshResolution, 2, 256);
        terrainSize = Mathf.Max(0.01f, terrainSize);
        terrainHeightScale = Mathf.Max(0f, terrainHeightScale);
        textureTiling.x = Mathf.Max(0.001f, textureTiling.x);
        textureTiling.y = Mathf.Max(0.001f, textureTiling.y);

        if (autoRegenerate && isActiveAndEnabled)
        {
            GenerateTerrain();
        }
    }

    private void OnDestroy()
    {
        DestroyReadableDepthMap();
    }

    [ContextMenu("Generate Terrain")]
    public void GenerateTerrain()
    {
        CacheComponents();

        if (depthMap == null)
        {
            Debug.LogWarning("Assign a depth map before generating terrain.", this);
            return;
        }

        Texture2D readableMap = CreateReadableCopy(depthMap);
        if (readableMap == null)
        {
            return;
        }

        int verticesPerSide = meshResolution + 1;
        int vertexCount = verticesPerSide * verticesPerSide;

        Vector3[] vertices = new Vector3[vertexCount];
        Vector2[] uvs = new Vector2[vertexCount];
        int[] triangles = new int[meshResolution * meshResolution * 6];

        for (int z = 0; z < verticesPerSide; z++)
        {
            for (int x = 0; x < verticesPerSide; x++)
            {
                int index = z * verticesPerSide + x;
                float u = x / (float)meshResolution;
                float v = z / (float)meshResolution;
                float depthValue = readableMap.GetPixelBilinear(u, v).grayscale;

                if (invertDepth)
                {
                    depthValue = 1f - depthValue;
                }

                float worldX = (u - 0.5f) * terrainSize;
                float worldZ = (v - 0.5f) * terrainSize;
                float worldY = depthValue * terrainHeightScale;

                vertices[index] = new Vector3(worldX, worldY, worldZ);
                uvs[index] = new Vector2(u * textureTiling.x, v * textureTiling.y);
            }
        }

        int triangleIndex = 0;
        for (int z = 0; z < meshResolution; z++)
        {
            for (int x = 0; x < meshResolution; x++)
            {
                int bottomLeft = z * verticesPerSide + x;
                int bottomRight = bottomLeft + 1;
                int topLeft = bottomLeft + verticesPerSide;
                int topRight = topLeft + 1;

                triangles[triangleIndex++] = bottomLeft;
                triangles[triangleIndex++] = topLeft;
                triangles[triangleIndex++] = topRight;

                triangles[triangleIndex++] = bottomLeft;
                triangles[triangleIndex++] = topRight;
                triangles[triangleIndex++] = bottomRight;
            }
        }

        Mesh mesh = GetOrCreateMesh(vertexCount);
        mesh.Clear();
        mesh.vertices = vertices;
        mesh.uv = uvs;
        mesh.triangles = triangles;
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();

        meshFilter.sharedMesh = mesh;
        ApplyMaterial();

        if (updateMeshCollider)
        {
            UpdateCollider(mesh);
        }
    }

    private void CacheComponents()
    {
        if (meshFilter == null)
        {
            meshFilter = GetComponent<MeshFilter>();
        }

        if (meshRenderer == null)
        {
            meshRenderer = GetComponent<MeshRenderer>();
        }

        if (updateMeshCollider && meshCollider == null)
        {
            meshCollider = GetComponent<MeshCollider>();
        }
    }

    private Mesh GetOrCreateMesh(int vertexCount)
    {
        Mesh mesh = meshFilter.sharedMesh;
        if (mesh == null || mesh.name != GeneratedMeshName)
        {
            mesh = new Mesh();
            mesh.name = GeneratedMeshName;
        }

        mesh.indexFormat = vertexCount > 65535 ? IndexFormat.UInt32 : IndexFormat.UInt16;
        return mesh;
    }

    private void ApplyMaterial()
    {
        Material material = terrainMaterial != null ? terrainMaterial : GetOrCreateGeneratedMaterial();

        if (blueprintTexture != null)
        {
            material.mainTexture = blueprintTexture;
        }

        meshRenderer.sharedMaterial = material;
    }

    private Material GetOrCreateGeneratedMaterial()
    {
        Material current = meshRenderer.sharedMaterial;
        if (current != null && current.name == GeneratedMaterialName)
        {
            return current;
        }

        Shader shader = Shader.Find("Unlit/Texture");
        if (shader == null)
        {
            shader = Shader.Find("Standard");
        }

        Material material = new Material(shader);
        material.name = GeneratedMaterialName;
        return material;
    }

    private void UpdateCollider(Mesh mesh)
    {
        if (meshCollider == null)
        {
            return;
        }

        meshCollider.sharedMesh = null;
        meshCollider.sharedMesh = mesh;
    }

    private Texture2D CreateReadableCopy(Texture2D source)
    {
        DestroyReadableDepthMap();

        RenderTexture previous = RenderTexture.active;
        RenderTexture temporary = RenderTexture.GetTemporary(
            source.width,
            source.height,
            0,
            RenderTextureFormat.ARGB32,
            RenderTextureReadWrite.Linear
        );

        try
        {
            Graphics.Blit(source, temporary);
            RenderTexture.active = temporary;

            readableDepthMap = new Texture2D(source.width, source.height, TextureFormat.RGBA32, false, true);
            readableDepthMap.ReadPixels(new Rect(0, 0, source.width, source.height), 0, 0);
            readableDepthMap.Apply();
            return readableDepthMap;
        }
        catch (System.Exception exception)
        {
            Debug.LogError($"Could not read depth map '{source.name}': {exception.Message}", this);
            DestroyReadableDepthMap();
            return null;
        }
        finally
        {
            RenderTexture.active = previous;
            RenderTexture.ReleaseTemporary(temporary);
        }
    }

    private void DestroyReadableDepthMap()
    {
        if (readableDepthMap == null)
        {
            return;
        }

        if (Application.isPlaying)
        {
            Destroy(readableDepthMap);
        }
        else
        {
            DestroyImmediate(readableDepthMap);
        }

        readableDepthMap = null;
    }
}
