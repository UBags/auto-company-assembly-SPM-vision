# Copyright (c) 2025 Uddipan Bagchi. All rights reserved.
# See LICENSE in the project root for license information.package com.costheta.cortexa.action

"""
CheckBunk.py v2.0 - UPDATED FOR V0.7 PIPELINE
Implements Bunk hole verification using MobileSAMv2 with v0.7 preprocessing.

CHANGES FROM V1:
1. Uses BunkSegmenter with two-stage cropping (outer R=250, inner R=110)
2. Fixed gamma sequence: [7.75, 6.5, 4.0, 2.0, 1.0] instead of brightness-based selection
3. Batch processing with early termination on definitive patterns
4. No morphological processing (direct SAM mask filtering)
5. Enhanced early termination: stops on definitive mismatch (e.g., 4-hole when expected 2)

PIPELINE:
1. Parse QR code → determine expected count (DOST=4, DOSTPLUS=2)
2. Preprocess ALL 4 gammas (7.75, 6.5, 4.0, 2.0, 1.0)
3. Batch process in single torch context with early termination
4. Apply cascade geometric validation on each gamma
5. Return image with masks painted + success status
"""

import numpy as np
import cv2
from typing import Dict, Tuple, Optional, Any
import os

from BaseUtils import *
from logutils.SlaveLoggers import logBoth
from logutils.Logger import MessageType
from utils.QRCodeHelper import getModel_LHSRHS_AndTonnage
from concurrent.futures import ThreadPoolExecutor

# Import the v2 Bunk segmentation engine
try:
    from camera.BunkSegmenter import (
        BunkSegmenter,
        paint_bunk_masks_on_image,
        GAMMA_SEQUENCE
    )

    SAM_AVAILABLE = True
except ImportError as e:
    logBoth('logWarning', __name__, f"Warning: BunkSegmenter not available: {e}", MessageType.RISK)
    SAM_AVAILABLE = False
    BunkSegmenter = None

# =============================================================================
# PRINT CONTROL FLAGS
# =============================================================================
PRINT_QR_PARSING = False
PRINT_IMAGE_PREPROCESSING = False
PRINT_BATCH_SEGMENTATION = False
PRINT_RESULT_PAINTING = False
PRINT_SUCCESS_EVALUATION = True


