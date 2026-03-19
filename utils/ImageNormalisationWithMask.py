"""
CORRECTED: Gamma implementation with proper convention (1/gamma).
FIXED: Label visibility issue resolved with subplots_adjust.
FIXED: All methods now properly limit their work to the mask region.
"""
from typing import List, Dict, Any, Tuple, Optional

import numpy as np
from scipy.ndimage import (
    minimum_filter, maximum_filter, uniform_filter,
    grey_opening, grey_closing, gaussian_filter, rank_filter
)
from scipy.interpolate import RectBivariateSpline
import cv2
import matplotlib.pyplot as plt


def rgb2gray(rgb: np.ndarray) -> np.ndarray:
    """Standard RGB → grayscale conversion."""
    if rgb.ndim == 2:
        return rgb
    return np.dot(rgb[..., :3], [0.299, 0.587, 0.114])


def ensure_float32(image: np.ndarray) -> np.ndarray:
    """Convert image to float32 in [0, 255] range."""
    img = image.copy()
    if img.dtype == np.uint8:
        return img.astype(np.float32)
    elif img.max() <= 1.0:
        return (img * 255.0).astype(np.float32)
    return img.astype(np.float32)


def create_annular_mask(shape, center, outer_radius, inner_radius):
    """
    Create an annular (ring) mask.

    Args:
        shape: (height, width) of image
        center: (cx, cy) center coordinates
        outer_radius: Outer radius of ring
        inner_radius: Inner radius of ring

    Returns:
        Boolean mask (True inside annular region)
    """
    h, w = shape
    cx, cy = center

    y, x = np.ogrid[:h, :w]
    dist = np.sqrt((x - cx)**2 + (y - cy)**2)

    mask = (dist <= outer_radius) & (dist >= inner_radius)
    return mask


def extract_annular_region(image: np.ndarray, center: tuple,
                           outer_radius: int, inner_radius: int,
                           fill_color: int = 0) -> tuple:
    """
    Extract annular region from image, painting outside as fill_color.

    This is a convenience function that combines masking and cropping in one step.
    Useful for preprocessing images before applying normalization methods.

    Args:
        image: Input image (grayscale or RGB)
        center: (cx, cy) center coordinates in original image
        outer_radius: Outer radius of annular region
        inner_radius: Inner radius of annular region (use 0 for full disk)
        fill_color: Color to fill outside the annular region (default: 0 for black)

    Returns:
        Tuple of (cropped_image, cropped_mask)
        - cropped_image: Image cropped to bounding box of outer circle,
                        with outside region filled with fill_color
        - cropped_mask: Boolean mask for the annular region (True inside ring)

    Example:
        >>> # Extract annular region and apply normalization
        >>> img_crop, mask_crop = extract_annular_region(
        ...     image, center=(320, 240), outer_radius=150, inner_radius=50
        ... )
        >>> normalized = pixBackgroundNorm_masked(img_crop, mask_crop)
    """
    h, w = image.shape[:2]

    # Create annular mask on full image
    mask = create_annular_mask((h, w), center, outer_radius, inner_radius)

    # Apply mask to image
    if image.ndim == 3:
        result = image.copy()
        for c in range(3):
            result[:, :, c] = np.where(mask, image[:, :, c], fill_color)
    else:
        result = np.where(mask, image, fill_color)

    # Crop to bounding box of outer circle
    cx, cy = center
    x1 = max(0, cx - outer_radius)
    x2 = min(w, cx + outer_radius)
    y1 = max(0, cy - outer_radius)
    y2 = min(h, cy + outer_radius)

    cropped_image = result[y1:y2, x1:x2]
    cropped_mask = mask[y1:y2, x1:x2]

    return cropped_image, cropped_mask


# =============================================================================
# GAMMA CORRECTION WITH LUT (CORRECTED)
# =============================================================================

class GammaLUT:
    """
    Gamma correction with precomputed lookup tables.

    CORRECTED: Uses power of (1/gamma) for standard convention:
    - gamma > 1.0 → brightens (e.g., gamma=2.0 applies power of 0.5)
    - gamma = 1.0 → no change
    - gamma < 1.0 → darkens (e.g., gamma=0.5 applies power of 2.0)

    Stores LUTs for gamma values from 0.5 to 6.0 in increments of 0.25.
    """

    def __init__(self):
        """Precompute all gamma LUTs."""
        self.gamma_values = np.arange(0.5, 6.25, 0.25)
        self.luts = {}

        print("Precomputing Gamma LUTs (using 1/gamma)...")
        for gamma in self.gamma_values:
            # CORRECTED: output = 255 * (input/255)^(1/gamma)
            power = 1.0 / gamma
            lut = np.array([((i / 255.0) ** power) * 255.0
                           for i in range(256)], dtype=np.uint8)
            self.luts[gamma] = lut

        print(f"  Created {len(self.luts)} LUTs for gamma values: {self.gamma_values[0]:.2f} to {self.gamma_values[-1]:.2f}")
        print(f"  gamma > 1.0 = brightens, gamma < 1.0 = darkens")

    def apply(self, image: np.ndarray, gamma: float) -> np.ndarray:
        """
        Apply gamma correction using precomputed LUT.

        Args:
            image: Input grayscale image (uint8 or float)
            gamma: Gamma value (0.5 to 6.0)
                   > 1.0 = brighten (good for dark images)
                   = 1.0 = no change
                   < 1.0 = darken (good for overexposed images)

        Returns:
            Gamma-corrected image (uint8)
        """
        gray = rgb2gray(image)

        if gray.dtype != np.uint8:
            gray = ensure_float32(gray).astype(np.uint8)

        # Find closest gamma value
        if gamma not in self.luts:
            closest_gamma = self.gamma_values[np.argmin(np.abs(self.gamma_values - gamma))]
            print(f"  Warning: gamma={gamma} not in LUT, using closest: {closest_gamma}")
            gamma = closest_gamma

        # Apply LUT
        return self.luts[gamma][gray]

    def apply_masked(self, image: np.ndarray, mask: np.ndarray, gamma: float) -> np.ndarray:
        """Apply gamma correction only to masked region."""
        gray = rgb2gray(image)

        if gray.dtype != np.uint8:
            gray = ensure_float32(gray).astype(np.uint8)

        # Apply gamma
        corrected = self.apply(image, gamma)

        # Apply mask
        result = gray.copy()
        result[mask] = corrected[mask]

        return result


# Initialize global gamma LUT
GAMMA_LUT = GammaLUT()


def pixGammaCorrection(image: np.ndarray, gamma: float) -> np.ndarray:
    """
    Gamma correction using precomputed LUT.

    CORRECTED: Standard gamma convention (uses 1/gamma as power):
    - gamma > 1.0 = brighten (e.g., 2.0 for dark images)
    - gamma = 1.0 = no change
    - gamma < 1.0 = darken (e.g., 0.5 for overexposed images)

    Args:
        image: Input grayscale image
        gamma: Gamma value (0.5 to 6.0)

    Returns:
        Gamma-corrected image (uint8)
    """
    return GAMMA_LUT.apply(image, gamma)


def pixGammaCorrection_masked(image: np.ndarray, mask: np.ndarray, gamma: float) -> np.ndarray:
    """Gamma correction with mask."""
    return GAMMA_LUT.apply_masked(image, mask, gamma)


def relative_gamma_masked(
    image: np.ndarray,
    mask: np.ndarray,
    percentile_cutoff: float = 50.0,
    uplift_gamma: float = 2.0,
    subdue_gamma: float = 0.75,
    kernel_height: int = 0,
    kernel_width: int = 0,
    kernel_type: str = 'rectangular',
) -> np.ndarray:
    """
    Relative (split) gamma correction within a mask.

    Pixels whose intensity is >= the percentile_cutoff value receive
    *uplift_gamma* (standard gamma: output = 255*(input/255)^(1/gamma),
    so gamma > 1 brightens).  Pixels below the cutoff receive
    *subdue_gamma* (gamma < 1 darkens).

    Two modes:

    **Global** (kernel_height=0 or kernel_width=0):
        A single percentile is computed from all masked pixels and used
        for the entire image.

    **Local / kernel-based** (kernel_height>0 and kernel_width>0):
        The image is divided into overlapping tiles of the given kernel
        size.  Within each tile the percentile is computed from the
        masked pixels in that tile, so the split adapts spatially.
        Kernel type can be 'rectangular' or 'elliptical'; an elliptical
        kernel masks out corner pixels of each tile.

    Args:
        image:             Input image (grayscale or RGB; converted to gray).
        mask:              Boolean mask (True = region of interest).
        percentile_cutoff: Percentile (0-100) used to split bright/dark.
        uplift_gamma:      Gamma for pixels >= cutoff (>1 brightens).
        subdue_gamma:      Gamma for pixels <  cutoff (<1 darkens).
        kernel_height:     Tile height for local mode (0 = global).
        kernel_width:      Tile width  for local mode (0 = global).
        kernel_type:       'rectangular' or 'elliptical' (local mode only).

    Returns:
        Processed grayscale image (uint8).  Outside mask is preserved.
    """
    gray = rgb2gray(image)
    if gray.dtype != np.uint8:
        gray = np.clip(ensure_float32(gray), 0, 255).astype(np.uint8)

    result = gray.copy()

    # Pre-build LUTs for both gammas (avoids recomputing per-tile)
    lut_uplift = np.array(
        [np.clip(255.0 * (i / 255.0) ** (1.0 / uplift_gamma), 0, 255)
         for i in range(256)], dtype=np.uint8)
    lut_subdue = np.array(
        [np.clip(255.0 * (i / 255.0) ** (1.0 / subdue_gamma), 0, 255)
         for i in range(256)], dtype=np.uint8)

    # ------------------------------------------------------------------
    # Global mode
    # ------------------------------------------------------------------
    if kernel_height <= 0 or kernel_width <= 0:
        masked_pixels = gray[mask]
        if len(masked_pixels) == 0:
            return result

        cutoff_val = np.percentile(masked_pixels, percentile_cutoff)

        # Apply split gamma only inside mask
        bright = mask & (gray >= cutoff_val)
        dark   = mask & (gray <  cutoff_val)
        result[bright] = lut_uplift[gray[bright]]
        result[dark]   = lut_subdue[gray[dark]]
        return result

    # ------------------------------------------------------------------
    # Local / kernel mode
    # ------------------------------------------------------------------
    h, w = gray.shape

    # Ensure odd kernel dimensions
    kh = kernel_height if kernel_height % 2 == 1 else kernel_height + 1
    kw = kernel_width  if kernel_width  % 2 == 1 else kernel_width  + 1
    half_h, half_w = kh // 2, kw // 2

    # Build elliptical kernel mask if requested (relative to kernel centre)
    if kernel_type == 'elliptical':
        ky, kx = np.ogrid[-half_h:half_h + 1, -half_w:half_w + 1]
        # Ellipse equation: (x/a)^2 + (y/b)^2 <= 1
        kern_mask = ((kx / max(half_w, 1)) ** 2 +
                     (ky / max(half_h, 1)) ** 2) <= 1.0
    else:
        kern_mask = np.ones((kh, kw), dtype=bool)

    # We accumulate weighted (by overlap count) gamma-corrected values
    # so that overlapping tiles blend smoothly.
    accum  = np.zeros_like(gray, dtype=np.float64)
    weight = np.zeros_like(gray, dtype=np.float64)

    # Step through centres on a grid (step = half kernel for 2× overlap)
    step_y = max(1, half_h)
    step_x = max(1, half_w)

    for cy in range(0, h, step_y):
        y0 = max(cy - half_h, 0)
        y1 = min(cy + half_h + 1, h)
        ky0 = y0 - (cy - half_h)          # offset into kern_mask
        ky1 = kh - ((cy + half_h + 1) - y1)

        for cx in range(0, w, step_x):
            x0 = max(cx - half_w, 0)
            x1 = min(cx + half_w + 1, w)
            kx0 = x0 - (cx - half_w)
            kx1 = kw - ((cx + half_w + 1) - x1)

            tile_kern = kern_mask[ky0:ky1, kx0:kx1]
            tile_mask = mask[y0:y1, x0:x1] & tile_kern
            tile      = gray[y0:y1, x0:x1]

            masked_px = tile[tile_mask]
            if len(masked_px) < 2:
                continue

            cutoff_val = np.percentile(masked_px, percentile_cutoff)

            bright = tile_mask & (tile >= cutoff_val)
            dark   = tile_mask & (tile <  cutoff_val)

            tile_result = np.zeros_like(tile, dtype=np.float64)
            tile_result[bright] = lut_uplift[tile[bright]]
            tile_result[dark]   = lut_subdue[tile[dark]]

            # Accumulate (only where tile_mask is True)
            tile_weight = tile_mask.astype(np.float64)
            accum[y0:y1, x0:x1]  += tile_result * tile_weight
            weight[y0:y1, x0:x1] += tile_weight

    # Blend overlapping tiles
    valid = mask & (weight > 0)
    result[valid] = np.clip(accum[valid] / weight[valid], 0, 255).astype(np.uint8)

    return result

