"""
ModelManager.py - Singleton manager for shared MobileSAM and YOLO models.

This ensures only ONE set of models is loaded into GPU memory,
shared across CheckBunk, CheckHubAndBottomBearing, and CheckNutAndPlateWasher.

GPU Memory Savings:
- BEFORE: 3 separate model sets = ~9-12 GB GPU memory
- AFTER: 1 shared model set = ~3-4 GB GPU memory
- SAVINGS: ~6-8 GB!

=================================================
Recommended Standardized Pattern
=================================================

from camera.ModelManager import ModelManager

class MySegmenter:
    def __init__(self):
        # 1. Get ModelManager singleton
        self.model_manager = ModelManager.get_instance()

        # 2. Get device
        self.device = self.model_manager.get_device()
        print(f"Using device: {self.device}")

        # 3. Get shared SAM predictor
        self.sam_predictor = self.model_manager.get_sam_predictor()

        # 4. Get shared YOLO model
        self.yolo_model = self.model_manager.get_yolo_model()

        # 5. Create mask generator with shared models
        self.mask_generator = MobileSAMv2AutomaticMaskGenerator(
            sam_predictor=self.sam_predictor,
            yolo_model=self.yolo_model,
            ...
        )

=================================================
Testing Verification
=================================================

# Test in Python console or test script:
from camera.ModelManager import ModelManager

# Create multiple instances
mm1 = ModelManager.get_instance()
mm2 = ModelManager.get_instance()

# Verify same instance
print(f"Same instance: {mm1 is mm2}")  # Should print: True
print(f"ID mm1: {id(mm1)}")
print(f"ID mm2: {id(mm2)}")  # Should be same as mm1

# Load models once
mm1.load_models()

# Verify models are shared
print(f"Same SAM: {mm1.sam_model is mm2.sam_model}")  # Should print: True
print(f"Same YOLO: {mm1.yolo_model is mm2.yolo_model}")  # Should print: True

=================================================
Memory Verification
=================================================

import torch

# Before creating any segmenters
torch.cuda.reset_peak_memory_stats()

# Create all three segmenters
from camera.BunkSegmenter import CheckBunk
from camera.HubAndBearingSegmenter import CheckHubAndBottomBearing
from camera.HexagonNutDetector import NutDetector

bunk = CheckBunk()
hub = CheckHubAndBottomBearing(mobile_sam_path="...", yolo_path="...")
nut = NutDetector()

# Check memory
allocated = torch.cuda.memory_allocated() / 1024**3
print(f"GPU Memory Allocated: {allocated:.2f} GB")
# Should be ~3.3-3.5 GB, not 9-12 GB

"""

# ============================================================================
# NUITKA COMPATIBILITY PATCH - MUST BE FIRST!
# ============================================================================
# Fix for "TypeError: Plain typing.Self is not valid as type argument"
# This occurs when Nuitka tries to freeze PyTorch/Ultralytics imports
import sys
import threading
import typing

# Patch typing.Self for Python < 3.11 or Nuitka compatibility
if not hasattr(typing, 'Self'):
    # Python < 3.11: Add Self as TypeVar
    typing.Self = typing.TypeVar('Self')
    print("✓ Added typing.Self compatibility shim")
else:
    # Python >= 3.11: Ensure Self works with Nuitka's frozen imports
    # Check if we're in a frozen/compiled environment (Nuitka)
    if getattr(sys, 'frozen', False) or hasattr(sys, '__compiled__'):
        # In Nuitka, replace typing.Self with a simple TypeVar to avoid _type_check errors
        _SelfTypeVar = typing.TypeVar('_SelfTypeVar')
        typing.Self = _SelfTypeVar
        print("✓ Patched typing.Self for Nuitka frozen environment")

