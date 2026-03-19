"""
CheckHubAndBottomBearing.py
Implements hub and bottom bearing verification using MobileSAMv2 segmentation.

v2.0 CHANGES:
- Updated to work with HubAndBearingSegmenter v2.0
- Added mismatch detection (detects if wrong component is presented)
- segment_holes_batch() now returns (count, groups, detected_model, is_match)
- Returns False when detected model doesn't match expected model from QR code

Uses HubAndBearingSegmenter_STANDALONE (no dependency on SAMSegmentation_v0_99)
"""

import copy
import numpy as np
import cv2
from typing import Dict, Tuple, Optional, List
import os
import sys

import torch
from numpy import ndarray

from BaseUtils import *
from logutils.SlaveLoggers import logBoth
from logutils.Logger import MessageType
from utils.QRCodeHelper import getModel_LHSRHS_AndTonnage
from Configuration import CosThetaConfigurator
from concurrent.futures import ThreadPoolExecutor

# Import the core segmentation engine (STANDALONE VERSION v2.0)
try:
    from camera.HubAndBearingSegmenter import (
        HubAndBearingSegmenter,
        select_best_group,
        paint_masks_on_image
    )

    SAM_AVAILABLE = True
except ImportError as e:
    logBoth('logWarning', __name__, f"Warning: HubAndBearingSegmenter not available: {e}", MessageType.RISK)
    SAM_AVAILABLE = False
    HubAndBearingSegmenter = None  # Prevents NameError


def determine_smart_gamma_order(image: np.ndarray) -> List[int]:
    """
    Determine optimal gamma testing order based on image brightness.

    Args:
        image: Input RGB image

    Returns:
        List of gamma values in priority order
    """
    _src = __name__

    # Calculate average brightness (0-255)
    brightness = np.mean(image)

    logBoth('logDebug', _src, f"[SmartGamma] Image brightness: {brightness:.1f}", MessageType.GENERAL)

    if brightness < 60:
        # Very dark image - needs strong brightening
        gamma_order = [4, 6, 3, 5, 2, 1]
        logBoth('logDebug', _src, "[SmartGamma] Very dark → trying high gammas first", MessageType.GENERAL)
    elif brightness < 90:
        # Dark image - moderate brightening
        gamma_order = [3, 4, 2, 5, 1, 6]
        logBoth('logDebug', _src, "[SmartGamma] Dark → trying medium-high gammas", MessageType.GENERAL)
    elif brightness < 120:
        # Normal brightness
        gamma_order = [1, 3, 2, 4, 5, 6]
        logBoth('logDebug', _src, "[SmartGamma] Normal → standard order", MessageType.GENERAL)
    elif brightness < 150:
        # Slightly bright
        gamma_order = [1, 2, 3, 4, 5, 6]
        logBoth('logDebug', _src, "[SmartGamma] Bright → trying lower gammas", MessageType.GENERAL)
    else:
        # Very bright - may need darkening
        gamma_order = [1, 2, 3, 4, 5, 6]
        logBoth('logDebug', _src, "[SmartGamma] Very bright → trying lowest gammas", MessageType.GENERAL)

    return gamma_order