def pixBackgroundNorm_masked(
    image: np.ndarray,
    mask: np.ndarray,
    sx: int = 10,
    sy: int = 10,
    thresh: int = 100,
    mincount: int = 50,
    bgval: int = 200,
    smoothx: int = 2,
    smoothy: int = 2
) -> np.ndarray:
    """Background normalization with mask support."""
    gray = rgb2gray(image)
    gray = ensure_float32(gray)
    h, w = gray.shape

    nx = (w + sx - 1) // sx
    ny = (h + sy - 1) // sy

    bg_map = np.zeros((ny, nx), dtype=np.float32)

    for j in range(ny):
        y_start = j * sy
        y_end = min((j + 1) * sy, h)

        for i in range(nx):
            x_start = i * sx
            x_end = min((i + 1) * sx, w)

            tile = gray[y_start:y_end, x_start:x_end]
            tile_mask = mask[y_start:y_end, x_start:x_end]

            masked_pixels = tile[tile_mask]

            if len(masked_pixels) > 0:
                bright_pixels = masked_pixels[masked_pixels > thresh]

                if len(bright_pixels) >= mincount:
                    bg_map[j, i] = np.mean(bright_pixels)
                else:
                    bg_map[j, i] = np.mean(masked_pixels)
            else:
                bg_map[j, i] = 200.0

    if smoothx > 0 or smoothy > 0:
        sigma_x = smoothx / 2.0
        sigma_y = smoothy / 2.0
        bg_map = gaussian_filter(bg_map, sigma=(sigma_y, sigma_x))

    x_coords = (np.arange(nx) + 0.5) * sx
    y_coords = (np.arange(ny) + 0.5) * sy

    interp = RectBivariateSpline(y_coords, x_coords, bg_map, kx=1, ky=1)

    x_full = np.arange(w)
    y_full = np.arange(h)
    bg_full = interp(y_full, x_full)

    bg_full = np.maximum(bg_full, 1.0)
    normalized = gray * bgval / bg_full
    normalized = np.clip(normalized, 0, 255)

    result = gray.copy()
    result[mask] = normalized[mask]

    return result.astype(np.uint8)


def pixBackgroundNormSimple_masked(
    image: np.ndarray,
    mask: np.ndarray,
    size: int = 50,
    bgval: int = 200
) -> np.ndarray:
    """
    CORRECTED: Simple background normalization with mask.

    Now properly fills outside-mask regions before morphological operation.
    """
    gray = rgb2gray(image)
    gray = ensure_float32(gray)

    # Create a masked image where outside pixels are set to mean of inside
    masked_img = gray.copy()
    if mask.sum() > 0:
        mean_inside = np.mean(gray[mask])
        masked_img[~mask] = mean_inside

    # Apply morphological opening only to this prepared image
    background = grey_opening(masked_img, size=size)

    background = np.maximum(background, 1.0)
    normalized = gray * bgval / background
    normalized = np.clip(normalized, 0, 255)

    result = gray.copy()
    result[mask] = normalized[mask]

    return result.astype(np.uint8)


def pixContrastNorm_masked(
    image: np.ndarray,
    mask: np.ndarray,
    sx: int = 10,
    sy: int = 10,
    mindiff: int = 50,
    smoothx: int = 2,
    smoothy: int = 2
) -> np.ndarray:
    """Contrast normalization with mask support."""
    gray = rgb2gray(image)
    gray = ensure_float32(gray)
    h, w = gray.shape

    nx = (w + sx - 1) // sx
    ny = (h + sy - 1) // sy

    mean_map = np.zeros((ny, nx), dtype=np.float32)
    std_map = np.zeros((ny, nx), dtype=np.float32)

    for j in range(ny):
        y_start = j * sy
        y_end = min((j + 1) * sy, h)

        for i in range(nx):
            x_start = i * sx
            x_end = min((i + 1) * sx, w)

            tile = gray[y_start:y_end, x_start:x_end]
            tile_mask = mask[y_start:y_end, x_start:x_end]

            masked_pixels = tile[tile_mask]

            if len(masked_pixels) > 0:
                mean_map[j, i] = np.mean(masked_pixels)
                std_map[j, i] = np.std(masked_pixels)
            else:
                mean_map[j, i] = 128.0
                std_map[j, i] = mindiff

    if smoothx > 0 or smoothy > 0:
        sigma_x = smoothx / 2.0
        sigma_y = smoothy / 2.0
        mean_map = gaussian_filter(mean_map, sigma=(sigma_y, sigma_x))
        std_map = gaussian_filter(std_map, sigma=(sigma_y, sigma_x))

    x_coords = (np.arange(nx) + 0.5) * sx
    y_coords = (np.arange(ny) + 0.5) * sy

    mean_interp = RectBivariateSpline(y_coords, x_coords, mean_map, kx=1, ky=1)
    std_interp = RectBivariateSpline(y_coords, x_coords, std_map, kx=1, ky=1)

    x_full = np.arange(w)
    y_full = np.arange(h)
    mean_full = mean_interp(y_full, x_full)
    std_full = std_interp(y_full, x_full)

    std_full = np.maximum(std_full, mindiff)
    normalized = (gray - mean_full) / std_full * 64.0 + 128.0
    normalized = np.clip(normalized, 0, 255)

    result = gray.copy()
    result[mask] = normalized[mask]

    return result.astype(np.uint8)


def pixGrayNormalize_masked(
    image: np.ndarray,
    mask: np.ndarray,
    black_clip: float = 0.0,
    white_clip: float = 0.0
) -> np.ndarray:
    """Gray normalization with mask."""
    gray = rgb2gray(image)
    gray = ensure_float32(gray)

    masked_pixels = gray[mask]

    if len(masked_pixels) == 0:
        return gray.astype(np.uint8)

    if black_clip > 0 or white_clip > 0:
        min_val = np.percentile(masked_pixels, black_clip * 100)
        max_val = np.percentile(masked_pixels, 100 - white_clip * 100)
    else:
        min_val = masked_pixels.min()
        max_val = masked_pixels.max()

    if max_val - min_val < 10:
        result = gray.copy()
        return result.astype(np.uint8)

    result = gray.copy()
    masked_normalized = (gray[mask] - min_val) / (max_val - min_val) * 255.0
    masked_normalized = np.clip(masked_normalized, 0, 255)
    result[mask] = masked_normalized

    return result.astype(np.uint8)


def pixRankFilterGray_masked(
    image: np.ndarray,
    mask: np.ndarray,
    size: int = 5,
    rank: float = 0.5
) -> np.ndarray:
    """
    CORRECTED: Rank filter with mask.

    Now applies rank filter only within the masked region by filling
    outside regions before filtering.
    """
    gray = rgb2gray(image)

    if gray.dtype != np.uint8:
        gray = ensure_float32(gray).astype(np.uint8)

    if size % 2 == 0:
        size += 1

    # Prepare image: fill outside mask with median of inside
    masked_img = gray.copy()
    if mask.sum() > 0:
        median_inside = np.median(gray[mask])
        masked_img[~mask] = median_inside

    percentile = int(rank * 100)
    filtered = rank_filter(masked_img, rank=percentile, size=size)

    result = gray.copy()
    result[mask] = filtered[mask]

    return result.astype(np.uint8)


def pixUnsharpMaskingGray_masked(
    image: np.ndarray,
    mask: np.ndarray,
    halfwidth: int = 5,
    fract: float = 2.5
) -> np.ndarray:
    """
    CORRECTED: Unsharp masking with mask.

    Now properly applies Gaussian blur only within the masked region
    to avoid boundary effects.
    """
    gray = rgb2gray(image)
    gray = ensure_float32(gray)

    # Prepare image: fill outside mask with mean of inside
    masked_img = gray.copy()
    if mask.sum() > 0:
        mean_inside = np.mean(gray[mask])
        masked_img[~mask] = mean_inside

    sigma = halfwidth / 2.0
    blurred = gaussian_filter(masked_img, sigma=sigma)

    sharpened = gray + fract * (gray - blurred)
    sharpened = np.clip(sharpened, 0, 255)

    result = gray.copy()
    result[mask] = sharpened[mask]

    return result.astype(np.uint8)


