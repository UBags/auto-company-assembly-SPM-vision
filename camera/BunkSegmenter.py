"""
BunkSegmenter.py v2.0 - UPDATED FOR V0.7 PIPELINE
Bunk hole detection using MobileSAMv2 segmentation with v0.7 preprocessing pipeline.

KEY CHANGES FROM V1:
1. Two-stage circular cropping (outer disc R=250, inner disc R=110)
2. Fixed gamma sequence: [7.75, 6.5, 4.0, 2.0, 1.0] with batch processing
3. Simplified processing: NO morphological opening, NO connected components
4. Direct area filtering on SAM masks (325-1200 pixels)
5. Retained cascade geometric validation for square detection

PIPELINE:
1. Extract outer disc (center 630,350; radius 250)
2. Bilateral Filter (d=21, σ_color=30, σ_space=30)
3. Gamma Correction (7.75, 6.5, 4.0, 2.0, or 1.0)
4. Bilateral Filter (d=21, σ_color=30, σ_space=50)
5. MobileSAMv2 Segmentation
6. Extract inner disc (radius 110 from outer disc center)
7. Filter masks: area 325-1200 pixels in inner disc
8. Cascade geometric validation (square detection for 4-hole patterns)
"""

import warnings
import numpy as np
import torch
import cv2
from typing import List, Dict, Any, Tuple, Optional, Union
from itertools import combinations
import sys
import os

from BaseUtils import get_project_root, getFullyQualifiedName
from camera.ModelManager import ModelManager
from logutils.SlaveLoggers import logBoth
from logutils.Logger import MessageType

# Suppress warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# =============================================================================
# PRINT CONTROL FLAGS
# =============================================================================
PRINT_PREPROCESSING = False
PRINT_SAM_SEGMENTATION = False
PRINT_MASK_FILTERING = False
PRINT_GEOMETRIC_VALIDATION = False
PRINT_BATCH_PROCESSING = False

# =============================================================================
# CONFIGURATION CONSTANTS (V0.7 PIPELINE)
# =============================================================================

# Two-stage cropping parameters
OUTER_DISC_CENTER = (630, 350)  # Center in full image
OUTER_DISC_RADIUS = 250

INNER_DISC_RADIUS = 110  # Radius from center of outer disc

# Gamma values - FIXED SEQUENCE (no brightness-based selection)
GAMMA_SEQUENCE = [7.75, 6.5, 4.0, 2.0, 1.0]

# Area filtering (applied to masks in inner disc)
MIN_MASK_AREA = 325
MAX_MASK_AREA = 1200

# Geometric validation thresholds (retained from v1)
EQUIDISTANT_DISTANCE_DEVIATION_THRESHOLD = 0.25  # 20% deviation
MINIMUM_INTERIOR_ANGLE = 65.0  # degrees
ALLOWED_STD_DEVIATION_IN_ANGLES = 20.0  # degrees
# Expected radius of hole for morphological filtering
EXPECTED_RADIUS_OF_HOLE = 30

def get_gamma_sequence_for_model(expected_count: int) -> List[float]:
    """
    Get appropriate gamma sequence based on expected count.

    Args:
        expected_count: Expected number of holes (2 or 4)

    Returns:
        List of gamma values to try in order
    """
    if expected_count == 2:
        # DOSTPLUS: Different sequence
        return [2.0, 7.75, 4.0, 6.5, 1.0]
    else:
        # DOST or other: Original sequence
        return [2.0, 7.75, 4.0, 6.5, 1.0]

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_circular_mask(shape: Tuple[int, int], center: Tuple[int, int],
                        radius: int) -> np.ndarray:
    """
    Create a circular mask.

    Args:
        shape: (height, width) of image
        center: (cx, cy) center coordinates
        radius: Radius of circle

    Returns:
        Boolean mask (True inside circular region)
    """
    h, w = shape
    cx, cy = center

    y, x = np.ogrid[:h, :w]
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)

    mask = dist <= radius
    return mask


def extract_circular_region(image: np.ndarray, center: Tuple[int, int],
                            radius: int, fill_color: int = 0) -> Tuple[np.ndarray, np.ndarray]:
    """
    Extract circular region from image, painting outside as fill_color.

    Returns:
        Tuple of (cropped_image, mask)
    """
    h, w = image.shape[:2]

    # Create circular mask on full image
    mask = create_circular_mask((h, w), center, radius)

    # Apply mask to image
    if image.ndim == 3:
        result = image.copy()
        for c in range(3):
            result[:, :, c] = np.where(mask, image[:, :, c], fill_color)
    else:
        result = np.where(mask, image, fill_color)

    # Crop to bounding box of circle
    cx, cy = center
    x1 = max(0, cx - radius)
    x2 = min(w, cx + radius)
    y1 = max(0, cy - radius)
    y2 = min(h, cy + radius)

    cropped_image = result[y1:y2, x1:x2]
    cropped_mask = mask[y1:y2, x1:x2]

    return cropped_image, cropped_mask


def order_centers_clockwise(centers: List[Tuple[float, float]],
                            reference_center: Tuple[float, float]) -> List[int]:
    """
    Order centers in clockwise direction based on angle from reference center.

    Args:
        centers: List of (x, y) tuples
        reference_center: (cx, cy) center point for angle calculation

    Returns:
        List of indices in clockwise order
    """
    if len(centers) < 2:
        return list(range(len(centers)))

    ref_x, ref_y = reference_center

    # Calculate angles from reference center
    angles = []
    for cx, cy in centers:
        angle = np.arctan2(cy - ref_y, cx - ref_x)
        angles.append(angle)

    # Sort by angle (counterclockwise)
    sorted_indices = sorted(range(len(angles)), key=lambda i: angles[i], reverse=False)

    return sorted_indices


def calculate_angle_between_points(p1: Tuple[float, float],
                                   p2: Tuple[float, float],
                                   center: Tuple[float, float]) -> float:
    """
    Calculate angle subtended at center by two points (in degrees).

    Args:
        p1: First point (x, y)
        p2: Second point (x, y)
        center: Center point (cx, cy)

    Returns:
        Angle in degrees (0-360)
    """
    cx, cy = center

    # Calculate angles from center to each point
    angle1 = np.arctan2(p1[1] - cy, p1[0] - cx)
    angle2 = np.arctan2(p2[1] - cy, p2[0] - cx)

    # Calculate difference
    angle_diff = angle2 - angle1

    # Normalize to [0, 2π]
    if angle_diff < 0:
        angle_diff += 2 * np.pi

    # Convert to degrees
    return np.degrees(angle_diff)


def compute_polygon_centroid(points: List[Tuple[float, float]]) -> Tuple[float, float]:
    """
    Compute the centroid (geometric center) of a polygon.

    This is robust - the centroid of a polygon is ALWAYS inside a convex polygon
    and provides a reliable reference for angular sorting.

    Args:
        points: List of (x, y) tuples

    Returns:
        (cx, cy) centroid coordinates
    """
    if not points:
        return (0.0, 0.0)

    x_coords = [p[0] for p in points]
    y_coords = [p[1] for p in points]

    cx = sum(x_coords) / len(points)
    cy = sum(y_coords) / len(points)

    return (cx, cy)


def order_points_counterclockwise(points: List[Tuple[float, float]]) -> List[int]:
    """
    Order points in counterclockwise direction using polygon centroid.

    ROBUST: Uses the polygon's own centroid as reference, which is guaranteed
    to be a good reference point regardless of external center location.

    Args:
        points: List of (x, y) tuples

    Returns:
        List of indices in counterclockwise order
    """
    if len(points) < 2:
        return list(range(len(points)))

    # Use polygon's own centroid as reference
    centroid = compute_polygon_centroid(points)
    cx, cy = centroid

    # Calculate angles from centroid to each point
    angles_with_indices = []
    for i, (px, py) in enumerate(points):
        angle = np.arctan2(py - cy, px - cx)
        angles_with_indices.append((angle, i))

    # Sort by angle (counterclockwise)
    angles_with_indices.sort(key=lambda x: x[0])

    # Return indices in order
    return [idx for _, idx in angles_with_indices]