# Additional Nuitka compatibility: Prevent typing module errors during frozen imports
if getattr(sys, 'frozen', False) or hasattr(sys, '__compiled__'):
    # Monkey-patch typing._type_check to be more lenient
    _original_type_check = typing._type_check

    def _lenient_type_check(arg, msg, is_argument=True, module=None, *, allow_special_forms=False):
        """More lenient type checking for Nuitka frozen environment."""
        try:
            return _original_type_check(arg, msg, is_argument, module, allow_special_forms=allow_special_forms)
        except TypeError as e:
            if 'typing.Self' in str(e) or 'Self' in str(arg):
                # Allow Self to pass through without strict type checking
                return arg
            raise

    typing._type_check = _lenient_type_check
    print("✓ Patched typing._type_check for Nuitka compatibility")

# ============================================================================

import os
import warnings
import torch
from typing import Optional

from BaseUtils import get_project_root

from logutils.SlaveLoggers import *
from logutils.Logger import *
from logutils.AbstractSlaveLogger import *

# --- Add MobileSAM to path ---
_PROJECT_ROOT = get_project_root()
_MOBILESAM_DIR = os.path.join(_PROJECT_ROOT, "models", "MobileSAM")
if os.path.exists(_MOBILESAM_DIR) and _MOBILESAM_DIR not in sys.path:
    sys.path.append(_MOBILESAM_DIR)

# Suppress warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="timm")
warnings.filterwarnings("ignore", category=UserWarning, message="Overwriting .* in registry")

# Torch monkeypatch for PyTorch 2.6+
_original_torch_load = torch.load

def _patched_torch_load(f, map_location=None, pickle_module=None, *, weights_only=None, mmap=None, **kwargs):
    """Patched torch.load that forces weights_only=False for trusted checkpoints."""
    return _original_torch_load(
        f, map_location=map_location, pickle_module=pickle_module,
        weights_only=False, mmap=mmap, **kwargs
    )


torch.load = _patched_torch_load
print("✓ torch.load patched to use weights_only=False")
print("=" * 70)
# Load YOLO
from ultralytics import YOLO

# PyTorch 2.6+ safe globals
try:
    if hasattr(torch.serialization, "add_safe_globals"):
        safe_classes = [
            torch.nn.modules.container.Sequential,
            torch.nn.modules.container.ModuleList,
            torch.nn.modules.container.ModuleDict,
        ]
        try:
            from ultralytics.nn.tasks import (
                SegmentationModel, DetectionModel, ClassificationModel,
                PoseModel, OBBModel
            )

            safe_classes.extend([
                SegmentationModel, DetectionModel, ClassificationModel,
                PoseModel, OBBModel,
            ])
        except ImportError:
            try:
                from ultralytics.nn.tasks import SegmentationModel, DetectionModel

                safe_classes.extend([SegmentationModel, DetectionModel])
            except ImportError:
                pass

        torch.serialization.add_safe_globals(safe_classes)
except (ImportError, AttributeError):
    pass

try:
    # Load MobileSAM
    from mobile_sam import sam_model_registry, SamPredictor
    MOBILESAM_AVAILABLE = True
    print("✓ MobileSAM loaded")
except ImportError as e:
    MOBILESAM_AVAILABLE = False
    print(f"✗ Failed to load MobileSAM: {e}")