def pixEqualizeHistogram_masked(
    image: np.ndarray,
    mask: np.ndarray
) -> np.ndarray:
    """
    CORRECTED: Histogram equalization with mask.

    Now computes histogram only from masked pixels.
    """
    gray = rgb2gray(image)

    if gray.dtype != np.uint8:
        gray = ensure_float32(gray).astype(np.uint8)

    # Extract masked pixels
    masked_pixels = gray[mask]

    if len(masked_pixels) == 0:
        return gray

    # Compute histogram and CDF from masked pixels only
    hist, bins = np.histogram(masked_pixels.flatten(), 256, [0, 256])
    cdf = hist.cumsum()
    cdf_normalized = cdf * 255 / cdf[-1]

    # Create lookup table
    lut = np.interp(np.arange(256), bins[:-1], cdf_normalized).astype(np.uint8)

    # Apply equalization
    equalized = lut[gray]

    result = gray.copy()
    result[mask] = equalized[mask]

    return result.astype(np.uint8)


# =============================================================================
# ADVANCED NORMALIZATION METHODS
# =============================================================================

def butterworth_homomorphic_filter_masked(
    image: np.ndarray,
    mask: np.ndarray,
    d0: float = 30.0,
    gamma_l: float = 0.5,
    gamma_h: float = 2.0,
    c: float = 1.0,
    order: int = 2
) -> np.ndarray:
    """
    Butterworth Homomorphic Filter with mask support.

    Separates illumination (low-frequency) from reflectance (high-frequency)
    in the log domain, then applies a Butterworth high-pass filter to
    compress illumination dynamic range while enhancing reflectance.

    Args:
        image: Input grayscale image
        mask: Boolean mask for region of interest
        d0: Cutoff frequency (higher = more low-freq passes through)
        gamma_l: Gain for low frequencies (< 1 compresses illumination)
        gamma_h: Gain for high frequencies (> 1 enhances reflectance)
        c: Controls sharpness of transition
        order: Butterworth filter order (higher = sharper cutoff)

    Returns:
        Filtered image (uint8)
    """
    gray = rgb2gray(image)
    gray = ensure_float32(gray)

    # Add small epsilon to avoid log(0)
    epsilon = 1.0

    # Fill outside-mask with mean of inside-mask to reduce FFT boundary artifacts
    gray_prepared = gray.copy()
    if mask.sum() > 0:
        mean_inside = np.mean(gray[mask])
        gray_prepared[~mask] = mean_inside

    log_img = np.log(gray_prepared + epsilon)

    # Compute FFT
    rows, cols = gray.shape
    f_transform = np.fft.fft2(log_img)
    f_shift = np.fft.fftshift(f_transform)

    # Create Butterworth high-pass filter
    crow, ccol = rows // 2, cols // 2
    u = np.arange(rows) - crow
    v = np.arange(cols) - ccol
    V, U = np.meshgrid(v, u)
    D = np.sqrt(U**2 + V**2)

    # Butterworth HPF: H(u,v) = 1 / (1 + (D0/D)^(2n))
    # Avoid division by zero at center
    D_safe = np.maximum(D, 1e-10)
    H_hp = 1.0 / (1.0 + (d0 / D_safe) ** (2 * order))

    # Homomorphic filter combines LPF and HPF with different gains
    # H = gamma_l + (gamma_h - gamma_l) * H_hp
    H = gamma_l + (gamma_h - gamma_l) * H_hp

    # Apply filter
    filtered_shift = f_shift * H
    f_ishift = np.fft.ifftshift(filtered_shift)
    filtered_log = np.fft.ifft2(f_ishift)
    filtered_log = np.real(filtered_log)

    # Inverse log transform
    filtered = np.exp(filtered_log) - epsilon

    # Normalize to [0, 255] - use masked region for min/max
    if mask.sum() > 0:
        filtered_masked = filtered[mask]
        min_val = filtered_masked.min()
        max_val = filtered_masked.max()
    else:
        min_val = filtered.min()
        max_val = filtered.max()

    filtered = filtered - min_val
    if max_val - min_val > 0:
        filtered = filtered / (max_val - min_val) * 255.0
    filtered = np.clip(filtered, 0, 255)

    # Apply mask
    result = gray.copy()
    result[mask] = filtered[mask]

    return result.astype(np.uint8)


def log_domain_normalization_masked(
    image: np.ndarray,
    mask: np.ndarray,
    sigma: float = 50.0
) -> np.ndarray:
    """
    Log Domain Normalization with mask support.

    Operates in logarithmic domain to separate illumination from reflectance.
    Uses Gaussian blur to estimate illumination component.
    Fills outside-mask region before blurring to prevent boundary contamination.

    Args:
        image: Input grayscale image
        mask: Boolean mask for region of interest
        sigma: Gaussian sigma for illumination estimation

    Returns:
        Normalized image (uint8)
    """
    gray = rgb2gray(image)
    gray = ensure_float32(gray)

    # Add epsilon to avoid log(0)
    epsilon = 1.0
    log_img = np.log(gray + epsilon)

    # Fill outside-mask with mean of inside-mask to prevent boundary contamination
    masked_log = log_img.copy()
    if mask.sum() > 0:
        mean_inside = np.mean(log_img[mask])
        masked_log[~mask] = mean_inside

    # Estimate illumination with Gaussian blur in log domain
    log_illumination = gaussian_filter(masked_log, sigma=sigma)

    # Subtract illumination (division in original domain)
    log_reflectance = log_img - log_illumination

    # Normalize log reflectance to usable range - use masked region for min/max
    if mask.sum() > 0:
        log_refl_masked = log_reflectance[mask]
        min_val = log_refl_masked.min()
        max_val = log_refl_masked.max()
    else:
        min_val = log_reflectance.min()
        max_val = log_reflectance.max()

    log_reflectance = log_reflectance - min_val
    if max_val - min_val > 0:
        log_reflectance = log_reflectance / (max_val - min_val)

    # Scale to [0, 255]
    normalized = log_reflectance * 255.0
    normalized = np.clip(normalized, 0, 255)

    # Apply mask
    result = gray.copy()
    result[mask] = normalized[mask]

    return result.astype(np.uint8)


def clahe_masked(
    image: np.ndarray,
    mask: np.ndarray,
    clip_limit: float = 2.0,
    tile_grid_size: tuple = (8, 8)
) -> np.ndarray:
    """
    CORRECTED: Contrast Limited Adaptive Histogram Equalization (CLAHE) with mask support.

    Now creates a masked version of the image before applying CLAHE to avoid
    contamination from pixels outside the mask.
    """
    gray = rgb2gray(image)

    if gray.dtype != np.uint8:
        gray = ensure_float32(gray).astype(np.uint8)

    # Prepare masked image
    masked_img = gray.copy()
    if mask.sum() > 0:
        mean_inside = np.mean(gray[mask])
        masked_img[~mask] = int(mean_inside)

    # Create CLAHE object
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)

    # Apply CLAHE to masked image
    clahe_result = clahe.apply(masked_img)

    # Apply mask
    result = gray.copy()
    result[mask] = clahe_result[mask]

    return result.astype(np.uint8)


def single_scale_retinex_masked(
    image: np.ndarray,
    mask: np.ndarray,
    sigma: float = 80.0
) -> np.ndarray:
    """
    Single Scale Retinex (SSR) with mask support.

    Based on Land's Retinex theory: the perceived image is the ratio
    of the image to a smoothed version (illumination estimate).

    SSR: R(x,y) = log(I(x,y)) - log(G(x,y) * I(x,y))

    Where G is a Gaussian surround function.
    Fills outside-mask region before blurring to prevent boundary contamination.

    Args:
        image: Input grayscale image
        mask: Boolean mask for region of interest
        sigma: Gaussian sigma for surround function

    Returns:
        SSR normalized image (uint8)
    """
    gray = rgb2gray(image)
    gray = ensure_float32(gray)

    # Add epsilon to avoid log(0)
    epsilon = 1.0
    gray_safe = gray + epsilon

    # Fill outside-mask with mean of inside-mask before blurring
    masked_img = gray_safe.copy()
    if mask.sum() > 0:
        mean_inside = np.mean(gray_safe[mask])
        masked_img[~mask] = mean_inside

    # Compute log of image
    log_img = np.log(gray_safe)

    # Compute Gaussian-smoothed version (illumination estimate) from masked image
    blurred = gaussian_filter(masked_img, sigma=sigma)
    blurred = np.maximum(blurred, epsilon)  # Ensure positive
    log_blurred = np.log(blurred)

    # SSR output
    retinex = log_img - log_blurred

    # Normalize to [0, 255]
    # Use robust normalization based on percentiles from masked region
    if mask.sum() > 0:
        retinex_masked = retinex[mask]
        p_low, p_high = np.percentile(retinex_masked, [1, 99])
    else:
        p_low, p_high = np.percentile(retinex, [1, 99])

    retinex = np.clip(retinex, p_low, p_high)
    retinex = (retinex - p_low) / (p_high - p_low + 1e-10) * 255.0
    retinex = np.clip(retinex, 0, 255)

    # Apply mask
    result = gray.copy()
    result[mask] = retinex[mask]

    return result.astype(np.uint8)


def multi_scale_retinex_masked(
    image: np.ndarray,
    mask: np.ndarray,
    sigmas: tuple = (15.0, 80.0, 250.0),
    weights: tuple = None
) -> np.ndarray:
    """
    Multi-Scale Retinex (MSR) with mask support.

    Combines multiple SSR outputs at different scales to capture
    both fine details (small sigma) and global illumination (large sigma).
    Fills outside-mask region before blurring to prevent boundary contamination.

    MSR: R(x,y) = sum_i(w_i * SSR_i(x,y))

    Args:
        image: Input grayscale image
        mask: Boolean mask for region of interest
        sigmas: Tuple of Gaussian sigmas for different scales
        weights: Weights for each scale (default: equal weights)

    Returns:
        MSR normalized image (uint8)
    """
    gray = rgb2gray(image)
    gray = ensure_float32(gray)

    if weights is None:
        weights = tuple([1.0 / len(sigmas)] * len(sigmas))

    # Add epsilon to avoid log(0)
    epsilon = 1.0
    gray_safe = gray + epsilon
    log_img = np.log(gray_safe)

    # Fill outside-mask with mean of inside-mask before blurring
    masked_img = gray_safe.copy()
    if mask.sum() > 0:
        mean_inside = np.mean(gray_safe[mask])
        masked_img[~mask] = mean_inside

    # Accumulate weighted retinex outputs
    msr = np.zeros_like(gray, dtype=np.float64)

    for sigma, weight in zip(sigmas, weights):
        # Gaussian-smoothed version from masked image
        blurred = gaussian_filter(masked_img, sigma=sigma)
        blurred = np.maximum(blurred, epsilon)
        log_blurred = np.log(blurred)

        # Single-scale retinex
        ssr = log_img - log_blurred
        msr += weight * ssr

    # Normalize to [0, 255] - use percentiles from masked region
    if mask.sum() > 0:
        msr_masked = msr[mask]
        p_low, p_high = np.percentile(msr_masked, [1, 99])
    else:
        p_low, p_high = np.percentile(msr, [1, 99])

    msr = np.clip(msr, p_low, p_high)
    msr = (msr - p_low) / (p_high - p_low + 1e-10) * 255.0
    msr = np.clip(msr, 0, 255)

    # Apply mask
    result = gray.copy()
    result[mask] = msr[mask]

    return result.astype(np.uint8)


