using System;
using UnityEngine;

[ExecuteAlways]
[RequireComponent(typeof(LineRenderer))]
public class SurfaceConformingLine : MonoBehaviour
{
    [Header("Inputs")]
    public DepthMapTerrainGenerator terrain;
    public TextAsset lineMetadata;
    public bool loadMetadataOnEnable = true;

    [Header("Line Points")]
    [Tooltip("Normalized image-space point from top-left origin. Use line_metadata.json values.")]
    public Vector2 pointAImageNormalized = new Vector2(0.2f, 0.72f);
    [Tooltip("Normalized image-space point from top-left origin. Use line_metadata.json values.")]
    public Vector2 pointBImageNormalized = new Vector2(0.8f, 0.72f);
    public bool flipImageY = true;

    [Header("Surface Line")]
    [Range(2, 512)]
    public int sampleCount = 96;
    public float surfaceOffset = 0.03f;
    public float lineWidth = 0.04f;
    public Color surfaceLineColor = new Color(0.25f, 1f, 0.25f, 1f);

    [Header("Flat Comparison")]
    public bool showFlatComparison = true;
    public float flatHeightOffset = 0.6f;
    public Color flatLineColor = new Color(0f, 0.8f, 1f, 1f);

    private const string FlatLineObjectName = "Flat Comparison Line";

    private LineRenderer surfaceLineRenderer;
    private LineRenderer flatLineRenderer;

    private void Reset()
    {
        terrain = GetComponent<DepthMapTerrainGenerator>();
        CacheRenderers();
        ConfigureLineRenderer(surfaceLineRenderer, surfaceLineColor);
        ConfigureLineRenderer(flatLineRenderer, flatLineColor);
    }

    private void OnEnable()
    {
        CacheRenderers();

        if (terrain == null)
        {
            terrain = GetComponent<DepthMapTerrainGenerator>();
        }

        if (loadMetadataOnEnable)
        {
            LoadMetadata(false);
        }

        RebuildLine();
    }

    private void OnValidate()
    {
        sampleCount = Mathf.Clamp(sampleCount, 2, 512);
        surfaceOffset = Mathf.Max(0f, surfaceOffset);
        lineWidth = Mathf.Max(0.001f, lineWidth);
        flatHeightOffset = Mathf.Max(0f, flatHeightOffset);

        if (isActiveAndEnabled)
        {
            CacheRenderers();
            RebuildLine();
        }
    }

    [ContextMenu("Load Metadata")]
    public void LoadMetadata()
    {
        LoadMetadata(true);
        RebuildLine();
    }

    [ContextMenu("Rebuild Surface Line")]
    public void RebuildLine()
    {
        CacheRenderers();

        if (terrain == null)
        {
            terrain = GetComponent<DepthMapTerrainGenerator>();
        }

        if (terrain == null)
        {
            Debug.LogWarning("Assign a DepthMapTerrainGenerator before rebuilding the surface line.", this);
            return;
        }

        terrain.GenerateTerrain();

        Vector3[] surfacePositions = new Vector3[sampleCount];
        Vector3[] flatPositions = new Vector3[sampleCount];
        float flatY = 0f;

        for (int index = 0; index < sampleCount; index++)
        {
            float t = sampleCount == 1 ? 0f : index / (float)(sampleCount - 1);
            Vector2 imagePoint = Vector2.Lerp(pointAImageNormalized, pointBImageNormalized, t);

            if (!terrain.TryGetLocalSurfacePointFromImageNormalized(imagePoint, flipImageY, surfaceOffset, out Vector3 localSurfacePoint))
            {
                Debug.LogWarning("Could not sample the depth terrain surface. Check that a depth map is assigned.", this);
                return;
            }

            Vector3 worldSurfacePoint = terrain.transform.TransformPoint(localSurfacePoint);
            surfacePositions[index] = worldSurfacePoint;

            if (index == 0 || worldSurfacePoint.y > flatY)
            {
                flatY = worldSurfacePoint.y;
            }
        }

        flatY += flatHeightOffset;
        for (int index = 0; index < sampleCount; index++)
        {
            Vector3 point = surfacePositions[index];
            flatPositions[index] = new Vector3(point.x, flatY, point.z);
        }

        ConfigureLineRenderer(surfaceLineRenderer, surfaceLineColor);
        surfaceLineRenderer.positionCount = surfacePositions.Length;
        surfaceLineRenderer.SetPositions(surfacePositions);

        ConfigureLineRenderer(flatLineRenderer, flatLineColor);
        flatLineRenderer.enabled = showFlatComparison;
        flatLineRenderer.positionCount = showFlatComparison ? flatPositions.Length : 0;
        if (showFlatComparison)
        {
            flatLineRenderer.SetPositions(flatPositions);
        }
    }