class CheckBunk:
    """
    Checks bunk assembly by detecting holes in the bunk region.

    Uses MobileSAMv2 with V0.7 pipeline:
    - Two-stage circular cropping (outer R=250, inner R=110)
    - Fixed gamma sequence [7.75, 6.5, 4.0, 2.0, 1.0]
    - Batch processing with early termination
    - Cascade geometric validation
    """

    # Class-level segmenter (singleton pattern)
    # _segmenter: Optional[BunkSegmenter] = None
    # _segmenter_initialized = False

    # @classmethod
    # def _get_segmenter(cls) -> Optional[BunkSegmenter]:
    #     """Get or initialize the segmenter (singleton pattern)."""
    #     if not SAM_AVAILABLE:
    #         return None
    #
    #     if not cls._segmenter_initialized:
    #         # cls._segmenter = BunkSegmenter(None, None)
    #         cls._segmenter = BunkSegmenter.get_instance()
    #         cls._segmenter_initialized = True
    #
    #     return cls._segmenter

    @staticmethod
    def _crop300(img: np.ndarray, center: Tuple[int, int]) -> np.ndarray:
        """
        Crop a 300x300 region centred on `center` from `img`.
        Pads with zeros if the crop extends beyond image boundaries.
        """
        cx, cy = center
        half = 150
        h, w = img.shape[:2]
        x1 = max(cx - half, 0)
        y1 = max(cy - half, 0)
        x2 = min(cx + half, w)
        y2 = min(cy + half, h)
        cropped = img[y1:y2, x1:x2]
        result = np.zeros((300, 300, 3), dtype=np.uint8)
        ch, cw = cropped.shape[:2]
        result[:ch, :cw] = cropped
        return result

    @staticmethod
    def checkBunk(
            anImage: np.ndarray,
            componentQRCode: str | None = None,
            bearing_geometry: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray | None, bool, None | float]:
        """
        Check bunk by detecting holes using MobileSAMv2 with LAZY EVALUATION.

        NEW Processing Pipeline (OPTIMIZED):
        1. Determine expected count from QR code (DOST=4, DOSTPLUS=2)
        2. Get optimized gamma sequence (gamma 2.0 first for both)
        3. LAZY EVALUATION: Process ONE gamma at a time
        4. PARALLEL PREPROCESSING: Preprocess gamma N+1 while GPU processes gamma N
        5. EARLY TERMINATION: Stop immediately on definitive pattern
        6. Paint winning components on original image
        7. Return success based on count AND geometry validation

        Args:
            anImage: Input camera image (BGR from OpenCV)
            componentQRCode: QR code string to determine model (DOST/DOSTPLUS)
            bearing_geometry: Optional dict with 'center', 'inner_radius', 'outer_radius'
                              from CheckTopBearing. When provided, the returned image is
                              cropped to 300x300 centred on bearing_geometry['center'].
                              When None, the full annotated image is returned.

        Returns:
            Tuple of:
                - processed_image: 300x300 crop centred on bearing centre (if
                                   bearing_geometry provided), otherwise full annotated image
                - success: True if correct hole count detected with valid geometry
                - winning_gamma: Gamma value that produced the result
        """
        _src = getFullyQualifiedName(__file__, CheckBunk)

        # Resolve crop centre once — used for every return path below
        if bearing_geometry is not None:
            crop_center = bearing_geometry["center"]
        else:
            crop_center = None

        def _maybe_crop(bgr_img: np.ndarray) -> np.ndarray:
            """Apply 300x300 crop if a bearing centre is available."""
            if crop_center is not None:
                return CheckBunk._crop300(bgr_img, crop_center)
            return bgr_img

        if PRINT_QR_PARSING:
            logBoth('logDebug', _src, f"[CheckBunk v2.0] Called with QRCode={componentQRCode}", MessageType.GENERAL)

        # Validate inputs
        if anImage is None:
            if PRINT_QR_PARSING:
                logBoth('logError', _src, "[CheckBunk] anImage is None", MessageType.ISSUE)
            return None, False, None

        if componentQRCode is None:
            if PRINT_QR_PARSING:
                logBoth('logError', _src, "[CheckBunk] componentQRCode is None", MessageType.ISSUE)
            return _maybe_crop(anImage), False, None

        # Get segmenter
        segmenter = BunkSegmenter.get_instance() if SAM_AVAILABLE else None
        if segmenter is None:
            if PRINT_QR_PARSING:
                logBoth('logError', _src, "[CheckBunk] Segmenter not available", MessageType.ISSUE)
            return _maybe_crop(anImage), False, None

        # Determine expected count from QR code
        try:
            model, lhs_rhs, tonnage = getModel_LHSRHS_AndTonnage(componentQRCode)
            if PRINT_QR_PARSING:
                logBoth('logDebug', _src, f"[CheckBunk] Model: {model}, LHS/RHS: {lhs_rhs}, Tonnage: {tonnage}", MessageType.GENERAL)

            if model == "DOST":
                expected_count = 4
            elif model == "DOSTPLUS":
                expected_count = 2
            else:
                if PRINT_QR_PARSING:
                    logBoth('logError', _src, f"[CheckBunk] Unknown model: {model}", MessageType.ISSUE)
                return _maybe_crop(anImage), False, None

            if PRINT_QR_PARSING:
                logBoth('logDebug', _src, f"[CheckBunk] Expected count: {expected_count}", MessageType.GENERAL)

        except Exception as e:
            if PRINT_QR_PARSING:
                logBoth('logError', _src, f"[CheckBunk] Failed to parse QR code: {e}", MessageType.ISSUE)
                import traceback
                traceback.print_exc()
            return _maybe_crop(anImage), False, None

        # Convert BGR to RGB (camera provides BGR, segmenter expects RGB)
        anImage_rgb = cv2.cvtColor(anImage, cv2.COLOR_BGR2RGB)
        if PRINT_IMAGE_PREPROCESSING:
            logBoth('logDebug', _src, "[CheckBunk] Converted BGR to RGB", MessageType.GENERAL)

        # STEP 1: Determine gamma sequence (now optimized with gamma 2.0 first)
        from camera.BunkSegmenter import get_gamma_sequence_for_model
        gamma_sequence = get_gamma_sequence_for_model(expected_count)

        if PRINT_IMAGE_PREPROCESSING:
            logBoth('logDebug', _src, f"[CheckBunk] Testing gammas in order: {gamma_sequence}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"[CheckBunk] Will stop as soon as definitive pattern found", MessageType.GENERAL)

        # Helper function for parallel preprocessing
        def preprocess_single_gamma(gamma):
            """Preprocess a single gamma variant."""
            return segmenter._preprocess_image(anImage_rgb, gamma)

        # STEP 2: LAZY EVALUATION with parallel preprocessing
        try:
            # Use ThreadPoolExecutor for parallel preprocessing
            with ThreadPoolExecutor(max_workers=2) as executor:
                future_next = None

                for idx, gamma in enumerate(gamma_sequence):
                    if PRINT_IMAGE_PREPROCESSING:
                        logBoth('logDebug', _src,
                                f"[CheckBunk] Processing gamma {gamma} (position {idx + 1}/{len(gamma_sequence)})...",
                                MessageType.GENERAL)

                    # If we have a future from previous iteration, get its result
                    # Otherwise, preprocess current gamma
                    if future_next is not None:
                        preprocessed = future_next.result()
                        if PRINT_IMAGE_PREPROCESSING:
                            logBoth('logDebug', _src, f"[CheckBunk] Used parallel-preprocessed gamma {gamma}", MessageType.GENERAL)
                    else:
                        preprocessed = preprocess_single_gamma(gamma)
                        if PRINT_IMAGE_PREPROCESSING:
                            logBoth('logDebug', _src, f"[CheckBunk] Preprocessed gamma {gamma}", MessageType.GENERAL)

                    # Start preprocessing NEXT gamma in parallel while GPU is busy
                    # (if there is a next gamma)
                    if idx + 1 < len(gamma_sequence):
                        next_gamma = gamma_sequence[idx + 1]
                        future_next = executor.submit(preprocess_single_gamma, next_gamma)
                        if PRINT_IMAGE_PREPROCESSING:
                            logBoth('logDebug', _src, f"[CheckBunk] Started parallel preprocessing of gamma {next_gamma}", MessageType.GENERAL)
                    else:
                        future_next = None

                    # Run GPU segmentation on current gamma
                    if PRINT_BATCH_SEGMENTATION:
                        logBoth('logDebug', _src, f"[CheckBunk] Running GPU segmentation on gamma {gamma}...", MessageType.GENERAL)

                    # Process single gamma
                    detected_count, components, found_definitive = \
                        segmenter.segment_holes_single(
                            preprocessed,
                            gamma,
                            expected_count=expected_count,
                            model_type=model
                        )

                    if PRINT_BATCH_SEGMENTATION:
                        logBoth('logDebug', _src, f"[CheckBunk] Result for gamma {gamma}:", MessageType.GENERAL)
                        logBoth('logDebug', _src, f"  Detected count: {detected_count}", MessageType.GENERAL)
                        logBoth('logDebug', _src, f"  Expected count: {expected_count}", MessageType.GENERAL)
                        logBoth('logDebug', _src, f"  Definitive pattern: {found_definitive}", MessageType.GENERAL)

                    # SUCCESS CRITERIA:
                    # - Count must match expected
                    # - Must have found definitive pattern (geometry validated)
                    success = (detected_count == expected_count and found_definitive)

                    # SPECIAL CASE: If expected 2 but found valid 4-hole square
                    # This is a FAIL (wrong model type - should be DOST not DOSTPLUS)
                    if expected_count == 2 and detected_count == 4 and found_definitive:
                        if PRINT_SUCCESS_EVALUATION:
                            logBoth('logError', _src,
                                    f"[CheckBunk] ✗ FAIL - Found 4-hole DOST pattern but expected 2-hole DOSTPLUS",
                                    MessageType.ISSUE)
                        success = False

                    # Check for definitive result (success OR definitive failure)
                    if found_definitive:
                        if success:
                            if PRINT_SUCCESS_EVALUATION:
                                logBoth('logInfo', _src,
                                        f"[CheckBunk] ✓ SUCCESS - Count {detected_count} matches expected with valid geometry",
                                        MessageType.SUCCESS)
                                logBoth('logInfo', _src,
                                        f"[CheckBunk] >>> WINNER: Gamma {gamma} (stopped at position {idx + 1}/{len(gamma_sequence)}) <<<",
                                        MessageType.SUCCESS)
                        else:
                            if PRINT_SUCCESS_EVALUATION:
                                logBoth('logError', _src,
                                        f"[CheckBunk] ✗ FAIL - Count {detected_count} != expected {expected_count} OR invalid geometry",
                                        MessageType.ISSUE)
                                logBoth('logError', _src,
                                        f"[CheckBunk] >>> DEFINITIVE FAILURE at gamma {gamma} (stopped at position {idx + 1}/{len(gamma_sequence)}) <<<",
                                        MessageType.ISSUE)

                        # Cancel any pending preprocessing (early termination!)
                        if future_next is not None:
                            cancelled = future_next.cancel()
                            if cancelled and PRINT_IMAGE_PREPROCESSING:
                                logBoth('logDebug', _src,
                                        f"[CheckBunk] Cancelled preprocessing of gamma {gamma_sequence[idx + 1]} (not needed)",
                                        MessageType.GENERAL)

                        # Paint masks on original image (even for failures, to show what was detected)
                        result_image = paint_bunk_masks_on_image(anImage_rgb, components, color=(0, 255, 0))

                        if PRINT_RESULT_PAINTING:
                            logBoth('logDebug', _src, f"[CheckBunk] Painted {len(components)} masks on image", MessageType.GENERAL)

                        # Convert back to BGR for OpenCV, then crop
                        result_bgr = cv2.cvtColor(result_image, cv2.COLOR_RGB2BGR)

                        return _maybe_crop(result_bgr), success, gamma

                    # No definitive result yet, continue to next gamma
                    else:
                        if PRINT_BATCH_SEGMENTATION:
                            logBoth('logDebug', _src, f"[CheckBunk] Gamma {gamma}: No definitive pattern - trying next gamma", MessageType.GENERAL)

                # If we get here, no gamma produced definitive result
                if PRINT_SUCCESS_EVALUATION:
                    logBoth('logError', _src, f"[CheckBunk] ✗ FAIL - No definitive pattern found in any gamma", MessageType.ISSUE)

                result_bgr = cv2.cvtColor(anImage_rgb, cv2.COLOR_RGB2BGR)
                return _maybe_crop(result_bgr), False, None

        except Exception as e:
            if PRINT_BATCH_SEGMENTATION:
                logBoth('logError', _src, f"[CheckBunk] Segmentation failed: {e}", MessageType.PROBLEM)
                import traceback
                traceback.print_exc()
            return _maybe_crop(cv2.cvtColor(anImage_rgb, cv2.COLOR_RGB2BGR)), False, None

def test_checkBunk():
    """Test function for CheckBunk v2.0."""
    import time
    from pathlib import Path

    print("CheckBunk v2.0 Test - V0.7 PIPELINE WITH FIXED GAMMA SEQUENCE")
    print("=" * 80)

    # Test folder path
    test_folder = "C:/AutoCompanyImages/DOSTPLUS/LHS/"  # Adjust as needed

    # Output directory
    output_dir = "C:/Test/Bunk"
    os.makedirs(output_dir, exist_ok=True)
    print(f"✓ Output directory: {output_dir}")

    # Get all image files
    image_extensions = ['.png', '.jpg', '.jpeg', '.bmp']
    all_files = []

    if os.path.exists(test_folder):
        for ext in image_extensions:
            all_files.extend(Path(test_folder).glob(f'*{ext}'))

        # Filter for bunk images
        test_files = [f for f in all_files if 'bung' in f.name.lower()]

        print(f"✓ Found {len(test_files)} bunk image files")
        print(f"  Folder: {test_folder}")
    else:
        print(f"✗ Folder not found: {test_folder}")
        test_files = []

    if not test_files:
        print("No test files found. Exiting.")
        return

    # Test QR codes
    # DOST - expects 4 holes
    dost_qr = "7204838$400112VA1D$11770$09.03.2025$C5211701$MEK$40cR4-B$1$SPDL ASSY-KNULH$SNPL-MAT$"

    # DOSTPLUS - expects 2 holes
    dostplus_qr = "8201206$400112VA1C$11770$09.03.2025$C5211701$MEK$40Cr4-B$1$SPDL ASSY-KNULH$SNPL-MAT$"

    # Choose based on folder
    test_qr = dost_qr if 'DOST' in test_folder and 'DOSTPLUS' not in test_folder else dostplus_qr

    print(f"\nUsing QR code: {test_qr[:50]}...")

    # Process each file
    results_summary = []

    for idx, test_file in enumerate(test_files, 1):
        print(f"\n{'=' * 80}")
        print(f"[{idx}/{len(test_files)}] Processing: {test_file.name}")
        print(f"{'=' * 80}")

        # Load image
        test_image = cv2.imread(str(test_file))
        if test_image is None:
            print(f"  ✗ Failed to load image")
            results_summary.append((test_file.name, False, None, None))
            continue

        print(f"  ✓ Loaded image: {test_image.shape}")

        # Run check
        start_time = time.time()

        result_img, success, gamma_used = CheckBunk.checkBunk(
            test_image,
            componentQRCode=test_qr
        )

        elapsed_time = time.time() - start_time

        status = '✓ SUCCESS' if success else '✗ FAIL'
        print(f"  Result: {status}")
        print(f"  Time: {elapsed_time:.3f}s")
        print(f"  Gamma: {gamma_used}")

        # Save result
        if result_img is not None:
            output_filename = os.path.join(output_dir, f"result_{test_file.stem}.png")
            cv2.imwrite(output_filename, result_img)
            print(f"  ✓ Saved: {output_filename}")

        results_summary.append((test_file.name, success, elapsed_time, gamma_used))

    # Final Summary
    print(f"\n{'=' * 80}")
    print("FINAL SUMMARY")
    print(f"{'=' * 80}")
    print(f"Total files processed: {len(test_files)}")
    print()

    passed = sum(1 for _, success, _, _ in results_summary if success)
    failed = len(results_summary) - passed

    print(f"PASS: {passed}/{len(results_summary)}")
    print(f"FAIL: {failed}/{len(results_summary)}")
    print()

    print("Detailed Results:")
    print(f"{'File':<50} {'Result':<8} {'Time':<8} {'Gamma':<8}")
    print("-" * 80)
    for filename, success, elapsed, gamma in results_summary:
        result_str = 'PASS' if success else 'FAIL'
        time_str = f"{elapsed:.2f}s" if elapsed else 'N/A'
        gamma_str = f"{gamma:.2f}" if gamma is not None else 'N/A'
        print(f"{filename:<50} {result_str:<8} {time_str:<8} {gamma_str:<8}")

    print(f"{'=' * 80}")


# Uncomment to run tests
# if __name__ == "__main__":
#     test_checkBunk()
