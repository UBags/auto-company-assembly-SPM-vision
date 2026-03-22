# Copyright (c) 2025 Uddipan Bagchi. All rights reserved.
# See LICENSE in the project root for license information.package com.costheta.cortexa.action

"""
CheckNutAndPlateWasher - Detects presence of Nut and Washer using HexagonNutDetector and color analysis.

New Detection Method (Washer Detection):
    1. Use HexagonNutDetector to detect nut and get nut mask
    2. If check.washers.presence.in.nutandplatewasher=False, return nut detection result
    3. If check.washers.presence.in.nutandplatewasher=True:
       - Extract annular regions from both nut and top bearing images
       - Create bearing mask in annular space
       - Exclude nut-occluded region from bearing mask
       - Calculate gamma-corrected R and R-B differences on non-overlapping region
       - Apply thresholds: diff_R > WASHER_THRESHOLD_R AND diff_RB > WASHER_THRESHOLD_RB

Returns:
    - Annotated image with nut in green, non-overlapping bearing in blue
    - True if washer present, False otherwise
"""

import cv2
import numpy as np
from typing import Dict, Tuple, Optional, Any
import sys
import os

# Add project root to path for imports
try:
    from BaseUtils import get_project_root
    _PROJECT_ROOT = get_project_root()
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)
except:
    pass

from camera.HexagonNutDetector import NutDetector

# Try to import production modules, fall back to mocks for standalone testing
try:
    from utils.RedisUtils import *
    from BaseUtils import *
    from Configuration import *
    from utils.QRCodeHelper import getModel_LHSRHS_AndTonnage, UNKNOWN
    from logutils.SlaveLoggers import logBoth
    from logutils.Logger import MessageType

    CosThetaConfigurator.getInstance()
except ImportError:
    # Standalone testing mode - define mocks
    DOST = "DOST"
    DOSTPLUS = "DOSTPLUS"
    hubAndBottomBearingPictureKeyString = "hubAndBottomBearingPicture"
    topBearingPictureKeyString = "topBearingPicture"

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

    def getModel_LHSRHS_AndTonnage(qrCode):
        return "DOST", "LHS", "Unknown"

    UNKNOWN = "Unknown"

    # Mock CosThetaConfigurator for standalone testing
    class CosThetaConfigurator:
        @classmethod
        def getInstance(cls):
            return cls

        @classmethod
        def getCheckWashersPresenceInNutAndPlateWasher(cls) -> bool:
            return True  # Default for standalone testing


