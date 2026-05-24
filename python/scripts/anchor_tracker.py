from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from terrain_line import clamp_points_to_image


@dataclass(frozen=True)
class AnchorConfig:
    roi_padding: int = 160
    min_points: int = 20
    max_misses: int = 5
    homography_min_points: int = 40
    max_corners: int = 500
    quality_level: float = 0.01
    min_distance: int = 8
    ransac_threshold: float = 4.0


@dataclass(frozen=True)
class AnchorTrackResult:
    transform: np.ndarray
    projected_points: np.ndarray
    tracked_points: np.ndarray
    reference_points: np.ndarray
    inlier_mask: np.ndarray
    roi: tuple[int, int, int, int]
    good_points: int
    inliers: int
    confidence: float
    transform_kind: str
    reused_last_transform: bool
    missed_frames: int


class FeatureAnchorTracker:
    def __init__(self, gray_frame: np.ndarray, anchor_points: np.ndarray, config: AnchorConfig) -> None:
        if gray_frame.ndim != 2:
            raise ValueError("gray_frame must be grayscale.")

        self.config = config
        self.height, self.width = gray_frame.shape
        self.roi = compute_anchor_roi(anchor_points, self.width, self.height, config.roi_padding)
        self.reference_points = detect_anchor_features(gray_frame, self.roi, config)
        if self.reference_points.shape[0] < config.min_points:
            raise ValueError(
                f"Only found {self.reference_points.shape[0]} anchor features; need at least {config.min_points}."
            )

        self.previous_gray = gray_frame.copy()
        self.current_points = self.reference_points.copy()
        self.last_transform = np.eye(3, dtype=np.float32)
        self.last_transform_kind = "identity"
        self.missed_frames = 0

    def project(self, current_gray: np.ndarray, points: np.ndarray) -> AnchorTrackResult:
        if current_gray.ndim != 2:
            raise ValueError("current_gray must be grayscale.")

        previous_cv = self.current_points.reshape((-1, 1, 2)).astype(np.float32)
        next_points, status, _error = cv2.calcOpticalFlowPyrLK(
            self.previous_gray,
            current_gray,
            previous_cv,
            None,
            winSize=(31, 31),
            maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
        )

        if next_points is None or status is None:
            return self._reuse_last(current_gray, points)

        good_mask = status.reshape(-1).astype(bool)
        good_reference = self.reference_points[good_mask]
        good_current = next_points.reshape((-1, 2))[good_mask]
        good_count = int(good_mask.sum())

        if good_count < self.config.min_points:
            return self._reuse_last(current_gray, points, good_reference, good_current)

        affine_transform, inlier_mask_raw = cv2.estimateAffinePartial2D(
            good_reference,
            good_current,
            method=cv2.RANSAC,
            ransacReprojThreshold=self.config.ransac_threshold,
            maxIters=2000,
            confidence=0.99,
        )

        transform_kind = "affine"
        transform = None
        if affine_transform is not None and inlier_mask_raw is not None:
            transform = affine_to_homogeneous(affine_transform)
        elif good_count >= self.config.homography_min_points:
            transform, inlier_mask_raw = cv2.findHomography(
                good_reference,
                good_current,
                cv2.RANSAC,
                ransacReprojThreshold=self.config.ransac_threshold,
                maxIters=2000,
                confidence=0.99,
            )
            transform_kind = "homography"

        if transform is None or inlier_mask_raw is None:
            return self._reuse_last(current_gray, points, good_reference, good_current)

        inlier_mask = inlier_mask_raw.reshape(-1).astype(bool)
        inliers = int(inlier_mask.sum())
        if inliers < self.config.min_points and good_count >= self.config.homography_min_points:
            homography_transform, homography_mask = cv2.findHomography(
                good_reference,
                good_current,
                cv2.RANSAC,
                ransacReprojThreshold=self.config.ransac_threshold,
                maxIters=2000,
                confidence=0.99,
            )
            if homography_transform is not None and homography_mask is not None:
                homography_inlier_mask = homography_mask.reshape(-1).astype(bool)
                homography_inliers = int(homography_inlier_mask.sum())
                if homography_inliers >= self.config.min_points:
                    transform = homography_transform
                    inlier_mask = homography_inlier_mask
                    inliers = homography_inliers
                    transform_kind = "homography"

        if inliers < self.config.min_points:
            return self._reuse_last(current_gray, points, good_reference, good_current, inlier_mask)

        self.last_transform = transform.astype(np.float32)
        self.last_transform_kind = transform_kind
        self.reference_points = good_reference
        self.current_points = good_current
        self.previous_gray = current_gray.copy()
        self.missed_frames = 0

        confidence = min(1.0, inliers / max(float(self.config.min_points * 2), 1.0))
        projected = apply_anchor_transform(points, self.last_transform, self.width, self.height)
        return AnchorTrackResult(
            transform=self.last_transform.copy(),
            projected_points=projected,
            tracked_points=good_current.astype(np.float32),
            reference_points=good_reference.astype(np.float32),
            inlier_mask=inlier_mask,
            roi=self.roi,
            good_points=good_count,
            inliers=inliers,
            confidence=float(confidence),
            transform_kind=transform_kind,
            reused_last_transform=False,
            missed_frames=0,
        )

    def _reuse_last(
        self,
        current_gray: np.ndarray,
        points: np.ndarray,
        reference_points: np.ndarray | None = None,
        tracked_points: np.ndarray | None = None,
        inlier_mask: np.ndarray | None = None,
    ) -> AnchorTrackResult:
        self.missed_frames += 1
        if self.missed_frames <= self.config.max_misses:
            self.previous_gray = current_gray.copy()

        reference_points = np.empty((0, 2), dtype=np.float32) if reference_points is None else reference_points
        tracked_points = np.empty((0, 2), dtype=np.float32) if tracked_points is None else tracked_points
        inlier_mask = np.zeros(tracked_points.shape[0], dtype=bool) if inlier_mask is None else inlier_mask
        if tracked_points.shape[0] > 0:
            self.reference_points = reference_points.astype(np.float32)
            self.current_points = tracked_points.astype(np.float32)
            self.previous_gray = current_gray.copy()
        projected = apply_anchor_transform(points, self.last_transform, self.width, self.height)
        confidence = 0.0 if self.missed_frames > self.config.max_misses else 0.15
        return AnchorTrackResult(
            transform=self.last_transform.copy(),
            projected_points=projected,
            tracked_points=tracked_points.astype(np.float32),
            reference_points=reference_points.astype(np.float32),
            inlier_mask=inlier_mask.astype(bool),
            roi=self.roi,
            good_points=int(tracked_points.shape[0]),
            inliers=int(inlier_mask.sum()),
            confidence=confidence,
            transform_kind=self.last_transform_kind,
            reused_last_transform=True,
            missed_frames=self.missed_frames,
        )