    private void LoadMetadata(bool logWarnings)
    {
        if (lineMetadata == null)
        {
            if (logWarnings)
            {
                Debug.LogWarning("Assign line_metadata.json as a TextAsset before loading metadata.", this);
            }
            return;
        }

        LineMetadata metadata;
        try
        {
            metadata = JsonUtility.FromJson<LineMetadata>(lineMetadata.text);
        }
        catch (Exception exception)
        {
            Debug.LogWarning($"Could not parse line metadata: {exception.Message}", this);
            return;
        }

        if (metadata == null)
        {
            Debug.LogWarning("Line metadata was empty or invalid.", this);
            return;
        }

        if (metadata.point_a_normalized != null)
        {
            pointAImageNormalized = metadata.point_a_normalized.ToVector2(pointAImageNormalized);
        }

        if (metadata.point_b_normalized != null)
        {
            pointBImageNormalized = metadata.point_b_normalized.ToVector2(pointBImageNormalized);
        }

        if (metadata.unity != null)
        {
            if (metadata.unity.line_samples >= 2)
            {
                sampleCount = Mathf.Clamp(metadata.unity.line_samples, 2, 512);
            }

            flipImageY = metadata.unity.flip_image_y;
            surfaceOffset = Mathf.Max(0f, metadata.unity.recommended_surface_offset);
            flatHeightOffset = Mathf.Max(0f, metadata.unity.recommended_flat_height_offset);
        }
    }

    private void CacheRenderers()
    {
        if (surfaceLineRenderer == null)
        {
            surfaceLineRenderer = GetComponent<LineRenderer>();
        }

        if (flatLineRenderer == null)
        {
            Transform existing = transform.Find(FlatLineObjectName);
            GameObject flatObject = existing != null ? existing.gameObject : new GameObject(FlatLineObjectName);
            flatObject.transform.SetParent(transform, false);
            flatLineRenderer = flatObject.GetComponent<LineRenderer>();
            if (flatLineRenderer == null)
            {
                flatLineRenderer = flatObject.AddComponent<LineRenderer>();
            }
        }
    }

    private void ConfigureLineRenderer(LineRenderer lineRenderer, Color color)
    {
        if (lineRenderer == null)
        {
            return;
        }

        lineRenderer.useWorldSpace = true;
        lineRenderer.startWidth = lineWidth;
        lineRenderer.endWidth = lineWidth;
        lineRenderer.numCapVertices = 4;
        lineRenderer.numCornerVertices = 4;
        lineRenderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        lineRenderer.receiveShadows = false;

        if (lineRenderer.sharedMaterial == null)
        {
            Shader shader = Shader.Find("Sprites/Default");
            if (shader == null)
            {
                shader = Shader.Find("Unlit/Color");
            }
            lineRenderer.sharedMaterial = new Material(shader);
        }

        lineRenderer.sharedMaterial.color = color;
        lineRenderer.startColor = color;
        lineRenderer.endColor = color;
    }

    [Serializable]
    private class LineMetadata
    {
        public Vector2Json point_a_normalized;
        public Vector2Json point_b_normalized;
        public UnitySettings unity;
    }

    [Serializable]
    private class Vector2Json
    {
        public float x;
        public float y;

        public Vector2 ToVector2(Vector2 fallback)
        {
            if (float.IsNaN(x) || float.IsNaN(y))
            {
                return fallback;
            }

            return new Vector2(Mathf.Clamp01(x), Mathf.Clamp01(y));
        }
    }

    [Serializable]
    private class UnitySettings
    {
        public int line_samples = 96;
        public bool flip_image_y = true;
        public float recommended_surface_offset = 0.03f;
        public float recommended_flat_height_offset = 0.6f;
    }
}