def intrinsic_reflectance_separation_masked(
    image: np.ndarray,
    mask: np.ndarray,
    sigma_spatial: float = 10.0,
    sigma_range: float = 30.0,
    iterations: int = 3
) -> np.ndarray:
    """
    CORRECTED: Intrinsic Reflectance Separation with mask support.

    Now applies bilateral filtering to a masked image to avoid
    contamination from outside the mask.
    """
    gray = rgb2gray(image)
    gray = ensure_float32(gray)

    # Convert to appropriate format for bilateral filter
    gray_uint8 = np.clip(gray, 0, 255).astype(np.uint8)

    # Prepare masked image
    masked_img = gray_uint8.copy()
    if mask.sum() > 0:
        mean_inside = int(np.mean(gray_uint8[mask]))
        masked_img[~mask] = mean_inside

    # Iterative bilateral filtering to estimate illumination
    illumination = masked_img.astype(np.float32)

    for _ in range(iterations):
        # Bilateral filter preserves edges while smoothing
        illumination = cv2.bilateralFilter(
            illumination.astype(np.uint8),
            d=-1,  # Computed from sigmaSpace
            sigmaColor=sigma_range,
            sigmaSpace=sigma_spatial
        ).astype(np.float32)

    # Avoid division by zero
    illumination = np.maximum(illumination, 1.0)

    # Compute reflectance: R = I / L
    reflectance = gray / illumination

    # Normalize reflectance to [0, 255] - use masked region for min/max
    if mask.sum() > 0:
        refl_masked = reflectance[mask]
        min_val = refl_masked.min()
        max_val = refl_masked.max()
    else:
        min_val = reflectance.min()
        max_val = reflectance.max()

    reflectance = reflectance - min_val
    if max_val - min_val > 0:
        reflectance = reflectance / (max_val - min_val) * 255.0
    reflectance = np.clip(reflectance, 0, 255)

    # Apply mask
    result = gray.copy()
    result[mask] = reflectance[mask]

    return result.astype(np.uint8)


def homomorphic_filter_robust_masked(
    image: np.ndarray,
    mask: np.ndarray,
    d0: float = 30.0,
    gamma_l: float = 0.5,
    gamma_h: float = 2.0
) -> np.ndarray:
    """
    Homomorphic Filter with robust numerical handling to avoid negative numbers.

    This implementation includes several safeguards:
    1. Proper epsilon handling to avoid log(0)
    2. Clipping after inverse log to ensure non-negative values
    3. Robust normalization using percentiles
    4. Gaussian HPF for smooth frequency response

    The image formation model is: I = L * R
    In log domain: log(I) = log(L) + log(R)

    HPF attenuates log(L) (low-freq illumination) while preserving
    log(R) (high-freq reflectance).

    Args:
        image: Input grayscale image
        mask: Boolean mask for region of interest
        d0: Cutoff frequency for Gaussian high-pass filter
        gamma_l: Gain for low frequencies (< 1 to compress illumination)
        gamma_h: Gain for high frequencies (> 1 to enhance reflectance)

    Returns:
        Filtered image (uint8), guaranteed non-negative
    """
    gray = rgb2gray(image)
    gray = ensure_float32(gray)

    # ROBUST: Use larger epsilon and ensure all values are positive
    epsilon = 1.0
    gray_safe = np.maximum(gray, epsilon)

    # Fill outside-mask with mean of inside-mask to reduce FFT boundary artifacts
    gray_prepared = gray_safe.copy()
    if mask.sum() > 0:
        mean_inside = np.mean(gray_safe[mask])
        gray_prepared[~mask] = mean_inside

    # Log transform
    log_img = np.log(gray_prepared)

    # Store original mean for DC restoration - use masked region
    if mask.sum() > 0:
        log_mean = np.mean(log_img[mask])
    else:
        log_mean = np.mean(log_img)

    # FFT
    rows, cols = gray.shape
    f_transform = np.fft.fft2(log_img)
    f_shift = np.fft.fftshift(f_transform)

    # Create Gaussian high-pass filter (smoother than Butterworth)
    crow, ccol = rows // 2, cols // 2
    u = np.arange(rows) - crow
    v = np.arange(cols) - ccol
    V, U = np.meshgrid(v, u)
    D = np.sqrt(U**2 + V**2)

    # Gaussian HPF: H_hp = 1 - exp(-D^2 / (2*D0^2))
    H_hp = 1.0 - np.exp(-D**2 / (2.0 * d0**2))

    # Homomorphic transfer function
    H = gamma_l + (gamma_h - gamma_l) * H_hp

    # Apply filter
    filtered_shift = f_shift * H
    f_ishift = np.fft.ifftshift(filtered_shift)
    filtered_log = np.fft.ifft2(f_ishift)
    filtered_log = np.real(filtered_log)

    # ROBUST: Restore DC component to avoid extreme values - use masked mean
    if mask.sum() > 0:
        filtered_log_mean = np.mean(filtered_log[mask])
    else:
        filtered_log_mean = np.mean(filtered_log)

    filtered_log = filtered_log - filtered_log_mean + log_mean

    # ROBUST: Clip log values to reasonable range before exp
    # This prevents overflow/underflow in exp()
    max_log = np.log(255.0 + epsilon)
    min_log = np.log(epsilon)
    filtered_log = np.clip(filtered_log, min_log, max_log * 1.5)

    # Inverse log transform
    filtered = np.exp(filtered_log) - epsilon

    # ROBUST: Ensure non-negative
    filtered = np.maximum(filtered, 0)

    # ROBUST: Percentile-based normalization to handle outliers - use masked region
    if mask.sum() > 0:
        filtered_masked = filtered[mask]
        p_low, p_high = np.percentile(filtered_masked, [0.5, 99.5])
    else:
        p_low, p_high = np.percentile(filtered, [0.5, 99.5])

    filtered = np.clip(filtered, p_low, p_high)

    # Scale to [0, 255]
    if p_high > p_low:
        filtered = (filtered - p_low) / (p_high - p_low) * 255.0
    else:
        filtered = np.zeros_like(filtered) + 128.0

    filtered = np.clip(filtered, 0, 255)

    # Apply mask
    result = gray.copy()
    result[mask] = filtered[mask]

    return result.astype(np.uint8)


# =============================================================================
# DYNAMIC RANGE RESTORATION METHODS
# =============================================================================

def restore_log(data: np.ndarray, mask: np.ndarray = None) -> np.ndarray:
    """
    Log Restoration: Scale data so that max maps to log(255).

    Method:
    1. Shift data to be > 0
    2. Find scale factor so max value maps to log(255)
    3. Apply same scale to all pixels
    4. Inverse log to get final values

    Args:
        data: Input array (can have any range including negatives)
        mask: Optional boolean mask - if provided, min/max computed from masked region only

    Returns:
        Restored array in [0, 255] range
    """
    # Step 1: Shift to ensure all values > 0
    # Use masked region for min/max if mask provided
    if mask is not None and mask.sum() > 0:
        min_val = data[mask].min()
    else:
        min_val = data.min()

    shifted = data - min_val + 1.0  # +1 ensures strictly positive

    # Step 2: Find scale factor
    # We want: scale * max(shifted) = log(255)
    # So: scale = log(255) / max(shifted)
    if mask is not None and mask.sum() > 0:
        max_shifted = shifted[mask].max()
    else:
        max_shifted = shifted.max()

    target_log = np.log(255.0)

    if max_shifted > 0:
        scale = target_log / max_shifted
    else:
        scale = 1.0

    # Step 3: Apply scale to all pixels (now in log domain)
    scaled_log = shifted * scale

    # Step 4: Inverse log transform
    restored = np.exp(scaled_log)

    # Clip to valid range
    restored = np.clip(restored, 0, 255)

    return restored


def restore_root(data: np.ndarray, n: float = 2.0, mask: np.ndarray = None) -> np.ndarray:
    """
    Root Restoration: Scale data using nth root mapping.

    Method:
    1. Shift data to be >= 0
    2. Find scale factor so max maps to 255^(1/n)
    3. Apply same scale to all pixels
    4. Raise to power n to get final values

    Args:
        data: Input array (can have any range including negatives)
        n: Root power (default 2.0 for square root)
        mask: Optional boolean mask - if provided, min/max computed from masked region only

    Returns:
        Restored array in [0, 255] range
    """
    # Step 1: Shift to ensure all values >= 0
    if mask is not None and mask.sum() > 0:
        min_val = data[mask].min()
    else:
        min_val = data.min()

    shifted = data - min_val

    # Step 2: Find scale factor
    # We want: scale * max(shifted) = 255^(1/n)
    # So: scale = 255^(1/n) / max(shifted)
    if mask is not None and mask.sum() > 0:
        max_shifted = shifted[mask].max()
    else:
        max_shifted = shifted.max()

    target_root = 255.0 ** (1.0 / n)

    if max_shifted > 0:
        scale = target_root / max_shifted
    else:
        scale = 1.0

    # Step 3: Apply scale to all pixels
    scaled = shifted * scale

    # Step 4: Raise to power n
    restored = scaled ** n

    # Clip to valid range
    restored = np.clip(restored, 0, 255)

    return restored


def restore_linear(data: np.ndarray, clip_percentile: float = 0.5, mask: np.ndarray = None) -> np.ndarray:
    """
    Linear Restoration: Histogram-equalization-like linear stretching.

    Method:
    1. Optionally clip outliers using percentiles
    2. Linear mapping from [min, max] to [0, 255]

    Args:
        data: Input array (can have any range including negatives)
        clip_percentile: Percentile for outlier clipping (0 = no clipping)
        mask: Optional boolean mask - if provided, percentiles computed from masked region only

    Returns:
        Restored array in [0, 255] range
    """
    # Use masked data for percentile calculation if mask provided
    if mask is not None and mask.sum() > 0:
        data_for_stats = data[mask]
    else:
        data_for_stats = data

    if clip_percentile > 0:
        p_low = np.percentile(data_for_stats, clip_percentile)
        p_high = np.percentile(data_for_stats, 100 - clip_percentile)
        clipped = np.clip(data, p_low, p_high)
    else:
        clipped = data.copy()

    # Linear stretch to [0, 255]
    # Use masked data for min/max if available
    if mask is not None and mask.sum() > 0:
        clipped_masked = clipped[mask]
        min_val = clipped_masked.min()
        max_val = clipped_masked.max()
    else:
        min_val = clipped.min()
        max_val = clipped.max()

    if max_val > min_val:
        restored = (clipped - min_val) / (max_val - min_val) * 255.0
    else:
        restored = np.zeros_like(clipped) + 128.0

    restored = np.clip(restored, 0, 255)

    return restored