def signed_polygon_area(points: List[Tuple[float, float]]) -> float:
    """
    Calculate signed area of polygon using shoelace formula.

    Positive area = counterclockwise vertices
    Negative area = clockwise vertices

    Args:
        points: List of (x, y) tuples in order

    Returns:
        Signed area (positive for CCW, negative for CW)
    """
    n = len(points)
    if n < 3:
        return 0.0

    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += points[i][0] * points[j][1]
        area -= points[j][0] * points[i][1]

    return area / 2.0


def ensure_counterclockwise_order(points: List[Tuple[float, float]],
                                  indices: List[int]) -> List[int]:
    """
    Ensure points are in counterclockwise order.

    Uses signed area to detect orientation and reverses if needed.

    Args:
        points: Original list of all points
        indices: Indices of selected points

    Returns:
        Indices in counterclockwise order
    """
    if len(indices) < 3:
        return indices

    # Extract points in current order
    ordered_points = [points[i] for i in indices]

    # Check orientation using signed area
    signed_area = signed_polygon_area(ordered_points)

    # If clockwise (negative area), reverse
    if signed_area < 0:
        return list(reversed(indices))

    return indices


def order_polygon_vertices_robust(points: List[Tuple[float, float]],
                                  indices: List[int]) -> List[int]:
    """
    ROBUST polygon vertex ordering that works even when center is outside polygon.

    Method:
    1. Extract subset of points
    2. Calculate their centroid (always inside convex hull)
    3. Sort by angle from centroid
    4. Verify orientation using signed area

    Args:
        points: All points (superset)
        indices: Indices of points to order

    Returns:
        Indices in counterclockwise order
    """
    if len(indices) < 2:
        return indices

    # Extract subset
    subset_points = [points[i] for i in indices]

    # Method 1: Order using subset's centroid
    ordered_indices = order_points_counterclockwise(subset_points)

    # Map back to original indices
    result_indices = [indices[i] for i in ordered_indices]

    # Method 2: Verify and correct orientation using signed area
    result_indices = ensure_counterclockwise_order(points, result_indices)

    return result_indices

# =============================================================================
# ENHANCED find_best_equidistant_subset_euclidean WITH ROBUST ORDERING
# =============================================================================