class ModelManager:
    """
    Singleton manager for shared MobileSAM and YOLO models.

    All checker classes (CheckBunk, CheckHub, CheckNut) get models from here.
    This ensures only ONE set of models in GPU memory.

    Usage:
        # In BunkSegmenter, HubAndBearingSegmenter, HexagonNutDetector:
        model_manager = ModelManager.get_instance()
        sam_predictor = model_manager.get_sam_predictor()
        yolo_model = model_manager.get_yolo_model()
    """

    _instance: Optional['ModelManager'] = None
    _initialized = False
    _load_lock = threading.Lock()
    logSource: str = ""

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if ModelManager._initialized:
            return

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        ModelManager.logSource = getFullyQualifiedName(__file__, __class__)
        logBoth('logInfo', ModelManager.logSource, f"Using device: {self.device}", Logger.GENERAL)

        # Model paths
        self.mobile_sam_path = os.path.join(
            _PROJECT_ROOT, "models", "MobileSAM", "weights", "mobile_sam.pt"
        )
        self.yolo_path = os.path.join(
            _PROJECT_ROOT, "models", "MobileSAM", "MobileSAMv2", "weight", "ObjectAwareModel.pt"
        )

        # Models (loaded lazily)
        self.sam_model = None
        self.sam_predictor = None
        self.yolo_model = None

        ModelManager._initialized = True

    @classmethod
    def get_instance(cls) -> 'ModelManager':
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = ModelManager()
        return cls._instance

    def load_models(self):
        """Load models if not already loaded (thread-safe lazy loading)."""
        with self._load_lock:
            if self.sam_model is not None and self.yolo_model is not None:
                logBoth('logInfo', ModelManager.logSource, "Models already loaded", Logger.GENERAL)
                return

            if not MOBILESAM_AVAILABLE:
                raise ImportError(
                    "mobile_sam module not available. "
                    "Ensure MobileSAM is installed and added to sys.path."
                )

            logBoth('logInfo', ModelManager.logSource, "Loading MobileSAM and YOLO models...", Logger.GENERAL)

            # Verify model files exist
            if not os.path.exists(self.mobile_sam_path):
                raise FileNotFoundError(f"MobileSAM not found: {self.mobile_sam_path}")
            if not os.path.exists(self.yolo_path):
                raise FileNotFoundError(f"YOLO not found: {self.yolo_path}")

            try:
                self.sam_model = sam_model_registry["vit_t"](checkpoint=self.mobile_sam_path)
                self.sam_model.to(device=self.device)
                self.sam_model.eval()

                # Create sam_predictor
                self.sam_predictor = SamPredictor(self.sam_model)

            except Exception as e:
                logBoth('logTakeAction', ModelManager.logSource, f"Failed to load MobileSAM: {e}", Logger.PROBLEM)
                raise

            # Enable TF32 for Ampere GPUs
            if self.device.type == "cuda":
                if torch.cuda.get_device_properties(0).major >= 8:
                    torch.backends.cuda.matmul.allow_tf32 = True
                    torch.backends.cudnn.allow_tf32 = True
                    logBoth('logInfo', ModelManager.logSource, "Enabled TF32 for Ampere GPU", Logger.SUCCESS)

            try:

                self.yolo_model = YOLO(self.yolo_path, task='detect')
                self._force_yolo_detection_mode(self.yolo_model)
                self.yolo_model.to(self.device)
                logBoth('logInfo', ModelManager.logSource, "YOLO loaded", Logger.SUCCESS)

            except Exception as e:
                logBoth('logTakeAction', ModelManager.logSource, f"Failed to load YOLO: {e}", Logger.PROBLEM)
                raise

            logBoth('logInfo', ModelManager.logSource, "All models loaded successfully", Logger.SUCCESS)

    def _force_yolo_detection_mode(self, yolo_model):
        """Force YOLO model to detection mode (same as BunkSegmenter)."""
        try:
            logBoth('logInfo', ModelManager.logSource, "Forcing YOLO to detection mode...", Logger.GENERAL)

            # Step 1: Patch model head
            if hasattr(yolo_model, 'model') and hasattr(yolo_model.model, 'model'):
                model_layers = yolo_model.model.model

                head = None
                head_index = None
                for i, layer in enumerate(model_layers):
                    if hasattr(layer, '__class__'):
                        class_name = layer.__class__.__name__
                        if 'Segment' in class_name or 'Detect' in class_name:
                            head = layer
                            head_index = i
                            break

                if head and 'Segment' in head.__class__.__name__ and not hasattr(head, 'proto'):
                    from ultralytics.nn.modules.head import Detect
                    import types

                    detect_forward = Detect.forward
                    head.forward = types.MethodType(detect_forward, head)
                    head._patched_for_detection = True
                    logBoth('logInfo', ModelManager.logSource, "Replaced forward with Detect.forward()", Logger.SUCCESS)

            # Step 2: Force task in overrides
            if hasattr(yolo_model, 'overrides'):
                yolo_model.overrides['task'] = 'detect'
                logBoth('logInfo', ModelManager.logSource, "Set task='detect' in overrides", Logger.SUCCESS)

            # Step 3: Replace sam_predictor
            if hasattr(yolo_model, 'sam_predictor') and yolo_model.sam_predictor is not None:
                from ultralytics.models.yolo.detect import DetectPredictor

                old_predictor = yolo_model.sam_predictor
                new_predictor = DetectPredictor(overrides=yolo_model.overrides)

                if hasattr(old_predictor, 'model'):
                    new_predictor.model = old_predictor.model
                if hasattr(old_predictor, 'args'):
                    new_predictor.args = old_predictor.args
                if hasattr(old_predictor, 'device'):
                    new_predictor.device = old_predictor.device

                yolo_model.sam_predictor = new_predictor
                logBoth('logInfo', ModelManager.logSource, "Replaced sam_predictor with DetectPredictor", Logger.SUCCESS)

            # Step 4: Set model.task
            if hasattr(yolo_model, 'task'):
                yolo_model.task = 'detect'
                logBoth('logInfo', ModelManager.logSource, "Set model.task='detect'", Logger.SUCCESS)

            # Step 5: Patch checkpoint metadata
            if hasattr(yolo_model, 'ckpt') and yolo_model.ckpt:
                if isinstance(yolo_model.ckpt, dict) and 'train_args' in yolo_model.ckpt:
                    if hasattr(yolo_model.ckpt['train_args'], 'task'):
                        yolo_model.ckpt['train_args'].task = 'detect'
                        logBoth('logInfo', ModelManager.logSource, "Updated checkpoint metadata task", Logger.SUCCESS)

            logBoth('logInfo', ModelManager.logSource, "Successfully forced detection mode", Logger.SUCCESS)

        except Exception as e:
            logBoth('logTakeNote', ModelManager.logSource, f"Warning during YOLO patching: {e}", Logger.RISK)
            import traceback
            traceback.print_exc()

    def get_sam_predictor(self):
        """Get the SAM sam_predictor (loads models if needed)."""
        if self.sam_predictor is None:
            self.load_models()
        return self.sam_predictor

    def get_yolo_model(self):
        """Get the YOLO model (loads models if needed)."""
        if self.yolo_model is None:
            self.load_models()
        return self.yolo_model

    def get_device(self):
        """Get the device (cuda/cpu)."""
        return self.device

    def get_sam_model(self):
        """Get the SAM model for creating custom predictors (thread-safe)."""
        if self.sam_model is None:
            self.load_models()
        return self.sam_model