def restore_gamma_suppress_express(
    data: np.ndarray,
    gamma_bright: float = 2.0,
    gamma_dark: float = 0.5,
    final_restoration: str = 'linear',
    root_n: float = 2.0,
    mask: np.ndarray = None
) -> np.ndarray:
    """
    Gamma-based Suppress-Express Restoration.

    Method:
    1. Shift data to >= 0
    2. Normalize to [0, 1] temporarily
    3. For pixels > average: apply gamma_bright (suppress bright, gamma > 1)
    4. For pixels < average: apply gamma_dark (darken, gamma < 1)
    5. Apply final restoration (log, root, or linear)

    This creates contrast by suppressing very bright areas and
    further darkening dark areas, then restores dynamic range.

    Args:
        data: Input array (can have any range including negatives)
        gamma_bright: Gamma for pixels above average (>1 suppresses)
        gamma_dark: Gamma for pixels below average (<1 darkens further)
        final_restoration: 'log', 'root', or 'linear'
        root_n: Power for root restoration (if used)
        mask: Optional boolean mask - if provided, min/max/mean computed from masked region only

    Returns:
        Restored array in [0, 255] range
    """
    # Step 1: Shift to >= 0
    if mask is not None and mask.sum() > 0:
        min_val = data[mask].min()
    else:
        min_val = data.min()

    shifted = data - min_val

    # Step 2: Normalize to [0, 1]
    if mask is not None and mask.sum() > 0:
        max_val = shifted[mask].max()
    else:
        max_val = shifted.max()

    if max_val > 0:
        normalized = shifted / max_val
    else:
        return np.zeros_like(data) + 128.0

    # Step 3 & 4: Apply different gamma based on average
    if mask is not None and mask.sum() > 0:
        avg = np.mean(normalized[mask])
    else:
        avg = np.mean(normalized)

    result = np.zeros_like(normalized)

    # Pixels above average: suppress with gamma > 1
    # output = input^(1/gamma) where gamma > 1 means power < 1 (brightens)
    # But we want to SUPPRESS, so use input^gamma directly
    bright_mask = normalized >= avg
    dark_mask = ~bright_mask

    # For bright pixels: apply power of gamma_bright (>1 compresses toward 0)
    # Actually for suppression of bright: use gamma > 1 as exponent
    result[bright_mask] = normalized[bright_mask] ** (1.0 / gamma_bright)

    # For dark pixels: apply power of 1/gamma_dark to make them darker
    # gamma_dark < 1 means 1/gamma_dark > 1, so values decrease
    epsilon = 1e-10
    result[dark_mask] = normalized[dark_mask] ** (1.0 / gamma_dark)

    # Step 5: Apply final restoration
    if final_restoration == 'log':
        # Scale back up and apply log restoration
        result = result * max_val + min_val
        restored = restore_log(result, mask=mask)
    elif final_restoration == 'root':
        result = result * max_val + min_val
        restored = restore_root(result, n=root_n, mask=mask)
    else:  # 'linear'
        # Already in [0, 1], just scale to [0, 255]
        restored = result * 255.0

    restored = np.clip(restored, 0, 255)

    return restored


def homomorphic_filter_with_restoration_masked(
    image: np.ndarray,
    mask: np.ndarray,
    d0: float = 30.0,
    gamma_l: float = 0.5,
    gamma_h: float = 2.0,
    restoration: str = 'linear',
    root_n: float = 2.0,
    suppress_gamma_bright: float = 2.0,
    suppress_gamma_dark: float = 0.5,
    suppress_final: str = 'linear'
) -> np.ndarray:
    """
    Homomorphic Filter with selectable dynamic range restoration methods.

    Args:
        image: Input grayscale image
        mask: Boolean mask for region of interest
        d0: Cutoff frequency for Gaussian high-pass filter
        gamma_l: Gain for low frequencies (< 1 to compress illumination)
        gamma_h: Gain for high frequencies (> 1 to enhance reflectance)
        restoration: Restoration method - 'log', 'root', 'linear', or 'gamma_suppress'
        root_n: Power for root restoration (only used if restoration='root')
        suppress_gamma_bright: Gamma for bright pixels (only if restoration='gamma_suppress')
        suppress_gamma_dark: Gamma for dark pixels (only if restoration='gamma_suppress')
        suppress_final: Final restoration after gamma suppress ('log', 'root', 'linear')

    Returns:
        Filtered image (uint8)

    Restoration Methods:
        'log': Maps max to log(255), applies exp() - good for high dynamic range
        'root': Maps max to 255^(1/n), raises to power n - adjustable compression
        'linear': Simple linear stretch to [0, 255] - histogram equalization style
        'gamma_suppress': Suppresses bright, darkens dark, then applies final restoration
    """
    gray = rgb2gray(image)
    gray = ensure_float32(gray)

    # Homomorphic filtering in log domain
    epsilon = 1.0
    gray_safe = np.maximum(gray, epsilon)

    # Fill outside-mask with mean of inside-mask to reduce FFT boundary artifacts
    gray_prepared = gray_safe.copy()
    if mask.sum() > 0:
        mean_inside = np.mean(gray_safe[mask])
        gray_prepared[~mask] = mean_inside

    log_img = np.log(gray_prepared)

    # FFT
    rows, cols = gray.shape
    f_transform = np.fft.fft2(log_img)
    f_shift = np.fft.fftshift(f_transform)

    # Create Gaussian high-pass filter
    crow, ccol = rows // 2, cols // 2
    u = np.arange(rows) - crow
    v = np.arange(cols) - ccol
    V, U = np.meshgrid(v, u)
    D = np.sqrt(U**2 + V**2)

    # Gaussian HPF
    H_hp = 1.0 - np.exp(-D**2 / (2.0 * d0**2))
    H = gamma_l + (gamma_h - gamma_l) * H_hp

    # Apply filter
    filtered_shift = f_shift * H
    f_ishift = np.fft.ifftshift(filtered_shift)
    filtered_log = np.fft.ifft2(f_ishift)
    filtered_log = np.real(filtered_log)

    # Inverse log transform (this may produce dark/negative values)
    filtered = np.exp(filtered_log) - epsilon

    # Apply selected restoration method - pass mask so statistics are computed from masked region
    if restoration == 'log':
        restored = restore_log(filtered, mask=mask)
    elif restoration == 'root':
        restored = restore_root(filtered, n=root_n, mask=mask)
    elif restoration == 'gamma_suppress':
        restored = restore_gamma_suppress_express(
            filtered,
            gamma_bright=suppress_gamma_bright,
            gamma_dark=suppress_gamma_dark,
            final_restoration=suppress_final,
            root_n=root_n,
            mask=mask
        )
    else:  # 'linear' (default)
        restored = restore_linear(filtered, mask=mask)

    # Apply mask
    result = gray.copy()
    result[mask] = restored[mask]

    return result.astype(np.uint8)


def bilateral_filter_masked(image: np.ndarray, mask: np.ndarray,
                            d: int = 9, sigmaColor: float = 75.0,
                            sigmaSpace: float = 75.0) -> np.ndarray:
    """
    CORRECTED: Apply bilateral filter only within masked region.

    Now prepares the image by filling outside-mask regions before filtering
    to avoid contamination.
    """
    # Convert to grayscale if needed
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image.copy()

    # Prepare masked image
    masked_img = gray.copy()
    if mask.sum() > 0:
        mean_inside = int(np.mean(gray[mask]))
        masked_img[~mask] = mean_inside

    # Apply bilateral filter
    filtered = cv2.bilateralFilter(masked_img, d, sigmaColor, sigmaSpace)

    # Apply only within mask
    result = gray.copy()
    result[mask] = filtered[mask]

    return result


def otsu_threshold_global(image: np.ndarray) -> np.ndarray:
    """
    Apply global Otsu thresholding.

    Args:
        image: Input grayscale image

    Returns:
        Binary thresholded image
    """
    # Convert to grayscale if needed
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image.copy()

    # Apply Otsu's thresholding
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return binary


