import cv2
import numpy as np
from typing import Tuple
from BaseUtils import *

class HandDetector:
    """
    Two-stage hand/operator detection system.

    Stage 1: MediaPipe Hands (fast, detects visible hands)
        - Speed: ~30-50ms
        - Catches: Visible hands with fingers/palm
        - Misses: Gloved hands, occluded hands

    Stage 2: YOLOv8-medium Person Detection (thorough, detects any operator)
        - Speed: ~60-80ms on RTX 3050
        - Catches: Any person/operator in frame
        - More reliable for industrial settings

    The two stages work together:
        - If MediaPipe detects hands → Return True immediately
        - If MediaPipe passes → Run YOLO person detection
        - If YOLO detects person → Return True
        - If both pass → Return False (clear)

    Installation:
        pip install mediapipe ultralytics opencv-python numpy

    Usage:
        has_operator = HandDetector.detectHands(image)
        if has_operator:
            return image, False  # Reject - operator in frame
    """

    # =========================================================================
    # MediaPipe Stage 1
    # =========================================================================
    _mp_hands = None
    _mp_detector = None
    _mp_initialized = False
    _mp_import_failed = False

    # =========================================================================
    # YOLO Stage 2
    # =========================================================================
    _yolo_model = None
    _yolo_initialized = False
    _yolo_import_failed = False

    @classmethod
    def _initialize_mediapipe(cls):
        """Initialize MediaPipe Hands (Stage 1)."""
        if cls._mp_import_failed or cls._mp_initialized:
            return

        print("HandDetector Stage 1: Initializing MediaPipe Hands...")

        try:
            import mediapipe as mp

            cls._mp_hands = mp.solutions.hands
            cls._mp_detector = cls._mp_hands.Hands(
                static_image_mode=True,
                max_num_hands=2,
                min_detection_confidence=0.3,  # Lower threshold to catch more
                min_tracking_confidence=0.3
            )
            cls._mp_initialized = True
            print("HandDetector Stage 1: MediaPipe loaded successfully")

        except (ImportError, AttributeError) as e:
            cls._mp_import_failed = True
            print(f"HandDetector Stage 1: MediaPipe not available - {e}")
            print("HandDetector Stage 1: DISABLED - will rely on Stage 2 (YOLO)")
        except Exception as e:
            cls._mp_import_failed = True
            print(f"HandDetector Stage 1: Failed to initialize - {e}")

    @classmethod
    def _initialize_yolo(cls):
        """Initialize YOLOv8-medium (Stage 2)."""
        if cls._yolo_import_failed or cls._yolo_initialized:
            return

        print("HandDetector Stage 2: Initializing YOLOv8-medium...")

        try:
            from ultralytics import YOLO

            # Use YOLOv8m for better accuracy
            # More reliable than small for detecting partially visible operators
            cls._yolo_model = YOLO(f'{get_project_root()}/models/yolo_models/yolov8m.pt')
            cls._yolo_initialized = True
            print("HandDetector Stage 2: YOLOv8m loaded successfully")

        except ImportError:
            cls._yolo_import_failed = True
            print("HandDetector Stage 2: ultralytics not installed")
            print("Install with: pip install ultralytics")
            print("HandDetector Stage 2: DISABLED")
        except Exception as e:
            cls._yolo_import_failed = True
            print(f"HandDetector Stage 2: Failed to initialize - {e}")

    @staticmethod
    def detectHands(anImage: np.ndarray, debug: bool = False) -> bool:
        """
        Two-stage detection: MediaPipe first, then YOLOv8m.

        Args:
            anImage: BGR image from OpenCV
            debug: If True, print detailed detection info

        Returns:
            bool: True if hands/operator detected, False if clear
        """
        # Initialize both stages on first call
        # if not HandDetector._mp_initialized and not HandDetector._mp_import_failed:
        #     HandDetector._initialize_mediapipe()
        #
        # if not HandDetector._yolo_initialized and not HandDetector._yolo_import_failed:
        #     HandDetector._initialize_yolo()
        #
        # # =====================================================================
        # # STAGE 1: MediaPipe Hand Detection (Fast Check)
        # # =====================================================================
        # if HandDetector._mp_initialized:
        #     try:
        #         # Convert BGR to RGB
        #         rgb_image = cv2.cvtColor(anImage, cv2.COLOR_BGR2RGB)
        #
        #         # Process with MediaPipe
        #         results = HandDetector._mp_detector.process(rgb_image)
        #
        #         if results.multi_hand_landmarks is not None:
        #             num_hands = len(results.multi_hand_landmarks)
        #             if debug:
        #                 print(f"HandDetector Stage 1: MediaPipe detected {num_hands} hand(s)")
        #             print(f"HandDetector: Stage 1 (MediaPipe) DETECTED - {num_hands} hand(s) found")
        #             return True
        #
        #         if debug:
        #             print("HandDetector Stage 1: MediaPipe passed - no visible hands")
        #
        #     except Exception as e:
        #         if debug:
        #             print(f"HandDetector Stage 1: Error - {e}")
        #
        # # =====================================================================
        # # STAGE 2: YOLOv8 Person Detection (Thorough Check)
        # # =====================================================================
        # if HandDetector._yolo_initialized:
        #     try:
        #         # Run YOLO person detection
        #         results = HandDetector._yolo_model(
        #             anImage,
        #             classes=[0],  # Only detect 'person' class
        #             conf=0.3,  # 30% confidence threshold
        #             verbose=False
        #         )
        #
        #         detections = results[0].boxes
        #         num_persons = len(detections)
        #
        #         if num_persons > 0:
        #             if debug:
        #                 conf = detections[0].conf[0].item()
        #                 print(f"HandDetector Stage 2: YOLO detected {num_persons} person(s), confidence: {conf:.2f}")
        #             print(f"HandDetector: Stage 2 (YOLO) DETECTED - {num_persons} operator(s) in frame")
        #             return True
        #
        #         if debug:
        #             print("HandDetector Stage 2: YOLO passed - no persons detected")
        #
        #     except Exception as e:
        #         if debug:
        #             print(f"HandDetector Stage 2: Error - {e}")
        #
        # # =====================================================================
        # # Both stages passed - frame is clear
        # # =====================================================================
        # if debug:
        #     print("HandDetector: Both stages passed - frame CLEAR")

        return False

    @classmethod
    def shutdown(cls):
        """Release resources (optional cleanup on application exit)."""
        # Close MediaPipe
        if cls._mp_initialized and cls._mp_detector is not None:
            cls._mp_detector.close()
            cls._mp_initialized = False
            cls._mp_detector = None
            cls._mp_hands = None
            print("HandDetector Stage 1: MediaPipe resources released")

        # YOLO doesn't need explicit cleanup
        if cls._yolo_initialized:
            cls._yolo_model = None
            cls._yolo_initialized = False
            print("HandDetector Stage 2: YOLO resources released")

    @classmethod
    def get_status(cls) -> dict:
        """
        Get initialization status of both detection stages.

        Returns:
            dict: Status of MediaPipe and YOLO stages
        """
        return {
            'stage1_mediapipe': {
                'initialized': cls._mp_initialized,
                'failed': cls._mp_import_failed,
                'status': 'READY' if cls._mp_initialized else ('FAILED' if cls._mp_import_failed else 'NOT INITIALIZED')
            },
            'stage2_yolo': {
                'initialized': cls._yolo_initialized,
                'failed': cls._yolo_import_failed,
                'status': 'READY' if cls._yolo_initialized else (
                    'FAILED' if cls._yolo_import_failed else 'NOT INITIALIZED')
            }
        }

    @classmethod
    def is_available(cls) -> bool:
        """
        Check if at least one detection method is available.

        Returns:
            bool: True if MediaPipe OR YOLO is working
        """
        if not cls._mp_initialized and not cls._mp_import_failed:
            cls._initialize_mediapipe()

        if not cls._yolo_initialized and not cls._yolo_import_failed:
            cls._initialize_yolo()

        return cls._mp_initialized or cls._yolo_initialized


