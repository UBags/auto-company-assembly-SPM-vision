# Copyright (c) 2025 Uddipan Bagchi. All rights reserved.
# See LICENSE in the project root for license information.package com.costheta.cortexa.action

"""
CheckTopBearing v2.0 - Integrated with TopBearingSegmentation Pipeline

Detects presence of Top Bearing using advanced image processing pipeline:
1. Annular extraction
2. Background normalization
3. Gamma/Bilateral filtering
4. Contrast normalization
5. Radial tracing and circle fitting
6. Final brightness validation (gamma=3.0 check)

Returns annotated image, detection result, and geometry dictionary.
"""

import copy
import math
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Tuple, List, Any, Optional
import cv2
import numpy as np
import warnings

from utils.QRCodeHelper import getModel_LHSRHS_AndTonnage

warnings.filterwarnings('ignore', '.*h264.*')

# Try to import production modules, fall back to mocks for standalone testing
try:
    from utils.CosThetaFileUtils import *
    from utils.RedisUtils import *
    from BaseUtils import *
    from logutils.SlaveLoggers import logBoth
    from logutils.Logger import MessageType
    from Configuration import *
    CosThetaConfigurator.getInstance()
except ImportError:
    # Standalone testing mode - define mocks
    DOST = "DOST"
    hubAndBottomBearingPictureKeyString = "hubAndBottomBearingPicture"

    def logBoth(level, source, msg, messageType=None):
        colours = {'logInfo': '\033[1;32m', 'logError': '\033[1;31m', 'logWarning': '\033[1;33m', 'logDebug': '\033[1;34m', 'logCritical': '\033[1;31m'}
        reset = '\033[0m'
        colour = colours.get(level, '')
        print(f"{colour}{msg}{reset}")

    class MessageType:
        GENERAL = 1
        SUCCESS = 2
        RISK = 3
        ISSUE = 4
        PROBLEM = 5

    def saveImage(img, name):
        pass

# Import image normalization methods from shared module
try:
    from utils.ImageNormalisationWithMask import (
        rgb2gray,
        ensure_float32,
        create_annular_mask,
        extract_annular_region,
        pixBackgroundNorm_masked,
        pixContrastNorm_masked,
        relative_gamma_masked)
except ImportError:
    logBoth('logError', __name__, "Warning: Could not import ImageNormalisationWithMask utilities", MessageType.ISSUE)


# =============================================================================
# CONSTANTS AND PARAMETERS
# =============================================================================

# Detection parameters from TopBearingSegmentation
MAX_ALLOWED_CENTER_PERCENT_DEVIATION = 25.0
PERCENTILE_CUT_OFF_FOR_BLACK_PIXELS = 25

# ---------------------------------------------------------------------------
# Diagnostic print verbosity flags (set True to enable)
# ---------------------------------------------------------------------------
PRINT_IMAGE_TRANSFORMATION_DETAILS = False  # Steps 1-8: annular extraction, bg norm, gamma, bilateral, contrast, channel, invert, binarisation
PRINT_RADIAL_TRACING_DETAILS = False  # Radial ray-casting that produces list_a / list_b
PRINT_CIRCLE_FITTING_DETAILS = False  # RANSAC + Kasa circle fitting
PRINT_ANCHOR_SELECTION_DETAILS = False  # Which edge (inner/outer) is chosen as anchor
PRINT_THICKNESS_DETERMINATION_DETAILS = False  # Thickness scanning and percentile selection
PRINT_WINNING_BRANCH_SELECTION_DETAILS = False  # Branch scoring, ranking, winner selection