def otsu_threshold_global_masked(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    Apply global Otsu thresholding using only masked pixels for threshold computation.

    The Otsu threshold is computed from the histogram of pixels inside the mask,
    then applied to the whole image, and only the masked region is written to result.

    Args:
        image: Input grayscale image
        mask:  Boolean mask (True = region of interest)

    Returns:
        Binary thresholded image (uint8, 0/255). Outside mask is preserved from input.
    """
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image.copy()

    if gray.dtype != np.uint8:
        gray = np.clip(gray, 0, 255).astype(np.uint8)

    masked_pixels = gray[mask]
    if len(masked_pixels) == 0:
        return gray

    # Compute Otsu threshold from masked pixels only
    thresh_val, _ = cv2.threshold(masked_pixels, 0, 255,
                                   cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Apply that threshold to the full image
    binary = np.where(gray >= thresh_val, np.uint8(255), np.uint8(0))

    result = gray.copy()
    result[mask] = binary[mask]
    return result


def otsu_threshold_local(image: np.ndarray, block_size: int = 35, C: float = 2.0) -> np.ndarray:
    """
    Apply local (adaptive) Otsu thresholding.

    Args:
        image: Input grayscale image
        block_size: Size of pixel neighborhood (must be odd)
        C: Constant subtracted from weighted mean

    Returns:
        Binary thresholded image
    """
    # Convert to grayscale if needed
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image.copy()

    # Ensure block_size is odd
    if block_size % 2 == 0:
        block_size += 1

    # Apply adaptive thresholding
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, block_size, C
    )

    return binary


def otsu_threshold_local_masked(image: np.ndarray, mask: np.ndarray,
                                 block_size: int = 35, C: float = 2.0) -> np.ndarray:
    """
    Apply local (adaptive) thresholding only to the masked region.

    Outside-mask pixels are filled with the mean of the masked region before
    running cv2.adaptiveThreshold so that blocks overlapping the mask boundary
    are not corrupted by black pixels.  Only the masked region of the result
    is written; outside-mask pixels are preserved from the input.

    Args:
        image:      Input grayscale image
        mask:       Boolean mask (True = region of interest)
        block_size: Size of pixel neighbourhood (must be odd)
        C:          Constant subtracted from weighted mean

    Returns:
        Binary thresholded image (uint8, 0/255). Outside mask preserved.
    """
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image.copy()

    if gray.dtype != np.uint8:
        gray = np.clip(gray, 0, 255).astype(np.uint8)

    if block_size % 2 == 0:
        block_size += 1

    # Fill outside mask so adaptive window is not corrupted
    prepared = gray.copy()
    if mask.sum() > 0:
        mean_inside = int(np.mean(gray[mask]))
        prepared[~mask] = mean_inside

    binary = cv2.adaptiveThreshold(
        prepared, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, block_size, C
    )

    result = gray.copy()
    result[mask] = binary[mask]
    return result


# Wrapper functions for restoration methods to work with masks
def restore_log_masked(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    Apply log restoration only to masked region.

    Min/max are calculated from the masked region only, ensuring
    the restoration is based on the actual data in the ROI.
    """
    gray = rgb2gray(image)
    gray = ensure_float32(gray)

    # Apply restoration with mask - min/max calculated from masked region
    restored = restore_log(gray, mask=mask)

    # Apply mask
    result = gray.copy()
    result[mask] = restored[mask]

    return result.astype(np.uint8)


def restore_root_masked(image: np.ndarray, mask: np.ndarray, n: float = 2.0) -> np.ndarray:
    """
    Apply root restoration only to masked region.

    Min/max are calculated from the masked region only.
    """
    gray = rgb2gray(image)
    gray = ensure_float32(gray)

    # Apply restoration with mask - min/max calculated from masked region
    restored = restore_root(gray, n=n, mask=mask)

    # Apply mask
    result = gray.copy()
    result[mask] = restored[mask]

    return result.astype(np.uint8)


def restore_linear_masked(image: np.ndarray, mask: np.ndarray, clip_percentile: float = 0.5) -> np.ndarray:
    """
    Apply linear restoration only to masked region.

    Percentiles and min/max are calculated from the masked region only.
    """
    gray = rgb2gray(image)
    gray = ensure_float32(gray)

    # Apply restoration with mask - percentiles/min/max calculated from masked region
    restored = restore_linear(gray, clip_percentile=clip_percentile, mask=mask)

    # Apply mask
    result = gray.copy()
    result[mask] = restored[mask]

    return result.astype(np.uint8)


def restore_gamma_suppress_masked(
        image: np.ndarray,
        mask: np.ndarray,
        gamma_bright: float = 2.0,
        gamma_dark: float = 0.5,
        final_restoration: str = 'linear',
        root_n: float = 2.0
) -> np.ndarray:
    """
    Apply gamma suppress-express restoration only to masked region.

    Min/max/mean are calculated from the masked region only.
    """
    gray = rgb2gray(image)
    gray = ensure_float32(gray)

    # Apply restoration with mask - statistics calculated from masked region
    restored = restore_gamma_suppress_express(
        gray,
        gamma_bright=gamma_bright,
        gamma_dark=gamma_dark,
        final_restoration=final_restoration,
        root_n=root_n,
        mask=mask
    )

    # Apply mask
    result = gray.copy()
    result[mask] = restored[mask]

    return result.astype(np.uint8)


# Morphological operation wrappers - CORRECTED
def morphology_dilate_masked(
        image: np.ndarray,
        mask: np.ndarray,
        kernel_size: int = 5,
        kernel_shape: str = 'ellipse'
) -> np.ndarray:
    """
    CORRECTED: Apply dilation only to masked region.

    Now properly handles the mask by only dilating pixels inside the mask,
    preventing contamination from outside pixels.
    """
    gray = rgb2gray(image)
    if gray.dtype != np.uint8:
        gray = ensure_float32(gray).astype(np.uint8)

    # Create kernel
    if kernel_shape == 'ellipse':
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    else:  # rectangle
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))

    # Prepare masked image: set outside to 0 (minimum) so dilation doesn't spread from outside
    masked_img = np.zeros_like(gray)
    masked_img[mask] = gray[mask]

    # Apply dilation
    dilated = cv2.dilate(masked_img, kernel)

    # Apply mask to result
    result = gray.copy()
    result[mask] = dilated[mask]

    return result


def morphology_erode_masked(
        image: np.ndarray,
        mask: np.ndarray,
        kernel_size: int = 5,
        kernel_shape: str = 'ellipse'
) -> np.ndarray:
    """
    CORRECTED: Apply erosion only to masked region.

    Now properly handles the mask by only eroding pixels inside the mask,
    preventing contamination from outside pixels.
    """
    gray = rgb2gray(image)
    if gray.dtype != np.uint8:
        gray = ensure_float32(gray).astype(np.uint8)

    # Create kernel
    if kernel_shape == 'ellipse':
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    else:  # rectangle
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))

    # Prepare masked image: set outside to 255 (maximum) so erosion doesn't spread from outside
    masked_img = np.full_like(gray, 255)
    masked_img[mask] = gray[mask]

    # Apply erosion
    eroded = cv2.erode(masked_img, kernel)

    # Apply mask to result
    result = gray.copy()
    result[mask] = eroded[mask]

    return result


# =============================================================================
# LAB COLOR SPACE OPERATIONS
# =============================================================================

def bgr_to_lab(image: np.ndarray) -> np.ndarray:
    """
    Convert BGR image to LAB color space.

    Args:
        image: Input BGR image (uint8 or float32)

    Returns:
        LAB image (float32 with L in [0, 100], a/b in [-127, 127])
    """
    if image.dtype != np.uint8:
        image = ensure_float32(image).astype(np.uint8)

    # OpenCV expects BGR input and returns LAB with L in [0, 100]
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)

    return lab.astype(np.float32)


def lab_to_bgr(lab_image: np.ndarray) -> np.ndarray:
    """
    Convert LAB image back to BGR color space.

    Args:
        lab_image: LAB image (float32)

    Returns:
        BGR image (uint8)
    """
    # Ensure proper range and type
    lab = lab_image.copy()

    # Clip L to [0, 100] and a,b to valid ranges
    lab[:, :, 0] = np.clip(lab[:, :, 0], 0, 100)
    lab[:, :, 1] = np.clip(lab[:, :, 1], -127, 127)
    lab[:, :, 2] = np.clip(lab[:, :, 2], -127, 127)

    # Convert to uint8 for cv2.cvtColor
    lab_uint8 = lab.astype(np.uint8)

    bgr = cv2.cvtColor(lab_uint8, cv2.COLOR_LAB2BGR)

    return bgr


def apply_gamma_to_lab_L(
        image: np.ndarray,
        mask: np.ndarray,
        gamma: float
) -> np.ndarray:
    """
    Apply gamma correction to the L channel of LAB color space within mask.

    The L channel represents lightness (0-100). Gamma correction adjusts
    brightness while preserving color information in a and b channels.

    Args:
        image: Input BGR image (uint8 or float32)
        mask: Boolean mask (True = process this region)
        gamma: Gamma value (0.5 to 6.0)
               > 1.0 = brighten
               = 1.0 = no change
               < 1.0 = darken

    Returns:
        BGR image with gamma applied to L channel within mask (uint8)
    """
    # Ensure BGR uint8
    if image.dtype != np.uint8:
        img_uint8 = ensure_float32(image).astype(np.uint8)
    else:
        img_uint8 = image.copy()

    # Convert to LAB
    lab = bgr_to_lab(img_uint8)

    # Extract L channel and scale to [0, 255] for gamma LUT
    L_channel = lab[:, :, 0].copy()
    L_scaled = (L_channel * 2.55).astype(np.uint8)  # Scale [0, 100] to [0, 255]

    # Apply gamma using LUT
    power = 1.0 / gamma
    lut = np.array([((i / 255.0) ** power) * 255.0 for i in range(256)], dtype=np.uint8)
    L_corrected_scaled = lut[L_scaled]

    # Scale back to [0, 100] for LAB
    L_corrected = (L_corrected_scaled / 2.55).astype(np.float32)

    # Apply only within mask
    L_result = L_channel.copy()
    L_result[mask] = L_corrected[mask]

    # Merge back into LAB
    lab[:, :, 0] = L_result

    # Convert back to BGR
    bgr_result = lab_to_bgr(lab)

    return bgr_result


def apply_clahe_to_lab_L(
        image: np.ndarray,
        mask: np.ndarray,
        clip_limit: float = 2.0,
        tile_grid_size: Tuple[int, int] = (8, 8)
) -> np.ndarray:
    """
    Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to the L channel
    of LAB color space within mask.

    CLAHE improves local contrast while preserving color. Works well for images
    with varying lighting conditions.

    Args:
        image: Input BGR image (uint8 or float32)
        mask: Boolean mask (True = process this region)
        clip_limit: Threshold for contrast limiting (1.0-4.0 typical)
                   Higher values = more contrast
        tile_grid_size: Size of grid for histogram equalization (e.g., (8, 8))
                       Smaller tiles = more local adaptation

    Returns:
        BGR image with CLAHE applied to L channel within mask (uint8)
    """
    # Ensure BGR uint8
    if image.dtype != np.uint8:
        img_uint8 = ensure_float32(image).astype(np.uint8)
    else:
        img_uint8 = image.copy()

    # Convert to LAB
    lab = bgr_to_lab(img_uint8)

    # Extract L channel and scale to [0, 255] for CLAHE
    L_channel = lab[:, :, 0].copy()
    L_scaled = (L_channel * 2.55).astype(np.uint8)  # Scale [0, 100] to [0, 255]

    # Create masked version for CLAHE
    L_masked = L_scaled.copy()
    L_masked[~mask] = 127  # Fill outside mask with neutral gray

    # Apply CLAHE
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    L_clahe = clahe.apply(L_masked)

    # Apply only within mask
    L_result_scaled = L_scaled.copy()
    L_result_scaled[mask] = L_clahe[mask]

    # Scale back to [0, 100] for LAB
    L_result = (L_result_scaled / 2.55).astype(np.float32)

    # Merge back into LAB
    lab[:, :, 0] = L_result

    # Convert back to BGR
    bgr_result = lab_to_bgr(lab)

    return bgr_result