# =============================================================================
# TESTING
# =============================================================================

# if __name__ == "__main__":
#     print("=" * 70)
#     print("Testing ModelManager Singleton")
#     print("=" * 70)
#
#     # Create first instance
#     manager1 = ModelManager.get_instance()
#     print(f"\nCreated manager1: {id(manager1)}")
#
#     # Create second instance
#     manager2 = ModelManager.get_instance()
#     print(f"Created manager2: {id(manager2)}")
#
#     # Verify singleton
#     print(f"\nSame instance? {manager1 is manager2}")
#     assert manager1 is manager2, "ModelManager is not a singleton!"
#
#     # Load models
#     print("\n" + "=" * 70)
#     print("Loading Models...")
#     print("=" * 70)
#     manager1.load_models()
#
#     # Verify models loaded
#     print(f"\nSAM loaded: {manager1.sam_model is not None}")
#     print(f"YOLO loaded: {manager1.yolo_model is not None}")
#     print(f"Device: {manager1.device}")
#
#     # Test that second instance has same models
#     print(f"\nSame SAM model: {manager1.sam_model is manager2.sam_model}")
#     print(f"Same YOLO model: {manager1.yolo_model is manager2.yolo_model}")
#
#     print("\n" + "=" * 70)
#     print("✓ ModelManager test complete!")
#     print("=" * 70)