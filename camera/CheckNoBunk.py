"""
CheckNoBunk - Detects presence of No Bunk state using HexagonNutDetector.

New Detection Method:
    1. Use HexagonNutDetector to detect nut and get nut mask
    2. Return nut detection result immediately (no washer check needed)
    3. Annotate image with nut outlined in green

Returns:
    - Annotated image with nut in green
    - True if nut detected, False otherwise
"""

import cv2
import numpy as np
from typing import Dict, Tuple, Optional
import sys

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
        colours = {
            'logInfo': '\033[1;32m',
            'logError': '\033[1;31m',
            'logWarning': '\033[1;33m',
            'logDebug': '\033[1;34m',
            'logCritical': '\033[1;31m',
        }
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


class CheckNoBunk:
    """
    Checks for the presence of No Bunk state using HexagonNutDetector.
    No Bunk = Nut is present (without washer check).
    """

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
            logBoth('logDebug', _src, "[CheckNoBunk] Initializing NutDetector...", MessageType.GENERAL)
            cls._nut_detector = NutDetector()
            cls._detector_initialized = True
            logBoth('logInfo', _src, "[CheckNoBunk] NutDetector initialized", MessageType.SUCCESS)
        return cls._nut_detector

    @staticmethod
    def checkNoBunk(
            anImage: np.ndarray,
            currentPictures: Dict[str, np.ndarray | None] = None,
            componentQRCode: str = DOST,
            gamma: float = 2.0
    ) -> Tuple[np.ndarray | None, bool]:
        """
        Check for the presence of No Bunk state using HexagonNutDetector.

        No Bunk state = Nut is present (detected by HexagonNutDetector).
        No washer check is performed in this step.

        Args:
            anImage: Current camera image (No Bunk image, BGR format)
            currentPictures: Dict containing previously captured images (unused)
            componentQRCode: Component QR code
            gamma: Unused (kept for signature compatibility)

        Returns:
            Tuple of (annotated_image, nut_present)
        """
        _src = getFullyQualifiedName(__file__, CheckNoBunk)

        logBoth('logDebug', _src, "="*80, MessageType.GENERAL)
        logBoth('logDebug', _src, "[CheckNoBunk] NO BUNK DETECTION START", MessageType.GENERAL)
        logBoth('logDebug', _src, "="*80, MessageType.GENERAL)

        # =====================================================================
        # VALIDATION
        # =====================================================================
        if anImage is None:
            logBoth('logError', _src, "[CheckNoBunk] anImage is None", MessageType.ISSUE)
            return anImage, False

        if componentQRCode is None:
            logBoth('logError', _src, "[CheckNoBunk] componentQRCode is None", MessageType.ISSUE)
            return anImage, False

        # Get component type
        # try:
        #     modelName, lhs_rhs, _ = getModel_LHSRHS_AndTonnage(componentQRCode)
        #     if modelName == UNKNOWN:
        #         modelName = "DOST"
        # except:
        #     modelName = "DOST"
        #     lhs_rhs = "LHS"

        # =====================================================================
        # DETECT NUT USING HexagonNutDetector
        # =====================================================================
        logBoth('logDebug', _src, "[CheckNoBunk] Detecting nut using HexagonNutDetector...", MessageType.GENERAL)

        detector = CheckNoBunk._get_nut_detector()
        image_rgb = cv2.cvtColor(anImage, cv2.COLOR_BGR2RGB)

        nut_found, nut_result = detector.detect_nut_in_image(
            image_rgb=image_rgb,
            center=CheckNoBunk.NUT_DETECTION_CENTER,
            outer_radius=CheckNoBunk.NUT_DETECTION_RADIUS,
            inner_radius=0,
            image_id="no_bunk_check"
        )

        # =====================================================================
        # COMPUTE CROP CENTER AND HELPER
        # =====================================================================
        if nut_found:
            _hcx, _hcy = nut_result.get('hex_center', (CheckNoBunk.NUT_DETECTION_RADIUS,
                                                        CheckNoBunk.NUT_DETECTION_RADIUS))
            _offset_x = CheckNoBunk.NUT_DETECTION_CENTER[0] - CheckNoBunk.NUT_DETECTION_RADIUS
            _offset_y = CheckNoBunk.NUT_DETECTION_CENTER[1] - CheckNoBunk.NUT_DETECTION_RADIUS
            hex_center_original = (_hcx + _offset_x, _hcy + _offset_y)
        else:
            hex_center_original = CheckNoBunk.NUT_DETECTION_CENTER

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
        # RETURN RESULT
        # =====================================================================
        if nut_found:
            logBoth('logInfo', _src, "[CheckNoBunk] ✓ NUT DETECTED - No Bunk State Present", MessageType.SUCCESS)
            logBoth('logDebug', _src, "="*80, MessageType.GENERAL)
            # Return annotated image with green nut outline
            annotated = _crop240(nut_result.get('annotated_original', anImage))
            return annotated, True
        else:
            logBoth('logError', _src, "[CheckNoBunk] ✗ NUT NOT DETECTED - No Bunk State Absent", MessageType.ISSUE)
            logBoth('logDebug', _src, "="*80, MessageType.GENERAL)
            # Return annotated image (or original)
            annotated = _crop240(nut_result.get('annotated_original', anImage))
            return annotated, False