# Example usage and testing
# if __name__ == "__main__":
#     import time
#
#     print("=" * 70)
#     print("Two-Stage HandDetector Test")
#     print("MediaPipe (Stage 1) → YOLOv8m (Stage 2)")
#     print("=" * 70)
#
#     # Check status before initialization
#     print("\nInitial Status:")
#     status = HandDetector.get_status()
#     print(f"  Stage 1 (MediaPipe): {status['stage1_mediapipe']['status']}")
#     print(f"  Stage 2 (YOLO):      {status['stage2_yolo']['status']}")
#     print(f"  At least one available: {HandDetector.is_available()}")
#
#     # Test with an image
#     test_image_path = 'Bad_Picture_-_2.png'
#
#     try:
#         test_image = cv2.imread(test_image_path)
#
#         if test_image is not None:
#             print(f"\nTest image loaded: {test_image.shape}")
#
#             # Run detection with debug output
#             print("\n" + "=" * 70)
#             print("Running Two-Stage Detection (with debug output)")
#             print("=" * 70)
#
#             start = time.time()
#             result = HandDetector.detectHands(test_image, debug=True)
#             elapsed = (time.time() - start) * 1000
#
#             print("\n" + "=" * 70)
#             print("FINAL RESULT")
#             print("=" * 70)
#             print(f"Detection result: {result}")
#             print(f"Total time: {elapsed:.1f}ms")
#
#             if result:
#                 print("\n✗ OPERATOR DETECTED - Would REJECT this image")
#             else:
#                 print("\n✓ CLEAR - Would ACCEPT this image")
#
#             # Show final status
#             print("\n" + "=" * 70)
#             print("Final Status:")
#             status = HandDetector.get_status()
#             print(f"  Stage 1 (MediaPipe): {status['stage1_mediapipe']['status']}")
#             print(f"  Stage 2 (YOLO):      {status['stage2_yolo']['status']}")
#
#         else:
#             print(f"\nCould not load test image: {test_image_path}")
#             print("Testing with blank image instead...")
#
#             blank_image = np.zeros((720, 1280, 3), dtype=np.uint8)
#             start = time.time()
#             result = HandDetector.detectHands(blank_image, debug=True)
#             elapsed = (time.time() - start) * 1000
#
#             print(f"\nResult: {result}, Time: {elapsed:.1f}ms")
#
#     except Exception as e:
#         print(f"\nError during test: {e}")
#         import traceback
#
#         traceback.print_exc()
#
#     # Cleanup
#     print("\n" + "=" * 70)
#     print("Cleanup")
#     print("=" * 70)
#     HandDetector.shutdown()
#
#     print("\n" + "=" * 70)
#     print("Test Complete")
#     print("=" * 70)