class CheckNutAndPlateWasher:
    """
    Checks for the presence of Nut and Washer using HexagonNutDetector and color analysis.
    """

    # Washer detection parameters (configurable)
    WASHER_THRESHOLD_R = 0.55     # 1% FPR - R channel threshold
    WASHER_THRESHOLD_RB = 5.57    # 1% FPR - R-B difference threshold
    WASHER_GAMMA = 3.0            # Gamma correction value

    # Nut detection parameters
    NUT_DETECTION_CENTER = (632, 360)
    NUT_DETECTION_RADIUS = 80

    # Singleton nut detector
    _nut_detector: Optional[NutDetector] = None
    _detector_initialized = False

    @classmethod
    def _get_nut_detector(cls) -> NutDetector:
        """Get or create singleton NutDetector instance."""
        _src = getFullyQualifiedName(__file__, cls)
        if not cls._detector_initialized or cls._nut_detector is None:
            logBoth('logDebug', _src, "[CheckNutAndPlateWasher] Initializing NutDetector...", MessageType.GENERAL)
            cls._nut_detector = NutDetector()
            cls._detector_initialized = True
            logBoth('logInfo', _src, "[CheckNutAndPlateWasher] NutDetector initialized", MessageType.SUCCESS)
        return cls._nut_detector

    @classmethod
    def _create_gamma_lut(cls, gamma: float) -> np.ndarray:
        """Create gamma correction lookup table."""
        inv_gamma = 1.0 / gamma
        return np.array([((i / 255.0) ** inv_gamma) * 255 for i in range(256)]).astype(np.uint8)

    @classmethod
    def _extract_annular_region(cls, image: np.ndarray, center: Tuple[int, int],
                               outer_radius: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract annular region from image.

        Returns:
            Tuple of (annular_image, annular_mask)
        """
        h, w = image.shape[:2]
        cx, cy = center

        # Create output image of size 2*outer_radius x 2*outer_radius
        size = 2 * outer_radius
        annular_image = np.zeros((size, size, 3), dtype=image.dtype)
        annular_mask = np.zeros((size, size), dtype=np.uint8)

        # Calculate crop region in original image
        x1 = max(0, cx - outer_radius)
        y1 = max(0, cy - outer_radius)
        x2 = min(w, cx + outer_radius)
        y2 = min(h, cy + outer_radius)

        # Calculate paste region in annular image
        paste_x1 = outer_radius - (cx - x1)
        paste_y1 = outer_radius - (cy - y1)
        paste_x2 = paste_x1 + (x2 - x1)
        paste_y2 = paste_y1 + (y2 - y1)

        # Copy image region
        annular_image[paste_y1:paste_y2, paste_x1:paste_x2] = image[y1:y2, x1:x2]

        # Create circular mask
        center_annular = (outer_radius, outer_radius)
        cv2.circle(annular_mask, center_annular, outer_radius, 255, -1)

        return annular_image, annular_mask

    @classmethod
    def _create_bearing_mask_in_annular_space(cls, bearing_geometry: Dict[str, Any],
                                              nut_annular_center: Tuple[int, int],
                                              nut_annular_radius: int,
                                              annular_image_shape: Tuple[int, int]) -> np.ndarray:
        """
        Create bearing annular mask in the nut's annular coordinate space.

        Args:
            bearing_geometry: Dict with 'center', 'inner_radius', 'outer_radius'
            nut_annular_center: Center used for nut extraction (e.g., (632, 360))
            nut_annular_radius: Radius used for nut extraction (e.g., 80)
            annular_image_shape: Shape of annular image (h, w)

        Returns:
            Binary mask of bearing annulus in nut's annular space
        """
        _src = getFullyQualifiedName(__file__, cls)

        bearing_cx_orig, bearing_cy_orig = bearing_geometry["center"]
        bearing_inner_r = bearing_geometry["inner_radius"]
        bearing_outer_r = bearing_geometry["outer_radius"]

        # Calculate crop offset (how nut annular image relates to original)
        crop_offset_x = nut_annular_center[0] - nut_annular_radius
        crop_offset_y = nut_annular_center[1] - nut_annular_radius

        # Translate bearing center to nut's annular space
        bearing_cx_annular = bearing_cx_orig - crop_offset_x
        bearing_cy_annular = bearing_cy_orig - crop_offset_y

        logBoth('logDebug', _src, f"[Bearing Mask] Original center: ({bearing_cx_orig}, {bearing_cy_orig})", MessageType.GENERAL)
        logBoth('logDebug', _src, f"[Bearing Mask] Annular center: ({bearing_cx_annular}, {bearing_cy_annular})", MessageType.GENERAL)
        logBoth('logDebug', _src, f"[Bearing Mask] Radii: inner={bearing_inner_r}, outer={bearing_outer_r}", MessageType.GENERAL)

        # Create bearing annular mask
        h, w = annular_image_shape
        bearing_mask = np.zeros((h, w), dtype=np.uint8)

        # Draw outer circle
        cv2.circle(bearing_mask,
                  (int(bearing_cx_annular), int(bearing_cy_annular)),
                  int(bearing_outer_r),
                  255, -1)

        # Remove inner circle
        cv2.circle(bearing_mask,
                  (int(bearing_cx_annular), int(bearing_cy_annular)),
                  int(bearing_inner_r),
                  0, -1)

        return bearing_mask

    @classmethod
    def _create_non_overlapping_mask(cls, bearing_mask: np.ndarray,
                                     nut_mask: np.ndarray) -> Tuple[np.ndarray, int, int, int]:
        """
        Create bearing mask with nut region excluded.

        Returns:
            Tuple of (non_overlap_mask, original_area, nut_area, final_area)
        """
        _src = getFullyQualifiedName(__file__, cls)

        original_area = np.sum(bearing_mask == 255)
        nut_area = np.sum(nut_mask == 255)

        # Exclude nut from bearing
        non_overlap_mask = bearing_mask.copy()
        non_overlap_mask[nut_mask == 255] = 0

        final_area = np.sum(non_overlap_mask == 255)
        overlap_removed = original_area - final_area

        logBoth('logDebug', _src,
                f"[Mask Creation] Bearing: {original_area}px, Nut: {nut_area}px, "
                f"Overlap: {overlap_removed}px, Final: {final_area}px",
                MessageType.GENERAL)

        return non_overlap_mask, original_area, nut_area, final_area

    @classmethod
    def _calculate_color_differences(cls, bearing_annular_rgb: np.ndarray,
                                     nut_annular_rgb: np.ndarray,
                                     non_overlap_mask: np.ndarray,
                                     gamma: float) -> Tuple[float, float]:
        """
        Calculate gamma-corrected R and R-B differences.

        Returns:
            Tuple of (diff_R, diff_RB)
        """
        _src = getFullyQualifiedName(__file__, cls)

        gamma_lut = cls._create_gamma_lut(gamma)

        # Extract and gamma-correct channels
        bearing_red = gamma_lut[bearing_annular_rgb[:, :, 0]]
        bearing_blue = gamma_lut[bearing_annular_rgb[:, :, 2]]
        nut_red = gamma_lut[nut_annular_rgb[:, :, 0]]
        nut_blue = gamma_lut[nut_annular_rgb[:, :, 2]]

        # Calculate R-B
        bearing_rb = bearing_red.astype(np.float32) - bearing_blue.astype(np.float32)
        nut_rb = nut_red.astype(np.float32) - nut_blue.astype(np.float32)

        # Get masked pixels only
        mask_bool = non_overlap_mask == 255

        if np.sum(mask_bool) == 0:
            logBoth('logError', _src, "[Color Calc] ERROR: Empty mask!", MessageType.ISSUE)
            return 0.0, 0.0

        # Calculate averages
        bearing_r_avg = float(np.mean(bearing_red[mask_bool]))
        nut_r_avg = float(np.mean(nut_red[mask_bool]))
        bearing_rb_avg = float(np.mean(bearing_rb[mask_bool]))
        nut_rb_avg = float(np.mean(nut_rb[mask_bool]))

        diff_R = bearing_r_avg - nut_r_avg
        diff_RB = bearing_rb_avg - nut_rb_avg

        logBoth('logDebug', _src, f"[Color Results] diff_R={diff_R:.2f}, diff_RB={diff_RB:.2f}", MessageType.GENERAL)

        return diff_R, diff_RB

    @classmethod
    def _create_annotated_image(cls, original_image: np.ndarray,
                                nut_mask_full: np.ndarray,
                                bearing_mask_annular: Optional[np.ndarray],
                                nut_annular_center: Tuple[int, int],
                                nut_annular_radius: int,
                                washer_present: bool,
                                hex_center_original: Tuple[int, int],
                                bearing_geometry: Optional[Dict[str, Any]] = None) -> np.ndarray:
        """
        Create annotated image with nut in green and non-overlapping bearing in blue.

        Args:
            original_image: Original BGR image
            nut_mask_full: Nut mask in original image space
            bearing_mask_annular: Non-overlapping bearing mask in annular space (can be None)
            nut_annular_center: Center used for nut extraction
            nut_annular_radius: Radius used for nut extraction
            washer_present: Detection result
            hex_center_original: Nut centre in original image space for 240x240 crop output.
        """
        annotated = original_image.copy()

        # Draw bearing annulus in blue, centred on bearing centre relocated by the
        # same delta that separates hex_center_original from nut_annular_center
        # printBoldBlue(f"{hex_center_original = }")
        # printBoldBlue(f"{nut_annular_center = }")
        # printBoldBlue(f"{bearing_geometry = }")
        if bearing_geometry is not None:
            # delta_x = hex_center_original[0] - nut_annular_center[0]
            # delta_y = hex_center_original[1] - nut_annular_center[1]
            # print(f"{delta_x = }; {delta_y = }")
            # bearing_cx = int(round(bearing_geometry["center"][0] + delta_x))
            # bearing_cy = int(round(bearing_geometry["center"][1] + delta_y))
            # print(f"{bearing_cx = }; {bearing_cy = }")
            bearing_cx = int(round(bearing_geometry["center"][0]))
            bearing_cy = int(round(bearing_geometry["center"][1]))
            inner_r = int(bearing_geometry["inner_radius"])
            outer_r = int(bearing_geometry["outer_radius"])
            # print(f"{inner_r = }; {outer_r = }")

            # Fill annulus with light blue (BGR: 255, 191, 0 is amber — light blue is 255, 200, 150... use (200, 150, 50) in BGR)
            annulus_mask = np.zeros(original_image.shape[:2], dtype=np.uint8)
            cv2.circle(annulus_mask, (bearing_cx, bearing_cy), outer_r, 255, -1)
            cv2.circle(annulus_mask, (bearing_cx, bearing_cy), inner_r, 0, -1)
            light_blue_bgr = (200, 150, 50)  # light blue in BGR
            annotated[annulus_mask == 255] = (
                annotated[annulus_mask == 255] * 0.6 +
                np.array(light_blue_bgr) * 0.4
            ).astype(np.uint8)

            # Draw inner and outer circle outlines in solid blue
            cv2.circle(annotated, (bearing_cx, bearing_cy), inner_r, (255, 100, 0), 2)
            cv2.circle(annotated, (bearing_cx, bearing_cy), outer_r, (255, 100, 0), 2)

        # Draw nut in green
        if np.sum(nut_mask_full) > 0:
            contours, _ = cv2.findContours(nut_mask_full, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(annotated, contours, -1, (0, 255, 0), 2)  # Green

        # Add text result
        # result_text = "WASHER PRESENT" if washer_present else "WASHER MISSING"
        # color = (0, 255, 0) if washer_present else (0, 0, 255)
        # cv2.putText(annotated, result_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

        # Crop 240x240 centred on the nut centre
        # cx, cy = hex_center_original
        cx, cy = bearing_geometry["center"]
        half = 120
        h, w = annotated.shape[:2]
        x1 = max(cx - half, 0)
        y1 = max(cy - half, 0)
        x2 = min(cx + half, w)
        y2 = min(cy + half, h)
        cropped = annotated[y1:y2, x1:x2]
        # Pad to exactly 240x240 if near edge
        result = np.zeros((240, 240, 3), dtype=np.uint8)
        ch, cw = cropped.shape[:2]
        result[:ch, :cw] = cropped
        return result

    @staticmethod
    def checkNutAndPlateWasher(
            anImage: np.ndarray,
            currentPictures: Dict[str, np.ndarray | None] = None,
            componentQRCode: str | None = DOST,
            gamma: float = 2.0,
            bearing_geometry: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray | None, bool]:
        """
        Detect nut and washer using HexagonNutDetector and color analysis.

        Args:
            anImage: Current camera image (nut image, BGR format)
            currentPictures: Dict containing 'topBearingPicture'
            componentQRCode: Component QR code
            gamma: Unused (kept for compatibility)
            bearing_geometry: Dict with 'center', 'inner_radius', 'outer_radius' from CheckTopBearing.
                              Required when washer check is enabled.

        Returns:
            Tuple of (annotated_image, washer_present)
        """
        _src = getFullyQualifiedName(__file__, CheckNutAndPlateWasher)

        logBoth('logDebug', _src, "="*80, MessageType.GENERAL)
        logBoth('logDebug', _src, "[CheckNutAndPlateWasher] DETECTION START", MessageType.GENERAL)
        logBoth('logDebug', _src, "="*80, MessageType.GENERAL)

        # =====================================================================
        # VALIDATION
        # =====================================================================
        if anImage is None:
            logBoth('logError', _src, "[CheckNutAndPlateWasher] anImage is None", MessageType.ISSUE)
            return anImage, False

        if currentPictures is None:
            logBoth('logError', _src, "[CheckNutAndPlateWasher] currentPictures is None", MessageType.ISSUE)
            return anImage, False

        if componentQRCode is None:
            logBoth('logError', _src, "[CheckNutAndPlateWasher] componentQRCode is None", MessageType.ISSUE)
            return anImage, False

        # Get component type
        try:
            modelName, lhs_rhs, _ = getModel_LHSRHS_AndTonnage(componentQRCode)
            if modelName == UNKNOWN:
                modelName = "DOST"
        except:
            modelName = "DOST"
            lhs_rhs = "LHS"

        # =====================================================================
        # STEP 1: DETECT NUT
        # =====================================================================
        logBoth('logDebug', _src, "[Step 1] Detecting nut using HexagonNutDetector...", MessageType.GENERAL)

        detector = CheckNutAndPlateWasher._get_nut_detector()
        image_rgb = cv2.cvtColor(anImage, cv2.COLOR_BGR2RGB)

        nut_found, nut_result = detector.detect_nut_in_image(
            image_rgb=image_rgb,
            center=CheckNutAndPlateWasher.NUT_DETECTION_CENTER,
            outer_radius=CheckNutAndPlateWasher.NUT_DETECTION_RADIUS,
            inner_radius=0,
            image_id="nut_check"
        )

        if not nut_found:
            logBoth('logError', _src, "[Step 1] Nut NOT detected", MessageType.ISSUE)
            # Return annotated image from detector (or original)
            _cx, _cy = CheckNutAndPlateWasher.NUT_DETECTION_CENTER
            _img = nut_result.get('annotated_original', anImage)
            _h, _w = _img.shape[:2]
            _x1, _y1 = max(_cx - 120, 0), max(_cy - 120, 0)
            _x2, _y2 = min(_cx + 120, _w), min(_cy + 120, _h)
            _cropped = _img[_y1:_y2, _x1:_x2]
            annotated = np.zeros((240, 240, 3), dtype=np.uint8)
            annotated[:_cropped.shape[0], :_cropped.shape[1]] = _cropped
            return annotated, False

        logBoth('logInfo', _src, "[Step 1] Nut DETECTED", MessageType.SUCCESS)

        # Compute hex_center in original image space (used for 240x240 crop in all paths)
        _hcx, _hcy = nut_result.get('hex_center', (CheckNutAndPlateWasher.NUT_DETECTION_RADIUS,
                                                    CheckNutAndPlateWasher.NUT_DETECTION_RADIUS))
        _offset_x = CheckNutAndPlateWasher.NUT_DETECTION_CENTER[0] - CheckNutAndPlateWasher.NUT_DETECTION_RADIUS
        _offset_y = CheckNutAndPlateWasher.NUT_DETECTION_CENTER[1] - CheckNutAndPlateWasher.NUT_DETECTION_RADIUS
        hex_center_original = (_hcx + _offset_x, _hcy + _offset_y)

        def _crop240(img: np.ndarray) -> np.ndarray:
            cx, cy = hex_center_original
            h, w = img.shape[:2]
            x1, y1 = max(cx - 120, 0), max(cy - 120, 0)
            x2, y2 = min(cx + 120, w), min(cy + 120, h)
            cropped = img[y1:y2, x1:x2]
            result = np.zeros((240, 240, 3), dtype=np.uint8)
            ch, cw = cropped.shape[:2]
            result[:ch, :cw] = cropped
            return result

        # =====================================================================
        # CHECK CONFIGURATION: Should we check washer presence?
        # =====================================================================
        check_washer = CosThetaConfigurator.getInstance().getCheckWashersPresenceInNutAndPlateWasher()

        if not check_washer:
            logBoth('logDebug', _src, "[Config] Washer check DISABLED - returning nut detection result", MessageType.GENERAL)
            logBoth('logInfo', _src, "[Result] Nut found - RETURNING TRUE (washer check skipped)", MessageType.SUCCESS)
            # Return nut detection result with green outline
            annotated = _crop240(nut_result.get('annotated_original', anImage))
            return annotated, True  # Nut found = True

        logBoth('logDebug', _src, "[Config] Washer check ENABLED - proceeding with washer detection", MessageType.GENERAL)

        # =====================================================================
        # STEP 2: GET PREREQUISITES FOR WASHER CHECK
        # =====================================================================

        # Get top bearing reference image
        top_bearing_image = currentPictures.get(topBearingPictureKeyString, None)
        if top_bearing_image is None:
            logBoth('logError', _src, "[CheckNutAndPlateWasher] Top Bearing image missing - cannot check washer", MessageType.ISSUE)
            annotated = _crop240(nut_result.get('annotated_original', anImage))
            return annotated, False

        # Get bearing geometry from parameter
        if bearing_geometry is None:
            logBoth('logError', _src, "[CheckNutAndPlateWasher] Bearing geometry not available - cannot check washer", MessageType.ISSUE)
            annotated = _crop240(nut_result.get('annotated_original', anImage))
            return annotated, False

        logBoth('logDebug', _src, f"[CheckNutAndPlateWasher] Bearing geometry: {bearing_geometry}", MessageType.GENERAL)

        nut_mask = nut_result['mask']  # Annular space
        nut_annular_rgb = nut_result['annular_rgb']  # RGB format

        # =====================================================================
        # STEP 3: EXTRACT BEARING ANNULAR REGION
        # =====================================================================
        logBoth('logDebug', _src, "[Step 3] Extracting bearing annular region...", MessageType.GENERAL)

        bearing_center = tuple(bearing_geometry["center"])
        bearing_annular_bgr, _ = CheckNutAndPlateWasher._extract_annular_region(
            top_bearing_image,
            center=bearing_center,
            outer_radius=CheckNutAndPlateWasher.NUT_DETECTION_RADIUS
        )
        bearing_annular_rgb = cv2.cvtColor(bearing_annular_bgr, cv2.COLOR_BGR2RGB)

        logBoth('logInfo', _src, f"[Step 3] Extracted bearing annular region centered at {bearing_center}", MessageType.SUCCESS)

        # =====================================================================
        # STEP 4: CREATE MASKS
        # =====================================================================
        logBoth('logDebug', _src, "[Step 4] Creating bearing mask in annular space...", MessageType.GENERAL)

        bearing_mask = CheckNutAndPlateWasher._create_bearing_mask_in_annular_space(
            bearing_geometry,
            CheckNutAndPlateWasher.NUT_DETECTION_CENTER,
            CheckNutAndPlateWasher.NUT_DETECTION_RADIUS,
            nut_annular_rgb.shape[:2]
        )

        non_overlap_mask, orig_area, nut_area, final_area = CheckNutAndPlateWasher._create_non_overlapping_mask(
            bearing_mask, nut_mask
        )

        if final_area < 500:
            logBoth('logWarning', _src, f"[Step 4] WARNING: Very small bearing area ({final_area}px)", MessageType.RISK)

        # =====================================================================
        # STEP 5: CALCULATE COLOR DIFFERENCES
        # =====================================================================
        logBoth('logDebug', _src, f"[Step 5] Calculating color differences (gamma={CheckNutAndPlateWasher.WASHER_GAMMA})...", MessageType.GENERAL)

        diff_R, diff_RB = CheckNutAndPlateWasher._calculate_color_differences(
            bearing_annular_rgb,
            nut_annular_rgb,
            non_overlap_mask,
            CheckNutAndPlateWasher.WASHER_GAMMA
        )

        # =====================================================================
        # STEP 6: APPLY THRESHOLDS
        # =====================================================================
        logBoth('logDebug', _src, "="*80, MessageType.GENERAL)
        logBoth('logDebug', _src, "[Step 6] DECISION", MessageType.GENERAL)
        logBoth('logDebug', _src, "="*80, MessageType.GENERAL)
        logBoth('logDebug', _src,
                f"Thresholds: diff_R > {CheckNutAndPlateWasher.WASHER_THRESHOLD_R:.2f} AND "
                f"diff_RB > {CheckNutAndPlateWasher.WASHER_THRESHOLD_RB:.2f}",
                MessageType.GENERAL)
        logBoth('logDebug', _src,
                f"Measured:   diff_R = {diff_R:.2f} AND diff_RB = {diff_RB:.2f}",
                MessageType.GENERAL)

        washer_present = (diff_R > CheckNutAndPlateWasher.WASHER_THRESHOLD_R) and (diff_RB > CheckNutAndPlateWasher.WASHER_THRESHOLD_RB)

        if washer_present:
            logBoth('logInfo', _src, "✓ WASHER PRESENT - Top Bearing Detected", MessageType.SUCCESS)
        else:
            logBoth('logError', _src, "✗ WASHER MISSING - Nut Only", MessageType.ISSUE)
            if diff_R <= CheckNutAndPlateWasher.WASHER_THRESHOLD_R:
                logBoth('logError', _src, f"  Reason: R channel failed ({diff_R:.2f} <= {CheckNutAndPlateWasher.WASHER_THRESHOLD_R:.2f})", MessageType.ISSUE)
            if diff_RB <= CheckNutAndPlateWasher.WASHER_THRESHOLD_RB:
                logBoth('logError', _src, f"  Reason: R-B failed ({diff_RB:.2f} <= {CheckNutAndPlateWasher.WASHER_THRESHOLD_RB:.2f})", MessageType.ISSUE)

        logBoth('logDebug', _src, "="*80, MessageType.GENERAL)

        # =====================================================================
        # STEP 7: CREATE ANNOTATED IMAGE
        # =====================================================================
        # Create full-size nut mask
        crop_offset_x = CheckNutAndPlateWasher.NUT_DETECTION_CENTER[0] - CheckNutAndPlateWasher.NUT_DETECTION_RADIUS
        crop_offset_y = CheckNutAndPlateWasher.NUT_DETECTION_CENTER[1] - CheckNutAndPlateWasher.NUT_DETECTION_RADIUS

        nut_mask_full = np.zeros((anImage.shape[0], anImage.shape[1]), dtype=np.uint8)
        nut_mask_full[crop_offset_y:crop_offset_y + nut_mask.shape[0],
                     crop_offset_x:crop_offset_x + nut_mask.shape[1]] = nut_mask

        annotated = CheckNutAndPlateWasher._create_annotated_image(
            anImage,
            nut_mask_full,
            non_overlap_mask,
            CheckNutAndPlateWasher.NUT_DETECTION_CENTER,
            CheckNutAndPlateWasher.NUT_DETECTION_RADIUS,
            washer_present,
            hex_center_original,
            bearing_geometry=bearing_geometry
        )

        return annotated, washer_present
