"""
CheckCap - Detects presence of Cap by comparing with previous assembly stage images.

Detection Method:
    Two-step verification:

    Step 1: Color Delta Analysis
        - Compare Cap image against 3 base images (Hub+Bottom Bearing, Top Bearing, Nut+Plate Washer)
        - For each pixel in circular mask, calculate (R_cap - R_base), (G_cap - G_base), (B_cap - B_base)
        - Clamp values to [0, 255] and average to get grayscale delta
        - If average delta for all 3 comparisons exceeds threshold, Step 1 passes

    Step 2: Cap Color Verification
        - Calculate average (R - B) within the circular mask
        - If R - B average is less than threshold, Step 2 passes

Parameters (from configuration):
    CENTER_X, CENTER_Y: Center of the cap region (default: 635, 360)
    RADIUS: 100 for DOST, 70 for DOSTPLUS
    DELTA_THRESHOLD: Minimum average delta required (default: 30)
    RB_THRESHOLD: Maximum R-B value for cap (default: -1)
"""

import cv2
import numpy as np
from typing import Dict, Tuple
import glob
import os
# from HandDetector import HandDetector

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
    nutAndPlateWasherPictureKeyString = "nutAndPlateWasherPicture"

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

    def getModel_LHSRHS_AndTonnage(qrCode):
        return "DOST", "LHS", "Unknown"

    UNKNOWN = "Unknown"

