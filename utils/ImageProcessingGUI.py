"""
Enhanced Image Processing GUI with Tkinter

New Features:
- All ImageNormalisationWithMask methods with dropdowns and buttons
- Persistent pipeline that auto-applies to next/previous images
- Dynamic pipeline updates when user undoes or modifies
- Homomorphic filter uses the one from ImageNormalisationWithMask
- Split into two modules for better code organization

Features:
- File selection with next/prev navigation
- Background normalization (full and simple) with parameter controls
- Contrast normalization with parameter controls
- Gray normalization
- Rank filter with size and rank controls
- Unsharp masking with halfwidth and fraction controls
- Bilateral filter with d, sigmaColor, sigmaSpace controls
- Gamma correction with values from 0.5 to 6.0 in steps of 0.25
- Histogram equalization
- Otsu thresholding (global and local)
- Homomorphic filter for illumination normalization (from ImageNormalisationWithMask)
- Annular disk cropping with centerX, centerY, outer radius, inner radius inputs
- Before/After image display panels
- Processing pipeline with undo capability
- Pipeline persistence: auto-applies to next/previous images
- Pipeline save/load functionality
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import numpy as np
import cv2
import os
from typing import List, Tuple, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import copy

# Import image processing functions
from ImageNormalisationWithMask import (
    # Mask creation
    create_annular_mask,
    rgb2gray,
    ensure_float32,
    GAMMA_LUT,

    # Processing functions
    pixBackgroundNorm_masked,
    pixBackgroundNormSimple_masked,
    pixContrastNorm_masked,
    pixGrayNormalize_masked,
    pixRankFilterGray_masked,
    pixUnsharpMaskingGray_masked,
    pixGammaCorrection_masked,
    pixEqualizeHistogram_masked,
    homomorphic_filter_with_restoration_masked,
    bilateral_filter_masked,
    otsu_threshold_global,
    otsu_threshold_global_masked,
    otsu_threshold_local, otsu_threshold_local_masked,
    intrinsic_reflectance_separation_masked, clahe_masked, multi_scale_retinex_masked,
    single_scale_retinex_masked, homomorphic_filter_robust_masked, butterworth_homomorphic_filter_masked, restore_log,
    restore_root, restore_linear, restore_gamma_suppress_express,

    # NEW: LAB and CLAHE methods
    bgr_to_lab,
    lab_to_bgr,
    apply_gamma_to_lab_L,
    apply_clahe_to_lab_L,
    apply_clahe_to_bgr_channels,

    # NEW: Polar unwrap, localised block Otsu, flipover detection
    polar_unwrap,
    otsu_threshold_local_block,
    otsu_threshold_local_block_masked,
    find_flipover_row,
    relative_gamma_masked,
)




# =============================================================================
# WRAPPER FUNCTIONS FOR NEW METHODS
# =============================================================================

def restore_log_masked(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    gray = rgb2gray(image)
    gray = ensure_float32(gray)
    restored = restore_log(gray)
    result = gray.copy()
    result[mask] = restored[mask]
    return result.astype(np.uint8)

def restore_root_masked(image: np.ndarray, mask: np.ndarray, n: float = 2.0) -> np.ndarray:
    gray = rgb2gray(image)
    gray = ensure_float32(gray)
    restored = restore_root(gray, n=n)
    result = gray.copy()
    result[mask] = restored[mask]
    return result.astype(np.uint8)

def restore_linear_masked(image: np.ndarray, mask: np.ndarray, clip_percentile: float = 0.5) -> np.ndarray:
    gray = rgb2gray(image)
    gray = ensure_float32(gray)
    restored = restore_linear(gray, clip_percentile=clip_percentile)
    result = gray.copy()
    result[mask] = restored[mask]
    return result.astype(np.uint8)

def restore_gamma_suppress_masked(image: np.ndarray, mask: np.ndarray, gamma_bright: float = 2.0,
                                   gamma_dark: float = 0.5, final_restoration: str = 'linear',
                                   root_n: float = 2.0) -> np.ndarray:
    gray = rgb2gray(image)
    gray = ensure_float32(gray)
    restored = restore_gamma_suppress_express(gray, gamma_bright=gamma_bright, gamma_dark=gamma_dark,
                                               final_restoration=final_restoration, root_n=root_n)
    result = gray.copy()
    result[mask] = restored[mask]
    return result.astype(np.uint8)

def morphology_dilate_masked(image: np.ndarray, mask: np.ndarray, kernel_size: int = 5,
                             kernel_shape: str = 'ellipse') -> np.ndarray:
    gray = rgb2gray(image)
    if gray.dtype != np.uint8:
        gray = ensure_float32(gray).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE if kernel_shape == 'ellipse' else cv2.MORPH_RECT,
                                       (kernel_size, kernel_size))
    dilated = cv2.dilate(gray, kernel)
    result = gray.copy()
    result[mask] = dilated[mask]
    return result

def morphology_erode_masked(image: np.ndarray, mask: np.ndarray, kernel_size: int = 5,
                            kernel_shape: str = 'ellipse') -> np.ndarray:
    gray = rgb2gray(image)
    if gray.dtype != np.uint8:
        gray = ensure_float32(gray).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE if kernel_shape == 'ellipse' else cv2.MORPH_RECT,
                                       (kernel_size, kernel_size))
    eroded = cv2.erode(gray, kernel)
    result = gray.copy()
    result[mask] = eroded[mask]
    return result

def morphology_open_masked(image: np.ndarray, mask: np.ndarray, kernel_size: int = 5,
                           kernel_shape: str = 'ellipse') -> np.ndarray:
    gray = rgb2gray(image)
    if gray.dtype != np.uint8:
        gray = ensure_float32(gray).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE if kernel_shape == 'ellipse' else cv2.MORPH_RECT,
                                       (kernel_size, kernel_size))
    opened = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel)
    result = gray.copy()
    result[mask] = opened[mask]
    return result

def morphology_close_masked(image: np.ndarray, mask: np.ndarray, kernel_size: int = 5,
                            kernel_shape: str = 'ellipse') -> np.ndarray:
    gray = rgb2gray(image)
    if gray.dtype != np.uint8:
        gray = ensure_float32(gray).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE if kernel_shape == 'ellipse' else cv2.MORPH_RECT,
                                       (kernel_size, kernel_size))
    closed = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
    result = gray.copy()
    result[mask] = closed[mask]
    return result

class ProcessingType(Enum):
    LOAD = "Load Image"
    BACKGROUND_NORM = "Background Normalization"
    BACKGROUND_NORM_SIMPLE = "Background Normalization Simple"
    CONTRAST_NORM = "Contrast Normalization"
    GRAY_NORMALIZE = "Gray Normalization"
    RANK_FILTER = "Rank Filter"
    UNSHARP_MASK = "Unsharp Masking"
    BILATERAL = "Bilateral Filter"
    GAMMA = "Gamma Correction"
    CROP_ANNULAR = "Annular Mask"
    HISTOGRAM_EQ = "Histogram Equalization"
    OTSU_GLOBAL = "Otsu Global"
    OTSU_LOCAL = "Otsu Local (Adaptive)"
    HOMOMORPHIC = "Homomorphic Filter"

    # NEW: Additional homomorphic filters
    HOMOMORPHIC_BUTTERWORTH = "Homomorphic Butterworth"
    HOMOMORPHIC_ROBUST = "Homomorphic Robust"

    # NEW: Retinex methods
    SSR = "SSR"
    MSR = "MSR"

    # NEW: Adaptive methods
    CLAHE = "CLAHE"
    INTRINSIC_REFLECTANCE = "Intrinsic Reflectance"

    # NEW: Restoration methods
    RESTORE_LOG = "Restore Log"
    RESTORE_ROOT = "Restore Root"
    RESTORE_LINEAR = "Restore Linear"
    RESTORE_GAMMA_SUPPRESS = "Restore Gamma Suppress"

    # NEW: Morphological operations
    MORPH_DILATE = "Morph Dilate"
    MORPH_ERODE = "Morph Erode"
    MORPH_OPEN = "Morph Open"
    MORPH_CLOSE = "Morph Close"

    # NEW: LAB color space operations
    BGR_TO_LAB = "BGR to LAB"
    LAB_TO_BGR = "LAB to BGR"
    GAMMA_LAB_L = "Gamma on LAB L"
    CLAHE_LAB_L = "CLAHE on LAB L"
    CLAHE_BGR_CHANNELS = "CLAHE on BGR Channels"

    # NEW: Polar unwrap, localised block Otsu, flipover detection
    POLAR_UNWRAP = "Polar Unwrap"
    OTSU_LOCAL_BLOCK = "Otsu Local Block"
    FIND_FLIPOVER = "Find Flipover Row"
    RELATIVE_GAMMA = "Relative Gamma"


@dataclass
class PipelineStep:
    """Stores information about a pipeline step."""
    processing_type: ProcessingType
    parameters: dict

    def __str__(self):
        params_str = ", ".join(f"{k}={v}" for k, v in self.parameters.items())
        return f"{self.processing_type.value}: {params_str}" if params_str else self.processing_type.value


class ImageProcessingGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Enhanced Image Processing Tool")
        self.root.geometry("1600x1000")
        self.root.minsize(1400, 900)

        # Image state
        self.current_image: Optional[np.ndarray] = None
        self.original_image: Optional[np.ndarray] = None
        self.current_mask: Optional[np.ndarray] = None
        self.mask_crop_region: Optional[Tuple[int, int, int, int]] = None  # (top, bottom, left, right)

        # Pipeline tracking - PERSISTENT across image loads
        self.pipeline: List[PipelineStep] = []  # Current pipeline steps
        self.image_stack: List[np.ndarray] = []  # Stack of images for undo

        # Track if we should auto-apply pipeline when loading new images
        self.auto_apply_pipeline: bool = False

        # File navigation state
        self.current_file_path: Optional[str] = None
        self.current_folder: Optional[str] = None
        self.folder_files: List[str] = []
        self.current_file_index: int = -1

        # Image extensions to filter
        self.image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.gif'}

        # Crosshair state
        self.mouse_x = None
        self.mouse_y = None
        self.before_frame_label = None
        self.after_frame_label = None
        self.crosshair_enabled = True

        # Store displayed image information for coordinate mapping
        self.before_display_info = None  # (img_array, offset_x, offset_y, scale)
        self.after_display_info = None   # (img_array, offset_x, offset_y, scale)

        # Trace mode: step-through pipeline without modifying it
        # trace_index = None means live mode (normal).
        # trace_index = 0..len(pipeline)-1 means viewing that step's output.
        self.trace_index: Optional[int] = None

        # Create GUI
        self._create_gui()

    def _create_gui(self):
        """Create the main GUI layout."""
        # Main container with scrollable canvas
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Create a canvas with scrollbar for controls
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))

        canvas = tk.Canvas(canvas_frame, width=380)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Controls in scrollable frame
        controls_frame = ttk.LabelFrame(scrollable_frame, text="Controls", padding="5")
        controls_frame.pack(fill=tk.X, pady=(0, 5))

        self._create_file_controls(controls_frame)
        self._create_processing_controls(controls_frame)
        self._create_history_controls(controls_frame)

        # Right side: Pipeline and image display
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Pipeline display
        pipeline_frame = ttk.LabelFrame(right_frame, text="Current Pipeline (Auto-applies to next/prev images)", padding="5")
        pipeline_frame.pack(fill=tk.X, pady=(0, 5))
        self._create_pipeline_display(pipeline_frame)

        # Trace controls
        trace_frame = ttk.Frame(right_frame)
        trace_frame.pack(fill=tk.X, pady=(0, 3))

        ttk.Button(trace_frame, text="◀ Trace Prev", command=self._trace_prev, width=14).pack(side=tk.LEFT, padx=2)
        ttk.Button(trace_frame, text="Trace Next ▶", command=self._trace_next, width=14).pack(side=tk.LEFT, padx=2)
        ttk.Button(trace_frame, text="Exit Trace", command=self._trace_exit, width=10).pack(side=tk.LEFT, padx=2)

        self.trace_label_var = tk.StringVar(value="")
        ttk.Label(trace_frame, textvariable=self.trace_label_var,
                  font=("TkDefaultFont", 9, "bold")).pack(side=tk.LEFT, padx=8)

        # Image display
        display_frame = ttk.LabelFrame(right_frame, text="Image View (Before | After)", padding="5")
        display_frame.pack(fill=tk.BOTH, expand=True)
        self._create_image_display(display_frame)

        # Status bar
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_label.pack(fill=tk.X, padx=2, pady=2)

    def _create_file_controls(self, parent):
        """Create file selection and navigation controls."""
        file_frame = ttk.LabelFrame(parent, text="File Selection", padding="5")
        file_frame.pack(fill=tk.X, pady=(0, 5))

        # Row 1: Load and save buttons
        row1 = ttk.Frame(file_frame)
        row1.pack(fill=tk.X, pady=2)

        ttk.Button(row1, text="Load Image", command=self._load_image, width=15).pack(side=tk.LEFT, padx=2)
        ttk.Button(row1, text="Save Result", command=self._save_result, width=15).pack(side=tk.LEFT, padx=2)

        # Row 2: Navigation
        row2 = ttk.Frame(file_frame)
        row2.pack(fill=tk.X, pady=2)

        ttk.Button(row2, text="◀ Previous", command=self._previous_image, width=15).pack(side=tk.LEFT, padx=2)
        ttk.Button(row2, text="Next ▶", command=self._next_image, width=15).pack(side=tk.LEFT, padx=2)

        # Current file label
        self.file_label_var = tk.StringVar(value="No file loaded")
        file_label = ttk.Label(file_frame, textvariable=self.file_label_var, relief=tk.SUNKEN)
        file_label.pack(fill=tk.X, pady=2)

    def _create_processing_controls(self, parent):
        """Create all processing controls with dropdowns."""
        proc_frame = ttk.LabelFrame(parent, text="Processing Operations", padding="5")
        proc_frame.pack(fill=tk.X, pady=(0, 5))

        # 1. Annular Mask
        self._create_annular_controls(proc_frame)

        # 2. Background Normalization (Full)
        self._create_background_norm_controls(proc_frame)

        # 3. Background Normalization Simple
        self._create_background_norm_simple_controls(proc_frame)

        # 4. Contrast Normalization
        self._create_contrast_norm_controls(proc_frame)

        # 5. Gray Normalization
        self._create_gray_normalize_controls(proc_frame)

        # 6. Rank Filter
        self._create_rank_filter_controls(proc_frame)

        # 7. Unsharp Masking
        self._create_unsharp_mask_controls(proc_frame)

        # 8. Bilateral Filter
        self._create_bilateral_controls(proc_frame)

        # 9. Gamma Correction
        self._create_gamma_controls(proc_frame)

        # 10. Histogram Equalization
        self._create_histogram_eq_controls(proc_frame)

        # 11. Homomorphic Filter
        self._create_homomorphic_controls(proc_frame)

        # 12. Otsu Thresholding
        self._create_otsu_controls(proc_frame)

        # 13-26: NEW METHODS
        self._create_homo_butterworth_controls(proc_frame)
        self._create_homo_robust_controls(proc_frame)
        self._create_ssr_controls(proc_frame)
        self._create_msr_controls(proc_frame)
        self._create_clahe_controls(proc_frame)
        self._create_intrinsic_controls(proc_frame)
        self._create_restore_log_controls(proc_frame)
        self._create_restore_root_controls(proc_frame)
        self._create_restore_linear_controls(proc_frame)
        self._create_restore_gamma_suppress_controls(proc_frame)
        self._create_morph_dilate_controls(proc_frame)
        self._create_morph_erode_controls(proc_frame)
        self._create_morph_open_controls(proc_frame)
        self._create_morph_close_controls(proc_frame)

        # 27-31: NEW LAB and CLAHE METHODS
        self._create_bgr_to_lab_controls(proc_frame)
        self._create_lab_to_bgr_controls(proc_frame)
        self._create_gamma_lab_l_controls(proc_frame)
        self._create_clahe_lab_l_controls(proc_frame)
        self._create_clahe_bgr_channels_controls(proc_frame)

        # 32-34: Polar Unwrap, Local Block Otsu, Flipover Detection
        self._create_polar_unwrap_controls(proc_frame)
        self._create_otsu_local_block_controls(proc_frame)
        self._create_find_flipover_controls(proc_frame)

        # 35: Relative Gamma
        self._create_relative_gamma_controls(proc_frame)

    def _create_annular_controls(self, parent):
        """Create annular mask controls."""
        frame = ttk.LabelFrame(parent, text="1. Annular Mask", padding="3")
        frame.pack(fill=tk.X, pady=2)

        # Parameters frame
        params = ttk.Frame(frame)
        params.pack(fill=tk.X)

        # Center X
        ttk.Label(params, text="Center X:", width=12).grid(row=0, column=0, sticky=tk.W)
        self.annular_cx_var = tk.StringVar(value="635")
        ttk.Entry(params, textvariable=self.annular_cx_var, width=8).grid(row=0, column=1, padx=2)

        # Center Y
        ttk.Label(params, text="Center Y:", width=12).grid(row=0, column=2, sticky=tk.W, padx=(10, 0))
        self.annular_cy_var = tk.StringVar(value="350")
        ttk.Entry(params, textvariable=self.annular_cy_var, width=8).grid(row=0, column=3, padx=2)

        # Outer radius
        ttk.Label(params, text="Outer R:", width=12).grid(row=1, column=0, sticky=tk.W)
        self.annular_outer_var = tk.StringVar(value="60")
        ttk.Entry(params, textvariable=self.annular_outer_var, width=8).grid(row=1, column=1, padx=2)

        # Inner radius
        ttk.Label(params, text="Inner R:", width=12).grid(row=1, column=2, sticky=tk.W, padx=(10, 0))
        self.annular_inner_var = tk.StringVar(value="25")
        ttk.Entry(params, textvariable=self.annular_inner_var, width=8).grid(row=1, column=3, padx=2)

        # Apply button
        ttk.Button(frame, text="Apply Mask", command=self._apply_annular_mask).pack(pady=2)

    def _create_background_norm_controls(self, parent):
        """Create background normalization controls."""
        frame = ttk.LabelFrame(parent, text="2. Background Normalization", padding="3")
        frame.pack(fill=tk.X, pady=2)

        params = ttk.Frame(frame)
        params.pack(fill=tk.X)

        # sx
        ttk.Label(params, text="sx:", width=8).grid(row=0, column=0, sticky=tk.W)
        self.bg_sx_var = tk.StringVar(value="10")
        ttk.Combobox(params, textvariable=self.bg_sx_var, values=list(range(5, 51, 5)), width=6).grid(row=0, column=1, padx=2)

        # sy
        ttk.Label(params, text="sy:", width=8).grid(row=0, column=2, sticky=tk.W)
        self.bg_sy_var = tk.StringVar(value="10")
        ttk.Combobox(params, textvariable=self.bg_sy_var, values=list(range(5, 51, 5)), width=6).grid(row=0, column=3, padx=2)

        # thresh
        ttk.Label(params, text="thresh:", width=8).grid(row=1, column=0, sticky=tk.W)
        self.bg_thresh_var = tk.StringVar(value="100")
        ttk.Combobox(params, textvariable=self.bg_thresh_var, values=list(range(50, 201, 10)), width=6).grid(row=1, column=1, padx=2)

        # mincount
        ttk.Label(params, text="mincount:", width=8).grid(row=1, column=2, sticky=tk.W)
        self.bg_mincount_var = tk.StringVar(value="50")
        ttk.Combobox(params, textvariable=self.bg_mincount_var, values=list(range(10, 101, 10)), width=6).grid(row=1, column=3, padx=2)

        # bgval
        ttk.Label(params, text="bgval:", width=8).grid(row=2, column=0, sticky=tk.W)
        self.bg_bgval_var = tk.StringVar(value="200")
        ttk.Combobox(params, textvariable=self.bg_bgval_var, values=list(range(150, 256, 10)), width=6).grid(row=2, column=1, padx=2)

        # smoothx
        ttk.Label(params, text="smoothx:", width=8).grid(row=2, column=2, sticky=tk.W)
        self.bg_smoothx_var = tk.StringVar(value="2")
        ttk.Combobox(params, textvariable=self.bg_smoothx_var, values=list(range(0, 11)), width=6).grid(row=2, column=3, padx=2)

        # smoothy
        ttk.Label(params, text="smoothy:", width=8).grid(row=3, column=0, sticky=tk.W)
        self.bg_smoothy_var = tk.StringVar(value="2")
        ttk.Combobox(params, textvariable=self.bg_smoothy_var, values=list(range(0, 11)), width=6).grid(row=3, column=1, padx=2)

        ttk.Button(frame, text="Apply Background Norm", command=self._apply_background_norm).pack(pady=2)

    def _create_background_norm_simple_controls(self, parent):
        """Create background normalization simple controls."""
        frame = ttk.LabelFrame(parent, text="3. Background Norm Simple", padding="3")
        frame.pack(fill=tk.X, pady=2)

        params = ttk.Frame(frame)
        params.pack(fill=tk.X)

        # size
        ttk.Label(params, text="size:", width=8).grid(row=0, column=0, sticky=tk.W)
        self.bg_simple_size_var = tk.StringVar(value="50")
        ttk.Combobox(params, textvariable=self.bg_simple_size_var, values=list(range(10, 101, 5)), width=8).grid(row=0, column=1, padx=2)

        # bgval
        ttk.Label(params, text="bgval:", width=8).grid(row=0, column=2, sticky=tk.W)
        self.bg_simple_bgval_var = tk.StringVar(value="200")
        ttk.Combobox(params, textvariable=self.bg_simple_bgval_var, values=list(range(150, 256, 10)), width=8).grid(row=0, column=3, padx=2)

        ttk.Button(frame, text="Apply Background Simple", command=self._apply_background_norm_simple).pack(pady=2)

    def _create_contrast_norm_controls(self, parent):
        """Create contrast normalization controls."""
        frame = ttk.LabelFrame(parent, text="4. Contrast Normalization", padding="3")
        frame.pack(fill=tk.X, pady=2)

        params = ttk.Frame(frame)
        params.pack(fill=tk.X)

        # sx
        ttk.Label(params, text="sx:", width=8).grid(row=0, column=0, sticky=tk.W)
        self.contrast_sx_var = tk.StringVar(value="10")
        ttk.Combobox(params, textvariable=self.contrast_sx_var, values=list(range(5, 51, 5)), width=8).grid(row=0, column=1, padx=2)

        # sy
        ttk.Label(params, text="sy:", width=8).grid(row=0, column=2, sticky=tk.W)
        self.contrast_sy_var = tk.StringVar(value="10")
        ttk.Combobox(params, textvariable=self.contrast_sy_var, values=list(range(5, 51, 5)), width=8).grid(row=0, column=3, padx=2)

        # mindiff
        ttk.Label(params, text="mindiff:", width=8).grid(row=1, column=0, sticky=tk.W)
        self.contrast_mindiff_var = tk.StringVar(value="30")
        ttk.Combobox(params, textvariable=self.contrast_mindiff_var, values=list(range(10, 101, 5)), width=8).grid(row=1, column=1, padx=2)

        ttk.Button(frame, text="Apply Contrast Norm", command=self._apply_contrast_norm).pack(pady=2)

    def _create_gray_normalize_controls(self, parent):
        """Create gray normalization controls."""
        frame = ttk.LabelFrame(parent, text="5. Gray Normalization", padding="3")
        frame.pack(fill=tk.X, pady=2)

        ttk.Label(frame, text="Normalize to [0, 255] range").pack()
        ttk.Button(frame, text="Apply Gray Normalize", command=self._apply_gray_normalize).pack(pady=2)

    def _create_rank_filter_controls(self, parent):
        """Create rank filter controls."""
        frame = ttk.LabelFrame(parent, text="6. Rank Filter", padding="3")
        frame.pack(fill=tk.X, pady=2)

        params = ttk.Frame(frame)
        params.pack(fill=tk.X)

        # size
        ttk.Label(params, text="size:", width=8).grid(row=0, column=0, sticky=tk.W)
        self.rank_size_var = tk.StringVar(value="31")
        ttk.Combobox(params, textvariable=self.rank_size_var, values=[str(i) for i in range(3, 52, 2)], width=8).grid(row=0, column=1, padx=2)

        # rank
        ttk.Label(params, text="rank:", width=8).grid(row=0, column=2, sticky=tk.W)
        self.rank_rank_var = tk.StringVar(value="0.5")
        ttk.Combobox(params, textvariable=self.rank_rank_var, values=[f"{i/100:.2f}" for i in range(0, 101, 5)], width=8).grid(row=0, column=3, padx=2)

        ttk.Button(frame, text="Apply Rank Filter", command=self._apply_rank_filter).pack(pady=2)

    def _create_unsharp_mask_controls(self, parent):
        """Create unsharp masking controls."""
        frame = ttk.LabelFrame(parent, text="7. Unsharp Masking", padding="3")
        frame.pack(fill=tk.X, pady=2)

        params = ttk.Frame(frame)
        params.pack(fill=tk.X)

        # halfwidth
        ttk.Label(params, text="halfwidth:", width=10).grid(row=0, column=0, sticky=tk.W)
        self.unsharp_hw_var = tk.StringVar(value="5")
        ttk.Combobox(params, textvariable=self.unsharp_hw_var, values=list(range(1, 21)), width=8).grid(row=0, column=1, padx=2)

        # fract
        ttk.Label(params, text="fract:", width=10).grid(row=0, column=2, sticky=tk.W)
        self.unsharp_fract_var = tk.StringVar(value="2.5")
        ttk.Combobox(params, textvariable=self.unsharp_fract_var, values=[f"{i/2:.1f}" for i in range(2, 21)], width=8).grid(row=0, column=3, padx=2)

        ttk.Button(frame, text="Apply Unsharp Mask", command=self._apply_unsharp_mask).pack(pady=2)

    def _create_bilateral_controls(self, parent):
        """Create bilateral filter controls."""
        frame = ttk.LabelFrame(parent, text="8. Bilateral Filter", padding="3")
        frame.pack(fill=tk.X, pady=2)

        params = ttk.Frame(frame)
        params.pack(fill=tk.X)

        # d
        ttk.Label(params, text="d:", width=12).grid(row=0, column=0, sticky=tk.W)
        self.bilateral_d_var = tk.StringVar(value="9")
        ttk.Combobox(params, textvariable=self.bilateral_d_var, values=[str(i) for i in range(3, 16, 2)], width=8).grid(row=0, column=1, padx=2)

        # sigmaColor
        ttk.Label(params, text="sigmaColor:", width=12).grid(row=1, column=0, sticky=tk.W)
        self.bilateral_sc_var = tk.StringVar(value="75")
        ttk.Combobox(params, textvariable=self.bilateral_sc_var, values=list(range(25, 201, 25)), width=8).grid(row=1, column=1, padx=2)

        # sigmaSpace
        ttk.Label(params, text="sigmaSpace:", width=12).grid(row=1, column=2, sticky=tk.W)
        self.bilateral_ss_var = tk.StringVar(value="75")
        ttk.Combobox(params, textvariable=self.bilateral_ss_var, values=list(range(25, 201, 25)), width=8).grid(row=1, column=3, padx=2)

        ttk.Button(frame, text="Apply Bilateral", command=self._apply_bilateral).pack(pady=2)

    def _create_gamma_controls(self, parent):
        """Create gamma correction controls."""
        frame = ttk.LabelFrame(parent, text="9. Gamma Correction", padding="3")
        frame.pack(fill=tk.X, pady=2)

        params = ttk.Frame(frame)
        params.pack(fill=tk.X)

        ttk.Label(params, text="Gamma (>1=brighten, <1=darken):", width=28).grid(row=0, column=0, sticky=tk.W)

        # Use the actual gamma values from GAMMA_LUT
        gamma_values = [f"{g:.2f}" for g in GAMMA_LUT.gamma_values]
        self.gamma_var = tk.StringVar(value="1.00")
        ttk.Combobox(params, textvariable=self.gamma_var, values=gamma_values, width=8).grid(row=0, column=1, padx=2)

        ttk.Button(frame, text="Apply Gamma", command=self._apply_gamma).pack(pady=2)

    def _create_histogram_eq_controls(self, parent):
        """Create histogram equalization controls."""
        frame = ttk.LabelFrame(parent, text="10. Histogram Equalization", padding="3")
        frame.pack(fill=tk.X, pady=2)

        ttk.Label(frame, text="Enhance contrast via histogram").pack()
        ttk.Button(frame, text="Apply Histogram Eq", command=self._apply_histogram_eq).pack(pady=2)

    def _create_homomorphic_controls(self, parent):
        """Create homomorphic filter controls."""
        frame = ttk.LabelFrame(parent, text="11. Homomorphic Filter", padding="3")
        frame.pack(fill=tk.X, pady=2)

        params = ttk.Frame(frame)
        params.pack(fill=tk.X)

        # d0
        ttk.Label(params, text="d0:", width=10).grid(row=0, column=0, sticky=tk.W)
        self.homo_d0_var = tk.StringVar(value="30")
        ttk.Combobox(params, textvariable=self.homo_d0_var, values=list(range(10, 101, 5)), width=8).grid(row=0, column=1, padx=2)

        # gamma_l
        ttk.Label(params, text="gamma_l:", width=10).grid(row=0, column=2, sticky=tk.W)
        self.homo_gl_var = tk.StringVar(value="0.5")
        ttk.Combobox(params, textvariable=self.homo_gl_var, values=[f"{i/10:.1f}" for i in range(1, 21)], width=8).grid(row=0, column=3, padx=2)

        # gamma_h
        ttk.Label(params, text="gamma_h:", width=10).grid(row=1, column=0, sticky=tk.W)
        self.homo_gh_var = tk.StringVar(value="2.0")
        ttk.Combobox(params, textvariable=self.homo_gh_var, values=[f"{i/10:.1f}" for i in range(10, 51)], width=8).grid(row=1, column=1, padx=2)

        # restoration method
        ttk.Label(params, text="restoration:", width=10).grid(row=1, column=2, sticky=tk.W)
        self.homo_restoration_var = tk.StringVar(value="log")
        ttk.Combobox(params, textvariable=self.homo_restoration_var,
                     values=["log", "linear", "root", "gamma_suppress"], width=12).grid(row=1, column=3, padx=2)

        # root_n (for root restoration)
        ttk.Label(params, text="root_n:", width=10).grid(row=2, column=0, sticky=tk.W)
        self.homo_root_n_var = tk.StringVar(value="3.0")
        ttk.Combobox(params, textvariable=self.homo_root_n_var, values=[f"{i/2:.1f}" for i in range(2, 21)], width=8).grid(row=2, column=1, padx=2)

        ttk.Button(frame, text="Apply Homomorphic", command=self._apply_homomorphic).pack(pady=2)

    def _create_otsu_controls(self, parent):
        """Create Otsu thresholding controls."""
        frame = ttk.LabelFrame(parent, text="12. Otsu Thresholding", padding="3")
        frame.pack(fill=tk.X, pady=2)

        # Global Otsu
        ttk.Button(frame, text="Apply Otsu Global", command=self._apply_otsu_global).pack(pady=2)

        # Local Otsu parameters
        params = ttk.Frame(frame)
        params.pack(fill=tk.X)

        ttk.Label(params, text="block_size:", width=12).grid(row=0, column=0, sticky=tk.W)
        self.otsu_block_var = tk.StringVar(value="35")
        ttk.Combobox(params, textvariable=self.otsu_block_var, values=[str(i) for i in range(11, 100, 2)], width=8).grid(row=0, column=1, padx=2)

        ttk.Label(params, text="C:", width=12).grid(row=0, column=2, sticky=tk.W)
        self.otsu_c_var = tk.StringVar(value="2")
        ttk.Combobox(params, textvariable=self.otsu_c_var, values=list(range(-10, 11)), width=8).grid(row=0, column=3, padx=2)

        ttk.Button(frame, text="Apply Otsu Local", command=self._apply_otsu_local).pack(pady=2)

    # =========================================================================
    # NEW METHODS - CONTROL CREATION
    # =========================================================================

    def _create_homo_butterworth_controls(self, parent):
        """Homomorphic Butterworth filter controls."""
        frame = ttk.LabelFrame(parent, text="13. Homomorphic Butterworth", padding="3")
        frame.pack(fill=tk.X, pady=2)
        params = ttk.Frame(frame)
        params.pack(fill=tk.X)
        ttk.Label(params, text="d0:", width=8).grid(row=0, column=0, sticky=tk.W)
        self.homo_butter_d0_var = tk.StringVar(value="30")
        ttk.Combobox(params, textvariable=self.homo_butter_d0_var, values=list(range(10, 101, 5)), width=6).grid(row=0, column=1, padx=2)
        ttk.Label(params, text="gamma_l:", width=8).grid(row=0, column=2, sticky=tk.W)
        self.homo_butter_gl_var = tk.StringVar(value="0.5")
        ttk.Combobox(params, textvariable=self.homo_butter_gl_var, values=[f"{i/10:.1f}" for i in range(1, 21)], width=6).grid(row=0, column=3, padx=2)
        ttk.Label(params, text="gamma_h:", width=8).grid(row=1, column=0, sticky=tk.W)
        self.homo_butter_gh_var = tk.StringVar(value="2.0")
        ttk.Combobox(params, textvariable=self.homo_butter_gh_var, values=[f"{i/10:.1f}" for i in range(10, 51)], width=6).grid(row=1, column=1, padx=2)
        ttk.Label(params, text="n:", width=8).grid(row=1, column=2, sticky=tk.W)
        self.homo_butter_n_var = tk.StringVar(value="2.0")
        ttk.Combobox(params, textvariable=self.homo_butter_n_var, values=[f"{i:.1f}" for i in [1.0, 1.5, 2.0, 2.5, 3.0]], width=6).grid(row=1, column=3, padx=2)
        ttk.Button(frame, text="Apply Homo Butterworth", command=self._apply_homo_butterworth).pack(pady=2)

    def _create_homo_robust_controls(self, parent):
        """Homomorphic Robust filter controls."""
        frame = ttk.LabelFrame(parent, text="14. Homomorphic Robust", padding="3")
        frame.pack(fill=tk.X, pady=2)
        params = ttk.Frame(frame)
        params.pack(fill=tk.X)
        ttk.Label(params, text="d0:", width=8).grid(row=0, column=0, sticky=tk.W)
        self.homo_robust_d0_var = tk.StringVar(value="30")
        ttk.Combobox(params, textvariable=self.homo_robust_d0_var, values=list(range(10, 101, 5)), width=6).grid(row=0, column=1, padx=2)
        ttk.Label(params, text="gamma_l:", width=8).grid(row=0, column=2, sticky=tk.W)
        self.homo_robust_gl_var = tk.StringVar(value="0.5")
        ttk.Combobox(params, textvariable=self.homo_robust_gl_var, values=[f"{i/10:.1f}" for i in range(1, 21)], width=6).grid(row=0, column=3, padx=2)
        ttk.Label(params, text="gamma_h:", width=8).grid(row=1, column=0, sticky=tk.W)
        self.homo_robust_gh_var = tk.StringVar(value="2.0")
        ttk.Combobox(params, textvariable=self.homo_robust_gh_var, values=[f"{i/10:.1f}" for i in range(10, 51)], width=6).grid(row=1, column=1, padx=2)
        ttk.Button(frame, text="Apply Homo Robust", command=self._apply_homo_robust).pack(pady=2)

    def _create_ssr_controls(self, parent):
        """SSR controls."""
        frame = ttk.LabelFrame(parent, text="15. SSR (Single Scale Retinex)", padding="3")
        frame.pack(fill=tk.X, pady=2)
        params = ttk.Frame(frame)
        params.pack(fill=tk.X)
        ttk.Label(params, text="Sigma:", width=10).grid(row=0, column=0, sticky=tk.W)
        self.ssr_sigma_var = tk.StringVar(value="80")
        ttk.Combobox(params, textvariable=self.ssr_sigma_var, values=list(range(15, 251, 15)), width=8).grid(row=0, column=1, padx=2)
        ttk.Button(frame, text="Apply SSR", command=self._apply_ssr).pack(pady=2)

    def _create_msr_controls(self, parent):
        """MSR controls."""
        frame = ttk.LabelFrame(parent, text="16. MSR (Multi-Scale Retinex)", padding="3")
        frame.pack(fill=tk.X, pady=2)
        params = ttk.Frame(frame)
        params.pack(fill=tk.X)
        ttk.Label(params, text="Sigma1:", width=8).grid(row=0, column=0, sticky=tk.W)
        self.msr_s1_var = tk.StringVar(value="15")
        ttk.Combobox(params, textvariable=self.msr_s1_var, values=list(range(5, 51, 5)), width=6).grid(row=0, column=1, padx=2)
        ttk.Label(params, text="Sigma2:", width=8).grid(row=0, column=2, sticky=tk.W)
        self.msr_s2_var = tk.StringVar(value="80")
        ttk.Combobox(params, textvariable=self.msr_s2_var, values=list(range(40, 151, 10)), width=6).grid(row=0, column=3, padx=2)
        ttk.Label(params, text="Sigma3:", width=8).grid(row=1, column=0, sticky=tk.W)
        self.msr_s3_var = tk.StringVar(value="250")
        ttk.Combobox(params, textvariable=self.msr_s3_var, values=list(range(150, 351, 25)), width=6).grid(row=1, column=1, padx=2)
        ttk.Button(frame, text="Apply MSR", command=self._apply_msr).pack(pady=2)

    def _create_clahe_controls(self, parent):
        """CLAHE controls."""
        frame = ttk.LabelFrame(parent, text="17. CLAHE", padding="3")
        frame.pack(fill=tk.X, pady=2)
        params = ttk.Frame(frame)
        params.pack(fill=tk.X)
        ttk.Label(params, text="Clip Limit:", width=10).grid(row=0, column=0, sticky=tk.W)
        self.clahe_clip_var = tk.StringVar(value="2.0")
        ttk.Combobox(params, textvariable=self.clahe_clip_var, values=[f"{i:.1f}" for i in np.arange(1.0, 10.5, 0.5)], width=8).grid(row=0, column=1, padx=2)
        ttk.Label(params, text="Tile Grid:", width=10).grid(row=0, column=2, sticky=tk.W)
        self.clahe_grid_var = tk.StringVar(value="8")
        ttk.Combobox(params, textvariable=self.clahe_grid_var, values=["4", "8", "16", "32"], width=8).grid(row=0, column=3, padx=2)
        ttk.Button(frame, text="Apply CLAHE", command=self._apply_clahe).pack(pady=2)

    def _create_intrinsic_controls(self, parent):
        """Intrinsic Reflectance controls."""
        frame = ttk.LabelFrame(parent, text="18. Intrinsic Reflectance", padding="3")
        frame.pack(fill=tk.X, pady=2)
        params = ttk.Frame(frame)
        params.pack(fill=tk.X)
        ttk.Label(params, text="Sigma Spatial:", width=12).grid(row=0, column=0, sticky=tk.W)
        self.intrinsic_spatial_var = tk.StringVar(value="10")
        ttk.Combobox(params, textvariable=self.intrinsic_spatial_var, values=list(range(5, 31, 5)), width=6).grid(row=0, column=1, padx=2)
        ttk.Label(params, text="Sigma Range:", width=12).grid(row=0, column=2, sticky=tk.W)
        self.intrinsic_range_var = tk.StringVar(value="30")
        ttk.Combobox(params, textvariable=self.intrinsic_range_var, values=list(range(10, 61, 10)), width=6).grid(row=0, column=3, padx=2)
        ttk.Label(params, text="Iterations:", width=12).grid(row=1, column=0, sticky=tk.W)
        self.intrinsic_iter_var = tk.StringVar(value="3")
        ttk.Combobox(params, textvariable=self.intrinsic_iter_var, values=list(range(1, 6)), width=6).grid(row=1, column=1, padx=2)
        ttk.Button(frame, text="Apply Intrinsic", command=self._apply_intrinsic).pack(pady=2)

    def _create_restore_log_controls(self, parent):
        """Log Restoration controls."""
        frame = ttk.LabelFrame(parent, text="19. Restore Log", padding="3")
        frame.pack(fill=tk.X, pady=2)
        ttk.Label(frame, text="Log restoration (no parameters)").pack()
        ttk.Button(frame, text="Apply Restore Log", command=self._apply_restore_log).pack(pady=2)

    def _create_restore_root_controls(self, parent):
        """Root Restoration controls."""
        frame = ttk.LabelFrame(parent, text="20. Restore Root", padding="3")
        frame.pack(fill=tk.X, pady=2)
        params = ttk.Frame(frame)
        params.pack(fill=tk.X)
        ttk.Label(params, text="n (root power):", width=15).grid(row=0, column=0, sticky=tk.W)
        self.restore_root_n_var = tk.StringVar(value="2.0")
        ttk.Combobox(params, textvariable=self.restore_root_n_var, values=[f"{i:.1f}" for i in np.arange(1.5, 5.5, 0.5)], width=8).grid(row=0, column=1, padx=2)
        ttk.Button(frame, text="Apply Restore Root", command=self._apply_restore_root).pack(pady=2)

    def _create_restore_linear_controls(self, parent):
        """Linear Restoration controls."""
        frame = ttk.LabelFrame(parent, text="21. Restore Linear", padding="3")
        frame.pack(fill=tk.X, pady=2)
        params = ttk.Frame(frame)
        params.pack(fill=tk.X)
        ttk.Label(params, text="Clip %ile:", width=12).grid(row=0, column=0, sticky=tk.W)
        self.restore_linear_clip_var = tk.StringVar(value="0.5")
        ttk.Combobox(params, textvariable=self.restore_linear_clip_var, values=[f"{i:.1f}" for i in np.arange(0, 5.5, 0.5)], width=8).grid(row=0, column=1, padx=2)
        ttk.Button(frame, text="Apply Restore Linear", command=self._apply_restore_linear).pack(pady=2)

    def _create_restore_gamma_suppress_controls(self, parent):
        """Gamma Suppress-Express Restoration controls."""
        frame = ttk.LabelFrame(parent, text="22. Restore Gamma Suppress", padding="3")
        frame.pack(fill=tk.X, pady=2)
        params = ttk.Frame(frame)
        params.pack(fill=tk.X)
        ttk.Label(params, text="γ bright:", width=10).grid(row=0, column=0, sticky=tk.W)
        self.restore_gs_bright_var = tk.StringVar(value="2.0")
        ttk.Combobox(params, textvariable=self.restore_gs_bright_var, values=[f"{i:.1f}" for i in np.arange(1.0, 3.5, 0.5)], width=6).grid(row=0, column=1, padx=2)
        ttk.Label(params, text="γ dark:", width=10).grid(row=0, column=2, sticky=tk.W)
        self.restore_gs_dark_var = tk.StringVar(value="0.5")
        ttk.Combobox(params, textvariable=self.restore_gs_dark_var, values=[f"{i:.1f}" for i in np.arange(0.3, 1.1, 0.1)], width=6).grid(row=0, column=3, padx=2)
        ttk.Label(params, text="Final:", width=10).grid(row=1, column=0, sticky=tk.W)
        self.restore_gs_final_var = tk.StringVar(value="linear")
        ttk.Combobox(params, textvariable=self.restore_gs_final_var, values=["linear", "log", "root"], width=8).grid(row=1, column=1, padx=2)
        ttk.Label(params, text="Root n:", width=10).grid(row=1, column=2, sticky=tk.W)
        self.restore_gs_root_n_var = tk.StringVar(value="2.0")
        ttk.Combobox(params, textvariable=self.restore_gs_root_n_var, values=[f"{i:.1f}" for i in np.arange(1.5, 5.5, 0.5)], width=6).grid(row=1, column=3, padx=2)
        ttk.Button(frame, text="Apply Restore Gamma Suppress", command=self._apply_restore_gamma_suppress).pack(pady=2)

    def _create_morph_dilate_controls(self, parent):
        """Morphology Dilate controls."""
        frame = ttk.LabelFrame(parent, text="23. Morph Dilate", padding="3")
        frame.pack(fill=tk.X, pady=2)
        params = ttk.Frame(frame)
        params.pack(fill=tk.X)
        ttk.Label(params, text="Kernel Size:", width=12).grid(row=0, column=0, sticky=tk.W)
        self.morph_dilate_size_var = tk.StringVar(value="5")
        ttk.Combobox(params, textvariable=self.morph_dilate_size_var, values=[str(i) for i in range(3, 16, 2)], width=8).grid(row=0, column=1, padx=2)
        ttk.Label(params, text="Shape:", width=12).grid(row=0, column=2, sticky=tk.W)
        self.morph_dilate_shape_var = tk.StringVar(value="ellipse")
        ttk.Combobox(params, textvariable=self.morph_dilate_shape_var, values=["ellipse", "rectangle"], width=10).grid(row=0, column=3, padx=2)
        ttk.Button(frame, text="Apply Dilate", command=self._apply_morph_dilate).pack(pady=2)

    def _create_morph_erode_controls(self, parent):
        """Morphology Erode controls."""
        frame = ttk.LabelFrame(parent, text="24. Morph Erode", padding="3")
        frame.pack(fill=tk.X, pady=2)
        params = ttk.Frame(frame)
        params.pack(fill=tk.X)
        ttk.Label(params, text="Kernel Size:", width=12).grid(row=0, column=0, sticky=tk.W)
        self.morph_erode_size_var = tk.StringVar(value="5")
        ttk.Combobox(params, textvariable=self.morph_erode_size_var, values=[str(i) for i in range(3, 16, 2)], width=8).grid(row=0, column=1, padx=2)
        ttk.Label(params, text="Shape:", width=12).grid(row=0, column=2, sticky=tk.W)
        self.morph_erode_shape_var = tk.StringVar(value="ellipse")
        ttk.Combobox(params, textvariable=self.morph_erode_shape_var, values=["ellipse", "rectangle"], width=10).grid(row=0, column=3, padx=2)
        ttk.Button(frame, text="Apply Erode", command=self._apply_morph_erode).pack(pady=2)

    def _create_morph_open_controls(self, parent):
        """Morphology Open controls."""
        frame = ttk.LabelFrame(parent, text="25. Morph Open", padding="3")
        frame.pack(fill=tk.X, pady=2)
        params = ttk.Frame(frame)
        params.pack(fill=tk.X)
        ttk.Label(params, text="Kernel Size:", width=12).grid(row=0, column=0, sticky=tk.W)
        self.morph_open_size_var = tk.StringVar(value="5")
        ttk.Combobox(params, textvariable=self.morph_open_size_var, values=[str(i) for i in range(3, 16, 2)], width=8).grid(row=0, column=1, padx=2)
        ttk.Label(params, text="Shape:", width=12).grid(row=0, column=2, sticky=tk.W)
        self.morph_open_shape_var = tk.StringVar(value="ellipse")
        ttk.Combobox(params, textvariable=self.morph_open_shape_var, values=["ellipse", "rectangle"], width=10).grid(row=0, column=3, padx=2)
        ttk.Button(frame, text="Apply Open", command=self._apply_morph_open).pack(pady=2)

    def _create_morph_close_controls(self, parent):
        """Morphology Close controls."""
        frame = ttk.LabelFrame(parent, text="26. Morph Close", padding="3")
        frame.pack(fill=tk.X, pady=2)
        params = ttk.Frame(frame)
        params.pack(fill=tk.X)
        ttk.Label(params, text="Kernel Size:", width=12).grid(row=0, column=0, sticky=tk.W)
        self.morph_close_size_var = tk.StringVar(value="5")
        ttk.Combobox(params, textvariable=self.morph_close_size_var, values=[str(i) for i in range(3, 16, 2)], width=8).grid(row=0, column=1, padx=2)
        ttk.Label(params, text="Shape:", width=12).grid(row=0, column=2, sticky=tk.W)
        self.morph_close_shape_var = tk.StringVar(value="ellipse")
        ttk.Combobox(params, textvariable=self.morph_close_shape_var, values=["ellipse", "rectangle"], width=10).grid(row=0, column=3, padx=2)
        ttk.Button(frame, text="Apply Close", command=self._apply_morph_close).pack(pady=2)

    # =========================================================================
    # NEW LAB AND CLAHE CONTROLS
    # =========================================================================

    def _create_bgr_to_lab_controls(self, parent):
        """BGR to LAB conversion controls."""
        frame = ttk.LabelFrame(parent, text="27. BGR to LAB", padding="3")
        frame.pack(fill=tk.X, pady=2)
        ttk.Label(frame, text="Convert BGR image to LAB color space").pack(pady=2)
        ttk.Button(frame, text="Convert to LAB", command=self._apply_bgr_to_lab).pack(pady=2)

    def _create_lab_to_bgr_controls(self, parent):
        """LAB to BGR conversion controls."""
        frame = ttk.LabelFrame(parent, text="28. LAB to BGR", padding="3")
        frame.pack(fill=tk.X, pady=2)
        ttk.Label(frame, text="Convert LAB image back to BGR color space").pack(pady=2)
        ttk.Button(frame, text="Convert to BGR", command=self._apply_lab_to_bgr).pack(pady=2)

    def _create_gamma_lab_l_controls(self, parent):
        """Gamma correction on LAB L channel controls."""
        frame = ttk.LabelFrame(parent, text="29. Gamma on LAB L Channel", padding="3")
        frame.pack(fill=tk.X, pady=2)
        params = ttk.Frame(frame)
        params.pack(fill=tk.X)
        ttk.Label(params, text="Gamma:", width=10).grid(row=0, column=0, sticky=tk.W)
        self.gamma_lab_l_var = tk.StringVar(value="2.0")
        ttk.Combobox(params, textvariable=self.gamma_lab_l_var,
                     values=[f"{i/4:.2f}" for i in range(2, 25)], width=8).grid(row=0, column=1, padx=2)
        ttk.Label(frame, text="Adjust brightness in LAB space (preserves color)").pack(pady=2)
        ttk.Button(frame, text="Apply Gamma on L", command=self._apply_gamma_lab_l).pack(pady=2)

    def _create_clahe_lab_l_controls(self, parent):
        """CLAHE on LAB L channel controls."""
        frame = ttk.LabelFrame(parent, text="30. CLAHE on LAB L Channel", padding="3")
        frame.pack(fill=tk.X, pady=2)
        params = ttk.Frame(frame)
        params.pack(fill=tk.X)

        # Clip limit
        ttk.Label(params, text="Clip Limit:", width=12).grid(row=0, column=0, sticky=tk.W)
        self.clahe_lab_l_clip_var = tk.StringVar(value="2.0")
        ttk.Combobox(params, textvariable=self.clahe_lab_l_clip_var,
                     values=[f"{i:.1f}" for i in np.arange(1.0, 4.5, 0.5)], width=8).grid(row=0, column=1, padx=2)

        # Tile grid size
        ttk.Label(params, text="Tile Size:", width=12).grid(row=0, column=2, sticky=tk.W)
        self.clahe_lab_l_tile_var = tk.StringVar(value="8")
        ttk.Combobox(params, textvariable=self.clahe_lab_l_tile_var,
                     values=[str(i) for i in [4, 6, 8, 12, 16]], width=8).grid(row=0, column=3, padx=2)

        ttk.Label(frame, text="Adaptive contrast on L (preserves color)").pack(pady=2)
        ttk.Button(frame, text="Apply CLAHE on L", command=self._apply_clahe_lab_l).pack(pady=2)

    def _create_clahe_bgr_channels_controls(self, parent):
        """CLAHE on selected BGR channels controls."""
        frame = ttk.LabelFrame(parent, text="31. CLAHE on BGR Channels", padding="3")
        frame.pack(fill=tk.X, pady=2)

        # Checkboxes for channel selection
        check_frame = ttk.Frame(frame)
        check_frame.pack(fill=tk.X, pady=2)
        ttk.Label(check_frame, text="Select Channels:", width=15).pack(side=tk.LEFT)

        self.clahe_bgr_blue_var = tk.BooleanVar(value=True)
        self.clahe_bgr_green_var = tk.BooleanVar(value=True)
        self.clahe_bgr_red_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(check_frame, text="Blue", variable=self.clahe_bgr_blue_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(check_frame, text="Green", variable=self.clahe_bgr_green_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(check_frame, text="Red", variable=self.clahe_bgr_red_var).pack(side=tk.LEFT, padx=5)

        # CLAHE parameters
        params = ttk.Frame(frame)
        params.pack(fill=tk.X)

        # Clip limit
        ttk.Label(params, text="Clip Limit:", width=12).grid(row=0, column=0, sticky=tk.W)
        self.clahe_bgr_clip_var = tk.StringVar(value="2.0")
        ttk.Combobox(params, textvariable=self.clahe_bgr_clip_var,
                     values=[f"{i:.1f}" for i in np.arange(1.0, 4.5, 0.5)], width=8).grid(row=0, column=1, padx=2)

        # Tile grid size
        ttk.Label(params, text="Tile Size:", width=12).grid(row=0, column=2, sticky=tk.W)
        self.clahe_bgr_tile_var = tk.StringVar(value="8")
        ttk.Combobox(params, textvariable=self.clahe_bgr_tile_var,
                     values=[str(i) for i in [4, 6, 8, 12, 16]], width=8).grid(row=0, column=3, padx=2)

        ttk.Label(frame, text="Apply CLAHE to selected color channels").pack(pady=2)
        ttk.Button(frame, text="Apply CLAHE on Channels", command=self._apply_clahe_bgr_channels).pack(pady=2)

    # =========================================================================
    # NEW: POLAR UNWRAP / LOCAL BLOCK OTSU / FLIPOVER DETECTION CONTROLS
    # =========================================================================

    def _create_polar_unwrap_controls(self, parent):
        """Create polar unwrap controls."""
        frame = ttk.LabelFrame(parent, text="32. Polar Unwrap", padding="3")
        frame.pack(fill=tk.X, pady=2)

        params = ttk.Frame(frame)
        params.pack(fill=tk.X)

        ttk.Label(params, text="Center X:", width=12).grid(row=0, column=0, sticky=tk.W)
        self.polar_cx_var = tk.StringVar(value="632")
        ttk.Entry(params, textvariable=self.polar_cx_var, width=8).grid(row=0, column=1, padx=2)

        ttk.Label(params, text="Center Y:", width=12).grid(row=0, column=2, sticky=tk.W, padx=(10, 0))
        self.polar_cy_var = tk.StringVar(value="360")
        ttk.Entry(params, textvariable=self.polar_cy_var, width=8).grid(row=0, column=3, padx=2)

        ttk.Label(params, text="Inner R:", width=12).grid(row=1, column=0, sticky=tk.W)
        self.polar_inner_r_var = tk.StringVar(value="55")
        ttk.Entry(params, textvariable=self.polar_inner_r_var, width=8).grid(row=1, column=1, padx=2)

        ttk.Label(params, text="Radial depth:", width=12).grid(row=1, column=2, sticky=tk.W, padx=(10, 0))
        self.polar_depth_var = tk.StringVar(value="30")
        ttk.Entry(params, textvariable=self.polar_depth_var, width=8).grid(row=1, column=3, padx=2)

        ttk.Label(frame, text="Unwraps annular band → rectangular strip").pack(pady=1)
        ttk.Button(frame, text="Apply Polar Unwrap", command=self._apply_polar_unwrap).pack(pady=2)

    def _create_otsu_local_block_controls(self, parent):
        """Create localised block Otsu controls."""
        frame = ttk.LabelFrame(parent, text="33. Otsu Local Block", padding="3")
        frame.pack(fill=tk.X, pady=2)

        params = ttk.Frame(frame)
        params.pack(fill=tk.X)

        ttk.Label(params, text="Block H:", width=12).grid(row=0, column=0, sticky=tk.W)
        self.otsu_block_h_var = tk.StringVar(value="30")
        ttk.Combobox(params, textvariable=self.otsu_block_h_var,
                     values=[str(i) for i in range(5, 101, 5)], width=8).grid(row=0, column=1, padx=2)

        ttk.Label(params, text="Block W:", width=12).grid(row=0, column=2, sticky=tk.W, padx=(10, 0))
        self.otsu_block_w_var = tk.StringVar(value="0")
        ttk.Entry(params, textvariable=self.otsu_block_w_var, width=8).grid(row=0, column=3, padx=2)

        ttk.Label(frame, text="Block W = 0 → auto (image width / 12)").pack(pady=1)
        ttk.Button(frame, text="Apply Otsu Block", command=self._apply_otsu_local_block).pack(pady=2)

    def _create_find_flipover_controls(self, parent):
        """Create flipover row detection controls."""
        frame = ttk.LabelFrame(parent, text="34. Find Flipover Row", padding="3")
        frame.pack(fill=tk.X, pady=2)

        params = ttk.Frame(frame)
        params.pack(fill=tk.X)

        ttk.Label(params, text="White thresh:", width=12).grid(row=0, column=0, sticky=tk.W)
        self.flipover_thresh_var = tk.StringVar(value="0.5")
        ttk.Combobox(params, textvariable=self.flipover_thresh_var,
                     values=[f"{v:.2f}" for v in np.arange(0.3, 0.81, 0.05)], width=8).grid(row=0, column=1, padx=2)

        ttk.Label(params, text="Confirm rows:", width=12).grid(row=0, column=2, sticky=tk.W, padx=(10, 0))
        self.flipover_confirm_var = tk.StringVar(value="2")
        ttk.Combobox(params, textvariable=self.flipover_confirm_var,
                     values=[str(i) for i in range(1, 6)], width=8).grid(row=0, column=3, padx=2)

        # Result display label
        self.flipover_result_var = tk.StringVar(value="(not yet run)")
        ttk.Label(frame, textvariable=self.flipover_result_var,
                  foreground="blue", font=("TkDefaultFont", 9, "bold")).pack(pady=2)

        ttk.Label(frame, text="Scans binary image bottom→up for B→W flip").pack(pady=1)
        ttk.Button(frame, text="Find Flipover", command=self._apply_find_flipover).pack(pady=2)

    def _create_relative_gamma_controls(self, parent):
        """Create relative (split) gamma controls."""
        frame = ttk.LabelFrame(parent, text="35. Relative Gamma", padding="3")
        frame.pack(fill=tk.X, pady=2)

        # Row 1: percentile, uplift, subdue
        row1 = ttk.Frame(frame)
        row1.pack(fill=tk.X)

        ttk.Label(row1, text="Percentile:", width=9).grid(row=0, column=0, sticky=tk.W)
        self.relgamma_pct_var = tk.StringVar(value="50")
        ttk.Combobox(row1, textvariable=self.relgamma_pct_var,
                     values=[str(v) for v in [10, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90]],
                     width=5).grid(row=0, column=1, padx=2)

        ttk.Label(row1, text="Uplift γ:", width=7).grid(row=0, column=2, sticky=tk.W, padx=(6, 0))
        self.relgamma_uplift_var = tk.StringVar(value="2.0")
        ttk.Combobox(row1, textvariable=self.relgamma_uplift_var,
                     values=[f"{v:.1f}" for v in [1.2, 1.5, 1.8, 2.0, 2.5, 3.0, 4.0]],
                     width=5).grid(row=0, column=3, padx=2)

        ttk.Label(row1, text="Subdue γ:", width=8).grid(row=0, column=4, sticky=tk.W, padx=(6, 0))
        self.relgamma_subdue_var = tk.StringVar(value="0.75")
        ttk.Combobox(row1, textvariable=self.relgamma_subdue_var,
                     values=[f"{v:.2f}" for v in [0.25, 0.33, 0.50, 0.60, 0.75, 0.85, 0.90, 1.00]],
                     width=5).grid(row=0, column=5, padx=2)

        # Row 2: kernel dimensions and type
        row2 = ttk.Frame(frame)
        row2.pack(fill=tk.X, pady=(2, 0))

        ttk.Label(row2, text="Kernel H:", width=9).grid(row=0, column=0, sticky=tk.W)
        self.relgamma_kh_var = tk.StringVar(value="0")
        ttk.Combobox(row2, textvariable=self.relgamma_kh_var,
                     values=["0"] + [str(v) for v in [11, 21, 31, 41, 51, 71, 101]],
                     width=5).grid(row=0, column=1, padx=2)

        ttk.Label(row2, text="Kernel W:", width=7).grid(row=0, column=2, sticky=tk.W, padx=(6, 0))
        self.relgamma_kw_var = tk.StringVar(value="0")
        ttk.Combobox(row2, textvariable=self.relgamma_kw_var,
                     values=["0"] + [str(v) for v in [11, 21, 31, 41, 51, 71, 101]],
                     width=5).grid(row=0, column=3, padx=2)

        ttk.Label(row2, text="Type:", width=5).grid(row=0, column=4, sticky=tk.W, padx=(6, 0))
        self.relgamma_ktype_var = tk.StringVar(value="rectangular")
        ttk.Combobox(row2, textvariable=self.relgamma_ktype_var,
                     values=["rectangular", "elliptical"],
                     width=10, state='readonly').grid(row=0, column=5, padx=2)

        ttk.Label(frame, text="H=0 or W=0 → global mode (single percentile for whole mask)").pack(pady=1)
        ttk.Button(frame, text="Apply Relative Gamma", command=self._apply_relative_gamma).pack(pady=2)


    def _create_history_controls(self, parent):
        """Create pipeline and history controls."""
        history_frame = ttk.LabelFrame(parent, text="Pipeline Actions", padding="5")
        history_frame.pack(fill=tk.X, pady=(0, 5))

        # Row 1
        row1 = ttk.Frame(history_frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Button(row1, text="Undo Last", command=self._undo_last, width=15).pack(side=tk.LEFT, padx=2)
        ttk.Button(row1, text="Reset All", command=self._reset_image, width=15).pack(side=tk.LEFT, padx=2)

        # Row 2
        row2 = ttk.Frame(history_frame)
        row2.pack(fill=tk.X, pady=2)
        ttk.Button(row2, text="Apply Pipeline", command=self._apply_pipeline, width=15).pack(side=tk.LEFT, padx=2)
        ttk.Button(row2, text="Clear Pipeline", command=self._clear_pipeline, width=15).pack(side=tk.LEFT, padx=2)

        # Row 3
        row3 = ttk.Frame(history_frame)
        row3.pack(fill=tk.X, pady=2)
        ttk.Button(row3, text="Save Pipeline", command=self._save_pipeline, width=15).pack(side=tk.LEFT, padx=2)
        ttk.Button(row3, text="Load Pipeline", command=self._load_pipeline, width=15).pack(side=tk.LEFT, padx=2)

    def _create_pipeline_display(self, parent):
        """Create pipeline display area."""
        # Scrollable text widget
        text_frame = ttk.Frame(parent)
        text_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.pipeline_text = tk.Text(text_frame, height=6, width=80, wrap=tk.WORD, yscrollcommand=scrollbar.set)
        self.pipeline_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.pipeline_text.yview)

        # Make read-only
        self.pipeline_text.config(state=tk.DISABLED)

    def _create_image_display(self, parent):
        """Create before/after image display."""
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True)

        # Before image
        before_frame = ttk.LabelFrame(container, text="Before", padding="3")
        before_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))
        self.before_frame_label = before_frame  # Store reference for updating title

        self.before_canvas = tk.Canvas(before_frame, bg='gray20')
        self.before_canvas.pack(fill=tk.BOTH, expand=True)

        # After image
        after_frame = ttk.LabelFrame(container, text="After", padding="3")
        after_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(2, 0))
        self.after_frame_label = after_frame  # Store reference for updating title

        self.after_canvas = tk.Canvas(after_frame, bg='gray20')
        self.after_canvas.pack(fill=tk.BOTH, expand=True)

        # Bind resize event
        self.before_canvas.bind('<Configure>', self._on_canvas_resize)
        self.after_canvas.bind('<Configure>', self._on_canvas_resize)

        # Bind mouse events for crosshair
        self.before_canvas.bind('<Motion>', lambda e: self._on_mouse_motion(e, 'before'))
        self.before_canvas.bind('<Leave>', self._on_mouse_leave)
        self.after_canvas.bind('<Motion>', lambda e: self._on_mouse_motion(e, 'after'))
        self.after_canvas.bind('<Leave>', self._on_mouse_leave)

    def _on_canvas_resize(self, event):
        """Handle canvas resize event."""
        self._update_display()

    # =========================================================================
    # FILE OPERATIONS
    # =========================================================================

    def _load_image(self):
        """Load an image file."""
        file_path = filedialog.askopenfilename(
            title="Select Image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.gif"),
                ("All files", "*.*")
            ]
        )

        if file_path:
            self._load_image_from_path(file_path)

    def _load_image_from_path(self, file_path: str):
        """Load image from given path and auto-apply pipeline if enabled."""
        try:
            # Load image
            img = cv2.imread(file_path)
            if img is None:
                messagebox.showerror("Error", f"Failed to load image: {file_path}")
                return

            # Convert BGR to RGB
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            # Update file navigation
            self.current_file_path = file_path
            self.current_folder = os.path.dirname(file_path)
            self._update_folder_files()

            # Set images
            self.original_image = img.copy()
            self.current_image = img.copy()
            self.image_stack = [img.copy()]

            # Reset mask when loading new image
            self.current_mask = None
            self.mask_crop_region = None
            self.trace_index = None
            self.trace_label_var.set("")

            # Update display
            filename = os.path.basename(file_path)
            self.file_label_var.set(f"[{self.current_file_index + 1}/{len(self.folder_files)}] {filename}")
            self.status_var.set(f"Loaded: {filename}")

            # Auto-apply pipeline if we have one and auto-apply is enabled
            if self.pipeline and self.auto_apply_pipeline:
                self._apply_pipeline_silently()
            else:
                self._update_display()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {str(e)}")

    def _apply_pipeline_silently(self):
        """Apply the current pipeline without showing messages."""
        self.trace_index = None
        self.trace_label_var.set("")
        if not self.pipeline:
            return

        try:
            # Reset to original
            self.current_image = self.original_image.copy()
            self.image_stack = [self.current_image.copy()]
            self.current_mask = None
            self.mask_crop_region = None

            # Apply each step
            for step in self.pipeline:
                if step.processing_type == ProcessingType.CROP_ANNULAR:
                    self._replay_annular_step(step)
                else:
                    # Apply processing
                    result = self._apply_processing_step(step)
                    if result is not None:
                        self.current_image = result
                        self.image_stack.append(result.copy())

            self._update_display()
            self.status_var.set(f"Auto-applied pipeline ({len(self.pipeline)} steps)")

        except Exception as e:
            self.status_var.set(f"Pipeline auto-apply failed: {str(e)}")

    def _apply_processing_step(self, step: PipelineStep) -> Optional[np.ndarray]:
        """Apply a single processing step and return the result."""
        if self.current_mask is None:
            messagebox.showwarning("Warning", "No mask set. Create annular mask first.")
            return None

        try:
            params = step.parameters
            ptype = step.processing_type

            if ptype == ProcessingType.BACKGROUND_NORM:
                result = pixBackgroundNorm_masked(
                    self.current_image, self.current_mask,
                    sx=params['sx'], sy=params['sy'],
                    thresh=params['thresh'], mincount=params['mincount'],
                    bgval=params['bgval'],
                    smoothx=params['smoothx'], smoothy=params['smoothy']
                )

            elif ptype == ProcessingType.BACKGROUND_NORM_SIMPLE:
                result = pixBackgroundNormSimple_masked(
                    self.current_image, self.current_mask,
                    size=params['size'], bgval=params['bgval']
                )

            elif ptype == ProcessingType.CONTRAST_NORM:
                result = pixContrastNorm_masked(
                    self.current_image, self.current_mask,
                    sx=params['sx'], sy=params['sy'],
                    mindiff=params['mindiff']
                )

            elif ptype == ProcessingType.GRAY_NORMALIZE:
                result = pixGrayNormalize_masked(self.current_image, self.current_mask)

            elif ptype == ProcessingType.RANK_FILTER:
                result = pixRankFilterGray_masked(
                    self.current_image, self.current_mask,
                    size=params['size'], rank=params['rank']
                )

            elif ptype == ProcessingType.UNSHARP_MASK:
                result = pixUnsharpMaskingGray_masked(
                    self.current_image, self.current_mask,
                    halfwidth=params['halfwidth'], fract=params['fract']
                )

            elif ptype == ProcessingType.BILATERAL:
                result = bilateral_filter_masked(
                    self.current_image, self.current_mask,
                    d=params['d'], sigmaColor=params['sigmaColor'],
                    sigmaSpace=params['sigmaSpace']
                )

            elif ptype == ProcessingType.GAMMA:
                result = pixGammaCorrection_masked(
                    self.current_image, self.current_mask,
                    gamma=params['gamma']
                )

            elif ptype == ProcessingType.HISTOGRAM_EQ:
                result = pixEqualizeHistogram_masked(self.current_image, self.current_mask)

            elif ptype == ProcessingType.HOMOMORPHIC:
                result = homomorphic_filter_with_restoration_masked(
                    self.current_image, self.current_mask,
                    d0=params['d0'], gamma_l=params['gamma_l'],
                    gamma_h=params['gamma_h'],
                    restoration=params.get('restoration', 'log'),
                    root_n=params.get('root_n', 3.0)
                )

            elif ptype == ProcessingType.OTSU_GLOBAL:
                result = otsu_threshold_global_masked(self.current_image, self.current_mask)

            elif ptype == ProcessingType.OTSU_LOCAL:
                result = otsu_threshold_local_masked(
                    self.current_image, self.current_mask,
                    block_size=params['block_size'],
                    C=params['C']
                )

            elif ptype == ProcessingType.HOMOMORPHIC_BUTTERWORTH:
                result = butterworth_homomorphic_filter_masked(self.current_image, self.current_mask,
                    d0=params['d0'], gamma_l=params['gamma_l'], gamma_h=params['gamma_h'], n=params['n'])

            elif ptype == ProcessingType.HOMOMORPHIC_ROBUST:
                result = homomorphic_filter_robust_masked(self.current_image, self.current_mask,
                    d0=params['d0'], gamma_l=params['gamma_l'], gamma_h=params['gamma_h'])

            elif ptype == ProcessingType.SSR:
                result = single_scale_retinex_masked(self.current_image, self.current_mask, sigma=params['sigma'])

            elif ptype == ProcessingType.MSR:
                result = multi_scale_retinex_masked(self.current_image, self.current_mask,
                    sigmas=(params['sigma1'], params['sigma2'], params['sigma3']))

            elif ptype == ProcessingType.CLAHE:
                result = clahe_masked(self.current_image, self.current_mask,
                    clip_limit=params['clip_limit'], tile_grid_size=(params['grid_size'], params['grid_size']))

            elif ptype == ProcessingType.INTRINSIC_REFLECTANCE:
                result = intrinsic_reflectance_separation_masked(self.current_image, self.current_mask,
                    sigma_spatial=params['sigma_spatial'], sigma_range=params['sigma_range'], iterations=params['iterations'])

            elif ptype == ProcessingType.RESTORE_LOG:
                result = restore_log_masked(self.current_image, self.current_mask)

            elif ptype == ProcessingType.RESTORE_ROOT:
                result = restore_root_masked(self.current_image, self.current_mask, n=params['n'])

            elif ptype == ProcessingType.RESTORE_LINEAR:
                result = restore_linear_masked(self.current_image, self.current_mask, clip_percentile=params['clip_percentile'])

            elif ptype == ProcessingType.RESTORE_GAMMA_SUPPRESS:
                result = restore_gamma_suppress_masked(self.current_image, self.current_mask,
                    gamma_bright=params['gamma_bright'], gamma_dark=params['gamma_dark'],
                    final_restoration=params['final_restoration'], root_n=params['root_n'])

            elif ptype == ProcessingType.MORPH_DILATE:
                result = morphology_dilate_masked(self.current_image, self.current_mask,
                    kernel_size=params['kernel_size'], kernel_shape=params['kernel_shape'])

            elif ptype == ProcessingType.MORPH_ERODE:
                result = morphology_erode_masked(self.current_image, self.current_mask,
                    kernel_size=params['kernel_size'], kernel_shape=params['kernel_shape'])

            elif ptype == ProcessingType.MORPH_OPEN:
                result = morphology_open_masked(self.current_image, self.current_mask,
                    kernel_size=params['kernel_size'], kernel_shape=params['kernel_shape'])

            elif ptype == ProcessingType.MORPH_CLOSE:
                result = morphology_close_masked(self.current_image, self.current_mask,
                    kernel_size=params['kernel_size'], kernel_shape=params['kernel_shape'])

            # NEW: LAB and CLAHE operations
            elif ptype == ProcessingType.BGR_TO_LAB:
                lab_result = bgr_to_lab(self.current_image)
                result = lab_to_bgr(lab_result)  # Convert back for visualization

            elif ptype == ProcessingType.LAB_TO_BGR:
                lab_temp = bgr_to_lab(self.current_image)
                result = lab_to_bgr(lab_temp)

            elif ptype == ProcessingType.GAMMA_LAB_L:
                result = apply_gamma_to_lab_L(
                    self.current_image,
                    self.current_mask,
                    gamma=params['gamma']
                )

            elif ptype == ProcessingType.CLAHE_LAB_L:
                result = apply_clahe_to_lab_L(
                    self.current_image,
                    self.current_mask,
                    clip_limit=params['clip_limit'],
                    tile_grid_size=(params['tile_size'], params['tile_size'])
                )

            elif ptype == ProcessingType.CLAHE_BGR_CHANNELS:
                result = apply_clahe_to_bgr_channels(
                    self.current_image,
                    self.current_mask,
                    channels=params['channels'],
                    clip_limit=params['clip_limit'],
                    tile_grid_size=(params['tile_size'], params['tile_size'])
                )

            # NEW: Polar Unwrap, Otsu Local Block, Flipover Detection
            elif ptype == ProcessingType.POLAR_UNWRAP:
                result = polar_unwrap(
                    self.current_image,
                    center=(params['cx'], params['cy']),
                    inner_radius=params['inner_r'],
                    radial_depth=params['radial_depth']
                )
                # After polar unwrap, reset mask to full image
                if result is not None:
                    h, w = result.shape[:2] if result.ndim == 2 else result.shape[:2]
                    self.current_mask = np.ones((h, w), dtype=bool)
                    self.mask_crop_region = None

            elif ptype == ProcessingType.OTSU_LOCAL_BLOCK:
                result = otsu_threshold_local_block_masked(
                    self.current_image,
                    self.current_mask,
                    block_height=params['block_height'],
                    block_width=params['block_width']
                )

            elif ptype == ProcessingType.FIND_FLIPOVER:
                result_dict = find_flipover_row(
                    self.current_image,
                    white_threshold=params['white_threshold'],
                    confirmation_rows=params['confirmation_rows']
                )
                # Draw flipover line on image
                result = self.current_image.copy()
                if result.ndim == 2:
                    result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)
                fr = result_dict['flipover_row']
                fh = result_dict['flipover_height']
                if fr >= 0:
                    h_img, w_img = result.shape[:2]
                    cv2.line(result, (0, fr), (w_img - 1, fr), (0, 255, 0), 2)
                    cv2.putText(result, f"Flipover H={fh}px from bottom (row {fr})",
                                (5, max(fr - 8, 15)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)


            elif ptype == ProcessingType.RELATIVE_GAMMA:
                result = relative_gamma_masked(
                    self.current_image, self.current_mask,
                    percentile_cutoff=params['percentile_cutoff'],
                    uplift_gamma=params['uplift_gamma'],
                    subdue_gamma=params['subdue_gamma'],
                    kernel_height=params['kernel_height'],
                    kernel_width=params['kernel_width'],
                    kernel_type=params['kernel_type'],
                )

            else:
                return None

            # Convert to RGB for display
            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)

            return result

        except Exception as e:
            raise e

    def _update_folder_files(self):
        """Update the list of image files in the current folder."""
        if not self.current_folder:
            return

        try:
            all_files = os.listdir(self.current_folder)
            self.folder_files = sorted([
                f for f in all_files
                if os.path.splitext(f.lower())[1] in self.image_extensions
            ])

            # Find current file index
            if self.current_file_path:
                filename = os.path.basename(self.current_file_path)
                try:
                    self.current_file_index = self.folder_files.index(filename)
                except ValueError:
                    self.current_file_index = 0
        except Exception:
            self.folder_files = []
            self.current_file_index = -1

    def _previous_image(self):
        """Load the previous image in the folder."""
        if not self.folder_files:
            messagebox.showinfo("Info", "No folder loaded.")
            return

        if self.current_file_index > 0:
            self.current_file_index -= 1
            new_path = os.path.join(self.current_folder, self.folder_files[self.current_file_index])
            # Enable auto-apply when navigating
            self.auto_apply_pipeline = True
            self._load_image_from_path(new_path)
        else:
            messagebox.showinfo("Info", "Already at first image.")

    def _next_image(self):
        """Load the next image in the folder."""
        if not self.folder_files:
            messagebox.showinfo("Info", "No folder loaded.")
            return

        if self.current_file_index < len(self.folder_files) - 1:
            self.current_file_index += 1
            new_path = os.path.join(self.current_folder, self.folder_files[self.current_file_index])
            # Enable auto-apply when navigating
            self.auto_apply_pipeline = True
            self._load_image_from_path(new_path)
        else:
            messagebox.showinfo("Info", "Already at last image.")

    # =========================================================================
    # PROCESSING OPERATIONS
    # =========================================================================

    def _apply_annular_mask(self):
        """Apply annular mask: black out exterior, physically crop to bounding box."""
        if self.current_image is None:
            messagebox.showwarning("Warning", "Load an image first.")
            return

        try:
            cx = int(self.annular_cx_var.get())
            cy = int(self.annular_cy_var.get())
            outer = int(self.annular_outer_var.get())
            inner = int(self.annular_inner_var.get())

            gray = rgb2gray(self.current_image)
            full_mask = create_annular_mask(gray.shape, (cx, cy), outer, inner)

            rows, cols = np.where(full_mask)
            if len(rows) == 0 or len(cols) == 0:
                messagebox.showerror("Error", "Mask is empty. Check parameters.")
                return

            # Bounding box with 10 % padding
            min_row, max_row = rows.min(), rows.max()
            min_col, max_col = cols.min(), cols.max()
            pad_h = int((max_row - min_row + 1) * 0.10)
            pad_w = int((max_col - min_col + 1) * 0.10)
            img_h, img_w = self.current_image.shape[:2]
            crop_top  = max(0, min_row - pad_h)
            crop_bot  = min(img_h, max_row + pad_h + 1)
            crop_left = max(0, min_col - pad_w)
            crop_right = min(img_w, max_col + pad_w + 1)

            # Black out pixels outside the annular mask on the full image
            masked_full = self.current_image.copy()
            if masked_full.ndim == 3:
                for c in range(masked_full.shape[2]):
                    masked_full[:, :, c] = np.where(full_mask, masked_full[:, :, c], 0)
            else:
                masked_full = np.where(full_mask, masked_full, 0).astype(masked_full.dtype)

            # Physically crop image and mask to the bounding box
            result = masked_full[crop_top:crop_bot, crop_left:crop_right].copy()
            self.current_mask = full_mask[crop_top:crop_bot, crop_left:crop_right].copy()

            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)

            # No display-level crop needed — the image IS the cropped region
            self.mask_crop_region = None

            params = {
                'cx': cx, 'cy': cy,
                'outer_radius': outer, 'inner_radius': inner,
                # Store crop offsets so replay can reproduce the exact crop
                'crop_top': crop_top, 'crop_bot': crop_bot,
                'crop_left': crop_left, 'crop_right': crop_right,
            }
            self._add_to_pipeline(ProcessingType.CROP_ANNULAR, params, result)

            self._update_display()
            self.status_var.set(
                f"Annular mask: center=({cx},{cy}), outer={outer}, inner={inner}, "
                f"cropped to {result.shape[1]}×{result.shape[0]}")

        except ValueError:
            messagebox.showerror("Error", "Invalid annular mask parameters.")

    def _apply_background_norm(self):
        """Apply background normalization."""
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return

        try:
            sx = int(self.bg_sx_var.get())
            sy = int(self.bg_sy_var.get())
            thresh = int(self.bg_thresh_var.get())
            mincount = int(self.bg_mincount_var.get())
            bgval = int(self.bg_bgval_var.get())
            smoothx = int(self.bg_smoothx_var.get())
            smoothy = int(self.bg_smoothy_var.get())

            result = pixBackgroundNorm_masked(
                self.current_image, self.current_mask,
                sx=sx, sy=sy, thresh=thresh, mincount=mincount,
                bgval=bgval, smoothx=smoothx, smoothy=smoothy
            )

            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)

            params = {
                'sx': sx, 'sy': sy, 'thresh': thresh, 'mincount': mincount,
                'bgval': bgval, 'smoothx': smoothx, 'smoothy': smoothy
            }
            self._add_to_pipeline(ProcessingType.BACKGROUND_NORM, params, result)
            self._update_display()
            self.status_var.set(f"Background normalization applied")

        except Exception as e:
            messagebox.showerror("Error", f"Background norm failed: {str(e)}")

    def _apply_background_norm_simple(self):
        """Apply simple background normalization."""
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return

        try:
            size = int(self.bg_simple_size_var.get())
            bgval = int(self.bg_simple_bgval_var.get())

            result = pixBackgroundNormSimple_masked(
                self.current_image, self.current_mask,
                size=size, bgval=bgval
            )

            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)

            params = {'size': size, 'bgval': bgval}
            self._add_to_pipeline(ProcessingType.BACKGROUND_NORM_SIMPLE, params, result)
            self._update_display()
            self.status_var.set(f"Background normalization (simple) applied")

        except Exception as e:
            messagebox.showerror("Error", f"Background norm simple failed: {str(e)}")

    def _apply_contrast_norm(self):
        """Apply contrast normalization."""
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return

        try:
            sx = int(self.contrast_sx_var.get())
            sy = int(self.contrast_sy_var.get())
            mindiff = int(self.contrast_mindiff_var.get())

            result = pixContrastNorm_masked(
                self.current_image, self.current_mask,
                sx=sx, sy=sy, mindiff=mindiff
            )

            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)

            params = {'sx': sx, 'sy': sy, 'mindiff': mindiff}
            self._add_to_pipeline(ProcessingType.CONTRAST_NORM, params, result)
            self._update_display()
            self.status_var.set(f"Contrast normalization applied")

        except Exception as e:
            messagebox.showerror("Error", f"Contrast norm failed: {str(e)}")

    def _apply_gray_normalize(self):
        """Apply gray normalization."""
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return

        try:
            result = pixGrayNormalize_masked(self.current_image, self.current_mask)

            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)

            self._add_to_pipeline(ProcessingType.GRAY_NORMALIZE, {}, result)
            self._update_display()
            self.status_var.set("Gray normalization applied")

        except Exception as e:
            messagebox.showerror("Error", f"Gray normalize failed: {str(e)}")

    def _apply_rank_filter(self):
        """Apply rank filter."""
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return

        try:
            size = int(self.rank_size_var.get())
            rank = float(self.rank_rank_var.get())

            result = pixRankFilterGray_masked(
                self.current_image, self.current_mask,
                size=size, rank=rank
            )

            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)

            params = {'size': size, 'rank': rank}
            self._add_to_pipeline(ProcessingType.RANK_FILTER, params, result)
            self._update_display()
            self.status_var.set(f"Rank filter applied: size={size}, rank={rank}")

        except Exception as e:
            messagebox.showerror("Error", f"Rank filter failed: {str(e)}")

    def _apply_unsharp_mask(self):
        """Apply unsharp masking."""
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return

        try:
            halfwidth = int(self.unsharp_hw_var.get())
            fract = float(self.unsharp_fract_var.get())

            result = pixUnsharpMaskingGray_masked(
                self.current_image, self.current_mask,
                halfwidth=halfwidth, fract=fract
            )

            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)

            params = {'halfwidth': halfwidth, 'fract': fract}
            self._add_to_pipeline(ProcessingType.UNSHARP_MASK, params, result)
            self._update_display()
            self.status_var.set(f"Unsharp masking applied")

        except Exception as e:
            messagebox.showerror("Error", f"Unsharp mask failed: {str(e)}")

    def _apply_bilateral(self):
        """Apply bilateral filter."""
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return

        try:
            d = int(self.bilateral_d_var.get())
            sigmaColor = float(self.bilateral_sc_var.get())
            sigmaSpace = float(self.bilateral_ss_var.get())

            result = bilateral_filter_masked(
                self.current_image, self.current_mask,
                d=d, sigmaColor=sigmaColor, sigmaSpace=sigmaSpace
            )

            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)

            params = {'d': d, 'sigmaColor': sigmaColor, 'sigmaSpace': sigmaSpace}
            self._add_to_pipeline(ProcessingType.BILATERAL, params, result)
            self._update_display()
            self.status_var.set(f"Bilateral filter applied")

        except Exception as e:
            messagebox.showerror("Error", f"Bilateral filter failed: {str(e)}")

    def _apply_gamma(self):
        """Apply gamma correction."""
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return

        try:
            gamma = float(self.gamma_var.get())

            result = pixGammaCorrection_masked(
                self.current_image, self.current_mask, gamma=gamma
            )

            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)

            params = {'gamma': gamma}
            self._add_to_pipeline(ProcessingType.GAMMA, params, result)
            self._update_display()
            self.status_var.set(f"Gamma correction applied: γ={gamma}")

        except Exception as e:
            messagebox.showerror("Error", f"Gamma correction failed: {str(e)}")

    def _apply_histogram_eq(self):
        """Apply histogram equalization."""
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return

        try:
            result = pixEqualizeHistogram_masked(self.current_image, self.current_mask)

            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)

            self._add_to_pipeline(ProcessingType.HISTOGRAM_EQ, {}, result)
            self._update_display()
            self.status_var.set("Histogram equalization applied")

        except Exception as e:
            messagebox.showerror("Error", f"Histogram equalization failed: {str(e)}")

    def _apply_homomorphic(self):
        """Apply homomorphic filter."""
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return

        try:
            d0 = float(self.homo_d0_var.get())
            gamma_l = float(self.homo_gl_var.get())
            gamma_h = float(self.homo_gh_var.get())
            restoration = self.homo_restoration_var.get()
            root_n = float(self.homo_root_n_var.get())

            result = homomorphic_filter_with_restoration_masked(
                self.current_image, self.current_mask,
                d0=d0, gamma_l=gamma_l, gamma_h=gamma_h,
                restoration=restoration, root_n=root_n
            )

            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)

            params = {
                'd0': d0, 'gamma_l': gamma_l, 'gamma_h': gamma_h,
                'restoration': restoration, 'root_n': root_n
            }
            self._add_to_pipeline(ProcessingType.HOMOMORPHIC, params, result)
            self._update_display()
            self.status_var.set(f"Homomorphic filter applied")

        except Exception as e:
            messagebox.showerror("Error", f"Homomorphic filter failed: {str(e)}")

    def _apply_otsu_global(self):
        """Apply global Otsu thresholding."""
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return

        try:
            result = otsu_threshold_global_masked(self.current_image, self.current_mask)

            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)

            self._add_to_pipeline(ProcessingType.OTSU_GLOBAL, {}, result)
            self._update_display()
            self.status_var.set("Otsu global thresholding applied")

        except Exception as e:
            messagebox.showerror("Error", f"Otsu global failed: {str(e)}")

    def _apply_otsu_local(self):
        """Apply local Otsu thresholding."""
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return

        try:
            block_size = int(self.otsu_block_var.get())
            C = float(self.otsu_c_var.get())

            result = otsu_threshold_local_masked(
                self.current_image, self.current_mask,
                block_size=block_size, C=C
            )

            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)

            params = {'block_size': block_size, 'C': C}
            self._add_to_pipeline(ProcessingType.OTSU_LOCAL, params, result)
            self._update_display()
            self.status_var.set(f"Otsu local thresholding applied")

        except Exception as e:
            messagebox.showerror("Error", f"Otsu local failed: {str(e)}")

    # =========================================================================
    # NEW METHODS - APPLY FUNCTIONS (Add these AFTER existing _apply methods)
    # =========================================================================

    def _apply_homo_butterworth(self):
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return
        try:
            d0 = float(self.homo_butter_d0_var.get())
            gamma_l = float(self.homo_butter_gl_var.get())
            gamma_h = float(self.homo_butter_gh_var.get())
            n = float(self.homo_butter_n_var.get())
            result = butterworth_homomorphic_filter_masked(self.current_image, self.current_mask, d0=d0, gamma_l=gamma_l, gamma_h=gamma_h, n=n)
            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)
            params = {'d0': d0, 'gamma_l': gamma_l, 'gamma_h': gamma_h, 'n': n}
            self._add_to_pipeline(ProcessingType.HOMOMORPHIC_BUTTERWORTH, params, result)
            self._update_display()
            self.status_var.set("Homomorphic Butterworth applied")
        except Exception as e:
            messagebox.showerror("Error", f"Homomorphic Butterworth failed: {str(e)}")

    def _apply_homo_robust(self):
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return
        try:
            d0 = float(self.homo_robust_d0_var.get())
            gamma_l = float(self.homo_robust_gl_var.get())
            gamma_h = float(self.homo_robust_gh_var.get())
            result = homomorphic_filter_robust_masked(self.current_image, self.current_mask, d0=d0, gamma_l=gamma_l, gamma_h=gamma_h)
            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)
            params = {'d0': d0, 'gamma_l': gamma_l, 'gamma_h': gamma_h}
            self._add_to_pipeline(ProcessingType.HOMOMORPHIC_ROBUST, params, result)
            self._update_display()
            self.status_var.set("Homomorphic Robust applied")
        except Exception as e:
            messagebox.showerror("Error", f"Homomorphic Robust failed: {str(e)}")

    def _apply_ssr(self):
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return
        try:
            sigma = float(self.ssr_sigma_var.get())
            result = single_scale_retinex_masked(self.current_image, self.current_mask, sigma=sigma)
            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)
            params = {'sigma': sigma}
            self._add_to_pipeline(ProcessingType.SSR, params, result)
            self._update_display()
            self.status_var.set(f"SSR applied: sigma={sigma}")
        except Exception as e:
            messagebox.showerror("Error", f"SSR failed: {str(e)}")

    def _apply_msr(self):
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return
        try:
            s1 = float(self.msr_s1_var.get())
            s2 = float(self.msr_s2_var.get())
            s3 = float(self.msr_s3_var.get())
            result = multi_scale_retinex_masked(self.current_image, self.current_mask, sigmas=(s1, s2, s3))
            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)
            params = {'sigma1': s1, 'sigma2': s2, 'sigma3': s3}
            self._add_to_pipeline(ProcessingType.MSR, params, result)
            self._update_display()
            self.status_var.set(f"MSR applied: sigmas=({s1},{s2},{s3})")
        except Exception as e:
            messagebox.showerror("Error", f"MSR failed: {str(e)}")

    def _apply_clahe(self):
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return
        try:
            clip_limit = float(self.clahe_clip_var.get())
            grid_size = int(self.clahe_grid_var.get())
            result = clahe_masked(self.current_image, self.current_mask, clip_limit=clip_limit, tile_grid_size=(grid_size, grid_size))
            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)
            params = {'clip_limit': clip_limit, 'grid_size': grid_size}
            self._add_to_pipeline(ProcessingType.CLAHE, params, result)
            self._update_display()
            self.status_var.set(f"CLAHE applied: clip={clip_limit}, grid={grid_size}")
        except Exception as e:
            messagebox.showerror("Error", f"CLAHE failed: {str(e)}")

    def _apply_intrinsic(self):
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return
        try:
            sigma_spatial = float(self.intrinsic_spatial_var.get())
            sigma_range = float(self.intrinsic_range_var.get())
            iterations = int(self.intrinsic_iter_var.get())
            result = intrinsic_reflectance_separation_masked(self.current_image, self.current_mask, sigma_spatial=sigma_spatial, sigma_range=sigma_range, iterations=iterations)
            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)
            params = {'sigma_spatial': sigma_spatial, 'sigma_range': sigma_range, 'iterations': iterations}
            self._add_to_pipeline(ProcessingType.INTRINSIC_REFLECTANCE, params, result)
            self._update_display()
            self.status_var.set("Intrinsic Reflectance applied")
        except Exception as e:
            messagebox.showerror("Error", f"Intrinsic Reflectance failed: {str(e)}")

    def _apply_restore_log(self):
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return
        try:
            result = restore_log_masked(self.current_image, self.current_mask)
            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)
            self._add_to_pipeline(ProcessingType.RESTORE_LOG, {}, result)
            self._update_display()
            self.status_var.set("Restore Log applied")
        except Exception as e:
            messagebox.showerror("Error", f"Restore Log failed: {str(e)}")

    def _apply_restore_root(self):
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return
        try:
            n = float(self.restore_root_n_var.get())
            result = restore_root_masked(self.current_image, self.current_mask, n=n)
            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)
            params = {'n': n}
            self._add_to_pipeline(ProcessingType.RESTORE_ROOT, params, result)
            self._update_display()
            self.status_var.set(f"Restore Root applied: n={n}")
        except Exception as e:
            messagebox.showerror("Error", f"Restore Root failed: {str(e)}")

    def _apply_restore_linear(self):
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return
        try:
            clip_percentile = float(self.restore_linear_clip_var.get())
            result = restore_linear_masked(self.current_image, self.current_mask, clip_percentile=clip_percentile)
            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)
            params = {'clip_percentile': clip_percentile}
            self._add_to_pipeline(ProcessingType.RESTORE_LINEAR, params, result)
            self._update_display()
            self.status_var.set(f"Restore Linear applied: clip={clip_percentile}")
        except Exception as e:
            messagebox.showerror("Error", f"Restore Linear failed: {str(e)}")

    def _apply_restore_gamma_suppress(self):
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return
        try:
            gamma_bright = float(self.restore_gs_bright_var.get())
            gamma_dark = float(self.restore_gs_dark_var.get())
            final_restoration = self.restore_gs_final_var.get()
            root_n = float(self.restore_gs_root_n_var.get())
            result = restore_gamma_suppress_masked(self.current_image, self.current_mask, gamma_bright=gamma_bright, gamma_dark=gamma_dark, final_restoration=final_restoration, root_n=root_n)
            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)
            params = {'gamma_bright': gamma_bright, 'gamma_dark': gamma_dark, 'final_restoration': final_restoration, 'root_n': root_n}
            self._add_to_pipeline(ProcessingType.RESTORE_GAMMA_SUPPRESS, params, result)
            self._update_display()
            self.status_var.set("Restore Gamma Suppress applied")
        except Exception as e:
            messagebox.showerror("Error", f"Restore Gamma Suppress failed: {str(e)}")

    def _apply_morph_dilate(self):
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return
        try:
            kernel_size = int(self.morph_dilate_size_var.get())
            kernel_shape = self.morph_dilate_shape_var.get()
            result = morphology_dilate_masked(self.current_image, self.current_mask, kernel_size=kernel_size, kernel_shape=kernel_shape)
            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)
            params = {'kernel_size': kernel_size, 'kernel_shape': kernel_shape}
            self._add_to_pipeline(ProcessingType.MORPH_DILATE, params, result)
            self._update_display()
            self.status_var.set(f"Dilate applied: size={kernel_size}, shape={kernel_shape}")
        except Exception as e:
            messagebox.showerror("Error", f"Dilate failed: {str(e)}")

    def _apply_morph_erode(self):
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return
        try:
            kernel_size = int(self.morph_erode_size_var.get())
            kernel_shape = self.morph_erode_shape_var.get()
            result = morphology_erode_masked(self.current_image, self.current_mask, kernel_size=kernel_size, kernel_shape=kernel_shape)
            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)
            params = {'kernel_size': kernel_size, 'kernel_shape': kernel_shape}
            self._add_to_pipeline(ProcessingType.MORPH_ERODE, params, result)
            self._update_display()
            self.status_var.set(f"Erode applied: size={kernel_size}, shape={kernel_shape}")
        except Exception as e:
            messagebox.showerror("Error", f"Erode failed: {str(e)}")

    def _apply_morph_open(self):
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return
        try:
            kernel_size = int(self.morph_open_size_var.get())
            kernel_shape = self.morph_open_shape_var.get()
            result = morphology_open_masked(self.current_image, self.current_mask, kernel_size=kernel_size, kernel_shape=kernel_shape)
            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)
            params = {'kernel_size': kernel_size, 'kernel_shape': kernel_shape}
            self._add_to_pipeline(ProcessingType.MORPH_OPEN, params, result)
            self._update_display()
            self.status_var.set(f"Open applied: size={kernel_size}, shape={kernel_shape}")
        except Exception as e:
            messagebox.showerror("Error", f"Open failed: {str(e)}")

    def _apply_morph_close(self):
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return
        try:
            kernel_size = int(self.morph_close_size_var.get())
            kernel_shape = self.morph_close_shape_var.get()
            result = morphology_close_masked(self.current_image, self.current_mask, kernel_size=kernel_size, kernel_shape=kernel_shape)
            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)
            params = {'kernel_size': kernel_size, 'kernel_shape': kernel_shape}
            self._add_to_pipeline(ProcessingType.MORPH_CLOSE, params, result)
            self._update_display()
            self.status_var.set(f"Close applied: size={kernel_size}, shape={kernel_shape}")
        except Exception as e:
            messagebox.showerror("Error", f"Close failed: {str(e)}")

    # =========================================================================
    # NEW LAB AND CLAHE APPLY METHODS
    # =========================================================================

    def _apply_bgr_to_lab(self):
        """Convert BGR to LAB color space."""
        if self.current_image is None:
            messagebox.showwarning("Warning", "Load image first.")
            return
        try:
            # Convert to LAB (this returns LAB float32)
            lab_result = bgr_to_lab(self.current_image)

            # For visualization, convert back to BGR
            # But note: actual LAB data is stored in the pipeline
            result_bgr = lab_to_bgr(lab_result)

            params = {}
            self._add_to_pipeline(ProcessingType.BGR_TO_LAB, params, result_bgr)
            self._update_display()
            self.status_var.set("Converted BGR to LAB (visualized as BGR)")
        except Exception as e:
            messagebox.showerror("Error", f"BGR to LAB failed: {str(e)}")

    def _apply_lab_to_bgr(self):
        """Convert LAB back to BGR color space."""
        if self.current_image is None:
            messagebox.showwarning("Warning", "Load image first.")
            return
        try:
            # Assume current image is in BGR, convert to LAB then back
            # This is mainly for pipeline consistency
            lab_temp = bgr_to_lab(self.current_image)
            result = lab_to_bgr(lab_temp)

            params = {}
            self._add_to_pipeline(ProcessingType.LAB_TO_BGR, params, result)
            self._update_display()
            self.status_var.set("Converted LAB to BGR")
        except Exception as e:
            messagebox.showerror("Error", f"LAB to BGR failed: {str(e)}")

    def _apply_gamma_lab_l(self):
        """Apply gamma correction to LAB L channel."""
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return
        try:
            gamma = float(self.gamma_lab_l_var.get())

            result = apply_gamma_to_lab_L(
                self.current_image,
                self.current_mask,
                gamma=gamma
            )

            params = {'gamma': gamma}
            self._add_to_pipeline(ProcessingType.GAMMA_LAB_L, params, result)
            self._update_display()
            self.status_var.set(f"Gamma {gamma} applied to LAB L channel")
        except Exception as e:
            messagebox.showerror("Error", f"Gamma LAB L failed: {str(e)}")

    def _apply_clahe_lab_l(self):
        """Apply CLAHE to LAB L channel."""
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return
        try:
            clip_limit = float(self.clahe_lab_l_clip_var.get())
            tile_size = int(self.clahe_lab_l_tile_var.get())

            result = apply_clahe_to_lab_L(
                self.current_image,
                self.current_mask,
                clip_limit=clip_limit,
                tile_grid_size=(tile_size, tile_size)
            )

            params = {'clip_limit': clip_limit, 'tile_size': tile_size}
            self._add_to_pipeline(ProcessingType.CLAHE_LAB_L, params, result)
            self._update_display()
            self.status_var.set(f"CLAHE applied to LAB L: clip={clip_limit}, tile={tile_size}")
        except Exception as e:
            messagebox.showerror("Error", f"CLAHE LAB L failed: {str(e)}")

    def _apply_clahe_bgr_channels(self):
        """Apply CLAHE to selected BGR channels."""
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return
        try:
            # Get selected channels
            channels = []
            if self.clahe_bgr_blue_var.get():
                channels.append("blue")
            if self.clahe_bgr_green_var.get():
                channels.append("green")
            if self.clahe_bgr_red_var.get():
                channels.append("red")

            if not channels:
                messagebox.showwarning("Warning", "Please select at least one channel.")
                return

            clip_limit = float(self.clahe_bgr_clip_var.get())
            tile_size = int(self.clahe_bgr_tile_var.get())

            result = apply_clahe_to_bgr_channels(
                self.current_image,
                self.current_mask,
                channels=channels,
                clip_limit=clip_limit,
                tile_grid_size=(tile_size, tile_size)
            )

            params = {
                'channels': channels,
                'clip_limit': clip_limit,
                'tile_size': tile_size
            }
            self._add_to_pipeline(ProcessingType.CLAHE_BGR_CHANNELS, params, result)
            self._update_display()
            self.status_var.set(f"CLAHE applied to {','.join(channels)}: clip={clip_limit}, tile={tile_size}")
        except Exception as e:
            messagebox.showerror("Error", f"CLAHE BGR Channels failed: {str(e)}")

    # =========================================================================
    # NEW: POLAR UNWRAP / LOCAL BLOCK OTSU / FLIPOVER DETECTION APPLY
    # =========================================================================

    def _apply_polar_unwrap(self):
        """Apply polar unwrap to convert annular band to rectangular strip."""
        if self.current_image is None:
            messagebox.showwarning("Warning", "Load an image first.")
            return
        try:
            cx = int(self.polar_cx_var.get())
            cy = int(self.polar_cy_var.get())
            inner_r = float(self.polar_inner_r_var.get())
            depth = int(self.polar_depth_var.get())

            result = polar_unwrap(
                self.current_image, center=(cx, cy),
                inner_radius=inner_r, radial_depth=depth
            )

            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)

            # After polar unwrap, the mask becomes the entire rectangular image
            # (all pixels valid) and the crop region is reset
            h, w = result.shape[:2]
            self.current_mask = np.ones((h, w), dtype=bool)
            self.mask_crop_region = None

            params = {'cx': cx, 'cy': cy, 'inner_r': inner_r, 'radial_depth': depth}
            self._add_to_pipeline(ProcessingType.POLAR_UNWRAP, params, result)
            self._update_display()
            self.status_var.set(
                f"Polar unwrap: center=({cx},{cy}), R_inner={inner_r:.0f}, "
                f"depth={depth} → {result.shape[1]}×{result.shape[0]}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Polar unwrap failed: {str(e)}")

    def _apply_otsu_local_block(self):
        """Apply localised block Otsu thresholding."""
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return
        try:
            block_h = int(self.otsu_block_h_var.get())
            block_w = int(self.otsu_block_w_var.get())

            result = otsu_threshold_local_block_masked(
                self.current_image, self.current_mask,
                block_height=block_h, block_width=block_w
            )

            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)

            params = {'block_height': block_h, 'block_width': block_w}
            self._add_to_pipeline(ProcessingType.OTSU_LOCAL_BLOCK, params, result)
            self._update_display()
            self.status_var.set(f"Otsu local block: H={block_h}, W={block_w}")
        except Exception as e:
            messagebox.showerror("Error", f"Otsu local block failed: {str(e)}")

    def _apply_find_flipover(self):
        """Find the flipover row (black→white transition from bottom)."""
        if self.current_image is None:
            messagebox.showwarning("Warning", "Load an image first.")
            return
        try:
            white_thresh = float(self.flipover_thresh_var.get())
            confirm = int(self.flipover_confirm_var.get())

            result_dict = find_flipover_row(
                self.current_image,
                white_threshold=white_thresh,
                confirmation_rows=confirm
            )

            fh = result_dict['flipover_height']
            fr = result_dict['flipover_row']

            # Draw a horizontal line on the image at the flipover row
            result = self.current_image.copy()
            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)

            h_img, w_img = result.shape[:2]
            if fr >= 0:
                # Draw green line at flipover row
                cv2.line(result, (0, fr), (w_img - 1, fr), (0, 255, 0), 2)
                # Label
                cv2.putText(result, f"Flipover H={fh}px from bottom (row {fr})",
                            (5, max(fr - 8, 15)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
                self.flipover_result_var.set(
                    f"Flipover at height {fh} from bottom (row {fr})")
            else:
                self.flipover_result_var.set("No flipover detected")

            params = {'white_threshold': white_thresh, 'confirmation_rows': confirm}
            self._add_to_pipeline(ProcessingType.FIND_FLIPOVER, params, result)
            self._update_display()
            self.status_var.set(
                f"Flipover: height={fh} from bottom, row={fr}")
        except Exception as e:
            messagebox.showerror("Error", f"Find flipover failed: {str(e)}")

    def _apply_relative_gamma(self):
        """Apply relative (split) gamma correction."""
        if self.current_image is None or self.current_mask is None:
            messagebox.showwarning("Warning", "Load image and create mask first.")
            return
        try:
            pct     = float(self.relgamma_pct_var.get())
            uplift  = float(self.relgamma_uplift_var.get())
            subdue  = float(self.relgamma_subdue_var.get())
            kh      = int(self.relgamma_kh_var.get())
            kw      = int(self.relgamma_kw_var.get())
            ktype   = self.relgamma_ktype_var.get()

            result = relative_gamma_masked(
                self.current_image, self.current_mask,
                percentile_cutoff=pct,
                uplift_gamma=uplift,
                subdue_gamma=subdue,
                kernel_height=kh,
                kernel_width=kw,
                kernel_type=ktype,
            )

            if result.ndim == 2:
                result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)

            params = {
                'percentile_cutoff': pct,
                'uplift_gamma': uplift, 'subdue_gamma': subdue,
                'kernel_height': kh, 'kernel_width': kw,
                'kernel_type': ktype,
            }
            self._add_to_pipeline(ProcessingType.RELATIVE_GAMMA, params, result)
            self._update_display()
            mode = "global" if (kh <= 0 or kw <= 0) else f"local {kh}×{kw} {ktype}"
            self.status_var.set(
                f"Relative gamma: p={pct}%, ↑γ={uplift}, ↓γ={subdue}, {mode}")
        except Exception as e:
            messagebox.showerror("Error", f"Relative gamma failed: {str(e)}")


    # =========================================================================
    # PIPELINE MANAGEMENT
    # =========================================================================

    def _add_to_pipeline(self, proc_type: ProcessingType, params: dict, result_image: Optional[np.ndarray]):
        """Add a processing step to the pipeline."""
        self.trace_index = None
        self.trace_label_var.set("")
        step = PipelineStep(processing_type=proc_type, parameters=params)
        self.pipeline.append(step)

        if result_image is not None:
            self.current_image = result_image
            self.image_stack.append(result_image.copy())

        # Enable auto-apply for subsequent images
        self.auto_apply_pipeline = True

        self._update_pipeline_display()

    def _undo_last(self):
        """Undo the last processing step by replaying the pipeline from scratch."""
        self.trace_index = None
        self.trace_label_var.set("")
        if len(self.pipeline) == 0:
            messagebox.showinfo("Info", "No steps to undo.")
            return

        if self.original_image is None:
            return

        # Remove the last pipeline step
        self.pipeline.pop()

        # Replay the remaining pipeline from the original image.
        # This guarantees the image, mask, and crop state are fully
        # consistent — no stale stack entries.
        self.current_image = self.original_image.copy()
        self.image_stack = [self.current_image.copy()]
        self.current_mask = None
        self.mask_crop_region = None

        for step in self.pipeline:
            if step.processing_type == ProcessingType.CROP_ANNULAR:
                self._replay_annular_step(step)
            else:
                result = self._apply_processing_step(step)
                if result is not None:
                    self.current_image = result
                    self.image_stack.append(result.copy())

        # Update auto-apply flag
        self.auto_apply_pipeline = len(self.pipeline) > 0

        self._update_pipeline_display()
        self._update_display()
        self.status_var.set("Undid last step")

    def _replay_annular_step(self, step: PipelineStep):
        """Replay a CROP_ANNULAR step during pipeline replay (undo / apply)."""
        params = step.parameters
        cx = params['cx']
        cy = params['cy']
        outer = params['outer_radius']
        inner = params['inner_radius']

        gray = rgb2gray(self.current_image)
        full_mask = create_annular_mask(gray.shape, (cx, cy), outer, inner)

        # Use stored crop bounds if available, otherwise recompute
        if 'crop_top' in params:
            crop_top   = params['crop_top']
            crop_bot   = params['crop_bot']
            crop_left  = params['crop_left']
            crop_right = params['crop_right']
        else:
            rows, cols = np.where(full_mask)
            if len(rows) == 0:
                return
            min_row, max_row = rows.min(), rows.max()
            min_col, max_col = cols.min(), cols.max()
            pad_h = int((max_row - min_row + 1) * 0.10)
            pad_w = int((max_col - min_col + 1) * 0.10)
            img_h, img_w = self.current_image.shape[:2]
            crop_top   = max(0, min_row - pad_h)
            crop_bot   = min(img_h, max_row + pad_h + 1)
            crop_left  = max(0, min_col - pad_w)
            crop_right = min(img_w, max_col + pad_w + 1)

        # Black out outside mask
        masked_full = self.current_image.copy()
        if masked_full.ndim == 3:
            for c in range(masked_full.shape[2]):
                masked_full[:, :, c] = np.where(full_mask, masked_full[:, :, c], 0)
        else:
            masked_full = np.where(full_mask, masked_full, 0).astype(masked_full.dtype)

        # Physically crop
        result = masked_full[crop_top:crop_bot, crop_left:crop_right].copy()
        self.current_mask = full_mask[crop_top:crop_bot, crop_left:crop_right].copy()
        self.mask_crop_region = None

        if result.ndim == 2:
            result = cv2.cvtColor(result, cv2.COLOR_GRAY2RGB)

        self.current_image = result
        self.image_stack.append(result.copy())

    def _reset_image(self):
        """Reset image to original."""
        if self.original_image is None:
            messagebox.showinfo("Info", "No image loaded.")
            return

        self.current_image = self.original_image.copy()
        self.image_stack = [self.original_image.copy()]
        self.pipeline = []
        self.current_mask = None
        self.mask_crop_region = None
        self.auto_apply_pipeline = False
        self.trace_index = None
        self.trace_label_var.set("")

        self._update_pipeline_display()
        self._update_display()
        self.status_var.set("Reset to original image")

    def _apply_pipeline(self):
        """Apply the current pipeline to the image."""
        self.trace_index = None
        self.trace_label_var.set("")
        if not self.pipeline:
            messagebox.showinfo("Info", "Pipeline is empty.")
            return

        if self.original_image is None:
            messagebox.showwarning("Warning", "Load an image first.")
            return

        try:
            # Reset to original
            self.current_image = self.original_image.copy()
            self.image_stack = [self.current_image.copy()]
            self.current_mask = None
            self.mask_crop_region = None

            # Apply each step
            for step in self.pipeline:
                if step.processing_type == ProcessingType.CROP_ANNULAR:
                    self._replay_annular_step(step)
                else:
                    # Apply processing
                    result = self._apply_processing_step(step)
                    if result is not None:
                        self.current_image = result
                        self.image_stack.append(result.copy())

            # Enable auto-apply
            self.auto_apply_pipeline = True

            self._update_display()
            self.status_var.set(f"Applied pipeline ({len(self.pipeline)} steps)")
            messagebox.showinfo("Success", f"Pipeline applied successfully.\n{len(self.pipeline)} steps executed.")

        except Exception as e:
            messagebox.showerror("Error", f"Pipeline application failed: {str(e)}")

    def _clear_pipeline(self):
        """Clear the current pipeline."""
        self.trace_index = None
        self.trace_label_var.set("")
        if not self.pipeline:
            messagebox.showinfo("Info", "Pipeline is already empty.")
            return

        confirm = messagebox.askyesno(
            "Confirm",
            "This will clear the current pipeline.\nContinue?"
        )

        if confirm:
            self.pipeline = []
            self.auto_apply_pipeline = False
            self._update_pipeline_display()
            self.status_var.set("Pipeline cleared")

    def _update_pipeline_display(self):
        """Update the pipeline display text."""
        self.pipeline_text.config(state=tk.NORMAL)
        self.pipeline_text.delete(1.0, tk.END)

        if not self.pipeline:
            self.pipeline_text.insert(tk.END, "No steps in pipeline")
        else:
            for i, step in enumerate(self.pipeline, 1):
                # Highlight the step being traced
                if self.trace_index is not None and i - 1 == self.trace_index:
                    self.pipeline_text.insert(tk.END, f"▶ {i}. {step}\n", "highlight")
                else:
                    self.pipeline_text.insert(tk.END, f"  {i}. {step}\n")

        # Configure highlight tag
        self.pipeline_text.tag_configure("highlight",
                                          background="#FFE066",
                                          font=("TkDefaultFont", 9, "bold"))

        # Auto-scroll to highlighted step
        if self.trace_index is not None and self.trace_index < len(self.pipeline):
            line_num = self.trace_index + 1
            self.pipeline_text.see(f"{line_num}.0")

        self.pipeline_text.config(state=tk.DISABLED)

    def _save_result(self):
        """Save the current processed image."""
        if self.current_image is None:
            messagebox.showwarning("Warning", "No image to save.")
            return

        file_path = filedialog.asksaveasfilename(
            title="Save Image",
            defaultextension=".png",
            filetypes=[
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg"),
                ("All files", "*.*")
            ]
        )

        if file_path:
            try:
                # Convert RGB to BGR for OpenCV
                if self.current_image.ndim == 3:
                    save_img = cv2.cvtColor(self.current_image, cv2.COLOR_RGB2BGR)
                else:
                    save_img = self.current_image

                cv2.imwrite(file_path, save_img)
                self.status_var.set(f"Saved: {file_path}")
                messagebox.showinfo("Success", f"Image saved to:\n{file_path}")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to save image: {str(e)}")

    def _save_pipeline(self):
        """Save the current pipeline to a file."""
        if not self.pipeline:
            messagebox.showinfo("Info", "Pipeline is empty.")
            return

        file_path = filedialog.asksaveasfilename(
            title="Save Pipeline",
            defaultextension=".txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )

        if file_path:
            try:
                with open(file_path, 'w') as f:
                    f.write("# Image Processing Pipeline\n")
                    f.write(f"# Steps: {len(self.pipeline)}\n\n")

                    for i, step in enumerate(self.pipeline):
                        f.write(f"[Step {i+1}]\n")
                        f.write(f"type={step.processing_type.name}\n")
                        for key, value in step.parameters.items():
                            f.write(f"{key}={value}\n")
                        f.write("\n")

                self.status_var.set(f"Pipeline saved: {file_path}")
                messagebox.showinfo("Success", f"Pipeline saved to:\n{file_path}")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to save pipeline: {str(e)}")

    def _load_pipeline(self):
        """Load a pipeline from a file."""
        file_path = filedialog.askopenfilename(
            title="Load Pipeline",
            filetypes=[
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )

        if file_path:
            try:
                with open(file_path, 'r') as f:
                    lines = f.readlines()

                # Parse pipeline
                new_pipeline = []
                current_step = None
                current_params = {}

                for line in lines:
                    line = line.strip()
                    if line.startswith('#') or not line:
                        continue

                    if line.startswith('[Step'):
                        # Save previous step
                        if current_step is not None:
                            new_pipeline.append(PipelineStep(
                                processing_type=current_step,
                                parameters=current_params
                            ))
                        current_step = None
                        current_params = {}

                    elif '=' in line:
                        key, value = line.split('=', 1)
                        if key == 'type':
                            current_step = ProcessingType[value]
                        else:
                            # Try to convert to appropriate type
                            try:
                                if '.' in value:
                                    current_params[key] = float(value)
                                else:
                                    current_params[key] = int(value)
                            except ValueError:
                                current_params[key] = value

                # Don't forget last step
                if current_step is not None:
                    new_pipeline.append(PipelineStep(
                        processing_type=current_step,
                        parameters=current_params
                    ))

                # Set the loaded pipeline - it will persist for subsequent images
                self.pipeline = new_pipeline
                self.auto_apply_pipeline = True
                self._update_pipeline_display()
                self.status_var.set(f"Pipeline loaded: {len(self.pipeline)} steps")
                messagebox.showinfo("Success",
                    f"Pipeline loaded from:\n{file_path}\n\n"
                    f"{len(self.pipeline)} steps loaded.\n\n"
                    "This pipeline will auto-apply to:\n"
                    "• Next/Previous images\n"
                    "• Click 'Apply Pipeline' to apply to current image")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load pipeline: {str(e)}")

    # =========================================================================
    # TRACE MODE — step through pipeline without modifying it
    # =========================================================================

    def _trace_prev(self):
        """Move trace view to the previous pipeline step."""
        if len(self.image_stack) < 2:
            self.status_var.set("Nothing to trace — pipeline is empty")
            return

        if self.trace_index is None:
            # Enter trace mode at the last step
            self.trace_index = len(self.image_stack) - 2
        else:
            self.trace_index = max(0, self.trace_index - 1)

        self._update_trace_display()

    def _trace_next(self):
        """Move trace view to the next pipeline step."""
        if len(self.image_stack) < 2:
            self.status_var.set("Nothing to trace — pipeline is empty")
            return

        if self.trace_index is None:
            # Not in trace mode — nothing to go forward to
            self.status_var.set("Press Trace Prev first to enter trace mode")
            return

        max_idx = len(self.image_stack) - 2
        if self.trace_index >= max_idx:
            # Already at last step — exit trace
            self._trace_exit()
            return

        self.trace_index = min(max_idx, self.trace_index + 1)
        self._update_trace_display()

    def _trace_exit(self):
        """Exit trace mode and return to live view."""
        self.trace_index = None
        self.trace_label_var.set("")
        self._update_pipeline_display()
        self._update_display()
        self.status_var.set("Exited trace mode — showing live pipeline output")

    def _update_trace_display(self):
        """Update display and labels for trace mode."""
        idx = self.trace_index
        n_steps = len(self.pipeline)
        n_stack = len(self.image_stack)

        # Determine step label
        if idx == 0:
            step_name = "Original → Step 1"
            if n_steps > 0:
                step_name += f": {self.pipeline[0].processing_type.value}"
        elif idx < n_steps:
            step_name = (f"Step {idx}: {self.pipeline[idx-1].processing_type.value}"
                         f" → Step {idx+1}: {self.pipeline[idx].processing_type.value}")
        else:
            step_name = f"Step {idx} → Step {idx+1}"

        self.trace_label_var.set(
            f"TRACE [{idx+1}/{n_stack-1}]  {step_name}")

        self._update_pipeline_display()
        self._update_display()
        self.status_var.set(
            f"Trace mode: viewing step {idx+1} of {n_stack-1}")

    def _update_display(self):
        """Update the before/after image display."""
        if self.current_image is None:
            return

        # Get canvas sizes
        before_width = self.before_canvas.winfo_width()
        before_height = self.before_canvas.winfo_height()
        after_width = self.after_canvas.winfo_width()
        after_height = self.after_canvas.winfo_height()

        # Minimum size check
        if before_width < 10 or before_height < 10:
            return

        # Get before image (previous state from stack)
        # In trace mode, show the step pair at trace_index
        if self.trace_index is not None and len(self.image_stack) > 1:
            idx = self.trace_index
            before_img = self.image_stack[idx]
            after_img  = self.image_stack[min(idx + 1, len(self.image_stack) - 1)]
        elif len(self.image_stack) > 1:
            before_img = self.image_stack[-2]  # Second to last
            after_img  = self.current_image
        else:
            before_img = self.original_image if self.original_image is not None else self.current_image
            after_img  = self.current_image

        # Update frame titles
        if self.trace_index is not None:
            idx = self.trace_index
            n = len(self.pipeline)
            before_title = f"Before — Step {idx}" if idx > 0 else "Before — Original"
            after_title  = f"After — Step {idx+1}" if idx + 1 <= n else f"After — Step {idx+1}"
            if idx < n:
                after_title += f": {self.pipeline[idx].processing_type.value}"
            if self.before_frame_label:
                self.before_frame_label.config(text=before_title)
            if self.after_frame_label:
                self.after_frame_label.config(text=after_title)
        else:
            if self.before_frame_label:
                self.before_frame_label.config(text="Before")
            if self.after_frame_label:
                self.after_frame_label.config(text="After")

        # Draw mask boundary overlay on the display copy (not on current_image)
        # This shows the annular ring edges without contaminating the data
        # Only draw if mask shape matches the after image (avoids trace mode mismatches)
        after_h, after_w = after_img.shape[:2]
        if (self.current_mask is not None
                and self.current_mask.shape == (after_h, after_w)
                and not self.current_mask.all()):
            after_img = after_img.copy()
            if after_img.ndim == 2:
                after_img = cv2.cvtColor(after_img, cv2.COLOR_GRAY2RGB)
            mask_uint8 = self.current_mask.astype(np.uint8) * 255
            contours, _ = cv2.findContours(mask_uint8, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
            cv2.drawContours(after_img, contours, -1, (0, 0, 255), 1)

        # If mask crop region is set, crop and scale both images
        if self.mask_crop_region is not None:
            crop_top, crop_bottom, crop_left, crop_right = self.mask_crop_region

            # Crop both images to the mask region
            before_img_cropped = before_img[crop_top:crop_bottom, crop_left:crop_right]
            after_img_cropped = after_img[crop_top:crop_bottom, crop_left:crop_right]

            # Scale using bicubic interpolation
            # Calculate target size (larger for better viewing)
            crop_h = crop_bottom - crop_top
            crop_w = crop_right - crop_left

            # Determine scaling factor to fit in canvas while maximizing size
            scale_w = (before_width - 10) / crop_w
            scale_h = (before_height - 10) / crop_h
            scale = min(scale_w, scale_h)

            # Apply minimum scale of 1.0 (no downscaling from cropped region)
            scale = max(scale, 1.0)

            target_w = int(crop_w * scale)
            target_h = int(crop_h * scale)

            # Scale with bicubic interpolation
            before_img = cv2.resize(before_img_cropped, (target_w, target_h), interpolation=cv2.INTER_CUBIC)
            after_img = cv2.resize(after_img_cropped, (target_w, target_h), interpolation=cv2.INTER_CUBIC)

        # Resize and display before image
        before_resized, before_info = self._resize_image_to_fit_with_info(before_img, before_width - 10, before_height - 10)
        self.before_photo = ImageTk.PhotoImage(Image.fromarray(before_resized))
        self.before_canvas.delete("all")
        before_x = before_width // 2
        before_y = before_height // 2
        self.before_canvas.create_image(
            before_x, before_y,
            image=self.before_photo, anchor=tk.CENTER
        )

        # Store display info for before panel (original image, offset, scale)
        self.before_display_info = (before_img, before_x, before_y, before_info['scale'])

        # Resize and display after image
        after_resized, after_info = self._resize_image_to_fit_with_info(after_img, after_width - 10, after_height - 10)
        self.after_photo = ImageTk.PhotoImage(Image.fromarray(after_resized))
        self.after_canvas.delete("all")
        after_x = after_width // 2
        after_y = after_height // 2
        self.after_canvas.create_image(
            after_x, after_y,
            image=self.after_photo, anchor=tk.CENTER
        )

        # Store display info for after panel (original image, offset, scale)
        self.after_display_info = (after_img, after_x, after_y, after_info['scale'])

        # Redraw crosshairs if mouse is over a panel
        if self.mouse_x is not None and self.mouse_y is not None:
            self._draw_crosshairs()

    def _resize_image_to_fit_with_info(self, image: np.ndarray, max_width: int, max_height: int) -> Tuple[np.ndarray, dict]:
        """Resize image to fit within given dimensions while maintaining aspect ratio.
        Returns resized image and info dict with scale factor."""
        if image.ndim == 2:
            h, w = image.shape
        else:
            h, w = image.shape[:2]

        # Calculate scaling factor
        scale = min(max_width / w, max_height / h)

        if scale < 1:
            new_w = int(w * scale)
            new_h = int(h * scale)
            resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            resized = image
            scale = 1.0

        return resized, {'scale': scale}

    def _on_mouse_motion(self, event, panel):
        """Handle mouse motion over canvas to update crosshairs."""
        if not self.crosshair_enabled:
            return

        # Store mouse position (canvas coordinates)
        self.mouse_x = event.x
        self.mouse_y = event.y

        # Draw crosshairs and update labels
        self._draw_crosshairs()
        self._update_coordinate_labels()

    def _on_mouse_leave(self, event):
        """Handle mouse leaving canvas."""
        # Clear crosshairs
        self.mouse_x = None
        self.mouse_y = None

        # Remove crosshair drawings
        self.before_canvas.delete('crosshair')
        self.after_canvas.delete('crosshair')

        # Reset labels
        if self.before_frame_label:
            self.before_frame_label.configure(text="Before")
        if self.after_frame_label:
            self.after_frame_label.configure(text="After")

    def _draw_crosshairs(self):
        """Draw synchronized crosshairs on both canvases."""
        # Always clear previous crosshairs first
        self.before_canvas.delete('crosshair')
        self.after_canvas.delete('crosshair')

        if self.mouse_x is None or self.mouse_y is None:
            return

        if self.before_display_info is None or self.after_display_info is None:
            return

        # Get display info
        before_img, before_cx, before_cy, before_scale = self.before_display_info
        after_img, after_cx, after_cy, after_scale = self.after_display_info

        # Map canvas coordinates to image coordinates for before panel
        img_x, img_y = self._canvas_to_image_coords(
            self.mouse_x, self.mouse_y,
            before_cx, before_cy, before_scale,
            before_img.shape[1], before_img.shape[0]
        )

        # If coordinates are valid, draw crosshairs on both panels
        if img_x is not None and img_y is not None:
            # Draw on before canvas
            self._draw_crosshair_on_canvas(
                self.before_canvas, self.mouse_x, self.mouse_y,
                before_cx, before_cy, before_scale,
                before_img.shape[1], before_img.shape[0]
            )

            # Draw on after canvas (synchronized position)
            # Map image coordinates back to canvas coordinates for after panel
            canvas_x, canvas_y = self._image_to_canvas_coords(
                img_x, img_y,
                after_cx, after_cy, after_scale
            )

            if canvas_x is not None:
                self._draw_crosshair_on_canvas(
                    self.after_canvas, canvas_x, canvas_y,
                    after_cx, after_cy, after_scale,
                    after_img.shape[1], after_img.shape[0]
                )

    def _draw_crosshair_on_canvas(self, canvas, x, y, center_x, center_y, scale, img_w, img_h):
        """Draw a crosshair with a hole in the centre (4 short non-intersecting lines)."""
        # Calculate image bounds in canvas coordinates
        half_w = (img_w * scale) / 2
        half_h = (img_h * scale) / 2

        left = center_x - half_w
        right = center_x + half_w
        top = center_y - half_h
        bottom = center_y + half_h

        # Gap and stub length (in canvas pixels)
        gap = 6       # half-size of the hole around the cursor
        stub = 18     # length of each stub line

        # Clamp stub endpoints to image bounds
        # Top stub (upward from cursor)
        y_top_end = max(top, y - gap - stub)
        y_top_start = max(top, y - gap)
        if y_top_start > y_top_end:
            canvas.create_line(x, y_top_start, x, y_top_end,
                               fill='yellow', width=1, tags='crosshair')

        # Bottom stub (downward from cursor)
        y_bot_start = min(bottom, y + gap)
        y_bot_end = min(bottom, y + gap + stub)
        if y_bot_end > y_bot_start:
            canvas.create_line(x, y_bot_start, x, y_bot_end,
                               fill='yellow', width=1, tags='crosshair')

        # Left stub
        x_left_end = max(left, x - gap - stub)
        x_left_start = max(left, x - gap)
        if x_left_start > x_left_end:
            canvas.create_line(x_left_start, y, x_left_end, y,
                               fill='yellow', width=1, tags='crosshair')

        # Right stub
        x_right_start = min(right, x + gap)
        x_right_end = min(right, x + gap + stub)
        if x_right_end > x_right_start:
            canvas.create_line(x_right_start, y, x_right_end, y,
                               fill='yellow', width=1, tags='crosshair')

    def _canvas_to_image_coords(self, canvas_x, canvas_y, center_x, center_y, scale, img_w, img_h):
        """Convert canvas coordinates to image coordinates."""
        # Calculate image bounds in canvas coordinates
        half_w = (img_w * scale) / 2
        half_h = (img_h * scale) / 2

        # Top-left corner of image in canvas coordinates
        img_left = center_x - half_w
        img_top = center_y - half_h

        # Convert to image coordinates
        img_x = int((canvas_x - img_left) / scale)
        img_y = int((canvas_y - img_top) / scale)

        # Check if within image bounds
        if 0 <= img_x < img_w and 0 <= img_y < img_h:
            return img_x, img_y
        return None, None

    def _image_to_canvas_coords(self, img_x, img_y, center_x, center_y, scale):
        """Convert image coordinates to canvas coordinates."""
        # Calculate image bounds in canvas coordinates
        # Assuming image is centered
        canvas_x = center_x - (scale * (self.before_display_info[0].shape[1] / 2)) + (img_x * scale)
        canvas_y = center_y - (scale * (self.before_display_info[0].shape[0] / 2)) + (img_y * scale)

        return canvas_x, canvas_y

    def _update_coordinate_labels(self):
        """Update frame labels with coordinate and RGB information."""
        if self.mouse_x is None or self.mouse_y is None:
            return

        if self.before_display_info is None or self.after_display_info is None:
            return

        # Get display info
        before_img, before_cx, before_cy, before_scale = self.before_display_info
        after_img, after_cx, after_cy, after_scale = self.after_display_info

        # Map canvas coordinates to image coordinates
        img_x, img_y = self._canvas_to_image_coords(
            self.mouse_x, self.mouse_y,
            before_cx, before_cy, before_scale,
            before_img.shape[1], before_img.shape[0]
        )

        if img_x is None or img_y is None:
            return

        # Get RGB values from both images
        # Before image
        if 0 <= img_y < before_img.shape[0] and 0 <= img_x < before_img.shape[1]:
            if before_img.ndim == 3:
                b_r, b_g, b_b = before_img[img_y, img_x]
                before_rgb = f"({b_r}, {b_g}, {b_b})"
            else:
                b_gray = before_img[img_y, img_x]
                before_rgb = f"({b_gray}, {b_gray}, {b_gray})"
        else:
            before_rgb = "(-, -, -)"

        # After image
        if 0 <= img_y < after_img.shape[0] and 0 <= img_x < after_img.shape[1]:
            if after_img.ndim == 3:
                a_r, a_g, a_b = after_img[img_y, img_x]
                after_rgb = f"({a_r}, {a_g}, {a_b})"
            else:
                a_gray = after_img[img_y, img_x]
                after_rgb = f"({a_gray}, {a_gray}, {a_gray})"
        else:
            after_rgb = "(-, -, -)"

        # Update labels
        if self.before_frame_label:
            self.before_frame_label.configure(
                text=f"Before  |  ({img_x}, {img_y}) RGB: {before_rgb}"
            )

        if self.after_frame_label:
            self.after_frame_label.configure(
                text=f"After  |  ({img_x}, {img_y}) RGB: {after_rgb}"
            )

    def _resize_image_to_fit(self, image: np.ndarray, max_width: int, max_height: int) -> np.ndarray:
        """Resize image to fit within given dimensions while maintaining aspect ratio."""
        if image.ndim == 2:
            h, w = image.shape
        else:
            h, w = image.shape[:2]

        # Calculate scaling factor
        scale = min(max_width / w, max_height / h)

        if scale < 1:
            new_w = int(w * scale)
            new_h = int(h * scale)
            resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            resized = image

        return resized


def main():
    root = tk.Tk()
    app = ImageProcessingGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()