class CheckHubAndBottomBearing:
    """
    Checks hub and bottom bearing assembly by detecting and counting mounting holes.

    Uses MobileSAMv2 for segmentation and sophisticated grouping algorithms to:
    1. Detect circular holes in annular region
    2. Group holes by distance and size
    3. Filter by spatial distribution and equispacing
    4. Verify correct count based on component model (DOST=4, DOSTPLUS=5)

    v2.0: Now includes mismatch detection - returns False if detected component
    type doesn't match the expected type from QR code.
    """

    # Class-level segmenter (lazy initialization)
    # _segmenter: Optional[HubAndBearingSegmenter] = None
    # _segmenter_initialized = False

    # Gamma correction LUT (gamma = 3.0)
    _gamma_lut = None

    @classmethod
    def _get_gamma_lut(cls) -> np.ndarray:
        """Get or create gamma correction lookup table (gamma=3.0)."""
        if cls._gamma_lut is None:
            inv_gamma = 1.0 / 3.0
            cls._gamma_lut = np.array([
                ((i / 255.0) ** inv_gamma) * 255
                for i in range(256)
            ]).astype(np.uint8)
        return cls._gamma_lut

    # @classmethod
    # def _get_segmenter(cls) -> Optional[HubAndBearingSegmenter]:
    #     """Get or initialize the segmenter (singleton pattern)."""
    #     if not SAM_AVAILABLE:
    #         return None
    #
    #     if not cls._segmenter_initialized:
    #         # cls._segmenter = HubAndBearingSegmenter(None, None)  # No paths needed
    #         cls._segmenter = HubAndBearingSegmenter.get_instance()
    #         cls._segmenter_initialized = True
    #     return cls._segmenter

    @classmethod
    def ensureNoBearingInCentre(cls, image: np.ndarray) -> bool:
        """
        Check if there's no bearing present in the center region.

        Args:
            image: Input BGR image

        Returns:
            True if average pixel value < 144 (no bearing), False otherwise
        """
        _src = getFullyQualifiedName(__file__, cls)

        # Get gamma LUT
        gamma_lut = cls._get_gamma_lut()

        # Apply gamma correction
        gamma_corrected = cv2.LUT(image, gamma_lut)

        # Convert to grayscale
        gray = cv2.cvtColor(gamma_corrected, cv2.COLOR_BGR2GRAY)

        # Create annular mask (center: 635, 350; inner: 20; outer: 60)
        h, w = gray.shape
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(mask, (635, 350), 60, 255, -1)  # Outer circle
        cv2.circle(mask, (635, 350), 20, 0, -1)  # Inner circle (hole)

        # Extract pixels within mask
        masked_pixels = gray[mask > 0]

        # Calculate average
        average = np.mean(masked_pixels)

        logBoth('logDebug', _src, f"[ensureNoBearingInCentre] Average pixel value: {average:.2f}", MessageType.GENERAL)

        # Return True if average < 144 (no bearing present)
        return average < 144

    @staticmethod
    def checkHubAndBottomBearing(
            anImage: np.ndarray,
            componentQRCode: str = None,
            use_smart_gamma: bool = True
    ) -> Tuple[Optional[ndarray], bool, Optional[int]]:
        """
        Test gamma values with TRUE early termination (lazy evaluation).
        Optionally parallelizes preprocessing of next gamma while GPU is busy.

        v2.0: Now includes mismatch detection. Returns False if detected component
        type (DOST/DOSTPLUS) doesn't match the expected type from QR code.

        Args:
            anImage: Input BGR image from camera
            componentQRCode: QR code string containing component info
            use_smart_gamma: If True, order gamma values based on image brightness

        Returns:
            Tuple of (result_image, success, winning_gamma)
            - result_image: Image with masks painted (or original if failed)
            - success: True if verification passed
            - winning_gamma: Gamma value that worked (or None)

        IMPORTANT: success will be False if:
        - No valid detections found
        - Count doesn't match expected
        - Detected model doesn't match expected (mismatch detection - v2.0)
        """
        _src = getFullyQualifiedName(__file__, CheckHubAndBottomBearing)

        logBoth('logDebug', _src,
                f"CheckHubAndBottomBearing.checkHubAndBottomBearing() called with "
                f"anImage = {anImage.shape if anImage is not None else 'None'}",
                MessageType.GENERAL)

        if anImage is None or componentQRCode is None:
            return None, False, None

        # Get model info from QR code
        model_name, lhs_rhs, tonnage = getModel_LHSRHS_AndTonnage(componentQRCode)

        if model_name not in ["DOST", "DOSTPLUS"]:
            logBoth('logError', _src, f"[CheckHubAndBottomBearing] Unknown model: {model_name}", MessageType.ISSUE)
            return anImage, False, None

        expected_count = 4 if model_name == "DOST" else 5
        logBoth('logDebug', _src, f"[CheckHubAndBottomBearing] Expected model: {model_name}, count: {expected_count}", MessageType.GENERAL)

        # Check if bearing is present in center region
        if not CheckHubAndBottomBearing.ensureNoBearingInCentre(anImage):
            logBoth('logError', _src, "[CheckHubAndBottomBearing] Bearing detected in center - should not be present", MessageType.ISSUE)
            return anImage, False, None

        logBoth('logInfo', _src, "[CheckHubAndBottomBearing] No bearing in center - proceeding with verification", MessageType.SUCCESS)

        # Get segmenter
        segmenter = HubAndBearingSegmenter.get_instance() if SAM_AVAILABLE else None
        if segmenter is None:
            logBoth('logError', _src, "[CheckHubAndBottomBearing] Segmenter not available", MessageType.ISSUE)
            return anImage, False, None

        # Convert BGR to RGB (camera provides BGR, segmenter expects RGB)
        anImage_rgb = cv2.cvtColor(anImage, cv2.COLOR_BGR2RGB)
        logBoth('logDebug', _src, "[CheckHubAndBottomBearing] Converted BGR to RGB", MessageType.GENERAL)

        try:
            # SMART GAMMA ORDERING
            if use_smart_gamma:
                gamma_values = determine_smart_gamma_order(anImage_rgb)
            else:
                gamma_values = [1, 2, 3, 4, 5, 6]

            logBoth('logDebug', _src, f"[LazyEval] Testing gammas in order: {gamma_values}", MessageType.GENERAL)
            logBoth('logDebug', _src, f"[LazyEval] Will stop as soon as valid detection found", MessageType.GENERAL)

            # Helper function for parallel preprocessing
            def preprocess_single_gamma(gamma):
                """Preprocess a single gamma variant."""
                preprocessed, _ = segmenter.preprocess_image(
                    anImage_rgb, gamma=gamma,
                    bg_sx=10, bg_sy=10, cn_sx=10, cn_sy=10,
                    apply_bilateral=True, alter_gamma=True
                )
                return preprocessed

            # Use ThreadPoolExecutor for parallel preprocessing
            with ThreadPoolExecutor(max_workers=2) as executor:
                future_next = None

                for idx, gamma in enumerate(gamma_values):
                    logBoth('logDebug', _src, f"[LazyEval] Processing gamma {gamma} (position {idx + 1}/{len(gamma_values)})...", MessageType.GENERAL)

                    # If we have a future from previous iteration, get its result
                    # Otherwise, preprocess current gamma
                    if future_next is not None:
                        preprocessed = future_next.result()
                        logBoth('logDebug', _src, f"[LazyEval] Used parallel-preprocessed gamma {gamma}", MessageType.GENERAL)
                    else:
                        preprocessed = preprocess_single_gamma(gamma)
                        logBoth('logDebug', _src, f"[LazyEval] Preprocessed gamma {gamma}", MessageType.GENERAL)

                    # Start preprocessing NEXT gamma in parallel while GPU is busy
                    # (if there is a next gamma)
                    if idx + 1 < len(gamma_values):
                        next_gamma = gamma_values[idx + 1]
                        future_next = executor.submit(preprocess_single_gamma, next_gamma)
                        logBoth('logDebug', _src, f"[LazyEval] Started parallel preprocessing of gamma {next_gamma}", MessageType.GENERAL)
                    else:
                        future_next = None

                    # Run GPU segmentation on current gamma
                    logBoth('logDebug', _src, f"[LazyEval] Running GPU segmentation on gamma {gamma}...", MessageType.GENERAL)
                    count, groups_with_tuples, detected_model, is_match = \
                        segmenter.segment_holes(preprocessed, model_type=model_name)

                    # Check if we have valid results
                    if count > 0 and groups_with_tuples:
                        winning_group = select_best_group(groups_with_tuples)

                        # v2.0: Check for model mismatch FIRST (safety-critical)
                        if not is_match:
                            logBoth('logError', _src, f"[LazyEval] *** MISMATCH DETECTED at gamma {gamma} ***", MessageType.PROBLEM)
                            logBoth('logError', _src, f"  Expected: {model_name}, Detected: {detected_model}", MessageType.PROBLEM)
                            logBoth('logError', _src, f"  WRONG COMPONENT may be presented!", MessageType.PROBLEM)

                            # Cancel any pending preprocessing
                            if future_next is not None:
                                future_next.cancel()

                            # Paint with RED to indicate mismatch
                            if winning_group:
                                result_image = paint_masks_on_image(anImage_rgb, winning_group, color=(255, 0, 0))
                                cv2.putText(result_image, f"MISMATCH: Expected {model_name}, Got {detected_model}",
                                            (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
                            else:
                                result_image = anImage_rgb

                            # Clear GPU
                            if torch.cuda.is_available():
                                torch.cuda.empty_cache()

                            # Return FAILURE due to mismatch
                            return cv2.cvtColor(result_image, cv2.COLOR_RGB2BGR), False, gamma

                        # Model matches - now check count
                        if winning_group and len(winning_group) == expected_count:
                            logBoth('logInfo', _src,
                                    f"[LazyEval] >>> WINNER: Gamma {gamma} (stopped at position {idx + 1}/{len(gamma_values)}) <<<",
                                    MessageType.SUCCESS)
                            logBoth('logInfo', _src,
                                    f"  Detected: {detected_model}, Count: {len(winning_group)}, Match: {is_match}",
                                    MessageType.SUCCESS)

                            # Cancel any pending preprocessing (early termination!)
                            if future_next is not None:
                                cancelled = future_next.cancel()
                                if cancelled:
                                    logBoth('logDebug', _src,
                                            f"[LazyEval] Cancelled preprocessing of gamma {gamma_values[idx + 1]} (not needed)",
                                            MessageType.GENERAL)

                            result_image = paint_masks_on_image(anImage_rgb, winning_group, color=(0, 255, 0))

                            # Clear GPU after finding winner
                            if torch.cuda.is_available():
                                torch.cuda.empty_cache()

                            # EARLY TERMINATION: Exit immediately without processing remaining gammas
                            return cv2.cvtColor(result_image, cv2.COLOR_RGB2BGR), True, gamma
                        else:
                            # Count mismatch (not a model mismatch)
                            actual_count = len(winning_group) if winning_group else 0
                            logBoth('logWarning', _src,
                                    f"[LazyEval] Gamma {gamma}: Count mismatch - expected {expected_count}, got {actual_count}",
                                    MessageType.RISK)
                            # Continue to next gamma
                    else:
                        logBoth('logWarning', _src, f"[LazyEval] Gamma {gamma}: No valid detections", MessageType.RISK)
                        # Continue to next gamma

            # No success after trying all gammas
            logBoth('logError', _src, "[LazyEval] No valid detections in any gamma", MessageType.ISSUE)
            return cv2.cvtColor(anImage_rgb, cv2.COLOR_RGB2BGR), False, None

        except Exception as e:
            logBoth('logCritical', _src, f"[LazyEval] Exception: {e}", MessageType.PROBLEM)
            import traceback
            traceback.print_exc()
            return cv2.cvtColor(anImage_rgb, cv2.COLOR_RGB2BGR), False, None

# =============================================================================
# TEST FUNCTION - Updated for v2.0
# =============================================================================

def test6NumpyStackedImagesImplementation():
    """
    Test function for batch processing with v2.0 mismatch detection.

    Saves final masked images to C:/Test/Hub/
    """
    import time
    from pathlib import Path

    print("=" * 80)
    print("CheckHubAndBottomBearing Test - v2.0 with MISMATCH DETECTION")
    print("=" * 80)

    # Folder path containing test images
    test_folder = "C:/AutoCompanyImages/DOSTPLUS/LHS/"

    # Use real QR code
    # DOST (4 holes)
    # test_qr = "7204838$400112VA1D$11770$09.03.2025$C5211701$MEK$40cR4-B$1$SPDL ASSY-KNULH$SNPL-MAT$"

    # DOSTPLUS (5 holes)
    test_qr = "8201206$400112VA1C$11770$09.03.2025$C5211701$MEK$40Cr4-B$1$SPDL ASSY-KNULH$SNPL-MAT$"

    # Output directory - Updated to C:/Test/Hub
    output_dir = "C:/Test/Hub"
    os.makedirs(output_dir, exist_ok=True)
    print(f"✓ Output directory: {output_dir}")

    # Get model info for display
    model_name, _, _ = getModel_LHSRHS_AndTonnage(test_qr)
    expected_count = 4 if model_name == "DOST" else 5
    print(f"✓ Expected model: {model_name} ({expected_count} holes)")

    # Get all image files (excluding knuckle)
    image_extensions = ['.png', '.jpg', '.jpeg', '.bmp']
    all_files = []

    if os.path.exists(test_folder):
        for ext in image_extensions:
            all_files.extend(Path(test_folder).glob(f'*{ext}'))

        # Filter out files with "knuckle" in name
        test_files = [f for f in all_files if 'hub' in f.name.lower()]

        # Test on previous stages image
        # test_files = [f for f in all_files if 'knuckle' in f.name.lower()]

        print(f"✓ Found {len(test_files)} image files (excluding knuckle)")
        print(f"  Folder: {test_folder}")
    else:
        print(f"✗ Folder not found: {test_folder}")
        test_files = []

    if not test_files:
        print("No test files found. Exiting.")
        sys.exit(1)

    # Process each file
    overall_start = time.time()
    results_summary = []

    for idx, test_file in enumerate(test_files, 1):
        print(f"\n{'=' * 80}")
        print(f"[{idx}/{len(test_files)}] Processing: {test_file.name}")
        print(f"{'=' * 80}")

        # Load image
        test_image = cv2.imread(str(test_file))
        if test_image is None:
            print(f"  ✗ Failed to load image")
            results_summary.append((test_file.name, False, None, None, None, None))
            continue

        print(f"  ✓ Loaded image: {test_image.shape}")

        # TEST 1: Batch processing WITH smart gamma ordering
        print(f"\n  === Test 1: Batch with Smart Gamma ===")
        start_time = time.time()

        result_img_smart, success_smart, winning_gamma_smart = \
            CheckHubAndBottomBearing.checkHubAndBottomBearing(
                test_image.copy(),
                test_qr,
                use_smart_gamma=True
            )

        time_smart = time.time() - start_time
        status_smart = '✓ SUCCESS' if success_smart else '✗ FAIL'
        print(f"  Result: {status_smart}")
        if winning_gamma_smart:
            print(f"  Winning gamma: {winning_gamma_smart}")
        print(f"  Time: {time_smart:.3f}s")

        # TEST 2: Batch processing WITHOUT smart gamma (standard order)
        print(f"\n  === Test 2: Batch with Standard Order ===")
        start_time = time.time()

        result_img_standard, success_standard, winning_gamma_standard = \
            CheckHubAndBottomBearing.checkHubAndBottomBearing(
                test_image.copy(),
                test_qr,
                use_smart_gamma=False
            )

        time_standard = time.time() - start_time
        status_standard = '✓ SUCCESS' if success_standard else '✗ FAIL'
        print(f"  Result: {status_standard}")
        if winning_gamma_standard:
            print(f"  Winning gamma: {winning_gamma_standard}")
        print(f"  Time: {time_standard:.3f}s")

        # Compare timing
        if time_smart < time_standard:
            speedup = ((time_standard - time_smart) / time_standard) * 100
            print(f"\n  🚀 Smart gamma was {speedup:.1f}% FASTER")
        elif time_smart > time_standard:
            slowdown = ((time_smart - time_standard) / time_standard) * 100
            print(f"\n  ⚠️ Smart gamma was {slowdown:.1f}% SLOWER")
        else:
            print(f"\n  ⚖️ Same performance")

        # Use smart gamma result as final
        final_result = result_img_smart
        final_success = success_smart
        winning_gamma = winning_gamma_smart
        elapsed_time = time_smart

        # Save result to C:/Test/Hub (ALWAYS save, with status prefix)
        if final_result is not None:
            # Determine filename based on result
            status_prefix = "PASS" if final_success else "FAIL"
            gamma_suffix = f"_gamma{winning_gamma}" if winning_gamma else ""
            output_filename = os.path.join(output_dir, f"{status_prefix}_{test_file.stem}{gamma_suffix}.png")

            # final_result is already in BGR format from checkHubAndBottomBearing
            cv2.imwrite(output_filename, final_result)
            print(f"\n  ✓ Saved: {output_filename}")

        results_summary.append((test_file.name, final_success, winning_gamma, elapsed_time, time_smart, time_standard))

        # Clear GPU cache
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()

    # Final Summary
    overall_time = time.time() - overall_start

    print(f"\n{'=' * 80}")
    print("FINAL SUMMARY - v2.0 BATCH PROCESSING with MISMATCH DETECTION")
    print(f"{'=' * 80}")
    print(f"Total files processed: {len(test_files)}")
    print(f"Total time: {overall_time:.2f}s")
    print(f"Average time per file: {overall_time / len(test_files):.2f}s" if test_files else "N/A")
    print()

    passed = sum(1 for _, success, _, _, _, _ in results_summary if success)
    failed = len(results_summary) - passed

    print(f"PASS: {passed}/{len(results_summary)}")
    print(f"FAIL: {failed}/{len(results_summary)}")
    print()

    # Calculate average speedup
    total_smart_time = sum(t_smart for _, _, _, _, t_smart, _ in results_summary if t_smart)
    total_standard_time = sum(t_std for _, _, _, _, _, t_std in results_summary if t_std)

    if total_standard_time > 0:
        overall_speedup = ((total_standard_time - total_smart_time) / total_standard_time) * 100
        print(f"Smart Gamma Overall Speedup: {overall_speedup:.1f}%")
        print(f"  Smart gamma total: {total_smart_time:.2f}s")
        print(f"  Standard order total: {total_standard_time:.2f}s")
        print()

    print("Detailed Results:")
    print(f"{'File':<40} {'Result':<8} {'Gamma':<7} {'Smart':<10} {'Standard':<10} {'Speedup':<10}")
    print("-" * 95)

    for filename, success, gamma, _, time_smart, time_standard in results_summary:
        result_str = 'PASS' if success else 'FAIL'
        gamma_str = str(gamma) if gamma else 'N/A'
        smart_str = f"{time_smart:.3f}s" if time_smart else 'N/A'
        standard_str = f"{time_standard:.3f}s" if time_standard else 'N/A'

        if time_smart and time_standard and time_standard > 0:
            speedup_pct = ((time_standard - time_smart) / time_standard) * 100
            speedup_str = f"{speedup_pct:+.1f}%"
        else:
            speedup_str = 'N/A'

        print(f"{filename:<40} {result_str:<8} {gamma_str:<7} {smart_str:<10} {standard_str:<10} {speedup_str:<10}")

    print(f"{'=' * 95}")
    print(f"\nAll results saved to: {output_dir}")


# Uncomment to run test
# test6NumpyStackedImagesImplementation()