class CheckTopBearing:
    """
    Checks for the presence of the Top Bearing using advanced image processing pipeline
    integrated from TopBearingSegmentation.
    """

    # Annular disc parameters (from TopBearingSegmentation defaults)
    ANNULAR_CENTER_X = 632
    ANNULAR_CENTER_Y = 360
    ANNULAR_OUTER_RADIUS = 120
    ANNULAR_INNER_RADIUS = 0  # Set to 0 to include full disc

    # Background normalization parameters
    BG_NORM_SX = 40
    BG_NORM_SY = 40

    # Contrast normalization parameters
    APPLY_CONTRAST_NORM = True
    CONTRAST_NORM_SX = 10
    CONTRAST_NORM_SY = 10

    # Gamma and filtering
    ALTER_GAMMA = True
    APPLY_BILATERAL = True
    GAMMA_FIRST = True  # Apply gamma before bilateral

    # Channel selection and inversion
    USE_CHANNEL = "Blue"  # "Red", "Green", "Blue", or "All channels"
    INVERT_CHANNELS = True

    # Remove inner region toggle
    REMOVE_INNER_REGION = False

    # Point prompt radius for bearing ring detection
    PROMPT_RADIUS = 40

    # Scoring mode
    SCORING_MODE = "InlierRatio+ArcCov"  # or "InlierRatio+ArcCov+Area"

    # Final gamma check threshold (from original CheckTopBearing)
    FINAL_GAMMA_THRESHOLD = 30.0
    FINAL_GAMMA_VALUE = 3.0

    # Gamma values to test in parallel branches
    GAMMA_CANDIDATES = [3.0, 4.0, 5.0, 6.0, 6.5]

    # Center offsets to test
    CENTER_OFFSETS = [(0, 0), (0, -10)]  # Relative to base center

    # Pre-calculated gamma LUTs
    _gamma_luts = {}

    @classmethod
    def _create_gamma_lut(cls, gamma: float) -> np.ndarray:
        """Create a gamma correction lookup table."""
        if gamma not in cls._gamma_luts:
            inv_gamma = 1.0 / gamma
            lut = np.array([
                ((i / 255.0) ** inv_gamma) * 255
                for i in range(256)
            ]).astype(np.uint8)
            cls._gamma_luts[gamma] = lut
        return cls._gamma_luts[gamma]

    @staticmethod
    def _to_rgb(image: np.ndarray) -> np.ndarray:
        """Convert grayscale to RGB if needed."""
        if image.ndim == 2:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        return image

    @staticmethod
    def _to_gray(image: np.ndarray) -> np.ndarray:
        """Convert RGB to grayscale if needed."""
        if image.ndim == 3:
            return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        return image

    @staticmethod
    def _fit_circle_ransac(points: List[Tuple[float, float]], max_iterations: int = 300,
                          threshold: float = 2.5, min_inliers: int = 10) -> Tuple[Tuple[float, float], float, float, int]:
        """
        Fit a circle to a set of 2D points using RANSAC + Kasa's method.

        Returns:
            center: (cx, cy)
            radius: r
            rmse: root mean square error of inliers
            num_inliers: number of inlier points
        """
        if len(points) < 3:
            return (0.0, 0.0), 0.0, 9999.0, 0

        points_arr = np.array(points, dtype=np.float64)
        best_center = (0.0, 0.0)
        best_radius = 0.0
        best_inliers_mask = None
        best_inlier_count = 0

        for _ in range(max_iterations):
            if len(points_arr) < 3:
                break

            # Randomly sample 3 points
            sample_indices = np.random.choice(len(points_arr), size=3, replace=False)
            sample_points = points_arr[sample_indices]

            # Fit circle using Kasa's method on these 3 points
            cx, cy, r = CheckTopBearing._kasa_fit(sample_points)

            if r <= 0:
                continue

            # Compute distances from all points to this circle
            distances = np.abs(np.sqrt((points_arr[:, 0] - cx)**2 + (points_arr[:, 1] - cy)**2) - r)

            # Find inliers
            inliers_mask = distances < threshold
            inlier_count = np.sum(inliers_mask)

            if inlier_count > best_inlier_count:
                best_inlier_count = inlier_count
                best_inliers_mask = inliers_mask
                best_center = (cx, cy)
                best_radius = r

        # Refine using all inliers if we found any
        if best_inlier_count >= min_inliers:
            inlier_points = points_arr[best_inliers_mask]
            cx, cy, r = CheckTopBearing._kasa_fit(inlier_points)
            best_center = (cx, cy)
            best_radius = r

            # Compute RMSE on inliers
            distances = np.abs(np.sqrt((inlier_points[:, 0] - cx)**2 + (inlier_points[:, 1] - cy)**2) - r)
            rmse = float(np.sqrt(np.mean(distances**2)))
        else:
            rmse = 9999.0

        return best_center, best_radius, rmse, best_inlier_count

    @staticmethod
    def _kasa_fit(points: np.ndarray) -> Tuple[float, float, float]:
        """
        Kasa's algebraic circle fit.

        Returns:
            cx, cy, r
        """
        if len(points) < 3:
            return 0.0, 0.0, 0.0

        x = points[:, 0]
        y = points[:, 1]

        # Build coefficient matrix
        A = np.column_stack([x, y, np.ones_like(x)])
        b = x**2 + y**2

        # Solve least squares
        try:
            coef, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
        except np.linalg.LinAlgError:
            return 0.0, 0.0, 0.0

        cx = coef[0] / 2.0
        cy = coef[1] / 2.0
        r = float(np.sqrt(coef[2] + cx**2 + cy**2))

        return cx, cy, r

    @staticmethod
    def _compute_arc_coverage(points: List[Tuple[float, float]], center: Tuple[float, float], n_bins: int = 36) -> float:
        """
        Compute the fraction of angular bins (around the circle) that contain at least one point.

        Args:
            points: List of (x, y) tuples
            center: Circle center (cx, cy)
            n_bins: Number of angular bins (default 36 = 10° each)

        Returns:
            Fraction of bins with at least one point [0.0, 1.0]
        """
        if len(points) < 1 or n_bins < 1:
            return 0.0

        cx, cy = center
        occupied = set()
        for (px, py) in points:
            angle = math.atan2(py - cy, px - cx)      # −π … +π
            # Map to [0, 2π)
            if angle < 0:
                angle += 2.0 * math.pi
            bin_idx = int(angle / (2.0 * math.pi) * n_bins) % n_bins
            occupied.add(bin_idx)

        return len(occupied) / n_bins

    @classmethod
    def _run_branch(cls, bg_normalized: np.ndarray, annular_mask: np.ndarray,
                    original_annular: np.ndarray, gamma_value: float,
                    det_cx: int, det_cy: int, prompt_r: int,
                    trace_distance: int, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run one branch of the pipeline from the gamma step onwards.

        Everything before gamma (steps 1-2) is shared.  This method applies
        gamma -> remaining steps -> radial detection and returns a result dict
        so the caller can pick the branch with the maximum area.

        All variable values are passed via the *cfg* dict.
        """
        _src = getFullyQualifiedName(__file__, cls)
        branch_images: Dict[str, Any] = {}

        # Unpack pre-read config (plain Python values)
        gamma_first = cfg['gamma_first']
        alter_gamma = cfg['alter_gamma']
        apply_bilateral = cfg['apply_bilateral']
        apply_contrast_norm = cfg['apply_contrast_norm']
        cn_sx = cfg['cn_sx']
        cn_sy = cfg['cn_sy']
        channel_choice = cfg['channel_choice']
        invert = cfg['invert']

        gamma_lut = cls._create_gamma_lut(gamma_value)

        # --- Step 3 & 4: Bilateral + Gamma (order depends on toggle) ---
        if gamma_first:
            # Gamma first
            if alter_gamma:
                step3_result = gamma_lut[bg_normalized]
                branch_images['step3'] = step3_result
                branch_images['step3_name'] = f"Gamma {gamma_value}"
            else:
                step3_result = bg_normalized.copy()
                branch_images['step3'] = step3_result
                branch_images['step3_name'] = "Gamma (skipped)"

            if apply_bilateral:
                step4_result = cv2.bilateralFilter(step3_result, d=21, sigmaColor=30, sigmaSpace=30)
                branch_images['step4'] = step4_result
                branch_images['step4_name'] = "Bilateral (21,30,30)"
            else:
                step4_result = step3_result.copy()
                branch_images['step4'] = step4_result
                branch_images['step4_name'] = "Bilateral (skipped)"
        else:
            # Bilateral first
            if apply_bilateral:
                step3_result = cv2.bilateralFilter(bg_normalized, d=21, sigmaColor=30, sigmaSpace=30)
                branch_images['step3'] = step3_result
                branch_images['step3_name'] = "Bilateral (21,30,30)"
            else:
                step3_result = bg_normalized.copy()
                branch_images['step3'] = step3_result
                branch_images['step3_name'] = "Bilateral (skipped)"

            if alter_gamma:
                step4_result = gamma_lut[step3_result]
                branch_images['step4'] = step4_result
                branch_images['step4_name'] = f"Gamma {gamma_value}"
            else:
                step4_result = step3_result.copy()
                branch_images['step4'] = step4_result
                branch_images['step4_name'] = "Gamma (skipped)"

        if PRINT_IMAGE_TRANSFORMATION_DETAILS:
            logBoth('logDebug', _src,
                    f"[Branch g={gamma_value} c=({det_cx},{det_cy})] "
                    f"Step3: {branch_images['step3_name']}  |  Step4: {branch_images['step4_name']}",
                    MessageType.GENERAL)

        # --- Step 5: Contrast Normalisation ---
        if apply_contrast_norm:
            gray_image = cls._to_gray(step4_result)
            step5_result = pixContrastNorm_masked(gray_image, annular_mask, sx=cn_sx, sy=cn_sy)
            branch_images['step5'] = step5_result
            branch_images['step5_name'] = f"ContrastNorm (sx={cn_sx}, sy={cn_sy})"
        else:
            step5_result = cls._to_gray(step4_result) if step4_result.ndim == 3 else step4_result.copy()
            branch_images['step5'] = step5_result
            branch_images['step5_name'] = "ContrastNorm (skipped)"

        # --- Step 6: Final Bilateral ---
        step6_result = cv2.bilateralFilter(step5_result, d=15, sigmaColor=30, sigmaSpace=40)
        branch_images['step6'] = step6_result
        branch_images['step6_name'] = "Bilateral (15,30,40)"

        if PRINT_IMAGE_TRANSFORMATION_DETAILS:
            logBoth('logDebug', _src,
                    f"[Branch g={gamma_value} c=({det_cx},{det_cy})] "
                    f"Step5: {branch_images['step5_name']}  |  Step6: {branch_images['step6_name']}",
                    MessageType.GENERAL)

        # --- Step 7: Use Channel ---
        if channel_choice != "All channels":
            step6_rgb = cls._to_rgb(step6_result)
            channel_map = {"Red": 0, "Green": 1, "Blue": 2}
            ch_idx = channel_map[channel_choice]
            single_ch = step6_rgb[:, :, ch_idx]
            step7_result = np.stack([single_ch, single_ch, single_ch], axis=-1)
            branch_images['step7'] = step7_result
            branch_images['step7_name'] = f"Channel: {channel_choice}"
        else:
            step7_result = step6_result.copy()
            branch_images['step7'] = step7_result
            branch_images['step7_name'] = "Channel: All (skipped)"

        # --- Step 8: Invert channels ---
        if invert:
            step8_result = (255 - step7_result).astype(np.uint8)
            branch_images['step8'] = step8_result
            branch_images['step8_name'] = "Invert"
        else:
            step8_result = step7_result.copy()
            branch_images['step8'] = step8_result
            branch_images['step8_name'] = "Invert (skipped)"

        if PRINT_IMAGE_TRANSFORMATION_DETAILS:
            logBoth('logDebug', _src,
                    f"[Branch g={gamma_value} c=({det_cx},{det_cy})] "
                    f"Step7: {branch_images['step7_name']}  |  Step8: {branch_images['step8_name']}",
                    MessageType.GENERAL)

        # =================================================================
        # Step 9: Annular ring detection via radial tracing
        # =================================================================
        image_for_detection = cls._to_rgb(step8_result)
        h_det, w_det = image_for_detection.shape[:2]
        cx, cy = det_cx, det_cy

        gray_det = cv2.cvtColor(image_for_detection, cv2.COLOR_RGB2GRAY)

        # Morphological open (circular 5x5 kernel) BEFORE binarisation
        morph_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        gray_det = cv2.morphologyEx(gray_det, cv2.MORPH_OPEN, morph_kernel)

        detection_radius = 60
        det_mask = np.zeros((h_det, w_det), dtype=np.uint8)
        cv2.circle(det_mask, (cx, cy), detection_radius, 255, -1)

        masked_pixels = gray_det[(det_mask == 255) & (gray_det < 250)]
        if len(masked_pixels) > 0:
            threshold_value = int(np.percentile(masked_pixels, PERCENTILE_CUT_OFF_FOR_BLACK_PIXELS))
        else:
            threshold_value = 128

        binary_img = np.zeros_like(gray_det)
        binary_img[gray_det >= threshold_value] = 255
        binary_img[gray_det < threshold_value] = 0

        # Morphological open (circular 5x5 kernel) AFTER binarisation
        binary_img = cv2.morphologyEx(binary_img, cv2.MORPH_OPEN, morph_kernel)

        branch_images['step9_binary'] = binary_img.copy()
        branch_images['step9_name'] = f"Binary (thresh={threshold_value})"

        if PRINT_IMAGE_TRANSFORMATION_DETAILS:
            white_pct = np.sum(binary_img == 255) / max(binary_img.size, 1) * 100
            logBoth('logDebug', _src,
                    f"[Branch g={gamma_value} c=({det_cx},{det_cy})] "
                    f"Binarisation: thresh={threshold_value}, white={white_pct:.1f}%",
                    MessageType.GENERAL)

        # --- Radial tracing with modified start and guard ---
        list_a = []
        list_b = []

        # Separate validation ranges for inner vs outer edge.
        min_valid_dist_inner = prompt_r * 0.65
        max_valid_dist_inner = prompt_r * 1.20
        min_valid_dist_outer = prompt_r * 0.80
        max_valid_dist_outer = prompt_r * 1.60

        # Modification 1: Start scanning from prompt_r - 18
        scan_start = max(1, prompt_r - 18)
        # Modification 2: Guard — ignore black pixels closer than prompt_r - 15
        guard_distance = prompt_r - 15

        for angle_deg in range(0, 360, 2):
            angle_rad = math.radians(angle_deg)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)

            found_a = None
            found_b = None
            dist_a = 0
            dist_b = 0

            for dist in range(scan_start, trace_distance + 1):
                px = int(round(cx + dist * cos_a))
                py = int(round(cy + dist * sin_a))

                if px < 0 or px >= w_det or py < 0 or py >= h_det:
                    break

                pixel_val = binary_img[py, px]

                if found_a is None and pixel_val == 0:
                    if dist < guard_distance:
                        continue
                    found_a = (px, py)
                    dist_a = dist
                elif found_a is not None and found_b is None and pixel_val == 255:
                    found_b = (px, py)
                    dist_b = dist
                    break

            if found_a is not None:
                if min_valid_dist_inner <= dist_a <= max_valid_dist_inner:
                    list_a.append(found_a)

            if found_b is not None:
                if min_valid_dist_outer <= dist_b <= max_valid_dist_outer:
                    list_b.append(found_b)

        if PRINT_RADIAL_TRACING_DETAILS:
            logBoth('logDebug', _src,
                    f"[Branch g={gamma_value} c=({cx},{cy})] Radial tracing: "
                    f"list_a(inner)={len(list_a)} pts, list_b(outer)={len(list_b)} pts, "
                    f"scan_start={scan_start}, guard={guard_distance}, "
                    f"innerRange=[{min_valid_dist_inner:.0f},{max_valid_dist_inner:.0f}], "
                    f"outerRange=[{min_valid_dist_outer:.0f},{max_valid_dist_outer:.0f}]",
                    MessageType.GENERAL)

        # =====================================================================
        # Fit circles via RANSAC then refine using anchor + thickness
        # =====================================================================
        center_a, radius_a, rmse_a, inliers_a = cls._fit_circle_ransac(list_a)
        center_b, radius_b, rmse_b, inliers_b = cls._fit_circle_ransac(list_b)

        # --- Compute inlier ratios ---
        inlier_ratio_a = (inliers_a / len(list_a)) if len(list_a) > 0 else 0.0
        inlier_ratio_b = (inliers_b / len(list_b)) if len(list_b) > 0 else 0.0

        # --- Compute arc coverage ---
        arc_cov_a = cls._compute_arc_coverage(list_a, center_a)
        arc_cov_b = cls._compute_arc_coverage(list_b, center_b)

        if PRINT_CIRCLE_FITTING_DETAILS:
            logBoth('logDebug', _src,
                    f"[Branch g={gamma_value} c=({cx},{cy})] "
                    f"CircleA(inner): c=({center_a[0]:.1f},{center_a[1]:.1f}) r={radius_a:.1f} "
                    f"rmse={rmse_a:.3f} inlRat={inlier_ratio_a:.2f} arcCov={arc_cov_a:.2f}  |  "
                    f"CircleB(outer): c=({center_b[0]:.1f},{center_b[1]:.1f}) r={radius_b:.1f} "
                    f"rmse={rmse_b:.3f} inlRat={inlier_ratio_b:.2f} arcCov={arc_cov_b:.2f}",
                    MessageType.GENERAL)

        # =================================================================
        # Calculate average G value from original annular region
        # (moved here to be just after circles are determined)
        # =================================================================
        avg_inlier_ratio = (inlier_ratio_a + inlier_ratio_b) / 2.0
        avg_arc_coverage = (arc_cov_a + arc_cov_b) / 2.0

        # Calculate score_A early for validation
        score_A = 0.4 * avg_inlier_ratio + 0.6 * avg_arc_coverage

        # Calculate average G value in the detected annular region
        # Use the two circles to create a temporary mask on the original image
        temp_mask = np.zeros((h_det, w_det), dtype=np.uint8)
        cA_int = (int(round(center_a[0])), int(round(center_a[1])))
        cB_int = (int(round(center_b[0])), int(round(center_b[1])))
        rA_int = int(round(radius_a))
        rB_int = int(round(radius_b))

        # Create annular mask using both circles
        if rA_int > 0 and rB_int > 0 and rA_int != rB_int:
            r_inner_temp = min(rA_int, rB_int)
            r_outer_temp = max(rA_int, rB_int)
            # Use center_a for the mask
            cv2.circle(temp_mask, cA_int, r_outer_temp, 255, -1)
            inner_hole_temp = np.zeros((h_det, w_det), dtype=np.uint8)
            cv2.circle(inner_hole_temp, cA_int, r_inner_temp, 255, -1)
            temp_mask = temp_mask - inner_hole_temp

            ring_pixels_temp = original_annular[temp_mask > 0]
            if len(ring_pixels_temp) > 0:
                average_G = float(np.mean(ring_pixels_temp[:, 1]))  # Green channel
            else:
                average_G = 0.0
        else:
            average_G = 0.0

        if PRINT_CIRCLE_FITTING_DETAILS:
            logBoth('logDebug', _src,
                    f"[Branch g={gamma_value} c=({cx},{cy})] "
                    f"Early metrics: score_A={score_A:.3f}, average_G={average_G:.1f}",
                    MessageType.GENERAL)

        # Decide which edge was found better using the same quality metrics
        # as branch scoring: weighted combination of inlier ratio and arc
        # coverage.  Higher = better.
        edge_score_a = 0.4 * inlier_ratio_a + 0.6 * arc_cov_a
        edge_score_b = 0.4 * inlier_ratio_b + 0.6 * arc_cov_b

        # "inner" means ListA / circle_a is better; "outer" means ListB / circle_b
        if edge_score_a >= edge_score_b:
            anchor_edge = "inner"
            anchor_center = center_a
            anchor_radius = radius_a
            anchor_rmse = rmse_a
        else:
            anchor_edge = "outer"
            anchor_center = center_b
            anchor_radius = radius_b
            anchor_rmse = rmse_b

        if PRINT_ANCHOR_SELECTION_DETAILS:
            logBoth('logDebug', _src,
                    f"[Branch g={gamma_value} c=({cx},{cy})] Anchor edge: {anchor_edge} "
                    f"(edgeScore_a={edge_score_a:.3f} [{len(list_a)}pts], "
                    f"edgeScore_b={edge_score_b:.3f} [{len(list_b)}pts])",
                    MessageType.GENERAL)

        # -----------------------------------------------------------------
        # Determine annulus thickness by scanning from the anchor circle
        # -----------------------------------------------------------------
        acx, acy = anchor_center
        a_r = anchor_radius
        list_c = []  # thickness measurements

        for angle_deg in range(0, 360, 1):
            angle_rad = math.radians(angle_deg)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)

            # CoordinateA: where the anchor circle's circumference is
            coord_a_x = acx + a_r * cos_a
            coord_a_y = acy + a_r * sin_a

            # Traverse from CoordinateA inward or outward to find 3
            # consecutive white pixels on the binary image.
            # If anchor is OUTER edge → traverse inward  (subtract)
            # If anchor is INNER edge → traverse outward (add)
            direction = 1 if anchor_edge == "inner" else -1

            consec_white = 0
            first_white_dist = None

            for step in range(1, 60):   # max 60px search
                sx = int(round(coord_a_x + direction * step * cos_a))
                sy = int(round(coord_a_y + direction * step * sin_a))

                if sx < 0 or sx >= w_det or sy < 0 or sy >= h_det:
                    break

                if binary_img[sy, sx] == 255:
                    consec_white += 1
                    if consec_white == 1:
                        first_white_dist = step
                    if consec_white >= 3:
                        # first_white_dist is the thickness for this ray
                        list_c.append(first_white_dist)
                        break
                else:
                    consec_white = 0
                    first_white_dist = None

        if PRINT_THICKNESS_DETERMINATION_DETAILS:
            logBoth('logDebug', _src,
                    f"[Branch g={gamma_value} c=({cx},{cy})] ListC (thickness samples): {len(list_c)}",
                    MessageType.GENERAL)

        # Determine thickness from percentiles, pick closest to 14
        TARGET_THICKNESS = 14
        if len(list_c) >= 5:
            arr_c = np.array(list_c, dtype=np.float64)
            percentiles = [25, 40, 50, 60, 75, 90]
            pct_values = [float(np.percentile(arr_c, p)) for p in percentiles]
            # Pick the percentile value closest to TARGET_THICKNESS
            best_pct_idx = int(np.argmin([abs(v - TARGET_THICKNESS) for v in pct_values]))
            thickness = pct_values[best_pct_idx]
            chosen_pct = percentiles[best_pct_idx]
            if PRINT_THICKNESS_DETERMINATION_DETAILS:
                logBoth('logDebug', _src,
                        f"[Branch g={gamma_value} c=({cx},{cy})] Thickness percentiles: "
                        f"{dict(zip(percentiles, [f'{v:.1f}' for v in pct_values]))}",
                        MessageType.GENERAL)
                logBoth('logDebug', _src,
                        f"[Branch g={gamma_value} c=({cx},{cy})] Chosen thickness={thickness:.1f} "
                        f"(p{chosen_pct}, target={TARGET_THICKNESS})",
                        MessageType.GENERAL)
        else:
            # Fallback: not enough thickness samples, use 14
            thickness = float(TARGET_THICKNESS)
            chosen_pct = -1
            if PRINT_THICKNESS_DETERMINATION_DETAILS:
                logBoth('logDebug', _src,
                        f"[Branch g={gamma_value} c=({cx},{cy})] Too few thickness samples "
                        f"({len(list_c)}), defaulting to {TARGET_THICKNESS}",
                        MessageType.GENERAL)

        # Construct the final two circles from anchor + thickness
        final_center = anchor_center
        if anchor_edge == "inner":
            r_inner_final = anchor_radius
            r_outer_final = anchor_radius + thickness
        else:
            r_outer_final = anchor_radius
            r_inner_final = anchor_radius - thickness

        # Ensure inner < outer
        if r_inner_final > r_outer_final:
            r_inner_final, r_outer_final = r_outer_final, r_inner_final

        # Compute area early (before validation) so it can be used in scoring
        fcx = int(round(final_center[0]))
        fcy = int(round(final_center[1]))
        ri = int(round(r_inner_final))
        ro = int(round(r_outer_final))

        # Calculate preliminary area for score_B calculation
        prelim_valid = (r_inner_final > 0 and r_outer_final > r_inner_final
                        and len(list_a) >= 3 and len(list_b) >= 3)

        if prelim_valid:
            annular_ring_mask = np.zeros((h_det, w_det), dtype=np.uint8)
            cv2.circle(annular_ring_mask, (fcx, fcy), ro, 255, -1)
            inner_hole = np.zeros((h_det, w_det), dtype=np.uint8)
            cv2.circle(inner_hole, (fcx, fcy), ri, 255, -1)
            annular_ring_mask = annular_ring_mask - inner_hole
            ring_bool = annular_ring_mask > 0
            area_pixels = int(np.sum(ring_bool))
        else:
            ring_bool = None
            area_pixels = 0

        # Calculate score_B now that we have area_pixels
        TARGET_THICK_FOR_SCORE = 15
        ideal_area = math.pi * ((prompt_r + TARGET_THICK_FOR_SCORE) ** 2 - prompt_r ** 2)
        area_score = min(area_pixels / ideal_area, 1.0) if ideal_area > 0 else 0.0
        score_B = 0.3 * avg_inlier_ratio + 0.4 * avg_arc_coverage + 0.3 * area_score

        # =================================================================
        # NEW VALIDATION RULE: Only valid if min(score_A, score_B) > 0.65 AND average_G > 77
        # =================================================================
        lower_score = min(score_A, score_B)
        validation_passed = (lower_score > 0.65) and (average_G > 77)

        # Final validity includes both old checks and new validation rule
        annular_valid = prelim_valid and validation_passed
        validation_reason = ""

        if not prelim_valid:
            validation_reason = "Basic geometry check failed"
        elif not validation_passed:
            if lower_score <= 0.65 and average_G <= 77:
                validation_reason = f"Failed: lower_score={lower_score:.3f}<=0.65 AND avg_G={average_G:.1f}<=77"
            elif lower_score <= 0.65:
                validation_reason = f"Failed: lower_score={lower_score:.3f}<=0.65"
            elif average_G <= 77:
                validation_reason = f"Failed: avg_G={average_G:.1f}<=77"

        if PRINT_THICKNESS_DETERMINATION_DETAILS:
            logBoth('logDebug', _src,
                    f"[Branch g={gamma_value} c=({cx},{cy})] Final: anchor={anchor_edge}, "
                    f"center=({final_center[0]:.1f},{final_center[1]:.1f}), "
                    f"r_in={r_inner_final:.1f}, r_out={r_outer_final:.1f}, "
                    f"thickness={thickness:.1f}, score_A={score_A:.3f}, score_B={score_B:.3f}, "
                    f"lower_score={lower_score:.3f}, avg_G={average_G:.1f}, valid={annular_valid}",
                    MessageType.GENERAL)
            if not annular_valid:
                logBoth('logDebug', _src,
                        f"[Branch g={gamma_value} c=({cx},{cy})] Validation: {validation_reason}",
                        MessageType.GENERAL)

        # =================================================================
        # Branch quality scores
        # =================================================================
        scoring_mode = cfg['scoring_mode']

        if scoring_mode == "InlierRatio+ArcCov+Area":
            branch_score = score_B
        else:
            branch_score = score_A

        if not annular_valid:
            branch_score = 0.0

        if PRINT_WINNING_BRANCH_SELECTION_DETAILS:
            logBoth('logDebug', _src,
                    f"[Branch g={gamma_value} c=({cx},{cy})] "
                    f"ScoreA={score_A:.3f} ScoreB={score_B:.3f} "
                    f"(avgInlR={avg_inlier_ratio:.2f}, avgArcCov={avg_arc_coverage:.2f}, "
                    f"areaSc={area_score:.2f}) → using={scoring_mode} → {branch_score:.3f}",
                    MessageType.GENERAL)

        # Draw result overlay
        result_overlay = original_annular.copy()

        if annular_valid:
            overlay_color = np.array([0, 220, 0], dtype=np.float32)
            alpha_overlay = 0.40
            result_float = result_overlay.astype(np.float32)
            result_float[ring_bool] = (
                result_float[ring_bool] * (1 - alpha_overlay) +
                overlay_color * alpha_overlay
            )
            result_overlay = np.clip(result_float, 0, 255).astype(np.uint8)

            result_bgr = cv2.cvtColor(result_overlay, cv2.COLOR_RGB2BGR)

            # Draw inner circle in BLUE, outer circle in CYAN
            cv2.circle(result_bgr, (fcx, fcy), ri, (255, 0, 0), 2)
            cv2.circle(result_bgr, (fcx, fcy), ro, (255, 255, 0), 2)
            # Centre dot in RED
            cv2.circle(result_bgr, (fcx, fcy), 4, (0, 0, 255), -1)

            area_text = f"Area={area_pixels}px  R_in={ri} R_out={ro}"
            center_text = f"C=({fcx},{fcy}) thick={thickness:.1f} anchor={anchor_edge}"
            score_text = (f"scA={score_A:.2f} scB={score_B:.2f} lower={min(score_A, score_B):.2f} "
                          f"inlR={avg_inlier_ratio:.2f} arcCov={avg_arc_coverage:.2f} "
                          f"areaSc={area_score:.2f}")
            gamma_text = f"gamma={gamma_value} ctr=({cx},{cy}) avg_G={average_G:.1f}"

            # cv2.putText(result_bgr, area_text, (10, h_det - 70),
            #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            # cv2.putText(result_bgr, center_text, (10, h_det - 50),
            #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            # cv2.putText(result_bgr, score_text, (10, h_det - 30),
            #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            # cv2.putText(result_bgr, gamma_text, (10, h_det - 10),
            #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
            # cv2.putText(result_bgr, "VALID", (w_det - 80, 25),
            #             cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            result_overlay = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)
        else:
            result_bgr = cv2.cvtColor(result_overlay, cv2.COLOR_RGB2BGR)
            # DON'T draw the circles when invalid per new requirements
            # Only show debugging info in text

            fail_text = f"INVALID: {validation_reason}"
            score_text = f"scA={score_A:.2f} scB={score_B:.2f} lower={min(score_A, score_B):.2f}"
            avg_text = f"avg_G={average_G:.1f} listA={len(list_a)} listB={len(list_b)}"
            gamma_text = f"gamma={gamma_value} ctr=({cx},{cy})"

            # cv2.putText(result_bgr, fail_text, (10, h_det - 70),
            #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            # cv2.putText(result_bgr, score_text, (10, h_det - 50),
            #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            # cv2.putText(result_bgr, avg_text, (10, h_det - 30),
            #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            # cv2.putText(result_bgr, gamma_text, (10, h_det - 10),
            #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
            # cv2.putText(result_bgr, "INVALID", (w_det - 100, 25),
            #             cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            result_overlay = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)
            area_pixels = 0

        branch_images['step9_result'] = result_overlay.copy()

        return {
            'area': area_pixels,
            'score': branch_score,
            'score_A': score_A,
            'score_B': score_B,
            'area_score': area_score,
            'inlier_ratio_a': inlier_ratio_a,
            'inlier_ratio_b': inlier_ratio_b,
            'arc_cov_a': arc_cov_a,
            'arc_cov_b': arc_cov_b,
            'avg_inlier_ratio': avg_inlier_ratio,
            'avg_arc_coverage': avg_arc_coverage,
            'gamma': gamma_value,
            'center': (cx, cy),
            'valid': annular_valid,
            'validation_reason': validation_reason,
            'average_G': average_G,
            'lower_score': min(score_A, score_B),
            'list_a_count': len(list_a),
            'list_b_count': len(list_b),
            'center_a': center_a,
            'center_b': center_b,
            'radius_a': radius_a,
            'radius_b': radius_b,
            'rmse_a': rmse_a,
            'rmse_b': rmse_b,
            'anchor_edge': anchor_edge,
            'thickness': thickness,
            'final_center': final_center,
            'r_inner_final': r_inner_final,
            'r_outer_final': r_outer_final,
            'center_dist_pct': 0.0,  # concentric by construction
            'threshold': threshold_value,
            'pipeline_images': branch_images,
        }

    @staticmethod
    def detect_geometry_only(anImage: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Detect annular geometry WITHOUT requiring hub comparison.
        This is the detection-only version for use in comparison tools.

        Returns:
            Dictionary with:
                'success': bool
                'center': (cx, cy)
                'inner_radius': int
                'outer_radius': int
                'thickness': float
                'score': float
                'average_G': float
            or None if detection fails
        """
        # Convert image to RGB
        if anImage.ndim == 2:
            image_rgb = cv2.cvtColor(anImage, cv2.COLOR_GRAY2RGB)
        elif anImage.shape[2] == 4:
            image_rgb = cv2.cvtColor(anImage, cv2.COLOR_BGRA2RGB)
        else:
            image_rgb = cv2.cvtColor(anImage, cv2.COLOR_BGR2RGB)

        # Step 1: Extract annular region
        inner_rad = CheckTopBearing.ANNULAR_INNER_RADIUS if CheckTopBearing.REMOVE_INNER_REGION else 0
        annular_center = (CheckTopBearing.ANNULAR_CENTER_X, CheckTopBearing.ANNULAR_CENTER_Y)
        outer_radius = CheckTopBearing.ANNULAR_OUTER_RADIUS

        annular_image, annular_mask = extract_annular_region(
            image_rgb, annular_center, outer_radius, inner_rad, fill_color=0
        )

        # Step 2: Background Normalization
        bg_normalized = pixBackgroundNorm_masked(
            annular_image, annular_mask,
            sx=CheckTopBearing.BG_NORM_SX,
            sy=CheckTopBearing.BG_NORM_SY
        )

        # Configuration
        cfg = {
            'gamma_first': CheckTopBearing.GAMMA_FIRST,
            'alter_gamma': CheckTopBearing.ALTER_GAMMA,
            'apply_bilateral': CheckTopBearing.APPLY_BILATERAL,
            'apply_contrast_norm': CheckTopBearing.APPLY_CONTRAST_NORM,
            'cn_sx': CheckTopBearing.CONTRAST_NORM_SX,
            'cn_sy': CheckTopBearing.CONTRAST_NORM_SY,
            'channel_choice': CheckTopBearing.USE_CHANNEL,
            'invert': CheckTopBearing.INVERT_CHANNELS,
            'scoring_mode': CheckTopBearing.SCORING_MODE,
        }

        prompt_r = CheckTopBearing.PROMPT_RADIUS
        detection_radius = 60
        trace_distance = max(detection_radius, outer_radius)

        h_det, w_det = annular_image.shape[:2]
        base_cx = w_det // 2
        base_cy = h_det // 2

        centre_candidates = [
            (base_cx + offset[0], base_cy + offset[1])
            for offset in CheckTopBearing.CENTER_OFFSETS
        ]

        original_annular_copy = annular_image.copy()

        # Disable OpenCV threading
        prev_cv_threads = cv2.getNumThreads()
        cv2.setNumThreads(1)

        # Run branches in parallel
        futures = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            for gamma_val in CheckTopBearing.GAMMA_CANDIDATES:
                for (c_x, c_y) in centre_candidates:
                    future = executor.submit(
                        CheckTopBearing._run_branch,
                        bg_normalized, annular_mask, original_annular_copy,
                        gamma_val, c_x, c_y, prompt_r, trace_distance, cfg
                    )
                    futures.append(future)

        cv2.setNumThreads(prev_cv_threads)

        # Collect results
        all_results = [future.result() for future in futures]
        all_results.sort(key=lambda r: r['score'], reverse=True)
        best = all_results[0]

        if not best['valid']:
            return None

        # Convert to absolute coordinates
        crop_offset_x = annular_center[0] - w_det // 2
        crop_offset_y = annular_center[1] - h_det // 2

        abs_cx = int(round(best['center'][0] + crop_offset_x))
        abs_cy = int(round(best['center'][1] + crop_offset_y))

        return {
            'success': True,
            'center': (abs_cx, abs_cy),
            'inner_radius': int(round(best['r_inner_final'])),
            'outer_radius': int(round(best['r_outer_final'])),
            'thickness': best['thickness'],
            'score': best['score'],
            'average_G': best['average_G'],
        }

    @staticmethod
    def find_inner_white_radius(
            anImage: np.ndarray,
            bearing_center: Tuple[int, int],
            bearing_outer_radius: int,
            bg_norm_s: int = 10,
            bilateral_sigma_color: float = 25.0,
            bilateral_sigma_space: float = 25.0,
            gamma_percentile_cutoff: float = 50.0,
            debug: bool = False,
    ) -> Dict[str, Any]:
        """
        Apply a processing pipeline to a top-bearing image and use
        radial tracing to find the radius of the first white ring from center.

        Called after checkTopBearing() has already determined the bearing
        center and outer radius.  The annular extraction mask is derived
        from bearing_outer_radius:
            outer_radius = bearing_outer_radius
            inner_radius = bearing_outer_radius - 33

        Parameters
        ----------
        anImage : np.ndarray
            Input image (BGR as read by cv2.imread, or RGB).
        bearing_center : tuple of (cx, cy)
            Pixel coordinates of the bearing center in the original image
            (as returned by checkTopBearing geometry dict).
        bearing_outer_radius : int
            Outer radius of the detected bearing annulus
            (as returned by checkTopBearing geometry dict).
        bg_norm_s : int
            sx and sy for background normalisation (default 10).
        bilateral_sigma_color : float
            sigmaColor for bilateral filter (default 25.0).
        bilateral_sigma_space : float
            sigmaSpace for bilateral filter (default 25.0).
        gamma_percentile_cutoff : float
            percentile_cutoff for relative gamma (default 50.0).
        debug : bool
            If True, print intermediate info and return extra images.

        Returns
        -------
        dict with keys:
            'radius'          : int   – the mode of the distance list
            'confidence'      : str   – "100%" or "75%"
            'median'          : float – median of distance list
            'mode'            : int   – mode of distance list
            'coordinates'     : list  – list of (x, y) of first white pixels
            'distances'       : list  – list of distances from center
            'binary_image'    : np.ndarray – the Otsu-binarised image (cropped)
            'debug_images'    : dict  – intermediate images (only if debug=True)
            'params'          : dict  – the pipeline parameters used
        """
        # Derive annular mask radii from the bearing outer radius
        outer_radius = bearing_outer_radius
        inner_radius = bearing_outer_radius - 33
        # ------------------------------------------------------------------
        # Convert to RGB if BGR
        # ------------------------------------------------------------------
        if anImage.ndim == 2:
            image_rgb = cv2.cvtColor(anImage, cv2.COLOR_GRAY2RGB)
        elif anImage.shape[2] == 4:
            image_rgb = cv2.cvtColor(anImage, cv2.COLOR_BGRA2RGB)
        else:
            # Assume BGR from cv2.imread
            image_rgb = cv2.cvtColor(anImage, cv2.COLOR_BGR2RGB)

        debug_images = {}

        # ==================================================================
        # Step 1: Extract Annular Mask
        # ==================================================================
        annular_image, annular_mask = extract_annular_region(
            image_rgb,
            center=bearing_center,
            outer_radius=outer_radius,
            inner_radius=inner_radius,
            fill_color=0,
        )

        if debug:
            debug_images['step1_annular'] = annular_image.copy()
            print(f"[Step 1] Annular extraction: center={bearing_center}, "
                  f"outer_r={outer_radius}, inner_r={inner_radius}, "
                  f"crop_shape={annular_image.shape}")

        # ==================================================================
        # Step 2: Background Normalisation
        # ==================================================================
        bg_normalized = pixBackgroundNorm_masked(
            annular_image, annular_mask,
            sx=bg_norm_s, sy=bg_norm_s, thresh=100, mincount=50, bgval=200,
            smoothx=2, smoothy=2,
        )

        if debug:
            debug_images['step2_bg_norm'] = bg_normalized.copy()
            print(f"[Step 2] Background normalisation (sx={bg_norm_s}, sy={bg_norm_s})")

        # ==================================================================
        # Step 3: Bilateral Filter
        # ==================================================================
        # bg_normalized is uint8 grayscale; bilateralFilter works on it directly
        bilateral_filtered = cv2.bilateralFilter(bg_normalized, d=15,
                                                 sigmaColor=bilateral_sigma_color,
                                                 sigmaSpace=bilateral_sigma_space)

        if debug:
            debug_images['step3_bilateral'] = bilateral_filtered.copy()
            print(f"[Step 3] Bilateral filter (d=15, sigC={bilateral_sigma_color}, sigS={bilateral_sigma_space})")

        # ==================================================================
        # Step 4: Relative Gamma
        # ==================================================================
        gamma_result = relative_gamma_masked(
            bilateral_filtered, annular_mask,
            percentile_cutoff=gamma_percentile_cutoff,
            uplift_gamma=3.0,
            subdue_gamma=0.75,
            kernel_height=0,
            kernel_width=11,
            kernel_type='elliptical',
        )

        if debug:
            debug_images['step4_rel_gamma'] = gamma_result.copy()
            print(f"[Step 4] Relative gamma (pct={gamma_percentile_cutoff}, up=3.0, sub=0.75, kw=11)")

        # ==================================================================
        # Step 5: Morph Open (3×3 ellipse)
        # ==================================================================
        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        morph_opened = cv2.morphologyEx(gamma_result, cv2.MORPH_OPEN, kernel_open)

        if debug:
            debug_images['step5_morph_open'] = morph_opened.copy()
            print(f"[Step 5] Morph open (3×3 ellipse)")

        # ==================================================================
        # Step 6: Morph Close (3×3 ellipse)
        # ==================================================================
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        morph_closed = cv2.morphologyEx(morph_opened, cv2.MORPH_CLOSE, kernel_close)

        if debug:
            debug_images['step6_morph_close'] = morph_closed.copy()
            print(f"[Step 6] Morph close (3×3 ellipse)")

        # ==================================================================
        # Step 7: Otsu Global Threshold
        # ==================================================================
        # Only threshold on the masked region: extract masked pixels,
        # compute Otsu, then apply.
        gray_for_otsu = morph_closed.copy()

        # Apply Otsu only considering masked pixels
        masked_pixels = gray_for_otsu[annular_mask]
        if len(masked_pixels) > 0:
            otsu_thresh, _ = cv2.threshold(
                masked_pixels, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
        else:
            otsu_thresh = 128

        binary = np.zeros_like(gray_for_otsu)
        binary[gray_for_otsu >= otsu_thresh] = 255
        # Zero out anything outside the mask
        binary[~annular_mask] = 0

        if debug:
            debug_images['step7_otsu'] = binary.copy()
            print(f"[Step 7] Otsu threshold = {otsu_thresh}")

        # ==================================================================
        # Radial Tracing
        # ==================================================================
        h_crop, w_crop = binary.shape[:2]

        # Center in the cropped image coordinate system
        cx_crop = w_crop // 2
        cy_crop = h_crop // 2

        # Maximum trace distance = outer_radius (we're already in the cropped region)
        max_trace = outer_radius

        coordinate_list: List[Tuple[int, int]] = []
        distance_list: List[int] = []

        for angle_deg in range(360):
            angle_rad = math.radians(angle_deg)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)

            consec_white = 0
            first_white_coord = None

            for dist in range(1, max_trace + 1):
                px = int(round(cx_crop + dist * cos_a))
                py = int(round(cy_crop + dist * sin_a))

                # Bounds check
                if px < 0 or px >= w_crop or py < 0 or py >= h_crop:
                    break

                if binary[py, px] == 255:
                    consec_white += 1
                    if consec_white == 1:
                        first_white_coord = (px, py)
                    if consec_white >= 2:
                        # Found 2 consecutive white pixels
                        # Store the first one's coordinate and its distance
                        first_dist = int(round(
                            math.sqrt((first_white_coord[0] - cx_crop) ** 2 +
                                      (first_white_coord[1] - cy_crop) ** 2)
                        ))
                        coordinate_list.append(first_white_coord)
                        distance_list.append(first_dist)
                        break
                else:
                    consec_white = 0
                    first_white_coord = None

        # ==================================================================
        # Compute median and mode
        # ==================================================================
        if len(distance_list) == 0:
            return {
                'radius': 0,
                'confidence': '0%',
                'median': 0.0,
                'mode': 0,
                'coordinates': [],
                'distances': [],
                'binary_image': binary,
                'debug_images': debug_images if debug else {},
            }

        median_val = float(np.median(distance_list))
        counter = Counter(distance_list)
        mode_val = counter.most_common(1)[0][0]

        # ==================================================================
        # Confidence determination
        # ==================================================================
        diff = abs(mode_val - median_val)
        if median_val == mode_val:
            confidence = "100%"
        elif diff <= 2:
            confidence = "100%"
        else:
            confidence = "75%"

        if debug:
            print(f"  radius = {mode_val}, confidence = {confidence}")
            print(f"  Distances found: {len(distance_list)}/360")
            print(f"  Median: {median_val:.1f}, Mode: {mode_val}, Diff: {diff:.1f}")
            print(f"  Distance distribution (top 5): {counter.most_common(5)}")

        params_used = {
            'bg_norm_s': bg_norm_s,
            'bilateral_sigma_color': bilateral_sigma_color,
            'bilateral_sigma_space': bilateral_sigma_space,
            'gamma_percentile_cutoff': gamma_percentile_cutoff,
        }

        return {
            'radius': mode_val,
            'confidence': confidence,
            'median': median_val,
            'mode': mode_val,
            'coordinates': coordinate_list,
            'distances': distance_list,
            'binary_image': binary,
            'debug_images': debug_images if debug else {},
            'params': params_used,
        }

    @staticmethod
    def find_inner_white_radius_parallel(
            anImage: np.ndarray,
            bearing_center: Tuple[int, int],
            bearing_outer_radius: int,
    ) -> None:
        """
        Run find_inner_white_radius with 8 parameter combinations in parallel.
        Exits early as soon as any thread returns 100% confidence.

        Parameter grid (2 × 2 × 2 = 8 combinations):
            bg_norm_s:              [5, 10]
            bilateral (sigC, sigS): [(25, 25), (30, 30)]
            gamma_percentile_cutoff:[40, 50]

        If a 100% confidence result is found, prints its radius and confidence.
        If no 100% result is found, picks the radius that occurs most often
        across all results and prints it with 75% confidence.

        Parameters
        ----------
        anImage : np.ndarray
            Input image (BGR).
        bearing_center : tuple of (cx, cy)
            Bearing center in original image coordinates.
        bearing_outer_radius : int
            Outer radius of the detected bearing annulus.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading

        _src = getFullyQualifiedName(__file__, CheckTopBearing)

        # Parameter grid
        bg_norm_values = [5, 10]
        bilateral_values = [(25.0, 25.0), (30.0, 30.0)]
        gamma_pct_values = [40.0, 50.0]

        # Build all 8 parameter combos
        param_combos = []
        for bg_s in bg_norm_values:
            for (sig_c, sig_s) in bilateral_values:
                for g_pct in gamma_pct_values:
                    param_combos.append((bg_s, sig_c, sig_s, g_pct))

        # Shared flag so threads can check if we already have a 100% result
        found_100 = threading.Event()
        winning_result: list[dict | None] = [None] # mutable container for the winner
        all_results: List[Dict] = []     # collect all completed results
        results_lock = threading.Lock()

        def _run_one(bg_s, sig_c, sig_s, g_pct):
            # If another thread already found 100%, skip heavy work
            if found_100.is_set():
                return None
            result = CheckTopBearing.find_inner_white_radius(
                anImage,
                bearing_center=bearing_center,
                bearing_outer_radius=bearing_outer_radius,
                bg_norm_s=bg_s,
                bilateral_sigma_color=sig_c,
                bilateral_sigma_space=sig_s,
                gamma_percentile_cutoff=g_pct,
                debug=False,
            )
            return result

        prev_cv_threads = cv2.getNumThreads()
        cv2.setNumThreads(1)

        try:
            with ThreadPoolExecutor(max_workers=8) as executor:
                future_to_params = {}
                for combo in param_combos:
                    f = executor.submit(_run_one, *combo)
                    future_to_params[f] = combo

                for future in as_completed(future_to_params):
                    result = future.result()
                    if result is None:
                        continue

                    with results_lock:
                        all_results.append(result)

                    if result['confidence'] == '100%':
                        # First 100% wins — signal all other threads to bail
                        if not found_100.is_set():
                            found_100.set()
                            winning_result[0] = result

        finally:
            cv2.setNumThreads(prev_cv_threads)

        # --- Report ---
        if winning_result[0] is not None:
            r = winning_result[0]
            logBoth('logInfo', _src,
                    f"[InnerWhiteRadius] radius = {r['radius']}, "
                    f"confidence = {r['confidence']}, "
                    f"outer_radius = {bearing_outer_radius}",
                    MessageType.SUCCESS)
        elif all_results:
            # No 100% — pick the radius that occurs most often across all results
            all_radii = [r['radius'] for r in all_results if r['radius'] > 0]
            if all_radii:
                counter = Counter(all_radii)
                best_radius = counter.most_common(1)[0][0]
                logBoth('logDebug', _src,
                        f"[InnerWhiteRadius] radius = {best_radius}, "
                        f"confidence = 75%, "
                        f"outer_radius = {bearing_outer_radius}",
                        MessageType.GENERAL)
            else:
                logBoth('logError', _src, "[InnerWhiteRadius] No valid radius found across 8 branches", MessageType.ISSUE)
        else:
            logBoth('logError', _src, "[InnerWhiteRadius] No results returned from any branch", MessageType.ISSUE)

    @staticmethod
    def checkTopBearing(anImage: np.ndarray,
                        currentPictures: Dict[str, np.ndarray | None] = None,
                        componentQRCode: str | None = DOST,
                        gamma: float = 2.0) -> Tuple[np.ndarray | None, bool, Optional[Dict[str, Any]]]:
        """
        Check for the presence of the Top Bearing using integrated pipeline.

        Pipeline:
        1. Extract annular region from current image
        2. Apply background normalization
        3. Run parallel branches with different gamma values and center offsets
        4. Select best branch based on quality scores
        5. If valid annulus detected, perform final brightness comparison
        6. Return annotated image, detection result, and geometry dictionary

        Args:
            anImage: Current camera image to analyze
            currentPictures: Dictionary containing previously captured images,
                           must include 'hubAndBottomBearingPicture'
            componentQRCode: Component QR code for the assembly
            gamma: Unused (kept for signature compatibility)

        Returns:
            Tuple of:
                - Annotated image showing the detection result
                - Boolean indicating if Top Bearing is present (True) or not (False)
                - Dictionary with geometry: {"center": [cx, cy], "inner_radius": ri, "outer_radius": ro}
                  or None if detection failed
        """
        _src = getFullyQualifiedName(__file__, CheckTopBearing)

        # printBoldBlue(
        #     f"CheckTopBearing.checkTopBearing() v2.0 called with "
        #     f"anImage = {anImage.shape if anImage is not None else 'None'}"
        # )

        # Basic validation
        # try:
        #     modelName, lhs_rhs, _ = getModel_LHSRHS_AndTonnage(componentQRCode)
        #     # logBoth('logDebug', _src, f"Got modelName as {modelName}", MessageType.GENERAL)
        # except:
        #     pass

        if anImage is None:
            logBoth('logError', _src, "CheckTopBearing: anImage is None, returning False", MessageType.ISSUE)
            return anImage, False, None

        if currentPictures is None:
            logBoth('logError', _src, "CheckTopBearing: currentPictures is None, returning False", MessageType.ISSUE)
            return anImage, False, None

        # Get the Hub+Bottom Bearing reference image
        base_image = currentPictures.get(hubAndBottomBearingPictureKeyString, None)

        if base_image is None:
            logBoth('logError', _src,
                    "CheckTopBearing: Hub+Bottom Bearing reference image not found, "
                    "returning False",
                    MessageType.ISSUE)
            return anImage, False, None

        try:
            start_time = time.perf_counter()

            # Convert image to RGB if needed
            if anImage.ndim == 2:
                image_rgb = cv2.cvtColor(anImage, cv2.COLOR_GRAY2RGB)
            elif anImage.shape[2] == 4:
                image_rgb = cv2.cvtColor(anImage, cv2.COLOR_BGRA2RGB)
            else:
                image_rgb = cv2.cvtColor(anImage, cv2.COLOR_BGR2RGB)

            # =================================================================
            # SHARED PREFIX — Step 1 & 2 (single branch)
            # =================================================================

            # Step 1: Extract annular region
            inner_rad = CheckTopBearing.ANNULAR_INNER_RADIUS if CheckTopBearing.REMOVE_INNER_REGION else 0

            annular_center = (CheckTopBearing.ANNULAR_CENTER_X, CheckTopBearing.ANNULAR_CENTER_Y)
            outer_radius = CheckTopBearing.ANNULAR_OUTER_RADIUS

            annular_image, annular_mask = extract_annular_region(
                image_rgb,
                center=annular_center,
                outer_radius=outer_radius,
                inner_radius=inner_rad,
                fill_color=0
            )

            if PRINT_IMAGE_TRANSFORMATION_DETAILS:
                h_ann, w_ann = annular_image.shape[:2]
                logBoth('logDebug', _src,
                        f"[Pipeline] Step 1: Annular extraction — "
                        f"center={annular_center}, outerR={outer_radius}, "
                        f"innerR={inner_rad}, crop={w_ann}x{h_ann}",
                        MessageType.GENERAL)

            # Step 2: Background Normalisation
            bg_sx = CheckTopBearing.BG_NORM_SX
            bg_sy = CheckTopBearing.BG_NORM_SY
            bg_normalized = pixBackgroundNorm_masked(
                annular_image, annular_mask, sx=bg_sx, sy=bg_sy
            )

            if PRINT_IMAGE_TRANSFORMATION_DETAILS:
                logBoth('logDebug', _src,
                        f"[Pipeline] Step 2: Background normalisation — sx={bg_sx}, sy={bg_sy}",
                        MessageType.GENERAL)

            # =================================================================
            # PRE-READ all configuration into plain Python values
            # =================================================================
            cfg = {
                'gamma_first': CheckTopBearing.GAMMA_FIRST,
                'alter_gamma': CheckTopBearing.ALTER_GAMMA,
                'apply_bilateral': CheckTopBearing.APPLY_BILATERAL,
                'apply_contrast_norm': CheckTopBearing.APPLY_CONTRAST_NORM,
                'cn_sx': CheckTopBearing.CONTRAST_NORM_SX,
                'cn_sy': CheckTopBearing.CONTRAST_NORM_SY,
                'channel_choice': CheckTopBearing.USE_CHANNEL,
                'invert': CheckTopBearing.INVERT_CHANNELS,
                'scoring_mode': CheckTopBearing.SCORING_MODE,
            }

            prompt_r = CheckTopBearing.PROMPT_RADIUS
            detection_radius = 60
            trace_distance = max(detection_radius, outer_radius)

            # Image centre for detection (centre of cropped annular image)
            h_det, w_det = annular_image.shape[:2]
            base_cx = w_det // 2
            base_cy = h_det // 2

            gamma_candidates = CheckTopBearing.GAMMA_CANDIDATES
            centre_candidates = [
                (base_cx + offset[0], base_cy + offset[1])
                for offset in CheckTopBearing.CENTER_OFFSETS
            ]

            original_annular_copy = annular_image.copy()

            n_branches = len(gamma_candidates) * len(centre_candidates)
            if PRINT_WINNING_BRANCH_SELECTION_DETAILS:
                logBoth('logDebug', _src,
                        f"[Pipeline] Launching {len(gamma_candidates)}x{len(centre_candidates)} "
                        f"= {n_branches} parallel branches",
                        MessageType.GENERAL)

            # -----------------------------------------------------------------
            # Disable OpenCV's internal thread pool to avoid deadlocks
            # -----------------------------------------------------------------
            prev_cv_threads = cv2.getNumThreads()
            cv2.setNumThreads(1)

            futures = []
            with ThreadPoolExecutor(max_workers=n_branches) as executor:
                for gamma_val in gamma_candidates:
                    for (c_x, c_y) in centre_candidates:
                        future = executor.submit(
                            CheckTopBearing._run_branch,
                            bg_normalized, annular_mask, original_annular_copy,
                            gamma_val, c_x, c_y, prompt_r, trace_distance, cfg
                        )
                        futures.append(future)

            # Restore OpenCV thread count
            cv2.setNumThreads(prev_cv_threads)

            # Collect results and find the branch with maximum score
            all_results = []
            for future in futures:
                result = future.result()
                all_results.append(result)

            # Sort by quality score descending; pick the best
            all_results.sort(key=lambda r: r['score'], reverse=True)
            best = all_results[0]

            # Log all branch results
            scoring_mode = cfg['scoring_mode']
            if PRINT_WINNING_BRANCH_SELECTION_DETAILS:
                logBoth('logDebug', _src,
                        f"[Pipeline] Branch results (sorted by score, mode={scoring_mode}):",
                        MessageType.GENERAL)
                for i, r in enumerate(all_results):
                    tag = " <<<< WINNER" if i == 0 else ""
                    val_info = f" [{r.get('validation_reason', '')}]" if not r['valid'] else ""
                    logBoth('logDebug', _src,
                            f"  gamma={r['gamma']}, ctr={r['center']}, "
                            f"scA={r['score_A']:.3f}, scB={r['score_B']:.3f}, lower={r.get('lower_score', 0):.3f}, "
                            f"avg_G={r.get('average_G', 0):.1f}, "
                            f"area={r['area']}, areaSc={r['area_score']:.2f}, valid={r['valid']}{val_info}, "
                            f"anchor={r['anchor_edge']}, thick={r['thickness']:.1f}, "
                            f"inlR_a={r['inlier_ratio_a']:.2f}, inlR_b={r['inlier_ratio_b']:.2f}, "
                            f"arcCov_a={r['arc_cov_a']:.2f}, arcCov_b={r['arc_cov_b']:.2f}, "
                            f"listA={r['list_a_count']}, listB={r['list_b_count']}{tag}",
                            MessageType.GENERAL)

            # Get the result overlay image
            result_overlay = best.get('pipeline_images', {}).get('step9_result', annular_image.copy())

            # =================================================================
            # FINAL VALIDATION: Brightness comparison with gamma=3.0
            # =================================================================
            if best['valid']:
                # Extract geometry from best branch
                fc = best['final_center']
                ri_f = int(round(best['r_inner_final']))
                ro_f = int(round(best['r_outer_final']))
                fcx_f = int(round(fc[0]))
                fcy_f = int(round(fc[1]))

                # logBoth('logDebug', _src, f"[Final Check] Detected annulus: center=({fcx_f},{fcy_f}), "
                #              f"r_inner={ri_f}, r_outer={ro_f}", MessageType.GENERAL)

                # Create annular mask for both images using detected geometry
                h_orig, w_orig = annular_image.shape[:2]
                ring_mask_final = np.zeros((h_orig, w_orig), dtype=np.uint8)
                cv2.circle(ring_mask_final, (fcx_f, fcy_f), ro_f, 255, -1)
                inner_hole_final = np.zeros((h_orig, w_orig), dtype=np.uint8)
                cv2.circle(inner_hole_final, (fcx_f, fcy_f), ri_f, 255, -1)
                ring_mask_final = ring_mask_final - inner_hole_final

                # Apply gamma=3.0 to both images
                final_gamma_lut = CheckTopBearing._create_gamma_lut(CheckTopBearing.FINAL_GAMMA_VALUE)

                # Current image (Top Bearing candidate)
                curr_gamma = final_gamma_lut[annular_image]
                curr_gray = cv2.cvtColor(curr_gamma, cv2.COLOR_RGB2GRAY)
                curr_masked = curr_gray[ring_mask_final > 0]
                curr_mean = float(np.mean(curr_masked)) if len(curr_masked) > 0 else 0.0

                # Reference image (Hub+Bottom Bearing)
                # First extract the same annular region from base image
                base_image_rgb = cv2.cvtColor(base_image, cv2.COLOR_BGR2RGB) if base_image.ndim == 3 else base_image
                base_annular, _ = extract_annular_region(
                    base_image_rgb,
                    center=annular_center,
                    outer_radius=outer_radius,
                    inner_radius=inner_rad,
                    fill_color=0
                )
                base_gamma = final_gamma_lut[base_annular]
                base_gray = cv2.cvtColor(base_gamma, cv2.COLOR_RGB2GRAY)
                base_masked = base_gray[ring_mask_final > 0]
                base_mean = float(np.mean(base_masked)) if len(base_masked) > 0 else 0.0

                # Calculate difference
                brightness_diff = curr_mean - base_mean

                # Final validation check
                final_valid = brightness_diff > CheckTopBearing.FINAL_GAMMA_THRESHOLD

                if final_valid:
                    # logBoth('logInfo', _src,
                    #     f"[Final Check] TOP BEARING DETECTED "
                    #     f"(base_mean={base_mean:.1f}, curr_mean={curr_mean:.1f}, "
                    #     f"diff={brightness_diff:+.1f} > threshold={CheckTopBearing.FINAL_GAMMA_THRESHOLD})",
                    #     MessageType.SUCCESS)

                    # Add final check info to overlay
                    result_bgr = cv2.cvtColor(result_overlay, cv2.COLOR_RGB2BGR)
                    final_text = f"Final: diff={brightness_diff:+.1f} > {CheckTopBearing.FINAL_GAMMA_THRESHOLD}"
                    # cv2.putText(result_bgr, final_text, (10, h_det - 90),
                    #            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    result_overlay = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)

                    # Convert to original image space coordinates
                    # The annular extraction centers at (ANNULAR_CENTER_X, ANNULAR_CENTER_Y)
                    # and the detected center is relative to the cropped image
                    # We need to convert back to original image coordinates

                    # Calculate offset from annular extraction
                    crop_offset_x = annular_center[0] - w_det // 2
                    crop_offset_y = annular_center[1] - h_det // 2

                    original_cx = fcx_f + crop_offset_x
                    original_cy = fcy_f + crop_offset_y

                    # Prepare geometry dictionary
                    geometry_dict = {
                        "center": [original_cx, original_cy],
                        "inner_radius": ri_f,
                        "outer_radius": ro_f
                    }

                    end_time = time.perf_counter()
                    processing_time = end_time - start_time
                    # logBoth('logInfo', _src, f"[Pipeline] Processing completed in {processing_time:.2f}s", MessageType.SUCCESS)

                    # Run inner white radius detection in parallel
                    # CheckTopBearing.find_inner_white_radius_parallel(anImage, tuple(geometry_dict["center"]), ro_f)

                    # Convert result back to BGR for return
                    result_bgr_final = cv2.cvtColor(result_overlay, cv2.COLOR_RGB2BGR)
                    return result_bgr_final, True, geometry_dict

                else:
                    logBoth('logError', _src,
                            f"[Final Check] TOP BEARING NOT DETECTED - Failed brightness check "
                            f"(base_mean={base_mean:.1f}, curr_mean={curr_mean:.1f}, "
                            f"diff={brightness_diff:+.1f} <= threshold={CheckTopBearing.FINAL_GAMMA_THRESHOLD})",
                            MessageType.ISSUE)

                    # Add failure info to overlay
                    result_bgr = cv2.cvtColor(result_overlay, cv2.COLOR_RGB2BGR)
                    fail_text = f"Final: diff={brightness_diff:+.1f} <= {CheckTopBearing.FINAL_GAMMA_THRESHOLD}"
                    # cv2.putText(result_bgr, fail_text, (10, h_det - 90),
                    #            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                    # cv2.putText(result_bgr, "FAILED BRIGHTNESS CHECK", (w_det - 300, 50),
                    #            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    result_overlay = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)

                    end_time = time.perf_counter()
                    processing_time = end_time - start_time
                    logBoth('logError', _src,
                            f"[Pipeline] Processing completed in {processing_time:.2f}s - FAILED",
                            MessageType.ISSUE)

                    # Convert result back to BGR for return
                    result_bgr_final = cv2.cvtColor(result_overlay, cv2.COLOR_RGB2BGR)
                    return result_bgr_final, False, None

            else:
                # No valid annulus detected
                validation_reason = best.get('validation_reason', 'Unknown reason')
                avg_g_val = best.get('average_G', 0.0)
                lower_sc = best.get('lower_score', 0.0)
                logBoth('logError', _src,
                        f"[Pipeline] NO VALID ANNULUS DETECTED "
                        f"(best score={best['score']:.3f}, gamma={best['gamma']}, "
                        f"ctr={best['center']}, reason={validation_reason}, "
                        f"avg_G={avg_g_val:.1f}, lower_score={lower_sc:.3f})",
                        MessageType.ISSUE)

                end_time = time.perf_counter()
                processing_time = end_time - start_time
                logBoth('logError', _src,
                        f"[Pipeline] Processing completed in {processing_time:.2f}s - NO VALID ANNULUS",
                        MessageType.ISSUE)

                # Convert result back to BGR for return
                result_bgr_final = cv2.cvtColor(result_overlay, cv2.COLOR_RGB2BGR)
                return result_bgr_final, False, None

        except Exception as e:
            logBoth('logCritical', _src, f"CheckTopBearing: Exception during detection: {e}", MessageType.PROBLEM)
            import traceback
            traceback.print_exc()
            return anImage, False, None


    # =============================================================================
    # For backward compatibility - keep the old simple method as a fallback
    # =============================================================================

    @staticmethod
    def checkTopBearing_simple(anImage: np.ndarray,
                               currentPictures: Dict[str, np.ndarray | None] = None,
                               componentQRCode: str = DOST,
                               gamma: float = 2.0) -> Tuple[np.ndarray | None, bool]:
        """
        Simple wrapper for backward compatibility (original method signature).

        Returns:
            Tuple of (annotated_image, is_bearing_present)
        """
        result_img, is_present, _ = CheckTopBearing.checkTopBearing(
            anImage, currentPictures, componentQRCode, gamma
        )
        return result_img, is_present

@staticmethod
def test(directory_path: str) -> None:
    """
    Test CheckTopBearing on images in a directory.

    Finds all images with 'top' in filename and tests each against 15 random
    images with 'hub' in filename as references.

    Args:
        directory_path: Path to directory containing test images
    """
    import os
    import random
    from pathlib import Path

    _src = __name__

    # Common image extensions
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}

    # Find all image files
    all_files = []
    for file in os.listdir(directory_path):
        filepath = os.path.join(directory_path, file)
        if os.path.isfile(filepath):
            ext = Path(file).suffix.lower()
            if ext in image_extensions:
                all_files.append(filepath)

    # Filter for top and hub images
    top_list = [f for f in all_files if 'top' in os.path.basename(f).lower()]
    # top_list = [f for f in all_files if 'nut' in os.path.basename(f).lower()]
    # top_list = [f for f in all_files if 'trials - nut' in os.path.basename(f).lower()]
    hub_candidates = [f for f in all_files if 'hub' in os.path.basename(f).lower()]

    # Randomly select N hub images
    random_sample_size = 10
    if len(hub_candidates) < random_sample_size:
        logBoth('logWarning', _src, f"Warning: Only {len(hub_candidates)} hub images found, using all", MessageType.RISK)
        hub_list = hub_candidates
    else:
        hub_list = random.sample(hub_candidates, random_sample_size)

    logBoth('logDebug', _src, f"Test Configuration:", MessageType.GENERAL)
    logBoth('logDebug', _src, f"  Directory: {directory_path}", MessageType.GENERAL)
    logBoth('logDebug', _src, f"  Top images found: {len(top_list)}", MessageType.GENERAL)
    logBoth('logDebug', _src, f"  Hub images selected: {len(hub_list)}", MessageType.GENERAL)
    logBoth('logDebug', _src, "=" * 70, MessageType.GENERAL)

    # Test each top image against all hub images
    for top_idx, top_file in enumerate(top_list, 1):
        top_name = os.path.basename(top_file)
        logBoth('logDebug', _src, f"\n[{top_idx}/{len(top_list)}] Testing: {top_name}", MessageType.GENERAL)

        # Load top image
        top_image = cv2.imread(top_file)
        if top_image is None:
            logBoth('logError', _src, f"  ERROR: Could not load {top_name}", MessageType.ISSUE)
            continue

        # Test against all hub images
        failures = []
        savedOnce = False
        for hub_idx, hub_file in enumerate(hub_list, 1):
            hub_name = os.path.basename(hub_file)

            # Load hub image
            hub_image = cv2.imread(hub_file)
            if hub_image is None:
                failures.append((hub_name, "Could not load hub image"))
                continue

            # Prepare currentPictures dictionary
            currentPictures = {
                hubAndBottomBearingPictureKeyString: hub_image
            }

            if "DOSTPLUS" in directory_path:
                qr_code = "8201206$400112VA1C$11770$09.03.2025$C5211701$MEK$40Cr4-B$1$SPDL ASSY-KNULH$SNPL-MAT$"
            else:
                qr_code = "7204838$400112VA1D$11770$09.03.2025$C5211701$MEK$40cR4-B$1$SPDL ASSY-KNULH$SNPL-MAT$"

            # Run detection
            try:
                annotated_img, is_present, geometry = CheckTopBearing.checkTopBearing(
                    top_image,
                    currentPictures,
                    componentQRCode=qr_code
                )

                if not savedOnce:
                    # Save annotated image
                    save_dir = r"C:\Test\TopBearing"
                    # save_dir = r"C:\Test\NutAndPlatewasher"
                    os.makedirs(save_dir, exist_ok=True)

                    # Create filename with hub image identifier
                    save_filename = f"{Path(top_name).stem}_with_{Path(hub_name).stem}.jpg"
                    save_path = os.path.join(save_dir, save_filename)
                    cv2.imwrite(save_path, annotated_img)
                    savedOnce = True

                # Check result - expect True for top bearing images
                if not is_present:
                    failures.append((hub_name, "Detection returned False (no bearing detected)"))

            except Exception as e:
                failures.append((hub_name, f"Exception: {str(e)}"))

        # Report results for this top image
        if len(failures) == 0:
            logBoth('logInfo', _src, f"  ✓ OK - All {len(hub_list)} tests passed", MessageType.SUCCESS)
        else:
            logBoth('logError', _src, f"  ✗ NOT OK - {len(failures)}/{len(hub_list)} failed", MessageType.ISSUE)
            for hub_name, reason in failures:
                logBoth('logError', _src, f"    - {hub_name}: {reason}", MessageType.ISSUE)

    logBoth('logDebug', _src, "=" * 70, MessageType.GENERAL)
    logBoth('logDebug', _src, "Test complete", MessageType.GENERAL)

if __name__ == "__main__":
    # print("CheckTopBearing v2.0 - Complete Implementation")
    # print("Integrated TopBearingSegmentation pipeline")
    # print("Ready for deployment")
    test("C:/AutoCompanyImages/DOST/LHS")