def apply_clahe_to_bgr_channels(
        image: np.ndarray,
        mask: np.ndarray,
        channels: List[str],
        clip_limit: float = 2.0,
        tile_grid_size: Tuple[int, int] = (8, 8)
) -> np.ndarray:
    """
    Apply CLAHE to selected BGR channels within mask.

    This applies CLAHE independently to chosen color channels. Can enhance
    specific color features while preserving others.

    Args:
        image: Input BGR image (uint8 or float32)
        mask: Boolean mask (True = process this region)
        channels: List of channel names to process: "blue", "green", "red"
                 Can be any combination, e.g., ["red", "green"] or ["blue"]
        clip_limit: Threshold for contrast limiting (1.0-4.0 typical)
                   Higher values = more contrast
        tile_grid_size: Size of grid for histogram equalization (e.g., (8, 8))
                       Smaller tiles = more local adaptation

    Returns:
        BGR image with CLAHE applied to selected channels within mask (uint8)

    Example:
        # Enhance only red and green channels
        result = apply_clahe_to_bgr_channels(
            img, mask, channels=["red", "green"],
            clip_limit=3.0, tile_grid_size=(8, 8)
        )
    """
    # Ensure BGR uint8
    if image.dtype != np.uint8:
        img_uint8 = ensure_float32(image).astype(np.uint8)
    else:
        img_uint8 = image.copy()

    # Split into BGR channels
    b, g, r = cv2.split(img_uint8)
    channel_map = {
        "blue": (b, 0),
        "green": (g, 1),
        "red": (r, 2)
    }

    # Validate channels
    valid_channels = {"blue", "green", "red"}
    for ch in channels:
        if ch.lower() not in valid_channels:
            raise ValueError(f"Invalid channel '{ch}'. Must be one of: blue, green, red")

    # Create CLAHE object
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)

    # Process each requested channel
    result_channels = [b.copy(), g.copy(), r.copy()]

    for channel_name in channels:
        ch_name = channel_name.lower()
        channel_data, channel_idx = channel_map[ch_name]

        # Create masked version
        ch_masked = channel_data.copy()
        ch_masked[~mask] = 127  # Fill outside mask with neutral gray

        # Apply CLAHE
        ch_clahe = clahe.apply(ch_masked)

        # Apply only within mask
        ch_result = channel_data.copy()
        ch_result[mask] = ch_clahe[mask]

        result_channels[channel_idx] = ch_result

    # Merge channels back
    bgr_result = cv2.merge(result_channels)

    return bgr_result


# =============================================================================
# MORPHOLOGICAL OPERATIONS
# =============================================================================


def morphology_open_masked(
        image: np.ndarray,
        mask: np.ndarray,
        kernel_size: int = 5,
        kernel_shape: str = 'ellipse'
) -> np.ndarray:
    """
    CORRECTED: Apply morphological opening only to masked region.

    Opening = erosion followed by dilation. Now properly masks both operations.
    """
    gray = rgb2gray(image)
    if gray.dtype != np.uint8:
        gray = ensure_float32(gray).astype(np.uint8)

    # Create kernel
    if kernel_shape == 'ellipse':
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    else:  # rectangle
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))

    # For opening: erode then dilate
    # Erosion: set outside to 255 (max)
    masked_img_erode = np.full_like(gray, 255)
    masked_img_erode[mask] = gray[mask]
    eroded = cv2.erode(masked_img_erode, kernel)

    # Dilation: set outside to 0 (min)
    masked_img_dilate = np.zeros_like(gray)
    masked_img_dilate[mask] = eroded[mask]
    opened = cv2.dilate(masked_img_dilate, kernel)

    # Apply mask to result
    result = gray.copy()
    result[mask] = opened[mask]

    return result


def morphology_close_masked(
        image: np.ndarray,
        mask: np.ndarray,
        kernel_size: int = 5,
        kernel_shape: str = 'ellipse'
) -> np.ndarray:
    """
    CORRECTED: Apply morphological closing only to masked region.

    Closing = dilation followed by erosion. Now properly masks both operations.
    """
    gray = rgb2gray(image)
    if gray.dtype != np.uint8:
        gray = ensure_float32(gray).astype(np.uint8)

    # Create kernel
    if kernel_shape == 'ellipse':
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    else:  # rectangle
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))

    # For closing: dilate then erode
    # Dilation: set outside to 0 (min)
    masked_img_dilate = np.zeros_like(gray)
    masked_img_dilate[mask] = gray[mask]
    dilated = cv2.dilate(masked_img_dilate, kernel)

    # Erosion: set outside to 255 (max)
    masked_img_erode = np.full_like(gray, 255)
    masked_img_erode[mask] = dilated[mask]
    closed = cv2.erode(masked_img_erode, kernel)

    # Apply mask to result
    result = gray.copy()
    result[mask] = closed[mask]

    return result

# =============================================================================
# POLAR UNWRAP (ANNULAR → RECTANGULAR)
# =============================================================================

def polar_unwrap(
    image: np.ndarray,
    center: tuple,
    inner_radius: float,
    radial_depth: int = 30,
    angular_samples: int = 0,
) -> np.ndarray:
    """
    Unwrap an annular band into a rectangular (trapezoidal) strip.

    Scans radially **outward** from *inner_radius* for *radial_depth* pixels
    and maps the full 360° sweep into a 2-D image whose:
        - width  = number of angular samples (default: circumference at mid-radius)
        - height = radial_depth  (row 0 = inner_radius, row H-1 = inner_radius + radial_depth - 1)

    The output image is oriented so that **row 0 corresponds to the
    outermost radius** (inner_radius + radial_depth − 1) and **the last
    row (bottom) corresponds to inner_radius**.  This makes "height from
    the bottom" equal to radial distance from the inner radius.

    Args:
        image:           Input image (grayscale uint8 or float, or RGB/BGR).
        center:          (cx, cy) centre of the annular region.
        inner_radius:    Start radius of the band (pixels).
        radial_depth:    Number of pixels to scan outward (height of output).
        angular_samples: Width of the output strip.  0 → auto (circumference
                         at the mid-radius).

    Returns:
        Rectangular image of shape (radial_depth, angular_samples [, C]).
        Row 0 = outer edge, last row = inner edge.
    """
    cx, cy = center

    if angular_samples <= 0:
        mid_r = inner_radius + radial_depth / 2.0
        angular_samples = int(round(2.0 * np.pi * mid_r))
        angular_samples = max(angular_samples, 1)

    is_color = (image.ndim == 3)
    h_img, w_img = image.shape[:2]

    if is_color:
        out = np.zeros((radial_depth, angular_samples, image.shape[2]),
                        dtype=image.dtype)
    else:
        out = np.zeros((radial_depth, angular_samples), dtype=image.dtype)

    angles = np.linspace(0, 2.0 * np.pi, angular_samples, endpoint=False)

    for ri in range(radial_depth):
        # ri = 0 → inner_radius,  ri = radial_depth-1 → outer edge
        r = inner_radius + ri
        xs = (cx + r * np.cos(angles)).astype(np.float32)
        ys = (cy + r * np.sin(angles)).astype(np.float32)

        # Clamp to image bounds
        xs = np.clip(xs, 0, w_img - 1)
        ys = np.clip(ys, 0, h_img - 1)

        # Bilinear interpolation via cv2.remap requires map arrays
        # For a single row it's simpler to just round and index
        xi = np.clip(np.round(xs).astype(int), 0, w_img - 1)
        yi = np.clip(np.round(ys).astype(int), 0, h_img - 1)

        # Output row:  flip so that row 0 = outer, last row = inner
        out_row = radial_depth - 1 - ri
        if is_color:
            out[out_row] = image[yi, xi]
        else:
            out[out_row] = image[yi, xi]

    return out


# =============================================================================
# LOCALISED OTSU WITH SEPARATE BLOCK HEIGHT AND WIDTH
# =============================================================================