def find_best_equidistant_subset_euclidean_robust(
        points: List[Tuple[float, float]],
        n: int,
        center: Tuple[float, float],  # Still provided but only for angular spacing check
        tolerance: float = 0.2,
        min_interior_angle: float = 65.0,
        max_interior_angle: float = 115.0,
        allowed_angle_std: float = 20.0
) -> Tuple[Optional[List[int]], float, dict]:
    """
    ROBUST VERSION: Find best subset forming regular polygon.

    KEY IMPROVEMENT: Uses polygon's own centroid for vertex ordering,
    not the external reference center. This works even when center is
    outside the polygon.

    The reference center is still used for angular spacing validation,
    but NOT for vertex ordering.

    Args:
        points: List of (x, y) tuples
        n: Target number of points
        center: Reference center (only for angular spacing check)
        tolerance: Max allowed deviation in side lengths
        min_interior_angle: Minimum interior angle (degrees)
        max_interior_angle: Maximum interior angle (degrees)
        allowed_angle_std: Maximum std deviation of angles (degrees)

    Returns:
        Tuple of (best_indices, best_score, diagnostics) or (None, inf, {})
    """
    _src = __name__

    if len(points) < n:
        return None, float('inf'), {}

    best_indices = None
    best_score = float('inf')
    best_diagnostics = {}

    combo_number = 0

    for combo_indices in combinations(range(len(points)), n):
        combo_number += 1

        # ROBUST ORDERING: Use polygon's own centroid
        ordered_indices = order_polygon_vertices_robust(points, list(combo_indices))

        if PRINT_GEOMETRIC_VALIDATION:
            logBoth('logDebug', _src, f"\n--- Testing combination #{combo_number}: indices {list(combo_indices)} ---", MessageType.GENERAL)
            logBoth('logDebug', _src, f"  Original order: {list(combo_indices)}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"  Ordered (CCW):  {ordered_indices}", MessageType.GENERAL)

        # Extract ordered points
        ordered_points = [points[i] for i in ordered_indices]

        # Verify we got the right number
        if len(ordered_points) != n:
            continue

        # =================================================================
        # 1. CHECK SIDE LENGTHS
        # =================================================================
        distances = []
        for i in range(n):
            p1 = ordered_points[i]
            p2 = ordered_points[(i + 1) % n]
            dist = np.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)
            distances.append(dist)

        if PRINT_GEOMETRIC_VALIDATION:
            logBoth('logDebug', _src, f"  Side lengths: {[f'{d:.2f}' for d in distances]}", MessageType.GENERAL)

        median_dist = np.median(distances)
        if median_dist == 0:
            if PRINT_GEOMETRIC_VALIDATION:
                logBoth('logDebug', _src, f"  ✗ REJECTED: Median distance is zero", MessageType.GENERAL)
            continue

        deviations = [abs(d - median_dist) / median_dist for d in distances]
        max_deviation = max(deviations)

        if PRINT_GEOMETRIC_VALIDATION:
            logBoth('logDebug', _src, f"  Median distance: {median_dist:.2f}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"  Max deviation: {max_deviation:.1%} (threshold: {tolerance:.1%})", MessageType.GENERAL)

        if max_deviation > tolerance:
            if PRINT_GEOMETRIC_VALIDATION:
                logBoth('logDebug', _src, f"  ✗ REJECTED: Distance deviation {max_deviation:.1%} > {tolerance:.1%}", MessageType.GENERAL)
            continue

        if PRINT_GEOMETRIC_VALIDATION:
            logBoth('logDebug', _src, f"  ✓ Distance check passed", MessageType.GENERAL)

        # =================================================================
        # 2. CHECK INTERIOR ANGLES
        # =================================================================
        interior_angles = []
        for i in range(n):
            p_prev = ordered_points[(i - 1) % n]
            p_curr = ordered_points[i]
            p_next = ordered_points[(i + 1) % n]

            # Vectors from current to previous and next
            v1 = np.array([p_prev[0] - p_curr[0], p_prev[1] - p_curr[1]])
            v2 = np.array([p_next[0] - p_curr[0], p_next[1] - p_curr[1]])

            # Calculate angle using atan2(cross, dot)
            dot = v1[0] * v2[0] + v1[1] * v2[1]
            det = v1[0] * v2[1] - v1[1] * v2[0]
            angle_rad = np.arctan2(det, dot)

            angle_deg = np.degrees(angle_rad)
            if angle_deg < 0:
                angle_deg += 360

            # Interior angle should be < 180
            if angle_deg > 180:
                angle_deg = 360 - angle_deg

            interior_angles.append(angle_deg)

        if PRINT_GEOMETRIC_VALIDATION:
            logBoth('logDebug', _src, f"  Interior angles: {[f'{a:.1f}°' for a in interior_angles]}", MessageType.GENERAL)

        min_angle = min(interior_angles)
        max_angle = max(interior_angles)

        if PRINT_GEOMETRIC_VALIDATION:
            logBoth('logDebug', _src, f"  Min angle: {min_angle:.1f}° (threshold: ≥{min_interior_angle}°)", MessageType.GENERAL)
            logBoth('logDebug', _src, f"  Max angle: {max_angle:.1f}° (threshold: ≤{max_interior_angle}°)", MessageType.GENERAL)

        # Check minimum angle requirement
        if min_angle < min_interior_angle:
            if PRINT_GEOMETRIC_VALIDATION:
                logBoth('logDebug', _src, f"  ✗ REJECTED: Min angle {min_angle:.1f}° < {min_interior_angle}°", MessageType.GENERAL)
            continue

        # Check maximum angle requirement (for squares/rectangles)
        if max_angle > max_interior_angle:
            if PRINT_GEOMETRIC_VALIDATION:
                logBoth('logDebug', _src, f"  ✗ REJECTED: Max angle {max_angle:.1f}° > {max_interior_angle}°", MessageType.GENERAL)
            continue

        if PRINT_GEOMETRIC_VALIDATION:
            logBoth('logDebug', _src, f"  ✓ Angle range check passed", MessageType.GENERAL)

        # Special checks for Square (4 holes)
        if n == 4:
            if PRINT_GEOMETRIC_VALIDATION:
                logBoth('logDebug', _src, f"  [4-hole square checks]", MessageType.GENERAL)

            angle_std = np.std(interior_angles)
            if PRINT_GEOMETRIC_VALIDATION:
                logBoth('logDebug', _src, f"  Angle std dev: {angle_std:.1f}° (threshold: ≤{allowed_angle_std}°)", MessageType.GENERAL)
            if angle_std > allowed_angle_std:
                if PRINT_GEOMETRIC_VALIDATION:
                    logBoth('logDebug', _src, f"  ✗ REJECTED: Angle std {angle_std:.1f}° > {allowed_angle_std}°", MessageType.GENERAL)
                continue
            if PRINT_GEOMETRIC_VALIDATION:
                logBoth('logDebug', _src, f"  ✓ Angle uniformity check passed", MessageType.GENERAL)

            mean_angle = np.mean(interior_angles)
            if PRINT_GEOMETRIC_VALIDATION:
                logBoth('logDebug', _src, f"  Mean angle: {mean_angle:.1f}° (target: 90° ± {allowed_angle_std}°)", MessageType.GENERAL)
            if abs(mean_angle - 90.0) > allowed_angle_std:
                if PRINT_GEOMETRIC_VALIDATION:
                    logBoth('logDebug', _src, f"  ✗ REJECTED: Mean angle {mean_angle:.1f}° too far from 90°", MessageType.GENERAL)
                continue
            if PRINT_GEOMETRIC_VALIDATION:
                logBoth('logDebug', _src, f"  ✓ Mean angle check passed", MessageType.GENERAL)

        # =================================================================
        # 3. CHECK ANGULAR SPACING FROM REFERENCE CENTER (optional)
        # =================================================================
        # This uses the external reference center for validation
        angles_from_center = []
        for px, py in ordered_points:
            angle = np.arctan2(py - center[1], px - center[0])
            angles_from_center.append(angle)

        # Calculate angular spacing
        angles_between = []
        for i in range(n):
            a1 = angles_from_center[i]
            a2 = angles_from_center[(i + 1) % n]

            angle_diff = a2 - a1
            if angle_diff < 0:
                angle_diff += 2 * np.pi

            angles_between.append(np.degrees(angle_diff))

        expected_angle = 360.0 / n
        angle_deviations = [abs(a - expected_angle) / expected_angle
                            for a in angles_between]
        max_angle_deviation = max(angle_deviations)

        if PRINT_GEOMETRIC_VALIDATION:
            logBoth('logDebug', _src, f"  Angular spacing from ref center: {[f'{a:.1f}°' for a in angles_between]}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"  Expected: {expected_angle:.1f}° each", MessageType.GENERAL)
            logBoth('logDebug', _src, f"  Max deviation: {max_angle_deviation:.1%}", MessageType.GENERAL)

        # =================================================================
        # 4. CALCULATE SCORE
        # =================================================================
        # Combine distance deviation and angular spacing
        score = (0.7 * max_deviation + 0.3 * max_angle_deviation)
        if PRINT_GEOMETRIC_VALIDATION:
            logBoth('logDebug', _src, f"  Combined score: {score:.4f} (lower is better)", MessageType.GENERAL)

        if score < best_score:
            if PRINT_GEOMETRIC_VALIDATION:
                logBoth('logDebug', _src, f"  ★ NEW BEST! (previous best: {best_score:.4f})", MessageType.GENERAL)
            best_score = score
            best_indices = ordered_indices

            best_diagnostics = {
                'distances': distances,
                'median_distance': median_dist,
                'max_distance_deviation': max_deviation,
                'angles': angles_between,
                'interior_angles': interior_angles,
                'min_interior_angle': min_angle,
                'max_interior_angle': max_angle,
                'expected_angle': expected_angle,
                'max_angle_deviation': max_angle_deviation,
                'score': score
            }
        else:
            if PRINT_GEOMETRIC_VALIDATION:
                logBoth('logDebug', _src, f"  Score not better than current best ({best_score:.4f})", MessageType.GENERAL)

    if PRINT_GEOMETRIC_VALIDATION:
        logBoth('logDebug', _src, f"\n{'=' * 70}", MessageType.GENERAL)
        if best_indices is None:
            logBoth('logDebug', _src, f"FINAL RESULT: No valid combination found after testing {combo_number} combinations", MessageType.GENERAL)
        else:
            logBoth('logDebug', _src, f"FINAL RESULT: Best combination found with score {best_score:.4f}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"  Best indices (CCW ordered): {best_indices}", MessageType.GENERAL)

    return best_indices, best_score, best_diagnostics

# =============================================================================
# MOBILESAM MASK GENERATOR
# =============================================================================

class MobileSAMv2AutomaticMaskGenerator:
    """
    MobileSAMv2 Automatic Mask Generator (V0.7 optimized).

    Uses YOLOv8 for object detection + MobileSAM for segmentation.
    """

    def __init__(
            self,
            sam_predictor,
            yolo_model,
            conf_threshold: float = 0.3,
            iou_threshold: float = 0.7,
            min_mask_region_area: int = MIN_MASK_AREA,
            max_mask_region_area: int = MAX_MASK_AREA,
            use_grid_points: bool = True,
            points_per_side: int = 32,
    ):
        """
        Args:
            sam_predictor: MobileSAM SamPredictor instance
            yolo_model: Loaded YOLO model for object detection
            conf_threshold: Confidence threshold for YOLO detections
            iou_threshold: IoU threshold for NMS
            min_mask_region_area: Minimum mask area to keep
            max_mask_region_area: Maximum mask area to keep
            use_grid_points: If True, also use grid points
            points_per_side: Number of points per side for grid
        """
        self.predictor = sam_predictor
        self.yolo_model = yolo_model
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.min_mask_region_area = min_mask_region_area
        self.max_mask_region_area = max_mask_region_area
        self.use_grid_points = use_grid_points
        self.points_per_side = points_per_side

    def generate(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Generate masks for all objects in the image.

        Args:
            image: RGB image as numpy array (H, W, 3)

        Returns:
            List of mask dictionaries with 'segmentation', 'area', 'bbox', etc.
        """
        masks = []

        # Set image for SAM predictor
        self.predictor.set_image(image)

        # Run YOLO object detection
        try:
            results = self.yolo_model.predict(
                image,
                conf=self.conf_threshold,
                iou=self.iou_threshold,
                verbose=False
            )
        except Exception as e:
            if PRINT_SAM_SEGMENTATION:
                logBoth('logDebug', __name__, f"YOLO prediction error: {e}", MessageType.GENERAL)
            results = []

        # Get bounding boxes from YOLO
        boxes = []
        if len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()

        if PRINT_SAM_SEGMENTATION:
            logBoth('logDebug', __name__, f"[YOLO] Detected {len(boxes)} boxes", MessageType.GENERAL)

        # Generate masks using box prompts
        if len(boxes) > 0:
            for box in boxes:
                try:
                    mask_data = self._generate_mask_from_box(image, box)
                    if mask_data is not None:
                        area = mask_data['area']
                        if self.min_mask_region_area <= area <= self.max_mask_region_area:
                            masks.append(mask_data)
                except Exception as e:
                    if PRINT_SAM_SEGMENTATION:
                        logBoth('logDebug', __name__, f"Warning: Failed to generate mask for box {box}: {e}", MessageType.GENERAL)

        # Optionally add grid-based point prompts
        if self.use_grid_points and len(masks) < 5:
            grid_masks = self._generate_grid_masks(image)
            for gm in grid_masks:
                if not self._overlaps_existing(gm['segmentation'], masks):
                    area = gm['area']
                    if self.min_mask_region_area <= area <= self.max_mask_region_area:
                        masks.append(gm)

        return masks

    def _generate_mask_from_box(self, image: np.ndarray, box: np.ndarray) -> Optional[Dict[str, Any]]:
        """Generate a single mask from a bounding box."""
        x1, y1, x2, y2 = box

        masks, scores, _ = self.predictor.predict(
            point_coords=None,
            point_labels=None,
            box=np.array([x1, y1, x2, y2]),
            multimask_output=False
        )

        if masks is None or len(masks) == 0:
            return None

        mask = masks[0]
        score = scores[0] if scores is not None else 0.0
        area = int(mask.sum())

        return {
            'segmentation': mask,
            'area': area,
            'bbox': [int(x1), int(y1), int(x2 - x1), int(y2 - y1)],
            'predicted_iou': float(score),
            'stability_score': float(score),
        }

    def _generate_grid_masks(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Generate masks using grid point prompts."""
        masks = []
        h, w = image.shape[:2]

        # Sparse grid sampling (1/8th of points)
        step = max(1, (h // self.points_per_side) * 8)

        for y in range(0, h, step):
            for x in range(0, w, step):
                try:
                    point = np.array([[x, y]])
                    label = np.array([1])

                    pred_masks, scores, _ = self.predictor.predict(
                        point_coords=point,
                        point_labels=label,
                        multimask_output=False
                    )

                    if pred_masks is not None and len(pred_masks) > 0:
                        mask = pred_masks[0]
                        area = int(mask.sum())

                        if area > 0:
                            masks.append({
                                'segmentation': mask,
                                'area': area,
                                'bbox': self._mask_to_bbox(mask),
                                'predicted_iou': float(scores[0]) if scores is not None else 0.0,
                                'stability_score': float(scores[0]) if scores is not None else 0.0,
                            })
                except Exception:
                    continue

        return masks

    def _overlaps_existing(self, new_mask: np.ndarray, existing_masks: List[Dict], threshold: float = 0.5) -> bool:
        """Check if new mask overlaps significantly with existing masks."""
        for existing in existing_masks:
            intersection = (new_mask & existing['segmentation']).sum()
            union = (new_mask | existing['segmentation']).sum()

            if union > 0:
                iou = intersection / union
                if iou > threshold:
                    return True

        return False

    def _mask_to_bbox(self, mask: np.ndarray) -> List[int]:
        """Convert binary mask to bounding box [x, y, w, h]."""
        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        if not rows.any() or not cols.any():
            return [0, 0, 0, 0]
        y1, y2 = np.where(rows)[0][[0, -1]]
        x1, x2 = np.where(cols)[0][[0, -1]]
        return [int(x1), int(y1), int(x2 - x1 + 1), int(y2 - y1 + 1)]


# =============================================================================
# Bunk SEGMENTER CLASS
# =============================================================================

class BunkSegmenter:
    """
    Bunk hole segmentation using MobileSAMv2 with V0.7 pipeline.

    Two-stage cropping + bilateral filtering + gamma correction + SAM + geometric validation.
    """

    _instance: Optional['BunkSegmenter'] = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, mobile_sam_checkpoint: Optional[str] = None,
                 yolo_checkpoint: Optional[str] = None):
        """
        Initialize BunkSegmenter.

        Args:
            mobile_sam_checkpoint: Path to mobile_sam.pt (optional, uses ModelManager)
            yolo_checkpoint: Path to ObjectAwareModel.pt (optional, uses ModelManager)
        """

        if BunkSegmenter._initialized:
            return  # Already initialized

        _src = getFullyQualifiedName(__file__, BunkSegmenter)

        if PRINT_PREPROCESSING:
            logBoth('logDebug', _src, "[BunkSegmenter] Initializing with V0.7 pipeline...", MessageType.GENERAL)

        # Load models using ModelManager
        self.model_manager = ModelManager.get_instance()
        self.device = self.model_manager.get_device()

        # Load SAM
        if PRINT_PREPROCESSING:
            logBoth('logDebug', _src, "[BunkSegmenter] Loading MobileSAM...", MessageType.GENERAL)
        self.sam_predictor = self.model_manager.get_sam_predictor()

        # Load YOLO
        if PRINT_PREPROCESSING:
            logBoth('logDebug', _src, "[BunkSegmenter] Loading YOLO ObjectAwareModel...", MessageType.GENERAL)
        self.yolo_model = self.model_manager.get_yolo_model()

        # Create mask generator
        self.mask_generator = MobileSAMv2AutomaticMaskGenerator(
            sam_predictor=self.sam_predictor,
            yolo_model=self.yolo_model,
            conf_threshold=0.3,
            iou_threshold=0.7,
            min_mask_region_area=MIN_MASK_AREA,
            max_mask_region_area=MAX_MASK_AREA,
            use_grid_points=True,
            points_per_side=32
        )

        # Precompute gamma LUTs for all gamma values
        if PRINT_PREPROCESSING:
            logBoth('logDebug', _src, f"[BunkSegmenter] Precomputing gamma LUTs for {GAMMA_SEQUENCE}...", MessageType.GENERAL)
        self.gamma_luts = {}
        for gamma in GAMMA_SEQUENCE:
            inv_gamma = 1.0 / gamma
            lut = np.array([((i / 255.0) ** inv_gamma) * 255
                            for i in range(256)], dtype=np.uint8)
            self.gamma_luts[gamma] = lut

        if PRINT_PREPROCESSING:
            logBoth('logDebug', _src, "[BunkSegmenter] ✓ Initialization complete", MessageType.GENERAL)

        BunkSegmenter._initialized = True

    @classmethod
    def get_instance(cls) -> 'BunkSegmenter':
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = BunkSegmenter(None, None)
        return cls._instance

    def _preprocess_image(self, image: np.ndarray, gamma: float) -> np.ndarray:
        """
        V0.7 Preprocessing Pipeline:

        1. Extract outer disc (630, 350, R=250)
        2. Bilateral filter (21, 30, 30)
        3. Gamma correction
        4. Bilateral filter (21, 30, 50)

        Args:
            image: Input RGB image (full resolution)
            gamma: Gamma correction value

        Returns:
            Processed outer disc image ready for SAM
        """
        # Step 1: Extract outer disc
        outer_disc, outer_mask = extract_circular_region(
            image,
            center=OUTER_DISC_CENTER,
            radius=OUTER_DISC_RADIUS,
            fill_color=0
        )

        # Step 2: First bilateral filter
        bilateral1 = cv2.bilateralFilter(outer_disc, d=21, sigmaColor=30, sigmaSpace=30)

        # Step 3: Gamma correction
        gamma_lut = self.gamma_luts[gamma]
        gamma_corrected = gamma_lut[bilateral1]

        # Step 4: Second bilateral filter
        bilateral2 = cv2.bilateralFilter(gamma_corrected, d=21, sigmaColor=30, sigmaSpace=50)

        return bilateral2

    def _extract_and_filter_masks_in_inner_disc(
            self,
            all_masks: List[Dict[str, Any]],
            outer_disc_image: np.ndarray
    ) -> Tuple[List[Tuple[Tuple[float, float], np.ndarray]], int]:
        """
        Extract inner disc and filter masks by area.

        Args:
            all_masks: All masks from SAM (in outer disc coordinates)
            outer_disc_image: Outer disc image for reference

        Returns:
            Tuple of (filtered_components, count)
            filtered_components: List of ((cx, cy), contour) in inner disc coordinates
        """
        _src = getFullyQualifiedName(__file__, BunkSegmenter)

        if PRINT_MASK_FILTERING:
            logBoth('logDebug', _src, f"\n{'=' * 70}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"INNER DISC FILTERING", MessageType.GENERAL)
            logBoth('logDebug', _src, f"{'=' * 70}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"Total SAM masks: {len(all_masks)}", MessageType.GENERAL)

        # Center of outer disc in cropped coordinates
        outer_h, outer_w = outer_disc_image.shape[:2]
        inner_center = (OUTER_DISC_RADIUS, OUTER_DISC_RADIUS)

        # Extract inner disc mask
        inner_disc_mask = create_circular_mask(
            (outer_h, outer_w),
            inner_center,
            INNER_DISC_RADIUS
        )

        # Calculate bounding box of inner disc
        cx, cy = inner_center
        x1 = max(0, cx - INNER_DISC_RADIUS)
        x2 = min(outer_w, cx + INNER_DISC_RADIUS)
        y1 = max(0, cy - INNER_DISC_RADIUS)
        y2 = min(outer_h, cy + INNER_DISC_RADIUS)

        if PRINT_MASK_FILTERING:
            logBoth('logDebug', _src, f"Inner disc center: {inner_center}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"Inner disc radius: {INNER_DISC_RADIUS}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"Inner disc bbox: x=[{x1}, {x2}], y=[{y1}, {y2}]", MessageType.GENERAL)
            logBoth('logDebug', _src, f"Area filter range: [{MIN_MASK_AREA}, {MAX_MASK_AREA}] pixels", MessageType.GENERAL)

        # Crop inner disc mask
        inner_disc_mask_crop = inner_disc_mask[y1:y2, x1:x2]

        # Filter masks
        valid_components = []
        dropped_masks = []

        if PRINT_MASK_FILTERING:
            logBoth('logDebug', _src, f"\n{'─' * 70}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"MASK-BY-MASK FILTERING:", MessageType.GENERAL)
            logBoth('logDebug', _src, f"{'─' * 70}", MessageType.GENERAL)

        for idx, mask_data in enumerate(all_masks):
            mask = mask_data['segmentation']
            original_area = mask_data['area']

            # Crop mask to inner disc region
            mask_crop = mask[y1:y2, x1:x2]

            # Check presence in inner disc
            mask_in_inner = mask_crop & inner_disc_mask_crop
            pixels_in_inner = mask_in_inner.sum()

            if PRINT_MASK_FILTERING:
                logBoth('logDebug', _src, f"\nMask #{idx}:", MessageType.GENERAL)
                logBoth('logDebug', _src, f"  Original area: {original_area} pixels", MessageType.GENERAL)
                logBoth('logDebug', _src, f"  Pixels in inner disc: {pixels_in_inner}", MessageType.GENERAL)

            # Filter by area
            if pixels_in_inner < MIN_MASK_AREA:
                if PRINT_MASK_FILTERING:
                    logBoth('logDebug', _src, f"  ✗ DROPPED: Too small ({pixels_in_inner} < {MIN_MASK_AREA})", MessageType.GENERAL)
                dropped_masks.append({
                    'index': idx,
                    'reason': 'too_small',
                    'area': pixels_in_inner,
                    'threshold': MIN_MASK_AREA
                })
                continue

            if pixels_in_inner > MAX_MASK_AREA:
                if PRINT_MASK_FILTERING:
                    logBoth('logDebug', _src, f"  ✗ DROPPED: Too large ({pixels_in_inner} > {MAX_MASK_AREA})", MessageType.GENERAL)
                dropped_masks.append({
                    'index': idx,
                    'reason': 'too_large',
                    'area': pixels_in_inner,
                    'threshold': MAX_MASK_AREA
                })
                continue

            # Extract contour
            mask_uint8 = (mask_in_inner * 255).astype(np.uint8)
            contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if len(contours) > 0:
                contour = max(contours, key=cv2.contourArea)

                # Calculate center in inner disc coordinates
                M = cv2.moments(contour)
                if M['m00'] != 0:
                    cx_inner = M['m10'] / M['m00']
                    cy_inner = M['m01'] / M['m00']

                    if PRINT_MASK_FILTERING:
                        logBoth('logDebug', _src, f"  ✓ KEPT: area={pixels_in_inner}, center=({cx_inner:.1f}, {cy_inner:.1f})", MessageType.GENERAL)
                    valid_components.append(((cx_inner, cy_inner), contour))
                else:
                    if PRINT_MASK_FILTERING:
                        logBoth('logDebug', _src, f"  ✗ DROPPED: Invalid moments (M['m00']=0)", MessageType.GENERAL)
                    dropped_masks.append({
                        'index': idx,
                        'reason': 'invalid_moments',
                        'area': pixels_in_inner
                    })
            else:
                if PRINT_MASK_FILTERING:
                    logBoth('logDebug', _src, f"  ✗ DROPPED: No contours found", MessageType.GENERAL)
                dropped_masks.append({
                    'index': idx,
                    'reason': 'no_contours',
                    'area': pixels_in_inner
                })

        if PRINT_MASK_FILTERING:
            logBoth('logDebug', _src, f"\n{'=' * 70}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"FILTERING SUMMARY", MessageType.GENERAL)
            logBoth('logDebug', _src, f"{'=' * 70}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"Total masks: {len(all_masks)}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"Kept: {len(valid_components)}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"Dropped: {len(dropped_masks)}", MessageType.GENERAL)

            if dropped_masks:
                logBoth('logDebug', _src, f"\nDropped mask breakdown:", MessageType.GENERAL)
                reason_counts = {}
                for dm in dropped_masks:
                    reason = dm['reason']
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1
                for reason, count in reason_counts.items():
                    logBoth('logDebug', _src, f"  {reason}: {count}", MessageType.GENERAL)

            logBoth('logDebug', _src, f"\nKept mask details:", MessageType.GENERAL)
            for i, (center, contour) in enumerate(valid_components):
                area = cv2.contourArea(contour)
                logBoth('logDebug', _src, f"  Component {i}: center=({center[0]:.1f}, {center[1]:.1f}), area={area:.0f}", MessageType.GENERAL)

            logBoth('logDebug', _src, f"{'=' * 70}\n", MessageType.GENERAL)

        return valid_components, len(valid_components)

    def _morphological_filter_components(
            self,
            components: List[Tuple[Tuple[float, float], np.ndarray]],
            inner_disc_shape: Tuple[int, int]
    ) -> List[Tuple[Tuple[float, float], np.ndarray]]:
        """
        Apply morphological filtering to clean up components.

        Pipeline:
        1. Create black image
        2. Draw white masks with boundaries
        3. Morphological opening (ellipse kernel 5)
        4. Find connected components
        5. Filter by bounding box dimensions (50-150% of EXPECTED_RADIUS_OF_HOLE)
        6. Filter by area (≥40% of bbox area)

        Args:
            components: List of (center, contour) tuples
            inner_disc_shape: Shape of inner disc image (height, width)

        Returns:
            Filtered list of (center, contour) tuples
        """
        if not components:
            return components

        _src = getFullyQualifiedName(__file__, BunkSegmenter)

        if PRINT_MASK_FILTERING:
            logBoth('logDebug', _src, f"\n{'=' * 70}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"MORPHOLOGICAL FILTERING", MessageType.GENERAL)
            logBoth('logDebug', _src, f"{'=' * 70}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"Input components: {len(components)}", MessageType.GENERAL)

        h, w = inner_disc_shape

        # Step 1: Create all-black image
        black_image = np.zeros((h, w), dtype=np.uint8)

        # Step 2: Draw masks in white (filled + boundary)
        for center, contour in components:
            cv2.drawContours(black_image, [contour], -1, 255, thickness=cv2.FILLED)
            cv2.drawContours(black_image, [contour], -1, 255, thickness=1)

        if PRINT_MASK_FILTERING:
            logBoth('logDebug', _src, f"Drew {len(components)} masks on black image", MessageType.GENERAL)

        # Step 3: Morphological opening with elliptical kernel 5
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        opened = cv2.morphologyEx(black_image, cv2.MORPH_OPEN, kernel)

        if PRINT_MASK_FILTERING:
            logBoth('logDebug', _src, f"Applied morphological opening (ellipse kernel 5)", MessageType.GENERAL)

        # Step 4: Find connected components
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            opened, connectivity=8
        )

        if PRINT_MASK_FILTERING:
            logBoth('logDebug', _src, f"Found {num_labels - 1} connected components (excluding background)", MessageType.GENERAL)

        # Step 5 & 6: Filter by bounding box dimensions and area
        filtered_components = []

        min_dim = int(0.5 * EXPECTED_RADIUS_OF_HOLE)  # 50% of 30 = 15
        max_dim = int(1.5 * EXPECTED_RADIUS_OF_HOLE)  # 150% of 30 = 45

        if PRINT_MASK_FILTERING:
            logBoth('logDebug', _src, f"\nFiltering criteria:", MessageType.GENERAL)
            logBoth('logDebug', _src, f"  Bounding box dimensions: [{min_dim}, {max_dim}] pixels", MessageType.GENERAL)
            logBoth('logDebug', _src, f"  Min area ratio: 40% of bbox area", MessageType.GENERAL)
            logBoth('logDebug', _src, f"\nComponent-by-component:", MessageType.GENERAL)

        for label_id in range(1, num_labels):  # Skip 0 (background)
            # Get bounding box
            x, y, bbox_w, bbox_h, area = stats[label_id]

            if PRINT_MASK_FILTERING:
                logBoth('logDebug', _src, f"\n  Component {label_id}:", MessageType.GENERAL)
                logBoth('logDebug', _src, f"    Bbox: ({x}, {y}), size: {bbox_w}x{bbox_h}", MessageType.GENERAL)
                logBoth('logDebug', _src, f"    Area: {area}", MessageType.GENERAL)

            # Check dimension constraints
            if bbox_w < min_dim or bbox_h < min_dim:
                if PRINT_MASK_FILTERING:
                    logBoth('logDebug', _src, f"    ✗ DROPPED: Dimension too small (min={min_dim})", MessageType.GENERAL)
                continue

            if bbox_w > max_dim or bbox_h > max_dim:
                if PRINT_MASK_FILTERING:
                    logBoth('logDebug', _src, f"    ✗ DROPPED: Dimension too large (max={max_dim})", MessageType.GENERAL)
                continue

            # Check area constraint
            bbox_area = bbox_w * bbox_h
            min_area = 0.4 * bbox_area

            if area < min_area:
                if PRINT_MASK_FILTERING:
                    logBoth('logDebug', _src, f"    ✗ DROPPED: Area {area} < 40% of bbox area ({min_area:.0f})", MessageType.GENERAL)
                continue

            # Extract contour for this component
            component_mask = (labels == label_id).astype(np.uint8) * 255
            contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if len(contours) > 0:
                contour = max(contours, key=cv2.contourArea)

                # Calculate centroid
                M = cv2.moments(contour)
                if M['m00'] != 0:
                    cx = M['m10'] / M['m00']
                    cy = M['m01'] / M['m00']

                    filtered_components.append(((cx, cy), contour))
                    if PRINT_MASK_FILTERING:
                        logBoth('logDebug', _src, f"    ✓ KEPT: center=({cx:.1f}, {cy:.1f})", MessageType.GENERAL)

        if PRINT_MASK_FILTERING:
            logBoth('logDebug', _src, f"\n{'=' * 70}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"MORPHOLOGICAL FILTERING RESULT", MessageType.GENERAL)
            logBoth('logDebug', _src, f"{'=' * 70}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"Input: {len(components)} components", MessageType.GENERAL)
            logBoth('logDebug', _src, f"Output: {len(filtered_components)} components", MessageType.GENERAL)
            logBoth('logDebug', _src, f"Dropped: {len(components) - len(filtered_components)} components", MessageType.GENERAL)
            logBoth('logDebug', _src, f"{'=' * 70}\n", MessageType.GENERAL)

        return filtered_components

    def _apply_cascade_geometric_validation(
            self,
            components: List[Tuple[Tuple[float, float], np.ndarray]],
            expected_count: int,
            model_type: str
    ) -> Tuple[int, List[Tuple[Tuple[float, float], np.ndarray]], bool]:
        """
        Apply cascade geometric validation.

        Returns:
            Tuple of (final_count, final_components, found_definitive_pattern)
        """
        count = len(components)
        valid_components = components
        found_definitive_pattern = False

        _src = getFullyQualifiedName(__file__, BunkSegmenter)

        if PRINT_GEOMETRIC_VALIDATION:
            logBoth('logDebug', _src, f"\n{'#' * 70}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"CASCADE GEOMETRIC VALIDATION", MessageType.GENERAL)
            logBoth('logDebug', _src, f"{'#' * 70}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"Model type: {model_type}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"Expected count: {expected_count}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"Current count: {count}", MessageType.GENERAL)

            # Log input components
            logBoth('logDebug', _src, f"\nInput components for geometric validation:", MessageType.GENERAL)
            for i, (center, contour) in enumerate(components):
                area = cv2.contourArea(contour)
                logBoth('logDebug', _src, f"  Component {i}: center=({center[0]:.1f}, {center[1]:.1f}), area={area:.0f}", MessageType.GENERAL)

        # Reference center for inner disc
        reference_center = (INNER_DISC_RADIUS, INNER_DISC_RADIUS)
        if PRINT_GEOMETRIC_VALIDATION:
            logBoth('logDebug', _src, f"\nReference center for geometry: {reference_center}", MessageType.GENERAL)

        # FIRST: Check for 4-hole square pattern if count >= 4
        if count >= 4:
            # SPECIAL CASE: If expecting 2 holes but found 4+, this is immediate fail
            if expected_count == 2:
                if PRINT_GEOMETRIC_VALIDATION:
                    logBoth('logDebug', _src, f"[Cascade] Found {count} components but expected 2 (DOSTPLUS)", MessageType.GENERAL)
                    logBoth('logDebug', _src, f"[Cascade] ✗ DEFINITIVE REJECTION: Too many holes for DOSTPLUS", MessageType.GENERAL)
                count = 0
                valid_components = []
                found_definitive_pattern = True
            else:
                # Expected 4, proceed with square validation
                if PRINT_GEOMETRIC_VALIDATION:
                    logBoth('logDebug', _src, f"[Cascade] Checking for 4-hole square pattern...", MessageType.GENERAL)
                centers = [center for center, contour in valid_components]

                best_indices, best_score, diagnostics = find_best_equidistant_subset_euclidean_robust(
                    centers, 4, reference_center
                )

                if best_indices is not None:
                    # Found valid 4-hole square
                    count = 4
                    valid_components = [valid_components[i] for i in best_indices]
                    found_definitive_pattern = True

                    if PRINT_GEOMETRIC_VALIDATION:
                        if expected_count == 4:
                            logBoth('logDebug', _src, f"[Cascade] ✓ Found expected 4-hole square pattern!", MessageType.GENERAL)
                        else:
                            logBoth('logDebug', _src, f"[Cascade] ✗ Found 4-hole square but expected {expected_count} holes", MessageType.GENERAL)
                else:
                    # No valid square found
                    if PRINT_GEOMETRIC_VALIDATION:
                        logBoth('logDebug', _src, f"[Cascade] No valid 4-hole square found", MessageType.GENERAL)

                    if expected_count == 4:
                        if PRINT_GEOMETRIC_VALIDATION:
                            logBoth('logDebug', _src, f"[Cascade] No valid 4-hole square (irregular geometry)", MessageType.GENERAL)
                        # DO NOT set found_definitive_pattern = True for expected=4
                        # This allows trying next gamma
                        count = 0
                        valid_components = []
                        # found_definitive_pattern remains False

        # SECOND: Try 2-hole pattern if no definitive pattern and expected==2
        if not found_definitive_pattern and expected_count == 2:
            if PRINT_GEOMETRIC_VALIDATION:
                logBoth('logDebug', _src, f"[Cascade] Checking for 2-hole pattern (distance-based)...", MessageType.GENERAL)

            # NEW LOGIC: Count must be EXACTLY 2
            if count == 2:
                centers = [center for center, contour in valid_components]

                # Calculate distance between the two centers
                c1 = centers[0]
                c2 = centers[1]
                distance = np.sqrt((c2[0] - c1[0]) ** 2 + (c2[1] - c1[1]) ** 2)

                if PRINT_GEOMETRIC_VALIDATION:
                    logBoth('logDebug', _src, f"  Center 1: ({c1[0]:.1f}, {c1[1]:.1f})", MessageType.GENERAL)
                    logBoth('logDebug', _src, f"  Center 2: ({c2[0]:.1f}, {c2[1]:.1f})", MessageType.GENERAL)
                    logBoth('logDebug', _src, f"  Distance between centers: {distance:.1f} pixels", MessageType.GENERAL)
                    logBoth('logDebug', _src, f"  Required range: [75, 100] pixels", MessageType.GENERAL)

                # Check if distance is in range [75, 100]
                if 75 <= distance <= 100:
                    found_definitive_pattern = True
                    if PRINT_GEOMETRIC_VALIDATION:
                        logBoth('logDebug', _src, f"[Cascade] ✓ Found valid 2-hole pattern (distance check passed)!", MessageType.GENERAL)
                else:
                    if PRINT_GEOMETRIC_VALIDATION:
                        logBoth('logDebug', _src, f"[Cascade] ✗ Distance {distance:.1f} outside range [75, 100]", MessageType.GENERAL)
                        logBoth('logDebug', _src, f"[Cascade] Will try next gamma", MessageType.GENERAL)
                    count = 0
                    valid_components = []
                    # found_definitive_pattern remains False - allows continuing to next gamma
            else:
                if PRINT_GEOMETRIC_VALIDATION:
                    logBoth('logDebug', _src, f"[Cascade] ✗ Count is {count}, expected exactly 2", MessageType.GENERAL)
                    logBoth('logDebug', _src, f"[Cascade] Will try next gamma", MessageType.GENERAL)
                count = 0
                valid_components = []
                # found_definitive_pattern remains False - allows continuing to next gamma

        if PRINT_GEOMETRIC_VALIDATION:
            logBoth('logDebug', _src, f"\n{'#'*70}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"CASCADE RESULT", MessageType.GENERAL)
            logBoth('logDebug', _src, f"{'#'*70}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"Final count: {count}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"Definitive pattern: {found_definitive_pattern}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"Match expected: {count == expected_count}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"{'#'*70}\n", MessageType.GENERAL)

        return count, valid_components, found_definitive_pattern

    def _merge_overlapping_masks(self, masks: List[Dict[str, Any]],
                                 overlap_threshold: float = 0.15) -> List[Dict[str, Any]]:
        """
        Merge masks that overlap significantly.

        Args:
            masks: List of mask dictionaries
            overlap_threshold: Overlap ratio threshold for merging

        Returns:
            List of merged masks
        """
        if len(masks) <= 1:
            return masks

        _src = getFullyQualifiedName(__file__, BunkSegmenter)

        if PRINT_MASK_FILTERING:
            logBoth('logDebug', _src, f"\n{'=' * 70}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"MASK MERGING (threshold={overlap_threshold})", MessageType.GENERAL)
            logBoth('logDebug', _src, f"{'=' * 70}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"Input masks: {len(masks)}", MessageType.GENERAL)

            # Log input masks
            for i, mask_data in enumerate(masks):
                logBoth('logDebug', _src, f"  Mask {i}: area={mask_data['area']}", MessageType.GENERAL)

        n = len(masks)
        merged = [False] * n
        result_masks = []
        merge_log = []

        for i in range(n):
            if merged[i]:
                continue

            # Start with mask i
            current_mask = masks[i]['segmentation'].copy()
            masks_to_merge = [i]

            # Find all masks that overlap > threshold
            changed = True
            while changed:
                changed = False
                for j in range(n):
                    if merged[j] or j in masks_to_merge:
                        continue

                    mask_j = masks[j]['segmentation']

                    # Calculate overlap
                    intersection = (current_mask & mask_j).sum()
                    area_i = current_mask.sum()
                    area_j = mask_j.sum()

                    min_area = min(area_i, area_j)
                    if min_area > 0:
                        overlap_ratio = intersection / min_area

                        if overlap_ratio > overlap_threshold:
                            # Merge
                            current_mask = current_mask | mask_j
                            masks_to_merge.append(j)
                            changed = True
                            if PRINT_MASK_FILTERING:
                                logBoth('logDebug', _src, f"  Merging mask {j} into group {masks_to_merge[0]} (overlap={overlap_ratio:.1%})", MessageType.GENERAL)

            # Mark merged
            for idx in masks_to_merge:
                merged[idx] = True

            merged_area = int(current_mask.sum())

            if len(masks_to_merge) > 1:
                merge_log.append({
                    'merged_from': masks_to_merge,
                    'final_area': merged_area
                })
                if PRINT_MASK_FILTERING:
                    logBoth('logDebug', _src, f"  ✓ Created merged mask from {masks_to_merge}: area={merged_area}", MessageType.GENERAL)

            result_masks.append({
                'segmentation': current_mask,
                'area': merged_area,
                'bbox': self._mask_to_bbox(current_mask),
                'predicted_iou': masks[i].get('predicted_iou', 0.0),
                'stability_score': masks[i].get('stability_score', 0.0),
                'merged_from': masks_to_merge
            })

        if PRINT_MASK_FILTERING:
            logBoth('logDebug', _src, f"\nMerge summary:", MessageType.GENERAL)
            logBoth('logDebug', _src, f"  Input masks: {len(masks)}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"  Output masks: {len(result_masks)}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"  Merge operations: {len(merge_log)}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"{'=' * 70}\n", MessageType.GENERAL)

        return result_masks

    def _mask_to_bbox(self, mask: np.ndarray) -> List[int]:
        """Convert binary mask to bounding box [x, y, w, h]."""
        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        if not rows.any() or not cols.any():
            return [0, 0, 0, 0]
        y1, y2 = np.where(rows)[0][[0, -1]]
        x1, x2 = np.where(cols)[0][[0, -1]]
        return [int(x1), int(y1), int(x2 - x1 + 1), int(y2 - y1 + 1)]

    def segment_holes_batch_from_preprocessed(
        self,
        preprocessed_images: List[np.ndarray],
        gamma_values: List[float],
        expected_count: int,
        model_type: str
    ) -> Tuple[int, List[Tuple[Tuple[float, float], np.ndarray]], float, bool]:
        """
        Batch process preprocessed images with early termination.

        EARLY TERMINATION CONDITIONS:
        1. Found valid 4-hole square AND expected==4
        2. Found valid 2-hole pattern AND expected==2
        3. Found definitive mismatch (4-hole square when expected==2)
        4. Found definitive rejection (no valid geometry when expected)

        Args:
            preprocessed_images: List of preprocessed outer disc images
            gamma_values: Corresponding gamma values
            expected_count: Expected number of holes (2 or 4)
            model_type: "DOST" or "DOSTPLUS"

        Returns:
            Tuple of (best_count, best_components, best_gamma, found_definitive)
        """
        if len(preprocessed_images) != len(gamma_values):
            raise ValueError(f"Mismatch: {len(preprocessed_images)} images vs {len(gamma_values)} gammas")

        _src = getFullyQualifiedName(__file__, BunkSegmenter)

        if PRINT_BATCH_PROCESSING:
            logBoth('logDebug', _src, f"[BunkSegmenter] Batch processing {len(preprocessed_images)} gamma values", MessageType.GENERAL)
            logBoth('logDebug', _src, f"[BunkSegmenter] Expected: {expected_count}, Model: {model_type}", MessageType.GENERAL)

        best_count = 0
        best_components = []
        best_gamma = gamma_values[0]
        found_definitive = False

        # Single torch.inference_mode() for all gammas
        with torch.inference_mode():
            for idx, (preprocessed, gamma) in enumerate(zip(preprocessed_images, gamma_values)):
                if PRINT_BATCH_PROCESSING:
                    logBoth('logDebug', _src, f"\n[BunkSegmenter] --- Gamma {idx+1}/{len(preprocessed_images)}: {gamma} ---", MessageType.GENERAL)

                # Run SAM
                masks = self.mask_generator.generate(preprocessed)
                if PRINT_SAM_SEGMENTATION:
                    logBoth('logDebug', _src, f"[BunkSegmenter] SAM detected {len(masks)} raw masks", MessageType.GENERAL)

                # Merge overlapping masks
                masks = self._merge_overlapping_masks(masks, overlap_threshold=0.15)
                if PRINT_MASK_FILTERING:
                    logBoth('logDebug', _src, f"[BunkSegmenter] After merging: {len(masks)} masks", MessageType.GENERAL)

                # Extract and filter in inner disc
                components, count = self._extract_and_filter_masks_in_inner_disc(
                    masks, preprocessed
                )
                if PRINT_MASK_FILTERING:
                    logBoth('logDebug', _src, f"[BunkSegmenter] After inner disc filtering: {count} components", MessageType.GENERAL)

                # Apply morphological filtering
                inner_disc_shape = preprocessed.shape[:2]
                components = self._morphological_filter_components(components, inner_disc_shape)
                count = len(components)
                if PRINT_MASK_FILTERING:
                    logBoth('logDebug', _src, f"[BunkSegmenter] After morphological filtering: {count} components", MessageType.GENERAL)

                # Apply cascade geometric validation
                count, components, definitive = self._apply_cascade_geometric_validation(
                    components, expected_count, model_type
                )

                # CRITICAL FIX: Update best BEFORE early termination check
                # Priority: definitive > count
                if definitive:
                    # Definitive result always wins
                    best_count = count
                    best_components = components
                    best_gamma = gamma
                    found_definitive = definitive
                    if PRINT_BATCH_PROCESSING:
                        logBoth('logDebug', _src, f"[BunkSegmenter] ★ DEFINITIVE result: count={count}, gamma={gamma}", MessageType.GENERAL)
                elif count > best_count:
                    # Better count without definitive result
                    best_count = count
                    best_components = components
                    best_gamma = gamma
                    found_definitive = definitive
                    if PRINT_BATCH_PROCESSING:
                        logBoth('logDebug', _src, f"[BunkSegmenter] ★ New best: count={count}, gamma={gamma}", MessageType.GENERAL)

                # EARLY TERMINATION (now happens AFTER updating best)
                if definitive:
                    # Any definitive result terminates early
                    if PRINT_BATCH_PROCESSING:
                        if count == expected_count:
                            logBoth('logDebug', _src, f"[BunkSegmenter] ✓ EARLY TERMINATION: Found expected definitive pattern!", MessageType.GENERAL)
                        else:
                            logBoth('logDebug', _src, f"[BunkSegmenter] ✓ EARLY TERMINATION: Definitive rejection!", MessageType.GENERAL)
                        logBoth('logDebug', _src, f"[BunkSegmenter] Skipping remaining {len(preprocessed_images) - idx - 1} gammas", MessageType.GENERAL)
                    break

        # Clear GPU cache
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            if PRINT_BATCH_PROCESSING:
                logBoth('logDebug', _src, "[BunkSegmenter] GPU cache cleared", MessageType.GENERAL)

        if PRINT_BATCH_PROCESSING:
            logBoth('logDebug', _src, f"\n[BunkSegmenter] === WINNER: gamma={best_gamma}, count={best_count}, definitive={found_definitive} ===", MessageType.GENERAL)

        return best_count, best_components, best_gamma, found_definitive

    def segment_holes_single(
            self,
            preprocessed_image: np.ndarray,
            gamma: float,
            expected_count: int,
            model_type: str
    ) -> Tuple[int, List[Tuple[Tuple[float, float], np.ndarray]], bool]:
        """
        Process a single preprocessed image (single gamma) with early termination capability.

        This method is used for lazy evaluation - process one gamma at a time
        and stop as soon as a definitive pattern is found.

        Args:
            preprocessed_image: Single preprocessed outer disc image
            gamma: Gamma value used for this image
            expected_count: Expected number of holes (2 or 4)
            model_type: "DOST" or "DOSTPLUS"

        Returns:
            Tuple of (count, components, found_definitive)
            - count: Number of holes detected
            - components: List of (center, contour) tuples
            - found_definitive: True if definitive pattern found (valid geometry)
        """
        _src = getFullyQualifiedName(__file__, BunkSegmenter)

        if PRINT_BATCH_PROCESSING:
            logBoth('logDebug', _src, f"[BunkSegmenter] Processing single gamma {gamma}", MessageType.GENERAL)

        with torch.inference_mode():
            # Run SAM segmentation
            masks = self.mask_generator.generate(preprocessed_image)
            if PRINT_SAM_SEGMENTATION:
                logBoth('logDebug', _src, f"[BunkSegmenter] SAM detected {len(masks)} raw masks", MessageType.GENERAL)

            # Merge overlapping masks
            masks = self._merge_overlapping_masks(masks, overlap_threshold=0.15)
            if PRINT_MASK_FILTERING:
                logBoth('logDebug', _src, f"[BunkSegmenter] After merging: {len(masks)} masks", MessageType.GENERAL)

            # Extract and filter in inner disc
            components, count = self._extract_and_filter_masks_in_inner_disc(
                masks, preprocessed_image
            )
            if PRINT_MASK_FILTERING:
                logBoth('logDebug', _src, f"[BunkSegmenter] After inner disc filtering: {count} components", MessageType.GENERAL)

            # Apply morphological filtering
            inner_disc_shape = preprocessed_image.shape[:2]
            components = self._morphological_filter_components(components, inner_disc_shape)
            count = len(components)
            if PRINT_MASK_FILTERING:
                logBoth('logDebug', _src, f"[BunkSegmenter] After morphological filtering: {count} components", MessageType.GENERAL)

            # Apply cascade geometric validation
            count, components, definitive = self._apply_cascade_geometric_validation(
                components, expected_count, model_type
            )

            if PRINT_BATCH_PROCESSING:
                logBoth('logDebug', _src, f"[BunkSegmenter] Result: count={count}, definitive={definitive}", MessageType.GENERAL)

        # Clear GPU cache
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        return count, components, definitive

def paint_bunk_masks_on_image(
        original_image: np.ndarray,
        components: List[Tuple[Tuple[float, float], np.ndarray]],
        color: Tuple[int, int, int] = (0, 255, 0)
) -> np.ndarray:
    """
    Paint bunk component masks on original image.

    Args:
        original_image: Original full-resolution image (RGB)
        components: List of (center, contour) tuples in inner disc coordinates
        color: RGB color tuple (default: green)

    Returns:
        Image with masks painted
    """
    result = original_image.copy()

    if not components:
        return result

    # Calculate offset from inner disc coords to full image coords
    # Outer disc bbox in full image
    outer_x1 = OUTER_DISC_CENTER[0] - OUTER_DISC_RADIUS
    outer_y1 = OUTER_DISC_CENTER[1] - OUTER_DISC_RADIUS

    # Inner disc bbox in outer disc coords
    inner_x1 = OUTER_DISC_RADIUS - INNER_DISC_RADIUS
    inner_y1 = OUTER_DISC_RADIUS - INNER_DISC_RADIUS

    # Total offset
    offset_x = outer_x1 + inner_x1
    offset_y = outer_y1 + inner_y1

    # Create overlay
    overlay = np.zeros_like(result)

    for center, contour in components:
        if len(contour) > 0:
            # Translate contour to full image coordinates
            translated_contour = contour.copy()
            translated_contour[:, :, 0] += offset_x
            translated_contour[:, :, 1] += offset_y

            # Fill mask
            cv2.drawContours(overlay, [translated_contour], -1, color, thickness=cv2.FILLED)

    # Blend with alpha
    alpha = 0.5
    mask_present = overlay.sum(axis=2) > 0

    for c_idx in range(3):
        result[:, :, c_idx] = np.where(
            mask_present,
            result[:, :, c_idx] * (1 - alpha) + overlay[:, :, c_idx] * alpha,
            result[:, :, c_idx]
        )

    # Draw contours
    for center, contour in components:
        if len(contour) > 0:
            translated_contour = contour.copy()
            translated_contour[:, :, 0] += offset_x
            translated_contour[:, :, 1] += offset_y

            cv2.drawContours(result, [translated_contour], -1, color, thickness=2)

            # Draw center point
            cx, cy = int(center[0] + offset_x), int(center[1] + offset_y)
            cv2.circle(result, (cx, cy), 3, (255, 0, 0), -1)

    # Add count text
    text = f"COUNT: {len(components)}"
    cv2.putText(result, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

    return result