class CheckCap:
    """
    Checks for the presence of the Cap by comparing the current image
    with previously captured images using a circular mask and color analysis.
    """

    # Default detection parameters (will be overridden by configuration)
    CENTER_X = 633
    CENTER_Y = 344
    RADIUS_DOST = 90
    RADIUS_DOSTPLUS = 65
    DELTA_THRESHOLD_DOST = 30.0
    RB_THRESHOLD_DOST = -1.0
    DELTA_THRESHOLD_DOSTPLUS = 30.0
    RB_THRESHOLD_DOSTPLUS = 15.0

    # Component-specific delta thresholds for Step 1
    DELTA_THRESHOLD_HUB_DOST = 30.0
    DELTA_THRESHOLD_TOP_DOST = 30.0
    DELTA_THRESHOLD_NUT_DOST = 35.0

    DELTA_THRESHOLD_HUB_DOSTPLUS = 35.0
    DELTA_THRESHOLD_TOP_DOSTPLUS = 40.0  # <-- This is the key change!
    DELTA_THRESHOLD_NUT_DOSTPLUS = 35.0

    # Cached circular mask
    _circular_mask = None
    _mask_shape = None
    _mask_radius = None

    @classmethod
    def _load_parameters_from_config(cls, componentType: str = "DOST"):
        """Load parameters from configuration file."""
        try:
            cls.CENTER_X = CosThetaConfigurator.getInstance().getCapCheckCenterX()
            cls.CENTER_Y = CosThetaConfigurator.getInstance().getCapCheckCenterY()
            cls.RADIUS_DOST = CosThetaConfigurator.getInstance().getCapCheckRadius(DOST)
            cls.RADIUS_DOSTPLUS = CosThetaConfigurator.getInstance().getCapCheckRadius(DOSTPLUS)
            cls.DELTA_THRESHOLD_DOST = CosThetaConfigurator.getInstance().getCapCheckDeltaThreshold(DOST)
            cls.RB_THRESHOLD_DOST = CosThetaConfigurator.getInstance().getCapCheckRBThreshold(DOST)
            cls.DELTA_THRESHOLD_DOSTPLUS = CosThetaConfigurator.getInstance().getCapCheckDeltaThreshold(DOSTPLUS)
            cls.RB_THRESHOLD_DOSTPLUS = CosThetaConfigurator.getInstance().getCapCheckRBThreshold(DOSTPLUS)
            # Load component-specific thresholds if available
            cls.DELTA_THRESHOLD_HUB_DOSTPLUS = CosThetaConfigurator.getInstance().getCapCheckDeltaThresholdHub(DOSTPLUS)
            cls.DELTA_THRESHOLD_TOP_DOSTPLUS = CosThetaConfigurator.getInstance().getCapCheckDeltaThresholdTop(DOSTPLUS)
            cls.DELTA_THRESHOLD_NUT_DOSTPLUS = CosThetaConfigurator.getInstance().getCapCheckDeltaThresholdNut(DOSTPLUS)
        except:
            pass

    @classmethod
    def _get_radius_for_component(cls, componentType: str) -> int:
        """Get the appropriate radius based on component type."""
        if componentType.upper() == "DOSTPLUS":
            return cls.RADIUS_DOSTPLUS
        return cls.RADIUS_DOST

    @classmethod
    def _get_circular_mask(cls, image_shape: tuple, radius: int) -> np.ndarray:
        """
        Get the circular mask for the given image shape and radius.
        Creates it on first call or if parameters change, then reuses cached version.
        """
        if (cls._circular_mask is None or
                cls._mask_shape != image_shape[:2] or
                cls._mask_radius != radius):
            h, w = image_shape[:2]
            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.circle(mask, (CheckCap.CENTER_X, CheckCap.CENTER_Y), radius, 255, -1)

            cls._circular_mask = mask
            cls._mask_shape = image_shape[:2]
            cls._mask_radius = radius

        return cls._circular_mask

    @staticmethod
    def _compute_clamped_delta_grayscale(cap_image: np.ndarray,
                                         base_image: np.ndarray,
                                         mask: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Compute the clamped color delta between cap and base image.

        For each pixel: delta = clamp(cap - base, 0, 255) for each channel
        Then average the 3 channels to get grayscale delta.
        """
        cap_float = cap_image.astype(np.float32)
        base_float = base_image.astype(np.float32)

        # Calculate delta for each channel: cap - base
        delta = cap_float - base_float

        # Clamp to [0, 255]
        delta = np.clip(delta, 0, 255)

        # Average across channels to get grayscale (B + G + R) / 3
        delta_grayscale = np.mean(delta, axis=2).astype(np.uint8)

        # Calculate average within the mask
        masked_pixels = delta_grayscale[mask > 0]
        average = float(np.mean(masked_pixels)) if len(masked_pixels) > 0 else 0.0

        return delta_grayscale, average

    @staticmethod
    def _compute_rb_difference(image: np.ndarray, mask: np.ndarray) -> float:
        """
        Compute the average R - B within the masked region.
        Simple subtraction, no absolute value, no clamping.
        """
        # OpenCV uses BGR order
        b_channel = image[:, :, 0].astype(np.float32)
        r_channel = image[:, :, 2].astype(np.float32)

        # Calculate R - B
        rb_diff = r_channel - b_channel

        # Get average within mask
        masked_pixels = rb_diff[mask > 0]
        average = float(np.mean(masked_pixels)) if len(masked_pixels) > 0 else 0.0

        return average

    @staticmethod
    def _create_annotated_image(image: np.ndarray,
                                is_cap_present: bool,
                                step1_passed: bool,
                                step2_passed: bool,
                                delta_averages: list,
                                rb_average: float,
                                radius: int) -> np.ndarray:
        """Create an annotated version of the input image showing the detection result."""
        annotated = image.copy()

        # Draw the circular region
        color = (0, 255, 0) if is_cap_present else (0, 0, 255)
        cv2.circle(annotated, (CheckCap.CENTER_X, CheckCap.CENTER_Y), radius, color, 2)

        # Add result text
        result_text = "CAP: PRESENT" if is_cap_present else "CAP: NOT DETECTED"
        cv2.putText(annotated, result_text, (50, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)

        # Add Step 1 details
        step1_color = (0, 255, 0) if step1_passed else (0, 0, 255)
        step1_text = f"Step1: {'PASS' if step1_passed else 'FAIL'}"
        cv2.putText(annotated, step1_text, (50, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, step1_color, 2)

        # Add delta values
        labels = ["Hub+Bot", "TopBrg", "Nut+PW"]
        for i, (label, avg) in enumerate(zip(labels, delta_averages)):
            delta_text = f"  {label}: {avg:.1f}"
            cv2.putText(annotated, delta_text, (50, 120 + i * 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Add Step 2 details
        step2_color = (0, 255, 0) if step2_passed else (0, 0, 255)
        step2_text = f"Step2: {'PASS' if step2_passed else 'FAIL'} (R-B={rb_average:.1f})"
        cv2.putText(annotated, step2_text, (50, 200),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, step2_color, 2)

        return annotated

    @staticmethod
    def checkCap(anImage: np.ndarray,
                 currentPictures: Dict[str, np.ndarray | None] = None,
                 componentQRCode: str | None = DOST, gamma: float = 2.0) -> Tuple[np.ndarray | None, bool]:
        """
        Check for the presence of the Cap.

        Two-step verification:
        1. Compare with base images - cap should show significant brightness increase
        2. Verify cap color - R - B should be less than threshold

        Args:
            anImage: Current camera image to analyze (Cap image)
            currentPictures: Dictionary containing previously captured images
            componentQRCode: Component QR code for the assembly

        Returns:
            Tuple of:
                - Annotated image showing the detection result
                - Boolean indicating if Cap is present (True) or not (False)
        """
        _src = getFullyQualifiedName(__file__, CheckCap)

        logBoth('logDebug', _src,
                f"CheckCap.checkCap() called with "
                f"anImage = {anImage.shape if anImage is not None else 'None'}",
                MessageType.GENERAL)

        # Basic validation
        if componentQRCode is None:
            logBoth('logError', _src, "CheckCap: componentQRCode is None, returning False", MessageType.ISSUE)
            return anImage, False

        if anImage is None:
            logBoth('logError', _src, "CheckCap: anImage is None, returning False", MessageType.ISSUE)
            return anImage, False

        if currentPictures is None:
            logBoth('logError', _src, "CheckCap: currentPictures is None, returning False", MessageType.ISSUE)
            return anImage, False

        # =====================================================================
        # HAND DETECTION CHECK - First check before any other processing
        # Ensure no operator hands are still in the frame
        # =====================================================================
        # if HandDetector.detectHands(anImage):
        #     logBoth('logError', _src, "CheckCap: HAND DETECTION FAILED - Operator hands detected in image!", MessageType.PROBLEM)
        #     logBoth('logError', _src, "CheckCap: Please ensure hands are completely out of frame before capturing", MessageType.PROBLEM)
        #     return anImage, False
        #
        # logBoth('logInfo', _src, "CheckCap: Hand detection passed - No hands in frame", MessageType.SUCCESS)

        # Get component type from QR code
        modelName, lhs_rhs, _ = getModel_LHSRHS_AndTonnage(componentQRCode)
        logBoth('logDebug', _src, f"Got modelName as {modelName}", MessageType.GENERAL)
        if modelName == UNKNOWN:
            modelName = "DOST"

        # Load parameters from configuration
        CheckCap._load_parameters_from_config(modelName)

        # Get radius based on component type
        radius = CheckCap._get_radius_for_component(modelName)

        logBoth('logDebug', _src, f"CheckCap: Using radius={radius} for component type={modelName}", MessageType.GENERAL)

        # Get base images
        hub_bottom_bearing_image = currentPictures.get(hubAndBottomBearingPictureKeyString, None)
        top_bearing_image = currentPictures.get(topBearingPictureKeyString, None)
        nut_platewasher_image = currentPictures.get(nutAndPlateWasherPictureKeyString, None)

        base_images = [
            ("Hub+Bottom Bearing", hub_bottom_bearing_image),
            ("Top Bearing", top_bearing_image),
            ("Nut+Plate Washer", nut_platewasher_image)
        ]

        missing_images = [name for name, img in base_images if img is None]
        if missing_images:
            logBoth('logError', _src, f"CheckCap: Missing base images: {missing_images}, returning False", MessageType.ISSUE)
            return anImage, False

        try:
            # Get circular mask
            mask = CheckCap._get_circular_mask(anImage.shape, radius)

            # # =====================================================================
            # # STEP 1: Color Delta Analysis
            # # =====================================================================
            # delta_averages = []
            # step1_all_pass = True
            #
            # for name, base_image in base_images:
            #     _, delta_avg = CheckCap._compute_clamped_delta_grayscale(
            #         anImage, base_image, mask
            #     )
            #     delta_averages.append(delta_avg)
            #
            #     if modelName == DOST:
            #         if delta_avg < CheckCap.DELTA_THRESHOLD_DOST:
            #             step1_all_pass = step1_all_pass and False
            #             logBoth('logError', _src,
            #                 f"CheckCap Step1: {name} delta={delta_avg:.1f} < threshold={CheckCap.DELTA_THRESHOLD_DOST}",
            #                 MessageType.ISSUE)
            #         else:
            #             logBoth('logInfo', _src,
            #                 f"CheckCap Step1: {name} delta={delta_avg:.1f} >= threshold={CheckCap.DELTA_THRESHOLD_DOST}",
            #                 MessageType.SUCCESS)
            #     elif modelName == DOSTPLUS:
            #         if delta_avg < CheckCap.DELTA_THRESHOLD_DOSTPLUS:
            #             step1_all_pass = step1_all_pass and False
            #             logBoth('logError', _src,
            #                 f"CheckCap Step1: {name} delta={delta_avg:.1f} < threshold={CheckCap.DELTA_THRESHOLD_DOSTPLUS}",
            #                 MessageType.ISSUE)
            #         else:
            #             logBoth('logInfo', _src,
            #                 f"CheckCap Step1: {name} delta={delta_avg:.1f} >= threshold={CheckCap.DELTA_THRESHOLD_DOSTPLUS}",
            #                 MessageType.SUCCESS)
            #
            # step1_passed = step1_all_pass
            #
            # if step1_passed:
            #     logBoth('logInfo', _src, "CheckCap: Step 1 PASSED - All delta comparisons above threshold", MessageType.SUCCESS)
            # else:
            #     logBoth('logError', _src, "CheckCap: Step 1 FAILED - Not all delta comparisons above threshold", MessageType.ISSUE)

            # =====================================================================
            # STEP 1: Color Delta Analysis with Component-Specific Thresholds
            # =====================================================================
            delta_averages = []
            step1_all_pass = True

            thresholds = []
            # Define component-specific thresholds based on model
            if modelName == DOST:
                thresholds = [
                    CheckCap.DELTA_THRESHOLD_HUB_DOST,
                    CheckCap.DELTA_THRESHOLD_TOP_DOST,
                    CheckCap.DELTA_THRESHOLD_NUT_DOST
                ]
            elif modelName == DOSTPLUS:
                thresholds = [
                    CheckCap.DELTA_THRESHOLD_HUB_DOSTPLUS,
                    CheckCap.DELTA_THRESHOLD_TOP_DOSTPLUS,
                    CheckCap.DELTA_THRESHOLD_NUT_DOSTPLUS
                ]

            for (name, base_image), threshold in zip(base_images, thresholds):
                _, delta_avg = CheckCap._compute_clamped_delta_grayscale(
                    anImage, base_image, mask
                )
                delta_averages.append(delta_avg)

                if delta_avg < threshold:
                    step1_all_pass = False
                    logBoth('logError', _src,
                            f"CheckCap Step1: {name} delta={delta_avg:.1f} < threshold={threshold}",
                            MessageType.ISSUE)
                else:
                    logBoth('logInfo', _src,
                            f"CheckCap Step1: {name} delta={delta_avg:.1f} >= threshold={threshold}",
                            MessageType.SUCCESS)

            step1_passed = step1_all_pass

            if step1_passed:
                logBoth('logInfo', _src, "CheckCap: Step 1 PASSED - All delta comparisons above threshold", MessageType.SUCCESS)
            else:
                logBoth('logError', _src, "CheckCap: Step 1 FAILED - Not all delta comparisons above threshold", MessageType.ISSUE)

            # =====================================================================
            # STEP 2: Cap Color Verification (R - B)
            # =====================================================================
            rb_average = CheckCap._compute_rb_difference(anImage, mask)

            step2_passed = False
            # Check if R - B is less than threshold
            if modelName == DOST:
                step2_passed = rb_average < CheckCap.RB_THRESHOLD_DOST
                if step2_passed:
                    logBoth('logInfo', _src,
                            f"CheckCap: Step 2 PASSED - R-B={rb_average:.1f} < threshold={CheckCap.RB_THRESHOLD_DOST}",
                            MessageType.SUCCESS)
                else:
                    logBoth('logError', _src,
                            f"CheckCap: Step 2 FAILED - R-B={rb_average:.1f} >= threshold={CheckCap.RB_THRESHOLD_DOST}",
                            MessageType.ISSUE)
            elif modelName == DOSTPLUS:
                step2_passed = rb_average > CheckCap.RB_THRESHOLD_DOSTPLUS
                if step2_passed:
                    logBoth('logInfo', _src,
                            f"CheckCap: Step 2 PASSED - R-B={rb_average:.1f} > threshold={CheckCap.RB_THRESHOLD_DOSTPLUS}",
                            MessageType.SUCCESS)
                else:
                    logBoth('logError', _src,
                            f"CheckCap: Step 2 FAILED - R-B={rb_average:.1f} <= threshold={CheckCap.RB_THRESHOLD_DOSTPLUS}",
                            MessageType.ISSUE)


            # =====================================================================
            # Final Decision
            # =====================================================================
            is_cap_present = step1_passed and step2_passed

            if is_cap_present:
                logBoth('logInfo', _src, "CheckCap: CAP DETECTED - Both steps passed", MessageType.SUCCESS)
            else:
                logBoth('logError', _src, "CheckCap: CAP NOT DETECTED - One or more steps failed", MessageType.ISSUE)

            # Create annotated output image
            annotated_image = CheckCap._create_annotated_image(
                anImage, is_cap_present, step1_passed, step2_passed,
                delta_averages, rb_average, radius
            )

            return annotated_image, is_cap_present

        except Exception as e:
            logBoth('logCritical', _src, f"CheckCap: Exception during detection: {e}", MessageType.PROBLEM)
            import traceback
            traceback.print_exc()
            return anImage, False

    @staticmethod
    def test(directory_path: str):
        """
        Test the CheckCap algorithm on images in the specified directory.

        Args:
            directory_path: Path to directory containing test images
        """
        GREEN = "\033[1;32m"
        RED = "\033[1;31m"
        YELLOW = "\033[1;33m"
        CYAN = "\033[1;36m"
        RESET = "\033[0m"

        print(f"{CYAN}{'=' * 80}{RESET}")
        print(f"{CYAN}CheckCap Test Suite{RESET}")
        print(f"{CYAN}{'=' * 80}{RESET}")
        print(f"\nDirectory: {directory_path}")
        print(f"Parameters:")
        print(f"  Center: ({CheckCap.CENTER_X}, {CheckCap.CENTER_Y})")
        if DOSTPLUS in directory_path:
            print("In DOSTPLUS path")
            print(f"  Radius DOSTPLUS: {CheckCap.RADIUS_DOSTPLUS}")
            print(f"  Delta Threshold: {CheckCap.DELTA_THRESHOLD_DOSTPLUS}")
            print(f"  R-B Threshold: {CheckCap.RB_THRESHOLD_DOSTPLUS}")
        else:
            print("In DOST path")
            print(f"  Radius DOST: {CheckCap.RADIUS_DOST}")
            print(f"  Delta Threshold: {CheckCap.DELTA_THRESHOLD_DOST}")
            print(f"  R-B Threshold: {CheckCap.RB_THRESHOLD_DOST}")


        # Find all PNG files
        all_files = glob.glob(os.path.join(directory_path, "*.png"))

        # Categorize files into lists
        list_cap = sorted([f for f in all_files if "Cap" in os.path.basename(f)])
        # Test against previous stage image
        # list_cap = sorted([f for f in all_files if "Nut" in os.path.basename(f)])
        list_hub_and_bottom_bearing = sorted(
            [f for f in all_files if "Hub_and" in os.path.basename(f) or "Hub and" in os.path.basename(f)])
        list_top_bearing = sorted([f for f in all_files if "Top" in os.path.basename(f)])
        list_nut_and_plate_washer = sorted([f for f in all_files if "Nut" in os.path.basename(f)])

        print(f"\n{YELLOW}Found files:{RESET}")
        print(f"  Cap: {len(list_cap)}")
        print(f"  Hub and Bottom Bearing: {len(list_hub_and_bottom_bearing)}")
        print(f"  Top Bearing: {len(list_top_bearing)}")
        print(f"  Nut and Plate Washer: {len(list_nut_and_plate_washer)}")

        if not list_hub_and_bottom_bearing:
            print(f"{RED}No Hub and Bottom Bearing images found!{RESET}")
            return

        # Load all images
        print(f"\n{YELLOW}Loading images...{RESET}")

        cap_images = [(f, cv2.imread(f)) for f in list_cap]
        hub_images = [(f, cv2.imread(f)) for f in list_hub_and_bottom_bearing]
        top_images = [(f, cv2.imread(f)) for f in list_top_bearing]
        nut_images = [(f, cv2.imread(f)) for f in list_nut_and_plate_washer]

        # Use first image of each type as base for testing
        hub_base = hub_images[0][1] if hub_images else None
        top_base = top_images[0][1] if top_images else None
        nut_base = nut_images[0][1] if nut_images else None

        # =====================================================================
        # TEST 1: Cap images against all 3 base lists
        # =====================================================================
        if list_cap:
            print(f"\n{CYAN}{'=' * 80}{RESET}")
            print(f"{CYAN}TEST 1: Cap images (tested against Hub+Bottom, Top, Nut+Washer){RESET}")
            print(f"{CYAN}{'=' * 80}{RESET}")
            print(
                f"{YELLOW}Base images: {os.path.basename(hub_images[0][0])}, {os.path.basename(top_images[0][0])}, {os.path.basename(nut_images[0][0])}{RESET}\n")

            cap_pass = 0
            cap_fail = 0

            for cap_file, cap_img in cap_images:
                currentPictures = {
                    hubAndBottomBearingPictureKeyString: hub_base,
                    topBearingPictureKeyString: top_base,
                    nutAndPlateWasherPictureKeyString: nut_base
                }

                result = False
                if DOSTPLUS in directory_path:
                    _, result = CheckCap.checkCap(cap_img, currentPictures, "8201206$400112VA1C$11770$09.03.2025$C5211701$MEK$40Cr4 - B$1$SPDLASSY - KNULH$SNPL - MAT$")
                elif DOST in directory_path:
                    _, result = CheckCap.checkCap(cap_img, currentPictures, DOST)

                if result:
                    cap_pass += 1
                    print(f"  {os.path.basename(cap_file):45s} {GREEN}Cap Present{RESET}")
                else:
                    cap_fail += 1
                    print(f"  {os.path.basename(cap_file):45s} {RED}Cap Not Present{RESET}")

            print(f"\n  Summary: {GREEN}{cap_pass} Cap Present{RESET}, {RED}{cap_fail} Cap Not Present{RESET}")

        # =====================================================================
        # TEST 2: Nut+Plate Washer images against 2 base lists (Hub+Bottom, Top)
        # =====================================================================
        if list_nut_and_plate_washer and list_top_bearing:
            print(f"\n{CYAN}{'=' * 80}{RESET}")
            print(f"{CYAN}TEST 2: Nut+Plate Washer images (tested against Hub+Bottom, Top){RESET}")
            print(f"{CYAN}{'=' * 80}{RESET}")
            print(
                f"{YELLOW}Base images: {os.path.basename(hub_images[0][0])}, {os.path.basename(top_images[0][0])}{RESET}\n")

            nut_pass = 0
            nut_fail = 0

            for nut_file, nut_img in nut_images:
                currentPictures = {
                    hubAndBottomBearingPictureKeyString: hub_base,
                    topBearingPictureKeyString: top_base,
                    nutAndPlateWasherPictureKeyString: nut_base  # Use same nut base as reference
                }

                result = False
                if DOSTPLUS in directory_path:
                    _, result = CheckCap.checkCap(nut_img, currentPictures,
                                                  "8201206$400112VA1C$11770$09.03.2025$C5211701$MEK$40Cr4 - B$1$SPDLASSY - KNULH$SNPL - MAT$")
                elif DOST in directory_path:
                    _, result = CheckCap.checkCap(nut_img, currentPictures, "DOST")

                if result:
                    nut_pass += 1
                    print(f"  {os.path.basename(nut_file):45s} {GREEN}Cap Present{RESET}")
                else:
                    nut_fail += 1
                    print(f"  {os.path.basename(nut_file):45s} {RED}Cap Not Present{RESET}")

            print(f"\n  Summary: {GREEN}{nut_pass} Cap Present{RESET}, {RED}{nut_fail} Cap Not Present{RESET}")

        # =====================================================================
        # TEST 3: Top Bearing images against 1 base list (Hub+Bottom)
        # =====================================================================
        if list_top_bearing:
            print(f"\n{CYAN}{'=' * 80}{RESET}")
            print(f"{CYAN}TEST 3: Top Bearing images (tested against Hub+Bottom){RESET}")
            print(f"{CYAN}{'=' * 80}{RESET}")
            print(f"{YELLOW}Base image: {os.path.basename(hub_images[0][0])}{RESET}\n")

            top_pass = 0
            top_fail = 0

            for top_file, top_img in top_images:
                currentPictures = {
                    hubAndBottomBearingPictureKeyString: hub_base,
                    topBearingPictureKeyString: top_base,  # Use same top base as reference
                    nutAndPlateWasherPictureKeyString: nut_base  # Use same nut base as reference
                }

                if DOSTPLUS in directory_path:
                    _, result = CheckCap.checkCap(top_img, currentPictures,
                                                  "8201206$400112VA1C$11770$09.03.2025$C5211701$MEK$40Cr4 - B$1$SPDLASSY - KNULH$SNPL - MAT$")
                elif DOST in directory_path:
                    _, result = CheckCap.checkCap(top_img, currentPictures, "DOST")

                if result:
                    top_pass += 1
                    print(f"  {os.path.basename(top_file):45s} {GREEN}Cap Present{RESET}")
                else:
                    top_fail += 1
                    print(f"  {os.path.basename(top_file):45s} {RED}Cap Not Present{RESET}")

            print(f"\n  Summary: {GREEN}{top_pass} Cap Present{RESET}, {RED}{top_fail} Cap Not Present{RESET}")

        # =====================================================================
        # FINAL SUMMARY
        # =====================================================================
        print(f"\n{CYAN}{'=' * 80}{RESET}")
        print(f"{CYAN}FINAL SUMMARY{RESET}")
        print(f"{CYAN}{'=' * 80}{RESET}")

        if list_cap:
            print(f"  Cap images:              {cap_pass}/{len(list_cap)} detected as Cap Present")
        if list_nut_and_plate_washer:
            print(f"  Nut+Plate Washer images: {nut_pass}/{len(list_nut_and_plate_washer)} detected as Cap Present")
        if list_top_bearing:
            print(f"  Top Bearing images:      {top_pass}/{len(list_top_bearing)} detected as Cap Present")


# if __name__ == "__main__":
#     import sys
#
#     if len(sys.argv) > 1:
#         CheckCap.test(sys.argv[1])
#     else:
#         CheckCap.test("C:/AutoCompanyImages/DOSTPLUS/LHS")