def otsu_threshold_local_block(
    image: np.ndarray,
    block_height: int = 30,
    block_width: int = 0,
) -> np.ndarray:
    """
    Block-based localised Otsu thresholding with independent height and width.

    Divides the image into non-overlapping rectangular blocks of size
    (block_height × block_width), computes an Otsu threshold per block,
    and applies it.  This is **not** cv2.adaptiveThreshold; it genuinely
    runs Otsu on each block independently.

    Args:
        image:        Input grayscale image (uint8).
        block_height: Height of each block in pixels.
        block_width:  Width of each block in pixels.
                      0 → auto = image_width / 12 (rounded to nearest odd).

    Returns:
        Binary image (0 / 255, uint8).
    """
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image.copy()

    if gray.dtype != np.uint8:
        gray = np.clip(gray, 0, 255).astype(np.uint8)

    h, w = gray.shape

    if block_width <= 0:
        block_width = max(3, int(round(w / 12.0)))
    # Ensure odd (some algorithms prefer it, and it's fine for Otsu too)
    if block_width % 2 == 0:
        block_width += 1
    if block_height % 2 == 0:
        block_height += 1

    result = np.zeros_like(gray)

    for y0 in range(0, h, block_height):
        y1 = min(y0 + block_height, h)
        for x0 in range(0, w, block_width):
            x1 = min(x0 + block_width, w)
            block = gray[y0:y1, x0:x1]

            # Otsu on this block
            if block.size == 0:
                continue
            # cv2.threshold with OTSU flag computes the optimal threshold
            thresh_val, binary_block = cv2.threshold(
                block, 0, 255,
                cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
            result[y0:y1, x0:x1] = binary_block

    return result


def otsu_threshold_local_block_masked(
    image: np.ndarray,
    mask: np.ndarray,
    block_height: int = 30,
    block_width: int = 0,
) -> np.ndarray:
    """
    Block-based localised Otsu thresholding, mask-aware.

    For each block, Otsu is computed from **only the masked pixels** in that
    block.  If a block has no masked pixels the output for that block is 0.
    Outside-mask pixels in the result are preserved from the input.

    Args:
        image:        Input grayscale image (uint8).
        mask:         Boolean mask (True = region of interest).
        block_height: Height of each block in pixels.
        block_width:  Width of each block in pixels.
                      0 → auto = image_width / 12 (rounded to nearest odd).

    Returns:
        Binary image (0 / 255, uint8). Outside mask is preserved from input.
    """
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image.copy()

    if gray.dtype != np.uint8:
        gray = np.clip(gray, 0, 255).astype(np.uint8)

    h, w = gray.shape

    if block_width <= 0:
        block_width = max(3, int(round(w / 12.0)))
    if block_width % 2 == 0:
        block_width += 1
    if block_height % 2 == 0:
        block_height += 1

    result = gray.copy()  # preserve outside mask

    for y0 in range(0, h, block_height):
        y1 = min(y0 + block_height, h)
        for x0 in range(0, w, block_width):
            x1 = min(x0 + block_width, w)
            block = gray[y0:y1, x0:x1]
            block_mask = mask[y0:y1, x0:x1]

            masked_pixels = block[block_mask]
            if len(masked_pixels) < 2:
                # Not enough pixels for Otsu — leave as-is
                continue

            # Compute Otsu threshold from masked pixels only
            thresh_val, _ = cv2.threshold(
                masked_pixels, 0, 255,
                cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )

            # Apply threshold to the whole block, then write only masked pixels
            binary_block = np.where(block >= thresh_val, np.uint8(255), np.uint8(0))
            # Write only where mask is True
            result[y0:y1, x0:x1][block_mask] = binary_block[block_mask]

    return result

def find_flipover_row(
    binary_image: np.ndarray,
    white_threshold: float = 0.5,
    confirmation_rows: int = 2,
) -> dict:
    """
    Scan a binary image from the bottom upward to find the row where
    a definitive changeover from black-majority to white-majority occurs.

    "Definitive" means that *confirmation_rows* consecutive rows above the
    transition all show a white-majority (fraction of white pixels ≥
    *white_threshold*), while the rows at and below the transition are
    black-majority.

    Args:
        binary_image:      Binary image (0/255 uint8).  Should be the
                           output of a thresholding step.
        white_threshold:   Fraction ≥ this counts as "white-majority" row.
        confirmation_rows: How many successive white-majority rows are
                           needed to confirm the flipover.

    Returns:
        Dictionary with:
            'flipover_height'  : int — height (in pixels) from the bottom
                                  of the image where the changeover starts.
                                  -1 if no flipover detected.
            'flipover_row'     : int — row index (0-based from top) of the
                                  changeover.  -1 if none.
            'row_white_fractions': list[float] — per-row white fraction,
                                  ordered from row 0 (top) to last row.
    """
    if binary_image.ndim == 3:
        gray = cv2.cvtColor(binary_image, cv2.COLOR_RGB2GRAY)
    else:
        gray = binary_image.copy()

    h, w = gray.shape

    # Compute per-row white fraction
    row_white = np.zeros(h, dtype=np.float64)
    for r in range(h):
        row_white[r] = np.sum(gray[r] > 127) / w

    # Scan from bottom (row h-1) upward
    # We're looking for: rows at bottom are black-majority,
    # at some point they flip to white-majority for ≥ confirmation_rows
    flipover_row = -1

    for r in range(h - 1, confirmation_rows - 1, -1):
        # Check if this row is still black-majority
        if row_white[r] >= white_threshold:
            continue

        # This row is black-majority.  Check if the *confirmation_rows*
        # rows above (r-1, r-2, …) are all white-majority.
        all_white = True
        for cr in range(1, confirmation_rows + 1):
            check_row = r - cr
            if check_row < 0 or row_white[check_row] < white_threshold:
                all_white = False
                break

        if all_white:
            # Row r is the last black row; the flipover starts at r
            # (i.e. the boundary between black and white regions).
            flipover_row = r
            break

    if flipover_row >= 0:
        flipover_height = h - 1 - flipover_row
    else:
        flipover_height = -1

    return {
        'flipover_height': flipover_height,
        'flipover_row': flipover_row,
        'row_white_fractions': row_white.tolist(),
    }


# =============================================================================
# MAIN DEMONSTRATION
# =============================================================================

# if __name__ == "__main__":
#     # Load image
#     filename = 'C:/AutoCompanyImages/DOSTPLUS/LHS/2 - Hub and Bottom Bearing - 1.png'
#     img = plt.imread(filename)
#
#     # Create annular mask
#     center = (635, 360)
#     outer_radius = 230
#     inner_radius = 130
#
#     gray = rgb2gray(img)
#     mask = create_annular_mask(gray.shape, center, outer_radius, inner_radius)
#
#     print(f"Annular mask created:")
#     print(f"  Center: {center}")
#     print(f"  Outer radius: {outer_radius}")
#     print(f"  Inner radius: {inner_radius}")
#     print(f"  Pixels in annular: {mask.sum()}")
#
#     # Apply all normalizations INCLUDING GAMMA (CORRECTED LABELS)
#     results = {
#         'Original': gray,
#         'Background Norm\n(sx=15, sy=15)': pixBackgroundNorm_masked(
#             img, mask, sx=15, sy=15, bgval=200
#         ),
#         'Background Simple\n(size=50)': pixBackgroundNormSimple_masked(
#             img, mask, size=50, bgval=200
#         ),
#         'Contrast Norm\n(sx=10, mindiff=30)': pixContrastNorm_masked(
#             img, mask, sx=10, sy=10, mindiff=30
#         ),
#         'Contrast Norm\n(sx=6, mindiff=15)': pixContrastNorm_masked(
#             img, mask, sx=6, sy=6, mindiff=15
#         ),
#         'Gray Normalize': pixGrayNormalize_masked(img, mask),
#         'Rank Filter (5%)\n(size=31)': pixRankFilterGray_masked(
#             img, mask, size=31, rank=0.05
#         ),
#         'Rank Filter (95%)\n(size=31)': pixRankFilterGray_masked(
#             img, mask, size=31, rank=0.95
#         ),
#         'Unsharp Mask\n(hw=5, fract=2.5)': pixUnsharpMaskingGray_masked(
#             img, mask, halfwidth=5, fract=2.5
#         ),
#         'Histogram Eq': pixEqualizeHistogram_masked(img, mask),
#         'Gamma 2.0\n(brighten)': pixGammaCorrection_masked(img, mask, gamma=2.0),
#         'Gamma 0.5\n(darken)': pixGammaCorrection_masked(img, mask, gamma=0.5)
#     }
#
#     # Display with 4x4 grid - FIXED LABEL VISIBILITY
#     fig, axs = plt.subplots(4, 4, figsize=(20, 20))
#     axs = axs.ravel()
#
#     # Show mask in first position
#     mask_overlay = gray.copy()
#     mask_overlay = np.stack([mask_overlay]*3, axis=2).astype(np.uint8)
#     mask_overlay[mask, 0] = 255
#     axs[0].imshow(mask_overlay)
#     axs[0].set_title('Annular Mask\n(Red = Processing Region)', fontsize=11, fontweight='bold', pad=12)
#     axs[0].axis('off')
#
#     # Show ALL results with proper labels
#     for idx, (title, result) in enumerate(results.items(), start=1):
#         axs[idx].imshow(result, cmap='gray', vmin=0, vmax=255)
#         # CRITICAL FIX: Increased pad value and font size
#         axs[idx].set_title(title, fontsize=11, fontweight='bold', pad=12)
#         axs[idx].axis('off')
#         axs[idx].contour(mask, levels=[0.5], colors='red', linewidths=1, alpha=0.5)
#
#     # Hide unused subplots
#     for idx in range(13, 16):
#         axs[idx].axis('off')
#
#     # CRITICAL FIX: Use subplots_adjust instead of tight_layout
#     # This gives precise control over spacing
#     plt.subplots_adjust(
#         hspace=0.35,  # Vertical spacing between rows (MORE space for titles!)
#         wspace=0.12,  # Horizontal spacing
#         top=0.93,     # Top margin
#         bottom=0.03,  # Bottom margin
#         left=0.02,    # Left margin
#         right=0.98    # Right margin
#     )
#
#     plt.savefig('annular_normalizations_corrected.png', dpi=150)
#     plt.show()
#
#     # =========================================================================
#     # Show GAMMA VARIATIONS (CORRECTED)
#     # =========================================================================
#
#     print("\n=== Testing Gamma Variations (CORRECTED) ===")
#     gamma_values = [0.5, 0.75, 1.0, 1.5, 2.0, 3.0]
#
#     fig, axs = plt.subplots(2, 3, figsize=(18, 12))
#     axs = axs.ravel()
#
#     for idx, gamma in enumerate(gamma_values):
#         result = pixGammaCorrection_masked(img, mask, gamma=gamma)
#         axs[idx].imshow(result, cmap='gray', vmin=0, vmax=255)
#
#         # CORRECTED LABELS
#         if gamma > 1.0:
#             effect = "brighter"
#         elif gamma < 1.0:
#             effect = "darker"
#         else:
#             effect = "no change"
#
#         axs[idx].set_title(f'Gamma = {gamma} ({effect})', fontsize=12, fontweight='bold')
#         axs[idx].axis('off')
#         axs[idx].contour(mask, levels=[0.5], colors='red', linewidths=1, alpha=0.5)
#
#     plt.tight_layout()
#     plt.savefig('annular_gamma_variations_corrected.png', dpi=150)
#     plt.show()
#
#     # =========================================================================
#     # Show zoomed comparison
#     # =========================================================================
#
#     y_min = max(0, center[1] - outer_radius)
#     y_max = min(gray.shape[0], center[1] + outer_radius)
#     x_min = max(0, center[0] - outer_radius)
#     x_max = min(gray.shape[1], center[0] + outer_radius)
#
#     best_methods = {
#         'Original': gray[y_min:y_max, x_min:x_max],
#         'Contrast Norm\n(sx=6, mindiff=15)': pixContrastNorm_masked(
#             img, mask, sx=6, sy=6, mindiff=15
#         )[y_min:y_max, x_min:x_max],
#         'Gamma 2.0 + Contrast': pixContrastNorm_masked(
#             pixGammaCorrection_masked(img, mask, gamma=2.0),
#             mask, sx=6, sy=6, mindiff=15
#         )[y_min:y_max, x_min:x_max],
#         'Gamma 2.0 + Unsharp': pixUnsharpMaskingGray_masked(
#             pixGammaCorrection_masked(img, mask, gamma=2.0),
#             mask, halfwidth=3, fract=2.0
#         )[y_min:y_max, x_min:x_max]
#     }
#
#     fig, axs = plt.subplots(1, 4, figsize=(20, 5))
#
#     for idx, (title, result) in enumerate(best_methods.items()):
#         axs[idx].imshow(result, cmap='gray', vmin=0, vmax=255)
#         axs[idx].set_title(title, fontsize=12, fontweight='bold')
#         axs[idx].axis('off')
#
#         mask_crop = mask[y_min:y_max, x_min:x_max]
#         axs[idx].contour(mask_crop, levels=[0.5], colors='red', linewidths=1.5, alpha=0.6)
#
#     plt.tight_layout()
#     plt.savefig('annular_best_methods_corrected.png', dpi=150)
#     plt.show()
#
#     print("\n=== Processing Complete ===")
#     print("Images saved:")
#     print("  - annular_normalizations_corrected.png (ALL LABELS VISIBLE)")
#     print("  - annular_gamma_variations_corrected.png")
#     print("  - annular_best_methods_corrected.png")
#
#     print(f"\n=== Gamma Convention (CORRECTED) ===")
#     print(f"Formula: output = 255 × (input/255)^(1/gamma)")
#     print(f"  gamma > 1.0 → BRIGHTENS (applies power < 1)")
#     print(f"  gamma = 1.0 → no change")
#     print(f"  gamma < 1.0 → DARKENS (applies power > 1)")
#     print(f"\nAvailable gamma values: {list(GAMMA_LUT.gamma_values)}")