def compute_anchor_roi(points: np.ndarray, width: int, height: int, padding: int) -> tuple[int, int, int, int]:
    points = np.asarray(points, dtype=np.float32)
    min_x = int(np.floor(float(np.min(points[:, 0])))) - padding
    min_y = int(np.floor(float(np.min(points[:, 1])))) - padding
    max_x = int(np.ceil(float(np.max(points[:, 0])))) + padding
    max_y = int(np.ceil(float(np.max(points[:, 1])))) + padding

    x1 = max(0, min_x)
    y1 = max(0, min_y)
    x2 = min(width - 1, max_x)
    y2 = min(height - 1, max_y)
    if x2 <= x1 or y2 <= y1:
        raise ValueError("Anchor ROI is empty.")
    return x1, y1, x2, y2


def detect_anchor_features(gray_frame: np.ndarray, roi: tuple[int, int, int, int], config: AnchorConfig) -> np.ndarray:
    x1, y1, x2, y2 = roi
    mask = np.zeros(gray_frame.shape, dtype=np.uint8)
    mask[y1:y2 + 1, x1:x2 + 1] = 255
    corners = cv2.goodFeaturesToTrack(
        gray_frame,
        maxCorners=config.max_corners,
        qualityLevel=config.quality_level,
        minDistance=config.min_distance,
        mask=mask,
        blockSize=7,
    )
    if corners is None:
        return np.empty((0, 2), dtype=np.float32)
    return corners.reshape((-1, 2)).astype(np.float32)


def affine_to_homogeneous(transform: np.ndarray) -> np.ndarray:
    output = np.eye(3, dtype=np.float32)
    output[:2, :] = transform.astype(np.float32)
    return output


def apply_anchor_transform(points: np.ndarray, transform: np.ndarray, width: int, height: int) -> np.ndarray:
    points = np.asarray(points, dtype=np.float32)
    transform = transform.astype(np.float32)
    if transform.shape == (2, 3):
        transformed = cv2.transform(points.reshape((-1, 1, 2)), transform).reshape((-1, 2))
    elif transform.shape == (3, 3):
        transformed = cv2.perspectiveTransform(points.reshape((-1, 1, 2)), transform).reshape((-1, 2))
    else:
        raise ValueError("Anchor transform must be 2x3 affine or 3x3 homography.")
    return clamp_points_to_image(transformed, width=width, height=height)


def draw_anchor_debug(
    frame: np.ndarray,
    result: AnchorTrackResult,
    projected_points: np.ndarray,
    adjusted_points: np.ndarray,
    thickness: int,
) -> np.ndarray:
    output = frame.copy()
    x1, y1, x2, y2 = result.roi
    cv2.rectangle(output, (x1, y1), (x2, y2), (255, 190, 80), 2)

    for index, point in enumerate(result.tracked_points):
        center = (int(round(point[0])), int(round(point[1])))
        is_inlier = index < result.inlier_mask.size and bool(result.inlier_mask[index])
        color = (60, 255, 90) if is_inlier else (40, 80, 255)
        cv2.circle(output, center, 3, color, -1, cv2.LINE_AA)

    cv2.polylines(output, [np.rint(projected_points).astype(np.int32).reshape((-1, 1, 2))], False, (0, 210, 255), max(1, thickness - 1), cv2.LINE_AA)
    cv2.polylines(output, [np.rint(adjusted_points).astype(np.int32).reshape((-1, 1, 2))], False, (70, 255, 80), thickness, cv2.LINE_AA)

    label = (
        f"Anchor: inliers {result.inliers}/{result.good_points}, "
        f"{result.transform_kind}, confidence {result.confidence:.2f}, reused {result.reused_last_transform}"
    )
    cv2.rectangle(output, (0, 0), (output.shape[1], 34), (0, 0, 0), thickness=-1)
    cv2.putText(output, label, (12, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 1, cv2.LINE_AA)
    return output
